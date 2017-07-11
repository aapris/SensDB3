# SensDB3
IoT Platform
# Getting started
Clone this repo. Initialize SQLite3 database:
```
$ python manage.py migrate
```
Create a superuser:

```
$ python manage.py createsuperuser
```

Run development server:
```
$ python manage.py runserver
```

Use (in another terminal window) Httpie application to POST some data to `espeasy` endpoint:
```
echo -n "idcode=newlogger&sensor=bme280&id=0&data=Temperature=25.84,Humidity=54.05,Pressure=1004.50" \
   | http -v --auth user:pass --form POST http://127.0.0.1:8000/api/espeasy
```
The output should look like this:

```
POST /api/espeasy HTTP/1.1
Accept: */*
Accept-Encoding: gzip, deflate
Authorization: Basic dXNlcjpwYXNz
Connection: keep-alive
Content-Length: 90
Content-Type: application/x-www-form-urlencoded; charset=utf-8
Host: 127.0.0.1:8000
User-Agent: HTTPie/0.9.8

idcode=newlogger&sensor=bme280&id=0&data=Temperature=25.84,Humidity=54.05,Pressure=1004.50

HTTP/1.0 200 OK
Content-Length: 24
Content-Type: text/html; charset=utf-8
Date: Tue, 11 Jul 2017 08:49:38 GMT
Server: WSGIServer/0.2 CPython/3.6.0
X-Frame-Options: SAMEORIGIN

$OK,2017-07-11T08:49:38Z
```
Now you have created a `Datapost` into Sensdb3's database. You can try to process it 
(turn it to a `Data` object) using command:
```
$ python manage.py process_dataposts
Datalogger 'newlogger' doesn't exist (1 unprocessed Dataposts). You should create it to get rid of this message.
```
Oops, no Datalogger? Don't worry, create a Datalogger with unique ID code `newlogger` using this command:

```
$ python manage.py manage_datalogger create --idcode newlogger --activate
Warning: Datalogger's time zone was set to UTC.
Datalogger was created successfully.
```
Go ahead and list all Dataloggers:
```
$ python manage.py manage_datalogger list
Idcode               Status    Created
newlogger            ACTIVE    2017-07-11 08:50:53.770013+00:00
```
Now you should be able to process Dataposts:
```
$ python manage.py process_dataposts
newlogger 2017-07-11 08:49:38.201217+00:00
created bme280_Temperature  
created bme280_Humidity  
created bme280_Pressure  
Processed 1 Dataposts and failed 0 in 0.04 seconds.
```

# ESP826 and ESP Easy
If you have some ESP8266 MCUs and a bunch of sensors, you can flash it with 
[Esp Easy 2.0 firmware](https://github.com/letscontrolit/ESPEasy/releases) 
and send sensor data to SensDB3.

Set up a controller with following configuration:

* Protocol: `Generic HTTP Advanced [TESTING]`
* Controller IP / Hostname / Port: you name them
* Controller User: an unpriviledged user you've created in Django admin
* Controller Password: user's password
* Enabled: true
* HTTP Method: `POST`
* HTTP URI: `espeasy`
* HTTP Header:	
    ```
    Content-Type: application/x-www-form-urlencoded
    X-Local-IP: %ip%
    X-Uptime: %uptime%
    X-Sysload: %sysload%	
    ```
* HTTP Body:
    ```
    idcode=%sysname%&sensor=%tskname%&id=%id%&data=%1%%vname1%=%val1%%/1%%2%,%vname2%=%val2%%/2%%3%,%vname3%=%val3%%/3%%4%%vname4%=%val4%%/4%
    ```

# Any questions?
Feel free to file an issue.
