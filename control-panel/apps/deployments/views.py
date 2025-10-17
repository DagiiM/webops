"""
Views for Deployments app.

Reference: CLAUDE.md "Django App Structure" section
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Deployment, DeploymentLog


@login_required
def deployment_list(request):
    """List all deployments."""
    deployments = Deployment.objects.all()
    return render(request, 'deployments/list.html', {
        'deployments': deployments
    })


@login_required
def deployment_detail(request, pk):
    """Show deployment details and logs."""
    deployment = get_object_or_404(Deployment, pk=pk)
    # Redirect LLM deployments to their dedicated detail view
    if deployment.project_type == Deployment.ProjectType.LLM:
        return redirect('deployments:llm_detail', pk=pk)
    logs = deployment.logs.all()[:100]  # Last 100 logs

    # Get service status
    from .service_manager import ServiceManager
    service_manager = ServiceManager()
    service_status = service_manager.get_service_status(deployment)

    return render(request, 'deployments/detail.html', {
        'deployment': deployment,
        'logs': logs,
        'service_status': service_status
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
        if Deployment.objects.filter(name=sanitized_name).exists():
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
            from .services import DeploymentService
            from .tasks import deploy_application

            deployment = Deployment.objects.create(
                name=sanitized_name,
                repo_url=repo_url,
                branch=branch or 'main',
                domain=domain,
                deployed_by=request.user
            )

            # Ensure Celery worker is running (non-interactive)
            from .service_manager import ServiceManager
            ServiceManager().ensure_celery_running()

            # Queue deployment task
            deploy_application.delay(deployment.id)

            messages.success(request, f"Deployment '{sanitized_name}' created and queued successfully.")
            return redirect('deployments:deployment_detail', pk=deployment.id)

        except Exception as e:
            messages.error(request, f"Failed to create deployment: {str(e)}")
            return redirect('deployments:deployment_list')

    if request.method == 'POST':
        return _handle_post(request)

    # GET request - show form with GitHub repositories
    from apps.core.integration_services import GitHubIntegrationService

    github_connected = False
    github_repos = []

    # Check if user has GitHub connection
    github_service = GitHubIntegrationService()
    if github_service.get_connection(request.user):
        github_connected = True
        github_repos = github_service.list_repositories(request.user) or []

    # Core services status (read-only)
    from .service_manager import ServiceManager
    core_status = ServiceManager().get_core_services_status()

    return render(request, 'deployments/create.html', {
        'github_connected': github_connected,
        'github_repos': github_repos,
        'core_status': core_status,
    })


@login_required
def dashboard(request):
    """Main dashboard view with comprehensive statistics."""
    from apps.databases.models import Database
    from apps.api.models import APIToken
    from django.db.models import Count
    from django.utils import timezone

    deployments = Deployment.objects.all().order_by('-created_at')[:10]

    # Deployment stats
    deployment_stats = {
        'total': Deployment.objects.count(),
        'running': Deployment.objects.filter(status=Deployment.Status.RUNNING).count(),
        'stopped': Deployment.objects.filter(status=Deployment.Status.STOPPED).count(),
        'failed': Deployment.objects.filter(status=Deployment.Status.FAILED).count(),
        'pending': Deployment.objects.filter(status=Deployment.Status.PENDING).count(),
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
    project_types = Deployment.objects.values('project_type').annotate(
        count=Count('id')
    )

    # Recent activity (last 7 days)
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    recent_deployments = Deployment.objects.filter(
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
    deployment = get_object_or_404(Deployment, pk=pk)

    from .service_manager import ServiceManager

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
    deployment = get_object_or_404(Deployment, pk=pk)

    from .service_manager import ServiceManager

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
    deployment = get_object_or_404(Deployment, pk=pk)

    from .service_manager import ServiceManager

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
    deployment = get_object_or_404(Deployment, pk=pk)

    if request.method == 'POST':
        from .tasks import delete_deployment

        deployment_name = deployment.name

        # Ensure Celery worker is running (non-interactive)
        from .service_manager import ServiceManager
        ServiceManager().ensure_celery_running()

        # Trigger background deletion task
        delete_deployment.delay(deployment.id)

        messages.success(
            request,
            f'Deployment {deployment_name} deletion queued'
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

    deployment = get_object_or_404(Deployment, pk=pk)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            env_vars = data.get('env_vars', {})

            # Update environment variables
            deployment.env_vars = env_vars
            deployment.save()

            # Restart service to apply changes
            from .service_manager import ServiceManager
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
    from .validators import validate_project
    from .services import DeploymentService

    deployment = get_object_or_404(Deployment, pk=pk)

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
    from apps.core.env_manager import EnvParser
    from .services import DeploymentService

    deployment = get_object_or_404(Deployment, pk=pk)

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
    from .services import DeploymentService

    deployment = get_object_or_404(Deployment, pk=pk)
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
    from .services import DeploymentService
    import os

    deployment = get_object_or_404(Deployment, pk=pk)
    # Block file browsing for LLM deployments
    if deployment.project_type == Deployment.ProjectType.LLM:
        return JsonResponse({
            'success': False,
            'error': 'File browsing is not available for LLM deployments'
        }, status=400)
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
    deployment = get_object_or_404(Deployment, pk=pk)
    # Prevent LLM deployments from accessing the code editor
    if deployment.project_type == Deployment.ProjectType.LLM:
        messages.error(request, 'Code editor is not available for LLM deployments.')
        return redirect('deployments:llm_detail', pk=pk)
    return render(request, 'deployments/editor.html', {
        'deployment': deployment
    })


@login_required
def deployment_health_check(request, pk):
    """Run health check on deployment and return results."""
    from django.http import JsonResponse
    from .health_check import perform_health_check

    deployment = get_object_or_404(Deployment, pk=pk)

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

    deployment = get_object_or_404(Deployment, pk=pk)

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

    deployment = get_object_or_404(Deployment, pk=pk)

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
    from apps.core.integration_services import GitHubIntegrationService

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