"""
Tests for rate limiting functionality.

Tests the token bucket rate limiter including:
- Rate limit enforcement
- Token refill
- Per-user vs per-IP limiting
- Superuser bypass
- Rate limit headers
- Graceful degradation
"""

import time
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.addons.rate_limiting import (
    RateLimiter,
    RateLimitConfig,
    rate_limit,
    rate_limiter,
)

User = get_user_model()


class TestRateLimiter(TestCase):
    """Tests for RateLimiter class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        # Clear cache before each test
        cache.clear()

        # Create rate limiter with test config
        self.limiter = RateLimiter()
        self.limiter.enabled = True

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def test_rate_limiter_allows_first_request(self):
        """Test that first request is always allowed."""
        request = self.factory.get('/api/test/')
        request.user = self.user

        allowed, info = self.limiter.check_rate_limit(request, 'test')

        self.assertTrue(allowed)
        self.assertIsNotNone(info['limit'])
        self.assertIsNotNone(info['remaining'])

    def test_rate_limiter_enforces_limit(self):
        """Test that rate limit is enforced after exhausting tokens."""
        # Configure very low limit for testing
        self.limiter.limits['test'] = RateLimitConfig(requests=2, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        # First request - allowed
        allowed1, info1 = self.limiter.check_rate_limit(request, 'test')
        self.assertTrue(allowed1)
        self.assertEqual(info1['remaining'], 1)

        # Second request - allowed
        allowed2, info2 = self.limiter.check_rate_limit(request, 'test')
        self.assertTrue(allowed2)
        self.assertEqual(info2['remaining'], 0)

        # Third request - denied
        allowed3, info3 = self.limiter.check_rate_limit(request, 'test')
        self.assertFalse(allowed3)
        self.assertEqual(info3['remaining'], 0)

    def test_superuser_bypasses_rate_limit(self):
        """Test that superusers bypass rate limiting."""
        self.limiter.limits['test'] = RateLimitConfig(requests=1, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.superuser

        # Make multiple requests - all should be allowed
        for _ in range(10):
            allowed, info = self.limiter.check_rate_limit(request, 'test')
            self.assertTrue(allowed)

    def test_rate_limiter_per_user(self):
        """Test that rate limits are tracked per user."""
        self.limiter.limits['test'] = RateLimitConfig(requests=1, window=60)

        user2 = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )

        request1 = self.factory.get('/api/test/')
        request1.user = self.user

        request2 = self.factory.get('/api/test/')
        request2.user = user2

        # First user's first request - allowed
        allowed1, _ = self.limiter.check_rate_limit(request1, 'test')
        self.assertTrue(allowed1)

        # First user's second request - denied
        allowed2, _ = self.limiter.check_rate_limit(request1, 'test')
        self.assertFalse(allowed2)

        # Second user's first request - allowed (different user)
        allowed3, _ = self.limiter.check_rate_limit(request2, 'test')
        self.assertTrue(allowed3)

    def test_rate_limiter_per_ip_for_anonymous(self):
        """Test that rate limits are tracked per IP for anonymous users."""
        self.limiter.limits['test'] = RateLimitConfig(requests=1, window=60)

        # Create anonymous request
        request = self.factory.get('/api/test/')
        request.user = MagicMock(is_authenticated=False)
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        # First request - allowed
        allowed1, _ = self.limiter.check_rate_limit(request, 'test')
        self.assertTrue(allowed1)

        # Second request from same IP - denied
        allowed2, _ = self.limiter.check_rate_limit(request, 'test')
        self.assertFalse(allowed2)

        # Request from different IP - allowed
        request2 = self.factory.get('/api/test/')
        request2.user = MagicMock(is_authenticated=False)
        request2.META['REMOTE_ADDR'] = '192.168.1.101'

        allowed3, _ = self.limiter.check_rate_limit(request2, 'test')
        self.assertTrue(allowed3)

    def test_rate_limiter_different_endpoints(self):
        """Test that different endpoints have separate limits."""
        self.limiter.limits['endpoint1'] = RateLimitConfig(requests=1, window=60)
        self.limiter.limits['endpoint2'] = RateLimitConfig(requests=1, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        # Use up limit for endpoint1
        allowed1, _ = self.limiter.check_rate_limit(request, 'endpoint1')
        self.assertTrue(allowed1)

        allowed2, _ = self.limiter.check_rate_limit(request, 'endpoint1')
        self.assertFalse(allowed2)

        # endpoint2 should still have tokens
        allowed3, _ = self.limiter.check_rate_limit(request, 'endpoint2')
        self.assertTrue(allowed3)

    def test_rate_limiter_disabled(self):
        """Test that rate limiting can be disabled."""
        self.limiter.enabled = False
        self.limiter.limits['test'] = RateLimitConfig(requests=1, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        # All requests should be allowed when disabled
        for _ in range(10):
            allowed, _ = self.limiter.check_rate_limit(request, 'test')
            self.assertTrue(allowed)

    def test_get_identifier_authenticated_user(self):
        """Test identifier generation for authenticated users."""
        request = self.factory.get('/api/test/')
        request.user = self.user

        identifier = self.limiter._get_identifier(request)

        self.assertTrue(identifier.startswith('user:'))
        self.assertIn(str(self.user.id), identifier)

    def test_get_identifier_anonymous_user(self):
        """Test identifier generation for anonymous users."""
        request = self.factory.get('/api/test/')
        request.user = MagicMock(is_authenticated=False)
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        identifier = self.limiter._get_identifier(request)

        self.assertTrue(identifier.startswith('ip:'))
        self.assertIn('192.168.1.100', identifier)

    def test_get_identifier_with_x_forwarded_for(self):
        """Test identifier extraction from X-Forwarded-For header."""
        request = self.factory.get('/api/test/')
        request.user = MagicMock(is_authenticated=False)
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1'

        identifier = self.limiter._get_identifier(request)

        # Should use first IP from X-Forwarded-For
        self.assertIn('203.0.113.1', identifier)


class TestRateLimitDecorator(TestCase):
    """Tests for rate_limit decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        cache.clear()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def test_decorator_allows_request_within_limit(self):
        """Test that decorator allows requests within limit."""
        @rate_limit('test')
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        # Configure limit
        rate_limiter.limits['test'] = RateLimitConfig(requests=5, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        response = test_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('X-RateLimit-Limit', response)
        self.assertIn('X-RateLimit-Remaining', response)

    def test_decorator_blocks_request_over_limit(self):
        """Test that decorator blocks requests over limit."""
        @rate_limit('test')
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        # Configure very low limit
        rate_limiter.limits['test'] = RateLimitConfig(requests=1, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        # First request - allowed
        response1 = test_view(request)
        self.assertEqual(response1.status_code, 200)

        # Second request - blocked
        response2 = test_view(request)
        self.assertEqual(response2.status_code, 429)

        # Check error response
        import json
        data = json.loads(response2.content)
        self.assertIn('error', data)
        self.assertIn('Rate limit exceeded', data['error'])
        self.assertIn('Retry-After', response2)

    def test_decorator_adds_rate_limit_headers(self):
        """Test that decorator adds rate limit headers to response."""
        @rate_limit('test')
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        rate_limiter.limits['test'] = RateLimitConfig(requests=10, window=60)

        request = self.factory.get('/api/test/')
        request.user = self.user

        response = test_view(request)

        self.assertIn('X-RateLimit-Limit', response)
        self.assertIn('X-RateLimit-Remaining', response)
        self.assertIn('X-RateLimit-Reset', response)
        self.assertEqual(response['X-RateLimit-Limit'], '10')


class TestRateLimitCacheFallback(TestCase):
    """Tests for graceful degradation when cache fails."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.limiter = RateLimiter()

    @patch('apps.addons.rate_limiting.cache.get')
    def test_cache_failure_allows_request(self, mock_cache_get):
        """Test that cache failures allow requests (fail open)."""
        mock_cache_get.side_effect = Exception("Cache unavailable")

        request = self.factory.get('/api/test/')
        request.user = self.user

        # Should allow request even though cache failed
        allowed, info = self.limiter.check_rate_limit(request, 'test')

        self.assertTrue(allowed)
