"""
URL configuration for notifications domain.
"""

from django.urls import path
from apps.core.notifications import views, api_views

app_name = 'notifications'

urlpatterns = [
    # Notification channels (web UI)
    path('', views.notification_list, name='notification_list'),
    path('create/', views.notification_create, name='notification_create'),
    path('<int:channel_id>/', views.notification_detail, name='notification_detail'),
    path('<int:channel_id>/toggle/', views.notification_toggle, name='notification_toggle'),
    path('<int:channel_id>/test/', views.notification_test, name='notification_test'),
    path('<int:channel_id>/delete/', views.notification_delete, name='notification_delete'),

    # In-app notifications API (for notification bell)
    path('api/notifications/', api_views.get_notifications, name='api_get_notifications'),
    path('api/notifications/unread-count/', api_views.get_unread_count, name='api_unread_count'),
    path('api/notifications/<int:notification_id>/', api_views.get_notification_detail, name='api_notification_detail'),
    path('api/notifications/<int:notification_id>/mark-read/', api_views.mark_as_read, name='api_mark_read'),
    path('api/notifications/<int:notification_id>/delete/', api_views.delete_notification, name='api_delete_notification'),
    path('api/notifications/mark-all-read/', api_views.mark_all_as_read, name='api_mark_all_read'),
    path('api/notifications/clear-all/', api_views.clear_all_notifications, name='api_clear_all'),
]