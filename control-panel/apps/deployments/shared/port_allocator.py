"""
Port allocation for deployments.

Handles allocation and management of ports for deployments.
"""

from typing import Set
from django.db import transaction


def get_used_ports() -> Set[int]:
    """
    Get all currently used ports across all deployment types.

    Returns:
        Set of port numbers in use
    """
    from apps.deployments.models import BaseDeployment

    return set(
        BaseDeployment.objects
        .exclude(port__isnull=True)
        .values_list('port', flat=True)
    )


@transaction.atomic
def allocate_port(deployment, min_port: int = 8000, max_port: int = 9000) -> int:
    """
    Allocate a port for a deployment with race condition protection.

    Args:
        deployment: BaseDeployment instance
        min_port: Minimum port number
        max_port: Maximum port number

    Returns:
        Allocated port number

    Raises:
        ValueError: If no ports available
    """
    from apps.deployments.models import BaseDeployment

    if deployment.port:
        return deployment.port

    # Use SELECT FOR UPDATE to prevent race conditions
    with transaction.atomic():
        used_ports = set(
            BaseDeployment.objects
            .select_for_update()
            .exclude(port__isnull=True)
            .values_list('port', flat=True)
        )

        # Find first available port
        for port in range(min_port, max_port + 1):
            if port not in used_ports:
                deployment.port = port
                deployment.save(update_fields=['port'])
                return port

        raise ValueError(f"No ports available in range {min_port}-{max_port}")


def release_port(deployment) -> None:
    """
    Release a port back to the pool.

    Args:
        deployment: BaseDeployment instance
    """
    if deployment.port:
        deployment.port = None
        deployment.save(update_fields=['port'])


def is_port_available(port: int) -> bool:
    """
    Check if a specific port is available.

    Args:
        port: Port number to check

    Returns:
        True if port is available, False otherwise
    """
    used_ports = get_used_ports()
    return port not in used_ports


def get_port_usage_stats() -> dict:
    """
    Get statistics about port usage.

    Returns:
        Dictionary with usage statistics
    """
    from django.conf import settings

    used_ports = get_used_ports()
    min_port = getattr(settings, 'MIN_PORT', 8000)
    max_port = getattr(settings, 'MAX_PORT', 9000)

    total_available = max_port - min_port + 1
    total_used = len(used_ports)
    total_free = total_available - total_used

    return {
        'total_available': total_available,
        'total_used': total_used,
        'total_free': total_free,
        'usage_percentage': (total_used / total_available) * 100 if total_available > 0 else 0,
        'min_port': min_port,
        'max_port': max_port,
        'used_ports': sorted(list(used_ports)),
    }
