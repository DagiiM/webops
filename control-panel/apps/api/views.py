from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
import secrets
import json
import os
from pathlib import Path

from .models import APIToken


def api_status(request):
    """
    Simple API status endpoint to check if the API is running.
    """
    return JsonResponse({
        'status': 'ok',
        'timestamp': timezone.now().isoformat()
    })


@login_required
@require_http_methods(["GET"])
def get_websocket_token(request):
    """
    Generate a temporary WebSocket token for the authenticated user.
    This token is specifically for WebSocket authentication and has a short expiry.
    """
    # Create a temporary token specifically for WebSocket use
    token_name = f"WebSocket Token - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Create a new API token with short expiry (1 hour)
    ws_token = APIToken.objects.create(
        user=request.user,
        name=token_name,
        expires_at=timezone.now() + timedelta(hours=1)
    )
    
    return JsonResponse({
        'token': ws_token.token,
        'expires_at': ws_token.expires_at.isoformat()
    })


@csrf_exempt
@require_http_methods(["POST"])
def refresh_websocket_token(request):
    """
    Refresh a WebSocket token. This endpoint accepts an existing token
    and returns a new one if the old token is valid.
    """
    from .authentication import get_user_from_token
    
    try:
        data = json.loads(request.body)
        old_token = data.get('token')
        
        if not old_token:
            return JsonResponse({'error': 'No token provided'}, status=400)
        
        # Verify the old token
        user = get_user_from_token(old_token)
        if not user:
            return JsonResponse({'error': 'Invalid token'}, status=401)
        
        # Create a new token
        token_name = f"WebSocket Token - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        new_token = APIToken.objects.create(
            user=user,
            name=token_name,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Deactivate the old token
        try:
            old_token_obj = APIToken.objects.get(token=old_token)
            old_token_obj.is_active = False
            old_token_obj.save()
        except APIToken.DoesNotExist:
            pass
        
        return JsonResponse({
            'token': new_token.token,
            'expires_at': new_token.expires_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Import existing deployment API views
from apps.deployments.api.deployments import (
    list_deployments,
    create_deployment,
    get_deployment,
    start_deployment_api,
    stop_deployment_api,
    restart_deployment_api,
    delete_deployment_api,
    get_deployment_logs,
    generate_env_api,
    validate_project_api,
    validate_env_api,
    get_env_vars_api,
    set_env_var_api,
    unset_env_var_api
)

# Wrapper functions for deployment API views with the expected names
@login_required
@require_http_methods(["GET"])
def deployment_list(request):
    """Wrapper for list_deployments"""
    return list_deployments(request)


@login_required
@require_http_methods(["POST"])
def deployment_create(request):
    """Wrapper for create_deployment"""
    return create_deployment(request)


@login_required
@require_http_methods(["GET"])
def deployment_detail(request, name):
    """Wrapper for get_deployment"""
    return get_deployment(request, name)


@login_required
@require_http_methods(["POST"])
def deployment_start(request, name):
    """Wrapper for start_deployment_api"""
    return start_deployment_api(request, name)


@login_required
@require_http_methods(["POST"])
def deployment_stop(request, name):
    """Wrapper for stop_deployment_api"""
    return stop_deployment_api(request, name)


@login_required
@require_http_methods(["POST"])
def deployment_restart(request, name):
    """Wrapper for restart_deployment_api"""
    return restart_deployment_api(request, name)


@login_required
@require_http_methods(["DELETE"])
def deployment_delete(request, name):
    """Wrapper for delete_deployment_api"""
    return delete_deployment_api(request, name)


@login_required
@require_http_methods(["GET"])
def deployment_logs(request, name):
    """Wrapper for get_deployment_logs"""
    return get_deployment_logs(request, name)


@login_required
@require_http_methods(["POST"])
def deployment_env_generate(request, name):
    """Wrapper for generate_env_api"""
    return generate_env_api(request, name)


@login_required
@require_http_methods(["GET"])
def deployment_project_validate(request, name):
    """Wrapper for validate_project_api"""
    return validate_project_api(request, name)


@login_required
@require_http_methods(["GET"])
def deployment_env_validate(request, name):
    """Wrapper for validate_env_api"""
    return validate_env_api(request, name)


@login_required
@require_http_methods(["GET"])
def deployment_env_vars(request, name):
    """Wrapper for get_env_vars_api"""
    return get_env_vars_api(request, name)


@login_required
@require_http_methods(["POST"])
def deployment_env_set(request, name):
    """Wrapper for set_env_var_api"""
    return set_env_var_api(request, name)


@login_required
@require_http_methods(["DELETE", "POST"])
def deployment_env_unset(request, name):
    """Wrapper for unset_env_var_api"""
    return unset_env_var_api(request, name)


# File Editor API Views
@login_required
@require_http_methods(["GET"])
def deployment_files_tree(request, deployment_id):
    """
    Get the file tree structure for a deployment.
    
    GET /api/deployments/{deployment_id}/files/tree/?path=/optional/subpath
    """
    try:
        from apps.deployments.models import ApplicationDeployment
        from apps.deployments.services import DeploymentService
        
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        
        if not repo_path.exists():
            return JsonResponse({'error': 'Repository not found'}, status=404)
        
        # Get the requested path, default to root
        requested_path = request.GET.get('path', '/')
        if requested_path == '/':
            requested_path = repo_path
        else:
            # Ensure the path is within the repo
            requested_path = repo_path / requested_path.lstrip('/')
            if not requested_path.exists() or not str(requested_path).startswith(str(repo_path)):
                return JsonResponse({'error': 'Invalid path'}, status=400)
        
        # Build file tree
        def build_tree(path):
            tree = []
            try:
                for item in path.iterdir():
                    # Skip hidden files and directories
                    if item.name.startswith('.'):
                        continue
                        
                    node = {
                        'name': item.name,
                        'path': str(item.relative_to(repo_path)),
                        'type': 'directory' if item.is_dir() else 'file'
                    }
                    
                    if item.is_dir():
                        node['children'] = build_tree(item)
                    
                    tree.append(node)
            except PermissionError:
                pass
            return tree
        
        tree = build_tree(requested_path)
        
        return JsonResponse({
            'success': True,
            'path': str(requested_path.relative_to(repo_path)),
            'tree': tree
        })
        
    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': 'Deployment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def deployment_file_read(request, deployment_id):
    """
    Read the contents of a file in a deployment.
    
    GET /api/deployments/{deployment_id}/files/read/?path=/path/to/file
    """
    try:
        from apps.deployments.models import ApplicationDeployment
        from apps.deployments.services import DeploymentService
        
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        
        if not repo_path.exists():
            return JsonResponse({'error': 'Repository not found'}, status=404)
        
        # Get the requested file path
        file_path = request.GET.get('path')
        if not file_path:
            return JsonResponse({'error': 'Path parameter is required'}, status=400)
        
        # Ensure the path is within the repo and is a file
        full_path = repo_path / file_path.lstrip('/')
        if not full_path.exists() or not full_path.is_file() or not str(full_path).startswith(str(repo_path)):
            return JsonResponse({'error': 'Invalid file path'}, status=400)
        
        # Read file content with size limit
        max_size = 1024 * 1024  # 1MB limit
        file_size = full_path.stat().st_size
        
        if file_size > max_size:
            return JsonResponse({'error': 'File too large'}, status=400)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with a different encoding
            try:
                with open(full_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception:
                return JsonResponse({'error': 'Cannot read binary file'}, status=400)
        
        return JsonResponse({
            'success': True,
            'path': file_path,
            'content': content,
            'size': file_size
        })
        
    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': 'Deployment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def deployment_file_write(request, deployment_id):
    """
    Write content to a file in a deployment.
    
    POST /api/deployments/{deployment_id}/files/write/
    Body: {
        "path": "/path/to/file",
        "content": "file content",
        "create_dirs": true
    }
    """
    try:
        from apps.deployments.models import ApplicationDeployment
        from apps.deployments.services import DeploymentService
        
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        
        if not repo_path.exists():
            return JsonResponse({'error': 'Repository not found'}, status=404)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        file_path = data.get('path')
        content = data.get('content', '')
        create_dirs = data.get('create_dirs', True)
        
        if not file_path:
            return JsonResponse({'error': 'Path parameter is required'}, status=400)
        
        # Ensure the path is within the repo
        full_path = repo_path / file_path.lstrip('/')
        if not str(full_path).startswith(str(repo_path)):
            return JsonResponse({'error': 'Invalid file path'}, status=400)
        
        # Create parent directories if needed
        if create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        elif not full_path.parent.exists():
            return JsonResponse({'error': 'Parent directory does not exist'}, status=400)
        
        # Write the file
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return JsonResponse({'error': f'Failed to write file: {str(e)}'}, status=500)
        
        return JsonResponse({
            'success': True,
            'message': f'File {file_path} saved successfully',
            'path': file_path
        })
        
    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': 'Deployment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# Database API Views
@login_required
@require_http_methods(["GET"])
def database_list(request):
    """
    List all databases.
    
    GET /api/databases/
    """
    try:
        from apps.databases.models import Database
        
        databases = Database.objects.all()
        db_list = []
        
        for db in databases:
            db_data = {
                'id': db.id,
                'name': db.name,
                'db_type': db.db_type,
                'host': db.host,
                'port': db.port,
                'database_name': db.database_name,
                'username': db.username,
                'is_active': db.is_active,
                'created_at': db.created_at.isoformat(),
                'updated_at': db.updated_at.isoformat(),
            }
            
            # Include deployment info if available
            if db.deployment:
                db_data['deployment'] = {
                    'id': db.deployment.id,
                    'name': db.deployment.name
                }
            
            # Include dependency status
            db_data['dependency_status'] = db.get_dependency_status()
            
            db_list.append(db_data)
        
        return JsonResponse({
            'databases': db_list,
            'count': len(db_list)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def database_detail(request, name):
    """
    Get details of a specific database.
    
    GET /api/databases/{name}/
    """
    try:
        from apps.databases.models import Database
        from apps.core.utils import decrypt_password
        from django.conf import settings
        
        try:
            database = Database.objects.get(name=name)
        except Database.DoesNotExist:
            return JsonResponse({'error': f'Database {name} not found'}, status=404)
        
        db_data = {
            'id': database.id,
            'name': database.name,
            'db_type': database.db_type,
            'host': database.host,
            'port': database.port,
            'database_name': database.database_name,
            'username': database.username,
            'is_active': database.is_active,
            'ssl_enabled': database.ssl_enabled,
            'connection_timeout': database.connection_timeout,
            'pool_size': database.pool_size,
            'environment': database.environment,
            'connection_uri': database.connection_uri,
            'metadata': database.metadata,
            'created_at': database.created_at.isoformat(),
            'updated_at': database.updated_at.isoformat(),
        }
        
        # Include deployment info if available
        if database.deployment:
            db_data['deployment'] = {
                'id': database.deployment.id,
                'name': database.deployment.name
            }
        
        # Include masked password and connection string
        db_data['connection_string'] = database.get_connection_string()
        
        # Include dependency status
        db_data['dependency_status'] = database.get_dependency_status()
        
        # Include required addons
        db_data['required_addons'] = [
            {'id': addon.id, 'name': addon.name}
            for addon in database.required_addons.all()
        ]
        
        return JsonResponse(db_data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def rate_limit_preview(request):
    """
    Preview the rate limit page.

    For testing/demo purposes only.
    Shows the ultra-sleek rate limit UI with real-time countdown.
    """
    import time
    from django.shortcuts import render

    # Sample data for preview (60 second countdown)
    now = int(time.time())
    context = {
        'retry_after': 60,  # 60 seconds
        'limit': 100,
        'remaining': 0,
        'reset': now + 60,  # Reset in 60 seconds
    }

    return render(request, 'errors/429.html', context, status=429)
