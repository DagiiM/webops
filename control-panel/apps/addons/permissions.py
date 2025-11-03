"""
Permission system for addon management.

Provides fine-grained permissions for addon operations:
- View addons
- Install/uninstall system addons
- Configure system addons
- Enable/disable application addons
- Manage addon settings
"""

from functools import wraps
from typing import Callable

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpRequest

from .models import SystemAddon, Addon


# Permission codenames
class AddonPermissions:
    """Centralized permission codenames for addon operations."""

    # View permissions
    VIEW_ADDON = 'view_addon'
    VIEW_SYSTEM_ADDON = 'view_systemaddon'

    # System addon permissions
    INSTALL_SYSTEM_ADDON = 'install_systemaddon'
    UNINSTALL_SYSTEM_ADDON = 'uninstall_systemaddon'
    CONFIGURE_SYSTEM_ADDON = 'configure_systemaddon'

    # Application addon permissions
    MANAGE_ADDON = 'manage_addon'
    CHANGE_ADDON = 'change_addon'

    # Admin permissions
    DELETE_ADDON = 'delete_addon'
    DELETE_SYSTEM_ADDON = 'delete_systemaddon'


def create_addon_permissions():
    """
    Create custom permissions for addon management.

    Should be called in a migration or management command.
    """
    # Get content types
    addon_ct = ContentType.objects.get_for_model(Addon)
    system_addon_ct = ContentType.objects.get_for_model(SystemAddon)

    # Define custom permissions
    permissions = [
        # System addon permissions
        (system_addon_ct, 'install_systemaddon', 'Can install system addons'),
        (system_addon_ct, 'uninstall_systemaddon', 'Can uninstall system addons'),
        (system_addon_ct, 'configure_systemaddon', 'Can configure system addons'),

        # Application addon permissions
        (addon_ct, 'manage_addon', 'Can manage application addons'),
    ]

    created_count = 0
    for content_type, codename, name in permissions:
        permission, created = Permission.objects.get_or_create(
            codename=codename,
            content_type=content_type,
            defaults={'name': name}
        )
        if created:
            created_count += 1

    return created_count


def has_addon_permission(user, permission_codename: str) -> bool:
    """
    Check if user has a specific addon permission.

    Args:
        user: Django user instance
        permission_codename: Permission code (e.g., 'install_systemaddon')

    Returns:
        bool: True if user has permission
    """
    if not user or not user.is_authenticated:
        return False

    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Staff users have all view permissions
    if user.is_staff and permission_codename.startswith('view_'):
        return True

    # Check specific permission
    if permission_codename in ['install_systemaddon', 'uninstall_systemaddon', 'configure_systemaddon']:
        perm_string = f'addons.{permission_codename}'
    elif permission_codename in ['manage_addon', 'change_addon', 'delete_addon']:
        perm_string = f'addons.{permission_codename}'
    else:
        perm_string = permission_codename

    return user.has_perm(perm_string)


def require_addon_permission(permission_codename: str, api: bool = False):
    """
    Decorator to require specific addon permission.

    Args:
        permission_codename: Required permission code
        api: If True, return JSON error response instead of raising exception

    Usage:
        @require_addon_permission('install_systemaddon')
        def install_addon(request, name):
            ...

        @require_addon_permission('install_systemaddon', api=True)
        def api_install_addon(request, name):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Check if user is authenticated
            if not request.user.is_authenticated:
                if api:
                    return JsonResponse(
                        {'error': 'Authentication required'},
                        status=401
                    )
                raise PermissionDenied('Authentication required')

            # Check permission
            if not has_addon_permission(request.user, permission_codename):
                permission_name = permission_codename.replace('_', ' ').title()

                if api:
                    return JsonResponse(
                        {
                            'error': f'Permission denied: {permission_name} required',
                            'required_permission': permission_codename
                        },
                        status=403
                    )
                raise PermissionDenied(f'Permission denied: {permission_name} required')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def require_superuser(api: bool = False):
    """
    Decorator to require superuser access.

    Args:
        api: If True, return JSON error response
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user.is_authenticated:
                if api:
                    return JsonResponse({'error': 'Authentication required'}, status=401)
                raise PermissionDenied('Authentication required')

            if not request.user.is_superuser:
                if api:
                    return JsonResponse({'error': 'Superuser access required'}, status=403)
                raise PermissionDenied('Superuser access required')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def can_install_addon(user) -> bool:
    """Check if user can install system addons."""
    return has_addon_permission(user, AddonPermissions.INSTALL_SYSTEM_ADDON)


def can_uninstall_addon(user) -> bool:
    """Check if user can uninstall system addons."""
    return has_addon_permission(user, AddonPermissions.UNINSTALL_SYSTEM_ADDON)


def can_configure_addon(user) -> bool:
    """Check if user can configure system addons."""
    return has_addon_permission(user, AddonPermissions.CONFIGURE_SYSTEM_ADDON)


def can_manage_app_addon(user) -> bool:
    """Check if user can manage application addons."""
    return has_addon_permission(user, AddonPermissions.MANAGE_ADDON)


def get_user_addon_permissions(user) -> dict:
    """
    Get all addon permissions for a user.

    Returns:
        dict: Permission status for all addon operations
    """
    return {
        'can_view': has_addon_permission(user, AddonPermissions.VIEW_ADDON),
        'can_view_system': has_addon_permission(user, AddonPermissions.VIEW_SYSTEM_ADDON),
        'can_install': can_install_addon(user),
        'can_uninstall': can_uninstall_addon(user),
        'can_configure': can_configure_addon(user),
        'can_manage_app': can_manage_app_addon(user),
        'is_superuser': user.is_superuser if user.is_authenticated else False,
    }
