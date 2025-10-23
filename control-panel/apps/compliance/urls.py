from django.urls import path
from . import views

app_name = 'compliance'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Frameworks
    path('frameworks/', views.frameworks_list, name='frameworks_list'),
    path('frameworks/<int:framework_id>/', views.framework_detail, name='framework_detail'),
    
    # Controls
    path('controls/', views.controls_list, name='controls_list'),
    path('controls/<int:control_id>/', views.control_detail, name='control_detail'),
    
    # Security Scans
    path('scans/', views.security_scans, name='security_scans'),
    path('scans/<str:scan_id>/', views.scan_detail, name='scan_detail'),
    
    # Reports
    path('reports/', views.compliance_reports, name='compliance_reports'),
    path('reports/<str:report_id>/', views.report_detail, name='report_detail'),
    
    # Alerts
    path('alerts/', views.compliance_alerts, name='compliance_alerts'),
    path('alerts/<str:alert_id>/', views.alert_detail, name='alert_detail'),
    path('alerts/<str:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
    
    # API endpoints
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/scan-now/', views.api_scan_now, name='api_scan_now'),
    path('api/generate-report/', views.api_generate_report, name='api_generate_report'),
]