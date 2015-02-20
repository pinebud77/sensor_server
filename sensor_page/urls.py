from django.conf.urls import patterns, url
from sensor_page import views

urlpatterns = patterns('',
                       url(r'^login/', views.login_page),
                       url(r'^userinfo/', views.sensor_list),
                       url(r'^admin/', views.admin_page),
                       url(r'^applogin/', views.app_login_page),
                       url(r'^appregister/', views.app_register_page),
                       url(r'^appphone/', views.app_phone_page),
                       url(r'^appnode/', views.app_node_page),
                       url(r'^logout/', views.logout_page),
                       url(r'^cronjob/', views.cron_job),
                       url(r'^sensornode/(?P<sensor_node_id>\w+)/(?P<display_fmt>\w+)/(?P<time_offset>\w+)/', views.sensor_node_page),
                       url(r'^sensornode/(?P<sensor_node_id>\w+)/(?P<display_fmt>\w+)/', views.sensor_node_page),
                       url(r'^sensornode/(?P<sensor_node_id>\w+)/', views.sensor_node_page),
                       url(r'^input/', views.input_page),
                       url(r'^/', views.index_page),
                       url(r'', views.index_page),
                       )