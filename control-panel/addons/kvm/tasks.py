"""
KVM Addon Celery Tasks

Background tasks for VM management, monitoring, and metering.
"""

import logging
from celery import shared_task
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def record_vm_usage(self):
    """
    Periodic task to record VM usage for billing.

    Runs hourly to capture VM state and resource usage.
    """
    from .models import VMDeployment, VMUsageRecord

    logger.info("Starting VM usage recording")

    try:
        # Get all VM deployments
        vms = VMDeployment.objects.select_related(
            'deployment',
            'vm_plan',
            'compute_node'
        ).filter(
            deployment__status__in=['running', 'stopped']
        )

        records_created = 0

        for vm in vms:
            try:
                # Get current VM state
                from .deployment_service import KVMDeploymentService
                service = KVMDeploymentService()
                state = service.update_vm_state(vm)

                # Calculate cost (only charge for running VMs)
                cost = Decimal('0.0000')
                uptime_seconds = 3600  # Default to full hour

                if state == 'running':
                    cost = vm.vm_plan.hourly_price
                    # TODO: Get actual uptime from libvirt

                # Create usage record
                VMUsageRecord.objects.create(
                    vm_deployment=vm,
                    timestamp=timezone.now(),
                    vcpus=vm.vcpus,
                    memory_mb=vm.memory_mb,
                    disk_gb=vm.disk_gb,
                    state=state,
                    uptime_seconds=uptime_seconds,
                    hourly_rate=vm.vm_plan.hourly_price,
                    cost=cost,
                )

                records_created += 1

            except Exception as e:
                logger.error(f"Error recording usage for VM {vm.vm_name}: {e}")
                continue

        logger.info(f"Recorded usage for {records_created} VMs")

        return {
            'success': True,
            'records_created': records_created,
        }

    except Exception as exc:
        logger.error(f"VM usage recording failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def update_vm_states(self):
    """
    Periodic task to update VM states from libvirt.

    Runs every 5 minutes to keep VM states in sync.
    """
    from .models import VMDeployment
    from .deployment_service import KVMDeploymentService

    logger.info("Starting VM state update")

    try:
        vms = VMDeployment.objects.select_related('compute_node', 'deployment').all()
        service = KVMDeploymentService()

        updated = 0
        errors = 0

        for vm in vms:
            try:
                state = service.update_vm_state(vm)
                logger.debug(f"Updated state for {vm.vm_name}: {state}")
                updated += 1
            except Exception as e:
                logger.error(f"Error updating state for {vm.vm_name}: {e}")
                errors += 1

        logger.info(f"Updated {updated} VM states ({errors} errors)")

        return {
            'success': True,
            'updated': updated,
            'errors': errors,
        }

    except Exception as exc:
        logger.error(f"VM state update failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def cleanup_orphaned_vms(self):
    """
    Periodic task to clean up orphaned VMs.

    Finds VMs in libvirt that don't have corresponding database records.
    """
    from .models import ComputeNode, VMDeployment
    from .libvirt_manager import LibvirtManager

    logger.info("Starting orphaned VM cleanup")

    try:
        orphaned_count = 0

        for node in ComputeNode.objects.filter(is_active=True):
            try:
                with LibvirtManager(node.libvirt_uri) as libvirt_mgr:
                    # Get all domains from libvirt
                    all_domains = libvirt_mgr.list_domains()

                    # Get known VM names from database
                    known_vms = set(
                        VMDeployment.objects.filter(compute_node=node)
                        .values_list('vm_name', flat=True)
                    )

                    # Find orphaned VMs (in libvirt but not in DB)
                    for domain_name in all_domains:
                        if domain_name.startswith('webops-vm-') and domain_name not in known_vms:
                            logger.warning(f"Found orphaned VM: {domain_name}")
                            # TODO: Decide whether to auto-delete or just log
                            # For safety, just log for now
                            orphaned_count += 1

            except Exception as e:
                logger.error(f"Error checking node {node.hostname}: {e}")
                continue

        logger.info(f"Found {orphaned_count} orphaned VMs")

        return {
            'success': True,
            'orphaned_count': orphaned_count,
        }

    except Exception as exc:
        logger.error(f"Orphaned VM cleanup failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def sync_compute_node_info(self):
    """
    Periodic task to sync compute node information from hypervisor.

    Updates CPU, memory, and other node stats.
    """
    from .models import ComputeNode
    from .libvirt_manager import LibvirtManager

    logger.info("Starting compute node info sync")

    try:
        synced = 0

        for node in ComputeNode.objects.filter(is_active=True):
            try:
                with LibvirtManager(node.libvirt_uri) as libvirt_mgr:
                    info = libvirt_mgr.get_hypervisor_info()

                    # Update node if info changed
                    if info:
                        # Could update total resources if they changed
                        # For now, just log
                        logger.debug(f"Node {node.hostname}: {info}")
                        synced += 1

            except Exception as e:
                logger.error(f"Error syncing node {node.hostname}: {e}")
                continue

        logger.info(f"Synced {synced} compute nodes")

        return {
            'success': True,
            'synced': synced,
        }

    except Exception as exc:
        logger.error(f"Compute node sync failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def auto_cleanup_stopped_vms(self, days_stopped: int = 30):
    """
    Periodic task to cleanup VMs that have been stopped for too long.

    Args:
        days_stopped: Number of days a VM can be stopped before cleanup
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import VMDeployment
    from .deployment_service import KVMDeploymentService

    logger.info(f"Starting auto-cleanup of VMs stopped for {days_stopped}+ days")

    try:
        cutoff_date = timezone.now() - timedelta(days=days_stopped)

        # Find VMs stopped before cutoff date
        stopped_vms = VMDeployment.objects.filter(
            deployment__status='stopped',
            updated_at__lt=cutoff_date,
        )

        cleaned_count = 0
        service = KVMDeploymentService()

        for vm in stopped_vms:
            try:
                logger.info(f"Auto-cleaning VM: {vm.vm_name} (stopped since {vm.updated_at})")

                # Delete VM
                success = service.delete_vm(vm, delete_disk=True)

                if success:
                    # Update deployment status
                    vm.deployment.status = 'deleted'
                    vm.deployment.save()

                    # Delete VMDeployment record
                    vm.delete()

                    cleaned_count += 1

            except Exception as e:
                logger.error(f"Error cleaning VM {vm.vm_name}: {e}")
                continue

        logger.info(f"Auto-cleaned {cleaned_count} VMs")

        return {
            'success': True,
            'cleaned_count': cleaned_count,
        }

    except Exception as exc:
        logger.error(f"Auto-cleanup failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
