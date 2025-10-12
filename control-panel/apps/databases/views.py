"""
Views for Databases app.

Reference: CLAUDE.md "Django App Structure" section
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Database
from .services import DatabaseService
from apps.core.utils.encryption import decrypt_password


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


@login_required
def database_create(request):
    """Create new database."""
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
