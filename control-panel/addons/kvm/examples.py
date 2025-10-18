"""
KVM Addon Usage Examples

Demonstrates how to use the KVM addon programmatically.
"""

# Example 1: Deploy a VM
def deploy_example_vm(user):
    """Deploy a small Ubuntu VM for a user."""
    from apps.deployments.models import Deployment
    from addons.kvm.models import VMPlan, OSTemplate
    from addons.kvm.deployment_service import KVMDeploymentService

    # Create deployment record
    deployment = Deployment.objects.create(
        user=user,
        name='example-vm',
        deployment_type='kvm',
        kvm_config={
            'plan': 'small',
            'template': 'ubuntu-22.04',
            'ssh_keys': [
                'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDExample user@example.com'
            ],
        }
    )

    # Get plan and template
    plan = VMPlan.objects.get(name='small')
    template = OSTemplate.objects.get(name='ubuntu-22.04')

    # Deploy VM
    service = KVMDeploymentService()
    result = service.deploy_vm(
        deployment=deployment,
        plan=plan,
        template=template,
        ssh_keys=deployment.kvm_config['ssh_keys'],
    )

    print(f"VM deployed successfully!")
    print(f"Name: {result['vm_name']}")
    print(f"IP: {result['ip_address']}")
    print(f"SSH: {result['ssh_command']}")
    print(f"Password: {result['root_password']}")

    return deployment


# Example 2: Manage VM lifecycle
def vm_lifecycle_example(vm_deployment):
    """Demonstrate VM lifecycle operations."""
    from addons.kvm.deployment_service import KVMDeploymentService

    service = KVMDeploymentService()

    # Stop VM
    print("Stopping VM...")
    service.stop_vm(vm_deployment)

    # Wait a moment
    import time
    time.sleep(5)

    # Start VM
    print("Starting VM...")
    service.start_vm(vm_deployment)

    # Create snapshot
    print("Creating snapshot...")
    service.create_snapshot(
        vm_deployment,
        'backup-before-update',
        'Pre-update backup'
    )

    # Check state
    state = service.update_vm_state(vm_deployment)
    print(f"Current state: {state}")


# Example 3: Check user quota
def check_user_quota_example(user):
    """Check if user can create a VM."""
    from addons.kvm.models import VMQuota, VMPlan

    # Get or create quota
    quota, created = VMQuota.objects.get_or_create(user=user)

    # Check if user can create a medium VM
    plan = VMPlan.objects.get(name='medium')
    can_create, msg = quota.check_can_create(plan)

    if can_create:
        print(f"User {user.username} can create a {plan.display_name} VM")
    else:
        print(f"User {user.username} cannot create VM: {msg}")

    # Display current usage
    from django.db.models import Sum
    from addons.kvm.models import VMDeployment

    vms = VMDeployment.objects.filter(
        deployment__user=user,
        deployment__status__in=['running', 'stopped']
    )

    vm_count = vms.count()
    total_vcpus = vms.aggregate(Sum('vcpus'))['vcpus__sum'] or 0
    total_memory = vms.aggregate(Sum('memory_mb'))['memory_mb__sum'] or 0

    print(f"\nCurrent usage:")
    print(f"  VMs: {vm_count}/{quota.max_vms}")
    print(f"  vCPUs: {total_vcpus}/{quota.max_vcpus}")
    print(f"  Memory: {total_memory}MB/{quota.max_memory_mb}MB")


# Example 4: Get cluster statistics
def cluster_stats_example():
    """Display cluster resource statistics."""
    from addons.kvm.resource_manager import ResourceManager

    mgr = ResourceManager()
    stats = mgr.get_cluster_stats()

    print("Cluster Statistics:")
    print(f"\nNodes: {stats['nodes']['active']}/{stats['nodes']['total']} active")

    print(f"\nvCPUs:")
    print(f"  Total: {stats['vcpus']['total']}")
    print(f"  Allocated: {stats['vcpus']['allocated']}")
    print(f"  Available: {stats['vcpus']['available']}")
    print(f"  Utilization: {stats['vcpus']['utilization_pct']:.1f}%")

    print(f"\nMemory:")
    print(f"  Total: {stats['memory_mb']['total']} MB")
    print(f"  Allocated: {stats['memory_mb']['allocated']} MB")
    print(f"  Available: {stats['memory_mb']['available']} MB")
    print(f"  Utilization: {stats['memory_mb']['utilization_pct']:.1f}%")

    print(f"\nDisk:")
    print(f"  Total: {stats['disk_gb']['total']} GB")
    print(f"  Allocated: {stats['disk_gb']['allocated']} GB")
    print(f"  Available: {stats['disk_gb']['available']} GB")
    print(f"  Utilization: {stats['disk_gb']['utilization_pct']:.1f}%")


# Example 5: Calculate monthly cost
def calculate_vm_cost_example(vm_deployment, year, month):
    """Calculate monthly cost for a VM."""
    from addons.kvm.models import VMUsageRecord
    from django.db.models import Sum

    records = VMUsageRecord.objects.filter(
        vm_deployment=vm_deployment,
        timestamp__year=year,
        timestamp__month=month,
    )

    total_cost = records.aggregate(Sum('cost'))['cost__sum'] or 0
    running_hours = records.filter(state='running').count()

    print(f"VM: {vm_deployment.vm_name}")
    print(f"Period: {year}-{month:02d}")
    print(f"Running hours: {running_hours}")
    print(f"Total cost: ${total_cost:.2f}")

    return float(total_cost)


# Example 6: List user VMs
def list_user_vms_example(user):
    """List all VMs for a user."""
    from addons.kvm.models import VMDeployment

    vms = VMDeployment.objects.filter(deployment__user=user).select_related(
        'compute_node',
        'vm_plan',
        'os_template',
        'deployment',
    )

    print(f"VMs for {user.username}:")
    for vm in vms:
        print(f"\n{vm.vm_name}")
        print(f"  Plan: {vm.vm_plan.display_name}")
        print(f"  OS: {vm.os_template.display_name}")
        print(f"  State: {vm.libvirt_state}")
        print(f"  IP: {vm.ip_address or 'Pending'}")
        print(f"  SSH: {vm.get_ssh_command()}")
        print(f"  Node: {vm.compute_node.hostname}")


# Example 7: Create custom VM plan
def create_custom_plan_example():
    """Create a custom VM plan."""
    from addons.kvm.models import VMPlan
    from decimal import Decimal

    plan = VMPlan.objects.create(
        name='xlarge',
        display_name='Extra Large',
        description='High-performance workloads',
        vcpus=16,
        memory_mb=16384,  # 16GB
        disk_gb=320,
        hourly_price=Decimal('0.0800'),
        is_active=True,
        sort_order=5,
    )

    print(f"Created plan: {plan.display_name}")
    print(f"Resources: {plan.vcpus}vCPU, {plan.memory_gb:.1f}GB RAM, {plan.disk_gb}GB disk")
    print(f"Price: ${plan.hourly_price}/hour")

    return plan


# Example 8: Bulk deploy VMs
def bulk_deploy_example(user, count=5):
    """Deploy multiple VMs for a user."""
    from addons.kvm.models import VMPlan, OSTemplate
    from apps.deployments.models import Deployment
    from addons.kvm.deployment_service import KVMDeploymentService

    plan = VMPlan.objects.get(name='micro')
    template = OSTemplate.objects.get(name='ubuntu-22.04')
    service = KVMDeploymentService()

    ssh_key = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDExample user@example.com'

    deployed = []

    for i in range(count):
        deployment = Deployment.objects.create(
            user=user,
            name=f'bulk-vm-{i+1}',
            deployment_type='kvm',
            kvm_config={
                'plan': 'micro',
                'template': 'ubuntu-22.04',
                'ssh_keys': [ssh_key],
            }
        )

        try:
            result = service.deploy_vm(
                deployment=deployment,
                plan=plan,
                template=template,
                ssh_keys=[ssh_key],
            )
            deployed.append(result)
            print(f"✓ Deployed: {result['vm_name']}")
        except Exception as e:
            print(f"✗ Failed to deploy VM {i+1}: {e}")

    print(f"\nDeployed {len(deployed)}/{count} VMs")
    return deployed


# Example 9: Monitor VM resources
def monitor_vm_resources_example(vm_deployment):
    """Monitor VM resource usage."""
    from addons.kvm.libvirt_manager import LibvirtManager

    with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
        info = mgr.get_domain_info(vm_deployment.vm_name)

        print(f"VM: {vm_deployment.vm_name}")
        print(f"State: {info['state']}")
        print(f"vCPUs: {info['vcpus']}")
        print(f"Memory: {info['memory_mb']} MB")
        print(f"CPU Time: {info['cpu_time_ns'] / 1e9:.2f} seconds")


# Example 10: Cleanup old VMs
def cleanup_old_vms_example(days=30):
    """Delete VMs stopped for more than X days."""
    from django.utils import timezone
    from datetime import timedelta
    from addons.kvm.models import VMDeployment
    from addons.kvm.deployment_service import KVMDeploymentService

    cutoff = timezone.now() - timedelta(days=days)

    old_vms = VMDeployment.objects.filter(
        deployment__status='stopped',
        updated_at__lt=cutoff,
    )

    service = KVMDeploymentService()
    deleted_count = 0

    for vm in old_vms:
        print(f"Deleting: {vm.vm_name} (stopped since {vm.updated_at})")
        success = service.delete_vm(vm, delete_disk=True)

        if success:
            vm.deployment.status = 'deleted'
            vm.deployment.save()
            vm.delete()
            deleted_count += 1

    print(f"Deleted {deleted_count} old VMs")
    return deleted_count


# Example usage in Django shell:
"""
from django.contrib.auth import get_user_model
from addons.kvm.examples import *

User = get_user_model()
user = User.objects.get(username='admin')

# Deploy a VM
deployment = deploy_example_vm(user)

# Check quota
check_user_quota_example(user)

# View cluster stats
cluster_stats_example()

# List user's VMs
list_user_vms_example(user)
"""
