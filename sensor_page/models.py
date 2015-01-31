# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
import pytz


class UserInfo(models.Model):
    user = models.ForeignKey(User)
    expire_date = models.DateField()

    TZ_CHOICES = [(tz, tz) for tz in pytz.all_timezones]
    timezone = models.CharField(max_length=30, default='Asia/Seoul', choices=TZ_CHOICES)

    def __unicode__(self):
        return self.user.username + u' (만료 : ' + unicode(self.expire_date) + u')'


class UserContact(models.Model):
    user_info = models.ForeignKey(UserInfo)
    phone_number = models.CharField(max_length=30)

    def __unicode__(self):
        return self.user_info.user.username + u' (' + self.phone_number + u')'


class SensorNode(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField(max_length=20)
    mac_address = models.CharField(max_length=20, unique=True)
    reporting_period = models.IntegerField(default=600)
    warning_period = models.IntegerField(default=3600, null=True)
    last_update = models.DateTimeField(auto_now_add=True)
    last_warning_date = models.DateTimeField(null=True)
    warning_count = models.IntegerField(null=True)

    def __unicode__(self):
        return self.user.username + u':' + self.name


class Sensor(models.Model):
    sensor_node = models.ForeignKey(SensorNode)

    SENSOR_TYPE_CHOICES = (
        (0, '온도'),
        (1, '습도'),
    )
    type = models.IntegerField(choices=SENSOR_TYPE_CHOICES)
    high_threshold = models.FloatField(null=True)
    low_threshold = models.FloatField(null=True)

    def __unicode__(self):
        repr = self.sensor_node.user.username + ':'
        repr += self.sensor_node.name + ':'
        if self.type == 0:
            repr += '(' + 'Thermal' + ')'
        elif self.type == 1:
            repr += '(' + 'Humidity' + ')'
        return repr


class MeasureEntry(models.Model):
    sensor = models.ForeignKey(Sensor)
    value = models.FloatField()
    date = models.DateTimeField('measured date', auto_now_add=True)
    ip = models.IPAddressField(null=True)

    def __unicode__(self):
        repr = unicode(self.value) + ':' + unicode(self.date)
        return repr
