# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
import datetime
import pytz


class UserInfo(models.Model):
    user = models.ForeignKey(User, db_index=True)
    expire_date = models.DateField(default=None, null=True, blank=True)

    TZ_CHOICES = [(tz, tz) for tz in pytz.all_timezones]
    timezone = models.CharField(max_length=30, default='Asia/Seoul', choices=TZ_CHOICES)

    def __unicode__(self):
        desc = self.user.username + u' (만료 : ' + unicode(self.expire_date) + u') '
        try:
            for contact in UserContact.objects.filter(user_info=self):
                desc += contact.phone_number + u' '
        except UserContact.DoesNotExist:
            pass
        return desc


class UserContact(models.Model):
    user_info = models.ForeignKey(UserInfo, db_index=True)
    phone_number = models.CharField(max_length=30)
    send_sms = models.BooleanField(default=True)

    PHONE_TYPE_CHOICES = (
        (0, '피쳐폰'),
        (1, '안드로이드'),
        (2, '아이폰'),
    )
    phone_type = models.IntegerField(choices=PHONE_TYPE_CHOICES, default=0)

    def __unicode__(self):
        return self.user_info.user.username + u' (' + self.phone_number + u')'


class SensorNode(models.Model):
    user = models.ForeignKey(User, db_index=True)
    name = models.CharField(max_length=20)
    mac_address = models.CharField(max_length=20, unique=True)
    reporting_period = models.IntegerField(default=600)
    warning_period = models.IntegerField(default=3600, null=True, blank=True)
    last_update = models.DateTimeField(auto_now_add=True)
    warning_start = models.DateTimeField(default=None, null=True, blank=True)
    last_warning_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    warning_count = models.IntegerField(default=0)
    last_rssi = models.IntegerField(default=-60)
    last_ip = models.IPAddressField(default=None, null=True, blank=True)
    first_report_count = models.IntegerField(default=0)

    def __unicode__(self):
        desc = self.user.username + u' ' + self.name + u' MAC(' + self.mac_address + u')'
        if self.warning_count:
            desc += u' warning(' + unicode(self.warning_count) + u')'
        if self.first_report_count:
            desc += u' reset_count(' + unicode(self.first_report_count) + u')'
        return desc


class Sensor(models.Model):
    sensor_node = models.ForeignKey(SensorNode, db_index=True)

    SENSOR_TYPE_CHOICES = (
        (0, '온도'),
        (1, '습도'),
        (2, '압력'),
    )
    type = models.IntegerField(choices=SENSOR_TYPE_CHOICES)
    high_threshold = models.FloatField(default=None, null=True, blank=True)
    low_threshold = models.FloatField(default=None, null=True, blank=True)

    def __unicode__(self):
        desc = self.sensor_node.user.username + ':'
        desc += self.sensor_node.name + ':'
        if self.type == 0:
            desc += u'(온도)'
        elif self.type == 1:
            desc += u'(습도)'
        return desc


class MeasureEntry(models.Model):
    #ToDO: consider DB optimization using raw SQL for measure entries
    sensor = models.ForeignKey(Sensor, db_index=True)
    value = models.FloatField()
    date = models.DateTimeField('measured date', auto_now_add=True, db_index=True)

    def __unicode__(self):
        desc = unicode(self.value) + ':' + unicode(self.date)
        return desc
