"""
KVM Deployment Service

High-level service for managing VM deployments.
Orchestrates libvirt, cloud-init, networking, and storage.
"""

import logging
import subprocess
import secrets
import string
from pathlib import Path
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone

from .libvirt_manager import LibvirtManager
from .cloud_init import CloudInitGenerator
from .models import (
    ComputeNode,
    VMPlan,
    OSTemplate,
    VMDeployment,
    VMQuota,
)
from .resource_manager import ResourceManager
from .networking import NetworkManager

logger = logging.getLogger(__name__)


class KVMDeploymentService:
    """
    Manages the complete VM deployment lifecycle.
    """

    def __init__(self):
        self.resource_manager = ResourceManager()
        self.network_manager = NetworkManager()
        self.cloud_init = CloudInitGenerator()

    def deploy_vm(
        self,
        deployment,
        plan: VMPlan,
        template: OSTemplate,
        ssh_keys: list[str],
        root_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deploy a new virtual machine.

        Args:
            deployment: Deployment model instance
            plan: VM resource plan
            template: OS template
            ssh_keys: List of SSH public keys
            root_password: Root password (auto-generated if None)

        Returns:
            Dictionary with deployment details

        Raises:
            Exception: If deployment fails
        """
        logger.info(f"Starting VM deployment: {deployment.name}")

        try:
            # 1. Check user quota
            user = deployment.user
            quota = self._get_or_create_quota(user)
            can_create, msg = quota.check_can_create(plan)
            if not can_create:
                raise Exception(f"Quota exceeded: {msg}")

            # 2. Find available compute node
            compute_node = self.resource_manager.find_available_node(plan)
            if not compute_node:
                raise Exception("No compute node with sufficient resources")

            # 3. Generate VM name and password
            vm_name = f"webops-vm-{deployment.id}"
            if root_password is None:
                root_password = self._generate_password()

            # 4. Allocate networking resources
            ssh_port = self.network_manager.allocate_ssh_port()
            vnc_port = self.network_manager.allocate_vnc_port()

            # 5. Create disk from template
            disk_path = self._create_vm_disk(
                deployment_id=deployment.id,
                template=template,
                size_gb=plan.disk_gb,
            )

            # 6. Generate cloud-init configuration
            logger.info(f"Generating cloud-init configuration for {vm_name}")
            with LibvirtManager(compute_node.libvirt_uri) as libvirt_mgr:
                # Generate domain XML to get MAC address
                xml = libvirt_mgr.generate_domain_xml(
                    vm_name=vm_name,
                    vcpus=plan.vcpus,
                    memory_mb=plan.memory_mb,
                    disk_path=disk_path,
                    vnc_port=vnc_port,
                )

                # Extract MAC address from XML
                from lxml import etree
                root = etree.fromstring(xml)
                mac_elem = root.xpath("//interface/mac")[0]
                mac_address = mac_elem.get('address')

                # Generate cloud-init config
                cloud_init_config = self.cloud_init.generate_default_config(
                    vm_name=vm_name,
                    vm_uuid=deployment.uuid,
                    ssh_keys=ssh_keys,
                    root_password=root_password,
                    mac_address=mac_address,
                )

                # Inject cloud-init into disk
                success = self.cloud_init.inject_into_disk(
                    disk_path=disk_path,
                    user_data=cloud_init_config['user_data'],
                    meta_data=cloud_init_config['meta_data'],
                    network_config=cloud_init_config['network_config'],
                )

                if not success:
                    raise Exception("Failed to inject cloud-init configuration")

                # 7. Define and start VM
                logger.info(f"Defining VM {vm_name} in libvirt")
                domain = libvirt_mgr.define_domain(xml)

                logger.info(f"Starting VM {vm_name}")
                libvirt_mgr.start_domain(vm_name)

                # 8. Wait for IP address
                logger.info(f"Waiting for {vm_name} to get IP address...")
                ip_address = libvirt_mgr.get_domain_ip(vm_name, timeout=120)

                if not ip_address:
                    logger.warning(f"Could not get IP for {vm_name}, will be available later")

                # 9. Setup NAT port forwarding
                if ip_address and ssh_port:
                    self.network_manager.setup_nat_forwarding(
                        host_ip=compute_node.hostname,
                        host_port=ssh_port,
                        guest_ip=ip_address,
                        guest_port=22,
                        protocol='tcp',
                    )

                # 10. Create VMDeployment record
                from apps.core.utils.encryption import encrypt_value
                encrypted_password = encrypt_value(root_password, settings.ENCRYPTION_KEY)

                vm_deployment = VMDeployment.objects.create(
                    deployment=deployment,
                    compute_node=compute_node,
                    vm_plan=plan,
                    os_template=template,
                    vm_uuid=domain.UUIDString(),
                    vm_name=vm_name,
                    vcpus=plan.vcpus,
                    memory_mb=plan.memory_mb,
                    disk_gb=plan.disk_gb,
                    ip_address=ip_address,
                    mac_address=mac_address,
                    ssh_port=ssh_port,
                    vnc_port=vnc_port,
                    disk_path=disk_path,
                    root_password=encrypted_password,
                    ssh_public_keys=ssh_keys,
                    libvirt_state='running',
                )

                logger.info(f"VM deployment completed: {vm_name}")

                return {
                    'success': True,
                    'vm_name': vm_name,
                    'vm_uuid': domain.UUIDString(),
                    'ip_address': ip_address,
                    'ssh_port': ssh_port,
                    'ssh_command': vm_deployment.get_ssh_command(),
                    'root_password': root_password,
                }

        except Exception as e:
            logger.error(f"VM deployment failed: {e}", exc_info=True)
            # Cleanup on failure
            try:
                if 'vm_name' in locals():
                    self._cleanup_failed_deployment(vm_name, compute_node)
            except Exception as cleanup_err:
                logger.error(f"Cleanup failed: {cleanup_err}")

            raise

    def stop_vm(self, vm_deployment: VMDeployment, force: bool = False) -> bool:
        """Stop a VM."""
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                success = libvirt_mgr.stop_domain(vm_deployment.vm_name, force=force)
                if success:
                    vm_deployment.libvirt_state = 'stopped'
                    vm_deployment.save()
                return success
        except Exception as e:
            logger.error(f"Failed to stop VM {vm_deployment.vm_name}: {e}")
            return False

    def start_vm(self, vm_deployment: VMDeployment) -> bool:
        """Start a stopped VM."""
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                success = libvirt_mgr.start_domain(vm_deployment.vm_name)
                if success:
                    # Update IP if changed
                    ip_address = libvirt_mgr.get_domain_ip(vm_deployment.vm_name, timeout=60)
                    if ip_address and ip_address != vm_deployment.ip_address:
                        # Update NAT forwarding
                        self.network_manager.remove_nat_forwarding(
                            vm_deployment.compute_node.hostname,
                            vm_deployment.ssh_port,
                        )
                        self.network_manager.setup_nat_forwarding(
                            host_ip=vm_deployment.compute_node.hostname,
                            host_port=vm_deployment.ssh_port,
                            guest_ip=ip_address,
                            guest_port=22,
                            protocol='tcp',
                        )
                        vm_deployment.ip_address = ip_address

                    vm_deployment.libvirt_state = 'running'
                    vm_deployment.save()
                return success
        except Exception as e:
            logger.error(f"Failed to start VM {vm_deployment.vm_name}: {e}")
            return False

    def restart_vm(self, vm_deployment: VMDeployment) -> bool:
        """Restart a VM."""
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                return libvirt_mgr.restart_domain(vm_deployment.vm_name)
        except Exception as e:
            logger.error(f"Failed to restart VM {vm_deployment.vm_name}: {e}")
            return False

    def delete_vm(self, vm_deployment: VMDeployment, delete_disk: bool = True) -> bool:
        """Delete a VM and cleanup resources."""
        try:
            logger.info(f"Deleting VM: {vm_deployment.vm_name}")

            # Remove NAT forwarding
            if vm_deployment.ssh_port:
                self.network_manager.remove_nat_forwarding(
                    vm_deployment.compute_node.hostname,
                    vm_deployment.ssh_port,
                )

            # Delete VM from libvirt
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                success = libvirt_mgr.delete_domain(
                    vm_deployment.vm_name,
                    delete_disk=delete_disk,
                )

            if success:
                # Free allocated ports
                self.network_manager.free_ssh_port(vm_deployment.ssh_port)
                self.network_manager.free_vnc_port(vm_deployment.vnc_port)

                logger.info(f"VM deleted successfully: {vm_deployment.vm_name}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete VM {vm_deployment.vm_name}: {e}")
            return False

    def update_vm_state(self, vm_deployment: VMDeployment) -> str:
        """Update and return current VM state."""
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                state = libvirt_mgr.get_domain_state(vm_deployment.vm_name)
                vm_deployment.libvirt_state = state
                vm_deployment.save(update_fields=['libvirt_state', 'updated_at'])
                return state
        except Exception as e:
            logger.error(f"Failed to update state for {vm_deployment.vm_name}: {e}")
            return 'unknown'

    def create_snapshot(
        self,
        vm_deployment: VMDeployment,
        snapshot_name: str,
        description: str = "",
    ) -> bool:
        """Create a VM snapshot."""
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as libvirt_mgr:
                snapshot_xml = libvirt_mgr.create_snapshot(
                    vm_deployment.vm_name,
                    snapshot_name,
                    description,
                )

                # Record snapshot in database
                from .models import VMSnapshot
                VMSnapshot.objects.create(
                    vm_deployment=vm_deployment,
                    name=snapshot_name,
                    description=description,
                    snapshot_xml=snapshot_xml,
                    disk_size_mb=0,  # TODO: Calculate actual size
                )

                return True
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return False

    def _create_vm_disk(
        self,
        deployment_id: int,
        template: OSTemplate,
        size_gb: int,
    ) -> str:
        """
        Create a VM disk from template using copy-on-write.

        Args:
            deployment_id: Deployment ID
            template: OS template
            size_gb: Disk size in GB

        Returns:
            Path to created disk
        """
        storage_path = Path(settings.KVM_STORAGE_PATH) / f"vm-{deployment_id}"
        storage_path.mkdir(parents=True, exist_ok=True)

        disk_path = storage_path / "disk.qcow2"

        # Create disk with backing file (COW)
        cmd = [
            'qemu-img', 'create',
            '-f', 'qcow2',
            '-F', 'qcow2',
            '-b', template.image_path,
            str(disk_path),
            f"{size_gb}G",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Created disk: {disk_path}")
            return str(disk_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create disk: {e.stderr}")
            raise

    def _generate_password(self, length: int = 16) -> str:
        """Generate a random secure password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _get_or_create_quota(self, user) -> VMQuota:
        """Get or create quota for user."""
        quota, created = VMQuota.objects.get_or_create(user=user)
        if created:
            logger.info(f"Created default quota for user {user.username}")
        return quota

    def _cleanup_failed_deployment(self, vm_name: str, compute_node: ComputeNode):
        """Cleanup resources after failed deployment."""
        logger.info(f"Cleaning up failed deployment: {vm_name}")
        try:
            with LibvirtManager(compute_node.libvirt_uri) as libvirt_mgr:
                libvirt_mgr.delete_domain(vm_name, delete_disk=True)
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
