"""
Celery Beat schedule for automation app.

This module defines the periodic tasks for scheduled workflow execution.
"""

from celery.schedules import crontab

# Define the beat schedule
beat_schedule = {
    # Execute scheduled workflows every minute
    'execute-scheduled-workflows': {
        'task': 'apps.automation.tasks.execute_scheduled_workflows',
        'schedule': crontab(minute='*'),  # Run every minute
        'options': {
            'queue': 'automation',
        }
    },
    
    # Clean up old execution logs daily at 2 AM
    'cleanup-old-executions': {
        'task': 'apps.automation.tasks.cleanup_old_executions',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
        'options': {
            'queue': 'automation',
        }
    },
    
    # Validate workflows weekly on Sunday at 3 AM
    'validate-workflows': {
        'task': 'apps.automation.tasks.validate_all_workflows',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Run weekly on Sunday at 3 AM
        'options': {
            'queue': 'automation',
        }
    },
}