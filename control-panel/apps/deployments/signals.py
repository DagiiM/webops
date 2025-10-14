"""
Django signals for real-time deployment updates via WebSocket.

This module handles broadcasting deployment status changes to connected
WebSocket clients for real-time updates in the CLI and web interface.
"""

from typing import Any, Dict, Optional
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

from .models import Deployment, DeploymentLog, HealthCheckRecord


def broadcast_to_websocket(group_name: str, message: Dict[str, Any]) -> None:
    """
    Broadcast a message to a WebSocket group.
    
    Args:
        group_name: The WebSocket group name to broadcast to
        message: The message data to send
    """
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'deployment_update',
                'message': message
            }
        )


@receiver(post_save, sender=Deployment)
def deployment_status_changed(sender: type, instance: Deployment, created: bool, **kwargs: Any) -> None:
    """
    Signal handler for deployment status changes.
    
    Broadcasts deployment updates to WebSocket clients when:
    - A new deployment is created
    - An existing deployment's status changes
    
    Args:
        sender: The model class that sent the signal
        instance: The deployment instance that was saved
        created: Whether this is a new deployment
        **kwargs: Additional signal arguments
    """
    message = {
        'type': 'deployment_created' if created else 'deployment_updated',
        'deployment': {
            'id': instance.id,
            'name': instance.name,
            'status': instance.status,
            'project_type': instance.project_type,
            'repo_url': instance.repo_url,
            'branch': instance.branch,
            'domain': instance.domain,
            'port': instance.port,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        },
        'timestamp': instance.updated_at.isoformat() if instance.updated_at else None
    }
    
    # Broadcast to all deployments group
    broadcast_to_websocket('deployments', message)
    
    # Broadcast to specific deployment group
    broadcast_to_websocket(f'deployment_{instance.name}', message)


@receiver(post_delete, sender=Deployment)
def deployment_deleted(sender: type, instance: Deployment, **kwargs: Any) -> None:
    """
    Signal handler for deployment deletion.
    
    Broadcasts deletion events to WebSocket clients.
    
    Args:
        sender: The model class that sent the signal
        instance: The deployment instance that was deleted
        **kwargs: Additional signal arguments
    """
    message = {
        'type': 'deployment_deleted',
        'deployment': {
            'id': instance.id,
            'name': instance.name,
        },
        'timestamp': None  # No timestamp available for deleted objects
    }
    
    # Broadcast to all deployments group
    broadcast_to_websocket('deployments', message)
    
    # Broadcast to specific deployment group
    broadcast_to_websocket(f'deployment_{instance.name}', message)


@receiver(post_save, sender=DeploymentLog)
def deployment_log_created(sender: type, instance: DeploymentLog, created: bool, **kwargs: Any) -> None:
    """
    Signal handler for new deployment logs.
    
    Broadcasts log entries to WebSocket clients for real-time log streaming.
    
    Args:
        sender: The model class that sent the signal
        instance: The log instance that was saved
        created: Whether this is a new log entry
        **kwargs: Additional signal arguments
    """
    if not created:
        return  # Only broadcast new log entries
    
    message = {
        'type': 'log_entry',
        'deployment_name': instance.deployment.name,
        'log': {
            'id': instance.id,
            'level': instance.level,
            'message': instance.message,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        },
        'timestamp': instance.created_at.isoformat() if instance.created_at else None
    }
    
    # Broadcast to all deployments group
    broadcast_to_websocket('deployments', message)
    
    # Broadcast to specific deployment group
    broadcast_to_websocket(f'deployment_{instance.deployment.name}', message)


@receiver(post_save, sender=HealthCheckRecord)
def health_check_completed(sender: type, instance: HealthCheckRecord, created: bool, **kwargs: Any) -> None:
    """
    Signal handler for health check results.
    
    Broadcasts health check results to WebSocket clients for real-time monitoring.
    
    Args:
        sender: The model class that sent the signal
        instance: The health check record that was saved
        created: Whether this is a new health check record
        **kwargs: Additional signal arguments
    """
    if not created:
        return  # Only broadcast new health check records
    
    message = {
        'type': 'health_check',
        'deployment_name': instance.deployment.name,
        'health_check': {
            'id': instance.id,
            'overall_healthy': instance.overall_healthy,
            'process_healthy': instance.process_healthy,
            'http_healthy': instance.http_healthy,
            'resources_healthy': instance.resources_healthy,
            'disk_healthy': instance.disk_healthy,
            'cpu_percent': instance.cpu_percent,
            'memory_mb': instance.memory_mb,
            'disk_free_gb': instance.disk_free_gb,
            'response_time_ms': instance.response_time_ms,
            'http_status_code': instance.http_status_code,
            'auto_restart_attempted': instance.auto_restart_attempted,
            'auto_restart_successful': instance.auto_restart_successful,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        },
        'timestamp': instance.created_at.isoformat() if instance.created_at else None
    }
    
    # Broadcast to all deployments group
    broadcast_to_websocket('deployments', message)
    
    # Broadcast to specific deployment group
    broadcast_to_websocket(f'deployment_{instance.deployment.name}', message)