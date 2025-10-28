"""
Rate limiting middleware and decorators for WebOps API.

"Security Best Practices" section
"""

import time
from typing import Dict, Tuple, Optional
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from functools import wraps


def get_client_ip(request) -> str:
    """
    Get client IP address from request.
    
    Args:
        request: Django request object
        
    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, 
                 max_requests: int = 100, 
                 window_seconds: int = 3600,
                 burst_requests: int = 20,
                 burst_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            burst_requests: Maximum burst requests
            burst_window: Burst window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_requests = burst_requests
        self.burst_window = burst_window
    
    def get_cache_keys(self, identifier: str) -> Tuple[str, str]:
        """Get cache keys for rate limiting."""
        return (
            f"rate_limit:{identifier}:{self.window_seconds}",
            f"burst_limit:{identifier}:{self.burst_window}"
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
            return False, {
                'retry_after': int(retry_after),
                'limit': self.max_requests,
                'remaining': max(0, self.max_requests - rate_data['count']),
                'reset': rate_data['reset_time']
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
            'reset': rate_data['reset_time']
        }


# Pre-configured rate limiters
API_RATE_LIMITER = RateLimiter(max_requests=100, window_seconds=3600)  # 100/hour
LOGIN_RATE_LIMITER = RateLimiter(max_requests=5, window_seconds=900)   # 5/15min
DEPLOYMENT_RATE_LIMITER = RateLimiter(max_requests=10, window_seconds=3600)  # 10/hour


def rate_limit(limiter: RateLimiter, key_func: Optional[callable] = None):
    """
    Rate limiting decorator.
    
    Args:
        limiter: RateLimiter instance
        key_func: Function to generate rate limit key (default: IP address)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Generate rate limit key
            if key_func:
                identifier = key_func(request, *args, **kwargs)
            else:
                identifier = get_client_ip(request)
            
            # Check rate limit
            allowed, info = limiter.is_allowed(identifier)

            if not allowed:
                # Check if request expects JSON (API request)
                if request.path.startswith('/api/') or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                    response = JsonResponse({
                        'error': 'Rate limit exceeded',
                        'retry_after': info['retry_after'],
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
                        'reset': info['reset']
                    }, status=429)

                # Add rate limit headers
                response['X-RateLimit-Limit'] = str(info['limit'])
                response['X-RateLimit-Remaining'] = str(info['remaining'])
                response['X-RateLimit-Reset'] = str(info['reset'])
                response['Retry-After'] = str(info['retry_after'])

                return response
            
            # Add rate limit headers to successful response
            response = view_func(request, *args, **kwargs)
            if hasattr(response, '__setitem__'):  # Check if response supports headers
                response['X-RateLimit-Limit'] = str(info['limit'])
                response['X-RateLimit-Remaining'] = str(info['remaining'])
                response['X-RateLimit-Reset'] = str(info['reset'])
            
            return response
        return wrapped_view
    return decorator


def api_rate_limit(view_func):
    """Standard API rate limiting decorator."""
    return rate_limit(API_RATE_LIMITER)(view_func)


def login_rate_limit(view_func):
    """Login rate limiting decorator."""
    return rate_limit(LOGIN_RATE_LIMITER)(view_func)


def deployment_rate_limit(view_func):
    """Deployment rate limiting decorator."""
    return rate_limit(DEPLOYMENT_RATE_LIMITER)(view_func)


def user_rate_limit(limiter: RateLimiter):
    """Rate limiting by authenticated user."""
    def key_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            return f"user_{request.user.id}"
        return get_client_ip(request)
    
    return rate_limit(limiter, key_func)


class RateLimitMiddleware:
    """
    Middleware for global rate limiting.
    
    Apply basic rate limiting to all requests.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.global_limiter = RateLimiter(max_requests=1000, window_seconds=3600)  # 1000/hour
    
    def __call__(self, request):
        # Skip rate limiting for static files and admin
        if (request.path.startswith('/static/') or
            request.path.startswith('/media/') or
            request.path.startswith('/admin/')):
            return self.get_response(request)
        
        # Get client identifier
        identifier = get_client_ip(request)
        
        # Check global rate limit
        allowed, info = self.global_limiter.is_allowed(identifier)
        
        print(f"Rate limit check for {identifier} on {request.path}: allowed={allowed}")
        
        if not allowed:
            print(f"Rate limit exceeded for {identifier}")

            # Check if request expects JSON (API request)
            if request.path.startswith('/api/') or request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
                response = JsonResponse({
                    'error': 'Global rate limit exceeded',
                    'message': 'Too many requests from this IP address',
                    'retry_after': info['retry_after']
                }, status=429)
            else:
                # Return HTML page for browser requests
                from django.shortcuts import render
                response = render(request, 'errors/429.html', {
                    'retry_after': info['retry_after'],
                    'limit': info['limit'],
                    'remaining': info['remaining'],
                    'reset': info['reset']
                }, status=429)

            response['Retry-After'] = str(info['retry_after'])
            return response
        
        response = self.get_response(request)
        return response


# Rate limiting for specific endpoints
def get_deployment_key(request, *args, **kwargs):
    """Generate rate limit key for deployment endpoints."""
    if request.user.is_authenticated:
        return f"deploy_user_{request.user.id}"
    return f"deploy_ip_{get_client_ip(request)}"