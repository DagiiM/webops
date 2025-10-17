"""
Service Control Views for admin interface and API.

Reference: CLAUDE.md "Services Control System"
Architecture: RESTful API and web interface for service management

This module provides:
- Service start/stop/restart endpoints
- Bulk service operations
- Configuration management UI
- Restart policy management
- Real-time service status
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages

from apps.deployments.models import Deployment
from .service_controller import service_controller
from .restart_policy import RestartPolicy, restart_policy_enforcer
from .config_manager import config_manager
from .tasks import (
    start_service_task,
    stop_service_task,
    restart_service_task
)


# =============================================================================
# SERVICE CONTROL VIEWS
# =============================================================================

@login_required
def service_control_dashboard(request):
    """Main service control dashboard."""
    # Get all deployments with status
    deployments = Deployment.objects.all()
    service_statuses = []

    for deployment in deployments:
        status = service_controller.get_service_status(deployment)

        # Get restart policy
        try:
            policy = RestartPolicy.objects.get(deployment=deployment)
        except RestartPolicy.DoesNotExist:
            policy = None

        service_statuses.append({
            'deployment': deployment,
            'status': status,
            'policy': policy
        })

    # System health
    system_health = service_controller.check_system_health()

    # Celery status
    celery_status = service_controller.check_celery_workers()

    context = {
        'service_statuses': service_statuses,
        'system_health': system_health,
        'celery_status': celery_status,
    }

    return render(request, 'services/control_dashboard.html', context)


@login_required
@require_POST
def start_service(request, deployment_id):
    """Start a specific service."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    # Check if background task requested
    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        # Queue background task
        task = start_service_task.delay(deployment_id)
        result = {
            'success': True,
            'message': f'Start task queued for {deployment.name}',
            'task_id': task.id
        }
    else:
        # Synchronous start
        result = service_controller.start_service(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('service_control_dashboard')


@login_required
@require_POST
def stop_service(request, deployment_id):
    """Stop a specific service."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        task = stop_service_task.delay(deployment_id)
        result = {
            'success': True,
            'message': f'Stop task queued for {deployment.name}',
            'task_id': task.id
        }
    else:
        result = service_controller.stop_service(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('service_control_dashboard')


@login_required
@require_POST
def restart_service(request, deployment_id):
    """Restart a specific service."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        task = restart_service_task.delay(deployment_id)
        result = {
            'success': True,
            'message': f'Restart task queued for {deployment.name}',
            'task_id': task.id
        }
    else:
        result = service_controller.restart_service(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('service_control_dashboard')


@login_required
@require_POST
def bulk_start_services(request):
    """Start all stopped services."""
    result = service_controller.start_all_services()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    messages.success(
        request,
        f"Started {result['started']} services ({result['failed']} failed)"
    )

    return redirect('service_control_dashboard')


@login_required
@require_POST
def bulk_stop_services(request):
    """Stop all running services."""
    result = service_controller.stop_all_services()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    messages.success(
        request,
        f"Stopped {result['stopped']} services ({result['failed']} failed)"
    )

    return redirect('service_control_dashboard')


@login_required
@require_POST
def bulk_restart_services(request):
    """Restart all running services."""
    result = service_controller.restart_all_services()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    messages.success(
        request,
        f"Restarted {result['restarted']} services ({result['failed']} failed)"
    )

    return redirect('service_control_dashboard')


# =============================================================================
# RESTART POLICY VIEWS
# =============================================================================

@login_required
def restart_policy_list(request):
    """List all restart policies."""
    policies = RestartPolicy.objects.select_related('deployment').all()

    # Get statistics for each
    policy_stats = []
    for policy in policies:
        stats = restart_policy_enforcer.get_restart_statistics(
            policy.deployment,
            hours=24
        )
        policy_stats.append({
            'policy': policy,
            'stats': stats
        })

    context = {
        'policy_stats': policy_stats,
    }

    return render(request, 'services/restart_policy_list.html', context)


@login_required
def restart_policy_edit(request, deployment_id):
    """Edit restart policy for a deployment."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    try:
        policy = RestartPolicy.objects.get(deployment=deployment)
    except RestartPolicy.DoesNotExist:
        policy = None

    if request.method == 'POST':
        # Create or update policy
        policy_data = {
            'policy_type': request.POST.get('policy_type'),
            'enabled': request.POST.get('enabled') == 'on',
            'max_restarts': int(request.POST.get('max_restarts', 3)),
            'time_window_minutes': int(request.POST.get('time_window_minutes', 15)),
            'initial_delay_seconds': int(request.POST.get('initial_delay_seconds', 10)),
            'max_delay_seconds': int(request.POST.get('max_delay_seconds', 300)),
            'backoff_multiplier': float(request.POST.get('backoff_multiplier', 2.0)),
            'cooldown_minutes': int(request.POST.get('cooldown_minutes', 5)),
            'require_health_check': request.POST.get('require_health_check') == 'on',
            'health_check_retries': int(request.POST.get('health_check_retries', 3)),
            'notify_on_restart': request.POST.get('notify_on_restart') == 'on',
            'notify_on_max_restarts': request.POST.get('notify_on_max_restarts') == 'on',
        }

        if policy:
            # Update existing
            for key, value in policy_data.items():
                setattr(policy, key, value)
            policy.save()
            messages.success(request, f'Restart policy updated for {deployment.name}')
        else:
            # Create new
            policy = RestartPolicy.objects.create(
                deployment=deployment,
                **policy_data
            )
            messages.success(request, f'Restart policy created for {deployment.name}')

        return redirect('restart_policy_list')

    context = {
        'deployment': deployment,
        'policy': policy,
        'policy_types': RestartPolicy.PolicyType.choices,
    }

    return render(request, 'services/restart_policy_edit.html', context)


@login_required
@require_POST
def restart_policy_delete(request, deployment_id):
    """Delete restart policy."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    try:
        policy = RestartPolicy.objects.get(deployment=deployment)
        policy.delete()
        messages.success(request, f'Restart policy deleted for {deployment.name}')
    except RestartPolicy.DoesNotExist:
        messages.error(request, 'Restart policy not found')

    return redirect('restart_policy_list')


# =============================================================================
# CONFIGURATION MANAGEMENT VIEWS
# =============================================================================

@login_required
def configuration_list(request):
    """List and edit configuration settings."""
    # Get all configuration by category
    categories = {}

    for key in config_manager.CONFIG_SCHEMA.keys():
        category = key.split('.')[0]
        if category not in categories:
            categories[category] = {}
        categories[category][key] = {
            'value': config_manager.get(key),
            'schema': config_manager.CONFIG_SCHEMA[key]
        }

    # Validate all configurations
    validation_errors = config_manager.validate_all()

    context = {
        'categories': categories,
        'validation_errors': validation_errors,
    }

    return render(request, 'services/configuration_list.html', context)


@login_required
@require_POST
def configuration_update(request):
    """Update configuration value."""
    key = request.POST.get('key')
    value = request.POST.get('value')

    if not key:
        return JsonResponse({
            'success': False,
            'error': 'Key is required'
        }, status=400)

    # Get schema for type conversion
    schema = config_manager.CONFIG_SCHEMA.get(key)
    if schema:
        try:
            # Convert to correct type
            if schema['type'] == bool:
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif schema['type'] == int:
                value = int(value)
            elif schema['type'] == float:
                value = float(value)
        except (ValueError, AttributeError) as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid value: {e}'
            }, status=400)

    success = config_manager.set(key, value)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': success,
            'key': key,
            'value': config_manager.get(key)
        })

    if success:
        messages.success(request, f'Configuration updated: {key}')
    else:
        messages.error(request, f'Failed to update configuration: {key}')

    return redirect('configuration_list')


@login_required
@require_POST
def configuration_reset(request, key):
    """Reset configuration to default value."""
    success = config_manager.reset_to_default(key)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': success,
            'key': key,
            'value': config_manager.get(key)
        })

    if success:
        messages.success(request, f'Configuration reset to default: {key}')
    else:
        messages.error(request, f'Failed to reset configuration: {key}')

    return redirect('configuration_list')


# =============================================================================
# CELERY MANAGEMENT VIEWS
# =============================================================================

@login_required
def celery_status(request):
    """Celery workers status and management."""
    worker_status = service_controller.check_celery_workers()

    context = {
        'worker_status': worker_status,
    }

    return render(request, 'services/celery_status.html', context)


@login_required
@require_POST
def celery_restart_workers(request):
    """Restart Celery workers."""
    result = service_controller.restart_celery_workers()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('celery_status')


# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
@require_http_methods(["GET"])
def api_service_status(request, deployment_id):
    """API: Get service status."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    status = service_controller.get_service_status(deployment)
    return JsonResponse(status)


@login_required
@require_http_methods(["GET"])
def api_system_health(request):
    """API: Get complete system health."""
    health = service_controller.check_system_health()
    return JsonResponse(health)


@login_required
@require_http_methods(["GET"])
def api_celery_status(request):
    """API: Get Celery worker status."""
    status = service_controller.check_celery_workers()
    return JsonResponse(status)


@login_required
@require_http_methods(["GET"])
def api_configuration(request):
    """API: Get all configuration."""
    config = config_manager.get_all()
    return JsonResponse({'config': config})


@login_required
@require_http_methods(["GET"])
def api_celery_inspect(request):
    """API: Inspect Celery worker details."""
    worker_name = request.GET.get('worker')

    # Get worker details from Celery
    from celery import current_app
    inspect = current_app.control.inspect()

    result = {
        'worker': worker_name,
        'active': 0,
        'scheduled': 0,
        'reserved': 0,
        'config': {}
    }

    if worker_name:
        # Get active tasks
        active_tasks = inspect.active()
        if active_tasks and worker_name in active_tasks:
            result['active'] = len(active_tasks[worker_name])

        # Get scheduled tasks
        scheduled_tasks = inspect.scheduled()
        if scheduled_tasks and worker_name in scheduled_tasks:
            result['scheduled'] = len(scheduled_tasks[worker_name])

        # Get reserved tasks
        reserved_tasks = inspect.reserved()
        if reserved_tasks and worker_name in reserved_tasks:
            result['reserved'] = len(reserved_tasks[worker_name])

        # Get worker config
        stats = inspect.stats()
        if stats and worker_name in stats:
            result['config'] = stats[worker_name]

    return JsonResponse(result)
