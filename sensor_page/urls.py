from django.conf.urls import patterns, url
from sensor_page import views

urlpatterns = patterns('',
                       url(r'^login/', views.loginpage),
                       url(r'^userinfo/(?P<format>\w+)/', views.userinfo),
                       url(r'^userinfo/', views.userinfo),
                       url(r'^input/', views.input),
                       url(r'^settings/', views.settings),
                       url(r'^ssettings/', views.sensor_settings),
                       )