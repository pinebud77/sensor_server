from django.conf.urls import patterns, url
from sensor_page import views

urlpatterns = patterns('',
                       url(r'^login/', views.login_page),
                       url(r'^test_page_9927/', views.test_page),
                       url(r'^logout/', views.logout_page),
                       url(r'^cronjob/', views.cron_job),
                       url(r'^userinfo/(?P<display_fmt>\w+)/(?P<time_offset>\w+)/', views.user_info),
                       url(r'^userinfo/(?P<display_fmt>\w+)/', views.user_info),
                       url(r'^userinfo/', views.user_info),
                       url(r'^input/', views.input_page),
                       url(r'', views.user_info),
                       )