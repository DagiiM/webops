"""
API authentication for WebOps.

"API Design" section

This module implements token-based authentication for the REST API.
"""

from typing import Optional, Tuple
from datetime import datetime
from functools import wraps
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils import timezone
from .models import APIToken


def get_user_from_token(token_string: str) -> Optional[User]:
    """
    Get user from API token.

    Args:
        token_string: The API token string

    Returns:
        User instance if valid token, None otherwise
    """
    try:
        token = APIToken.objects.select_related('user').get(
            token=token_string,
            is_active=True
        )

        # Check if token is expired
        if token.expires_at and token.expires_at < timezone.now():
            return None

        # Update last used timestamp
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])

        return token.user

    except APIToken.DoesNotExist:
        return None


def api_authentication_required(view_func):
    """
    Decorator for API views that require authentication.

    Usage:
        @api_authentication_required
        def my_api_view(request):
            # request.user will be set
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'error': 'Authentication required',
                'message': 'Missing or invalid Authorization header'
            }, status=401)

        token = auth_header.replace('Bearer ', '')
        user = get_user_from_token(token)

        if not user:
            return JsonResponse({
                'error': 'Invalid token',
                'message': 'Token is invalid or expired'
            }, status=401)

        # Attach user to request
        request.user = user

        return view_func(request, *args, **kwargs)

    return wrapper


def validate_request_data(required_fields: list):
    """
    Decorator to validate required fields in request data.

    Args:
        required_fields: List of required field names

    Usage:
        @validate_request_data(['name', 'repo_url'])
        def create_deployment(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            import json

            try:
                data = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                return JsonResponse({
                    'error': 'Invalid JSON',
                    'message': 'Request body must be valid JSON'
                }, status=400)

            # Check required fields
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                return JsonResponse({
                    'error': 'Missing required fields',
                    'missing_fields': missing_fields
                }, status=400)

            # Attach data to request
            request.json_data = data

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator