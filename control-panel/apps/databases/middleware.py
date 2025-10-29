"""
Database rate limiting middleware for WebOps.

"Security Best Practices" section
"""

import time
import logging
from typing import Dict, Tuple, Optional
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseRateLimitExceeded(Exception):
    """Exception raised when database rate limit is exceeded."""
    def __init__(self, retry_after: int, operation_type: str):
        self.retry_after = retry_after
        self.operation_type = operation_type
        super().__init__(f"Database rate limit exceeded for {operation_type}. Retry after {retry_after} seconds.")


class DatabaseRateLimiter:
    """
    Database-specific rate limiter with sliding window implementation.
    
    Supports different rate limits for different operation types:
    - read: Database read operations (list, detail)
    - write: Database write operations (create, update, delete)
    - admin: Administrative operations (credentials access, dependency checks)
    """
    
    def __init__(self, 
                 operation_type: str = 'read',
                 max_requests: int = 100, 
                 window_seconds: int = 3600,
                 burst_requests: int = 20,
                 burst_window: int = 60):
        """
        Initialize database rate limiter.
        
        Args:
            operation_type: Type of operation (read, write, admin)
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            burst_requests: Maximum burst requests
            burst_window: Burst window in seconds
        """
        self.operation_type = operation_type
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_requests = burst_requests
        self.burst_window = burst_window
    
    def get_cache_keys(self, identifier: str) -> Tuple[str, str]:
        """Get cache keys for rate limiting."""
        return (
            f"db_rate_limit:{self.operation_type}:{identifier}:{self.window_seconds}",
            f"db_burst_limit:{self.operation_type}:{identifier}:{self.burst_window}"
        )
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        now = int(time.time())
        rate_key, burst_key = self.get_cache_keys(identifier)
        
        # Check main rate limit
        rate_data = cache.get(rate_key, {'count': 0, 'reset_time': now + self.window_seconds})
        
        # Reset if window expired
        if now >= rate_data['reset_time']:
            rate_data = {'count': 0, 'reset_time': now + self.window_seconds}
        
        # Check burst limit
        burst_data = cache.get(burst_key, {'count': 0, 'reset_time': now + self.burst_window})
        
        # Reset burst if window expired
        if now >= burst_data['reset_time']:
            burst_data = {'count': 0, 'reset_time': now + self.burst_window}
        
        # Check limits
        rate_exceeded = rate_data['count'] >= self.max_requests
        burst_exceeded = burst_data['count'] >= self.burst_requests
        
        if rate_exceeded or burst_exceeded:
            retry_after = min(
                rate_data['reset_time'] - now if rate_exceeded else float('inf'),
                burst_data['reset_time'] - now if burst_exceeded else float('inf')
            )
            
            # Log rate limit violation for security monitoring
            logger.warning(
                f"Database rate limit exceeded for {self.operation_type} operation",
                extra={
                    'identifier': identifier,
                    'operation_type': self.operation_type,
                    'retry_after': retry_after,
                    'rate_count': rate_data['count'],
                    'burst_count': burst_data['count'],
                    'timestamp': str(timezone.now())
                }
            )
            
            return False, {
                'retry_after': int(retry_after),
                'limit': self.max_requests,
                'remaining': max(0, self.max_requests - rate_data['count']),
                'reset': rate_data['reset_time'],
                'operation_type': self.operation_type
            }
        
        # Increment counters
        rate_data['count'] += 1
        burst_data['count'] += 1
        
        # Save to cache
        cache.set(rate_key, rate_data, timeout=self.window_seconds)
        cache.set(burst_key, burst_data, timeout=self.burst_window)
        
        return True, {
            'limit': self.max_requests,
            'remaining': max(0, self.max_requests - rate_data['count']),
            'reset': rate_data['reset_time'],
            'operation_type': self.operation_type
        }


def get_database_rate_limiter(operation_type: str) -> DatabaseRateLimiter:
    """
    Get rate limiter instance for specific operation type.
    
    Args:
        operation_type: Type of operation (read, write, admin)
        
    Returns:
        DatabaseRateLimiter instance
    """
    # Get rate limit settings from configuration
    settings_dict = getattr(settings, 'DATABASE_RATE_LIMITS', {
        'read': {'max_requests': 200, 'window_seconds': 3600, 'burst_requests': 50, 'burst_window': 60},
        'write': {'max_requests': 50, 'window_seconds': 3600, 'burst_requests': 10, 'burst_window': 60},
        'admin': {'max_requests': 20, 'window_seconds': 3600, 'burst_requests': 5, 'burst_window': 300},
    })
    
    config = settings_dict.get(operation_type, settings_dict['read'])
    
    return DatabaseRateLimiter(
        operation_type=operation_type,
        max_requests=config.get('max_requests', 100),
        window_seconds=config.get('window_seconds', 3600),
        burst_requests=config.get('burst_requests', 20),
        burst_window=config.get('burst_window', 60)
    )


def get_client_identifier(request) -> str:
    """
    Get client identifier for rate limiting.
    
    Args:
        request: Django request object
        
    Returns:
        Client identifier string
    """
    # Use authenticated user ID if available
    if hasattr(request, 'user') and request.user.is_authenticated:
        return f"user_{request.user.id}"
    
    # Fall back to IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return f"ip_{ip}"


def get_database_operation_type(request) -> str:
    """
    Determine database operation type from request.
    
    Args:
        request: Django request object
        
    Returns:
        Operation type string (read, write, admin)
    """
    path = request.path
    method = request.method
    
    # Admin operations (sensitive operations)
    if 'credentials' in path or 'dependencies' in path:
        return 'admin'
    
    # Write operations
    if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
        return 'write'
    
    # Default to read operations
    return 'read'


class DatabaseRateLimitMiddleware(MiddlewareMixin):
    """
    Middleware for database-specific rate limiting.
    
    Applies rate limiting to all database-related requests.
    """
    
    def process_request(self, request):
        """Process incoming request for rate limiting."""
        # Skip rate limiting for static files and admin
        if (request.path.startswith('/static/') or
            request.path.startswith('/media/') or
            request.path.startswith('/admin/')):
            return None
        
        # Only apply to database-related paths
        if not request.path.startswith('/databases/'):
            return None
        
        # Get operation type and identifier
        operation_type = get_database_operation_type(request)
        identifier = get_client_identifier(request)
        
        # Get appropriate rate limiter
        limiter = get_database_rate_limiter(operation_type)
        
        # Check rate limit
        allowed, info = limiter.is_allowed(identifier)
        
        if not allowed:
            # Log rate limit violation
            logger.warning(
                f"Database rate limit exceeded: {operation_type} operation for {identifier}",
                extra={
                    'path': request.path,
                    'method': request.method,
                    'identifier': identifier,
                    'operation_type': operation_type,
                    'retry_after': info['retry_after'],
                    'timestamp': str(timezone.now())
                }
            )
            
            # Check if request expects JSON (API request)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
               request.path.endswith('/credentials/') or \
               'dependencies' in request.path:
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
                from django.shortcuts import render
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
        return None
    
    def process_response(self, request, response):
        """Add rate limit headers to successful responses."""
        # Only add headers to database-related requests
        if not request.path.startswith('/databases/'):
            return response
        
        # Get rate limit info from request if available
        if hasattr(request, '_db_rate_limit_info'):
            info = request._db_rate_limit_info
            
            # Add rate limit headers
            response['X-Database-RateLimit-Limit'] = str(info['limit'])
            response['X-Database-RateLimit-Remaining'] = str(info['remaining'])
            response['X-Database-RateLimit-Reset'] = str(info['reset'])
            response['X-Database-RateLimit-Operation'] = info['operation_type']
        
        return response