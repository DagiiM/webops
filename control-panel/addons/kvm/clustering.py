"""
Multi-Node Clustering

Manages cluster of compute nodes with load balancing and high availability.
"""

import logging
from typing import List, Optional, Dict, Any
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from .models import ComputeNode, VMPlan, VMDeployment
from .resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class ClusterManager:
    """
    Manages a cluster of compute nodes with intelligent scheduling.
    """

    CACHE_KEY_PREFIX = 'cluster:'
    NODE_HEALTH_TIMEOUT = 300  # 5 minutes

    def __init__(self):
        self.resource_manager = ResourceManager()

    def schedule_vm(
        self,
        plan: VMPlan,
        strategy: str = 'balanced',
        affinity_rules: Optional[Dict[str, Any]] = None,
    ) -> Optional[ComputeNode]:
        """
        Schedule a VM on the best compute node.

        Args:
            plan: VM resource plan
            strategy: Scheduling strategy ('balanced', 'packed', 'spread')
            affinity_rules: VM affinity/anti-affinity rules

        Returns:
            Selected compute node or None
        """
        nodes = ComputeNode.objects.filter(is_active=True)

        if not nodes:
            logger.error("No active compute nodes available")
            return None

        # Filter nodes that can fit the plan
        candidate_nodes = []
        for node in nodes:
            if node.can_fit_plan(plan):
                # Check node health
                if self.is_node_healthy(node):
                    candidate_nodes.append(node)

        if not candidate_nodes:
            logger.warning(f"No nodes have resources for plan: {plan.name}")
            return None

        # Apply affinity rules if provided
        if affinity_rules:
            candidate_nodes = self._apply_affinity_rules(
                candidate_nodes,
                affinity_rules
            )

        # Select node based on strategy
        if strategy == 'balanced':
            return self._schedule_balanced(candidate_nodes, plan)
        elif strategy == 'packed':
            return self._schedule_packed(candidate_nodes, plan)
        elif strategy == 'spread':
            return self._schedule_spread(candidate_nodes)
        else:
            logger.warning(f"Unknown strategy: {strategy}, using balanced")
            return self._schedule_balanced(candidate_nodes, plan)

    def _schedule_balanced(
        self,
        nodes: List[ComputeNode],
        plan: VMPlan
    ) -> ComputeNode:
        """
        Balanced scheduling: Distribute load evenly across nodes.

        Selects node with most available resources (percentage-wise).
        """
        best_node = None
        best_score = -1

        for node in nodes:
            # Calculate utilization percentages
            cpu_util = 1 - (node.available_vcpus() / (node.total_vcpus * node.cpu_overcommit_ratio))
            mem_util = 1 - (node.available_memory_mb() / (node.total_memory_mb * node.memory_overcommit_ratio))
            disk_util = 1 - (node.available_disk_gb() / node.total_disk_gb)

            # Average utilization (lower is better for balanced)
            avg_util = (cpu_util + mem_util + disk_util) / 3

            # Invert score (prefer nodes with lower utilization)
            score = 1 - avg_util

            if score > best_score:
                best_score = score
                best_node = node

        logger.info(f"Balanced scheduling selected: {best_node.hostname}")
        return best_node

    def _schedule_packed(
        self,
        nodes: List[ComputeNode],
        plan: VMPlan
    ) -> ComputeNode:
        """
        Packed scheduling: Fill up nodes before using new ones (bin packing).

        Selects node with least available resources (to pack VMs).
        """
        best_node = None
        min_available = float('inf')

        for node in nodes:
            # Calculate total available resources (normalized)
            available = (
                (node.available_vcpus() / node.total_vcpus) +
                (node.available_memory_mb() / node.total_memory_mb) +
                (node.available_disk_gb() / node.total_disk_gb)
            ) / 3

            if available < min_available:
                min_available = available
                best_node = node

        logger.info(f"Packed scheduling selected: {best_node.hostname}")
        return best_node

    def _schedule_spread(self, nodes: List[ComputeNode]) -> ComputeNode:
        """
        Spread scheduling: Distribute VMs across as many nodes as possible.

        Selects node with fewest VMs.
        """
        best_node = None
        min_vms = float('inf')

        for node in nodes:
            vm_count = VMDeployment.objects.filter(
                compute_node=node,
                deployment__status__in=['running', 'deploying']
            ).count()

            if vm_count < min_vms:
                min_vms = vm_count
                best_node = node

        logger.info(f"Spread scheduling selected: {best_node.hostname} ({min_vms} VMs)")
        return best_node

    def _apply_affinity_rules(
        self,
        nodes: List[ComputeNode],
        rules: Dict[str, Any]
    ) -> List[ComputeNode]:
        """
        Apply affinity/anti-affinity rules to filter nodes.

        Rules format:
        {
            'affinity': ['node1', 'node2'],  # Prefer these nodes
            'anti_affinity': ['node3'],       # Avoid these nodes
            'same_node_as': deployment_id,    # Same node as another VM
            'different_node_from': deployment_id,  # Different node
        }
        """
        filtered_nodes = nodes.copy()

        # Anti-affinity: Remove nodes from list
        if 'anti_affinity' in rules:
            avoid_hostnames = rules['anti_affinity']
            filtered_nodes = [
                n for n in filtered_nodes
                if n.hostname not in avoid_hostnames
            ]

        # Affinity: Prefer specific nodes
        if 'affinity' in rules:
            prefer_hostnames = rules['affinity']
            preferred = [
                n for n in filtered_nodes
                if n.hostname in prefer_hostnames
            ]
            if preferred:
                filtered_nodes = preferred

        # Same node as another VM
        if 'same_node_as' in rules:
            try:
                ref_vm = VMDeployment.objects.get(
                    deployment_id=rules['same_node_as']
                )
                filtered_nodes = [
                    n for n in filtered_nodes
                    if n == ref_vm.compute_node
                ]
            except VMDeployment.DoesNotExist:
                pass

        # Different node from another VM
        if 'different_node_from' in rules:
            try:
                ref_vm = VMDeployment.objects.get(
                    deployment_id=rules['different_node_from']
                )
                filtered_nodes = [
                    n for n in filtered_nodes
                    if n != ref_vm.compute_node
                ]
            except VMDeployment.DoesNotExist:
                pass

        return filtered_nodes if filtered_nodes else nodes

    def is_node_healthy(self, node: ComputeNode) -> bool:
        """
        Check if node is healthy and reachable.

        Uses cached health status with timeout.
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}health:{node.id}"
        cached_health = cache.get(cache_key)

        if cached_health is not None:
            return cached_health

        # Perform health check
        try:
            from .libvirt_manager import LibvirtManager

            with LibvirtManager(node.libvirt_uri) as mgr:
                info = mgr.get_hypervisor_info()
                is_healthy = bool(info and info.get('cpus'))

            # Cache result for 5 minutes
            cache.set(cache_key, is_healthy, self.NODE_HEALTH_TIMEOUT)
            return is_healthy

        except Exception as e:
            logger.error(f"Health check failed for {node.hostname}: {e}")
            cache.set(cache_key, False, 60)  # Cache failure for 1 minute
            return False

    def mark_node_maintenance(self, node: ComputeNode, maintenance: bool = True):
        """
        Mark node as in maintenance mode.

        When in maintenance, no new VMs will be scheduled on it.
        """
        node.is_active = not maintenance
        node.save()

        if maintenance:
            logger.info(f"Node {node.hostname} marked for maintenance")
        else:
            logger.info(f"Node {node.hostname} returned from maintenance")

    def evacuate_node(self, node: ComputeNode, target_node: Optional[ComputeNode] = None):
        """
        Migrate all VMs from a node (for maintenance).

        Args:
            node: Source node to evacuate
            target_node: Optional target node (auto-select if None)
        """
        from .migration import VMMigrationService

        vms = VMDeployment.objects.filter(
            compute_node=node,
            deployment__status='running'
        )

        if not vms:
            logger.info(f"No VMs to evacuate from {node.hostname}")
            return

        logger.info(f"Evacuating {vms.count()} VMs from {node.hostname}")

        migration_service = VMMigrationService()
        failed_migrations = []

        for vm in vms:
            try:
                # Find target node if not specified
                if not target_node:
                    # Find best node for this VM (excluding source)
                    candidates = ComputeNode.objects.filter(
                        is_active=True
                    ).exclude(id=node.id)

                    target = None
                    for candidate in candidates:
                        if candidate.can_fit_plan(vm.vm_plan):
                            target = candidate
                            break

                    if not target:
                        raise Exception("No target node available")
                else:
                    target = target_node

                # Migrate VM
                logger.info(f"Migrating {vm.vm_name} to {target.hostname}")
                migration_service.migrate_vm(vm, target, live=True)

            except Exception as e:
                logger.error(f"Failed to migrate {vm.vm_name}: {e}")
                failed_migrations.append((vm, str(e)))

        if failed_migrations:
            logger.warning(f"Evacuation completed with {len(failed_migrations)} failures")
        else:
            logger.info(f"Evacuation completed successfully")

    def rebalance_cluster(self, dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Rebalance VMs across cluster for optimal resource distribution.

        Args:
            dry_run: If True, only plan migrations without executing

        Returns:
            List of planned migrations
        """
        nodes = ComputeNode.objects.filter(is_active=True)

        if nodes.count() < 2:
            logger.info("Cluster has fewer than 2 nodes, nothing to rebalance")
            return []

        # Calculate current utilization per node
        node_stats = []
        for node in nodes:
            total_vcpus = node.total_vcpus * node.cpu_overcommit_ratio
            total_memory = node.total_memory_mb * node.memory_overcommit_ratio

            available_vcpus = node.available_vcpus()
            available_memory = node.available_memory_mb()

            cpu_util = 1 - (available_vcpus / total_vcpus) if total_vcpus > 0 else 0
            mem_util = 1 - (available_memory / total_memory) if total_memory > 0 else 0

            avg_util = (cpu_util + mem_util) / 2

            node_stats.append({
                'node': node,
                'utilization': avg_util,
                'cpu_util': cpu_util,
                'mem_util': mem_util,
            })

        # Sort by utilization
        node_stats.sort(key=lambda x: x['utilization'], reverse=True)

        # Calculate target utilization (average)
        target_util = sum(s['utilization'] for s in node_stats) / len(node_stats)

        logger.info(f"Target utilization: {target_util:.2%}")

        # Plan migrations from overloaded to underloaded nodes
        migrations = []
        max_migrations = 10  # Limit to prevent too many simultaneous moves

        for stat in node_stats:
            if stat['utilization'] > target_util + 0.1:  # 10% threshold
                # Node is overloaded, find VMs to move
                vms = VMDeployment.objects.filter(
                    compute_node=stat['node'],
                    deployment__status='running'
                ).order_by('vcpus')  # Start with smallest VMs

                for vm in vms:
                    if len(migrations) >= max_migrations:
                        break

                    # Find underloaded target
                    for target_stat in reversed(node_stats):
                        if target_stat['utilization'] < target_util - 0.1:
                            if target_stat['node'].can_fit_plan(vm.vm_plan):
                                migrations.append({
                                    'vm': vm,
                                    'source': stat['node'],
                                    'target': target_stat['node'],
                                    'reason': 'rebalance',
                                })
                                # Update target utilization estimate
                                # (simplified, doesn't account for overcommit)
                                target_stat['utilization'] += 0.05
                                break

        logger.info(f"Planned {len(migrations)} migrations for rebalancing")

        # Execute migrations if not dry run
        if not dry_run and migrations:
            from .migration import VMMigrationService
            migration_service = VMMigrationService()

            for plan in migrations:
                try:
                    logger.info(
                        f"Migrating {plan['vm'].vm_name} from "
                        f"{plan['source'].hostname} to {plan['target'].hostname}"
                    )
                    migration_service.migrate_vm(
                        plan['vm'],
                        plan['target'],
                        live=True
                    )
                except Exception as e:
                    logger.error(f"Rebalance migration failed: {e}")

        return migrations

    def get_cluster_health(self) -> Dict[str, Any]:
        """
        Get comprehensive cluster health metrics.

        Returns:
            Dictionary with cluster health information
        """
        nodes = ComputeNode.objects.all()
        active_nodes = nodes.filter(is_active=True)

        healthy_nodes = sum(1 for n in active_nodes if self.is_node_healthy(n))

        total_vms = VMDeployment.objects.filter(
            deployment__status__in=['running', 'stopped']
        ).count()

        running_vms = VMDeployment.objects.filter(
            deployment__status='running'
        ).count()

        stats = self.resource_manager.get_cluster_stats()

        return {
            'nodes': {
                'total': nodes.count(),
                'active': active_nodes.count(),
                'healthy': healthy_nodes,
                'maintenance': nodes.filter(is_active=False).count(),
            },
            'vms': {
                'total': total_vms,
                'running': running_vms,
                'stopped': total_vms - running_vms,
            },
            'resources': {
                'cpu_utilization': stats['vcpus']['utilization_pct'],
                'memory_utilization': stats['memory_mb']['utilization_pct'],
                'disk_utilization': stats['disk_gb']['utilization_pct'],
            },
            'status': 'healthy' if healthy_nodes == active_nodes.count() else 'degraded',
        }


class LoadBalancer:
    """
    Load balancer for distributing new deployments across cluster.
    """

    def __init__(self, strategy: str = 'balanced'):
        self.strategy = strategy
        self.cluster_manager = ClusterManager()

    def assign_node(self, plan: VMPlan, **kwargs) -> Optional[ComputeNode]:
        """
        Assign a compute node for new VM deployment.

        Wrapper around ClusterManager.schedule_vm with logging.
        """
        logger.info(f"Load balancer assigning node for plan: {plan.name}")

        node = self.cluster_manager.schedule_vm(
            plan,
            strategy=self.strategy,
            affinity_rules=kwargs.get('affinity_rules')
        )

        if node:
            logger.info(f"Assigned node: {node.hostname}")
        else:
            logger.error("Failed to assign node (no resources)")

        return node
