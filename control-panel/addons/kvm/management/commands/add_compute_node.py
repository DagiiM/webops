"""
Add Compute Node

Management command to register a compute node.
"""

from django.core.management.base import BaseCommand
from ...models import ComputeNode
from ...libvirt_manager import LibvirtManager
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add a compute node to WebOps'

    def add_arguments(self, parser):
        parser.add_argument('hostname', type=str, help='Hostname or IP address')
        parser.add_argument(
            '--libvirt-uri',
            type=str,
            default='qemu:///system',
            help='Libvirt connection URI (default: qemu:///system)',
        )
        parser.add_argument(
            '--auto-detect',
            action='store_true',
            help='Auto-detect resources from hypervisor',
        )
        parser.add_argument(
            '--vcpus',
            type=int,
            help='Total vCPUs (required if not using --auto-detect)',
        )
        parser.add_argument(
            '--memory-mb',
            type=int,
            help='Total RAM in MB (required if not using --auto-detect)',
        )
        parser.add_argument(
            '--disk-gb',
            type=int,
            help='Total disk in GB (required if not using --auto-detect)',
        )
        parser.add_argument(
            '--cpu-overcommit',
            type=float,
            default=2.0,
            help='CPU overcommit ratio (default: 2.0)',
        )
        parser.add_argument(
            '--memory-overcommit',
            type=float,
            default=1.0,
            help='Memory overcommit ratio (default: 1.0)',
        )

    def handle(self, *args, **options):
        hostname = options['hostname']
        libvirt_uri = options['libvirt_uri']

        self.stdout.write(f'Adding compute node: {hostname}')

        # Check if node already exists
        if ComputeNode.objects.filter(hostname=hostname).exists():
            self.stdout.write(
                self.style.ERROR(f'Compute node already exists: {hostname}')
            )
            return

        # Auto-detect or use provided values
        if options['auto_detect']:
            vcpus, memory_mb, disk_gb = self._detect_resources(hostname, libvirt_uri)
            if not vcpus:
                return
        else:
            vcpus = options.get('vcpus')
            memory_mb = options.get('memory_mb')
            disk_gb = options.get('disk_gb')

            if not all([vcpus, memory_mb, disk_gb]):
                self.stdout.write(
                    self.style.ERROR(
                        'Error: --vcpus, --memory-mb, and --disk-gb are required '
                        'when not using --auto-detect'
                    )
                )
                return

        # Create compute node
        node = ComputeNode.objects.create(
            hostname=hostname,
            libvirt_uri=libvirt_uri,
            total_vcpus=vcpus,
            total_memory_mb=memory_mb,
            total_disk_gb=disk_gb,
            cpu_overcommit_ratio=options['cpu_overcommit'],
            memory_overcommit_ratio=options['memory_overcommit'],
            is_active=True,
        )

        self.stdout.write(self.style.SUCCESS(f'✓ Compute node added: {hostname}'))
        self.stdout.write(f'  vCPUs: {vcpus}')
        self.stdout.write(f'  Memory: {memory_mb} MB ({memory_mb / 1024:.1f} GB)')
        self.stdout.write(f'  Disk: {disk_gb} GB')
        self.stdout.write(f'  CPU overcommit: {options["cpu_overcommit"]}x')
        self.stdout.write(f'  Memory overcommit: {options["memory_overcommit"]}x')

    def _detect_resources(self, hostname, libvirt_uri):
        """Auto-detect resources from hypervisor."""
        self.stdout.write('Auto-detecting resources...')

        try:
            with LibvirtManager(libvirt_uri) as libvirt_mgr:
                info = libvirt_mgr.get_hypervisor_info()

                if not info:
                    self.stdout.write(
                        self.style.ERROR('Failed to detect resources')
                    )
                    return None, None, None

                vcpus = info['cpus']
                memory_mb = info['memory_mb']

                # For disk, we can't reliably detect, so ask user or use default
                self.stdout.write(
                    self.style.WARNING(
                        'Note: Disk space cannot be auto-detected. '
                        'Please provide --disk-gb manually.'
                    )
                )
                return None, None, None

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to connect to hypervisor: {e}')
            )
            return None, None, None
