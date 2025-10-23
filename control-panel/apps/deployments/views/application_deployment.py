"""
Views for Deployments app.

"Django App Structure" section
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import BaseDeployment, DeploymentLog, ApplicationDeployment


@login_required
def deployment_list(request):
    """List all deployments."""
    deployments = ApplicationDeployment.objects.all()
    return render(request, 'deployments/list.html', {
        'deployments': deployments
    })


@login_required
def deployment_detail(request, pk):
    """Show deployment details and logs."""
    deployment = get_object_or_404(ApplicationDeployment, pk=pk)
    logs = deployment.logs.all()[:100]  # Last 100 logs

    # Get service status
    from ..shared import ServiceManager
    service_manager = ServiceManager()
    service_status = service_manager.get_service_status(deployment)

    # Check for Celery services (placeholder - no configuration relationship exists)
    # TODO: Implement proper Celery service detection if needed
    celery_services = []

    return render(request, 'deployments/detail.html', {
        'deployment': deployment,
        'logs': logs,
        'service_status': service_status,
        'celery_services': celery_services
    })


@login_required
def deployment_create(request):
    """Create new deployment and trigger background task."""
    from apps.api.rate_limiting import deployment_rate_limit
    from apps.core.utils import sanitize_deployment_name, validate_repo_url, validate_domain

    @deployment_rate_limit
    def _handle_post(request):
        name = request.POST.get('name', '').strip()
        repo_url = request.POST.get('repo_url', '').strip()
        branch = request.POST.get('branch', 'main').strip()
        domain = request.POST.get('domain', '').strip()

        # Docker options
        use_docker = request.POST.get('use_docker') == 'on'
        auto_generate_dockerfile = request.POST.get('auto_generate_dockerfile') == 'on'
        dockerfile_path = request.POST.get('dockerfile_path', 'Dockerfile').strip()
        docker_network_mode = request.POST.get('docker_network_mode', 'bridge').strip()

        # Validation
        if not name:
            messages.error(request, "Deployment name is required.")
            return redirect('deployments:deployment_list')

        if not repo_url:
            messages.error(request, "Repository URL is required.")
            return redirect('deployments:deployment_list')

        # Sanitize and validate name
        try:
            sanitized_name = sanitize_deployment_name(name)
        except ValueError as e:
            messages.error(request, f"Invalid deployment name: {e}")
            return redirect('deployments:deployment_list')

        # Check if name already exists
        if ApplicationDeployment.objects.filter(name=sanitized_name).exists():
            messages.error(request, f"Deployment '{sanitized_name}' already exists.")
            return redirect('deployments:deployment_list')

        # Validate repository URL
        if not validate_repo_url(repo_url):
            messages.error(request, "Invalid repository URL. Only GitHub repositories are supported.")
            return redirect('deployments:deployment_list')

        # Validate domain if provided
        if domain and not validate_domain(domain):
            messages.error(request, "Invalid domain name format.")
            return redirect('deployments:deployment_list')

        # Create deployment
        try:
            deployment = ApplicationDeployment.objects.create(
                name=sanitized_name,
                repo_url=repo_url,
                branch=branch or 'main',
                domain=domain,
                deployed_by=request.user,
                use_docker=use_docker,
                auto_generate_dockerfile=auto_generate_dockerfile,
                dockerfile_path=dockerfile_path if use_docker else 'Dockerfile',
                docker_network_mode=docker_network_mode if use_docker else 'bridge'
            )

            # Ensure Celery worker is running (non-interactive)
            from ..shared import ServiceManager
            ServiceManager().ensure_celery_running()

            # Queue deployment task via background processor
            from apps.services.background import get_background_processor
            processor = get_background_processor()
            processor.submit('apps.deployments.tasks.application.deploy_application', deployment.id)

            messages.success(request, f"Deployment '{sanitized_name}' created and queued successfully.")
            return redirect('deployments:deployment_detail', pk=deployment.id)

        except Exception as e:
            messages.error(request, f"Failed to create deployment: {str(e)}")
            return redirect('deployments:deployment_list')

    if request.method == 'POST':
        return _handle_post(request)

    # GET request - show form with GitHub repositories
    from apps.core.integrations.services import GitHubIntegrationService

    github_connected = False
    github_repos = []

    # Check if user has GitHub connection
    github_service = GitHubIntegrationService()
    if github_service.get_connection(request.user):
        github_connected = True
        github_repos = github_service.list_repositories(request.user) or []

    # Core services status (read-only)
    from ..shared import ServiceManager
    core_status = ServiceManager().get_core_services_status()

    return render(request, 'deployments/create.html', {
        'github_connected': github_connected,
        'github_repos': github_repos,
        'core_status': core_status,
    })


@login_required
def restart_core_service(request, service_name):
    """Restart a core prerequisite service (Redis, PostgreSQL, Nginx, Celery)."""
    from django.http import JsonResponse
    from ..shared import ServiceManager
    
    # Validate service name
    valid_services = ['redis', 'postgresql', 'nginx', 'celery', 'celerybeat']
    if service_name not in valid_services:
        return JsonResponse({
            'success': False,
            'error': f'Invalid service name. Valid services: {", ".join(valid_services)}'
        }, status=400)
    
    service_manager = ServiceManager()
    success, message = service_manager.restart_core_service(service_name)
    
    if success:
        return JsonResponse({
            'success': True,
            'message': f'Service {service_name} restarted successfully',
            'service': service_name
        })
    else:
        # Check if this is a systemd/environment-related error
        if 'systemd' in message.lower() and ('not available' in message.lower() or 'container' in message.lower()):
            # Development environment - systemd not available
            return JsonResponse({
                'success': False,
                'error': f'Service restart is not available in this environment: {message}',
                'service': service_name,
                'environment': 'development',
                'suggestion': 'Service restart functionality requires systemd and appropriate sudo privileges. In development environments, you may need to restart services manually using docker commands or system administration tools.'
            }, status=500)
        elif 'sudo' in message.lower() or 'permission' in message.lower():
            detailed_message = f"""
                Failed to restart {service_name}: {message}
                
                To fix this issue, you need to configure sudo privileges for the web server user.
                
                Solution 1: Add the web server user to the sudoers file with passwordless systemctl access:
                Run: sudo visudo
                Add line: www-data ALL=(ALL) NOPASSWD: /bin/systemctl
                
                Solution 2: Configure specific service management permissions:
                Add line: www-data ALL=(ALL) NOPASSWD: /bin/systemctl start {service_name}.*, /bin/systemctl stop {service_name}.*, /bin/systemctl restart {service_name}.*
                
                Solution 3: Ensure services can be managed without sudo (not recommended for production).
                
                After making changes, restart the web server and try again.
            """
            return JsonResponse({
                'success': False,
                'error': detailed_message.strip(),
                'service': service_name,
                'sudo_required': True
            }, status=500)
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to restart {service_name}: {message}',
                'service': service_name
            }, status=500)


@login_required
def enable_service_health_monitoring(request):
    """Enable automatic health monitoring for core services."""
    try:
        service_manager = ServiceManager()
        service_manager.start_health_monitoring()
        
        return JsonResponse({
            'success': True,
            'message': 'Health monitoring enabled successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to enable health monitoring: {str(e)}'
        })


@login_required
def disable_service_health_monitoring(request):
    """Disable automatic health monitoring for core services."""
    try:
        service_manager = ServiceManager()
        service_manager.stop_health_monitoring()
        
        return JsonResponse({
            'success': True,
            'message': 'Health monitoring disabled successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to disable health monitoring: {str(e)}'
        })


@login_required
def set_service_auto_restart(request, service_name):
    """Enable or disable auto-restart for a specific service."""
    try:
        enabled = request.POST.get('enabled', 'true').lower() == 'true'
        
        from django.core.cache import cache
        cache.set(f'service_auto_restart_{service_name}', enabled)
        
        return JsonResponse({
            'success': True,
            'message': f'Auto-restart {"enabled" if enabled else "disabled"} for {service_name}',
            'service': service_name,
            'enabled': enabled
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to set auto-restart: {str(e)}',
            'service': service_name
        })


@login_required
def get_service_health_history(request, service_name):
    """Get health history and failure statistics for a service."""
    try:
        from django.core.cache import cache
        
        failures = cache.get(f'service_failures_{service_name}', 0)
        last_failure = cache.get(f'service_last_failure_{service_name}')
        auto_restart_enabled = cache.get(f'service_auto_restart_{service_name}', True)
        
        # Get current status
        service_manager = ServiceManager()
        detailed_status = service_manager.get_core_services_status_detailed()
        current_status = detailed_status.get(service_name, {})
        
        return JsonResponse({
            'success': True,
            'service': service_name,
            'health_history': {
                'consecutive_failures': failures,
                'last_failure_time': last_failure,
                'auto_restart_enabled': auto_restart_enabled,
                'current_status': current_status.get('status', 'unknown'),
                'fallback_available': service_name in service_manager._fallback_configs
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to get health history: {str(e)}',
            'service': service_name
        })


@login_required
def get_core_services_status_detailed(request):
    """Get detailed status of all core services with restart options."""
    from django.http import JsonResponse
    from ..shared import ServiceManager
    
    service_manager = ServiceManager()
    core_status = service_manager.get_core_services_status_detailed()
    
    return JsonResponse({
        'success': True,
        'services': core_status
    })


@login_required
def dashboard(request):
    """Main dashboard view with comprehensive statistics."""
    from apps.databases.models import Database
    from apps.api.models import APIToken
    from django.db.models import Count
    from django.utils import timezone

    deployments = BaseDeployment.objects.all().order_by('-created_at')[:10]

    # Deployment stats
    deployment_stats = {
        'total': BaseDeployment.objects.count(),
        'running': BaseDeployment.objects.filter(status='running').count(),
        'stopped': BaseDeployment.objects.filter(status='stopped').count(),
        'failed': BaseDeployment.objects.filter(status='failed').count(),
        'pending': BaseDeployment.objects.filter(status='pending').count(),
    }

    # Database stats
    database_stats = {
        'total': Database.objects.count(),
        'with_deployment': Database.objects.exclude(deployment__isnull=True).count(),
        'standalone': Database.objects.filter(deployment__isnull=True).count(),
    }

    # API token stats
    token_stats = {
        'total': APIToken.objects.count(),
        'active': APIToken.objects.filter(is_active=True).count(),
        'expired': APIToken.objects.filter(expires_at__lt=timezone.now()).count(),
    }

    # Project type breakdown
    project_types = ApplicationDeployment.objects.values('project_type').annotate(
        count=Count('id')
    )

    # Recent activity (last 7 days)
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    recent_deployments = BaseDeployment.objects.filter(
        created_at__gte=seven_days_ago
    ).count()

    return render(request, 'dashboard.html', {
        'deployments': deployments,
        'deployment_stats': deployment_stats,
        'database_stats': database_stats,
        'token_stats': token_stats,
        'project_types': project_types,
        'recent_deployments': recent_deployments,
    })


@login_required
def deployment_start(request, pk):
    """Start a deployment service."""
    deployment = get_object_or_404(BaseDeployment, pk=pk)

    from ..shared import ServiceManager

    service_manager = ServiceManager()
    success, message = service_manager.start_service(deployment)

    if success:
        messages.success(request, f'Deployment {deployment.name} started successfully')
    else:
        messages.error(request, f'Failed to start deployment: {message}')

    return redirect('deployments:deployment_detail', pk=pk)


@login_required
def deployment_stop(request, pk):
    """Stop a deployment service."""
    deployment = get_object_or_404(BaseDeployment, pk=pk)

    from ..shared import ServiceManager

    service_manager = ServiceManager()
    success, message = service_manager.stop_service(deployment)

    if success:
        messages.success(request, f'Deployment {deployment.name} stopped successfully')
    else:
        messages.error(request, f'Failed to stop deployment: {message}')

    return redirect('deployments:deployment_detail', pk=pk)


@login_required
def deployment_restart(request, pk):
    """Restart a deployment service."""
    deployment = get_object_or_404(BaseDeployment, pk=pk)

    from ..shared import ServiceManager

    service_manager = ServiceManager()
    success, message = service_manager.restart_service(deployment)

    if success:
        messages.success(request, f'Deployment {deployment.name} restarted successfully')
    else:
        messages.error(request, f'Failed to restart deployment: {message}')

    return redirect('deployments:deployment_detail', pk=pk)


@login_required
def deployment_delete(request, pk):
    """Delete a deployment and all its resources."""
    try:
        deployment = BaseDeployment.objects.get(pk=pk)
    except BaseDeployment.DoesNotExist:
        messages.error(request, f'Deployment with ID {pk} not found. It may have already been deleted.')
        return redirect('deployments:deployment_list')

    if request.method == 'POST':
        deployment_name = deployment.name

        # Handle different deployment types
        if hasattr(deployment, 'applicationdeployment'):
            # Application deployment - use background task
            from ..shared import ServiceManager
            ServiceManager().ensure_celery_running()

            from apps.services.background import get_background_processor
            processor = get_background_processor()
            processor.submit('apps.deployments.tasks.application.delete_deployment', deployment.id)

            messages.success(
                request,
                f'Deployment {deployment_name} deletion queued'
            )

        elif hasattr(deployment, 'llmdeployment'):
            # LLM deployment - delete directly (no complex services)
            try:
                # Remove deployment files
                from ..services import LLMDeploymentService
                llm_service = LLMDeploymentService()
                deployment_path = llm_service.get_deployment_path(deployment)

                if deployment_path.exists():
                    import shutil
                    shutil.rmtree(deployment_path)

                # Delete from database
                deployment.delete()

                messages.success(
                    request,
                    f'LLM deployment {deployment_name} deleted successfully'
                )

            except Exception as e:
                messages.error(
                    request,
                    f'Failed to delete LLM deployment: {str(e)}'
                )

        else:
            messages.error(
                request,
                f'Unknown deployment type for {deployment_name}'
            )

        return redirect('deployments:deployment_list')

    return render(request, 'deployments/delete_confirm.html', {
        'deployment': deployment
    })


@login_required
def deployment_env_update(request, pk):
    """Update deployment environment variables."""
    import json
    from django.http import JsonResponse

    deployment = get_object_or_404(BaseDeployment, pk=pk)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            env_vars = data.get('env_vars', {})

            # Update environment variables
            deployment.env_vars = env_vars
            deployment.save()

            # Restart service to apply changes
            from ..shared import ServiceManager
            service_manager = ServiceManager()
            service_manager.restart_service(deployment)

            messages.success(request, 'Environment variables updated successfully. Service restarted.')
            return JsonResponse({'success': True, 'message': 'Environment variables updated'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def deployment_validate(request, pk):
    """Validate deployment project structure and requirements."""
    import json
    from django.http import JsonResponse
    from ..shared.validators import validate_project
    from ..services import DeploymentService

    deployment = get_object_or_404(ApplicationDeployment, pk=pk)

    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'success': False,
            'error': 'Repository not cloned yet. Please wait for deployment to complete.'
        }, status=400)

    all_passed, results = validate_project(repo_path)

    return JsonResponse({
        'success': True,
        'all_passed': all_passed,
        'results': [
            {
                'passed': r.passed,
                'message': r.message,
                'level': r.level,
                'details': r.details
            }
            for r in results
        ]
    })


@login_required
def deployment_env_wizard(request, pk):
    """Get .env wizard data for deployment."""
    import json
    from django.http import JsonResponse
    from apps.core.managers.env_manager import EnvParser
    from ..services import DeploymentService

    deployment = get_object_or_404(ApplicationDeployment, pk=pk)

    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'available': False,
            'error': 'Repository not cloned yet'
        })

    # Check for .env.example
    env_example = repo_path / '.env.example'
    if not env_example.exists():
        return JsonResponse({
            'available': False,
            'error': 'No .env.example file found in repository'
        })

    try:
        # Parse .env.example
        parser = EnvParser(env_example)
        variables = parser.parse()

        # Check if .env exists
        env_file = repo_path / '.env'
        has_env_file = env_file.exists()

        # If .env exists, load current values
        current_values = {}
        if has_env_file:
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
                        current_values[key.strip()] = value

        # Build wizard data
        wizard_variables = []
        for var in variables:
            wizard_variables.append({
                'key': var.key,
                'value': current_values.get(var.key, var.value or ''),
                'type': var.var_type.value,
                'required': var.required,
                'comment': var.comment,
                'example_value': var.example_value
            })

        return JsonResponse({
            'available': True,
            'has_env_file': has_env_file,
            'variables': wizard_variables,
            'total': len(wizard_variables),
            'required': sum(1 for v in variables if v.required)
        })

    except Exception as e:
        return JsonResponse({
            'available': False,
            'error': str(e)
        }, status=500)


@login_required
def deployment_env_manage(request, pk):
    """Manage environment variables for a deployment."""
    from ..services import DeploymentService

    deployment = get_object_or_404(ApplicationDeployment, pk=pk)
    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    # Check if repository exists
    repo_exists = repo_path.exists()
    env_file_exists = False
    env_example_exists = False
    env_vars = {}

    if repo_exists:
        env_file = repo_path / '.env'
        env_example = repo_path / '.env.example'

        env_file_exists = env_file.exists()
        env_example_exists = env_example.exists()

        # Load current env vars if file exists
        if env_file_exists:
            try:
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
            except Exception as e:
                messages.error(request, f'Error reading .env file: {e}')

    return render(request, 'deployments/env_manage.html', {
        'deployment': deployment,
        'repo_exists': repo_exists,
        'env_file_exists': env_file_exists,
        'env_example_exists': env_example_exists,
        'env_vars': env_vars,
        'env_vars_count': len(env_vars),
    })


@login_required
def deployment_files(request, pk):
    """Browse deployment files."""
    import json
    from django.http import JsonResponse
    from ..services import DeploymentService
    import os

    deployment = get_object_or_404(ApplicationDeployment, pk=pk)
    service = DeploymentService()
    repo_path = service.get_repo_path(deployment)

    if not repo_path.exists():
        return JsonResponse({
            'success': False,
            'error': 'Repository not cloned yet'
        }, status=400)

    # Get path parameter (relative to repo root)
    rel_path = request.GET.get('path', '')

    # Security: prevent directory traversal
    if '..' in rel_path or rel_path.startswith('/'):
        return JsonResponse({
            'success': False,
            'error': 'Invalid path'
        }, status=400)

    target_path = repo_path / rel_path if rel_path else repo_path

    if not target_path.exists():
        return JsonResponse({
            'success': False,
            'error': 'Path not found'
        }, status=404)

    # If it's a file, return file content
    if target_path.is_file():
        try:
            # Check file size (limit to 1MB)
            file_size = target_path.stat().st_size
            if file_size > 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': 'File too large to display (>1MB)'
                }, status=400)

            # Try to read as text
            try:
                content = target_path.read_text()
                return JsonResponse({
                    'success': True,
                    'type': 'file',
                    'path': rel_path,
                    'content': content,
                    'size': file_size,
                    'name': target_path.name
                })
            except UnicodeDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'Binary file - cannot display'
                }, status=400)

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    # If it's a directory, list contents
    elif target_path.is_dir():
        try:
            items = []

            for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                # Skip hidden files and common ignore patterns
                if item.name.startswith('.') and item.name not in ['.env.example', '.gitignore']:
                    continue
                if item.name in ['__pycache__', 'node_modules', '.git', 'venv', '.venv']:
                    continue

                item_rel_path = str(item.relative_to(repo_path))

                items.append({
                    'name': item.name,
                    'path': item_rel_path,
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': item.stat().st_size if item.is_file() else 0
                })

            return JsonResponse({
                'success': True,
                'type': 'directory',
                'path': rel_path,
                'items': items
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@login_required
def deployment_editor(request, pk):
    """Open code editor for deployment."""
    deployment = get_object_or_404(ApplicationDeployment, pk=pk)
    return render(request, 'deployments/editor.html', {
        'deployment': deployment
    })


@login_required
def deployment_health_check(request, pk):
    """Run health check on deployment and return results."""
    from django.http import JsonResponse
    from .health_check import perform_health_check

    deployment = get_object_or_404(BaseDeployment, pk=pk)

    try:
        # Run health check (without auto-restart for manual checks)
        results = perform_health_check(deployment, auto_restart=False)

        return JsonResponse({
            'success': True,
            'results': results
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def deployment_health_history(request, pk):
    """Get health check history for deployment."""
    from django.http import JsonResponse
    from .models import HealthCheckRecord

    deployment = get_object_or_404(BaseDeployment, pk=pk)

    # Get limit from query parameters (default 24)
    limit = int(request.GET.get('limit', 24))

    # Get recent health check records
    records = deployment.health_check_records.all()[:limit]

    # Build response
    history = []
    for record in records:
        history.append({
            'id': record.id,
            'timestamp': record.created_at.isoformat(),
            'overall_healthy': record.overall_healthy,
            'process_healthy': record.process_healthy,
            'http_healthy': record.http_healthy,
            'resources_healthy': record.resources_healthy,
            'disk_healthy': record.disk_healthy,
            'cpu_percent': record.cpu_percent,
            'memory_mb': record.memory_mb,
            'disk_free_gb': record.disk_free_gb,
            'response_time_ms': record.response_time_ms,
            'http_status_code': record.http_status_code,
            'auto_restart_attempted': record.auto_restart_attempted,
        })

    return JsonResponse({
        'success': True,
        'count': len(history),
        'history': history
    })


@login_required
def deployment_monitoring(request, pk):
    """Monitoring dashboard for deployment."""
    from .models import HealthCheckRecord
    from django.utils import timezone
    from datetime import timedelta

    deployment = get_object_or_404(BaseDeployment, pk=pk)

    # Get latest health check
    latest_health_check = deployment.health_check_records.first()

    # Get health check history (last 24 hours)
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    recent_checks = deployment.health_check_records.filter(
        created_at__gte=twenty_four_hours_ago
    ).order_by('created_at')

    # Calculate stats
    total_checks = recent_checks.count()
    failed_checks = recent_checks.filter(overall_healthy=False).count()
    uptime_percentage = ((total_checks - failed_checks) / total_checks * 100) if total_checks > 0 else 0

    # Get average metrics
    avg_cpu = None
    avg_memory = None
    avg_response_time = None

    if total_checks > 0:
        cpu_values = [r.cpu_percent for r in recent_checks if r.cpu_percent is not None]
        memory_values = [r.memory_mb for r in recent_checks if r.memory_mb is not None]
        response_times = [r.response_time_ms for r in recent_checks if r.response_time_ms is not None]

        if cpu_values:
            avg_cpu = sum(cpu_values) / len(cpu_values)
        if memory_values:
            avg_memory = sum(memory_values) / len(memory_values)
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)

    return render(request, 'deployments/monitoring.html', {
        'deployment': deployment,
        'latest_health_check': latest_health_check,
        'recent_checks': recent_checks,
        'total_checks': total_checks,
        'failed_checks': failed_checks,
        'uptime_percentage': round(uptime_percentage, 2),
        'avg_cpu': round(avg_cpu, 2) if avg_cpu else None,
        'avg_memory': round(avg_memory, 2) if avg_memory else None,
        'avg_response_time': round(avg_response_time, 2) if avg_response_time else None,
    })


@login_required
def github_repo_branches(request):
    """AJAX endpoint to fetch branches for a GitHub repository."""
    from django.http import JsonResponse
    from apps.core.integrations.services import GitHubIntegrationService

    repo_full_name = request.GET.get('repo')

    if not repo_full_name:
        return JsonResponse({
            'success': False,
            'error': 'Repository name is required'
        }, status=400)

    # Check if user has GitHub connection
    github_service = GitHubIntegrationService()
    if not github_service.get_connection(request.user):
        return JsonResponse({
            'success': False,
            'error': 'GitHub not connected'
        }, status=401)

    # Fetch branches
    branches = github_service.list_branches(request.user, repo_full_name)

    if branches is None:
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch branches'
        }, status=500)

    return JsonResponse({
        'success': True,
        'branches': [branch['name'] for branch in branches]
    })
