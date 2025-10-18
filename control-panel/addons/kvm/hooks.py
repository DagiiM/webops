"""
KVM Addon Hooks

Integrates with WebOps addon system to handle deployment lifecycle.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def pre_deployment(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-deployment hook for KVM VMs.

    Validates configuration and checks resource availability.

    Args:
        context: Deployment context with:
            - deployment: Deployment model instance
            - deployment_type: Type of deployment ('kvm')
            - config: Deployment configuration

    Returns:
        Dictionary with success status and any modifications
    """
    from .models import VMPlan, OSTemplate, VMQuota
    from .resource_manager import ResourceManager

    deployment = context.get('deployment')

    # Only handle KVM deployments
    if deployment.deployment_type != 'kvm':
        return {'success': True, 'skip': True}

    logger.info(f"KVM pre-deployment hook for: {deployment.name}")

    try:
        kvm_config = deployment.kvm_config or {}

        # Validate required configuration
        plan_name = kvm_config.get('plan')
        template_name = kvm_config.get('template')
        ssh_keys = kvm_config.get('ssh_keys', [])

        if not plan_name:
            return {'success': False, 'error': 'No VM plan specified'}

        if not template_name:
            return {'success': False, 'error': 'No OS template specified'}

        # Validate plan exists
        try:
            plan = VMPlan.objects.get(name=plan_name, is_active=True)
        except VMPlan.DoesNotExist:
            return {'success': False, 'error': f'VM plan not found: {plan_name}'}

        # Validate template exists
        try:
            template = OSTemplate.objects.get(name=template_name, is_active=True)
        except OSTemplate.DoesNotExist:
            return {'success': False, 'error': f'OS template not found: {template_name}'}

        # Check user quota
        quota = VMQuota.objects.filter(user=deployment.user).first()
        if quota:
            can_create, msg = quota.check_can_create(plan)
            if not can_create:
                return {'success': False, 'error': f'Quota exceeded: {msg}'}

        # Check resource availability
        resource_manager = ResourceManager()
        compute_node = resource_manager.find_available_node(plan)

        if not compute_node:
            return {
                'success': False,
                'error': 'No compute node with sufficient resources available'
            }

        logger.info(f"Pre-deployment validation passed for {deployment.name}")

        return {
            'success': True,
            'metadata': {
                'compute_node_id': compute_node.id,
                'plan_id': plan.id,
                'template_id': template.id,
            }
        }

    except Exception as e:
        logger.error(f"Pre-deployment hook error: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def post_deployment(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-deployment hook for KVM VMs.

    Performs the actual VM deployment.

    Args:
        context: Deployment context

    Returns:
        Dictionary with success status
    """
    from .deployment_service import KVMDeploymentService
    from .models import VMPlan, OSTemplate

    deployment = context.get('deployment')

    # Only handle KVM deployments
    if deployment.deployment_type != 'kvm':
        return {'success': True, 'skip': True}

    logger.info(f"KVM post-deployment hook for: {deployment.name}")

    try:
        kvm_config = deployment.kvm_config or {}

        # Get plan and template
        plan = VMPlan.objects.get(name=kvm_config['plan'])
        template = OSTemplate.objects.get(name=kvm_config['template'])
        ssh_keys = kvm_config.get('ssh_keys', [])
        root_password = kvm_config.get('root_password')

        # Deploy VM
        service = KVMDeploymentService()
        result = service.deploy_vm(
            deployment=deployment,
            plan=plan,
            template=template,
            ssh_keys=ssh_keys,
            root_password=root_password,
        )

        if result['success']:
            # Update deployment with VM details
            deployment.port = result.get('ssh_port')  # For consistency with other deployments
            deployment.save()

            logger.info(f"VM deployed successfully: {result['vm_name']}")

            return {
                'success': True,
                'result': {
                    'vm_name': result['vm_name'],
                    'ip_address': result['ip_address'],
                    'ssh_command': result['ssh_command'],
                    'root_password': result['root_password'],
                }
            }
        else:
            return {'success': False, 'error': 'VM deployment failed'}

    except Exception as e:
        logger.error(f"Post-deployment hook error: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


def service_health_check(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Health check hook for KVM VMs.

    Checks VM state and updates deployment status.

    Args:
        context: Health check context

    Returns:
        Dictionary with health status
    """
    from .deployment_service import KVMDeploymentService
    from .models import VMDeployment

    deployment = context.get('deployment')

    # Only handle KVM deployments
    if deployment.deployment_type != 'kvm':
        return {'success': True, 'skip': True}

    try:
        vm_deployment = VMDeployment.objects.get(deployment=deployment)
        service = KVMDeploymentService()

        state = service.update_vm_state(vm_deployment)

        is_healthy = state == 'running'

        return {
            'success': True,
            'healthy': is_healthy,
            'state': state,
            'details': {
                'libvirt_state': state,
                'ip_address': vm_deployment.ip_address,
            }
        }

    except VMDeployment.DoesNotExist:
        return {'success': False, 'error': 'VM deployment not found'}
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return {'success': False, 'healthy': False, 'error': str(e)}


def pre_deletion(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-deletion hook for KVM VMs.

    Args:
        context: Deletion context

    Returns:
        Dictionary with success status
    """
    deployment = context.get('deployment')

    # Only handle KVM deployments
    if deployment.deployment_type != 'kvm':
        return {'success': True, 'skip': True}

    logger.info(f"KVM pre-deletion hook for: {deployment.name}")

    # Can add validation logic here (e.g., check for snapshots, backups)

    return {'success': True}


def post_deletion(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-deletion hook for KVM VMs.

    Cleans up VM resources.

    Args:
        context: Deletion context

    Returns:
        Dictionary with success status
    """
    from .deployment_service import KVMDeploymentService
    from .models import VMDeployment

    deployment = context.get('deployment')

    # Only handle KVM deployments
    if deployment.deployment_type != 'kvm':
        return {'success': True, 'skip': True}

    logger.info(f"KVM post-deletion hook for: {deployment.name}")

    try:
        vm_deployment = VMDeployment.objects.get(deployment=deployment)
        service = KVMDeploymentService()

        # Delete VM and cleanup resources
        success = service.delete_vm(vm_deployment, delete_disk=True)

        if success:
            # Delete VMDeployment record
            vm_deployment.delete()
            logger.info(f"VM cleanup completed for: {deployment.name}")
            return {'success': True}
        else:
            return {'success': False, 'error': 'Failed to delete VM'}

    except VMDeployment.DoesNotExist:
        # Already deleted, consider it success
        logger.warning(f"VM deployment already deleted: {deployment.name}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Post-deletion hook error: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}


# Register hooks with WebOps addon system
def register_hooks():
    """Register KVM hooks with the addon system."""
    try:
        from apps.addons.registry import hook_registry

        hook_registry.register('pre_deployment', priority=50)(pre_deployment)
        hook_registry.register('post_deployment', priority=50)(post_deployment)
        hook_registry.register('service_health_check', priority=50)(service_health_check)
        hook_registry.register('pre_deletion', priority=50)(pre_deletion)
        hook_registry.register('post_deletion', priority=50)(post_deletion)

        logger.info("KVM addon hooks registered successfully")

    except ImportError as e:
        logger.warning(f"Could not register hooks (addon system not available): {e}")
