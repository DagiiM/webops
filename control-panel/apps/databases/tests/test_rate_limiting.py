"""
Tests for database rate limiting functionality.

"Testing Best Practices" section
"""

import time
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.urls import reverse

from apps.databases.middleware import (
    DatabaseRateLimiter,
    DatabaseRateLimitExceeded,
    get_database_rate_limiter,
    get_client_identifier,
    get_database_operation_type,
    DatabaseRateLimitMiddleware
)
from apps.databases.decorators import (
    database_rate_limit,
    database_read_rate_limit,
    database_write_rate_limit,
    database_admin_rate_limit,
    database_rate_limit_by_user,
    database_rate_limit_by_database
)
from apps.databases.models import Database


class DatabaseRateLimiterTest(TestCase):
    """Test the DatabaseRateLimiter class."""
    
    def setUp(self):
        """Set up test environment."""
        cache.clear()
        self.limiter = DatabaseRateLimiter(
            operation_type='test',
            max_requests=5,
            window_seconds=60,
            burst_requests=3,
            burst_window=30
        )
        self.identifier = 'test_user_123'
    
    def test_is_allowed_within_limits(self):
        """Test that requests within limits are allowed."""
        # First request should be allowed
        allowed, info = self.limiter.is_allowed(self.identifier)
        self.assertTrue(allowed)
        self.assertEqual(info['remaining'], 4)
        self.assertEqual(info['limit'], 5)
        
        # Second request should also be allowed
        allowed, info = self.limiter.is_allowed(self.identifier)
        self.assertTrue(allowed)
        self.assertEqual(info['remaining'], 3)
    
    def test_is_allowed_exceeds_limit(self):
        """Test that requests exceeding limits are blocked."""
        # Make 5 requests (at limit)
        for i in range(5):
            allowed, info = self.limiter.is_allowed(self.identifier)
            if i < 4:  # First 4 should be allowed
                self.assertTrue(allowed)
            else:  # 5th should hit limit
                self.assertFalse(allowed)
                self.assertIn('retry_after', info)
                self.assertEqual(info['remaining'], 0)
    
    def test_burst_limiting(self):
        """Test burst limiting functionality."""
        # Make 3 requests quickly (at burst limit)
        for i in range(3):
            allowed, info = self.limiter.is_allowed(self.identifier)
            self.assertTrue(allowed)
        
        # 4th request should exceed burst limit
        allowed, info = self.limiter.is_allowed(self.identifier)
        self.assertFalse(allowed)
        self.assertIn('retry_after', info)
    
    def test_cache_keys(self):
        """Test that cache keys are generated correctly."""
        rate_key, burst_key = self.limiter.get_cache_keys(self.identifier)
        self.assertIn('db_rate_limit:test', rate_key)
        self.assertIn('burst_limit:test', burst_key)
        self.assertIn('60', rate_key)  # window_seconds
        self.assertIn('30', burst_key)  # burst_window
    
    def test_window_reset(self):
        """Test that counters reset when window expires."""
        # Create a limiter with very short window for testing
        short_limiter = DatabaseRateLimiter(
            operation_type='test',
            max_requests=2,
            window_seconds=1,  # 1 second window
            burst_requests=2,
            burst_window=1
        )
        
        # Make 2 requests (at limit)
        for i in range(2):
            allowed, info = short_limiter.is_allowed(self.identifier)
            self.assertTrue(allowed)
        
        # 3rd request should be blocked
        allowed, info = short_limiter.is_allowed(self.identifier)
        self.assertFalse(allowed)
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # After window expires, request should be allowed again
        allowed, info = short_limiter.is_allowed(self.identifier)
        self.assertTrue(allowed)
        self.assertEqual(info['remaining'], 1)


class DatabaseRateLimitMiddlewareTest(TestCase):
    """Test the DatabaseRateLimitMiddleware class."""
    
    def setUp(self):
        """Set up test environment."""
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.middleware = DatabaseRateLimitMiddleware(get_response=lambda r: r)
    
    def test_process_request_skips_non_database_paths(self):
        """Test that middleware skips non-database paths."""
        request = self.factory.get('/deployments/')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)
        
        request = self.factory.get('/static/css/style.css')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)
        
        request = self.factory.get('/admin/')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)
    
    def test_process_request_applies_to_database_paths(self):
        """Test that middleware applies to database paths."""
        request = self.factory.get('/databases/')
        request.user = self.user
        
        # First request should be allowed
        result = self.middleware.process_request(request)
        self.assertIsNone(result)
        self.assertTrue(hasattr(request, '_db_rate_limit_info'))
        
        # Make many requests to trigger rate limit
        for i in range(25):  # Exceed default read limit
            request = self.factory.get('/databases/')
            request.user = self.user
            result = self.middleware.process_request(request)
            
            if result is not None:
                self.assertIsInstance(result, JsonResponse)
                self.assertEqual(result.status_code, 429)
                break
    
    def test_get_database_operation_type(self):
        """Test operation type detection."""
        # Read operations
        request = self.factory.get('/databases/1/')
        self.assertEqual(get_database_operation_type(request), 'read')
        
        # Write operations
        request = self.factory.post('/databases/create/')
        self.assertEqual(get_database_operation_type(request), 'write')
        
        request = self.factory.delete('/databases/1/delete/')
        self.assertEqual(get_database_operation_type(request), 'write')
        
        # Admin operations
        request = self.factory.get('/databases/1/credentials/')
        self.assertEqual(get_database_operation_type(request), 'admin')
        
        request = self.factory.get('/databases/check-dependencies/')
        self.assertEqual(get_database_operation_type(request), 'admin')
    
    def test_get_client_identifier_with_user(self):
        """Test client identifier generation with authenticated user."""
        request = self.factory.get('/databases/')
        request.user = self.user
        identifier = get_client_identifier(request)
        self.assertEqual(identifier, f'user_{self.user.id}')
    
    def test_get_client_identifier_without_user(self):
        """Test client identifier generation without authenticated user."""
        request = self.factory.get('/databases/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        identifier = get_client_identifier(request)
        self.assertEqual(identifier, 'ip_192.168.1.100')
        
        # Test with X-Forwarded-For header
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 192.168.1.100'
        identifier = get_client_identifier(request)
        self.assertEqual(identifier, 'ip_203.0.113.1')


class DatabaseRateLimitDecoratorsTest(TestCase):
    """Test the database rate limiting decorators."""
    
    def setUp(self):
        """Set up test environment."""
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_database_read_rate_limit_decorator(self):
        """Test read rate limit decorator."""
        @database_read_rate_limit
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.get('/databases/')
        request.user = self.user
        
        # First request should succeed
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('X-Database-RateLimit-Limit', response)
        self.assertIn('X-Database-RateLimit-Remaining', response)
        self.assertIn('X-Database-RateLimit-Operation', response)
        self.assertEqual(response['X-Database-RateLimit-Operation'], 'read')
    
    def test_database_write_rate_limit_decorator(self):
        """Test write rate limit decorator."""
        @database_write_rate_limit
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.post('/databases/create/')
        request.user = self.user
        
        # First request should succeed
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Database-RateLimit-Operation'], 'write')
    
    def test_database_admin_rate_limit_decorator(self):
        """Test admin rate limit decorator."""
        @database_admin_rate_limit
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.get('/databases/1/credentials/')
        request.user = self.user
        
        # First request should succeed
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Database-RateLimit-Operation'], 'admin')
    
    def test_rate_limit_exceeded_response(self):
        """Test response when rate limit is exceeded."""
        @database_read_rate_limit
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.get('/databases/')
        request.user = self.user
        
        # Make many requests to trigger rate limit
        for i in range(25):  # Exceed default read limit
            response = test_view(request)
            
            if response.status_code == 429:
                self.assertIsInstance(response, JsonResponse)
                self.assertIn('error', json.loads(response.content))
                self.assertIn('retry_after', json.loads(response.content))
                self.assertIn('X-Database-RateLimit-Limit', response)
                self.assertIn('Retry-After', response)
                break
    
    def test_database_rate_limit_by_user_decorator(self):
        """Test rate limiting by user decorator."""
        @database_rate_limit_by_user('read')
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.get('/databases/')
        request.user = self.user
        
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
        
        # Test with different user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        request.user = other_user
        response = test_view(request)
        self.assertEqual(response.status_code, 200)
    
    def test_database_rate_limit_by_database_decorator(self):
        """Test rate limiting by database decorator."""
        @database_rate_limit_by_database('read')
        def test_view(request, pk):
            return HttpResponse(f'OK: {pk}')
        
        request = self.factory.get('/databases/1/')
        request.user = self.user
        
        response = test_view(request, pk=1)
        self.assertEqual(response.status_code, 200)
        
        # Test with different database ID
        response = test_view(request, pk=2)
        self.assertEqual(response.status_code, 200)


class DatabaseRateLimitIntegrationTest(TestCase):
    """Integration tests for database rate limiting."""
    
    def setUp(self):
        """Set up test environment."""
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Create a test database
        self.database = Database.objects.create(
            name='test_db',
            db_type='postgresql',
            host='localhost',
            port=5432,
            username='testuser',
            password='encrypted_password',
            database_name='test_db'
        )
    
    def test_database_list_view_rate_limiting(self):
        """Test rate limiting on database list view."""
        url = reverse('database_list')
        
        # First request should succeed
        request = self.factory.get(url)
        request.user = self.user
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Make many requests to trigger rate limit
        for i in range(25):  # Exceed default read limit
            response = self.client.get(url)
            
            if response.status_code == 429:
                self.assertIn('X-Database-RateLimit-Limit', response)
                self.assertIn('Retry-After', response)
                break
    
    def test_database_detail_view_rate_limiting(self):
        """Test rate limiting on database detail view."""
        url = reverse('database_detail', kwargs={'pk': self.database.pk})
        
        # First request should succeed
        request = self.factory.get(url)
        request.user = self.user
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Make many requests to trigger rate limit
        for i in range(25):  # Exceed default read limit
            response = self.client.get(url)
            
            if response.status_code == 429:
                self.assertIn('X-Database-RateLimit-Limit', response)
                self.assertIn('Retry-After', response)
                break
    
    def test_database_credentials_json_rate_limiting(self):
        """Test rate limiting on credentials JSON view."""
        url = reverse('database_credentials_json', kwargs={'pk': self.database.pk})
        
        # First request should succeed
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Make many requests to trigger rate limit (admin limit is lower)
        for i in range(25):  # Exceed default admin limit
            response = self.client.get(url)
            
            if response.status_code == 429:
                self.assertIn('X-Database-RateLimit-Limit', response)
                self.assertIn('Retry-After', response)
                self.assertEqual(response['X-Database-RateLimit-Operation'], 'admin')
                break
    
    def test_rate_limit_headers_in_response(self):
        """Test that rate limit headers are included in responses."""
        url = reverse('database_list')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check for rate limit headers
        self.assertIn('X-Database-RateLimit-Limit', response)
        self.assertIn('X-Database-RateLimit-Remaining', response)
        self.assertIn('X-Database-RateLimit-Reset', response)
        self.assertIn('X-Database-RateLimit-Operation', response)
        
        # Verify header values
        self.assertEqual(response['X-Database-RateLimit-Operation'], 'read')
        self.assertGreater(int(response['X-Database-RateLimit-Limit']), 0)
        self.assertGreaterEqual(int(response['X-Database-RateLimit-Remaining']), 0)
    
    @patch('apps.databases.middleware.logger')
    def test_rate_limit_violation_logging(self, mock_logger):
        """Test that rate limit violations are logged."""
        @database_read_rate_limit
        def test_view(request):
            return HttpResponse('OK')
        
        request = self.factory.get('/databases/')
        request.user = self.user
        
        # Make many requests to trigger rate limit
        for i in range(25):  # Exceed default read limit
            response = test_view(request)
            
            if response.status_code == 429:
                # Check that violation was logged
                mock_logger.warning.assert_called()
                call_args = mock_logger.warning.call_args[0]
                self.assertIn('Database rate limit exceeded', call_args[0])
                self.assertIn('extra', call_args[1])
                self.assertIn('operation_type', call_args[1]['extra'])
                self.assertEqual(call_args[1]['extra']['operation_type'], 'read')
                break