"""
Tests for network utilities.
"""

from django.test import TestCase, RequestFactory
from apps.core.common.utils.network import (
    generate_port,
    validate_repo_url,
    get_client_ip
)


class NetworkUtilsTests(TestCase):
    """Test network utility functions."""

    def test_generate_port(self):
        """Test port generation."""
        used_ports = {8001, 8002, 8003}
        port = generate_port(used_ports)
        
        self.assertNotIn(port, used_ports)
        self.assertGreaterEqual(port, 8001)
        self.assertLessEqual(port, 9000)

    def test_generate_port_no_available(self):
        """Test port generation with no available ports."""
        used_ports = set(range(8001, 9001))
        
        with self.assertRaises(ValueError) as context:
            generate_port(used_ports)
        
        self.assertIn('No available ports', str(context.exception))

    def test_validate_repo_url_https(self):
        """Test HTTPS repository URL validation."""
        valid_urls = [
            'https://github.com/user/repo',
            'https://github.com/user/repo.git',
            'https://www.github.com/user/repo',
            'https://www.github.com/user/repo.git',
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(validate_repo_url(url))

    def test_validate_repo_url_ssh(self):
        """Test SSH repository URL validation."""
        valid_urls = [
            'git@github.com:user/repo.git',
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(validate_repo_url(url))

    def test_validate_repo_url_invalid(self):
        """Test invalid repository URL validation."""
        invalid_urls = [
            'http://github.com/user/repo',  # Not HTTPS
            'https://gitlab.com/user/repo',  # Not GitHub
            'https://github.com/user',  # Missing repo
            'https://github.com/user/',  # Missing repo
            'https://github.com//repo',  # Missing user
            'https://github.com/user/repo/extra',  # Too many path parts
            'git@github.com:user/repo',  # Missing .git suffix
            'not-a-url',
            '',
            None,
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(validate_repo_url(url))

    def test_get_client_ip_with_x_forwarded_for(self):
        """Test getting client IP with X-Forwarded-For header."""
        factory = RequestFactory()
        request = factory.get('/', HTTP_X_FORWARDED_FOR='192.168.1.1, 10.0.0.1')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

    def test_get_client_ip_without_x_forwarded_for(self):
        """Test getting client IP without X-Forwarded-For header."""
        factory = RequestFactory()
        request = factory.get('/', REMOTE_ADDR='192.168.1.2')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.2')

    def test_get_client_ip_default(self):
        """Test getting client IP with no IP headers."""
        factory = RequestFactory()
        request = factory.get('/')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')