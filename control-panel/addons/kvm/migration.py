"""
VM Migration Service

Handles VM migration between compute nodes (offline and live migration).
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional
from .models import ComputeNode, VMDeployment
from .libvirt_manager import LibvirtManager

logger = logging.getLogger(__name__)


class VMMigrationService:
    """
    Manages VM migration between compute nodes.
    """

    def __init__(self):
        pass

    def migrate_vm(
        self,
        vm_deployment: VMDeployment,
        target_node: ComputeNode,
        live: bool = False,
    ) -> bool:
        """
        Migrate a VM to a different compute node.

        Args:
            vm_deployment: VM to migrate
            target_node: Destination compute node
            live: If True, perform live migration (no downtime)

        Returns:
            True if successful

        Raises:
            Exception: If migration fails
        """
        source_node = vm_deployment.compute_node

        if source_node == target_node:
            raise ValueError("Source and target nodes are the same")

        # Check if target node has resources
        if not target_node.can_fit_plan(vm_deployment.vm_plan):
            raise Exception("Target node does not have sufficient resources")

        logger.info(
            f"Starting {'live' if live else 'offline'} migration: "
            f"{vm_deployment.vm_name} from {source_node.hostname} to {target_node.hostname}"
        )

        if live:
            return self._live_migrate(vm_deployment, source_node, target_node)
        else:
            return self._offline_migrate(vm_deployment, source_node, target_node)

    def _offline_migrate(
        self,
        vm_deployment: VMDeployment,
        source_node: ComputeNode,
        target_node: ComputeNode,
    ) -> bool:
        """
        Offline migration (VM must be stopped).

        Steps:
        1. Stop VM on source
        2. Copy disk to target
        3. Copy VM definition XML
        4. Start VM on target
        5. Cleanup source
        """
        try:
            # 1. Stop VM on source
            logger.info(f"Stopping VM on source node")
            with LibvirtManager(source_node.libvirt_uri) as src_mgr:
                state = src_mgr.get_domain_state(vm_deployment.vm_name)
                if state == 'running':
                    src_mgr.stop_domain(vm_deployment.vm_name, force=False)

                # Get VM XML
                domain = src_mgr.conn.lookupByName(vm_deployment.vm_name)
                xml = domain.XMLDesc()

            # 2. Copy disk to target node
            logger.info(f"Copying disk to target node")
            source_disk = vm_deployment.disk_path
            target_disk_path = source_disk.replace(
                str(source_node.hostname),
                str(target_node.hostname)
            )

            # Use rsync or scp for disk copy
            if target_node.hostname not in ['localhost', '127.0.0.1']:
                self._copy_disk_remote(source_disk, target_node.hostname, target_disk_path)
            else:
                # Local copy (same host, different paths)
                self._copy_disk_local(source_disk, target_disk_path)

            # 3. Define VM on target
            logger.info(f"Defining VM on target node")
            # Update XML with new disk path if needed
            xml = xml.replace(source_disk, target_disk_path)

            with LibvirtManager(target_node.libvirt_uri) as tgt_mgr:
                tgt_mgr.define_domain(xml)

                # 4. Start VM on target
                logger.info(f"Starting VM on target node")
                tgt_mgr.start_domain(vm_deployment.vm_name)

                # Wait for IP
                new_ip = tgt_mgr.get_domain_ip(vm_deployment.vm_name, timeout=120)

            # 5. Update database
            vm_deployment.compute_node = target_node
            vm_deployment.disk_path = target_disk_path
            if new_ip:
                vm_deployment.ip_address = new_ip
            vm_deployment.save()

            # 6. Cleanup source (optional, can be deferred)
            logger.info(f"Cleaning up source node")
            with LibvirtManager(source_node.libvirt_uri) as src_mgr:
                src_mgr.delete_domain(vm_deployment.vm_name, delete_disk=True)

            logger.info(f"Migration completed successfully")
            return True

        except Exception as e:
            logger.error(f"Offline migration failed: {e}", exc_info=True)
            # TODO: Rollback on failure
            raise

    def _live_migrate(
        self,
        vm_deployment: VMDeployment,
        source_node: ComputeNode,
        target_node: ComputeNode,
    ) -> bool:
        """
        Live migration (VM stays running).

        Requires:
        - Shared storage OR block migration
        - Network connectivity between nodes
        - Compatible CPU/hypervisor versions
        """
        try:
            logger.info(f"Starting live migration")

            # Build migration URI
            # For local migration, both nodes must be accessible
            if target_node.hostname in ['localhost', '127.0.0.1']:
                dest_uri = 'qemu:///system'
            else:
                dest_uri = f'qemu+ssh://{target_node.hostname}/system'

            with LibvirtManager(source_node.libvirt_uri) as src_mgr:
                domain = src_mgr.conn.lookupByName(vm_deployment.vm_name)

                # Perform live migration
                # VIR_MIGRATE_LIVE = 1
                # VIR_MIGRATE_PEER2PEER = 2
                # VIR_MIGRATE_TUNNELLED = 4
                # VIR_MIGRATE_PERSIST_DEST = 8
                # VIR_MIGRATE_UNDEFINE_SOURCE = 16
                # VIR_MIGRATE_NON_SHARED_DISK = 64 (for block migration)

                import libvirt
                flags = (
                    libvirt.VIR_MIGRATE_LIVE |
                    libvirt.VIR_MIGRATE_PEER2PEER |
                    libvirt.VIR_MIGRATE_PERSIST_DEST |
                    libvirt.VIR_MIGRATE_UNDEFINE_SOURCE |
                    libvirt.VIR_MIGRATE_NON_SHARED_DISK  # Block migration
                )

                logger.info(f"Migrating to {dest_uri}")
                new_dom = domain.migrate(
                    dest_uri=dest_uri,
                    flags=flags,
                    dname=None,  # Keep same name
                    uri=None,
                    bandwidth=0,  # No bandwidth limit
                )

                if new_dom:
                    logger.info("Live migration successful")

                    # Update database
                    vm_deployment.compute_node = target_node
                    vm_deployment.save()

                    return True
                else:
                    raise Exception("Live migration returned None")

        except Exception as e:
            logger.error(f"Live migration failed: {e}", exc_info=True)
            raise

    def _copy_disk_remote(
        self,
        source_path: str,
        target_host: str,
        target_path: str,
    ):
        """Copy disk to remote host using rsync."""
        # Ensure target directory exists
        target_dir = str(Path(target_path).parent)
        subprocess.run(
            ['ssh', target_host, 'mkdir', '-p', target_dir],
            check=True,
            capture_output=True,
        )

        # Copy disk with rsync (faster, resumable)
        cmd = [
            'rsync',
            '-avz',
            '--progress',
            source_path,
            f"{target_host}:{target_path}",
        ]

        logger.info(f"Copying disk: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    def _copy_disk_local(self, source_path: str, target_path: str):
        """Copy disk locally."""
        import shutil

        target_dir = Path(target_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Copying disk locally: {source_path} -> {target_path}")
        shutil.copy2(source_path, target_path)

    def can_migrate(
        self,
        vm_deployment: VMDeployment,
        target_node: ComputeNode,
    ) -> tuple[bool, str]:
        """
        Check if VM can be migrated to target node.

        Returns:
            (can_migrate, reason)
        """
        # Check if target is different from source
        if vm_deployment.compute_node == target_node:
            return False, "Target is the same as source"

        # Check target node is active
        if not target_node.is_active:
            return False, "Target node is not active"

        # Check resource availability
        if not target_node.can_fit_plan(vm_deployment.vm_plan):
            return False, "Target node has insufficient resources"

        # Check network connectivity (could ping target)
        # TODO: Add actual connectivity check

        return True, "OK"
