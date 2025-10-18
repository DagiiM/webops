"""
Resource Manager

Handles resource allocation and tracking across compute nodes.
"""

import logging
from typing import Optional
from .models import ComputeNode, VMPlan

logger = logging.getLogger(__name__)


class ResourceManager:
    """
    Manages compute resource allocation.
    """

    def find_available_node(self, plan: VMPlan) -> Optional[ComputeNode]:
        """
        Find a compute node with sufficient resources for a VM plan.

        Uses a simple best-fit algorithm (node with least available resources that can fit).

        Args:
            plan: VM resource plan

        Returns:
            ComputeNode or None if no suitable node found
        """
        # Get all active nodes
        nodes = ComputeNode.objects.filter(is_active=True)

        suitable_nodes = []
        for node in nodes:
            if node.can_fit_plan(plan):
                # Calculate "score" based on remaining resources after allocation
                remaining_vcpus = node.available_vcpus() - plan.vcpus
                remaining_memory = node.available_memory_mb() - plan.memory_mb
                remaining_disk = node.available_disk_gb() - plan.disk_gb

                # Lower score = less wasted space (better fit)
                score = remaining_vcpus + (remaining_memory / 1024) + remaining_disk

                suitable_nodes.append((node, score))

        if not suitable_nodes:
            logger.warning(f"No compute node available for plan: {plan.name}")
            return None

        # Sort by score (best fit first)
        suitable_nodes.sort(key=lambda x: x[1])

        selected_node = suitable_nodes[0][0]
        logger.info(f"Selected compute node: {selected_node.hostname} for plan {plan.name}")

        return selected_node

    def get_cluster_stats(self) -> dict:
        """
        Get aggregate statistics for all compute nodes.

        Returns:
            Dictionary with cluster resource statistics
        """
        from django.db.models import Sum

        nodes = ComputeNode.objects.filter(is_active=True)

        total_vcpus = sum(node.total_vcpus for node in nodes)
        total_memory_mb = sum(node.total_memory_mb for node in nodes)
        total_disk_gb = sum(node.total_disk_gb for node in nodes)

        available_vcpus = sum(node.available_vcpus() for node in nodes)
        available_memory_mb = sum(node.available_memory_mb() for node in nodes)
        available_disk_gb = sum(node.available_disk_gb() for node in nodes)

        allocated_vcpus = total_vcpus - available_vcpus
        allocated_memory_mb = total_memory_mb - available_memory_mb
        allocated_disk_gb = total_disk_gb - available_disk_gb

        return {
            'nodes': {
                'total': nodes.count(),
                'active': nodes.filter(is_active=True).count(),
            },
            'vcpus': {
                'total': total_vcpus,
                'allocated': allocated_vcpus,
                'available': available_vcpus,
                'utilization_pct': (allocated_vcpus / total_vcpus * 100) if total_vcpus > 0 else 0,
            },
            'memory_mb': {
                'total': total_memory_mb,
                'allocated': allocated_memory_mb,
                'available': available_memory_mb,
                'utilization_pct': (allocated_memory_mb / total_memory_mb * 100) if total_memory_mb > 0 else 0,
            },
            'disk_gb': {
                'total': total_disk_gb,
                'allocated': allocated_disk_gb,
                'available': available_disk_gb,
                'utilization_pct': (allocated_disk_gb / total_disk_gb * 100) if total_disk_gb > 0 else 0,
            },
        }

    def get_node_vms(self, node: ComputeNode) -> dict:
        """
        Get VMs running on a specific node.

        Args:
            node: ComputeNode instance

        Returns:
            Dictionary with VM statistics
        """
        from .models import VMDeployment

        vms = VMDeployment.objects.filter(compute_node=node)

        running_vms = vms.filter(deployment__status='running')
        stopped_vms = vms.filter(deployment__status='stopped')

        return {
            'total': vms.count(),
            'running': running_vms.count(),
            'stopped': stopped_vms.count(),
            'vms': [
                {
                    'id': vm.id,
                    'name': vm.vm_name,
                    'status': vm.deployment.status,
                    'vcpus': vm.vcpus,
                    'memory_mb': vm.memory_mb,
                    'disk_gb': vm.disk_gb,
                }
                for vm in vms
            ],
        }
