#!/usr/bin/env python
"""
Enhanced test runner for WebOps with coverage reporting.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py apps.deployments  # Run specific app tests
    python run_tests.py --coverage        # Run with coverage
"""

import os
import sys
import django
from django.core.management import execute_from_command_line
from django.test.utils import get_runner
from django.conf import settings

def main():
    """Run tests with enhanced configuration."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    # Check for coverage flag
    use_coverage = '--coverage' in sys.argv
    if use_coverage:
        sys.argv.remove('--coverage')
        try:
            import coverage
            cov = coverage.Coverage()
            cov.start()
        except ImportError:
            print("Coverage package not installed. Install with: pip install coverage")
            sys.exit(1)
    
    # Set test database settings
    settings.DATABASES['default']['NAME'] = ':memory:'
    
    # Run tests
    test_runner = get_runner(settings)()
    
    # Determine test labels
    if len(sys.argv) > 1:
        test_labels = sys.argv[1:]
    else:
        test_labels = [
            'apps.core.tests',
            'apps.deployments.tests', 
            'apps.databases.tests',
            'apps.services.tests',
            'apps.api.tests'
        ]
    
    failures = test_runner.run_tests(test_labels, verbosity=2)
    
    if use_coverage:
        cov.stop()
        cov.save()
        
        print("\nCoverage Report:")
        print("=" * 50)
        cov.report()
        
        # Generate HTML report
        cov.html_report(directory='htmlcov')
        print(f"\nDetailed HTML coverage report: {os.getcwd()}/htmlcov/index.html")
    
    if failures:
        print(f"\n{failures} test(s) failed.")
        sys.exit(1)
    else:
        print("\nAll tests passed!")

if __name__ == '__main__':
    main()