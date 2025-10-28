"""
Celery configuration for WebOps.

"Celery Tasks" section
Architecture: Background task processing for deployments

This module configures Celery for handling asynchronous tasks:
- Deployment operations
- Service management
- Database operations
- System monitoring
"""

import os
import sys
from celery import Celery
from celery.schedules import crontab
from decouple import config

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Add system-templates directory to Python path for template_registry
sys.path.insert(0, '/home/douglas/webops/system-templates')

# Create Celery application
app = Celery('webops')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {
    # =========================================================================
    # DEPLOYMENT HEALTH CHECKS
    # =========================================================================
    'run-health-checks-every-5-minutes': {
        'task': 'apps.deployments.tasks.run_all_health_checks',
        'schedule': 300.0,  # 5 minutes in seconds
        'kwargs': {'auto_restart': True}
    },

    'cleanup-health-records-daily': {
        'task': 'apps.deployments.tasks.cleanup_old_health_records',
        'schedule': crontab(hour=2, minute=0),
        'kwargs': {'days': 30}
    },

    # =========================================================================
    # SERVICE MONITORING (apps.services.tasks)
    # =========================================================================
    'collect-system-metrics-every-5-minutes': {
        'task': 'services.collect_system_metrics',
        'schedule': 300.0,  # 5 minutes
    },

    'check-service-statuses-every-2-minutes': {
        'task': 'services.check_all_service_statuses',
        'schedule': 120.0,  # 2 minutes
    },

    'perform-health-checks-every-5-minutes': {
        'task': 'services.perform_health_checks',
        'schedule': 300.0,  # 5 minutes
        'kwargs': {'auto_restart': True}
    },

    'auto-recover-failed-services-every-5-minutes': {
        'task': 'services.auto_recover_failed_services',
        'schedule': 300.0,  # 5 minutes
    },

    'check-celery-health-every-10-minutes': {
        'task': 'services.check_celery_health',
        'schedule': 600.0,  # 10 minutes
    },

    'check-system-services-every-10-minutes': {
        'task': 'services.check_system_services',
        'schedule': 600.0,  # 10 minutes
    },

    # =========================================================================
    # DATA CLEANUP
    # =========================================================================
    'cleanup-monitoring-data-daily': {
        'task': 'services.cleanup_old_monitoring_data',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
        'kwargs': {'days': 7}
    },

    # =========================================================================
    # REPORTING
    # =========================================================================
    'generate-daily-report': {
        'task': 'services.generate_daily_report',
        'schedule': crontab(hour=0, minute=5),  # 12:05 AM daily
    },
}

# Celery Beat Configuration
app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')