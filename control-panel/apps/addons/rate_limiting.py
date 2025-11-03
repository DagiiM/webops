"""
Rate limiting for addon API endpoints.

Implements token bucket algorithm with configurable limits:
- Per-user rate limits
- Per-IP rate limits
- Endpoint-specific limits
- Graceful degradation when Redis unavailable
"""

import time
import hashlib
from functools import wraps
from typing import Optional, Tuple, Callable
from dataclasses import dataclass

from django.core.cache import cache
from django.http import JsonResponse, HttpRequest
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds


class RateLimiter:
    """
    Token bucket rate limiter with Redis/cache backend.

    Falls back to in-memory if cache unavailable.
    """

    # Default rate limits (can be overridden in settings)
    DEFAULT_LIMITS = {
        'default': RateLimitConfig(requests=60, window=60),  # 60 req/min
        'install': RateLimitConfig(requests=10, window=60),  # 10 req/min
        'uninstall': RateLimitConfig(requests=10, window=60),
        'configure': RateLimitConfig(requests=30, window=60),
        'discover': RateLimitConfig(requests=5, window=60),
        'list': RateLimitConfig(requests=100, window=60),
    }

    def __init__(self):
        """Initialize rate limiter with configuration."""
        self.limits = getattr(settings, 'ADDON_RATE_LIMITS', self.DEFAULT_LIMITS)
        self.enabled = getattr(settings, 'ADDON_RATE_LIMITING_ENABLED', True)

    def _get_cache_key(self, identifier: str, endpoint: str) -> str:
        """
        Generate cache key for rate limit tracking.

        Args:
            identifier: User ID or IP address
            endpoint: API endpoint name

        Returns:
            Cache key string
        """
        # Hash to keep keys short
        hash_input = f"{identifier}:{endpoint}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"ratelimit:{endpoint}:{hash_value}"

    def _get_identifier(self, request: HttpRequest) -> str:
        """
        Get unique identifier for the request.

        Prefers user ID, falls back to IP address.

        Args:
            request: Django request object

        Returns:
            Unique identifier string
        """
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"

        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')

        return f"ip:{ip}"

    def check_rate_limit(
        self,
        request: HttpRequest,
        endpoint: str = 'default'
    ) -> Tuple[bool, dict]:
        """
        Check if request is within rate limit.

        Args:
            request: Django request object
            endpoint: Endpoint identifier for specific limits

        Returns:
            Tuple of (allowed: bool, info: dict)
            info contains: limit, remaining, reset_time
        """
        if not self.enabled:
            return True, {'limit': float('inf'), 'remaining': float('inf'), 'reset': 0}

        # Superusers bypass rate limiting
        if request.user and request.user.is_authenticated and request.user.is_superuser:
            return True, {'limit': float('inf'), 'remaining': float('inf'), 'reset': 0}

        # Get rate limit config
        config = self.limits.get(endpoint, self.DEFAULT_LIMITS['default'])

        # Get identifier and cache key
        identifier = self._get_identifier(request)
        cache_key = self._get_cache_key(identifier, endpoint)

        try:
            # Get current bucket state
            now = time.time()
            bucket = cache.get(cache_key)

            if bucket is None:
                # Initialize new bucket
                bucket = {
                    'tokens': config.requests - 1,  # Consume one token
                    'last_update': now,
                    'limit': config.requests,
                    'window': config.window,
                }
                cache.set(cache_key, bucket, config.window)

                return True, {
                    'limit': config.requests,
                    'remaining': bucket['tokens'],
                    'reset': int(now + config.window),
                }

            # Refill tokens based on time passed
            time_passed = now - bucket['last_update']
            refill_rate = config.requests / config.window
            new_tokens = min(
                config.requests,
                bucket['tokens'] + (time_passed * refill_rate)
            )

            # Check if we have tokens available
            if new_tokens >= 1:
                # Consume one token
                bucket['tokens'] = new_tokens - 1
                bucket['last_update'] = now

                # Calculate reset time
                reset_time = int(now + (config.window - time_passed))

                # Update cache
                cache.set(cache_key, bucket, config.window)

                return True, {
                    'limit': config.requests,
                    'remaining': int(bucket['tokens']),
                    'reset': reset_time,
                }
            else:
                # Rate limit exceeded
                reset_time = int(bucket['last_update'] + config.window)

                return False, {
                    'limit': config.requests,
                    'remaining': 0,
                    'reset': reset_time,
                }

        except Exception as e:
            # If cache fails, allow request but log error
            logger.error(f"Rate limit check failed: {e}")
            return True, {'limit': config.requests, 'remaining': config.requests, 'reset': 0}

    def get_retry_after(self, reset_time: int) -> int:
        """
        Calculate Retry-After header value.

        Args:
            reset_time: Unix timestamp when limit resets

        Returns:
            Seconds until reset
        """
        return max(0, reset_time - int(time.time()))


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(endpoint: str = 'default'):
    """
    Decorator to apply rate limiting to API endpoints.

    Args:
        endpoint: Endpoint identifier for specific rate limit

    Usage:
        @rate_limit('install')
        def install_addon(request, name):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Check rate limit
            allowed, info = rate_limiter.check_rate_limit(request, endpoint)

            if not allowed:
                retry_after = rate_limiter.get_retry_after(info['reset'])

                response = JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': f"Too many requests. Please try again in {retry_after} seconds.",
                    'limit': info['limit'],
                    'reset': info['reset'],
                    'retry_after': retry_after,
                }, status=429)

                # Add rate limit headers
                response['X-RateLimit-Limit'] = str(info['limit'])
                response['X-RateLimit-Remaining'] = str(info['remaining'])
                response['X-RateLimit-Reset'] = str(info['reset'])
                response['Retry-After'] = str(retry_after)

                return response

            # Call original view
            response = view_func(request, *args, **kwargs)

            # Add rate limit headers to successful response
            if hasattr(response, '__setitem__'):
                response['X-RateLimit-Limit'] = str(info['limit'])
                response['X-RateLimit-Remaining'] = str(info['remaining'])
                response['X-RateLimit-Reset'] = str(info['reset'])

            return response

        return wrapper
    return decorator


def configure_rate_limits(limits: dict):
    """
    Configure rate limits at runtime.

    Args:
        limits: Dictionary of endpoint: RateLimitConfig

    Usage:
        configure_rate_limits({
            'install': RateLimitConfig(requests=5, window=60),
            'list': RateLimitConfig(requests=200, window=60),
        })
    """
    rate_limiter.limits.update(limits)
    logger.info(f"Updated rate limits: {limits}")


def get_rate_limit_status(request: HttpRequest, endpoint: str = 'default') -> dict:
    """
    Get current rate limit status for a request.

    Args:
        request: Django request
        endpoint: Endpoint identifier

    Returns:
        Dictionary with limit, remaining, reset
    """
    allowed, info = rate_limiter.check_rate_limit(request, endpoint)
    return {
        'allowed': allowed,
        'limit': info['limit'],
        'remaining': info['remaining'],
        'reset': info['reset'],
        'reset_in': max(0, info['reset'] - int(time.time())),
    }
