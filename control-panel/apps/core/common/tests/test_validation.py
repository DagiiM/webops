"""
Tests for validation utilities.
"""

from django.test import TestCase
from apps.core.common.utils.validation import (
    validate_domain_name,
    sanitize_deployment_name
)


class ValidationUtilsTests(TestCase):
    """Test validation utility functions."""

    def test_validate_domain_name_valid(self):
        """Test valid domain name validation."""
        valid_domains = [
            'example.com',
            'sub.example.com',
            'example.co.uk',
            'a.b.c.d.e.f.g.h.i.j.k.l.m.n.o.p.q.r.s.t.u.v.w.x.y.z.com',
            'test123.com',
            '123-test.com',
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertTrue(validate_domain_name(domain))

    def test_validate_domain_name_invalid(self):
        """Test invalid domain name validation."""
        invalid_domains = [
            '',  # Empty
            '.example.com',  # Starts with dot
            'example.com.',  # Ends with dot
            'example..com',  # Double dot
            'example.com/',  # Ends with slash
            'example.com/extra',  # Has path
            'ex' + 'a' * 250 + '.com',  # Too long
            'ex' + 'a' * 63 + '.com',  # Label too long
            '-example.com',  # Starts with hyphen
            'example-.com',  # Ends with hyphen
            'example.c',  # Single character TLD
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.assertFalse(validate_domain_name(domain))

    def test_sanitize_deployment_name_valid(self):
        """Test valid deployment name sanitization."""
        test_cases = [
            ('My App', 'my-app'),
            ('Test_App-123', 'test-app-123'),
            ('My App (Production)', 'my-app-production'),
            ('My App - Production', 'my-app-production'),
            ('My   App', 'my-app'),  # Multiple spaces
            ('My__App', 'my-app'),  # Multiple underscores
            ('My--App', 'my-app'),  # Multiple hyphens
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_deployment_name(input_name)
                self.assertEqual(result, expected)

    def test_sanitize_deployment_name_empty(self):
        """Test empty deployment name."""
        with self.assertRaises(ValueError) as context:
            sanitize_deployment_name('')
        
        self.assertIn('Deployment name cannot be empty', str(context.exception))

    def test_sanitize_deployment_name_too_short(self):
        """Test deployment name that becomes too short after sanitization."""
        with self.assertRaises(ValueError) as context:
            sanitize_deployment_name('a')
        
        self.assertIn('Deployment name too short', str(context.exception))

    def test_sanitize_deployment_name_too_long(self):
        """Test deployment name that becomes too long after sanitization."""
        long_name = 'A' * 100
        result = sanitize_deployment_name(long_name)
        
        self.assertLessEqual(len(result), 50)
        self.assertTrue(result.endswith('a'))

    def test_sanitize_deployment_name_special_chars(self):
        """Test deployment name with special characters."""
        test_cases = [
            ('My App!', 'my-app'),  # Exclamation mark
            ('My App@#$', 'my-app'),  # Multiple special chars
            ('My App_With_Underscores', 'my-app-with-underscores'),
            ('My App.With.Dots', 'my-app-with-dots'),
            ('My App/With/Slashes', 'my-app-with-slashes'),
            ('My App\\With\\Backslashes', 'my-app-with-backslashes'),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input_name=input_name):
                result = sanitize_deployment_name(input_name)
                self.assertEqual(result, expected)