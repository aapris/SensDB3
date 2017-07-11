# -*- coding: utf-8 -*-

import datetime
import time
import pytz
import dateutil.parser
import re
from dateutil import tz
import json

from django.db import transaction
from django.db.models import Count
from django.core.management.base import BaseCommand

from sensdb3.models import Datalogger, Data, Unit
from sensdb3.models import update_grouplogger_aggregates
from sensdb3.models import Datapost
from .tools import check_alerts
from .tools import apply_filter

import logging
log = logging.getLogger('datapost')


def process_datapost_sensdb(datapost, verbosity=0):
    """
    Process one data.Datapost record and insert values into the database.
    Update also Datalogger's aggregate fields.
    E.g.
    SERVER,2014-05-13T01:30:01Z,pg_database_size=156517176,datalogger_objects=8,measuring_objects=136020,data_objects=273365
    """
    if datapost.protocol != 'SENSDB':  # process only SENSDB Dataposts
        return False
    data = datapost.get_data()
    # Remove newline characters, trailing asterisk and split to lines
    lines = data.strip().split('\n')
    line = lines[0]
    if line.find(';') == 15:  # has timestamp field, separated by ';'
        timestamp, line = line.split(';')
    # Take the very first field, it's loggers code. Then get the logger object
    idcode = line.split(',')[0]
    idcode_re = re.compile(r'^[a-zA-Z0-90-9\-_]+$')
    if idcode_re.match(idcode) is None:
        # Got some garbage, ignore this datapost
        datapost.status = -2
        datapost.save()
        return False
    # TODO: use get_or_create()
    # datalogger, created = Datalogger.objects.get_or_create(idcode=idcode)
    if Datalogger.objects.filter(idcode=idcode).count() == 0:
        datalogger = Datalogger(idcode=idcode, name=idcode)
        datalogger.save()
    else:  # This will raise DoesNotExist (if it doesn't exist :-)
        datalogger = Datalogger.objects.get(idcode=idcode)
    try:
        logger_timezone = pytz.timezone(datalogger.timezone)
        for line in lines:  # loop all "lines" (originally separated by '*')
            line = line.split('*')[0]
            if line.strip() == '':
                continue
            # Create utc timestamp from datefield
            try:
                t = line.split(',')
                t.pop(0)  # idcode is the first field
                time_str = t.pop(0)
                dt = dateutil.parser.parse(time_str)
                # If there was no timezone info in time_str dt is
                # unaware and we have to make it aware
                if dt.tzinfo is None:
                    # Check datalogger's settings should we use
                    # UTC or logger's timezone for localization
                    if datalogger.in_utc:
                        dt = pytz.utc.localize(dt)
                    else:
                        dt = logger_timezone.localize(dt)
                utctime = dt
            except ValueError:
                continue
            # to_zone = tz.gettz(datalogger.timezone)
            if utctime.tzinfo is None:
                from_zone = tz.gettz('UTC')
                utctime = utctime.replace(tzinfo=from_zone)
            try:
                for sensor in t:
                    if sensor.find("=") < 0:
                        continue
                    key, val = sensor.split('=')
                    val = float(val)
                    try:
                        unit = Unit.objects.filter(
                            datalogger=datalogger).filter(uniquename=key)
                        if unit:
                            unit = unit[0]
                        else:
                            unit = Unit(uniquename=key,
                                        datalogger=datalogger, name=key)
                            unit.save()
                    except Unit.DoesNotExist:
                        print("NO UNIT")
                        pass
                    dataitem = Data(unit=unit, value=val, datapost=datapost, timestamp=utctime)
                    # Make data invalid if it is below or exceeds filter limits
                    dataitem.valid = apply_filter(unit, val)
                    dataitem.save()
                    check_alerts(datalogger, dataitem)
            except ValueError as err:
                print(err)
                raise
        datapost.status = 1
        datapost.datalogger = datalogger
        datapost.save()
        datalogger.set_aggregates()
        datalogger.save()
        update_grouplogger_aggregates(datalogger)
    except Exception as err:
        print("DATALINE", line)
        print(str(err))
        raise
    return True


def process_datapost_espeasy(datapost, verbosity=0):
    """
    Process one data.Datapost record and insert values into the database.
    Update also Datalogger's aggregate fields.
    {"data": "Temperature=21.75", "idcode": "logger_idcode", "sensor": "outside_temp", "id": "0"}
    """
    if datapost.protocol != 'ESPEASY':  # process only ESPEASY Dataposts
        return False
    all_data = json.loads(datapost.get_data())
    data = all_data.get('data')
    idcode = all_data.get('idcode')
    sensor = all_data.get('sensor')
    # Remove newline characters, trailing asterisk and split to lines
    datalogger = Datalogger.objects.get(idcode=idcode)
    # Some reasonable(?) defaults
    MIN_TIME = 30
    MAX_TIME = 60 * 30
    # MAX_TIME = 60 * 10
    MIN_CHANGE = 1.0
    datapost_has_saved_data = False
    try:
        for keyval in data.split(','):
            if keyval.find("=") < 0:
                continue
            key, val = keyval.split('=')
            key = '{}_{}'.format(sensor, key)
            val = float(val)
            unit, created = Unit.objects.get_or_create(datalogger=datalogger, uniquename=key)
            if created:
                unit.name = key
                unit.save()
                print('created {}'.format(unit))
            last_data = Data.objects.filter(unit=unit).order_by('-timestamp')
            if last_data.count() > 0:
                last_val = last_data[0].value
                last_age = (datapost.created - last_data[0].timestamp).total_seconds()
            else:
                last_val = -9999999999
                last_age = 9999999999
            min_time = unit.min_time if unit.min_time > 0 else MIN_TIME
            max_time = unit.max_time if unit.max_time > 0 else MAX_TIME
            # MAX_TIME = 60 * 10
            min_change = unit.min_change if unit.min_change > 0 else MIN_CHANGE

            if (
                    (last_age >= min_time and abs(last_val - val) >= min_change)
                  or last_age >= max_time
            ):
                dataitem = Data(unit=unit, value=val, datapost=datapost, timestamp=datapost.created)
                # Make data invalid if it is below or exceeds filter limits
                dataitem.valid = apply_filter(unit, val)
                dataitem.save()
                datapost_has_saved_data = True
                check_alerts(datalogger, dataitem)
                # print('SAVED     {} {} {} {}'.format(last_age, last_val, val, key))
            else:
                pass
                # print('NOT SAVED {} {} {} {}'.format(last_age, last_val, val, key))
    except ValueError as err:
        print(err)
        raise
    if datapost_has_saved_data:
        datapost.status = 1
    else:
        datapost.status = 3
    datapost.datalogger = datalogger
    datapost.save()
    datalogger.set_aggregates()
    datalogger.save()
    update_grouplogger_aggregates(datalogger)
    return True


def process_dataposts(command, limit=None, idcode=None,
                      maxprocessingtime=None, verbosity=0, pk=None):
    # Get all Dataposts, which have existing Datalogger in the database
    starttime = time.time()
    available_dataloggers = Datalogger.objects.filter(active=True)\
        .values_list('idcode', flat=True).distinct()
    dataposts = Datapost.objects.filter(status=0)
    if idcode:
        dataposts = dataposts.filter(idcode=idcode)
    if pk:
        dataposts = dataposts.filter(pk=pk)
    dataposts = dataposts.filter(idcode__in=available_dataloggers)
    dataposts = dataposts.order_by('created', 'idcode')
    successcount = failedcount = 0
    # Limit, if called with --limit <n> switch
    if limit is not None:
        dataposts = dataposts[:limit]
    for datapost in dataposts:
        if maxprocessingtime and time.time() > starttime + maxprocessingtime:
            msg = u'Maximum processing time %s seconds is exceeded.' % (
                maxprocessingtime)
            log.warning(msg)
            return successcount, failedcount
        # TODO: use --verbose instead
        msg = u'%s %s' % (datapost, datapost.created)
        log.info(msg)
        if verbosity > 0:
            command.stdout.write(msg + '\n')
        with transaction.atomic():
            if datapost.protocol == 'SENSDB':
                success = process_datapost_sensdb(datapost, verbosity)
            elif datapost.protocol == 'ESPEASY':
                success = process_datapost_espeasy(datapost, verbosity)
            else:
                success = False
                print('No handler for protocol "{}"'.format(datapost.protocol))
            if success:
                successcount += 1
            else:
                failedcount += 1
    return successcount, failedcount


class Command(BaseCommand):
    def add_arguments(self, parser):

        # Limit max number of dataposts to process
        parser.add_argument('--limit',
                        action='store',
                        dest='limit',
                        default=None,
                        help=u'Limit the number of dataposts to handle')
        # Limit dataposts to one idcode
        parser.add_argument('--idcode',
                        action='store',
                        dest='idcode',
                        default=None,
                        help=u'Handle only dataposts of "idcode"')
        # Limit processing time
        parser.add_argument('--maxprocessingtime',
                        action='store',
                        dest='maxprocessingtime',
                        default=None,
                        help=u'Stop processing after "maxprocessingtime" '
                             u'seconds is reached')
        parser.add_argument('--pk',
                        action='store',
                        dest='pk',
                        type=int,
                        default=None,
                        help=u'Process only Datapost which has "pk"')

    args = ''
    help = 'Processes Dataposts'

    def handle(self, *args, **options):
        limit = options.get('limit')
        idcode = options.get('idcode')
        pk = options.get('pk')
        maxprocessingtime = options.get('maxprocessingtime')
        try:
            verbosity = int(options.get('verbosity', 1))  # 0, 1 (default) or 2
        except ValueError:
            verbosity = 1
        if limit is not None:
            limit = int(limit)
        if maxprocessingtime is not None:
            maxprocessingtime = int(maxprocessingtime)
        starttime = time.time()
        successcount, failedcount = process_dataposts(
            self, limit,
            idcode=idcode, maxprocessingtime=maxprocessingtime,
            verbosity=verbosity, pk=pk)
        secs = time.time() - starttime
        if successcount + failedcount > 0:
            msg = u'Processed %d Dataposts and failed %d in %.2f seconds.' % \
                  (successcount, failedcount, secs)
            log.info(msg)
            if verbosity > 0:
                self.stdout.write(msg + '\n')
        no_logger = Datapost.objects.filter(datalogger__isnull=True)\
            .exclude(idcode__in=Datalogger.objects.values('idcode'))\
            .values('idcode').annotate(Count('idcode'))
        if len(no_logger) > 0:
            for cnt in no_logger:
                msg = (u"Datalogger '%(idcode)s' doesn't exist "
                       "(%(idcode__count)d unprocessed Dataposts). You should "
                       "create it to get rid of this message." % cnt)
                log.info(msg)
                if verbosity > 0:
                    self.stdout.write(msg + '\n')
        act_loggers = Datalogger.objects.filter(active=False).values('idcode')
        inactive_logger = Datapost.objects.filter(datalogger__isnull=True)\
            .filter(idcode__in=act_loggers).values('idcode')\
            .annotate(Count('idcode'))
        if len(inactive_logger) > 0:
            for cnt in inactive_logger:
                msg = ("Datalogger '%(idcode)s' exists, but is inactive "
                       "(%(idcode__count)d unprocessed Dataposts). You should "
                       "activate it to get rid of this message.\n" % cnt)
                log.info(msg)
                if verbosity > 0:
                    self.stdout.write(msg + '\n')
