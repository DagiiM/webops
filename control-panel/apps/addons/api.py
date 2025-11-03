"""
API views for WebOps addon management.

Provides REST API endpoints for:
- Addon discovery and listing
- System addon installation/uninstallation
- Addon configuration
- Health checks and status
- Execution history
"""

from typing import Dict, Any, Optional
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
import json
import logging

from .models import SystemAddon, AddonExecution, Addon
from .unified_registry import get_addon_registry
from .tasks import (
    install_system_addon,
    uninstall_system_addon,
    configure_system_addon,
    sync_system_addon_status,
)
from .permissions import (
    require_addon_permission,
    get_user_addon_permissions,
    AddonPermissions,
)
from .rate_limiting import rate_limit
from .validation import (
    validate_request_json,
    validate_addon_name_param,
    AddonSchemas,
    validate_pagination_params,
    ValidationError,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Addon Listing and Discovery
# ============================================================================

@login_required
@rate_limit('list')
@require_http_methods(["GET"])
def list_addons(request) -> JsonResponse:
    """
    List all available addons (both system and application).

    Query Parameters:
        - type: Filter by addon type ('system', 'application')
        - status: Filter by status
        - category: Filter by category
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)

    Rate Limit: 100 requests per minute
    """
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    addon_type = request.GET.get('type')
    status = request.GET.get('status')
    category = request.GET.get('category')

    # Get system addons
    system_addons = []
    if not addon_type or addon_type == 'system':
        queryset = SystemAddon.objects.all()

        if status:
            queryset = queryset.filter(status=status)
        if category:
            queryset = queryset.filter(category=category)

        system_addons = [
            _serialize_system_addon(addon)
            for addon in queryset
        ]

    # Get application addons
    app_addons = []
    if not addon_type or addon_type == 'application':
        queryset = Addon.objects.all()

        app_addons = [
            _serialize_app_addon(addon)
            for addon in queryset
        ]

    # Combine and paginate
    all_addons = system_addons + app_addons

    paginator = Paginator(all_addons, per_page)
    page_obj = paginator.get_page(page)

    return JsonResponse({
        'addons': list(page_obj),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': len(all_addons),
            'pages': paginator.num_pages,
        }
    })


@login_required
@require_http_methods(["GET"])
def get_addon(request, name: str) -> JsonResponse:
    """
    Get detailed information about a specific addon.

    URL Parameters:
        - name: Addon name
    """
    # Try system addon first
    try:
        addon = SystemAddon.objects.get(name=name)
        return JsonResponse(_serialize_system_addon(addon, detailed=True))
    except SystemAddon.DoesNotExist:
        pass

    # Try application addon
    try:
        addon = Addon.objects.get(name=name)
        return JsonResponse(_serialize_app_addon(addon, detailed=True))
    except Addon.DoesNotExist:
        pass

    return JsonResponse({'error': f'Addon {name} not found'}, status=404)


@login_required
@rate_limit('discover')
@require_addon_permission(AddonPermissions.INSTALL_SYSTEM_ADDON, api=True)
@require_http_methods(["POST"])
def discover_addons(request) -> JsonResponse:
    """
    Trigger addon discovery process.

    Discovers all system addons from filesystem and updates database.
    Requires: install_systemaddon permission
    Rate Limit: 5 requests per minute
    """
    try:
        registry = get_addon_registry()
        count = registry.discover_system_addons()

        return JsonResponse({
            'success': True,
            'message': f'Discovered {count} system addon(s)',
            'count': count
        })
    except Exception as e:
        logger.exception("Error discovering addons")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ============================================================================
# System Addon Operations
# ============================================================================

@login_required
@rate_limit('install')
@require_addon_permission(AddonPermissions.INSTALL_SYSTEM_ADDON, api=True)
@validate_request_json(AddonSchemas.INSTALL_REQUEST_SCHEMA)
@validate_addon_name_param
@require_http_methods(["POST"])
def install_addon(request, name: str) -> JsonResponse:
    """
    Install a system addon.

    URL Parameters:
        - name: Addon name

    Requires: install_systemaddon permission
    Rate Limit: 10 requests per minute

    Request Body (JSON):
        - config: Optional configuration dict
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        # Parse config from request body
        config = {}
        if request.body:
            try:
                data = json.loads(request.body)
                config = data.get('config', {})
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Trigger async installation
        task = install_system_addon.delay(
            addon_id=addon.id,
            config=config,
            user_id=request.user.id
        )

        return JsonResponse({
            'success': True,
            'message': f'Installation of {name} started',
            'task_id': task.id,
            'addon': _serialize_system_addon(addon)
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error installing addon {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@rate_limit('uninstall')
@require_addon_permission(AddonPermissions.UNINSTALL_SYSTEM_ADDON, api=True)
@validate_request_json(AddonSchemas.UNINSTALL_REQUEST_SCHEMA)
@validate_addon_name_param
@require_http_methods(["POST"])
def uninstall_addon(request, name: str) -> JsonResponse:
    """
    Uninstall a system addon.

    URL Parameters:
        - name: Addon name

    Requires: uninstall_systemaddon permission
    Rate Limit: 10 requests per minute

    Request Body (JSON):
        - keep_data: Whether to keep data (default: true)
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        # Parse options from request body
        keep_data = True
        if request.body:
            try:
                data = json.loads(request.body)
                keep_data = data.get('keep_data', True)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Trigger async uninstallation
        task = uninstall_system_addon.delay(
            addon_id=addon.id,
            keep_data=keep_data,
            user_id=request.user.id
        )

        return JsonResponse({
            'success': True,
            'message': f'Uninstallation of {name} started',
            'task_id': task.id,
            'addon': _serialize_system_addon(addon)
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error uninstalling addon {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@rate_limit('configure')
@require_addon_permission(AddonPermissions.CONFIGURE_SYSTEM_ADDON, api=True)
@validate_request_json(AddonSchemas.CONFIGURE_REQUEST_SCHEMA)
@validate_addon_name_param
@require_http_methods(["POST"])
def configure_addon(request, name: str) -> JsonResponse:
    """
    Configure a system addon.

    URL Parameters:
        - name: Addon name

    Requires: configure_systemaddon permission
    Rate Limit: 30 requests per minute

    Request Body (JSON):
        - config: Configuration dict
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        # Parse config from request body
        if not request.body:
            return JsonResponse({'error': 'Configuration required'}, status=400)

        try:
            data = json.loads(request.body)
            config = data.get('config')
            if not config:
                return JsonResponse({'error': 'Config key required'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Trigger async configuration
        task = configure_system_addon.delay(
            addon_id=addon.id,
            config=config,
            user_id=request.user.id
        )

        return JsonResponse({
            'success': True,
            'message': f'Configuration of {name} started',
            'task_id': task.id,
            'addon': _serialize_system_addon(addon)
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error configuring addon {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def sync_addon_status(request, name: str) -> JsonResponse:
    """
    Sync addon status from system to database.

    URL Parameters:
        - name: Addon name
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        # Trigger async status sync
        task = sync_system_addon_status.delay(addon.id)

        return JsonResponse({
            'success': True,
            'message': f'Status sync for {name} started',
            'task_id': task.id
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error syncing addon status {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def toggle_addon(request, name: str) -> JsonResponse:
    """
    Enable or disable an addon.

    URL Parameters:
        - name: Addon name

    Request Body (JSON):
        - enabled: Boolean
    """
    try:
        # Try system addon first
        try:
            addon = SystemAddon.objects.get(name=name)
            addon_type = 'system'
        except SystemAddon.DoesNotExist:
            addon = Addon.objects.get(name=name)
            addon_type = 'application'

        # Parse enabled from request body
        if not request.body:
            return JsonResponse({'error': 'enabled parameter required'}, status=400)

        try:
            data = json.loads(request.body)
            enabled = data.get('enabled')
            if enabled is None:
                return JsonResponse({'error': 'enabled key required'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        addon.enabled = enabled
        addon.save()

        return JsonResponse({
            'success': True,
            'message': f'Addon {name} {"enabled" if enabled else "disabled"}',
            'addon': {
                'name': addon.name,
                'enabled': addon.enabled,
                'type': addon_type
            }
        })

    except (SystemAddon.DoesNotExist, Addon.DoesNotExist):
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error toggling addon {name}")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# Health and Status
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_addon_status(request, name: str) -> JsonResponse:
    """
    Get current status of an addon.

    URL Parameters:
        - name: Addon name
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        return JsonResponse({
            'name': addon.name,
            'status': addon.status,
            'health': addon.health,
            'version': addon.version or 'unknown',
            'installed_at': addon.installed_at.isoformat() if addon.installed_at else None,
            'last_error': addon.last_error
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error getting addon status {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def health_check_addons(request) -> JsonResponse:
    """
    Trigger health check for all installed system addons.
    """
    try:
        from .tasks import health_check_system_addons

        task = health_check_system_addons.delay()

        return JsonResponse({
            'success': True,
            'message': 'Health check started for all addons',
            'task_id': task.id
        })

    except Exception as e:
        logger.exception("Error starting health check")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# Execution History
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_addon_executions(request, name: str) -> JsonResponse:
    """
    Get execution history for an addon.

    URL Parameters:
        - name: Addon name

    Query Parameters:
        - page: Page number (default: 1)
        - per_page: Items per page (default: 20)
        - operation: Filter by operation type
        - status: Filter by status
    """
    try:
        addon = SystemAddon.objects.get(name=name)

        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        operation = request.GET.get('operation')
        status = request.GET.get('status')

        queryset = addon.executions.all()

        if operation:
            queryset = queryset.filter(operation=operation)
        if status:
            queryset = queryset.filter(status=status)

        queryset = queryset.order_by('-started_at')

        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page)

        executions = [
            {
                'id': exec.id,
                'operation': exec.operation,
                'status': exec.status,
                'started_at': exec.started_at.isoformat(),
                'completed_at': exec.completed_at.isoformat() if exec.completed_at else None,
                'duration_ms': exec.duration_ms,
                'requested_by': exec.requested_by.username if exec.requested_by else None,
                'error_message': exec.error_message,
                'celery_task_id': exec.celery_task_id
            }
            for exec in page_obj
        ]

        return JsonResponse({
            'executions': executions,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginator.count,
                'pages': paginator.num_pages,
            }
        })

    except SystemAddon.DoesNotExist:
        return JsonResponse({'error': f'Addon {name} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error getting executions for {name}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_execution_detail(request, execution_id: int) -> JsonResponse:
    """
    Get detailed information about a specific execution.

    URL Parameters:
        - execution_id: Execution ID
    """
    try:
        execution = AddonExecution.objects.get(id=execution_id)

        return JsonResponse({
            'id': execution.id,
            'addon': execution.system_addon.name,
            'operation': execution.operation,
            'status': execution.status,
            'started_at': execution.started_at.isoformat(),
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'duration_ms': execution.duration_ms,
            'requested_by': execution.requested_by.username if execution.requested_by else None,
            'input_data': execution.input_data,
            'output_data': execution.output_data,
            'error_message': execution.error_message,
            'stdout': execution.stdout,
            'stderr': execution.stderr,
            'celery_task_id': execution.celery_task_id
        })

    except AddonExecution.DoesNotExist:
        return JsonResponse({'error': f'Execution {execution_id} not found'}, status=404)
    except Exception as e:
        logger.exception(f"Error getting execution {execution_id}")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# Statistics and Metrics
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_addon_stats(request) -> JsonResponse:
    """
    Get overall statistics for all addons.
    """
    try:
        # System addon stats
        system_stats = {
            'total': SystemAddon.objects.count(),
            'installed': SystemAddon.objects.filter(status='installed').count(),
            'healthy': SystemAddon.objects.filter(health='healthy').count(),
            'unhealthy': SystemAddon.objects.filter(health='unhealthy').count(),
            'degraded': SystemAddon.objects.filter(health='degraded').count(),
        }

        # Application addon stats
        app_stats = {
            'total': Addon.objects.count(),
            'enabled': Addon.objects.filter(enabled=True).count(),
        }

        # Execution stats (last 24 hours)
        from django.utils import timezone
        from datetime import timedelta

        yesterday = timezone.now() - timedelta(days=1)
        recent_executions = AddonExecution.objects.filter(started_at__gte=yesterday)

        execution_stats = {
            'total': recent_executions.count(),
            'success': recent_executions.filter(status='success').count(),
            'failed': recent_executions.filter(status='failed').count(),
            'running': recent_executions.filter(status='running').count(),
        }

        return JsonResponse({
            'system_addons': system_stats,
            'application_addons': app_stats,
            'executions_24h': execution_stats
        })

    except Exception as e:
        logger.exception("Error getting addon stats")
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# Helper Functions
# ============================================================================

def _serialize_system_addon(addon: SystemAddon, detailed: bool = False) -> Dict[str, Any]:
    """Serialize a SystemAddon to a dictionary."""
    data = {
        'id': addon.id,
        'name': addon.name,
        'display_name': addon.display_name,
        'type': 'system',
        'version': addon.version or 'unknown',
        'status': addon.status,
        'health': addon.health,
        'enabled': addon.enabled,
        'category': addon.category,
        'description': addon.description,
        'created_at': addon.created_at.isoformat(),
        'updated_at': addon.updated_at.isoformat(),
    }

    if detailed:
        data.update({
            'script_path': addon.script_path,
            'depends_on': addon.depends_on,
            'provides': addon.provides,
            'conflicts_with': addon.conflicts_with,
            'config': addon.config,
            'installed_at': addon.installed_at.isoformat() if addon.installed_at else None,
            'installed_by': addon.installed_by.username if addon.installed_by else None,
            'last_run_at': addon.last_run_at.isoformat() if addon.last_run_at else None,
            'last_success_at': addon.last_success_at.isoformat() if addon.last_success_at else None,
            'last_error': addon.last_error,
            'last_duration_ms': addon.last_duration_ms,
            'success_count': addon.success_count,
            'failure_count': addon.failure_count,
        })

    return data


def _serialize_app_addon(addon: Addon, detailed: bool = False) -> Dict[str, Any]:
    """Serialize an Addon (application) to a dictionary."""
    data = {
        'id': addon.id,
        'name': addon.name,
        'display_name': addon.name,  # No separate display name for app addons
        'type': 'application',
        'version': addon.version,
        'enabled': addon.enabled,
        'description': addon.description,
        'author': addon.author,
        'license': addon.license,
        'created_at': addon.created_at.isoformat(),
        'updated_at': addon.updated_at.isoformat(),
    }

    if detailed:
        data.update({
            'django_app': addon.django_app,
            'cli_entrypoint': addon.cli_entrypoint,
            'manifest_path': addon.manifest_path,
            'capabilities': addon.capabilities,
            'settings_schema': addon.settings_schema,
            'last_run_at': addon.last_run_at.isoformat() if addon.last_run_at else None,
            'last_success_at': addon.last_success_at.isoformat() if addon.last_success_at else None,
            'last_duration_ms': addon.last_duration_ms,
            'last_error': addon.last_error,
            'success_count': addon.success_count,
            'failure_count': addon.failure_count,
        })

    return data
