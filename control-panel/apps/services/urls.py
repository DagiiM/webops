"""
URL configuration for services app.

Reference: CLAUDE.md "URL Routing" section
"""

from django.urls import path
from . import views

urlpatterns = [
    # Main monitoring dashboard
    path('', views.monitoring_dashboard, name='monitoring_dashboard'),

    # Alerts
    path('alerts/', views.alerts_list, name='alerts_list'),
    path('alerts/<int:pk>/acknowledge/', views.alert_acknowledge, name='alert_acknowledge'),
    path('alerts/acknowledge-all/', views.alert_acknowledge_all, name='alert_acknowledge_all'),

    # Service status
    path('service/<int:deployment_id>/', views.service_status_detail, name='service_status_detail'),
    path('service/<int:deployment_id>/refresh/', views.refresh_service_status, name='refresh_service_status'),

    # API endpoints for real-time data
    path('api/metrics/current/', views.current_metrics_api, name='current_metrics_api'),
    path('api/metrics/history/', views.metrics_history, name='metrics_history'),
    path('api/system/summary/', views.system_summary_api, name='system_summary_api'),
    path('api/health-check/<int:deployment_id>/', views.health_check_history, name='health_check_history'),
]
