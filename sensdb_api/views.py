import base64
import json
import datetime
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from sensdb3.models import Datapost
from sensdb_api.tasks import process_dataposts_task


def _basicauth(request):
    # Check for valid basic auth header
    uname, passwd, user = None, None, None
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2:
            if auth[0].lower() == "basic":
                a = auth[1].encode('utf8')
                s = base64.b64decode(a)
                uname, passwd = s.decode('utf8').split(':')
                user = authenticate(username=uname, password=passwd)
    return uname, passwd, user


@csrf_exempt
def postdata_espeasy(request, version='0.0.0'):
    """
    POST data using self made "espeasy" protocol. Example below uses Httpie application.
    echo -n "idcode=logger_id_code&sensor=bme280&id=0&data=Temperature=24.84,Humidity=52.05,Pressure=1002.50" |
       http -v --auth user:pass --form POST http://127.0.0.1:8000/api/espeasy
    """
    uname, passwd, user = _basicauth(request)
    # You might want to return HTTP 403 here, if user was not authenticated
    data = request.POST.get('data', '').strip()
    # lograw.info(data)
    dp = None
    if data:
        json_data = json.dumps(request.POST)
        idcode = request.POST.get('idcode', '').strip()
        # sensor = request.POST.get('sensor', '').strip()
        idcode = idcode.replace('\r', '').replace('\n', '')
        dp = Datapost(data=json_data, idcode=idcode)
        if idcode == '':
            pass  # TODO: set dp.status = 'NO_IDCODE' ?
        dp.protocol = request.POST.get('protocol', 'ESPEASY').strip()
        dp.version = request.POST.get('version', version).strip()
        dp.user = user
        dp.set_request_data(request)
        dp.save()
        try:
            process_dataposts_task.delay(dp.pk)
        except Exception as err:  # Broker is not listening: redis.exceptions.ConnectionError
            # lograw.info(err)
            print('Task error (broker not running?): {}'.format(err))
    utc_dt = timezone.now()
    time_str = utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    responsetext = '$OK,{}'.format(time_str)
    if dp:
        dp.response = responsetext
        dp.save()
    response = HttpResponse(responsetext)
    return response
