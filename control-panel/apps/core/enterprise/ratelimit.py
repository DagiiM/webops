"""
Enterprise API rate limiting.

Features:
- Per-user rate limiting
- Per-organization rate limiting
- Per-IP rate limiting
- Configurable limits per tier
- Redis-backed (efficient)
"""

from django.core.cache import cache
from django.http import JsonResponse
from functools import wraps
import time


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """
    Enterprise rate limiter with tier-based limits.

    Usage:
        limiter = RateLimiter()
        limiter.check_limit(user, 'api_calls', max_calls=100, window=60)
    """

    def __init__(self):
        self.cache = cache

    def check_limit(self, key, max_calls, window):
        """
        Check if rate limit is exceeded.

        Args:
            key: Unique key (user_id, org_id, ip, etc.)
            max_calls: Maximum calls allowed in window
            window: Time window in seconds

        Returns:
            Tuple (allowed: bool, remaining: int, reset_time: int)

        Raises:
            RateLimitExceeded: If limit exceeded
        """

        cache_key = f"ratelimit:{key}"

        # Get current count
        data = self.cache.get(cache_key)

        if data is None:
            # First request in window
            data = {
                'count': 1,
                'reset_time': int(time.time()) + window
            }
            self.cache.set(cache_key, data, window)
            return True, max_calls - 1, data['reset_time']

        # Increment count
        data['count'] += 1

        # Check if exceeded
        if data['count'] > max_calls:
            remaining = 0
            raise RateLimitExceeded(
                f"Rate limit exceeded. Limit: {max_calls}/{window}s. Reset at: {data['reset_time']}"
            )

        # Update cache
        remaining_window = data['reset_time'] - int(time.time())
        if remaining_window > 0:
            self.cache.set(cache_key, data, remaining_window)

        remaining = max_calls - data['count']
        return True, remaining, data['reset_time']

    def get_remaining(self, key):
        """Get remaining calls for key."""
        cache_key = f"ratelimit:{key}"
        data = self.cache.get(cache_key)

        if data is None:
            return None

        return data.get('count', 0)


class TierLimits:
    """
    Rate limits per organization tier.

    Tiers:
    - Free: 100 requests/hour
    - Starter: 1000 requests/hour
    - Pro: 10000 requests/hour
    - Enterprise: Unlimited (or very high limit)
    """

    FREE = {
        'api_calls_per_hour': 100,
        'api_calls_per_minute': 20,
        'deployments_per_day': 10,
        'concurrent_deployments': 2,
    }

    STARTER = {
        'api_calls_per_hour': 1000,
        'api_calls_per_minute': 100,
        'deployments_per_day': 50,
        'concurrent_deployments': 5,
    }

    PRO = {
        'api_calls_per_hour': 10000,
        'api_calls_per_minute': 500,
        'deployments_per_day': 200,
        'concurrent_deployments': 20,
    }

    ENTERPRISE = {
        'api_calls_per_hour': 100000,
        'api_calls_per_minute': 5000,
        'deployments_per_day': 1000,
        'concurrent_deployments': 100,
    }

    @classmethod
    def get_limits(cls, tier='free'):
        """Get limits for tier."""
        tier_map = {
            'free': cls.FREE,
            'starter': cls.STARTER,
            'pro': cls.PRO,
            'enterprise': cls.ENTERPRISE,
        }
        return tier_map.get(tier.lower(), cls.FREE)


def rate_limit(
    limit_type='api_calls',
    per='hour',
    tier_based=True,
    key_func=None
):
    """
    Decorator for rate limiting views.

    Usage:
        @rate_limit(limit_type='api_calls', per='hour')
        def api_view(request):
            ...

        @rate_limit(limit_type='deployments', per='day', key_func=lambda r: r.user.id)
        def create_deployment(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            limiter = RateLimiter()

            # Determine limit key
            if key_func:
                limit_key = key_func(request)
            elif request.user.is_authenticated:
                limit_key = f"user:{request.user.id}"
            else:
                # Fall back to IP
                limit_key = f"ip:{get_client_ip(request)}"

            # Get tier limits
            if tier_based and request.user.is_authenticated:
                tier = get_user_tier(request.user)
                limits = TierLimits.get_limits(tier)
            else:
                limits = TierLimits.FREE

            # Determine max calls and window
            limit_key_full = f"{limit_key}:{limit_type}:{per}"

            if per == 'minute':
                max_calls = limits.get(f'{limit_type}_per_minute', 20)
                window = 60
            elif per == 'hour':
                max_calls = limits.get(f'{limit_type}_per_hour', 100)
                window = 3600
            elif per == 'day':
                max_calls = limits.get(f'{limit_type}_per_day', 1000)
                window = 86400
            else:
                max_calls = 100
                window = 3600

            # Check limit
            try:
                allowed, remaining, reset_time = limiter.check_limit(
                    limit_key_full,
                    max_calls,
                    window
                )

                # Add headers to response
                response = view_func(request, *args, **kwargs)
                response['X-RateLimit-Limit'] = max_calls
                response['X-RateLimit-Remaining'] = remaining
                response['X-RateLimit-Reset'] = reset_time

                return response

            except RateLimitExceeded as e:
                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'message': str(e),
                    'limit': max_calls,
                    'window': per,
                    'reset_time': limiter.get_remaining(limit_key_full)
                }, status=429)

        return wrapper
    return decorator


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_tier(user):
    """
    Get user's organization tier.

    TODO: Implement actual tier lookup from Organization model.
    For now, return 'free' as default.
    """
    # This should look up the user's organization and return its tier
    # organization = user.organization_memberships.filter(is_active=True).first()
    # if organization:
    #     return organization.organization.tier
    return 'free'


class RateLimitMiddleware:
    """
    Global rate limiting middleware.

    Add to MIDDLEWARE in settings.py:
        'apps.core.enterprise.ratelimit.RateLimitMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.limiter = RateLimiter()

    def __call__(self, request):
        # Skip static files and admin
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return self.get_response(request)

        # Apply global rate limit
        if request.user.is_authenticated:
            limit_key = f"user:{request.user.id}:global"
            tier = get_user_tier(request.user)
            limits = TierLimits.get_limits(tier)
            max_calls = limits['api_calls_per_minute']
            window = 60
        else:
            # Anonymous requests: strict limits
            limit_key = f"ip:{get_client_ip(request)}:global"
            max_calls = 10  # 10 requests per minute for anonymous
            window = 60

        try:
            self.limiter.check_limit(limit_key, max_calls, window)
        except RateLimitExceeded as e:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': str(e)
            }, status=429)

        response = self.get_response(request)
        return response
