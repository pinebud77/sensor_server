from django.conf.urls import patterns, url
from sensor_page import views

urlpatterns = patterns('',
                       url(r'^login/', views.login_page),
                       url(r'^logout/', views.logout_page),
                       url(r'^cronjob/', views.cron_job),
                       url(r'^userinfo/(?P<display_fmt>\w+)/', views.userinfo),
                       url(r'^userinfo/', views.userinfo),
                       url(r'^input/', views.input_page),
                       url(r'', views.userinfo),
                       )