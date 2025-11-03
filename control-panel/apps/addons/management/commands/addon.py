"""
Management command for addon operations (enable, disable, list, reload).

Usage:
    python manage.py addon list
    python manage.py addon enable docker
    python manage.py addon disable docker
    python manage.py addon reload
"""

from django.core.management.base import BaseCommand, CommandError
from apps.addons.models import Addon
from apps.addons.loader import register_discovered_addons
from apps.addons.registry import event_registry
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage WebOps addons (list, enable, disable, reload)'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['list', 'enable', 'disable', 'reload', 'info'],
            help='Action to perform on addons'
        )
        parser.add_argument(
            'addon_name',
            nargs='?',
            type=str,
            help='Name of the addon (required for enable, disable, info)'
        )

    def handle(self, *args, **options):
        action = options['action']
        addon_name = options.get('addon_name')

        if action == 'list':
            self.list_addons()
        elif action == 'enable':
            if not addon_name:
                raise CommandError('Addon name is required for enable action')
            self.enable_addon(addon_name)
        elif action == 'disable':
            if not addon_name:
                raise CommandError('Addon name is required for disable action')
            self.disable_addon(addon_name)
        elif action == 'reload':
            self.reload_addons()
        elif action == 'info':
            if not addon_name:
                raise CommandError('Addon name is required for info action')
            self.addon_info(addon_name)

    def list_addons(self):
        """List all discovered addons with their status."""
        addons = Addon.objects.all().order_by('name')

        if not addons:
            self.stdout.write(self.style.WARNING('No addons found.'))
            return

        self.stdout.write(self.style.SUCCESS('\nWebOps Addons:\n'))
        self.stdout.write('=' * 80)

        for addon in addons:
            status = self.style.SUCCESS('✓ ENABLED') if addon.enabled else self.style.ERROR('✗ DISABLED')
            self.stdout.write(f'\n{addon.name} (v{addon.version})')
            self.stdout.write(f'  Status: {status}')
            self.stdout.write(f'  Description: {addon.description}')
            if addon.author:
                self.stdout.write(f'  Author: {addon.author}')
            if addon.capabilities:
                self.stdout.write(f'  Capabilities: {", ".join(addon.capabilities)}')

            # Show metrics
            if addon.success_count > 0 or addon.failure_count > 0:
                total_runs = addon.success_count + addon.failure_count
                success_rate = (addon.success_count / total_runs * 100) if total_runs > 0 else 0
                self.stdout.write(f'  Metrics: {addon.success_count} success, {addon.failure_count} failures ({success_rate:.1f}% success rate)')

            if addon.last_error:
                self.stdout.write(self.style.ERROR(f'  Last Error: {addon.last_error[:100]}...'))

        self.stdout.write('\n' + '=' * 80)

        enabled_count = addons.filter(enabled=True).count()
        disabled_count = addons.filter(enabled=False).count()
        self.stdout.write(f'\nTotal: {addons.count()} addons ({enabled_count} enabled, {disabled_count} disabled)\n')

    def enable_addon(self, addon_name):
        """Enable an addon."""
        try:
            addon = Addon.objects.get(name=addon_name)
        except Addon.DoesNotExist:
            raise CommandError(f'Addon "{addon_name}" not found. Run "python manage.py addon list" to see available addons.')

        if addon.enabled:
            self.stdout.write(self.style.WARNING(f'Addon "{addon_name}" is already enabled.'))
            return

        addon.enabled = True
        addon.save()

        self.stdout.write(self.style.SUCCESS(f'✓ Addon "{addon_name}" has been enabled.'))
        self.stdout.write(self.style.WARNING('\n⚠ You must restart WebOps for changes to take effect:'))
        self.stdout.write('  - Development: Restart runserver')
        self.stdout.write('  - Production: sudo systemctl restart webops-control-panel\n')

    def disable_addon(self, addon_name):
        """Disable an addon."""
        try:
            addon = Addon.objects.get(name=addon_name)
        except Addon.DoesNotExist:
            raise CommandError(f'Addon "{addon_name}" not found. Run "python manage.py addon list" to see available addons.')

        if not addon.enabled:
            self.stdout.write(self.style.WARNING(f'Addon "{addon_name}" is already disabled.'))
            return

        addon.enabled = False
        addon.save()

        self.stdout.write(self.style.SUCCESS(f'✓ Addon "{addon_name}" has been disabled.'))
        self.stdout.write(self.style.WARNING('\n⚠ You must restart WebOps for changes to take effect:'))
        self.stdout.write('  - Development: Restart runserver')
        self.stdout.write('  - Production: sudo systemctl restart webops-control-panel\n')

    def reload_addons(self):
        """Reload all addons (re-discover and re-register)."""
        self.stdout.write('Reloading addons...\n')

        try:
            # Clear existing hooks
            for event in event_registry.hooks.keys():
                event_registry.hooks[event] = []

            # Re-register addons
            register_discovered_addons(event_registry)

            self.stdout.write(self.style.SUCCESS('✓ Addons reloaded successfully.'))

            # Show summary
            enabled_addons = Addon.objects.filter(enabled=True)
            disabled_addons = Addon.objects.filter(enabled=False)

            self.stdout.write(f'\nEnabled addons: {", ".join(enabled_addons.values_list("name", flat=True))}')
            if disabled_addons:
                self.stdout.write(f'Disabled addons: {", ".join(disabled_addons.values_list("name", flat=True))}')

        except Exception as e:
            raise CommandError(f'Failed to reload addons: {e}')

    def addon_info(self, addon_name):
        """Show detailed information about an addon."""
        try:
            addon = Addon.objects.get(name=addon_name)
        except Addon.DoesNotExist:
            raise CommandError(f'Addon "{addon_name}" not found. Run "python manage.py addon list" to see available addons.')

        self.stdout.write(self.style.SUCCESS(f'\n{addon.name} v{addon.version}\n'))
        self.stdout.write('=' * 80)

        # Basic info
        status = self.style.SUCCESS('✓ ENABLED') if addon.enabled else self.style.ERROR('✗ DISABLED')
        self.stdout.write(f'\nStatus: {status}')
        self.stdout.write(f'Description: {addon.description}')
        if addon.author:
            self.stdout.write(f'Author: {addon.author}')
        if addon.license:
            self.stdout.write(f'License: {addon.license}')
        self.stdout.write(f'Manifest: {addon.manifest_path}')

        # Capabilities
        if addon.capabilities:
            self.stdout.write(f'\nCapabilities:')
            for cap in addon.capabilities:
                self.stdout.write(f'  - {cap}')

        # Settings schema
        if addon.settings_schema:
            self.stdout.write(f'\nSettings Schema:')
            for key, schema in addon.settings_schema.items():
                default = schema.get('default', 'N/A')
                self.stdout.write(f'  - {key}: {schema.get("type", "unknown")} (default: {default})')
                if 'description' in schema:
                    self.stdout.write(f'    {schema["description"]}')

        # Metrics
        self.stdout.write(f'\nMetrics:')
        total_runs = addon.success_count + addon.failure_count
        if total_runs > 0:
            success_rate = (addon.success_count / total_runs * 100)
            self.stdout.write(f'  Total runs: {total_runs}')
            self.stdout.write(f'  Successes: {addon.success_count}')
            self.stdout.write(f'  Failures: {addon.failure_count}')
            self.stdout.write(f'  Success rate: {success_rate:.1f}%')
            if addon.last_run_at:
                self.stdout.write(f'  Last run: {addon.last_run_at}')
            if addon.last_success_at:
                self.stdout.write(f'  Last success: {addon.last_success_at}')
            if addon.last_duration_ms:
                self.stdout.write(f'  Last duration: {addon.last_duration_ms}ms')
        else:
            self.stdout.write('  No runs recorded yet')

        # Last error
        if addon.last_error:
            self.stdout.write(f'\nLast Error:')
            self.stdout.write(self.style.ERROR(f'  {addon.last_error}'))

        # Registered hooks
        if addon.enabled:
            self.stdout.write(f'\nRegistered Hooks:')
            hook_count = 0
            for event in event_registry.hooks.keys():
                hooks = [h for h in event_registry.get_hooks(event) if h.addon_name == addon_name]
                if hooks:
                    self.stdout.write(f'  {event}:')
                    for hook in hooks:
                        self.stdout.write(f'    - Priority: {hook.priority}, Timeout: {hook.timeout_ms}ms, Enforcement: {hook.enforcement}')
                        hook_count += 1
            if hook_count == 0:
                self.stdout.write('  No hooks registered')
        else:
            self.stdout.write(f'\n{self.style.WARNING("Addon is disabled - no hooks are registered")}')

        self.stdout.write('\n' + '=' * 80 + '\n')
