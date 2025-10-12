"""
Celery configuration for WebOps.

Reference: CLAUDE.md "Celery Tasks" section
Architecture: Background task processing for deployments

This module configures Celery for handling asynchronous tasks:
- Deployment operations
- Service management
- Database operations
- System monitoring
"""

import os
from celery import Celery
from celery.schedules import crontab
from decouple import config

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create Celery application
app = Celery('webops')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {
    # Health checks every 5 minutes
    'run-health-checks-every-5-minutes': {
        'task': 'apps.deployments.tasks.run_all_health_checks',
        'schedule': 300.0,  # 5 minutes in seconds
        'kwargs': {'auto_restart': True}
    },

    # Cleanup old health records daily at 2 AM
    'cleanup-health-records-daily': {
        'task': 'apps.deployments.tasks.cleanup_old_health_records',
        'schedule': crontab(hour=2, minute=0),
        'kwargs': {'days': 30}
    },
}

# Celery Beat Configuration
app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')