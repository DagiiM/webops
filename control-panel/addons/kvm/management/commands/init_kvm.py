"""
Initialize KVM Addon

Sets up directories, networks, and default configurations.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize KVM addon (directories, networks, defaults)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-network',
            action='store_true',
            help='Skip network creation',
        )
        parser.add_argument(
            '--create-defaults',
            action='store_true',
            help='Create default VM plans and templates',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Initializing KVM addon...'))

        # 1. Create storage directories
        self._create_directories()

        # 2. Setup NAT network
        if not options['skip_network']:
            self._setup_network()

        # 3. Create default plans and templates
        if options['create_defaults']:
            self._create_defaults()

        self.stdout.write(self.style.SUCCESS('KVM addon initialized successfully!'))

    def _create_directories(self):
        """Create necessary directories for VM storage."""
        self.stdout.write('Creating storage directories...')

        # Get storage path from settings or use default
        storage_path = getattr(settings, 'KVM_STORAGE_PATH', '/var/lib/webops/vms')
        template_path = getattr(settings, 'KVM_TEMPLATE_PATH', '/var/lib/webops/templates')

        paths = [
            Path(storage_path),
            Path(template_path),
        ]

        for path in paths:
            try:
                path.mkdir(parents=True, exist_ok=True)
                self.stdout.write(f'  ✓ Created: {path}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed to create {path}: {e}')
                )

    def _setup_network(self):
        """Setup libvirt NAT network."""
        self.stdout.write('Setting up NAT network...')

        from addons.kvm.networking import NetworkManager

        network_mgr = NetworkManager()

        # Check if network already exists
        if network_mgr.check_network_exists('webops-nat'):
            self.stdout.write(self.style.WARNING('  ! Network already exists'))
            return

        # Create network
        success = network_mgr.create_nat_network('webops-nat')

        if success:
            self.stdout.write(self.style.SUCCESS('  ✓ NAT network created'))
        else:
            self.stdout.write(
                self.style.ERROR('  ✗ Failed to create NAT network')
            )

    def _create_defaults(self):
        """Create default VM plans and OS templates."""
        self.stdout.write('Creating default plans and templates...')

        from addons.kvm.models import VMPlan, OSTemplate
        from decimal import Decimal

        # Default VM plans
        plans = [
            {
                'name': 'micro',
                'display_name': 'Micro',
                'description': 'Minimal resources for testing and development',
                'vcpus': 1,
                'memory_mb': 1024,  # 1GB
                'disk_gb': 20,
                'hourly_price': Decimal('0.0050'),
                'sort_order': 1,
            },
            {
                'name': 'small',
                'display_name': 'Small',
                'description': 'Small production workloads',
                'vcpus': 2,
                'memory_mb': 2048,  # 2GB
                'disk_gb': 40,
                'hourly_price': Decimal('0.0100'),
                'sort_order': 2,
            },
            {
                'name': 'medium',
                'display_name': 'Medium',
                'description': 'Medium production workloads',
                'vcpus': 4,
                'memory_mb': 4096,  # 4GB
                'disk_gb': 80,
                'hourly_price': Decimal('0.0200'),
                'sort_order': 3,
            },
            {
                'name': 'large',
                'display_name': 'Large',
                'description': 'Large production workloads',
                'vcpus': 8,
                'memory_mb': 8192,  # 8GB
                'disk_gb': 160,
                'hourly_price': Decimal('0.0400'),
                'sort_order': 4,
            },
        ]

        for plan_data in plans:
            plan, created = VMPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(f'  ✓ Created plan: {plan.display_name}')
            else:
                self.stdout.write(f'  • Plan exists: {plan.display_name}')

        # Note: OS templates need to be created manually or downloaded
        self.stdout.write(
            self.style.WARNING(
                '\nNote: OS templates must be created manually or downloaded.\n'
                'Use the create_os_template command to add templates.'
            )
        )
