"""
Management command to initialize addon permissions.

Usage:
    python manage.py init_addon_permissions
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from apps.addons.models import SystemAddon, Addon
from apps.addons.permissions import create_addon_permissions


class Command(BaseCommand):
    help = 'Initialize addon permissions and create default permission groups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-groups',
            action='store_true',
            help='Create default permission groups (Addon Managers, Addon Viewers)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Initializing addon permissions...')

        # Create custom permissions
        created_count = create_addon_permissions()
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} custom permission(s)')
        )

        # Create default groups if requested
        if options['create_groups']:
            self.create_default_groups()

        self.stdout.write(self.style.SUCCESS('Addon permissions initialized successfully'))

    def create_default_groups(self):
        """Create default permission groups for addon management."""
        self.stdout.write('Creating default permission groups...')

        # Get content types
        addon_ct = ContentType.objects.get_for_model(Addon)
        system_addon_ct = ContentType.objects.get_for_model(SystemAddon)

        # 1. Addon Administrators (full control)
        admin_group, created = Group.objects.get_or_create(name='Addon Administrators')
        if created:
            self.stdout.write(self.style.SUCCESS('  Created group: Addon Administrators'))

        admin_permissions = Permission.objects.filter(
            content_type__in=[addon_ct, system_addon_ct]
        )
        admin_group.permissions.set(admin_permissions)
        self.stdout.write(
            f'  Assigned {admin_permissions.count()} permissions to Addon Administrators'
        )

        # 2. Addon Managers (install, configure, but not delete)
        manager_group, created = Group.objects.get_or_create(name='Addon Managers')
        if created:
            self.stdout.write(self.style.SUCCESS('  Created group: Addon Managers'))

        manager_permission_codes = [
            'view_addon',
            'view_systemaddon',
            'change_addon',
            'change_systemaddon',
            'install_systemaddon',
            'uninstall_systemaddon',
            'configure_systemaddon',
            'manage_addon',
        ]

        manager_permissions = Permission.objects.filter(
            content_type__in=[addon_ct, system_addon_ct],
            codename__in=manager_permission_codes
        )
        manager_group.permissions.set(manager_permissions)
        self.stdout.write(
            f'  Assigned {manager_permissions.count()} permissions to Addon Managers'
        )

        # 3. Addon Viewers (read-only)
        viewer_group, created = Group.objects.get_or_create(name='Addon Viewers')
        if created:
            self.stdout.write(self.style.SUCCESS('  Created group: Addon Viewers'))

        viewer_permissions = Permission.objects.filter(
            content_type__in=[addon_ct, system_addon_ct],
            codename__in=['view_addon', 'view_systemaddon']
        )
        viewer_group.permissions.set(viewer_permissions)
        self.stdout.write(
            f'  Assigned {viewer_permissions.count()} permissions to Addon Viewers'
        )

        self.stdout.write(self.style.SUCCESS('Default permission groups created'))
