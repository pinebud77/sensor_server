from django.contrib import admin
from sensor_page.models import *


class UserContactInline(admin.TabularInline):
    model = UserContact
    extra = 2


class UserInfoAdmin(admin.ModelAdmin):
    inlines = [UserContactInline]


class MeasureInline(admin.TabularInline):
    model = MeasureEntry
    extra = 3


class SensorAdmin(admin.ModelAdmin):
    inlines = [MeasureInline]
    #ToDO:sequence for high / low threshold


class SensorInline(admin.TabularInline):
    model = Sensor
    extra = 2


class SensorNodeAdmin(admin.ModelAdmin):
    inlines = [SensorInline]


admin.site.register(UserInfo, UserInfoAdmin)
admin.site.register(SensorNode, SensorNodeAdmin)
admin.site.register(Sensor, SensorAdmin)