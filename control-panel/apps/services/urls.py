"""
URL configuration for services app.

Reference: CLAUDE.md "URL Routing" section
"""

from django.urls import path
from . import views
from . import control_views

urlpatterns = [
    # =========================================================================
    # MONITORING DASHBOARD
    # =========================================================================
    path('', views.monitoring_dashboard, name='monitoring_dashboard'),

    # =========================================================================
    # SERVICE CONTROL
    # =========================================================================
    path('control/', control_views.service_control_dashboard, name='service_control_dashboard'),
    path('control/<int:deployment_id>/start/', control_views.start_service, name='start_service'),
    path('control/<int:deployment_id>/stop/', control_views.stop_service, name='stop_service'),
    path('control/<int:deployment_id>/restart/', control_views.restart_service, name='restart_service'),

    # Bulk operations
    path('control/bulk/start/', control_views.bulk_start_services, name='bulk_start_services'),
    path('control/bulk/stop/', control_views.bulk_stop_services, name='bulk_stop_services'),
    path('control/bulk/restart/', control_views.bulk_restart_services, name='bulk_restart_services'),

    # =========================================================================
    # RESTART POLICIES
    # =========================================================================
    path('restart-policies/', control_views.restart_policy_list, name='restart_policy_list'),
    path('restart-policies/<int:deployment_id>/edit/', control_views.restart_policy_edit, name='restart_policy_edit'),
    path('restart-policies/<int:deployment_id>/delete/', control_views.restart_policy_delete, name='restart_policy_delete'),

    # =========================================================================
    # CONFIGURATION MANAGEMENT
    # =========================================================================
    path('configuration/', control_views.configuration_list, name='configuration_list'),
    path('configuration/update/', control_views.configuration_update, name='configuration_update'),
    path('configuration/<str:key>/reset/', control_views.configuration_reset, name='configuration_reset'),
    path('configuration/reset-all/', control_views.configuration_reset_all, name='configuration_reset_all'),

    # =========================================================================
    # CELERY MANAGEMENT
    # =========================================================================
    path('celery/', control_views.celery_status, name='celery_status'),
    path('celery/restart/', control_views.celery_restart_workers, name='celery_restart_workers'),

    # =========================================================================
    # ALERTS
    # =========================================================================
    path('alerts/', views.alerts_list, name='alerts_list'),
    path('alerts/<int:pk>/acknowledge/', views.alert_acknowledge, name='alert_acknowledge'),
    path('alerts/acknowledge-all/', views.alert_acknowledge_all, name='alert_acknowledge_all'),

    # =========================================================================
    # SERVICE STATUS
    # =========================================================================
    path('service/<int:deployment_id>/', views.service_status_detail, name='service_status_detail'),
    path('service/<int:deployment_id>/refresh/', views.refresh_service_status, name='refresh_service_status'),

    # =========================================================================
    # API ENDPOINTS (Real-time data)
    # =========================================================================
    path('api/metrics/current/', views.current_metrics_api, name='current_metrics_api'),
    path('api/metrics/history/', views.metrics_history, name='metrics_history'),
    path('api/system/summary/', views.system_summary_api, name='system_summary_api'),
    path('api/health-check/<int:deployment_id>/', views.health_check_history, name='health_check_history'),

    # Service control API
    path('api/service/<int:deployment_id>/status/', control_views.api_service_status, name='api_service_status'),
    path('api/system/health/', control_views.api_system_health, name='api_system_health'),
    path('api/celery/status/', control_views.api_celery_status, name='api_celery_status'),
    path('api/celery/inspect/', control_views.api_celery_inspect, name='api_celery_inspect'),
    path('api/configuration/', control_views.api_configuration, name='api_configuration'),
]
