# -*- coding: utf-8 -*-

import re
import math
import string
import random
import pytz
import datetime
import zlib
import base64
import os

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError


ALPHANUM = string.ascii_letters + string.digits


def get_uid(length=12):
    """
    Generate and return a random string which can be considered unique.
    Default length is 12 characters from set [a-zA-Z0-9].

    Args:
        length (int): length of generated string in characters

    Returns:
        str: a random string of string.letters + string.digits
    """
    return ''.join([ALPHANUM[random.randint(0,
                             len(ALPHANUM) - 1)] for _ in range(length)])

MEASURINGINTERVAL_CHOICES = [
    (1 * 60, _('1 min')),
    (5 * 60, _('5 min')),
    (10 * 60, _('10 min')),
    (15 * 60, _('15 min')),
    (30 * 60, _('30 min')),
    (1 * 60 * 60, _('1 h')),
    (3 * 60 * 60, _('3 h')),
    (6 * 60 * 60, _('6 h')),
    (12 * 60 * 60, _('12 h')),
]

TRANSINTERVAL_CHOICES = MEASURINGINTERVAL_CHOICES + [
    (24 * 60 * 60, _('24 h')),
]

ALL_TIMEZONE_CHOICES = tuple(zip(pytz.all_timezones, pytz.all_timezones))
COMMON_TIMEZONE_CHOICES = tuple(zip(pytz.common_timezones,
                                    pytz.common_timezones))
PRETTY_TIMEZONE_CHOICES = []
# PRETTY_TIMEZONE_CHOICES = [('', '---')]

FOO = {}
for tzone in pytz.common_timezones:
    tokens = tzone.split('/')
    continent, place = tokens.pop(0), '/'.join(tokens)
    if continent not in FOO:
        FOO[continent] = []
    now = datetime.datetime.now(pytz.timezone(tzone))
    try:
        # https://bugs.launchpad.net/pytz/+bug/885163
        PRETTY_TIMEZONE_CHOICES.append(
            (tzone, "%s (GMT%s)" % (tzone, now.strftime("%z"))))
        FOO[continent].append(
            (tzone, "%s (GMT%s)" % (tzone, now.strftime("%z"))))
    except ValueError as err:
        pass
    except Exception as err:
        print("TIMEZONE ERROR: {}".format(err))


IN_UTC_HELP = _(
    'If checked, data logger sends timestamps in the data in UTC time, '
    'otherwise in local time zone. '
    'DO NOT CHANGE THIS UNLESS YOU KNOW WHAT YOU ARE DOING.')

LOGGER_STATUS_CHOICES = [
    ('INACTIVE', _('Inactive')),
    ('ACTIVE', _('Active')),
    ('RESET_SCHEDULED', _('Reset scheduled')),
    ('RESET_IN_PROGRESS', _('Reset in progress')),
    ('RESET_FAILED', _('Reset failed')),
    ('RESET_FINISHED', _('Reset finished')),
]


class Organization(models.Model):
    """
    Organization is used to group Dataloggers and give users access to
    multiple Dataloggers in one transaction.
    """
    name = models.CharField(max_length=100, editable=True,
                            verbose_name=_('Name'))
    slug = models.SlugField(max_length=100, editable=True,
                            verbose_name=_('Slug'))
    admins = models.ManyToManyField(User, blank=True,
                                    related_name='admins',
                                    verbose_name=_('Admins'))
    viewers = models.ManyToManyField(User, blank=True,
                                     related_name='viewers',
                                     verbose_name=_('Viewers'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Datalogger(models.Model):
    """
    TODO
    """
    user = models.ForeignKey(User, blank=True, null=True,
                             verbose_name=_('Owner'))
    organization = models.ForeignKey('Organization', blank=True, null=True,
                                     verbose_name=_('Organization'))
    admins = models.ManyToManyField(User, blank=True,
                                    related_name='admin_dataloggers',
                                    verbose_name=_('Admins'))
    viewers = models.ManyToManyField(User, blank=True,
                                     related_name='viewer_dataloggers',
                                     verbose_name=_('Viewers'))
    related_users = models.ManyToManyField(User,
                                           blank=True,
                                           through="DataloggerUser",
                                           related_name="related_dataloggers",
                                           verbose_name=_("Related users"))
    uid = models.CharField(max_length=40, unique=True, db_index=True,
                           default=get_uid, editable=False)
    idcode = models.CharField(max_length=40, blank=False, db_index=True,
                              unique=True,
                              verbose_name=_('Identification code'))
    customcode = models.CharField(max_length=255, db_index=True,
                                  editable=True, blank=True,
                                  default='', verbose_name=_('Custom code'),
                                  help_text=_('Custom code string'))
    status = models.CharField(max_length=40,
                              default=LOGGER_STATUS_CHOICES[0][0],
                              editable=False,
                              choices=LOGGER_STATUS_CHOICES,
                              verbose_name=_('Status'))
    name = models.CharField(max_length=100, blank=True, editable=True,
                            verbose_name=_('Name'))
    description = models.TextField(blank=True, editable=True,
                                   verbose_name=_('Description'))
    measuringinterval = models.IntegerField(default=0, editable=True,
                                            choices=MEASURINGINTERVAL_CHOICES,
                                            verbose_name=_(
                                                'Measuring interval'))
    transmissioninterval = models.IntegerField(default=0, editable=True,
                                               choices=TRANSINTERVAL_CHOICES,
                                               verbose_name=_(
                                                   'Transmission interval'))
    timezone = models.CharField(max_length=40, blank=True, null=True,
                                editable=True, default=None,
                                choices=PRETTY_TIMEZONE_CHOICES,
                                verbose_name=_('Time zone'))
    in_utc = models.BooleanField(default=True, editable=True,
                                 help_text=IN_UTC_HELP,
                                 verbose_name=_('Logger data is in UTC time'))
    active = models.BooleanField(default=False, editable=True,
                                 verbose_name=_('Active'))
    alertemail = models.TextField(max_length=500, blank=True, editable=True,
                                 help_text=_('Separate multiple addresses by newline'),
                                 verbose_name=_('E-mail alert addresses'))
    contactperson = models.TextField(blank=True, editable=True,
                                     verbose_name=_('Contact person'))
    lat = models.FloatField(blank=True, null=True,
                            verbose_name=_('Latitude (dd.dddd)'))
    lon = models.FloatField(blank=True, null=True,
                            verbose_name=_('Longitude (dd.dddd)'))
    firmwareurl = models.URLField(max_length=200, blank=True, editable=True,
                                  verbose_name=_('Firmware URL'))
    configurl = models.URLField(max_length=200, blank=True, editable=True,
                                verbose_name=_('Config URL'))
    firstmeasuring = models.DateTimeField(blank=True, null=True,
                                          editable=False,
                                          verbose_name=_(
                                              'First measuring time'))
    lastmeasuring = models.DateTimeField(blank=True, null=True, editable=False,
                                         verbose_name=_(
                                             'Latest measuring time'))
    measuringcount = models.IntegerField(default=0, editable=False,
                                         verbose_name=_(
                                             'Total number of measurings'))
    datapostcount = models.IntegerField(default=0, editable=False,
                                        verbose_name=_(
                                             'Total number of Dataposts'))
    lastdatapost = models.DateTimeField(blank=True, null=True, editable=False,
                                        verbose_name=_(
                                            'Latest datapost received'))

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s' % self.idcode

    @property
    def all_admins(self):
        """Get datalogger and organization admins"""
        query = Q(admin_dataloggers=self)
        if self.organization:
            query |= Q(admins=self.organization)
        return User.objects.filter(query).distinct()

    @property
    def all_viewers(self):
        """Get datalogger and organization viewers"""
        query = Q(viewer_dataloggers=self)
        if self.organization:
            query |= Q(viewers=self.organization)
        return User.objects.filter(query).distinct()

    def get_timezone(self):
        return self.timezone

    def set_aggregates(self):
        """
        Save Logger's measuring related metadata so won't be queried
        every time it is needed.

        explain analyze SELECT "data_measuring"."id",
        "data_measuring"."timestamp", "data_measuring"."utctime",
        "data_measuring"."localtime", "data_measuring"."datalogger_id",
        "data_measuring"."datapost_id", "data_measuring"."created"
        FROM "data_measuring"
        WHERE "data_measuring"."datalogger_id" = 293
        ORDER BY "data_measuring"."timestamp" deSC limit 1;
        or
        explain analyze SELECT "data_measuring"."id",
        "data_measuring"."timestamp", "data_measuring"."utctime",
        "data_measuring"."localtime", "data_measuring"."datalogger_id",
        "data_measuring"."datapost_id", "data_measuring"."created"
        FROM "data_measuring"
        WHERE "data_measuring"."datalogger_id" = 293
        ORDER BY "data_measuring"."utctime" deSC limit 1;
        """
        dataposts = Datapost.objects.filter(idcode=self.idcode)
        datapost_count = dataposts.count()
        if datapost_count > 0:
            self.datapostcount = datapost_count
            self.lastdatapost = dataposts.order_by('-created')[0].created
        else:
            self.datapostcount = 0
            self.lastdatapost = None
        data_obj = Data.objects.filter(unit__in=self.units.all())
        if data_obj.count() > 0:
            self.firstmeasuring = data_obj.order_by('timestamp')[0].timestamp
            self.lastmeasuring = data_obj.order_by('-timestamp')[0].timestamp
        else:
            self.firstmeasuring = None
            self.lastmeasuring = None

    def save(self, *args, **kwargs):
        """
        Check that time zone is set before saving and activating logger.
        """
        if self.timezone is None:
            # Datalogger can't be active if timezone is None
            self.active = False
        super(Datalogger, self).save(*args, **kwargs)

    def reset(self):
        """
        Delete all Measuring and Data objects related to this Logger.
        Reset also pre-saved aggregates.
        """
        self.active = False
        self.status = "RESET_IN_PROGRESS"
        self.save()
        try:
            units = Datalogger.units.all()
            Data.objects.select_related().filter(unit__in=units).delete()
            # TODO: remove, this doesn't work with new dataloggers not using Measuring anymore
            Datapost.objects.select_related().filter(datalogger=self).update(
                datalogger=None, status=0)
            self.set_aggregates()
            # self.status = "RESET_FINISHED"
            # TODO: check if also: self.active = False
            self.status = "INACTIVE"
        except Exception:
            self.status = "RESET_FAILED"
            pass
        self.save()


class DataloggerUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    datalogger = models.ForeignKey(Datalogger, on_delete=models.CASCADE)
    role = models.CharField(max_length=100)

    def __str__(self):
        return "%s -> %s (%s)" % (self.user, self.datalogger, self.role)


DATAPOST_STATUS_CHOICES = [
    (-1, _('Deleted')),
    (0, _('New')),
    (1, _('Processed')),
]


class Datapost(models.Model):
    """
    Stores a single chunk of raw data sent by a data logger and
    most of available metadata about the sender of this chunk.
    Raw data may be compressed with zlib, if it saves disk space.

    Datapost's data contains one or more measurements and one measurement
    contains from one to (virtually) unlimited number of data items.

    After processing a Datapost its' datalogger field is set to refer
    to correct :model:`data.Datalogger`.
    """

    datalogger = models.ForeignKey(Datalogger, blank=True, null=True)
    user = models.ForeignKey(User, models.SET_NULL, blank=True, null=True, verbose_name=_('Sender'))
    idcode = models.CharField(max_length=40, db_index=True,
                              editable=False,
                              help_text="Dataogger's unique id code string")
    status = models.IntegerField(default=0, editable=True,
                                 choices=DATAPOST_STATUS_CHOICES,
                                 verbose_name=_('Status'))
    protocol = models.CharField(max_length=20, default='', editable=False)
    version = models.CharField(max_length=20, default='', editable=False)
    compression = models.CharField(max_length=20, blank=True, editable=False)
    data = models.TextField(editable=False,
                            help_text="Raw data, received from data logger")
    response = models.TextField(editable=False, blank=True, null=True)
    sessionid = models.CharField(max_length=200, blank=True, editable=False)
    ip = models.GenericIPAddressField(blank=True, null=True, editable=False)
    useragent = models.CharField(max_length=500, blank=True, editable=False)
    httpheaders = models.TextField(blank=True, editable=False)
    created = models.DateTimeField(auto_now_add=True,
                                   help_text="Record's creation time stamp")

    def compress_data(self):
        """zlib compress and base64 encode the data field's value."""
        if self.compression == '':
            self.data = base64.b64encode(zlib.compress(self.data))
            self.compression = 'zlib+base64'

    def decompress_data(self):
        if self.compression == 'zlib+base64':
            self.data = zlib.decompress(base64.b64decode(self.data))
            self.compression = ''

    def get_data(self):
        """Get data in uncompressed format."""
        if self.compression == 'zlib+base64':
            return zlib.decompress(base64.b64decode(self.data))
        else:
            return self.data

    def set_request_data(self, request):
        self.sessionid = request.session.session_key \
            if request.session.session_key else ''
        # Try to get X-Real-IP header from nginx first, then REMOTE_ADDR
        self.ip = request.META.get('HTTP_X_REAL_IP',
                                   request.META.get('REMOTE_ADDR'))
        regex = re.compile('^HTTP_')
        header_tuples = [(regex.sub('', header), value) for (header, value)
                         in request.META.items() if header.startswith('HTTP_')]
        for header in ['REQUEST_METHOD', 'CONTENT_LENGTH', 'CONTENT_TYPE']:
            val = request.META.get(header)
            if val:
                header_tuples.append((header, val))
        header_tuples.sort()
        try:
            self.httpheaders = "\n".join(['%s: %s' % (h, v)
                                         for h, v in header_tuples])
        except Exception as err:  # Don't crash if there is some mysterious error
            self.httpheaders = 'Error while parsing HTTP-headers. Check logs.'
            print(str(err))
        self.useragent = request.META.get('HTTP_USER_AGENT', '')[:500]

    # @abstractmethod
    def get_unit_uniquenames(self):
        """
        Return all Unit "uniquenames" in this Datapost.
        Implementation depends on datapost's format.
        """
        pass

    def __str__(self):
        return self.idcode


class UnitType(models.Model):
    """
    The Unit is usually some kind of physical quantity, e.g. temperature, humidity,
    """
    name = models.CharField(max_length=64, verbose_name=_('Name'))  # e.g. "temperature"
    description = models.TextField(blank=True, verbose_name=_('Comment'))
    symbol = models.CharField(max_length=64, blank=True, verbose_name=_('Symbol'))  # e.g. '°C', '%'
    min = models.FloatField(blank=True, null=True, verbose_name=_('Min default scale'))  # default scale
    max = models.FloatField(blank=True, null=True, verbose_name=_('Max default scale'))  # default scale
    # These values affect how often data is saved to Data objects
    min_time = models.FloatField(default=0, verbose_name=_('Min time in seconds between saved values'))
    max_time = models.FloatField(default=0, verbose_name=_('Max time in seconds between saved values'))
    min_change = models.FloatField(default=0, verbose_name=_('Min change to save new value'))
    max_change = models.FloatField(default=0, verbose_name=_('Max change to save always new value'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} {}'.format(self.name, self.symbol)


INTERVALCHOICES = (
    (1, _('Second')),
    (60 * 60, _('Hour')),
)

VISIBILITY_CHOICES = [
    ('E', _('Everyone')),
    ('A', _('Admins')),
    ('N', _('Nobody')),
]


class Unit(models.Model):
    """
    All Dataloggers have one or more data channels, which all have one Unit.
    """
    datalogger = models.ForeignKey(Datalogger, editable=False, related_name='units')
    unittype = models.ForeignKey(UnitType, models.SET_NULL, blank=True, null=True, related_name='units')
    uniquename = models.CharField(max_length=64, blank=True, verbose_name=_(
        'Unique name for unit'))  # e.g. "dht22_1"
    name = models.CharField(max_length=64, blank=True,
                            verbose_name=_('Name'))  # e.g. "Temperature"
    comment = models.CharField(max_length=64, blank=True,
                               verbose_name=_('Comment'))  # e.g. "water"
    symbol = models.CharField(max_length=64, blank=True,
                              verbose_name=_('Symbol'))  # e.g. "°C"
    min = models.FloatField(blank=True, null=True, verbose_name=_(
        'Min default scale'))  # default scale
    max = models.FloatField(blank=True, null=True, verbose_name=_(
        'Max default scale'))  # default scale
    # These values affect how often data is saved to Data objects
    min_time = models.FloatField(default=0, verbose_name=_('Min time in seconds between saved values'))
    max_time = models.FloatField(default=0, verbose_name=_('Max time in seconds between saved values'))
    min_change = models.FloatField(default=0, verbose_name=_('Min change to save new value'))
    max_change = models.FloatField(default=0, verbose_name=_('Max change to save always new value'))

    alertlow = models.FloatField(blank=True, null=True,
                                 verbose_name=_('Lower alert limit'))
    alerthigh = models.FloatField(blank=True, null=True,
                                  verbose_name=_('Higher alert limit'))
    # TODO: some day low and high may be replaced with expression
    # alertexpression = models.CharField(max_length=256, blank=True,
    #                                    default='',
    #                                    verbose_name=_('Alert expression'))
    filterlow = models.FloatField(blank=True, null=True,
                                  verbose_name=_('Lower filter limit'))
    filterhigh = models.FloatField(blank=True, null=True,
                                   verbose_name=_('Higher filter limit'))
    # TODO: some day low and high may be replaced with expression
    # filterexpression = models.CharField(max_length=256, blank=True,
    #                                     default='',
    #                                     verbose_name=_('Filter expression'))
    # For ordering, not in use
    serial = models.IntegerField(blank=True, null=True)
    # interval = models.IntegerField(blank=True, null=True, default=None,
    #                                choices=INTERVALCHOICES,
    # help_text=u"Unit's time interval (e.g. 1/s, 1/h")
    active = models.BooleanField(default=True, editable=True,
                                 verbose_name=_('Active'))
    api_read_only = models.BooleanField(default=True, editable=True,
                                        verbose_name=_('API read only'))
    visibility = models.CharField(max_length=12,
                                  # blank=True, null=True,
                                  default=VISIBILITY_CHOICES[0][0],
                                  choices=VISIBILITY_CHOICES,
                                  verbose_name=_('Visible'))
    mplparams = models.CharField(
        max_length=250, blank=True,
        verbose_name=_('Matplotlib graph extra parameters'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        # comment = u'(%s)' % self.comment if self.comment else u''
        return '%s %s %s' % (self.name, self.comment, self.symbol)

    class Meta:
        unique_together = (("datalogger", "uniquename"),)


class Data(models.Model):
    """
    Single data element, which has a measuring timestamp, a unit and a value.
    """
    unit = models.ForeignKey(Unit)
    value = models.FloatField()
    valid = models.BooleanField(default=True, verbose_name=_('Valid'))
    timestamp = models.DateTimeField(db_index=True, blank=True, null=True)
    datapost = models.ForeignKey(Datapost, blank=True, null=True,
                                 related_name='datavalues')

    def __str__(self):
        return '%.3f' % self.value

    # class Meta:
    #     unique_together = [["unit", "timestamp"],]
    #     index_together = [["unit", "timestamp"],]


LOGGERLOG_TYPE_CHOICES = (
    ('AUTO', _('Auto')),
    ('MANUAL', _('Manual')),
)

LOGGERLOG_ACTION_CHOICES = (
    ('INSERT', _('Insert')),
    ('UPDATE', _('Update')),
    ('DELETE', _('Delete')),
)


class Dataloggerlog(models.Model):
    """
    Log records for Dataloggers.
    """
    datalogger = models.ForeignKey(Datalogger, related_name='logs')
    user = models.ForeignKey(User, blank=True, null=True,
                             verbose_name=_('Writer'))
    type = models.CharField(max_length=32, blank=False,
                            choices=LOGGERLOG_TYPE_CHOICES,
                            verbose_name=_('Event type'))
    action = models.CharField(max_length=32, blank=False,
                              choices=LOGGERLOG_ACTION_CHOICES,
                              verbose_name=_('Action'))
    target = models.CharField(max_length=64, blank=False,
                              # choices=LOGGERLOG_TYPE_CHOICES,
                              verbose_name=_('Event target'))
    title = models.CharField(max_length=100, blank=True,
                             verbose_name=_('Title'))
    text = models.TextField(blank=True, editable=True, verbose_name=_('Text'))
    starttime = models.DateTimeField(editable=True,
                                     verbose_name=_(
                                         "Time of occurrence or start time"))
    endtime = models.DateTimeField(blank=True, null=True, editable=True,
                                   verbose_name=_('Endtime (optional)'))
    showongraph = models.BooleanField(default=True, editable=True,
                                      verbose_name=_('Show on graph'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{}: {}'.format(self.starttime.strftime('%Y%m%dT%H%M%S%z'),
                               self.text)

    # class Meta:
    #     unique_together = (("datalogger", "uniquename"),)


ALERT_ACTION_CHOICES = (
    ('EMAIL', _('Send email')),
    # ('SMS', _('Send SMS')),
    # ('HTTP', _('Make HTTP GET request')),
)


# class AlertExpression(models.Model):
#     """
#
#     """
#     datalogger = models.ForeignKey('Unit')
#     expression = models.CharField(max_length=1000,
#                                   verbose_name=_('Alert expression'))
#     action = models.CharField(max_length=32, choices=ALERT_ACTION_CHOICES,
#                               verbose_name=_('Action'))
#     actiontarget = models.CharField(max_length=255,
#                                   verbose_name=_('Alert target'))
#     created = models.DateTimeField(auto_now_add=True)
#     expires = models.DateTimeField(blank=True, null=True)


class Alert(models.Model):
    """
    If Alert object hasn't expired no new Alerts are created.
    """
    unit = models.ForeignKey('Unit')
    state = models.CharField(max_length=64, blank=True,
                             verbose_name=_('State'))
    created = models.DateTimeField(auto_now_add=True)
    expires = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '%s %s' % (
            self.unit, self.state)


FORMULACHOICES = (
    ('v-weir', _('V-weir')),
    ('polynomial', _('Polynomial')),
)


class Formula(models.Model):
    """
    """
    datalogger = models.ForeignKey(Datalogger, related_name='formulas')
    type = models.CharField(max_length=32, choices=FORMULACHOICES,
                            verbose_name=_('Formula type'))
    name = models.CharField(max_length=64, blank=True,
                            verbose_name=_('Name'))  # e.g. "Temperature"
    comment = models.CharField(max_length=64, blank=True,
                               verbose_name=_('Comment'))  # e.g. "water"
    symbol = models.CharField(max_length=64, blank=True,
                              verbose_name=_('Symbol'))  # e.g. "°C"
    min = models.FloatField(blank=True, null=True, verbose_name=_(
        'Min default scale'))  # default scale
    max = models.FloatField(blank=True, null=True, verbose_name=_(
        'Max default scale'))  # default scale
    active = models.BooleanField(default=False, editable=True,
                                 verbose_name=_('Active'))
#    activationdate = models.DateTimeField(blank=True, null=True,
#                                          verbose_name=_('Activation date'))

    # Hard-coded 4 units. If you plan to add more,
    # you must change the database schema too
    unit1 = models.ForeignKey(Unit, blank=True, null=True,
                              related_name='formula1',
                              verbose_name=_('Unit 1 (c1)'))
    unit2 = models.ForeignKey(Unit, blank=True, null=True,
                              related_name='formula2',
                              verbose_name=_('Unit 2 (c2)'))
    unit3 = models.ForeignKey(Unit, blank=True, null=True,
                              related_name='formula3',
                              verbose_name=_('Unit 3 (c3)'))
    unit4 = models.ForeignKey(Unit, blank=True, null=True,
                              related_name='formula4',
                              verbose_name=_('Unit 4 (c4)'))
    # Hard-coded 1 formula, current formula's result
    # can base on some other formula
    formula1 = models.ForeignKey('self', blank=True, null=True,
                                 related_name='formulaf1',
                                 verbose_name=_('Formula 1 (f1)'))
    parameters = models.CharField(max_length=256, blank=True, default='',
                                  verbose_name=_(
                                      u"Parameters (',' separated list)"))
    multiplier = models.FloatField(default=1, verbose_name=_('Multiplier'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s %s %s (%s)' % (
            self.name, self.comment, self.symbol, self.type)


class Timeformula(models.Model):
    formula = models.ForeignKey(Formula,
                                related_name='timeformulas',
                                verbose_name=_('Time based formula'))
    starttime = models.DateTimeField(editable=True,
                                     verbose_name=_(
                                         "Start time of validity"))
    parameters = models.CharField(max_length=256,
                                  verbose_name=_(
                                      u"Parameters (',' separated list)"))
    multiplier = models.FloatField(default=1, verbose_name=_('Multiplier'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def clean(self, *args, **kwargs):
        try:
            functions = {'__builtins__': None, 'math': math}
            variables = {'c1': 1.0, 'c2': 1.0, 'c3': 1.0, 'c4': 1.0, 'f1': 1.0}
            eval(self.parameters, functions, variables)
        except SyntaxError as err:
            raise ValidationError('Syntax error: %s' % err)
        except Exception as inst:
            error_msg = _('Not a valid expression: ') + u' ' + self.parameters
            error_msg += u' ({})'.format(inst)
            raise ValidationError(error_msg)
        super(Timeformula, self).clean(*args, **kwargs)

    class Meta:
        ordering = ['starttime']

    def __str__(self):
        return '%s %s' % (
            self.formula, self.starttime)


class Grouplogger(models.Model):
    """

    """
    user = models.ForeignKey(User, blank=True, null=True,
                             verbose_name=_('Owner'))
    admins = models.ManyToManyField(User, blank=True,
                                    related_name='admin_grouploggers',
                                    verbose_name=_('Admins'))
    viewers = models.ManyToManyField(User, blank=True,
                                     related_name='viewer_grouploggers',
                                     verbose_name=_('Viewers'))
    uid = models.CharField(max_length=40, unique=True, db_index=True,
                           default=get_uid, editable=False)
    idcode = models.CharField(max_length=40, unique=True, db_index=True,
                              default=get_uid, editable=False)
    name = models.CharField(max_length=100, blank=True, editable=True,
                            verbose_name=_('Name'))
    description = models.TextField(blank=True, editable=True,
                                   verbose_name=_('Description'))
    units = models.ManyToManyField(Unit, blank=True,
                                   related_name='grouploggers',
                                   verbose_name=_('Group loggers'))
    formulas = models.ManyToManyField(Formula, blank=True,
                                      related_name='grouploggers',
                                      verbose_name=_('Group loggers'))
    active = models.BooleanField(default=False, editable=True,
                                 verbose_name=_('Active'))
    firstmeasuring = models.DateTimeField(blank=True, null=True,
                                          editable=False,
                                          verbose_name=_(
                                              'First measuring time'))
    lastmeasuring = models.DateTimeField(blank=True, null=True, editable=False,
                                         verbose_name=_(
                                             'Latest measuring time'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s' % self.uid

    def get_timezone(self):
        """
        Return the first timezone of all Dataloggers
        """
        timezones = [x.datalogger.timezone for x in self.units.all()]
        timezones += [x.datalogger.timezone for x in self.formulas.all()]
        tz_set = set(timezones)
        if len(tz_set) == 1:
            return list(tz_set)[0]
        elif len(tz_set) > 1:
            timezones = list(tz_set)
            timezones.sort()
            return timezones[0]
        else:
            return None

    def set_aggregates(self):
        """
        Get earliest and latest measuring timestamp of all Units and Formulas.
        """
        units = list(self.units.all())
        # It is possible that grouplogger has only formulas,
        # take into account 1st unit too
        for f in self.formulas.all():
            if f.unit1:
                units.append(f.unit1)
        try:
            # Filter out timestamps which are None
            fm_lst = filter(None, [u.datalogger.firstmeasuring for u in units])
            lm_lst = filter(None, [u.datalogger.lastmeasuring for u in units])
            self.firstmeasuring = min(fm_lst)
            self.lastmeasuring = max(lm_lst)
        except (ValueError, TypeError):
            pass


def update_grouplogger_aggregates(datalogger):
    """
    Update all Grouploggers aggregates, which are related to this Datalogger.
    Used when Datalogger's data changes.

    Args:
        datalogger (Datalogger): a Datalogger instance

    """
    datalogger_units = datalogger.units.filter(active=True)
    datalogger_formulas = datalogger.formulas.filter(active=True)
    qset = Q(units__in=datalogger_units) | Q(formulas__in=datalogger_formulas)
    grouploggers = Grouplogger.objects.filter(qset).distinct()
    for gl in grouploggers:
        gl.set_aggregates()
        gl.save()


CONVERSION_CHOICES = (
    ('raw_eng', _('Raw->Eng')),  # Default value
    ('le_float', _('Little Endian Float->Eng')),
    ('dbl_float', _('Two int var->Eng')),
)


class BaseConversion(models.Model):
    """
    Base class for Conversion objects.
    """
    type = models.CharField(max_length=64, blank=False,
                            default=CONVERSION_CHOICES[0][0],
                            choices=CONVERSION_CHOICES,
                            verbose_name=_('Conversion type'))
    raw_min = models.FloatField(default=0, editable=True)
    raw_max = models.FloatField(default=0, editable=True)
    eng_min = models.FloatField(default=0, editable=True)
    eng_max = models.FloatField(default=0, editable=True)
    offset = models.FloatField(default=0, editable=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return '%s %s' % (
            self.type, self.pk)


class Conversion(BaseConversion):
    """
    Contains values which are used to convert raw data values to
    engineering units.
    """
    unit = models.ForeignKey(Unit)
    channel = models.IntegerField(default=0, editable=True)

    def __str__(self):
        return '%s-%s' % (self.unit.datalogger, self.unit)

    class Meta:
        unique_together = (('unit', 'channel'),)


class ConversionTb(BaseConversion):
    """
    Time-based Conversion. If exists, these are used for Dataposts after
    starttime has past.
    """
    conversion = models.ForeignKey(Conversion)
    starttime = models.DateTimeField()

    def __str__(self):
        return '%s-%s-%s' % (self.conversion.unit.datalogger,
                             self.conversion.unit, self.starttime)


class DataloggerAccess(models.Model):
    """Relationship model between User and Datalogger."""
    user = models.ForeignKey(User)
    datalogger = models.ForeignKey(Datalogger, related_name='datavalue')
    is_owner = models.BooleanField(default=False, editable=True)
    is_viewer = models.BooleanField(default=True, editable=True)

    def __str__(self):
        return '%s-%s' % (self.user, self.datalogger)
