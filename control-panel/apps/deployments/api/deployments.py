"""
API views for WebOps deployments.

"API Design" section

This module implements REST API endpoints for:
- Deployment management
- Environment variable management
- Log retrieval
"""

from typing import Dict, Any
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from pathlib import Path
import json

from ..models import ApplicationDeployment, DeploymentLog
from apps.services.background import get_background_processor
from apps.core.managers.env_manager import EnvManager
from ..shared.validators import validate_project


@login_required
@require_http_methods(["GET"])
def api_status(request) -> JsonResponse:
    """Get API status."""
    return JsonResponse({
        'status': 'ok',
        'version': '0.1.0',
        'timestamp': '2025-10-10T00:00:00Z'
    })


@login_required
@require_http_methods(["GET"])
def list_deployments(request) -> JsonResponse:
    """List all deployments with pagination."""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status_filter = request.GET.get('status')

    queryset = ApplicationDeployment.objects.all()

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)

    deployments = [
        {
            'id': d.id,
            'name': d.name,
            'status': d.status,
            'project_type': d.project_type,
            'repo_url': d.repo_url,
            'branch': d.branch,
            'domain': d.domain,
            'port': d.port,
            'created_at': d.created_at.isoformat(),
            'updated_at': d.updated_at.isoformat(),
        }
        for d in page_obj
    ]

    return JsonResponse({
        'deployments': deployments,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': paginator.count,
            'pages': paginator.num_pages,
        }
    })


@login_required
@require_http_methods(["GET"])
def get_deployment(request, name: str) -> JsonResponse:
    """Get deployment details by name."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        return JsonResponse({
            'id': deployment.id,
            'name': deployment.name,
            'status': deployment.status,
            'project_type': deployment.project_type,
            'repo_url': deployment.repo_url,
            'branch': deployment.branch,
            'domain': deployment.domain,
            'port': deployment.port,
            'created_at': deployment.created_at.isoformat(),
            'updated_at': deployment.updated_at.isoformat(),
            'env_vars': deployment.env_vars or {},
        })
    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def create_deployment(request) -> JsonResponse:
    """Create new deployment."""
    try:
        data = json.loads(request.body)

        # Validate required fields
        required_fields = ['name', 'repo_url']
        if not all(field in data for field in required_fields):
            return JsonResponse(
                {'error': 'Missing required fields: name, repo_url'},
                status=400
            )

        # Check if deployment already exists
        if ApplicationDeployment.objects.filter(name=data['name']).exists():
            return JsonResponse(
                {'error': f"Deployment {data['name']} already exists"},
                status=400
            )

        # Create deployment
        deployment = ApplicationDeployment.objects.create(
            name=data['name'],
            repo_url=data['repo_url'],
            branch=data.get('branch', 'main'),
            domain=data.get('domain', ''),
            env_vars=data.get('env_vars', {}),
            status=ApplicationDeployment.Status.PENDING
        )

        # Ensure Celery worker is running (non-interactive)
        from ..shared import ServiceManager
        ServiceManager().ensure_celery_running()

        # Queue deployment task
        # deploy_application.delay(deployment.id)
        get_background_processor().submit('apps.deployments.tasks.application.deploy_application', deployment.id)

        return JsonResponse({
            'id': deployment.id,
            'name': deployment.name,
            'status': deployment.status,
            'message': 'Deployment queued successfully'
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_deployment_logs(request, name: str) -> JsonResponse:
    """Get deployment logs."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        tail = request.GET.get('tail')
        queryset = DeploymentLog.objects.filter(deployment=deployment)

        if tail:
            queryset = queryset[:int(tail)]

        logs = [
            {
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at.isoformat(),
            }
            for log in queryset
        ]

        return JsonResponse({'logs': logs})

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def start_deployment_api(request, name: str) -> JsonResponse:
    """Start a deployment."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Update status
        deployment.status = ApplicationDeployment.Status.RUNNING
        deployment.save(update_fields=['status'])

        return JsonResponse({
            'message': f'Deployment {name} started',
            'status': deployment.status
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def stop_deployment_api(request, name: str) -> JsonResponse:
    """Stop a deployment."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Ensure Celery worker is running (non-interactive)
        from ..shared import ServiceManager
        ServiceManager().ensure_celery_running()

        # Queue stop task
        # stop_deployment.delay(deployment.id)
        get_background_processor().submit('apps.deployments.tasks.stop_deployment', deployment.id)

        return JsonResponse({
            'message': f'Deployment {name} stop queued',
            'status': deployment.status
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def restart_deployment_api(request, name: str) -> JsonResponse:
    """Restart a deployment."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Ensure Celery worker is running (non-interactive)
        from ..shared import ServiceManager
        ServiceManager().ensure_celery_running()

        # Queue restart task
        # restart_deployment.delay(deployment.id)
        get_background_processor().submit('apps.deployments.tasks.restart_deployment', deployment.id)

        return JsonResponse({
            'message': f'Deployment {name} restart queued',
            'status': deployment.status
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


@login_required
@require_http_methods(["DELETE"])
def delete_deployment_api(request, name: str) -> JsonResponse:
    """Delete a deployment."""
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Ensure Celery worker is running (non-interactive)
        from ..shared import ServiceManager
        ServiceManager().ensure_celery_running()

        # Queue delete task
        get_background_processor().submit('apps.deployments.tasks.application.delete_deployment', deployment.id)

        return JsonResponse({
            'message': f'Deployment {name} delete queued'
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)


# Environment Variable Management API Endpoints

@login_required
@require_http_methods(["POST"])
def generate_env_api(request, name: str) -> JsonResponse:
    """
    Generate .env file from .env.example for a deployment.

    POST /api/deployments/{name}/env/generate/
    Body: {
        "debug": false,
        "domain": "example.com",
        "custom_vars": {"KEY": "value"}
    }
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Get deployment path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)

        if not repo_path.exists():
            return JsonResponse(
                {'error': 'Repository not cloned yet. Deploy first.'},
                status=400
            )

        # Prepare database info
        from apps.databases.models import Database
        from apps.core.utils import decrypt_password

        database_info = None
        try:
            db = Database.objects.filter(deployment=deployment).first()
            if db:
                database_info = {
                    'db_name': db.name,
                    'db_user': db.username,
                    'db_password': decrypt_password(db.password),
                    'db_host': db.host,
                    'db_port': str(db.port),
                }
        except Exception:
            pass

        # Generate .env file
        success, message = EnvManager.process_env_file(
            repo_path=repo_path,
            deployment_name=deployment.name,
            domain=data.get('domain', deployment.domain),
            database_info=database_info,
            redis_url="redis://localhost:6379/0",
            debug=data.get('debug', False),
            custom_values=data.get('custom_vars')
        )

        if success:
            return JsonResponse({
                'success': True,
                'message': message
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message
            }, status=400)

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def validate_project_api(request, name: str) -> JsonResponse:
    """
    Validate deployment project structure and requirements.

    GET /api/deployments/{name}/project/validate/
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Get repo path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)

        if not repo_path.exists():
            return JsonResponse(
                {'error': 'Repository not cloned yet. Deploy first.'},
                status=400
            )

        all_passed, results = validate_project(repo_path)

        return JsonResponse({
            'success': True,
            'all_passed': all_passed,
            'results': [
                {
                    'passed': r.passed,
                    'message': r.message,
                    'level': r.level,
                    'details': r.details,
                }
                for r in results
            ]
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def validate_env_api(request, name: str) -> JsonResponse:
    """
    Validate .env file for a deployment.

    GET /api/deployments/{name}/env/validate/
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Get deployment path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)

        if not repo_path.exists():
            return JsonResponse(
                {'error': 'Repository not cloned yet. Deploy first.'},
                status=400
            )

        # Validate .env file
        is_valid, missing = EnvManager.validate_env_file(repo_path)

        return JsonResponse({
            'valid': is_valid,
            'missing': missing
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_env_vars_api(request, name: str) -> JsonResponse:
    """
    Get all environment variables for a deployment.

    GET /api/deployments/{name}/env/
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Get deployment path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        env_file = repo_path / '.env'

        if not env_file.exists():
            return JsonResponse({'env_vars': {}})

        # Parse .env file
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    env_vars[key.strip()] = value

        return JsonResponse({'env_vars': env_vars})

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def set_env_var_api(request, name: str) -> JsonResponse:
    """
    Set an environment variable for a deployment.

    POST /api/deployments/{name}/env/set/
    Body: {"key": "DEBUG", "value": "False"}
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'key' not in data or 'value' not in data:
            return JsonResponse({'error': 'Missing key or value'}, status=400)

        key = data['key'].strip()
        value = data['value']

        # Get deployment path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        env_file = repo_path / '.env'

        if not env_file.exists():
            return JsonResponse({'error': '.env file not found'}, status=404)

        # Read current .env
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Update or add the variable
        found = False
        new_lines = []
        for line in lines:
            if line.strip() and not line.strip().startswith('#') and '=' in line:
                existing_key = line.split('=', 1)[0].strip()
                if existing_key == key:
                    # Update existing
                    if ' ' in value or any(c in value for c in ['#', '$', '&']):
                        new_lines.append(f'{key}="{value}"\n')
                    else:
                        new_lines.append(f'{key}={value}\n')
                    found = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # Add new variable if not found
        if not found:
            if ' ' in value or any(c in value for c in ['#', '$', '&']):
                new_lines.append(f'\n{key}="{value}"\n')
            else:
                new_lines.append(f'\n{key}={value}\n')

        # Write back
        with open(env_file, 'w') as f:
            f.writelines(new_lines)

        return JsonResponse({
            'success': True,
            'message': f'Set {key} = {value}'
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE", "POST"])
def unset_env_var_api(request, name: str) -> JsonResponse:
    """
    Remove an environment variable from a deployment.

    DELETE /api/deployments/{name}/env/unset/
    Body: {"key": "DEBUG"}
    """
    try:
        deployment = ApplicationDeployment.objects.get(name=name)

        # Parse request body
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'key' not in data:
            return JsonResponse({'error': 'Missing key'}, status=400)

        key = data['key'].strip()

        # Get deployment path
        from ..services import DeploymentService
        service = DeploymentService()
        repo_path = service.get_repo_path(deployment)
        env_file = repo_path / '.env'

        if not env_file.exists():
            return JsonResponse({'error': '.env file not found'}, status=404)

        # Read current .env
        with open(env_file, 'r') as f:
            lines = f.readlines()

        # Remove the variable
        new_lines = []
        removed = False
        for line in lines:
            if line.strip() and not line.strip().startswith('#') and '=' in line:
                existing_key = line.split('=', 1)[0].strip()
                if existing_key == key:
                    removed = True
                    continue  # Skip this line
            new_lines.append(line)

        if not removed:
            return JsonResponse({'error': f'Variable {key} not found'}, status=404)

        # Write back
        with open(env_file, 'w') as f:
            f.writelines(new_lines)

        return JsonResponse({
            'success': True,
            'message': f'Removed {key}'
        })

    except ApplicationDeployment.DoesNotExist:
        return JsonResponse({'error': f'Deployment {name} not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
