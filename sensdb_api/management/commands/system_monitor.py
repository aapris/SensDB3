from django.conf import settings
from django.db import connection
from sensdb3.models import Datapost, Datalogger, Data, Unit
from sensdb_api.tasks import process_dataposts_task
import datetime
import psutil
import pytz

IDCODE = 'SERVER'


def utc_datetime_str():
    """Return timezone aware datetime object at timezone UTC. """
    formatting = '%Y-%m-%dT%H:%M:%S' + 'Z'
    # TODO: replace with timezone.now()
    ts = datetime.datetime.now(pytz.utc)
    return ts.strftime(formatting)


def disk_usage(mountpoint='/'):
    """
    :return: disk_total, disk_used, disk_free MiB int, disk_percent_used float
    """
    disk = psutil.disk_usage(mountpoint)
    disk_total = disk.total / 2**20     # MiB.
    disk_used = disk.used / 2**20
    disk_free = disk.free / 2**20
    disk_percent_used = disk.percent
    return disk_total, disk_used, disk_free, disk_percent_used


def disk_usages(disks=[]):
    if not disks:  # return all partitions if disks was empty
        disks = [p.mountpoint for p in psutil.disk_partitions()]
    usages = []
    for partition in disks:
        mp = partition
        disk_total, disk_used, disk_free, disk_percent_used = disk_usage(mp)
        mp = 'disk' + mp.replace('/', '_')
        usages.append([mp, disk_percent_used])
    return usages


def pg_database_size():
    """
    :return: Database size on the disk in bytes (B)
    """
    if settings.DATABASES['default']['ENGINE'] in [
            'django.contrib.gis.db.backends.postgis',
            'django.db.backends.postgresql_psycopg2']:
        dbname = settings.DATABASES['default']['NAME']
        cursor = connection.cursor()
        cursor.execute("SELECT pg_database_size(%s) ", [dbname])
        row = cursor.fetchone()
        return row[0]
    else:
        return None


def object_count():
    counts = [
        ('datalogger_objects', Datalogger.objects.count()),
        ('data_objects', Data.objects.count()),
        ('unit_objects', Unit.objects.count()),
    ]
    return counts


def save_datapost(idcode, data, version):
    """
    Save data string as a Datapost and schedule processing.
    :param idcode: ID code of the Datalogger
    :param data: Data as a string
    :param version: Data format version
    :return: Datapost object
    """
    dp = Datapost(data=data, idcode=idcode)
    dp.protocol = 'SENSDB'
    dp.version = version
    dp.save()
    process_dataposts_task.delay(dp.pk)
    return dp


def main(idcode=IDCODE, disks=[]):
    channels = [
        ('pg_database_size', pg_database_size),
    ]
    key_val = []
    for name, func in channels:
        key_val.append((name, func()))
    key_val += disk_usages(disks)
    key_val += object_count()
    data = [idcode, utc_datetime_str()]
    data += ['='.join((x[0], str(x[1]))) for x in key_val]
    data_str = ','.join(data)
    dp = save_datapost(IDCODE, data_str, '0.2.0')
    return data_str


if __name__ == '__main__':
    print(main())
