# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate, login

from django.template import RequestContext
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse

from sensor_page.models import *
from sensor_page.forms import *

import pytz
import datetime

import os
import StringIO
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

        return render_to_response('sensor_page/settings_values.txt', context_dict, context)
    else:
        form = SettingForm()
        return render_to_response('sensor_page/settings.html', {'form': form}, context)


def loginpage(request):
    context = RequestContext(request)

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('sensor_page/nouser.html')
        if not user.is_active:
            return render_to_response('isensor_page/nact_user.html')
        login(request, user)
        return redirect('/sensor/userinfo/')

    else:
        form = LoginForm()
        return render_to_response('sensor_page/login.html', {'form': form}, context)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def input(request):
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

        sensor_node = SensorNode.objects.get(mac_address=request.POST['mac_address'])
        sensor = Sensor.objects.get(sensor_node=sensor_node, type=int(request.POST['type']))

        measure = MeasureEntry()
        measure.ip = get_client_ip(request)
        measure.value = float(request.POST['value'])
        measure.sensor = sensor
        measure.save()

        sensor_node.last_update = measure.date
        sensor_node.save()

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
    try:
        sensor = Sensor.objects.get(pk=sensor_id)
        try:
            measure_entries = MeasureEntry.objects.filter(sensor=sensor)
        except MeasureEntry.DoesNotExist:
            pass
    except Sensor.DoesNotExist:
        pass

    if not measure_entries:
        return None

    dates = []
    values = []

    highs = [measure_entries[0].sensor.high_threshold, measure_entries[0].sensor.high_threshold]
    lows = [measure_entries[0].sensor.low_threshold, measure_entries[0].sensor.low_threshold]

    ymax = highs[0] + 10
    ymin = lows[0] - 10

    user_info = UserInfo.objects.get(user=sensor.sensor_node.user)
    tz = pytz.timezone(user_info.timezone)

    for measure in measure_entries:
        measure.date = measure.date.replace(tzinfo=None)
        measure.date += tz.utcoffset(measure.date)
        dates.append(measure.date)
        values.append(measure.value)
        if measure.value > highs[0]:
            ymax = measure.value + 10
        elif measure.value < lows[0]:
            ymin = measure.value - 10

    highs = [measure_entries[0].sensor.high_threshold, measure_entries[0].sensor.high_threshold]
    lows = [measure_entries[0].sensor.low_threshold, measure_entries[0].sensor.low_threshold]

    try:
        fig, ax = plt.subplots()
        ax.plot_date(dates, values,linestyle='solid', color='blue')

        date_max = dates[-1]
        if format == "hour":
            delta = datetime.timedelta(hours = 1)
            def xformat(x):
                return '%d:%d'%(x.hour, x.minute)
            ax.format_xdata = xformat
        elif format == "day":
            delta = datetime.timedelta(days = 1)
        elif format == "week":
            delta = datetime.timedelta(weeks = 1)
        elif format == "month":
            delta = datetime.timedelta(weeks=4)
        else:
            delta = datetime.timedelta(days = 365)
        date_min = date_max - delta

        ax.plot_date([date_min, date_max], highs, linestyle='solid', color='red', linewidth=3, marker="")
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
    if not request.user.is_authenticated():
        return render_to_response('sensor_page/nouser.html')

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