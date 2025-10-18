"""
VM Resize Service

Handles VM resource resizing/upgrading to different plans.
"""

import logging
from .models import VMDeployment, VMPlan
from .libvirt_manager import LibvirtManager
import subprocess

logger = logging.getLogger(__name__)


class VMResizeService:
    """
    Manages VM resource resizing operations.
    """

    def resize_vm(
        self,
        vm_deployment: VMDeployment,
        new_plan: VMPlan,
        resize_disk: bool = False,
    ) -> bool:
        """
        Resize a VM to a different plan.

        Args:
            vm_deployment: VM to resize
            new_plan: Target VM plan
            resize_disk: If True, also resize disk (requires downtime)

        Returns:
            True if successful

        Notes:
            - CPU/RAM changes require VM restart
            - Disk resize requires VM to be stopped
        """
        try:
            logger.info(
                f"Resizing VM {vm_deployment.vm_name} from "
                f"{vm_deployment.vm_plan.name} to {new_plan.name}"
            )

            # Check quota
            from apps.core.models import VMQuota
            quota = VMQuota.objects.filter(user=vm_deployment.deployment.user).first()
            if quota:
                # Temporarily "free" current resources
                old_vcpus = vm_deployment.vcpus
                old_memory = vm_deployment.memory_mb
                old_disk = vm_deployment.disk_gb

                # Check new allocation
                can_create, msg = quota.check_can_create(new_plan)
                if not can_create:
                    return False, f"Quota exceeded: {msg}"

            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
                domain = mgr.conn.lookupByName(vm_deployment.vm_name)
                is_running = domain.isActive() == 1

                # 1. Resize vCPUs
                if new_plan.vcpus != vm_deployment.vcpus:
                    logger.info(f"Resizing vCPUs: {vm_deployment.vcpus} -> {new_plan.vcpus}")
                    self._resize_vcpus(mgr, vm_deployment, new_plan.vcpus, is_running)

                # 2. Resize memory
                if new_plan.memory_mb != vm_deployment.memory_mb:
                    logger.info(f"Resizing memory: {vm_deployment.memory_mb}MB -> {new_plan.memory_mb}MB")
                    self._resize_memory(mgr, vm_deployment, new_plan.memory_mb, is_running)

                # 3. Resize disk (if requested and different)
                if resize_disk and new_plan.disk_gb > vm_deployment.disk_gb:
                    logger.info(f"Resizing disk: {vm_deployment.disk_gb}GB -> {new_plan.disk_gb}GB")

                    # Disk resize requires VM to be stopped
                    if is_running:
                        logger.info("Stopping VM for disk resize...")
                        mgr.stop_domain(vm_deployment.vm_name)

                    self._resize_disk(vm_deployment, new_plan.disk_gb)

                    # Restart if it was running
                    if is_running:
                        logger.info("Restarting VM...")
                        mgr.start_domain(vm_deployment.vm_name)

            # Update database
            vm_deployment.vm_plan = new_plan
            vm_deployment.vcpus = new_plan.vcpus
            vm_deployment.memory_mb = new_plan.memory_mb
            if resize_disk:
                vm_deployment.disk_gb = new_plan.disk_gb
            vm_deployment.save()

            logger.info(f"VM resize completed successfully")
            return True

        except Exception as e:
            logger.error(f"VM resize failed: {e}", exc_info=True)
            raise

    def _resize_vcpus(
        self,
        mgr: LibvirtManager,
        vm_deployment: VMDeployment,
        new_vcpus: int,
        is_running: bool,
    ):
        """Resize vCPUs (hot-plug if running, cold if stopped)."""
        import libvirt

        domain = mgr.conn.lookupByName(vm_deployment.vm_name)

        if is_running:
            # Hot-plug (live resize)
            try:
                domain.setVcpusFlags(new_vcpus, libvirt.VIR_DOMAIN_AFFECT_LIVE)
            except libvirt.libvirtError as e:
                logger.warning(f"Hot vCPU resize not supported, will require restart: {e}")
                # Fall back to config change
                domain.setVcpusFlags(new_vcpus, libvirt.VIR_DOMAIN_AFFECT_CONFIG)
                logger.info("vCPU change will take effect after VM restart")
        else:
            # Cold resize (VM stopped)
            domain.setVcpusFlags(new_vcpus, libvirt.VIR_DOMAIN_AFFECT_CONFIG)

    def _resize_memory(
        self,
        mgr: LibvirtManager,
        vm_deployment: VMDeployment,
        new_memory_mb: int,
        is_running: bool,
    ):
        """Resize memory (hot-plug if supported)."""
        import libvirt

        domain = mgr.conn.lookupByName(vm_deployment.vm_name)
        new_memory_kb = new_memory_mb * 1024

        if is_running:
            # Try hot-plug (may not be supported)
            try:
                domain.setMemoryFlags(new_memory_kb, libvirt.VIR_DOMAIN_AFFECT_LIVE)
            except libvirt.libvirtError as e:
                logger.warning(f"Hot memory resize not supported, will require restart: {e}")
                # Fall back to config change
                domain.setMemoryFlags(new_memory_kb, libvirt.VIR_DOMAIN_AFFECT_CONFIG)
                domain.setMaxMemory(new_memory_kb)
                logger.info("Memory change will take effect after VM restart")
        else:
            # Cold resize
            domain.setMemoryFlags(new_memory_kb, libvirt.VIR_DOMAIN_AFFECT_CONFIG)
            domain.setMaxMemory(new_memory_kb)

    def _resize_disk(self, vm_deployment: VMDeployment, new_size_gb: int):
        """
        Resize disk image (VM must be stopped).

        Uses qemu-img to resize the qcow2 image.
        """
        disk_path = vm_deployment.disk_path

        try:
            # Resize qcow2 image
            cmd = [
                'qemu-img', 'resize',
                disk_path,
                f'{new_size_gb}G',
            ]

            logger.info(f"Resizing disk: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            logger.info(f"Disk resized to {new_size_gb}GB")
            logger.info("Note: Guest OS may need to resize filesystem manually")

        except subprocess.CalledProcessError as e:
            logger.error(f"Disk resize failed: {e.stderr}")
            raise

    def can_downsize(self, current_plan: VMPlan, target_plan: VMPlan) -> tuple[bool, str]:
        """
        Check if downsize is possible/safe.

        Generally, downsizing is risky and not recommended.
        """
        if target_plan.vcpus < current_plan.vcpus:
            return False, "vCPU downsizing may cause performance issues"

        if target_plan.memory_mb < current_plan.memory_mb:
            return False, "Memory downsizing may cause VM instability"

        if target_plan.disk_gb < current_plan.disk_gb:
            return False, "Disk shrinking is not supported (data loss risk)"

        return True, "OK"

    def estimate_downtime(
        self,
        vm_deployment: VMDeployment,
        new_plan: VMPlan,
        resize_disk: bool,
    ) -> dict:
        """
        Estimate downtime for resize operation.

        Returns:
            Dictionary with downtime estimate
        """
        downtime_seconds = 0
        requires_restart = False
        notes = []

        # vCPU change
        if new_plan.vcpus != vm_deployment.vcpus:
            # Hot-plug may work, but not guaranteed
            notes.append("vCPU change may require restart (10-30 seconds)")
            requires_restart = True

        # Memory change
        if new_plan.memory_mb != vm_deployment.memory_mb:
            notes.append("Memory change may require restart (10-30 seconds)")
            requires_restart = True

        # Disk resize
        if resize_disk and new_plan.disk_gb > vm_deployment.disk_gb:
            downtime_seconds += 60  # Estimated 1 minute for disk resize
            notes.append("Disk resize requires VM to be stopped (~1 minute)")
            requires_restart = True

        if requires_restart:
            downtime_seconds += 20  # Restart time

        return {
            'downtime_seconds': downtime_seconds,
            'requires_restart': requires_restart,
            'notes': notes,
        }
