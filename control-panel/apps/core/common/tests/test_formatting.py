"""
Tests for formatting utilities.
"""

from django.test import TestCase
from apps.core.common.utils.formatting import (
    format_bytes,
    format_uptime
)


class FormattingUtilsTests(TestCase):
    """Test formatting utility functions."""

    def test_format_bytes(self):
        """Test bytes formatting."""
        test_cases = [
            (500, '500.0 B'),
            (1023, '1023.0 B'),
            (1024, '1.0 KB'),
            (1536, '1.5 KB'),
            (1024 * 1024, '1.0 MB'),
            (1024 * 1024 * 1.5, '1.5 MB'),
            (1024 * 1024 * 1024, '1.0 GB'),
            (1024 * 1024 * 1024 * 1.5, '1.5 GB'),
            (1024 * 1024 * 1024 * 1024, '1.0 TB'),
            (1024 * 1024 * 1024 * 1024 * 1.5, '1.5 TB'),
            (1024 * 1024 * 1024 * 1024 * 1024, '1.0 PB'),
            (1024 * 1024 * 1024 * 1024 * 1024 * 1.5, '1.5 PB'),
        ]
        
        for bytes_value, expected in test_cases:
            with self.subTest(bytes_value=bytes_value):
                result = format_bytes(bytes_value)
                self.assertEqual(result, expected)

    def test_format_uptime(self):
        """Test uptime formatting."""
        test_cases = [
            (30, '30 seconds'),
            (59, '59 seconds'),
            (60, '1 minutes'),
            (61, '1 minutes'),
            (120, '2 minutes'),
            (3599, '59 minutes'),
            (3600, '1h 0m'),
            (3601, '1h 0m'),
            (3660, '1h 1m'),
            (7200, '2h 0m'),
            (86399, '23h 59m'),
            (86400, '1d 0h'),
            (86401, '1d 0h'),
            (86460, '1d 1h'),
            (90000, '1d 1h'),
            (172800, '2d 0h'),
            (259200, '3d 0h'),
        ]
        
        for seconds, expected in test_cases:
            with self.subTest(seconds=seconds):
                result = format_uptime(seconds)
                self.assertEqual(result, expected)