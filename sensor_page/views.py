# -*- coding: utf-8 -*-

from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext, loader, Context
from django.shortcuts import render_to_response, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

from sensor_page.models import *
from sensor_page.forms import *
from sensor_page.utils import *

import pytz
import datetime

from munjanara_sms import send_sms

import logging
import threading

import cStringIO

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


# list of mobile User Agents
mobile_uas = [
    'w3c ','acs-','alav','alca','amoi','audi','avan','benq','bird','blac',
    'blaz','brew','cell','cldc','cmd-','dang','doco','eric','hipt','inno',
    'ipaq','java','jigs','kddi','keji','leno','lg-c','lg-d','lg-g','lge-',
    'maui','maxo','midp','mits','mmef','mobi','mot-','moto','mwbp','nec-',
    'newt','noki','oper','palm','pana','pant','phil','play','port','prox',
    'qwap','sage','sams','sany','sch-','sec-','send','seri','sgh-','shar',
    'sie-','siem','smal','smar','sony','sph-','symb','t-mo','teli','tim-',
    'tosh','tsm-','upg1','upsi','vk-v','voda','wap-','wapa','wapi','wapp',
    'wapr','webc','winw','winw','xda','xda-'
]

mobile_ua_hints = ['SymbianOS', 'Opera Mini', 'iPhone', 'Android']


def mobile_browser(request):
    mobile = False
    ua = request.META['HTTP_USER_AGENT'].lower()[0:4]

    if ua in mobile_uas:
        mobile = True
    else:
        for hint in mobile_ua_hints:
            if request.META['HTTP_USER_AGENT'].find(hint) > 0:
                mobile = True

    return mobile


class SmsThread (threading.Thread):
    def __init__(self, phone_number, msg):
        threading.Thread.__init__(self)
        self.phone_number = phone_number
        self.sms_message = msg

    def run(self):
        send_sms(self.phone_number, self.sms_message)


def send_sms_for_node(sensor_node, text):
    threads = []
    try:
        userinfo = UserInfo.objects.only('user').get(user=sensor_node.user)
        user_contacts = UserContact.objects.only('user_info', 'phone_number').filter(user_info=userinfo)
        for contact in user_contacts:
            if contact.send_sms:
                t = SmsThread(contact.phone_number, text)
                t.start()
                threads.append(t)
    except UserInfo.DoesNotExist:
        logging.error(u'User info was not specified : ' + sensor_node.user.username)

    for t in threads:
        t.join()


def login_page(request):
    context = RequestContext(request)

    if request.method == 'POST':
        fields = ('username', 'password')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)
        if not user:
            return render_to_response('kitchen_theme/nouser.html')
        if not user.is_active:
            return render_to_response('kitchen_theme/inact_user.html')
        login(request, user)
        logging.info(u'user logged in : ' + unicode(user))
        return redirect('/sensor/userinfo/')

    else:
        form = LoginForm()
        return render_to_response('/', {'form': form}, context)


def check_fields_in_post(fields, post):
    for field in fields:
        if not field in post:
            logging.error('no ' + field + 'in the request')
            return False

    return True


@csrf_exempt
def app_node_page(request):
    context = RequestContext(request)
    if request.method == 'POST':
        fields = ('username', 'password', 'secure_key', 't_low', 't_high', 'h_low', 'h_high',
                  'name', 'report_period', 'alarm_period', 'mac_address')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        username = request.POST.get('username')
        password = request.POST.get('password')
        secure_key = request.POST.get('secure_key')

        user = authenticate(username=username, password=password)
        if not user:
            logging.error(u'User login failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if not user.is_active:
            logging.error(u'User not active ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if secure_key != get_app_hash(username, password):
            logging.error(u'Secure hash failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        mac_address = request.POST.get('mac_address')

        try:
            sensor_node = SensorNode.objects.get(mac_address=mac_address)

            try:
                t_sensor = Sensor.objects.get(sensor_node=sensor_node, type=0)
            except Sensor.DoesNotExist:
                t_sensor = Sensor()
                t_sensor.type = 0
                t_sensor.sensor_node = sensor_node

            try:
                h_sensor = Sensor.objects.get(sensor_node=sensor_node, type=1)
            except Sensor.DoesNotExist:
                h_sensor = Sensor()
                h_sensor.type = 0
                h_sensor.sensor_node = sensor_node

        except SensorNode.DoesNotExist:
            sensor_node = SensorNode()
            sensor_node.user = user

            t_sensor = Sensor()
            t_sensor.type = 0
            t_sensor.sensor_node = sensor_node
            h_sensor = Sensor()
            h_sensor.type = 1
            h_sensor.sensor_node = sensor_node

        if user != sensor_node.user:
            logging.error(u'sensor register from different user ' + username + u' mac ' + mac_address)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        sensor_node.name = request.POST.get('name')

        sensor_node.first_report_count = 0
        t_sensor.low_threshold = None
        t_sensor.high_threshold = None
        h_sensor.low_threshold = None
        h_sensor.high_threshold = None
        sensor_node.warning_period = None

        if request.POST.get('t_low') != 'N':
            t_sensor.low_threshold = int(request.POST.get('t_low'))

        if request.POST.get('t_high') != 'N':
            t_sensor.high_threshold = int(request.POST.get('t_high'))

        if request.POST.get('h_low') != 'N':
            h_sensor.low_threshold = int(request.POST.get('h_low'))

        if request.POST.get('h_high') != 'N':
            h_sensor.high_threshold = int(request.POST.get('h_high'))

        if request.POST.get('report_period') != 'N':
            sensor_node.reporting_period = int(request.POST.get('report_period'))

        if request.POST.get('alarm_period') != 'N':
            sensor_node.warning_period = int(request.POST.get('alarm_period'))

        sensor_node.save()
        t_sensor.save()
        h_sensor.save()

        t = loader.get_template('sensor_page/success.txt')
        c = Context({})
        return HttpResponse(t.render(c), content_type='text/plain')

    else:
        return render_to_response('sensor_page/error.html', {}, context)


@csrf_exempt
def app_phone_page(request):
    context = RequestContext(request)
    if request.method == 'POST':
        fields = ('username', 'password', 'secure_key', 'phone_number')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        username = request.POST.get('username')
        password = request.POST.get('password')
        secure_key = request.POST.get('secure_key')

        user = authenticate(username=username, password=password)
        if not user:
            logging.error(u'User login failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if not user.is_active:
            logging.error(u'User not active ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if secure_key != get_app_hash(username, password):
            logging.error(u'Secure hash failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        userinfo = UserInfo.objects.filter(user=user)
        if not userinfo:
            logging.error(u'Secure hash failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        phone_number = request.POST.get('phone_number')

        contact = UserContact()
        contact.user_info = userinfo[0]
        contact.phone_number = phone_number
        contact.phone_type = 0
        contact.save()

        t = loader.get_template('sensor_page/success.txt')
        c = Context({})
        return HttpResponse(t.render(c), content_type='text/plain')

    else:
        return render_to_response('sensor_page/error.html', {}, context)


@csrf_exempt
def app_register_page(request):
    context = RequestContext(request)
    if request.method == 'POST':
        fields = ('username', 'password', 'secure_key', 'family_name', 'first_name', 'email')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        username = request.POST.get('username')
        password = request.POST.get('password')
        secure_key = request.POST.get('secure_key')

        if secure_key != get_app_hash(username, password):
            logging.error(u'Secure hash failed ' + username)
            logging.error(secure_key)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        try:
            User.objects.get(username=username)
            found = True
        except User.DoesNotExist:
            found = False

        if found:
            logging.error(u'Username exist ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        family_name = request.POST.get('family_name')
        first_name = request.POST.get('first_name')
        email = request.POST.get('email')

        user = User.objects.create_user(username, email, password)
        user.is_staff = False
        user.is_active = True
        user.last_name = family_name
        user.first_name = first_name
        user.save()

        userinfo = UserInfo()
        userinfo.user = user
        userinfo.save()

        t = loader.get_template('sensor_page/success.txt')
        c = Context({})
        return HttpResponse(t.render(c), content_type='text/plain')

    else:
        return render_to_response('sensor_page/error.html', {}, context)


@csrf_exempt
def app_login_page(request):
    context = RequestContext(request)
    if request.method == 'POST':
        fields = ('username', 'password', 'secure_key')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        username = request.POST.get('username')
        password = request.POST.get('password')
        secure_key = request.POST.get('secure_key')

        user = authenticate(username=username, password=password)
        if not user:
            logging.error(u'User login failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if not user.is_active:
            logging.error(u'User not active ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')
        if secure_key != get_app_hash(username, password):
            logging.error(u'Secure hash failed ' + username)
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        t = loader.get_template('sensor_page/success.txt')
        c = Context({})
        return HttpResponse(t.render(c), content_type='text/plain')

    else:
        return render_to_response('sensor_page/error.html', {}, context)


def logout_page(request):
    logout(request)
    return redirect('/')


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
        else:
            text = u'센서가 다시 데이터를 보냈습니다. : '
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
        fields = ('secure_key', 'mac_address', 'type', 'value', 'rssi', 'first')
        if not check_fields_in_post(fields, request.POST):
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        secure_key = request.POST.get('secure_key')
        mac_address = request.POST.get('mac_address');
        if secure_key != get_hash_from_mac(mac_address):
            logging.error("mismatching credential")
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        try:
            sensor_node = SensorNode.objects.get(mac_address=mac_address)
        except SensorNode.DoesNotExist:
            logging.error(u'No Sensor Node for MAC ' + unicode(mac_address))
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

        try:
            sensor = Sensor.objects.get(sensor_node=sensor_node, type=int(request.POST['type']))
        except Sensor.DoesNotExist:
            logging.error(u'No Sensor for MAC ' + unicode(mac_address))
            t = loader.get_template('sensor_page/error.txt')
            c = Context({})
            return HttpResponse(t.render(c), content_type='text/plain')

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

        if sensor_node.last_rssi < -85:
            logging.warning(u'RSSI too low : ' + unicode(sensor_node))
            text = u'센서노드의 무선 세기가 낮습니다. '
            text += sensor_node.user.username + u':'
            text += sensor_node.name + u' (' + unicode(sensor_node.last_rssi) + u')'
            send_sms_for_node(sensor_node, text)

        context_dict = {
            'sensor': sensor,
            'sensor_node': sensor_node,
        }

        t = loader.get_template('sensor_page/saved.txt')
        c = Context(context_dict)
        return HttpResponse(t.render(c), content_type='text/plain')

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


def dynamic_png(sensor, display_fmt, time_offset, is_mobile=False):
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
        measure_entries = MeasureEntry.objects.defer('sensor').filter(sensor=sensor,
                                                      date__gt=(date_max - delta - datetime.timedelta(hours=1)),
                                                      date__lt=(date_max + datetime.timedelta(hours=1))
                                                        ).order_by('-date')
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

    warning_delta = datetime.timedelta(seconds=sensor.sensor_node.warning_period*2)

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

    mpl.rcParams['axes.edgecolor'] = 'black'
    mpl.rcParams['axes.facecolor'] = 'white'
    mpl.rcParams['figure.facecolor'] = 'white'
    mpl.rcParams['figure.edgecolor'] = 'white'
    mpl.rcParams['figure.autolayout'] = 'True'
    mpl.rcParams['axes.formatter.use_locale'] = 'True'
    mpl.rcParams['savefig.edgecolor'] = 'white'
    mpl.rcParams['savefig.facecolor'] = 'white'

    fig = Figure(figsize=[7, 4])
    ax = fig.add_axes([0.07, 0.2, 0.92, 0.75], axisbg='white')
    font = {'size': 10}
    mpl.rc('font', **font)
    fig.patch.set_alpha(1)

    ax.plot_date(dates, values, linestyle='solid', color='blue', marker=marker)

    if highs:
        ax.plot_date([date_min, date_max], highs, linestyle='solid', color='red', linewidth=3, marker="")
    if lows:
        ax.plot_date([date_min, date_max], lows, linestyle='solid', color='red', linewidth=3, marker="")

    ax.set_xlim(date_min, date_max)
    ax.set_ylim(y_min, y_max)
    ax.grid(True)

    fig.autofmt_xdate()

    canvas = FigureCanvasAgg(fig)

    buf = cStringIO.StringIO()
    canvas.print_png(buf)

    if is_mobile:
        height = 160
        width = 280
    else:
        height = 320
        width = 560

    return """<img height=%d width=%d src="data:image/png;base64,%s"/>""" % (height, width, buf.getvalue().encode("base64").strip())


def sensor_node_page(request, sensor_node_id, display_fmt="day", time_offset=0):
    if not request.user.is_authenticated():
        return redirect('/')

    context = RequestContext(request)

    if time_offset < 0:
        time_offset = 0

    sensors = []

    try:
        sensor_node = SensorNode.objects.get(id=int(sensor_node_id))
    except SensorNode.DoesNotExist:
        return render_to_response('kitchen_theme/no_sensor_node.html')

    if not request.user.is_staff and request.user != sensor_node.user:
        return render_to_response('kitchen_theme/no_privilege.html')

    for sensor in Sensor.objects.filter(sensor_node=sensor_node):
        sensor.pic = dynamic_png(sensor, display_fmt, int(time_offset), is_mobile=mobile_browser(request))
        sensors.append(sensor)
    sensor_node.reporting_period /= 60
    sensor_node.warning_period /= 60

    context_dict = {
        'sensor_node': sensor_node,
        'sensors': sensors,
        'display_fmt': display_fmt,
        'time_offset_prev': int(time_offset) + 1,
        'time_offset_next': int(time_offset) - 1,
    }

    if mobile_browser(request):
        return render_to_response('kitchen_theme/sensor_node.html', context_dict, context)
    else:
        return render_to_response('kitchen_theme/sensor_node_pc.html', context_dict, context)


def sensor_list(request):
    if not request.user.is_authenticated():
        return redirect('/')

    context = RequestContext(request)

    phone_numbers = []
    sensor_nodes = []
    sensors = []

    cur_time = datetime.datetime.utcnow()
    cur_time = cur_time.replace(tzinfo=pytz.utc)

    try:
        userinfo = UserInfo.objects.get(user=request.user)

        user_contacts = []
        user_contacts += UserContact.objects.filter(user_info=userinfo)
        for contact in user_contacts:
            phone_numbers.append(contact.phone_number)
    except UserInfo.DoesNotExist:
        pass

    for sensor_node in SensorNode.objects.filter(user=request.user):
        sensor_nodes.append(sensor_node)
        sensor_node.reporting_period /= 60
        sensor_node.warning_period /= 60
        for sensor in Sensor.objects.filter(sensor_node=sensor_node):
            try:
                last_measure = MeasureEntry.objects.filter(sensor=sensor).order_by('-date')[0]
                sensor.last_value = last_measure.value
            except MeasureEntry.DoesNotExist:
                sensor.last_value = None

            if cur_time > sensor.sensor_node.warning_start:
                sensor.inactive = True
            else:
                sensor.inactive = False

            sensor.sensor_node.reporting_period /= 60
            sensor.sensor_node.warning_period /= 60

            sensors.append(sensor)

    context_dict = {
        'user': request.user,
        'username': request.user.username,
        'phone_numbers': phone_numbers,
        'sensor_nodes': sensor_nodes,
        'sensors': sensors,
    }
    if mobile_browser(request):
        return render_to_response('kitchen_theme/sensor_list.html', context_dict, context)
    else:
        return render_to_response('kitchen_theme/sensor_list_pc.html', context_dict, context)


def index_page(request):
    context = RequestContext(request)

    context_dict = {
        'user': request.user,
    }

    return render_to_response('kitchen_theme/index_page.html', context_dict, context)

def contact_page(request):
    context = RequestContext(request)

    return render_to_response('kitchen_theme/contact.html', {}, context)


def admin_page(request):
    context = RequestContext(request)

    if not request.user.is_staff:
        return render_to_response('kitchen_theme/no_privilege.html')

    sensor_nodes = SensorNode.objects.all()

    for sensor_node in sensor_nodes:
        sensor_node.reporting_period /= 60
        sensor_node.warning_period /= 60

    context_dict = {
        'sensor_nodes': sensor_nodes
    }
    return render_to_response('sensor_page/admin_page.html', context_dict, context)


def cron_job(request):
    now = datetime.datetime.now()
    now = now.replace(tzinfo=pytz.utc)

    thread_list = []

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
                    t = SmsThread(contact.phone_number, message)
                    t.start()
                    thread_list.append(t)

            sensor_node.warning_count += 1
            now_utc = now.replace(tzinfo=pytz.utc)
            sensor_node.warning_start = now_utc.astimezone(pytz.timezone(userinfo.timezone))\
                                        + datetime.timedelta(seconds=sensor_node.warning_period)
            sensor_node.last_warning_date = now_utc.astimezone(pytz.timezone(userinfo.timezone))
            sensor_node.save()
        except UserInfo.DoesNotExist:
            logging.error(u'no user information for dead sensor : ' + sensor_node.user.username)

    for t in thread_list:
        t.join()

    return render_to_response('sensor_page/cronjobdone.html')

