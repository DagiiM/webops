"""
Service Control Views for admin interface and API.

"Services Control System"
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
from django.utils import timezone

from apps.deployments.models import BaseDeployment, ApplicationDeployment
from .service_controller import service_controller
from .restart_policy import RestartPolicy, restart_policy_enforcer
from .config_manager import config_manager
from .tasks import (
    start_service_task,
    stop_service_task,
    restart_service_task
)
from .background import get_background_processor
from apps.core.security.decorators import require_resource_ownership


# =============================================================================
# SERVICE CONTROL VIEWS
# =============================================================================

@login_required
def service_control_dashboard(request):
    """Main service control dashboard."""
    # Get all deployments with status
    # SECURITY FIX: Filter by user to prevent IDOR vulnerability
    deployments = ApplicationDeployment.objects.filter(deployed_by=request.user)
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
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def start_service(request, deployment_id):
    """Start a specific service."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)

    # Check if background task requested
    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        # Queue background task via adapter (backward-compatible with Celery)
        processor = get_background_processor()
        handle = processor.submit('services.start_service_task', deployment_id)
        result = {
            'success': True,
            'message': f'Start task queued for {deployment.name}',
            'task_id': handle.id
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

    return redirect('monitoring:service_control_dashboard')


# =============================================================================
# BACKGROUND PROCESSOR MANAGEMENT VIEWS
# =============================================================================

@login_required
def background_management(request):
    """Processor-agnostic background management view."""
    from .background import get_background_processor
    processor = get_background_processor()
    
    try:
        # Get processor status
        status = processor.get_status()
        
        # Get queue statistics if available
        queue_stats = {}
        if hasattr(processor, 'get_queue_stats'):
            queue_stats = processor.get_queue_stats()
        
        # Determine backend type for template rendering
        backend_name = processor.__class__.__name__.lower()
        if 'celery' in backend_name:
            backend_type = 'celery'
        elif 'memory' in backend_name:
            backend_type = 'memory'
        else:
            backend_type = 'unknown'
        
        context = {
            'processor_status': status,
            'queue_stats': queue_stats,
            'backend_type': backend_type,
        }
        
        return render(request, 'services/background_management.html', context)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting background processor status: {e}")
        from django.contrib import messages
        messages.error(request, f"Error getting background processor status: {e}")
        return redirect('monitoring:service_control_dashboard')


@login_required
@require_POST
def background_restart(request):
    """Restart the active background-processor workers."""
    from .background import get_background_processor
    processor = get_background_processor()
    # Delegate to service_controller for actual restart logic
    result = service_controller.restart_background_workers(processor)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('monitoring:background_management')


# =============================================================================
# LEGACY REDIRECTS
# =============================================================================

@login_required
def celery_status_redirect(request):
    """Redirect old /celery/ URLs to new /background/ page."""
    messages.info(request, 'Celery management has moved to Background Processes.')
    return redirect('monitoring:background_management')


@login_required
def celery_restart_redirect(request):
    """Redirect old /celery/restart/ to new /background/restart/."""
    messages.info(request, 'Celery restart has moved to Background Processes.')
    return redirect('monitoring:background_restart')

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('monitoring:service_control_dashboard')


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def stop_service(request, deployment_id):
    """Stop a specific service."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)

    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        processor = get_background_processor()
        handle = processor.submit('services.stop_service_task', deployment_id)
        result = {
            'success': True,
            'message': f'Stop task queued for {deployment.name}',
            'task_id': handle.id
        }
    else:
        result = service_controller.stop_service(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('monitoring:service_control_dashboard')


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def restart_service(request, deployment_id):
    """Restart a specific service."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)

    use_task = request.POST.get('background', 'false') == 'true'

    if use_task:
        processor = get_background_processor()
        handle = processor.submit('services.restart_service_task', deployment_id)
        result = {
            'success': True,
            'message': f'Restart task queued for {deployment.name}',
            'task_id': handle.id
        }
    else:
        result = service_controller.restart_service(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)

    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])

    return redirect('monitoring:service_control_dashboard')


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

    return redirect('monitoring:service_control_dashboard')


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

    return redirect('monitoring:service_control_dashboard')


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
    return redirect('monitoring:service_control_dashboard')


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
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def restart_policy_edit(request, deployment_id):
    """Edit restart policy for a deployment."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)

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

        return redirect('monitoring:restart_policy_list')

    context = {
        'deployment': deployment,
        'policy': policy,
        'policy_types': RestartPolicy.PolicyType.choices,
    }

    return render(request, 'services/restart_policy_edit.html', context)


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def restart_policy_delete(request, deployment_id):
    """Delete restart policy."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)

    try:
        policy = RestartPolicy.objects.get(deployment=deployment)
        policy.delete()
        messages.success(request, f'Restart policy deleted for {deployment.name}')
    except RestartPolicy.DoesNotExist:
        messages.error(request, 'Restart policy not found')

    return redirect('monitoring:restart_policy_list')


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
    """Update configuration values."""
    # Handle single key update (for AJAX requests)
    if 'key' in request.POST and 'value' in request.POST:
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

        return redirect('monitoring:configuration_list')

    # Handle multiple key updates (for form submissions)
    updated_count = 0
    errors = []
    
    # Get all configuration keys from the schema
    for key in config_manager.CONFIG_SCHEMA.keys():
        if key in request.POST:
            value = request.POST.get(key)
            
            # Skip empty values
            if value == '':
                continue
                
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
                    errors.append(f'Invalid value for {key}: {e}')
                    continue

            success = config_manager.set(key, value)
            if success:
                updated_count += 1
            else:
                errors.append(f'Failed to update {key}')

    # Provide feedback
    if updated_count > 0:
        messages.success(request, f'Updated {updated_count} configuration(s)')
    
    if errors:
        for error in errors:
            messages.error(request, error)

    return redirect('monitoring:configuration_list')


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

    return redirect('monitoring:configuration_list')


@login_required
@require_POST
def configuration_reset_all(request):
    """Reset all configurations to default values."""
    count = config_manager.reset_all_to_defaults()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'count': count,
            'message': f'Reset {count} configurations to defaults'
        })

    messages.success(request, f'Reset {count} configurations to defaults')
    return redirect('monitoring:configuration_list')


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

    return redirect('monitoring:celery_status')


# =============================================================================
# API ENDPOINTS
# =============================================================================

@login_required
@require_http_methods(["GET"])
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def api_service_status(request, deployment_id):
    """API: Get service status."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
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


# =============================================================================
# BACKGROUND PROCESSOR MANAGEMENT VIEWS
# =============================================================================

@login_required
def background_management(request):
    """Generic background processor management page."""
    from apps.services.background import get_background_processor
    
    try:
        processor = get_background_processor()
        processor_status = processor.get_status()
        backend_type = processor_status.get('processor', 'unknown')
        
        # Get worker status based on processor type
        if backend_type == 'celery':
            worker_status = service_controller.check_celery_workers()
        else:
            # For in-memory processor, create mock worker status
            worker_status = {
                'status': 'healthy',
                'workers': [{
                    'name': 'in-memory-worker',
                    'status': 'online',
                    'active': processor_status.get('running_tasks', 0),
                    'scheduled': processor_status.get('pending_tasks', 0),
                }]
            }
        
        context = {
            'backend_type': backend_type,
            'processor_status': processor_status,
            'worker_status': worker_status,
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting background processor status: {e}")
        context = {
            'backend_type': 'error',
            'processor_status': {'status': 'error', 'error': str(e)},
            'worker_status': {'status': 'error', 'workers': []},
        }
    
    return render(request, 'services/background_management.html', context)


@login_required
@require_POST
def background_restart_workers(request):
    """Restart background processor workers."""
    result = service_controller.restart_background_workers()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(result)
    
    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['message'])
    
    return redirect('monitoring:background_management')


# =============================================================================
# LEGACY REDIRECTS (FOR BACKWARD COMPATIBILITY)
# =============================================================================

@login_required
def celery_status_redirect(request):
    """Redirect old Celery status URL to new background management page."""
    return redirect('monitoring:background_management')


@login_required
def celery_restart_redirect(request):
    """Redirect old Celery restart URL to new background restart endpoint."""
    return background_restart_workers(request)


# =============================================================================
# SSL CONFIGURATION MANAGEMENT VIEWS
# =============================================================================

@login_required
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_configuration(request, deployment_id):
    """SSL configuration management page."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    # Get or create SSL configuration
    from .models import SSLConfiguration
    ssl_config, created = SSLConfiguration.objects.get_or_create(
        deployment=deployment,
        defaults={'ssl_enabled': False}
    )
    
    context = {
        'deployment': deployment,
        'ssl_config': ssl_config,
        'days_until_expiry': ssl_config.get_days_until_expiry() if ssl_config.certificate_expires_at else None,
    }
    
    return render(request, 'services/ssl_configuration.html', context)


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_toggle(request, deployment_id):
    """Toggle SSL enable/disable for a deployment."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    from .models import SSLConfiguration
    ssl_config, created = SSLConfiguration.objects.get_or_create(
        deployment=deployment,
        defaults={'ssl_enabled': False}
    )
    
    # Toggle SSL status
    ssl_config.ssl_enabled = not ssl_config.ssl_enabled
    
    if ssl_config.ssl_enabled:
        # Validate certificate before enabling
        if not ssl_config.certificate_file:
            return JsonResponse({
                'success': False,
                'message': 'Cannot enable SSL: No certificate file uploaded'
            })
        
        if not ssl_config.private_key_file:
            return JsonResponse({
                'success': False,
                'message': 'Cannot enable SSL: No private key file uploaded'
            })
        
        # Validate certificate
        validation_result = service_controller.validate_ssl_certificate(ssl_config)
        if not validation_result['valid']:
            return JsonResponse({
                'success': False,
                'message': f"Cannot enable SSL: {validation_result['error']}"
            })
        
        ssl_config.status = ssl_config.SSLStatus.ENABLED
        ssl_config.validation_error = ''
    else:
        ssl_config.status = ssl_config.SSLStatus.DISABLED
    
    ssl_config.save()
    
    # Apply SSL configuration to service
    result = service_controller.apply_ssl_configuration(deployment, ssl_config)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': f"SSL {'enabled' if ssl_config.ssl_enabled else 'disabled'} successfully",
                'ssl_enabled': ssl_config.ssl_enabled,
                'status': ssl_config.status
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result['message']
            })
    
    if result['success']:
        messages.success(request, f"SSL {'enabled' if ssl_config.ssl_enabled else 'disabled'} successfully")
    else:
        messages.error(request, result['message'])
    
    return redirect('monitoring:ssl_configuration', deployment_id)


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_upload_certificate(request, deployment_id):
    """Upload SSL certificate files."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    from .models import SSLConfiguration
    ssl_config, created = SSLConfiguration.objects.get_or_create(
        deployment=deployment,
        defaults={'ssl_enabled': False}
    )
    
    try:
        # Handle certificate file upload
        if 'certificate_file' in request.FILES:
            ssl_config.certificate_file = request.FILES['certificate_file']
        
        # Handle private key file upload
        if 'private_key_file' in request.FILES:
            ssl_config.private_key_file = request.FILES['private_key_file']
        
        # Handle certificate chain file upload
        if 'certificate_chain_file' in request.FILES:
            ssl_config.certificate_chain_file = request.FILES['certificate_chain_file']
        
        # Validate uploaded certificate
        validation_result = service_controller.validate_ssl_certificate(ssl_config)
        
        if validation_result['valid']:
            ssl_config.status = ssl_config.SSLStatus.ENABLED if ssl_config.ssl_enabled else ssl_config.SSLStatus.DISABLED
            ssl_config.validation_error = ''
            
            # Extract certificate information
            if 'certificate_info' in validation_result:
                info = validation_result['certificate_info']
                ssl_config.certificate_expires_at = info.get('expires_at')
                ssl_config.certificate_issuer = info.get('issuer', '')
                ssl_config.certificate_subject = info.get('subject', '')
                ssl_config.domain = info.get('domain', '')
        else:
            ssl_config.status = ssl_config.SSLStatus.INVALID
            ssl_config.validation_error = validation_result['error']
        
        ssl_config.last_validation_at = timezone.now()
        ssl_config.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(validation_result)
        
        if validation_result['valid']:
            messages.success(request, 'Certificate uploaded and validated successfully')
        else:
            messages.error(request, f"Certificate validation failed: {validation_result['error']}")
        
    except Exception as e:
        error_msg = f"Error uploading certificate: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    
    return redirect('monitoring:ssl_configuration', deployment_id)


@login_required
@require_POST
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_update_configuration(request, deployment_id):
    """Update SSL configuration settings."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    from .models import SSLConfiguration
    ssl_config, created = SSLConfiguration.objects.get_or_create(
        deployment=deployment,
        defaults={'ssl_enabled': False}
    )
    
    try:
        # Update configuration fields
        ssl_config.encryption_protocol = request.POST.get('encryption_protocol', 'TLSv1.3')
        ssl_config.cipher_suite = request.POST.get('cipher_suite', 'ECDHE-RSA-AES256-GCM-SHA384')
        ssl_config.hsts_enabled = request.POST.get('hsts_enabled') == 'on'
        ssl_config.hsts_max_age = int(request.POST.get('hsts_max_age', 31536000))
        ssl_config.auto_redirect_http = request.POST.get('auto_redirect_http') == 'on'
        ssl_config.certificate_type = request.POST.get('certificate_type', 'self_signed')
        ssl_config.lets_encrypt_email = request.POST.get('lets_encrypt_email', '')
        ssl_config.auto_renew = request.POST.get('auto_renew') == 'on'
        ssl_config.renewal_days_before = int(request.POST.get('renewal_days_before', 30))
        ssl_config.domain = request.POST.get('domain', '')
        
        ssl_config.save()
        
        # Apply updated configuration
        if ssl_config.ssl_enabled:
            result = service_controller.apply_ssl_configuration(deployment, ssl_config)
            if not result['success']:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(result)
                messages.error(request, result['message'])
                return redirect('monitoring:ssl_configuration', deployment_id)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'SSL configuration updated successfully'
            })
        
        messages.success(request, 'SSL configuration updated successfully')
        
    except Exception as e:
        error_msg = f"Error updating configuration: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
    
    return redirect('monitoring:ssl_configuration', deployment_id)


@login_required
@require_http_methods(["GET"])
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_status(request, deployment_id):
    """Get SSL status for a deployment (JSON endpoint)."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    from .models import SSLConfiguration
    try:
        ssl_config = SSLConfiguration.objects.get(deployment=deployment)
        
        # Get certificate validation info
        validation_result = service_controller.validate_ssl_certificate(ssl_config)
        
        return JsonResponse({
            'success': True,
            'configured': True,
            'enabled': ssl_config.ssl_enabled,
            'status': ssl_config.status,
            'certificate_type': ssl_config.certificate_type,
            'domain': ssl_config.domain,
            'valid_until': ssl_config.certificate_expires_at.isoformat() if ssl_config.certificate_expires_at else None,
            'days_until_expiry': ssl_config.get_days_until_expiry() if ssl_config.certificate_expires_at else None,
            'validation': validation_result,
            'last_validation_at': ssl_config.last_validation_at.isoformat() if ssl_config.last_validation_at else None
        })
        
    except SSLConfiguration.DoesNotExist:
        return JsonResponse({
            'success': True,
            'configured': False,
            'enabled': False,
            'status': 'disabled',
            'message': 'SSL not configured for this deployment'
        })


@login_required
@require_http_methods(["GET"])
@require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by', lookup_field='deployment_id')
def ssl_validate(request, deployment_id):
    """Validate current SSL certificate."""
    # SECURITY FIX: Ownership verified by decorator
    deployment = get_object_or_404(ApplicationDeployment, pk=deployment_id, deployed_by=request.user)
    
    from .models import SSLConfiguration
    try:
        ssl_config = SSLConfiguration.objects.get(deployment=deployment)
        validation_result = service_controller.validate_ssl_certificate(ssl_config)
        
        # Update validation timestamp
        ssl_config.last_validation_at = timezone.now()
        
        if validation_result['valid']:
            ssl_config.status = ssl_config.SSLStatus.ENABLED if ssl_config.ssl_enabled else ssl_config.SSLStatus.DISABLED
            ssl_config.validation_error = ''
        else:
            ssl_config.status = ssl_config.SSLStatus.INVALID
            ssl_config.validation_error = validation_result['error']
        
        ssl_config.save()
        
        return JsonResponse(validation_result)
        
    except SSLConfiguration.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No SSL configuration found for this deployment'
        })
