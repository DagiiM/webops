"""
Security decorators for WebOps Control Panel.

This module provides reusable security decorators for views and API endpoints.
All decorators follow the minimal frameworks principle using Django built-ins only.
"""

from functools import wraps
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


def require_resource_ownership(model_class, ownership_field='user', lookup_field='pk'):
    """
    Decorator to ensure the current user owns the requested resource.

    Usage:
        @require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def deployment_detail(request, pk):
            deployment = get_object_or_404(ApplicationDeployment, pk=pk)
            ...

    Args:
        model_class: The Django model class to check ownership for
        ownership_field: The field name that references the owner (default: 'user')
        lookup_field: The field name used for lookup (default: 'pk')

    Raises:
        PermissionDenied: If user doesn't own the resource
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Extract the lookup value from kwargs
            lookup_value = kwargs.get(lookup_field)
            if not lookup_value:
                raise PermissionDenied("Resource identifier not provided")

            # Build the ownership filter
            ownership_filter = {
                lookup_field: lookup_value,
                ownership_field: request.user
            }

            # Check if resource exists and user owns it
            if not model_class.objects.filter(**ownership_filter).exists():
                # Resource either doesn't exist or user doesn't own it
                # Return same error for security (don't reveal if resource exists)
                raise PermissionDenied("You do not have permission to access this resource")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_related_ownership(model_class, relation_path, lookup_field='pk'):
    """
    Decorator for resources owned through a foreign key relationship.

    Usage:
        @require_related_ownership(Database, relation_path='deployment__deployed_by')
        def database_detail(request, pk):
            database = get_object_or_404(Database, pk=pk)
            ...

    Args:
        model_class: The Django model class to check ownership for
        relation_path: The path to the user field (e.g., 'deployment__deployed_by')
        lookup_field: The field name used for lookup (default: 'pk')

    Raises:
        PermissionDenied: If user doesn't own the related resource
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Extract the lookup value from kwargs
            lookup_value = kwargs.get(lookup_field)
            if not lookup_value:
                raise PermissionDenied("Resource identifier not provided")

            # Build the ownership filter with relation path
            ownership_filter = {
                lookup_field: lookup_value,
                relation_path: request.user
            }

            # Check if resource exists and user owns it through relation
            if not model_class.objects.filter(**ownership_filter).exists():
                raise PermissionDenied("You do not have permission to access this resource")

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def api_require_ownership(model_class, ownership_field='user', lookup_field='pk'):
    """
    Decorator for API endpoints that returns JSON error responses.

    Usage:
        @api_require_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def api_deployment_detail(request, pk):
            ...

    Args:
        model_class: The Django model class to check ownership for
        ownership_field: The field name that references the owner (default: 'user')
        lookup_field: The field name used for lookup (default: 'pk')

    Returns:
        JSON error response with 403 status if unauthorized
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Extract the lookup value from kwargs
            lookup_value = kwargs.get(lookup_field)
            if not lookup_value:
                return JsonResponse({
                    'error': 'Resource identifier not provided',
                    'status': 'error'
                }, status=400)

            # Build the ownership filter
            ownership_filter = {
                lookup_field: lookup_value,
                ownership_field: request.user
            }

            # Check if resource exists and user owns it
            if not model_class.objects.filter(**ownership_filter).exists():
                return JsonResponse({
                    'error': 'You do not have permission to access this resource',
                    'status': 'error'
                }, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def superuser_required(view_func):
    """
    Decorator to restrict access to superusers only.

    Usage:
        @superuser_required
        def admin_panel(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("This action requires superuser privileges")
        return view_func(request, *args, **kwargs)
    return wrapper
