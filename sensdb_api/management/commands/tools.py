import datetime
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.utils import timezone

from sensdb3.models import Alert
from django.conf import settings


def get(key, default):
    return getattr(settings, key, default)


FROM_EMAIL = get('DEFAULT_FROM_EMAIL', 'noreply@non-existing.example.com')
# EXPIRE_TIME = get('ALERT_EXPIRE_TIME', 2 * 60 * 60) # seconds
EXPIRE_TIME = 2 * 60 * 60  # seconds


def check_alerts(datalogger, dataitem):
    """
    Create an Alert if data value is lower than data channel's lower threshold
    or higher than upper threshold.

    Args:
        datalogger (Datalogger): a Datalogger object
        dataitem (Data): a Data object

    """
    low_alert = dataitem.unit.alertlow is not None and \
                dataitem.value < dataitem.unit.alertlow
    high_alert = dataitem.unit.alerthigh is not None and \
                 dataitem.value > dataitem.unit.alerthigh
    # alertexpression = dataitem.unit.alertexpression
    if low_alert or high_alert:
        current_site = Site.objects.get_current()
        now = timezone.now()
        active_alerts = Alert.objects.filter(unit=dataitem.unit).filter(
            expires__gt=now)
        if active_alerts.count() == 0:
            expires = now + datetime.timedelta(seconds=EXPIRE_TIME)
            unit = dataitem.unit
            a = Alert(state='NEW', unit=unit, expires=expires)
            a.save()
            subject = u'[%s alert] %s %s' % (
                current_site.domain, datalogger.idcode, datalogger.name)
            msg = []
            msg.append(
                u"Alert in logger %s. %s" % (datalogger.idcode, unit.name))
            # FIXME: hardcoded http scheme (https) here!
            # TODO: use resolve()?
            msg.append(u"https://%s/logger/%s" % (
                current_site.domain, datalogger.idcode))
            if low_alert:
                msg.append(u"LOW:  %.3f < %.3f" % (
                    dataitem.value, dataitem.unit.alertlow))
            if high_alert:
                msg.append(u"HIGH: %.3f > %.3f" % (
                    dataitem.value, dataitem.unit.alerthigh))
            tos = []
            if datalogger.alertemail:
                tos += datalogger.alertemail  # MultiEmailField
            send_mail(subject, u'\r\n'.join(msg), FROM_EMAIL,
                      tos, fail_silently=True)


def apply_filter(unit, value):
    """
    Return False if value is below or exceeds filter limits

    Args:
        unit (Unit): a Unit object
        value (float): a value to compare to filters

    Returns:
        bool: True if value is filtered. False otherwise.
    """
    if ((unit.filterlow is not None and value < unit.filterlow) or
            (unit.filterhigh is not None and value > unit.filterhigh)):
        return False
    else:
        return True
