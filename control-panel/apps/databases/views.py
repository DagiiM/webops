"""
Views for Databases app.

"Django App Structure" section
"""

import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
from .models import Database
from .services import DatabaseService
from .forms import DatabaseForm
from .adapters.factory import DatabaseFactory
from .adapters.base import DatabaseType
from .installer import DatabaseInstaller, DatabaseServiceInstaller
from apps.core.utils import decrypt_password, encrypt_password
from apps.addons.models import Addon

logger = logging.getLogger(__name__)


@login_required
def database_list(request):
    """List all databases."""
    databases = Database.objects.all()

    # Get statistics
    stats = {
        'total': databases.count(),
        'with_deployment': databases.exclude(deployment__isnull=True).count(),
        'standalone': databases.filter(deployment__isnull=True).count(),
    }

    return render(request, 'databases/list.html', {
        'databases': databases,
        'stats': stats
    })


@login_required
def database_detail(request, pk):
    """Show database details and credentials."""
    database = get_object_or_404(Database, pk=pk)

    # Decrypt password for display
    db_service = DatabaseService()
    connection_string = db_service.get_connection_string(database, decrypted=True)
    decrypted_password = decrypt_password(database.password)

    return render(request, 'databases/detail.html', {
        'database': database,
        'decrypted_password': decrypted_password,
        'connection_string': connection_string
    })


class DatabaseCreateView(LoginRequiredMixin, CreateView):
    """View for creating a new database."""
    model = Database
    form_class = DatabaseForm
    template_name = 'databases/create.html'
    success_url = '/databases/'

    def dispatch(self, request, *args, **kwargs):
        logger.debug(
            "Database create view dispatch",
            extra={
                'user_authenticated': request.user.is_authenticated,
                'user': str(request.user),
                'method': request.method,
            }
        )
        if request.method == 'POST':
            logger.debug(
                "POST request to database create",
                extra={
                    'has_csrf': bool(request.POST.get('csrfmiddlewaretoken')),
                    'db_type': request.POST.get('db_type'),
                }
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get available database types with metadata
        factory = DatabaseFactory()
        context['available_databases'] = factory.get_available_databases()

        return context

    def form_valid(self, form):
        # Check dependencies before creating database
        db_type = form.cleaned_data.get('db_type')
        if db_type:
            try:
                db_type_enum = DatabaseType(db_type)
                all_installed, missing_deps = DatabaseInstaller.check_dependencies(db_type_enum)

                logger.info(
                    "Dependency check for database creation",
                    extra={
                        'db_type': db_type,
                        'all_installed': all_installed,
                        'missing_deps': missing_deps,
                        'user_id': self.request.user.id,
                    }
                )

                if not all_installed:
                    # Return form invalid with dependency error
                    messages.error(
                        self.request,
                        f'Cannot create database: Missing dependencies: {", ".join(missing_deps)}. '
                        'Please install dependencies first.'
                    )
                    logger.warning(
                        "Database creation blocked due to missing dependencies",
                        extra={
                            'db_type': db_type,
                            'missing_deps': missing_deps,
                            'user_id': self.request.user.id,
                        }
                    )
                    return self.form_invalid(form)
                    
            except ValueError as e:
                messages.error(self.request, f'Invalid database type: {db_type}')
                logger.error(
                    "Invalid database type error",
                    exc_info=True,
                    extra={'db_type': db_type, 'user_id': self.request.user.id}
                )
                return self.form_invalid(form)
            except Exception as e:
                messages.error(self.request, f'Error checking dependencies: {str(e)}')
                logger.error(
                    "Error checking dependencies",
                    exc_info=True,
                    extra={'db_type': db_type, 'user_id': self.request.user.id}
                )
                return self.form_invalid(form)
        
        try:
            # Auto-generate password if not provided for databases that need it
            db_type = form.cleaned_data.get('db_type')
            if db_type in ['postgresql', 'mysql', 'mongodb']:
                if not form.cleaned_data.get('password'):
                    from apps.core.utils import generate_password
                    generated_password = generate_password(32)
                    form.cleaned_data['password'] = generated_password
                    form.instance.password = encrypt_password(generated_password)
                    logger.info(
                        "Auto-generated password for database",
                        extra={
                            'database_name': form.instance.name,
                            'db_type': db_type,
                            'user_id': self.request.user.id,
                        }
                    )
                else:
                    # Encrypt provided password
                    form.instance.password = encrypt_password(form.cleaned_data['password'])
            elif form.cleaned_data.get('password'):
                # Encrypt password for other database types if provided
                form.instance.password = encrypt_password(form.cleaned_data['password'])

            # Encrypt API key if provided
            if form.cleaned_data.get('api_key'):
                form.instance.api_key = encrypt_password(form.cleaned_data['api_key'])

            logger.info(
                "Attempting to save database",
                extra={
                    'database_name': form.instance.name,
                    'db_type': form.instance.db_type,
                    'user_id': self.request.user.id,
                }
            )
            result = super().form_valid(form)
            logger.info(
                "Database created successfully",
                extra={
                    'database_id': form.instance.id,
                    'database_name': form.instance.name,
                    'db_type': form.instance.db_type,
                    'user_id': self.request.user.id,
                }
            )
            messages.success(self.request, f'Database {form.instance.name} created successfully!')
            return result
        except Exception as e:
            messages.error(self.request, f'Error creating database: {str(e)}')
            logger.error(
                "Error creating database",
                exc_info=True,
                extra={
                    'database_name': form.instance.name,
                    'user_id': self.request.user.id,
                }
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.warning(
            "Database creation form invalid",
            extra={
                'errors': dict(form.errors),
                'non_field_errors': list(form.non_field_errors()),
                'user_id': self.request.user.id,
            }
        )
        messages.error(self.request, f'Please correct the errors below: {form.errors}')
        return super().form_invalid(form)


@login_required
def database_delete(request, pk):
    """Delete database."""
    database = get_object_or_404(Database, pk=pk)

    if request.method == 'POST':
        db_service = DatabaseService()
        database_name = database.name
        username = database.username

        # Delete database and user
        db_service.delete_database(database_name)
        db_service.delete_user(username)

        # Delete from our database
        database.delete()

        messages.success(request, f'Database {database_name} deleted successfully')
        return redirect('database_list')

    return render(request, 'databases/delete_confirm.html', {
        'database': database
    })


@login_required
def database_credentials_json(request, pk):
    """Get database credentials as JSON (for copy functionality)."""
    database = get_object_or_404(Database, pk=pk)

    db_service = DatabaseService()
    connection_string = db_service.get_connection_string(database, decrypted=True)
    decrypted_password = decrypt_password(database.password)

    return JsonResponse({
        'name': database.name,
        'username': database.username,
        'password': decrypted_password,
        'host': database.host,
        'port': database.port,
        'connection_string': connection_string
    })


@login_required
@require_http_methods(["GET", "POST"])
def check_dependencies(request, db_id=None):
    """Check if dependencies are installed for a database type."""
    try:
        db_type = request.GET.get('db_type') if request.method == 'GET' else request.POST.get('db_type')
        
        if not db_type and db_id:
            database = get_object_or_404(Database, pk=db_id)
            db_type = database.db_type
        
        if not db_type:
            error_response = {
                'success': False,
                'status': 'error',
                'message': 'Database type is required'
            }
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(error_response)
            else:
                messages.error(request, error_response['message'])
                return render(request, 'databases/dependencies.html', {'error': error_response['message']})
        
        # Convert string to DatabaseType enum
        try:
            db_type_enum = DatabaseType(db_type)
        except ValueError as e:
            error_response = {
                'success': False,
                'status': 'error',
                'message': f'Invalid database type: {db_type}'
            }
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(error_response)
            else:
                messages.error(request, error_response['message'])
                return render(request, 'databases/dependencies.html', {'error': error_response['message']})
        
        # Get dependency information using our installer
        dep_info = DatabaseInstaller.get_dependency_info(db_type_enum)
        
        # Get available addons for this database type
        available_addons = Addon.objects.filter(
            capabilities__contains=['database', db_type]
        )
        
        context = {
            'db_type': db_type,
            'dependencies': dep_info['dependencies'],
            'missing_deps': dep_info['missing'],
            'all_installed': dep_info['all_installed'],
            'available_addons': available_addons,
            'install_commands': dep_info['install_commands']
        }
        
        if request.method == 'POST':
            # Install missing dependencies using our installer
            install_results = DatabaseInstaller.install_dependencies(db_type_enum)
            
            for dep, result in install_results.items():
                if result['success']:
                    messages.success(request, f"Successfully installed {dep}")
                else:
                    messages.error(request, f"Failed to install {dep}: {result['error']}")
            
            # Enable selected addons
            selected_addons = request.POST.getlist('addons')
            for addon_id in selected_addons:
                try:
                    addon = Addon.objects.get(pk=addon_id)
                    if not addon.enabled:
                        addon.enabled = True
                        addon.save()
                        messages.success(request, f"Enabled addon: {addon.name}")
                except Addon.DoesNotExist:
                    messages.error(request, f"Addon not found: {addon_id}")
                except Exception as e:
                    messages.error(request, f"Error enabling addon {addon_id}: {str(e)}")
            
            context['install_results'] = install_results
            
            # Check if all dependencies are now installed
            if all(result.get('success', False) for result in install_results.values()):
                messages.success(request, "All dependencies have been installed successfully!")
                return redirect('database_create' if not db_id else 'database_detail', db_id=db_id)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Format the response to match what the frontend expects
            dependencies = []
            for dep in dep_info['dependencies']:
                dependencies.append({
                    'name': dep,
                    'installed': dep not in dep_info['missing'],
                    'description': f'Required dependency for {db_type}',
                    'install_command': dep_info['install_commands'].get(dep, f'pip install {dep}')
                })
            
            return JsonResponse({
                'success': True,
                'status': 'success',
                'dependencies': dependencies,
                'all_installed': dep_info['all_installed'],
                'missing_deps': dep_info['missing'],
                'install_command': ' '.join([dep_info['install_commands'].get(dep, f'pip install {dep}') for dep in dep_info['missing']]),
                'available_addons': [
                    {
                        'id': addon.id,
                        'name': addon.name,
                        'description': addon.description or 'No description available'
                    } for addon in available_addons
                ]
            })
        
        return render(request, 'databases/dependencies.html', context)
    except Exception as e:
        import traceback
        error_response = {
            'success': False,
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(error_response, status=500)
        else:
            messages.error(request, f"Error checking dependencies: {str(e)}")
            return render(request, 'databases/dependencies.html', {'error': str(e)})


@login_required
@require_http_methods(["POST"])
def install_dependencies_ajax(request):
    """Install dependencies via AJAX."""
    try:
        # Parse JSON body for AJAX requests
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            db_type = data.get('db_type')
            dependencies = data.get('dependencies', [])
        else:
            db_type = request.POST.get('db_type')
            dependencies = request.POST.getlist('dependencies')
        
        if not db_type:
            return JsonResponse({
                'success': False,
                'status': 'error',
                'message': 'Database type is required'
            })
        
        # Convert string to DatabaseType enum
        try:
            db_type_enum = DatabaseType(db_type)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'status': 'error',
                'message': f'Invalid database type: {db_type}'
            })
        
        # Install dependencies using our installer
        install_results = DatabaseInstaller.install_dependencies(db_type_enum)
        
        # Format the results to match what the frontend expects
        formatted_results = {}
        for dep, result in install_results.items():
            formatted_results[dep] = {
                'success': result['success'],
                'message': result.get('error') if not result['success'] else 'Successfully installed',
                'output': result.get('output', '')
            }
        
        return JsonResponse({
            'success': True,
            'status': 'success',
            'results': formatted_results
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=500)
