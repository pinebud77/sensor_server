# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate, login, logout

from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.views.decorators.csrf import csrf_exempt

from sensor_page.models import *
from sensor_page.forms import *
from sensor_page.utils import *

import pytz
import datetime

import os
import StringIO
from munjanara_sms import send_sms, send_bulk_sms

import logging
import thread


os.environ["MATPLOTLIBDATA"] = os.getcwdu()
os.environ["MPLCONFIGDIR"] = os.getcwdu()
import subprocess


def no_popen(*args, **kwargs):
    raise OSError("forbjudet")


subprocess.Popen = no_popen
subprocess.PIPE = None
subprocess.STDOUT = None

import matplotlib.pyplot as plt


def send_sms_for_node(sensor_node, text):
    try:
        userinfo = UserInfo.objects.only('user').get(user=sensor_node.user)
        user_contacts = UserContact.objects.only('user_info', 'phone_number').filter(user_info=userinfo)
        for contact in user_contacts:
            if contact.send_sms:
                send_sms(contact.phone_number, text)
                logging.info(u'sent SMS : ' + contact.phone_number + u' : ' + text)
    except UserInfo.DoesNotExist:
        logging.error(u'User info was not specified : ' + sensor_node.user.username)


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


def test_page(request):
    logout(request)
    user = authenticate(username='young', password='11111111')
    login(request, user)

    return redirect('/sensor/userinfo/')


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


def handle_first_and_resume(measure, first):
    resume = False

    sensor_node = measure.sensor.sensor_node
    if sensor_node.warning_count:
        sensor_node.warning_count = 0
        sensor_node.save()
        resume = True

    if first:
        if sensor_node.first_report_count != 0:
            first = False
        sensor_node.first_report_count += 1
        sensor_node.save()

    if first or resume:
        if first:
            text = u'센서가 첫 데이터를 보냈습니다. : '
            logging.info(u'sent SMS for the first data : ' + sensor_node.user.username + ':' + sensor_node.name)
        else:
            text = u'센서가 다시 데이터를 보냈습니다. : '
            logging.info(u'sent SMS for the resume report : ' + sensor_node.user.username + ':' + sensor_node.name)
        text += sensor_node.name + u' : '
        text += get_sensor_type_str(measure.sensor.type) + u' : '
        text += '%.1f' % measure.value

        send_sms_for_node(sensor_node, text)

    return first or resume


def check_range(measure):
    sensor = measure.sensor

    report = False
    if sensor.high_threshold is not None and measure.value > sensor.high_threshold:
        report = True
    elif sensor.low_threshold is not None and measure.value < sensor.low_threshold:
        report = True

    if report:
        text = u'범위를 넘었습니다. '
        text += sensor.sensor_node.name
        text += u' : '
        text += get_sensor_type_str(measure.sensor.type) + u' : '
        text += '%.1f' % measure.value

        send_sms_for_node(sensor.sensor_node, text)

    return report


@csrf_exempt
def input_page(request):
    if request.method == 'POST':
        if not 'secure_key' in request.POST:
            logging.error('no secure_key in the request')
            return render_to_response('sensor_page/error.html')
        if not 'mac_address' in request.POST:
            logging.error('no mac_address in the request')
            return render_to_response('sensor_page/error.html')
        if not 'type' in request.POST:
            logging.error('no type in the request')
            return render_to_response('sensor_page/error.html')
        if not 'value' in request.POST:
            logging.error('no value in the request')
            return render_to_response('sensor_page/error.html')
        if not 'rssi' in request.POST:
            logging.error('no rssi in the request')
            return render_to_response('sensor_page/error.html')
        if not 'first' in request.POST:
            logging.error('no first in the request')
            return render_to_response('sensor_page/error.html')

        secure_key = request.POST.get('secure_key')
        if secure_key != get_hash_from_mac(request.POST['mac_address']):
            logging.error("mismatching credential")
            return render_to_response('sensor_page/error.html')

        sensor_node = SensorNode.objects.get(mac_address=request.POST['mac_address'])
        sensor = Sensor.objects.get(sensor_node=sensor_node, type=int(request.POST['type']))

        measure = MeasureEntry()
        measure.value = float(request.POST['value']) / 10.0
        measure.sensor = sensor
        measure.save()

        sensor_node.last_update = measure.date
        sensor_node.warning_start = measure.date + datetime.timedelta(seconds=sensor_node.warning_period)
        sensor_node.last_rssi = int(request.POST['rssi'])
        sensor_node.last_ip = get_client_ip(request)
        sensor_node.save()

        first = False
        if request.POST.get('first') == '1':
            first = True

        handle_first_and_resume(measure, first)
        check_range(measure)

        if sensor_node.last_rssi < -80:
            logging.warning(u'RSSI too low : ' + unicode(sensor.sensor_node))
            #ToDO: handle low rssi
            pass

        logging.debug(u'measurement saved : ' + sensor.sensor_node.name + ':' + unicode(sensor.type)
                      + u':' + unicode(sensor_node.last_rssi))

        context_dict = {
            'sensor': sensor,
            'sensor_node': sensor_node,
        }

        return render_to_response('sensor_page/saved.txt', context_dict)

    else:
        form = InputForm()
        return render_to_response('sensor_page/input.html', {'form': form})


class UtcTzinfo(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return 'UTC'

    def olsen_name(self):
        return 'UTC'


def dynamic_png(sensor, display_fmt, time_offset):
    #TODO: use localization for date format
    measure_entries = None
    date_max = datetime.datetime.utcnow()
    date_max = date_max.replace(tzinfo=pytz.utc)

    marker = ''

    userinfo = UserInfo.objects.get(user=sensor.sensor_node.user)
    tz = pytz.timezone(userinfo.timezone)

    if display_fmt == "hour":
        delta = datetime.timedelta(hours=1)
        date_max -= datetime.timedelta(hours=time_offset)
        marker = '.'
    elif display_fmt == "day":
        delta = datetime.timedelta(days=1)
        date_max -= datetime.timedelta(days=time_offset)
    elif display_fmt == "week":
        delta = datetime.timedelta(weeks=1)
        date_max -= datetime.timedelta(weeks=time_offset)
    elif display_fmt == "month":
        delta = datetime.timedelta(weeks=4)
        date_max -= datetime.timedelta(weeks=time_offset*4)
    else:
        delta = datetime.timedelta(days=365)
        date_max -= datetime.timedelta(days=time_offset*365)

    try:
        measure_entries = MeasureEntry.objects.filter(sensor=sensor,
                                                      date__gt=(date_max - delta - datetime.timedelta(days=1)),
                                                      date__lt=(date_max + datetime.timedelta(days=1)))
    except MeasureEntry.DoesNotExist:
        pass

    if not measure_entries:
        return None

    if len(measure_entries) == 1:
        marker = '.'

    date_min = date_max - delta

    dates = []
    values = []
    highs = []
    lows = []

    y_max = -1000.0
    y_min = 1000.0
    margin = 1.0

    if sensor.high_threshold is not None:
        highs = [sensor.high_threshold, sensor.high_threshold]
        y_max = sensor.high_threshold + margin
    if sensor.low_threshold is not None:
        lows = [sensor.low_threshold, sensor.low_threshold]
        y_min = sensor.low_threshold - margin

    date_max = date_max.replace(tzinfo=None)
    date_min = date_min.replace(tzinfo=None)

    warning_delta = datetime.timedelta(seconds=sensor.sensor_node.warning_period)

    date_max += tz.utcoffset(date_max)
    date_min += tz.utcoffset(date_min)

    data_in_range = False

    for measure in measure_entries:
        measure.date = measure.date.replace(tzinfo=None)
        measure.date += tz.utcoffset(measure.date)
        if dates and dates[-1] < measure.date - warning_delta:
            dates.append(dates[-1])
            values.append(None)
        dates.append(measure.date)
        values.append(measure.value)

        if date_min <= measure.date <= date_max:
            if measure.value > y_max - margin:
                y_max = measure.value + margin
            if measure.value < y_min + margin:
                y_min = measure.value - margin
            margin = (y_max - y_min) * 0.1
            if margin < 1.0:
                margin = 1.0
            data_in_range = True

    if not data_in_range:
        return None

    try:
        fig, ax = plt.subplots()
        ax.plot_date(dates, values, linestyle='solid', color='blue', marker=marker)

        if highs:
            ax.plot_date([date_min, date_max], highs, linestyle='solid', color='red', linewidth=3, marker="")
        if lows:
            ax.plot_date([date_min, date_max], lows, linestyle='solid', color='red', linewidth=3, marker="")

        ax.set_xlim(date_min, date_max)
        ax.set_ylim(y_min, y_max)
        ax.grid(True)

        fig.set_size_inches(6, 3.5)
        fig.autofmt_xdate()
        fig.tight_layout()

        rv = StringIO.StringIO()
        plt.savefig(rv, format="png")
        plt.close()

        return """<img src="data:image/png;base64,%s"/>""" % rv.getvalue().encode("base64").strip()
    finally:
        plt.close()


def user_info(request, display_fmt="day", time_offset=0):
    if not request.user.is_authenticated():
        return redirect('/sensor/login/')

    context = RequestContext(request)

    if time_offset < 0:
        time_offset = 0

    phone_numbers = []
    sensor_nodes = []
    sensors = []

    try:
        userinfo = UserInfo.objects.get(user=request.user)

        user_contacts = []
        try:
            user_contacts += UserContact.objects.filter(user_info=userinfo)
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
        sensor_node.reporting_period /= 60
        sensor_node.warning_period /= 60
        try:
            sensors += Sensor.objects.filter(sensor_node=sensor_node)
        except Sensor.DoesNotExist:
            pass

    for sensor in sensors:
        try:
            sensor.pic = dynamic_png(sensor, display_fmt, int(time_offset))
        except MeasureEntry.DoesNotExist:
            pass

    context_dict = {
        'username': request.user.username,
        'phone_numbers': phone_numbers,
        'sensor_nodes': sensor_nodes,
        'sensors': sensors,
        'display_fmt': display_fmt,
        'time_offset_prev': int(time_offset) + 1,
        'time_offset_next': int(time_offset) - 1,
    }

    return render_to_response('sensor_page/userinfo.html', context_dict, context)


def cron_job(request):
    now = datetime.datetime.now()
    now = now.replace(tzinfo=pytz.utc)

    sms_tuples = []

    sensor_nodes = SensorNode.objects.filter(warning_count__lt=3, warning_start__lt=now)

    for sensor_node in sensor_nodes:
        message = u'센서가 %d분동안 정보를 보내지 않았습니다. (%d/%d) ('\
                  % (sensor_node.warning_period / 60, sensor_node.warning_count+1, 3)
        message += sensor_node.user.username + u':' + sensor_node.name
        message += u')'
        try:
            userinfo = UserInfo.objects.get(user=sensor_node.user)
            for contact in UserContact.objects.filter(user_info=userinfo):
                if contact.send_sms:
                    sms_tuples.append((contact.phone_number, message))
                    logging.info(u'Sending SMS for dead sensor : ' + unicode(contact.phone_number)
                                 + u' : ' + unicode(sensor_node))

            sensor_node.warning_count += 1
            now_utc = now.replace(tzinfo=pytz.utc)
            sensor_node.warning_start = now_utc.astimezone(pytz.timezone(userinfo.timezone))\
                                        + datetime.timedelta(seconds=sensor_node.warning_period)
            sensor_node.last_warning_date = now_utc.astimezone(pytz.timezone(userinfo.timezone))
            sensor_node.save()
        except UserInfo.DoesNotExist:
            logging.error(u'no user information for dead sensor : ' + sensor_node.user.username)

    if sms_tuples:
        thread.start_new_thread(send_bulk_sms, (sms_tuples,))

    return render_to_response('sensor_page/cronjobdone.html')

