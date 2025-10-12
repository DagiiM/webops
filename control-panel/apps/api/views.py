"""
API views for WebOps.

Reference: CLAUDE.md "API Design" section

This module implements REST API endpoints for:
- Deployments (CRUD + actions)
- Databases (CRUD)
- Logs
"""

import json
from typing import Dict, Any
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator

from apps.deployments.models import Deployment, DeploymentLog
from apps.deployments.tasks import deploy_application, delete_deployment as delete_deployment_task
from apps.deployments.service_manager import ServiceManager
from apps.databases.models import Database
from apps.databases.services import DatabaseService

from .authentication import api_authentication_required, validate_request_data


# ============================================================================
# Deployment Endpoints
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def deployment_list(request) -> JsonResponse:
    """List all deployments with pagination."""
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 100)
    status_filter = request.GET.get('status')

    deployments = Deployment.objects.filter(deployed_by=request.user)
    if status_filter:
        deployments = deployments.filter(status=status_filter)

    paginator = Paginator(deployments, per_page)
    page_obj = paginator.get_page(page)

    deployment_list = [{
        'id': d.id,
        'name': d.name,
        'repo_url': d.repo_url,
        'branch': d.branch,
        'status': d.status,
        'project_type': d.project_type,
        'port': d.port,
        'domain': d.domain,
        'created_at': d.created_at.isoformat(),
        'updated_at': d.updated_at.isoformat(),
    } for d in page_obj]

    return JsonResponse({
        'deployments': deployment_list,
        'pagination': {
            'page': page_obj.number,
            'per_page': per_page,
            'total': paginator.count,
            'pages': paginator.num_pages
        }
    })


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
@validate_request_data(['name', 'repo_url'])
def deployment_create(request) -> JsonResponse:
    """Create new deployment."""
    data = request.json_data

    from apps.deployments.services import DeploymentService
    service = DeploymentService()

    if not service.validate_repo_url(data['repo_url']):
        return JsonResponse({
            'error': 'Invalid repository URL',
            'message': 'Must be a valid GitHub HTTPS URL'
        }, status=400)

    try:
        deployment = Deployment.objects.create(
            name=data['name'],
            repo_url=data['repo_url'],
            branch=data.get('branch', 'main'),
            domain=data.get('domain', ''),
            env_vars=data.get('env_vars', {}),
            deployed_by=request.user,
            status=Deployment.Status.PENDING
        )

        # Ensure Celery worker is running (non-interactive)
        ServiceManager().ensure_celery_running()
        deploy_application.delay(deployment.id)

        return JsonResponse({
            'id': deployment.id,
            'name': deployment.name,
            'status': deployment.status,
            'message': 'Deployment queued successfully'
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'error': 'Failed to create deployment',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def deployment_detail(request, name: str) -> JsonResponse:
    """Get deployment details."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    return JsonResponse({
        'id': deployment.id,
        'name': deployment.name,
        'repo_url': deployment.repo_url,
        'branch': deployment.branch,
        'status': deployment.status,
        'project_type': deployment.project_type,
        'port': deployment.port,
        'domain': deployment.domain,
        'env_vars': deployment.env_vars,
        'created_at': deployment.created_at.isoformat(),
        'updated_at': deployment.updated_at.isoformat(),
    })


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
def deployment_start(request, name: str) -> JsonResponse:
    """Start a deployment service."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    service_manager = ServiceManager()
    success, message = service_manager.start_service(deployment)

    if success:
        return JsonResponse({'success': True, 'message': message})
    else:
        return JsonResponse({'success': False, 'error': message}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
def deployment_stop(request, name: str) -> JsonResponse:
    """Stop a deployment service."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    service_manager = ServiceManager()
    success, message = service_manager.stop_service(deployment)

    if success:
        return JsonResponse({'success': True, 'message': message})
    else:
        return JsonResponse({'success': False, 'error': message}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
def deployment_restart(request, name: str) -> JsonResponse:
    """Restart a deployment service."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    service_manager = ServiceManager()
    success, message = service_manager.restart_service(deployment)

    if success:
        return JsonResponse({'success': True, 'message': message})
    else:
        return JsonResponse({'success': False, 'error': message}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@api_authentication_required
def deployment_delete(request, name: str) -> JsonResponse:
    """Delete a deployment."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    deployment_id = deployment.id
    deployment_name = deployment.name

    # Ensure Celery worker is running (non-interactive)
    ServiceManager().ensure_celery_running()
    delete_deployment_task.delay(deployment_id)

    return JsonResponse({
        'success': True,
        'message': f'Deployment {deployment_name} deletion queued'
    })


@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def deployment_logs(request, name: str) -> JsonResponse:
    """Get deployment logs."""
    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    tail = min(int(request.GET.get('tail', 100)), 1000)
    level_filter = request.GET.get('level')

    logs = deployment.logs.all()
    if level_filter:
        logs = logs.filter(level=level_filter)
    logs = logs[:tail]

    log_list = [{
        'level': log.level,
        'message': log.message,
        'created_at': log.created_at.isoformat(),
    } for log in logs]

    return JsonResponse({'logs': log_list})


# ============================================================================
# Database Endpoints
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def database_list(request) -> JsonResponse:
    """List all databases."""
    databases = Database.objects.filter(deployment__deployed_by=request.user)

    database_list = [{
        'id': db.id,
        'name': db.name,
        'username': db.username,
        'host': db.host,
        'port': db.port,
        'deployment': db.deployment.name if db.deployment else None,
        'created_at': db.created_at.isoformat(),
    } for db in databases]

    return JsonResponse({'databases': database_list})


@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def database_detail(request, name: str) -> JsonResponse:
    """Get database credentials."""
    database = get_object_or_404(
        Database,
        name=name,
        deployment__deployed_by=request.user
    )

    db_service = DatabaseService()
    connection_string = db_service.get_connection_string(database, decrypted=True)

    from apps.core.utils.encryption import decrypt_password
    decrypted_password = decrypt_password(database.password)

    return JsonResponse({
        'name': database.name,
        'username': database.username,
        'password': decrypted_password,
        'host': database.host,
        'port': database.port,
        'connection_string': connection_string
    })


# ============================================================================
# File Editor Endpoints
# ============================================================================

from django.contrib.auth.decorators import login_required

@require_http_methods(["GET"])
def deployment_files_tree(request, deployment_id: int) -> JsonResponse:
    """Get file tree for deployment."""
    from pathlib import Path

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    deployment = get_object_or_404(
        Deployment,
        id=deployment_id,
        deployed_by=request.user
    )

    from apps.deployments.services import DeploymentService
    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'error': 'Repository not cloned yet'
        }, status=400)

    def build_tree(path: Path, max_depth: int = 5, current_depth: int = 0) -> list:
        """Recursively build file tree."""
        if current_depth >= max_depth:
            return []

        items = []
        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                # Skip hidden and ignored files/folders
                if item.name.startswith('.') and item.name not in ['.env.example', '.gitignore']:
                    continue
                if item.name in ['__pycache__', 'node_modules', '.git', 'venv', '.venv', 'dist', 'build']:
                    continue

                rel_path = str(item.relative_to(repo_path))

                if item.is_dir():
                    items.append({
                        'name': item.name,
                        'path': rel_path,
                        'type': 'directory',
                        'children': build_tree(item, max_depth, current_depth + 1)
                    })
                else:
                    items.append({
                        'name': item.name,
                        'path': rel_path,
                        'type': 'file'
                    })
        except PermissionError:
            pass

        return items

    tree = build_tree(repo_path)

    return JsonResponse({
        'tree': tree,
        'root': str(repo_path)
    })


@require_http_methods(["GET"])
def deployment_file_read(request, deployment_id: int) -> JsonResponse:
    """Read file content."""
    from pathlib import Path

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    deployment = get_object_or_404(
        Deployment,
        id=deployment_id,
        deployed_by=request.user
    )

    from apps.deployments.services import DeploymentService
    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'error': 'Repository not cloned yet'
        }, status=400)

    # Get file path from query parameter
    file_path = request.GET.get('path', '')

    # Security: prevent directory traversal
    if '..' in file_path or file_path.startswith('/'):
        return JsonResponse({
            'error': 'Invalid path'
        }, status=400)

    target_path = repo_path / file_path

    # Ensure path is within repo
    try:
        target_path.resolve().relative_to(repo_path.resolve())
    except ValueError:
        return JsonResponse({
            'error': 'Invalid path - outside repository'
        }, status=400)

    if not target_path.exists():
        return JsonResponse({
            'error': 'File not found'
        }, status=404)

    if not target_path.is_file():
        return JsonResponse({
            'error': 'Not a file'
        }, status=400)

    # Check file size (limit to 5MB for editor)
    file_size = target_path.stat().st_size
    if file_size > 5 * 1024 * 1024:
        return JsonResponse({
            'error': 'File too large (>5MB)'
        }, status=400)

    # Try to read as text
    try:
        content = target_path.read_text(encoding='utf-8')
        return JsonResponse({
            'content': content,
            'path': file_path,
            'size': file_size,
            'name': target_path.name
        })
    except UnicodeDecodeError:
        return JsonResponse({
            'error': 'Binary file - cannot display'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def deployment_file_write(request, deployment_id: int) -> JsonResponse:
    """Write file content."""
    from pathlib import Path

    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    deployment = get_object_or_404(
        Deployment,
        id=deployment_id,
        deployed_by=request.user
    )

    from apps.deployments.services import DeploymentService
    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'error': 'Repository not cloned yet'
        }, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON'
        }, status=400)

    file_path = data.get('path')
    content = data.get('content')

    if not file_path or content is None:
        return JsonResponse({
            'error': 'Missing required fields: path and content'
        }, status=400)

    # Security: prevent directory traversal
    if '..' in file_path or file_path.startswith('/'):
        return JsonResponse({
            'error': 'Invalid path'
        }, status=400)

    target_path = repo_path / file_path

    # Ensure path is within repo
    try:
        target_path.resolve().relative_to(repo_path.resolve())
    except ValueError:
        return JsonResponse({
            'error': 'Invalid path - outside repository'
        }, status=400)

    # Don't allow writing to certain sensitive files
    forbidden_files = ['.git', 'venv', '.venv', '__pycache__']
    if any(part in target_path.parts for part in forbidden_files):
        return JsonResponse({
            'error': 'Cannot modify this file'
        }, status=403)

    try:
        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        target_path.write_text(content, encoding='utf-8')

        return JsonResponse({
            'success': True,
            'message': f'File {file_path} saved successfully',
            'size': len(content)
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


# ============================================================================
# Environment Variable Management Endpoints
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def deployment_env_vars(request, name: str) -> JsonResponse:
    """Get all environment variables for a deployment."""
    from apps.deployments import api_views as deploy_api

    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    # Call the deployment API view
    return deploy_api.get_env_vars_api(request, name)


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
def deployment_env_generate(request, name: str) -> JsonResponse:
    """Generate .env file from .env.example."""
    from apps.deployments import api_views as deploy_api

    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    # Call the deployment API view
    return deploy_api.generate_env_api(request, name)


@csrf_exempt
@require_http_methods(["GET"])
@api_authentication_required
def deployment_env_validate(request, name: str) -> JsonResponse:
    """Validate .env file for a deployment."""
    from apps.deployments import api_views as deploy_api

    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    # Call the deployment API view
    return deploy_api.validate_env_api(request, name)


@csrf_exempt
@require_http_methods(["POST"])
@api_authentication_required
def deployment_env_set(request, name: str) -> JsonResponse:
    """Set an environment variable."""
    from apps.deployments import api_views as deploy_api

    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    # Call the deployment API view
    return deploy_api.set_env_var_api(request, name)


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
@api_authentication_required
def deployment_env_unset(request, name: str) -> JsonResponse:
    """Remove an environment variable."""
    from apps.deployments import api_views as deploy_api

    deployment = get_object_or_404(
        Deployment,
        name=name,
        deployed_by=request.user
    )

    # Call the deployment API view
    return deploy_api.unset_env_var_api(request, name)


# ============================================================================
# Status Endpoint
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
def api_status(request) -> JsonResponse:
    """API health check."""
    return JsonResponse({
        'status': 'ok',
        'version': '0.3.0'
    })
