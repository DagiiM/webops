"""
URL configuration for notifications domain.
"""

from django.urls import path
from apps.core.notifications import views

app_name = 'notifications'

urlpatterns = [
    # Notification channels
    path('', views.notification_list, name='notification_list'),
    path('create/', views.notification_create, name='notification_create'),
    path('<int:channel_id>/', views.notification_detail, name='notification_detail'),
    path('<int:channel_id>/toggle/', views.notification_toggle, name='notification_toggle'),
    path('<int:channel_id>/test/', views.notification_test, name='notification_test'),
    path('<int:channel_id>/delete/', views.notification_delete, name='notification_delete'),
]