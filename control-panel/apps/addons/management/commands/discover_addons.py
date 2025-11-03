"""
Django management command to discover system addons.

Usage:
    python manage.py discover_addons
    python manage.py discover_addons --sync-status
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.addons.unified_registry import get_addon_registry
from apps.addons.models import SystemAddon


class Command(BaseCommand):
    help = 'Discover and register system addons from the filesystem'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync-status',
            action='store_true',
            help='Sync status from bash scripts after discovery',
        )
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Run health checks after discovery',
        )

    def handle(self, *args, **options):
        self.stdout.write('Discovering system addons...\n')

        registry = get_addon_registry()

        # Discover addons
        try:
            count = registry.discover_system_addons()
            self.stdout.write(self.style.SUCCESS(
                f'✓ Successfully discovered {count} system addon(s)\n'
            ))
        except Exception as e:
            raise CommandError(f'Failed to discover addons: {e}')

        # Display discovered addons
        self.stdout.write('\nDiscovered addons:')
        self.stdout.write('-' * 80)

        addons = SystemAddon.objects.all().order_by('category', 'display_name')

        if not addons.exists():
            self.stdout.write(self.style.WARNING('No addons found'))
            return

        for addon in addons:
            status_color = self._get_status_color(addon.status)
            health_icon = self._get_health_icon(addon.health)

            self.stdout.write(
                f'{addon.display_name:30} '
                f'[{status_color(addon.get_status_display()):12}] '
                f'{health_icon} '
                f'v{addon.version or "unknown":10} '
                f'({addon.category})'
            )

        # Sync status if requested
        if options['sync_status']:
            self.stdout.write('\nSyncing addon status...')

            from apps.addons.tasks import sync_system_addon_status

            for addon in addons:
                try:
                    task = sync_system_addon_status.delay(addon.id)
                    self.stdout.write(f'  {addon.name}: Task {task.id}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'  {addon.name}: Failed - {e}'
                    ))

        # Run health check if requested
        if options['health_check']:
            self.stdout.write('\nRunning health checks...')

            from apps.addons.tasks import health_check_system_addons

            try:
                task = health_check_system_addons.delay()
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Health check task started: {task.id}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ Failed to start health check: {e}'
                ))

        # Summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('Summary:')
        self.stdout.write('-' * 80)

        status_counts = SystemAddon.objects.values('status').annotate(
            count=models.Count('id')
        )

        for item in status_counts:
            self.stdout.write(
                f'  {item["status"]:20} : {item["count"]} addon(s)'
            )

        self.stdout.write('=' * 80)

    def _get_status_color(self, status):
        """Get colored output function for status."""
        colors = {
            'not_installed': self.style.WARNING,
            'installing': self.style.NOTICE,
            'installed': self.style.SUCCESS,
            'configuring': self.style.NOTICE,
            'failed': self.style.ERROR,
            'uninstalling': self.style.WARNING,
            'degraded': self.style.WARNING,
        }
        return colors.get(status, self.style.WARNING)

    def _get_health_icon(self, health):
        """Get icon for health status."""
        icons = {
            'healthy': '✓',
            'unhealthy': '✗',
            'degraded': '⚠',
            'unknown': '?',
        }
        return icons.get(health, '?')


# Import for annotation
from django.db import models
