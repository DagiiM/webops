"""
Views for Databases app.

"Django App Structure" section
"""

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
        print(f"User authenticated: {request.user.is_authenticated}")
        print(f"User: {request.user}")
        print(f"Request method: {request.method}")
        print(f"Request headers: {dict(request.headers)}")
        if request.method == 'POST':
            print(f"POST data: {dict(request.POST)}")
            print(f"CSRF token from POST: {request.POST.get('csrfmiddlewaretoken', 'NOT_FOUND')}")
            print(f"Session CSRF token: {request.META.get('CSRF_COOKIE', 'NOT_FOUND')}")
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
                
                print(f"Database type: {db_type}, all_installed: {all_installed}, missing_deps: {missing_deps}")
                
                if not all_installed:
                    # Return form invalid with dependency error
                    messages.error(
                        self.request,
                        f'Cannot create database: Missing dependencies: {", ".join(missing_deps)}. '
                        'Please install dependencies first.'
                    )
                    print(f"Form invalid due to missing dependencies: {missing_deps}")
                    return self.form_invalid(form)
                    
            except ValueError as e:
                messages.error(self.request, f'Invalid database type: {db_type}')
                print(f"Invalid database type error: {e}")
                return self.form_invalid(form)
            except Exception as e:
                messages.error(self.request, f'Error checking dependencies: {str(e)}')
                print(f"Error checking dependencies: {e}")
                return self.form_invalid(form)
        
        try:
            # Encrypt sensitive fields before saving
            if form.cleaned_data.get('password'):
                form.instance.password = encrypt_password(form.cleaned_data['password'])
            if form.cleaned_data.get('api_key'):
                form.instance.api_key = encrypt_password(form.cleaned_data['api_key'])
                
            print(f"Attempting to save database: {form.instance.name}")
            result = super().form_valid(form)
            print(f"Database created successfully: {form.instance.name}")
            messages.success(self.request, f'Database {form.instance.name} created successfully!')
            return result
        except Exception as e:
            messages.error(self.request, f'Error creating database: {str(e)}')
            print(f"Error creating database: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        print(f"Form invalid. Errors: {form.errors}")
        print(f"Form non-field errors: {form.non_field_errors()}")
        print(f"Form cleaned data: {form.cleaned_data}")
        messages.error(self.request, f'Please correct the errors below: {form.errors}')
        return super().form_invalid(form)


@login_required
def database_create_legacy(request):
    """Legacy database creation for PostgreSQL only."""
    if request.method == 'POST':
        name = request.POST.get('name')
        username = request.POST.get('username')

        if name and username:
            from apps.core.utils import generate_password, encrypt_password

            # Generate password
            password = generate_password(32)

            # Create database
            db_service = DatabaseService()
            success, message = db_service.create_user(username, password)

            if success:
                success, message = db_service.create_database(name, owner=username)

                if success:
                    # Save to our database
                    encrypted_password = encrypt_password(password)
                    Database.objects.create(
                        name=name,
                        username=username,
                        password=encrypted_password,
                        host='localhost',
                        port=5432
                    )

                    messages.success(request, f'Database {name} created successfully!')
                    return redirect('database_list')
                else:
                    messages.error(request, f'Failed to create database: {message}')
            else:
                messages.error(request, f'Failed to create user: {message}')
        else:
            messages.error(request, 'Name and username are required')

    return render(request, 'databases/create.html')


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
