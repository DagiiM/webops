"""
Django signals for the compliance app.

This module defines signal handlers for compliance-related events.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import ComplianceAlert, ComplianceFramework, ComplianceControl

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ComplianceAlert)
def log_compliance_alert_created(sender, instance, created, **kwargs):
    """Log when a compliance alert is created."""
    if created:
        logger.warning(f"Compliance alert created: {instance.title} (Severity: {instance.severity})")


@receiver(post_save, sender=ComplianceFramework)
def log_framework_updated(sender, instance, created, **kwargs):
    """Log when a compliance framework is created or updated."""
    action = "created" if created else "updated"
    logger.info(f"Compliance framework {action}: {instance.name}")


@receiver(post_save, sender=ComplianceControl)
def log_control_updated(sender, instance, created, **kwargs):
    """Log when a compliance control is created or updated."""
    action = "created" if created else "updated"
    logger.info(f"Compliance control {action}: {instance.control_id} - {instance.name}")


def create_compliance_alert(title, description, severity='medium', framework=None, control=None):
    """
    Utility function to create a compliance alert.
    
    Args:
        title (str): Alert title
        description (str): Alert description
        severity (str): Alert severity ('low', 'medium', 'high', 'critical')
        framework (ComplianceFramework, optional): Related framework
        control (ComplianceControl, optional): Related control
    """
    try:
        alert = ComplianceAlert.objects.create(
            title=title,
            description=description,
            severity=severity,
            framework=framework,
            control=control
        )
        logger.info(f"Compliance alert created: {title}")
        return alert
    except Exception as e:
        logger.error(f"Failed to create compliance alert: {e}")
        return None