"""
Test Celery worker connectivity.

This management command is used by setup.sh to verify that:
1. Redis is accessible
2. Celery worker is running
3. Tasks can be queued and processed
"""

from django.core.management.base import BaseCommand
from celery import shared_task
from celery.result import AsyncResult
import time
import sys


@shared_task
def celery_health_check():
    """Simple task to verify Celery is working."""
    return "OK"


class Command(BaseCommand):
    help = 'Test Celery worker connectivity and task processing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in seconds (default: 30)'
        )

    def handle(self, *args, **options):
        timeout = options['timeout']

        self.stdout.write("Testing Celery worker connectivity...")

        try:
            # Test 1: Check Redis connectivity
            self.stdout.write("  → Testing Redis connection...")
            from django.core.cache import cache
            try:
                cache.set('celery_test', 'ok', 10)
                if cache.get('celery_test') == 'ok':
                    self.stdout.write(self.style.SUCCESS("    ✓ Redis connection OK"))
                else:
                    self.stdout.write(self.style.ERROR("    ✗ Redis connection failed"))
                    sys.exit(1)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ✗ Redis error: {e}"))
                sys.exit(1)

            # Test 2: Queue a task
            self.stdout.write("  → Sending test task to Celery...")
            result = celery_health_check.delay()

            self.stdout.write(f"    Task ID: {result.id}")

            # Test 3: Wait for result
            self.stdout.write(f"  → Waiting for task completion (timeout: {timeout}s)...")
            start_time = time.time()

            while not result.ready():
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.stdout.write(self.style.ERROR(
                        f"    ✗ Task did not complete within {timeout}s"
                    ))
                    self.stdout.write(self.style.WARNING(
                        "    This likely means the Celery worker is not running."
                    ))
                    sys.exit(1)

                # Show progress
                if int(elapsed) % 5 == 0 and elapsed > 0:
                    self.stdout.write(f"    Waiting... ({int(elapsed)}s elapsed)")

                time.sleep(0.5)

            # Check result
            try:
                task_result = result.get(timeout=5)
                if task_result == "OK":
                    elapsed = time.time() - start_time
                    self.stdout.write(self.style.SUCCESS(
                        f"    ✓ Task completed successfully in {elapsed:.2f}s"
                    ))
                    self.stdout.write(self.style.SUCCESS("\n✓ Celery worker is healthy!"))
                    sys.exit(0)
                else:
                    self.stdout.write(self.style.ERROR(f"    ✗ Unexpected result: {task_result}"))
                    sys.exit(1)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"    ✗ Task failed: {e}"))
                sys.exit(1)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Celery test failed: {e}"))
            import traceback
            traceback.print_exc()
            sys.exit(1)
