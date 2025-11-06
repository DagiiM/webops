"""
Management command to seed enterprise permissions and roles.

Usage:
    python manage.py seed_enterprise
"""

from django.core.management.base import BaseCommand
from apps.core.enterprise.permissions import PermissionSeeder


class Command(BaseCommand):
    help = 'Seed enterprise permissions and roles'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Seeding enterprise permissions and roles...'))

        # Seed permissions
        self.stdout.write('Creating permissions...')
        perm_count = PermissionSeeder.seed_permissions()
        self.stdout.write(self.style.SUCCESS(f'✓ Created {perm_count} permissions'))

        # Seed roles
        self.stdout.write('Creating roles...')
        roles = PermissionSeeder.seed_roles()
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(roles)} roles:'))
        for slug, role in roles.items():
            perm_count = role.permissions.count()
            self.stdout.write(f'  - {role.name}: {perm_count} permissions')

        self.stdout.write(self.style.SUCCESS('\n✓ Enterprise setup complete!'))
