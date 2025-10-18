from django.urls import path
from . import views

app_name = 'addons'

urlpatterns = [
    path('', views.addons_list, name='addons_list'),
    path('<str:addon_name>/', views.addon_detail, name='addon_detail'),
    path('<str:addon_name>/toggle/', views.addon_toggle, name='addon_toggle'),
    path('<str:addon_name>/enable/', views.addon_enable, name='addon_enable'),
    path('<str:addon_name>/disable/', views.addon_disable, name='addon_disable'),
    path('<str:addon_name>/toggle-ajax/', views.addon_toggle_ajax, name='addon_toggle_ajax'),
]