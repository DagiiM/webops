"""
Database rate limiting decorators for WebOps.

"Security Best Practices" section
"""

import logging
from functools import wraps
from typing import Callable, Optional
from django.http import JsonResponse
from django.shortcuts import render
from .middleware import get_database_rate_limiter, get_client_identifier

logger = logging.getLogger(__name__)


def database_rate_limit(operation_type: str = 'read', key_func: Optional[Callable] = None):
    """
    Decorator for applying database rate limiting to views.
    
    Args:
        operation_type: Type of operation (read, write, admin)
        key_func: Optional function to generate rate limit key (default: IP/user based)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get rate limiter for this operation type
            limiter = get_database_rate_limiter(operation_type)
            
            # Generate identifier for rate limiting
            if key_func:
                identifier = key_func(request, *args, **kwargs)
            else:
                identifier = get_client_identifier(request)
            
            # Check rate limit
            allowed, info = limiter.is_allowed(identifier)
            
            if not allowed:
                # Log rate limit violation
                logger.warning(
                    f"Database rate limit exceeded for {operation_type} operation",
                    extra={
                        'path': request.path,
                        'method': request.method,
                        'identifier': identifier,
                        'operation_type': operation_type,
                        'retry_after': info['retry_after'],
                        'view_function': view_func.__name__,
                    }
                )
                
                # Check if request expects JSON (API request)
                if (request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                    request.path.endswith('/credentials/') or
                    'dependencies' in request.path):
                    response = JsonResponse({
                        'error': 'Database rate limit exceeded',
                        'message': f'Too many {operation_type} operations. Please try again later.',
                        'retry_after': info['retry_after'],
                        'operation_type': info['operation_type'],
                        'limit': info['limit'],
                        'remaining': info['remaining'],
                        'reset': info['reset']
                    }, status=429)
                else:
                    # Return HTML page for browser requests
                    response = render(request, 'errors/429.html', {
                        'retry_after': info['retry_after'],
                        'limit': info['limit'],
                        'remaining': info['remaining'],
                        'reset': info['reset'],
                        'operation_type': info['operation_type']
                    }, status=429)
                
                # Add rate limit headers
                response['X-Database-RateLimit-Limit'] = str(info['limit'])
                response['X-Database-RateLimit-Remaining'] = str(info['remaining'])
                response['X-Database-RateLimit-Reset'] = str(info['reset'])
                response['X-Database-RateLimit-Operation'] = info['operation_type']
                response['Retry-After'] = str(info['retry_after'])
                
                return response
            
            # Store rate limit info for later use in response headers
            request._db_rate_limit_info = info
            
            # Execute the view
            response = view_func(request, *args, **kwargs)
            
            # Add rate limit headers to successful response
            if hasattr(response, '__setitem__'):  # Check if response supports headers
                response['X-Database-RateLimit-Limit'] = str(info['limit'])
                response['X-Database-RateLimit-Remaining'] = str(info['remaining'])
                response['X-Database-RateLimit-Reset'] = str(info['reset'])
                response['X-Database-RateLimit-Operation'] = info['operation_type']
            
            return response
        
        return wrapped_view
    return decorator


def database_read_rate_limit(view_func):
    """
    Decorator for database read operations (list, detail).
    """
    return database_rate_limit('read')(view_func)


def database_write_rate_limit(view_func):
    """
    Decorator for database write operations (create, update, delete).
    """
    return database_rate_limit('write')(view_func)


def database_admin_rate_limit(view_func):
    """
    Decorator for database admin operations (credentials, dependencies).
    """
    return database_rate_limit('admin')(view_func)


def database_rate_limit_by_user(operation_type: str = 'read'):
    """
    Decorator for rate limiting by authenticated user ID.
    
    Args:
        operation_type: Type of operation (read, write, admin)
    """
    def key_func(request, *args, **kwargs):
        """Generate rate limit key based on authenticated user."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user_{request.user.id}"
        return get_client_identifier(request)
    
    return database_rate_limit(operation_type, key_func)


def database_rate_limit_by_database(operation_type: str = 'read'):
    """
    Decorator for rate limiting by specific database instance.
    
    Args:
        operation_type: Type of operation (read, write, admin)
    """
    def key_func(request, *args, **kwargs):
        """Generate rate limit key based on database ID."""
        # Try to get database ID from URL parameters
        db_id = kwargs.get('pk') or kwargs.get('id')
        if db_id:
            base_identifier = get_client_identifier(request)
            return f"db_{db_id}_{base_identifier}"
        return get_client_identifier(request)
    
    return database_rate_limit(operation_type, key_func)


def database_rate_limit_by_role(operation_type: str = 'read'):
    """
    Decorator for rate limiting by user role.
    
    Different rate limits for different user roles:
    - Superusers: Higher limits
    - Staff: Medium limits
    - Regular users: Standard limits
    
    Args:
        operation_type: Type of operation (read, write, admin)
    """
    def key_func(request, *args, **kwargs):
        """Generate rate limit key based on user role."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.is_superuser:
                role = 'superuser'
            elif request.user.is_staff:
                role = 'staff'
            else:
                role = 'user'
            return f"role_{role}_{request.user.id}"
        return get_client_identifier(request)
    
    return database_rate_limit(operation_type, key_func)


def database_rate_limit_with_burst(
    operation_type: str = 'read',
    burst_multiplier: float = 2.0
):
    """
    Decorator for rate limiting with custom burst settings.
    
    Args:
        operation_type: Type of operation (read, write, admin)
        burst_multiplier: Multiplier for burst requests (default: 2x)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Get rate limiter for this operation type
            limiter = get_database_rate_limiter(operation_type)
            
            # Temporarily increase burst limit
            original_burst = limiter.burst_requests
            limiter.burst_requests = int(original_burst * burst_multiplier)
            
            try:
                # Generate identifier for rate limiting
                identifier = get_client_identifier(request)
                
                # Check rate limit
                allowed, info = limiter.is_allowed(identifier)
                
                if not allowed:
                    # Log rate limit violation
                    logger.warning(
                        f"Database rate limit exceeded for {operation_type} operation (with burst)",
                        extra={
                            'path': request.path,
                            'method': request.method,
                            'identifier': identifier,
                            'operation_type': operation_type,
                            'retry_after': info['retry_after'],
                            'view_function': view_func.__name__,
                            'burst_multiplier': burst_multiplier,
                        }
                    )
                    
                    # Return rate limit error response
                    if (request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                        request.path.endswith('/credentials/') or
                        'dependencies' in request.path):
                        response = JsonResponse({
                            'error': 'Database rate limit exceeded',
                            'message': f'Too many {operation_type} operations. Please try again later.',
                            'retry_after': info['retry_after'],
                            'operation_type': info['operation_type'],
                            'limit': info['limit'],
                            'remaining': info['remaining'],
                            'reset': info['reset']
                        }, status=429)
                    else:
                        response = render(request, 'errors/429.html', {
                            'retry_after': info['retry_after'],
                            'limit': info['limit'],
                            'remaining': info['remaining'],
                            'reset': info['reset'],
                            'operation_type': info['operation_type']
                        }, status=429)
                    
                    # Add rate limit headers
                    response['X-Database-RateLimit-Limit'] = str(info['limit'])
                    response['X-Database-RateLimit-Remaining'] = str(info['remaining'])
                    response['X-Database-RateLimit-Reset'] = str(info['reset'])
                    response['X-Database-RateLimit-Operation'] = info['operation_type']
                    response['Retry-After'] = str(info['retry_after'])
                    
                    return response
                
                # Store rate limit info for later use in response headers
                request._db_rate_limit_info = info
                
                # Execute the view
                response = view_func(request, *args, **kwargs)
                
                # Add rate limit headers to successful response
                if hasattr(response, '__setitem__'):  # Check if response supports headers
                    response['X-Database-RateLimit-Limit'] = str(info['limit'])
                    response['X-Database-RateLimit-Remaining'] = str(info['remaining'])
                    response['X-Database-RateLimit-Reset'] = str(info['reset'])
                    response['X-Database-RateLimit-Operation'] = info['operation_type']
                
                return response
            finally:
                # Restore original burst limit
                limiter.burst_requests = original_burst
        
        return wrapped_view
    return decorator