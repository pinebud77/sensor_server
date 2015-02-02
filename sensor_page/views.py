# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate, login, logout

from django.template import RequestContext
from django.shortcuts import render_to_response, redirect

from sensor_page.models import *
from sensor_page.forms import *

import pytz
import datetime

import os
import StringIO
from munjanara_sms import send_sms

import logging


os.environ["MATPLOTLIBDATA"] = os.getcwdu()
os.environ["MPLCONFIGDIR"] = os.getcwdu()
import subprocess
def no_popen(*args, **kwargs): raise OSError("forbjudet")
subprocess.Popen = no_popen
subprocess.PIPE = None
subprocess.STDOUT = None

import matplotlib.pyplot as plt


def sensor_settings(request):
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if username != 'company':
            return render_to_response('sensor_page/nouser.html')

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('sensor_page/nouser.html')
        if not user.is_active:
            return render_to_response('sensor_page/nact_user.html')

        sensor = None

        try:
            sensor_node = SensorNode.objects.get(mac_address=request.POST['mac_address'])
            try:
                sensor = Sensor.objects.get(sensor_node=sensor_node, type=int(request.POST['type']))
            except Sensor.DoesNotExist:
                pass
        except SensorNode.DoesNotExist:
            pass

        context_dict = {
            'sensor': sensor,
            }

        logging.debug(u'sensor dispatched sensor setting : ' + unicode(sensor))

        return render_to_response('sensor_page/ssettings_values.txt', context_dict, context)
    else:
        form = SensorSettingForm()
        return render_to_response('sensor_page/ssettings.html', {'form': form}, context)


def settings(request):
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if username != 'company':
            return render_to_response('sensor_page/nouser.html')

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('sensor_page/nouser.html')
        if not user.is_active:
            return render_to_response('sensor_page/nact_user.html')

        sensor_node = None

        try:
            sensor_node = SensorNode.objects.get(mac_address=request.POST['mac_address'])
        except SensorNode.DoesNotExist:
            pass

        context_dict = {
            'sensor_node': sensor_node,
            }

        logging.debug(u'sensor node dispatched setting : ' + unicode(sensor_node))

        return render_to_response('sensor_page/settings_values.txt', context_dict, context)
    else:
        form = SettingForm()
        return render_to_response('sensor_page/settings.html', {'form': form}, context)


def login_page(request):
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('sensor_page/nouser.html')
        if not user.is_active:
            return render_to_response('sensor_page/inact_user.html')
        login(request, user)
        logging.info(u'user logged in : ' + unicode(user))
        return redirect('/sensor/userinfo/')

    else:
        form = LoginForm()
        return render_to_response('sensor_page/login.html', {'form': form}, context)


def logout_page(request):
    logout(request)
    return redirect('/sensor/login/')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_first_and_resume(measure):
    first = False
    resume = False

    measures_count = MeasureEntry.objects.filter(sensor=measure.sensor).count()
    if measures_count <= 1:
        first = True

    sensor_node = measure.sensor.sensor_node
    if sensor_node.warning_count:
        sensor_node.warning_count = 0
        sensor_node.save()
        resume = True

    if first or resume:
        if first:
            text = u'센서가 첫 데이터를 보냈습니다. : '
            logging.info(u'sent SMS for the first data : ' + sensor_node.user.username+ ':' + sensor_node.name)
        else:
            text = u'센서가 다시 데이터를 보냈습니다. : '
            logging.info(u'sent SMS for the resume report : ' + sensor_node.user.username + ':' + sensor_node.name)
        text += sensor_node.name + u' : '
        if measure.sensor.type == 0:
            text += u'온도 : '
        else:
            text += u'습도 : '
        text += '%.1f' % measure.value

        try:
            user_info = UserInfo.objects.get(user=sensor_node.user)
            user_contacts = UserContact.objects.filter(user_info=user_info)
            for contact in user_contacts:
                send_sms(contact.phone_number, text)
                logging.info(u'sent SMS')
        except UserInfo.DoesNotExist:
            logging.error(u'User info was not specified : ' + sensor_node.user.username)

    return first or resume


def check_range(measure):
    sensor = measure.sensor

    report = False
    if measure.value > sensor.high_threshold:
        report = True
    elif measure.value < sensor.low_threshold:
        report = True

    if report:
        text = u'범위를 넘었습니다. '
        text += sensor.sensor_node.name
        text += u' : '
        if sensor.type == 0:
            text += u'온도 : '
        else:
            text += u'습도 : '
        text += '%.1f' % measure.value

        try:
            user_info = UserInfo.objects.get(user=sensor.sensor_node.user)
            user_contacts = UserContact.objects.filter(user_info=user_info)
            for contact in user_contacts:
                send_sms(contact.phone_number, text)
                logging.info(u'sent SMS on the range error : ' + sensor.sensor_node.name)
        except UserInfo.DoesNotExist:
            logging.error(u'User info was not specified : ' + sensor_node.user.username)

    return report

def input(request):
    #ToDo : get the RSSI report from the sensor node
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if username != 'company':
            return render_to_response('sensor_page/nouser.html')

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('sensor_page/nouser.html')
        if not user.is_active:
            return render_to_response('sensor_page/inact_user.html')

        sensor_node = SensorNode.objects.get(mac_address=request.POST['mac_address'])
        sensor = Sensor.objects.get(sensor_node=sensor_node, type=int(request.POST['type']))

        measure = MeasureEntry()
        measure.ip = get_client_ip(request)
        measure.value = float(request.POST['value'])
        measure.sensor = sensor
        measure.save()

        sensor_node.last_update = measure.date
        sensor_node.save()

        check_first_and_resume(measure)
        check_range(measure)

        logging.debug(u'measurement saved : ' + sensor.sensor_node.name + ':' + unicode(sensor.type))

        return render_to_response('sensor_page/saved.html')

    else:
        form = InputForm()
        return render_to_response('sensor_page/input.html', {'form': form}, context)


class UtcTzinfo(datetime.tzinfo):
    def utcoffset(self, dt): return datetime.timedelta(0)
    def dst(self, dt): return datetime.timedelta(0)
    def tzname(self, dt): return 'UTC'
    def olsen_name(self): return 'UTC'


def dynamic_png(sensor_id, format):
    sensor = None
    measure_entries = None
    date_max = datetime.datetime.utcnow()
    tz = None
    delta = None

    try:
        sensor = Sensor.objects.get(pk=sensor_id)
        user_info = UserInfo.objects.get(user=sensor.sensor_node.user)
        tz = pytz.timezone(user_info.timezone)

        if format == "hour":
            delta = datetime.timedelta(hours=1)
        elif format == "day":
            delta = datetime.timedelta(days=1)
        elif format == "week":
            delta = datetime.timedelta(weeks=1)
        elif format == "month":
            delta = datetime.timedelta(weeks=4)
        else:
            delta = datetime.timedelta(days=365)

        try:
            measure_entries = MeasureEntry.objects.filter(sensor=sensor, date__gt=(date_max - delta - datetime.timedelta(days=2)))
        except MeasureEntry.DoesNotExist:
            pass
    except Sensor.DoesNotExist:
        pass

    if not measure_entries:
        return None

    date_min = date_max - delta

    dates = []
    values = []
    highs = []
    lows = []

    ymax = -1000.0
    ymin = 1000.0

    if sensor.high_threshold != 1000.0:
        highs = [sensor.high_threshold, sensor.high_threshold]
        ymax = highs[0] + 10
    if sensor.low_threshold != -1000.0:
        lows = [sensor.low_threshold, sensor.low_threshold]
        ymin = lows[0] - 10

    for measure in measure_entries:
        measure.date = measure.date.replace(tzinfo=None)
        measure.date += tz.utcoffset(measure.date)
        dates.append(measure.date)
        values.append(measure.value)

        if measure.date >= date_min:
            if measure.value > ymax:
                ymax = measure.value + 10
            if measure.value < ymin:
                ymin = measure.value - 10

    try:
        fig, ax = plt.subplots()
        ax.plot_date(dates, values,linestyle='solid', color='blue')

        if highs:
            ax.plot_date([date_min, date_max], highs, linestyle='solid', color='red', linewidth=3, marker="")
        if lows:
            ax.plot_date([date_min, date_max], lows, linestyle='solid', color='red', linewidth=3, marker="")

        ax.set_xlim(date_min, date_max)
        ax.set_ylim(ymin, ymax)

        ax.grid(True)

        fig.autofmt_xdate()

        rv = StringIO.StringIO()
        plt.savefig(rv, format="png")
        plt.clf()
        return """<img src="data:image/png;base64,%s"/>""" % rv.getvalue().encode("base64").strip()
    finally:
        plt.clf()


def userinfo(request, format="day"):
    #ToDO : add non graph output to userinfo page
    if not request.user.is_authenticated():
        return redirect('/sensor/login/')

    context = RequestContext(request)

    phone_numbers = []
    sensor_nodes = []
    sensors = []
    measure_entries = []

    try:
        user_info = UserInfo.objects.get(user=request.user)

        user_contacts = []
        try:
            user_contacts += UserContact.objects.filter(user_info=user_info)
        except UserContact.DoesNotExist:
            pass
        for contact in user_contacts:
            phone_numbers.append(contact.phone_number)
    except UserInfo.DoesNotExist:
        pass


    try:
        sensor_nodes = SensorNode.objects.filter(user=request.user)
    except SensorNode.DoesNotExist:
        pass

    for sensor_node in sensor_nodes:
        try:
            sensors += Sensor.objects.filter(sensor_node=sensor_node)
        except Sensor.DoesNotExist:
            pass

    for sensor in sensors:
        try:
            sensor.pic = dynamic_png(sensor.id, format)
        except MeasureEntry.DoesNotExist:
            pass

    for measure in measure_entries:
        measure.date = measure.date.replace(tzinfo=UtcTzinfo())
        measure.date.astimezone(pytz.timezone(user_info.timezone))

    context_dict = {
        'username': request.user.username,
        'phone_numbers': phone_numbers,
        'sensor_nodes': sensor_nodes,
        'sensors': sensors,
    }

    return render_to_response('sensor_page/userinfo.html', context_dict, context)


#ToDO: add cronjob to check Munjanara account

def cron_job(request):
    #ToDO: move cronjobs to a seperate file
    logging.info('cronjob started')

    now = datetime.datetime.now()

    for sensor_node in SensorNode.objects.all():
        if sensor_node.last_update.replace(tzinfo=None) < now - datetime.timedelta(seconds=sensor_node.warning_period):
            logging.debug(u'sensor node did not report : ' + unicode(sensor_node))
            report = False
            if sensor_node.warning_count + 1 > 3:
                report = False
            elif sensor_node.warning_count == 0:
                report = True
            elif sensor_node.last_warning_date.replace(tzinfo=None) < now - datetime.timedelta(seconds=sensor_node.warning_period):
                report = True

            if report:
                message = u'센서가 %d분동안 정보를 보내지 않았습니다. (%d/%d) (' % (sensor_node.warning_period / 60, sensor_node.warning_count+1, 3)
                message += sensor_node.user.username + u':' + sensor_node.name
                message += u')'
                try:
                    user_info = UserInfo.objects.get(user=sensor_node.user)
                    for contact in UserContact.objects.filter(user_info=user_info):
                        send_sms(contact.phone_number, message)

                    sensor_node.warning_count += 1
                    now_utc = now.replace(tzinfo=pytz.utc)
                    sensor_node.last_warning_date = now_utc.astimezone(pytz.timezone(user_info.timezone))
                    sensor_node.save()

                    logging.info(u'Sent SMS for dead sensor : ' + unicode(sensor_node))
                except UserInfo.DoesNotExist:
                    logging.error(u'no user information for dead sensor : ' + sensor_node.user.username)

    logging.info('cronjob finished')
    return render_to_response('sensor_page/cronjobdone.html')

