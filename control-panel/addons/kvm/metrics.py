"""
Prometheus Metrics Export

Exposes KVM addon metrics in Prometheus format.
"""

import logging
from typing import Dict, List
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta

from .models import (
    ComputeNode,
    VMDeployment,
    VMUsageRecord,
    VMPlan,
)

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """
    Generate Prometheus-format metrics for KVM resources.
    """

    @staticmethod
    def generate_metrics() -> str:
        """
        Generate all metrics in Prometheus exposition format.

        Returns:
            String in Prometheus text format
        """
        lines = []

        # Add header
        lines.append("# Prometheus metrics for WebOps KVM Addon")
        lines.append("")

        # Node metrics
        lines.extend(PrometheusMetrics._node_metrics())
        lines.append("")

        # VM metrics
        lines.extend(PrometheusMetrics._vm_metrics())
        lines.append("")

        # Resource metrics
        lines.extend(PrometheusMetrics._resource_metrics())
        lines.append("")

        # Usage metrics
        lines.extend(PrometheusMetrics._usage_metrics())
        lines.append("")

        return '\n'.join(lines)

    @staticmethod
    def _node_metrics() -> List[str]:
        """Generate compute node metrics."""
        lines = []

        # Total nodes
        lines.append("# HELP kvm_nodes_total Total number of compute nodes")
        lines.append("# TYPE kvm_nodes_total gauge")
        total_nodes = ComputeNode.objects.count()
        lines.append(f"kvm_nodes_total {total_nodes}")

        # Active nodes
        lines.append("# HELP kvm_nodes_active Number of active compute nodes")
        lines.append("# TYPE kvm_nodes_active gauge")
        active_nodes = ComputeNode.objects.filter(is_active=True).count()
        lines.append(f"kvm_nodes_active {active_nodes}")

        # Per-node resources
        lines.append("# HELP kvm_node_vcpus_total Total vCPUs per node")
        lines.append("# TYPE kvm_node_vcpus_total gauge")

        lines.append("# HELP kvm_node_vcpus_available Available vCPUs per node")
        lines.append("# TYPE kvm_node_vcpus_available gauge")

        lines.append("# HELP kvm_node_memory_mb_total Total memory in MB per node")
        lines.append("# TYPE kvm_node_memory_mb_total gauge")

        lines.append("# HELP kvm_node_memory_mb_available Available memory in MB per node")
        lines.append("# TYPE kvm_node_memory_mb_available gauge")

        for node in ComputeNode.objects.all():
            labels = f'node="{node.hostname}"'

            lines.append(f'kvm_node_vcpus_total{{{labels}}} {node.total_vcpus}')
            lines.append(f'kvm_node_vcpus_available{{{labels}}} {node.available_vcpus()}')
            lines.append(f'kvm_node_memory_mb_total{{{labels}}} {node.total_memory_mb}')
            lines.append(f'kvm_node_memory_mb_available{{{labels}}} {node.available_memory_mb()}')

        return lines

    @staticmethod
    def _vm_metrics() -> List[str]:
        """Generate VM metrics."""
        lines = []

        # Total VMs
        lines.append("# HELP kvm_vms_total Total number of VMs")
        lines.append("# TYPE kvm_vms_total gauge")
        total_vms = VMDeployment.objects.count()
        lines.append(f"kvm_vms_total {total_vms}")

        # VMs by state
        lines.append("# HELP kvm_vms_by_state Number of VMs by state")
        lines.append("# TYPE kvm_vms_by_state gauge")

        state_counts = VMDeployment.objects.values('libvirt_state').annotate(
            count=Count('id')
        )

        for state in state_counts:
            state_name = state['libvirt_state'] or 'unknown'
            count = state['count']
            lines.append(f'kvm_vms_by_state{{state="{state_name}"}} {count}')

        # VMs by plan
        lines.append("# HELP kvm_vms_by_plan Number of VMs by plan")
        lines.append("# TYPE kvm_vms_by_plan gauge")

        plan_counts = VMDeployment.objects.values('vm_plan__name').annotate(
            count=Count('id')
        )

        for plan in plan_counts:
            plan_name = plan['vm_plan__name']
            count = plan['count']
            lines.append(f'kvm_vms_by_plan{{plan="{plan_name}"}} {count}')

        # VMs per node
        lines.append("# HELP kvm_vms_per_node Number of VMs per node")
        lines.append("# TYPE kvm_vms_per_node gauge")

        node_counts = VMDeployment.objects.values(
            'compute_node__hostname'
        ).annotate(count=Count('id'))

        for node in node_counts:
            hostname = node['compute_node__hostname']
            count = node['count']
            lines.append(f'kvm_vms_per_node{{node="{hostname}"}} {count}')

        return lines

    @staticmethod
    def _resource_metrics() -> List[str]:
        """Generate resource utilization metrics."""
        lines = []

        # Calculate total allocated resources
        total_vcpus = VMDeployment.objects.aggregate(
            Sum('vcpus')
        )['vcpus__sum'] or 0

        total_memory = VMDeployment.objects.aggregate(
            Sum('memory_mb')
        )['memory_mb__sum'] or 0

        total_disk = VMDeployment.objects.aggregate(
            Sum('disk_gb')
        )['disk_gb__sum'] or 0

        # Allocated resources
        lines.append("# HELP kvm_resources_allocated_vcpus Total allocated vCPUs")
        lines.append("# TYPE kvm_resources_allocated_vcpus gauge")
        lines.append(f"kvm_resources_allocated_vcpus {total_vcpus}")

        lines.append("# HELP kvm_resources_allocated_memory_mb Total allocated memory in MB")
        lines.append("# TYPE kvm_resources_allocated_memory_mb gauge")
        lines.append(f"kvm_resources_allocated_memory_mb {total_memory}")

        lines.append("# HELP kvm_resources_allocated_disk_gb Total allocated disk in GB")
        lines.append("# TYPE kvm_resources_allocated_disk_gb gauge")
        lines.append(f"kvm_resources_allocated_disk_gb {total_disk}")

        # Available resources (cluster-wide)
        total_available_vcpus = sum(
            node.available_vcpus()
            for node in ComputeNode.objects.filter(is_active=True)
        )

        total_available_memory = sum(
            node.available_memory_mb()
            for node in ComputeNode.objects.filter(is_active=True)
        )

        lines.append("# HELP kvm_resources_available_vcpus Total available vCPUs")
        lines.append("# TYPE kvm_resources_available_vcpus gauge")
        lines.append(f"kvm_resources_available_vcpus {total_available_vcpus}")

        lines.append("# HELP kvm_resources_available_memory_mb Total available memory in MB")
        lines.append("# TYPE kvm_resources_available_memory_mb gauge")
        lines.append(f"kvm_resources_available_memory_mb {total_available_memory}")

        return lines

    @staticmethod
    def _usage_metrics() -> List[str]:
        """Generate usage/billing metrics."""
        lines = []

        # Usage from last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)

        usage_last_hour = VMUsageRecord.objects.filter(
            timestamp__gte=one_hour_ago
        ).aggregate(
            total_cost=Sum('cost'),
            count=Count('id')
        )

        cost = float(usage_last_hour['total_cost'] or 0)
        count = usage_last_hour['count']

        lines.append("# HELP kvm_usage_cost_last_hour Total usage cost in last hour")
        lines.append("# TYPE kvm_usage_cost_last_hour gauge")
        lines.append(f"kvm_usage_cost_last_hour {cost}")

        lines.append("# HELP kvm_usage_records_last_hour Number of usage records in last hour")
        lines.append("# TYPE kvm_usage_records_last_hour gauge")
        lines.append(f"kvm_usage_records_last_hour {count}")

        # Total cost today
        today = timezone.now().date()
        usage_today = VMUsageRecord.objects.filter(
            timestamp__date=today
        ).aggregate(total_cost=Sum('cost'))

        cost_today = float(usage_today['total_cost'] or 0)

        lines.append("# HELP kvm_usage_cost_today Total usage cost today")
        lines.append("# TYPE kvm_usage_cost_today gauge")
        lines.append(f"kvm_usage_cost_today {cost_today}")

        return lines


@require_http_methods(["GET"])
def prometheus_metrics_view(request):
    """
    HTTP endpoint for Prometheus to scrape metrics.

    URL: /kvm/metrics
    """
    try:
        metrics = PrometheusMetrics.generate_metrics()
        return HttpResponse(metrics, content_type='text/plain; charset=utf-8')
    except Exception as e:
        logger.error(f"Error generating metrics: {e}", exc_info=True)
        return HttpResponse(
            f"# Error generating metrics: {str(e)}\n",
            content_type='text/plain; charset=utf-8',
            status=500
        )


class MetricsCollector:
    """
    Custom metrics collector for more advanced Prometheus integration.

    Can be used with prometheus_client library for more features.
    """

    def __init__(self):
        try:
            from prometheus_client import Gauge, Counter, Histogram
            self.has_client = True

            # Define metrics
            self.vm_count = Gauge(
                'kvm_vms_total',
                'Total number of VMs'
            )

            self.vm_state = Gauge(
                'kvm_vms_by_state',
                'Number of VMs by state',
                ['state']
            )

            self.node_resources = Gauge(
                'kvm_node_resources',
                'Node resource metrics',
                ['node', 'resource', 'type']  # type: total/available
            )

            self.deployment_duration = Histogram(
                'kvm_deployment_duration_seconds',
                'VM deployment duration',
                buckets=[30, 60, 120, 300, 600, 1800]  # 30s to 30min
            )

        except ImportError:
            logger.warning("prometheus_client not installed, advanced metrics unavailable")
            self.has_client = False

    def collect(self):
        """Collect and update metrics."""
        if not self.has_client:
            return

        # Update VM count
        self.vm_count.set(VMDeployment.objects.count())

        # Update VM states
        state_counts = VMDeployment.objects.values('libvirt_state').annotate(
            count=Count('id')
        )
        for state in state_counts:
            self.vm_state.labels(state=state['libvirt_state'] or 'unknown').set(
                state['count']
            )

        # Update node resources
        for node in ComputeNode.objects.all():
            self.node_resources.labels(
                node=node.hostname,
                resource='vcpus',
                type='total'
            ).set(node.total_vcpus)

            self.node_resources.labels(
                node=node.hostname,
                resource='vcpus',
                type='available'
            ).set(node.available_vcpus())

            self.node_resources.labels(
                node=node.hostname,
                resource='memory_mb',
                type='total'
            ).set(node.total_memory_mb)

            self.node_resources.labels(
                node=node.hostname,
                resource='memory_mb',
                type='available'
            ).set(node.available_memory_mb())


# Global collector instance
metrics_collector = MetricsCollector()
