"""
Prometheus metrics for addon system monitoring.

Provides metrics for:
- Addon installation/uninstallation operations
- Execution success/failure rates
- Operation durations
- System health
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps
from typing import Callable

from .logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Metric Definitions
# ============================================================================

# Operation counters
addon_operations_total = Counter(
    'webops_addon_operations_total',
    'Total number of addon operations',
    ['operation', 'addon_type', 'status']
)

addon_installations_total = Counter(
    'webops_addon_installations_total',
    'Total number of addon installations',
    ['addon_name', 'status']
)

addon_uninstallations_total = Counter(
    'webops_addon_uninstallations_total',
    'Total number of addon uninstallations',
    ['addon_name', 'status']
)

addon_configurations_total = Counter(
    'webops_addon_configurations_total',
    'Total number of addon configurations',
    ['addon_name', 'status']
)

# Duration histograms
addon_operation_duration_seconds = Histogram(
    'webops_addon_operation_duration_seconds',
    'Duration of addon operations in seconds',
    ['operation', 'addon_name'],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)
)

addon_install_duration_seconds = Histogram(
    'webops_addon_install_duration_seconds',
    'Duration of addon installations in seconds',
    ['addon_name'],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600)
)

# Current state gauges
addon_installed_count = Gauge(
    'webops_addon_installed_count',
    'Number of currently installed addons',
    ['addon_type']
)

addon_healthy_count = Gauge(
    'webops_addon_healthy_count',
    'Number of healthy addons'
)

addon_unhealthy_count = Gauge(
    'webops_addon_unhealthy_count',
    'Number of unhealthy addons'
)

addon_degraded_count = Gauge(
    'webops_addon_degraded_count',
    'Number of degraded addons'
)

# Execution gauges
addon_executions_running = Gauge(
    'webops_addon_executions_running',
    'Number of currently running addon operations',
    ['operation']
)

# Error counters
addon_errors_total = Counter(
    'webops_addon_errors_total',
    'Total number of addon errors',
    ['addon_name', 'operation', 'error_type']
)

# Dependency resolution metrics
dependency_resolution_total = Counter(
    'webops_addon_dependency_resolution_total',
    'Number of dependency resolutions',
    ['status']
)

dependency_resolution_duration_seconds = Histogram(
    'webops_addon_dependency_resolution_duration_seconds',
    'Duration of dependency resolution in seconds',
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
)

# Cache metrics
cache_operations_total = Counter(
    'webops_addon_cache_operations_total',
    'Total number of cache operations',
    ['operation', 'status']
)

# Rate limiting metrics
rate_limit_exceeded_total = Counter(
    'webops_addon_rate_limit_exceeded_total',
    'Total number of rate limit exceeded events',
    ['endpoint']
)

# Permission check metrics
permission_checks_total = Counter(
    'webops_addon_permission_checks_total',
    'Total number of permission checks',
    ['permission', 'status']
)

# Validation metrics
validation_errors_total = Counter(
    'webops_addon_validation_errors_total',
    'Total number of validation errors',
    ['error_type']
)

# System info
addon_system_info = Info(
    'webops_addon_system',
    'Information about the addon system'
)


# ============================================================================
# Metric Helper Functions
# ============================================================================

def record_operation(operation: str, addon_type: str, status: str):
    """Record an addon operation."""
    addon_operations_total.labels(
        operation=operation,
        addon_type=addon_type,
        status=status
    ).inc()


def record_installation(addon_name: str, success: bool):
    """Record an installation attempt."""
    status = 'success' if success else 'failure'
    addon_installations_total.labels(
        addon_name=addon_name,
        status=status
    ).inc()


def record_uninstallation(addon_name: str, success: bool):
    """Record an uninstallation attempt."""
    status = 'success' if success else 'failure'
    addon_uninstallations_total.labels(
        addon_name=addon_name,
        status=status
    ).inc()


def record_configuration(addon_name: str, success: bool):
    """Record a configuration attempt."""
    status = 'success' if success else 'failure'
    addon_configurations_total.labels(
        addon_name=addon_name,
        status=status
    ).inc()


def record_error(addon_name: str, operation: str, error_type: str):
    """Record an error."""
    addon_errors_total.labels(
        addon_name=addon_name,
        operation=operation,
        error_type=error_type
    ).inc()


def record_validation_error(error_type: str):
    """Record a validation error."""
    validation_errors_total.labels(error_type=error_type).inc()


def record_rate_limit_exceeded(endpoint: str):
    """Record a rate limit exceeded event."""
    rate_limit_exceeded_total.labels(endpoint=endpoint).inc()


def record_permission_check(permission: str, allowed: bool):
    """Record a permission check."""
    status = 'allowed' if allowed else 'denied'
    permission_checks_total.labels(
        permission=permission,
        status=status
    ).inc()


def record_cache_operation(operation: str, success: bool):
    """Record a cache operation."""
    status = 'hit' if success else 'miss'
    cache_operations_total.labels(
        operation=operation,
        status=status
    ).inc()


# ============================================================================
# Decorator for Timing Operations
# ============================================================================

def track_operation_duration(operation: str, addon_name: str = None):
    """
    Decorator to track operation duration.

    Usage:
        @track_operation_duration('install', addon_name='postgresql')
        def install_addon(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record duration
                name = addon_name or kwargs.get('name', 'unknown')
                addon_operation_duration_seconds.labels(
                    operation=operation,
                    addon_name=name
                ).observe(duration)

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Still record duration even on error
                name = addon_name or kwargs.get('name', 'unknown')
                addon_operation_duration_seconds.labels(
                    operation=operation,
                    addon_name=name
                ).observe(duration)

                raise

        return wrapper
    return decorator


# ============================================================================
# Metric Update Functions
# ============================================================================

def update_addon_counts():
    """Update current addon count gauges from database."""
    from .repositories import system_addon_repository

    try:
        stats = system_addon_repository.get_statistics()

        # Update gauges
        addon_installed_count.labels(addon_type='system').set(
            stats.get('installed', 0)
        )

        addon_healthy_count.set(stats.get('healthy', 0))
        addon_unhealthy_count.set(stats.get('unhealthy', 0))
        addon_degraded_count.set(stats.get('degraded', 0))

    except Exception as e:
        logger.error(
            'Failed to update addon count metrics',
            exc_info=e,
            operation='update_addon_counts'
        )


def update_execution_counts():
    """Update running execution count gauges."""
    from .repositories import execution_repository

    try:
        running_executions = execution_repository.get_running()

        # Count by operation type
        operation_counts = {}
        for execution in running_executions:
            op = execution.operation
            operation_counts[op] = operation_counts.get(op, 0) + 1

        # Update gauges
        for operation in ['install', 'uninstall', 'configure', 'health_check']:
            count = operation_counts.get(operation, 0)
            addon_executions_running.labels(operation=operation).set(count)

    except Exception as e:
        logger.error(
            'Failed to update execution count metrics',
            exc_info=e,
            operation='update_execution_counts'
        )


def initialize_metrics():
    """Initialize metrics with system information."""
    addon_system_info.info({
        'version': '1.0.0',
        'component': 'addon_system',
    })

    logger.info(
        'Initialized Prometheus metrics',
        component='addon_system',
        version='1.0.0'
    )


# ============================================================================
# Context Manager for Tracking Executions
# ============================================================================

class MetricsContext:
    """Context manager for tracking operation metrics."""

    def __init__(self, operation: str, addon_name: str):
        """
        Initialize metrics context.

        Args:
            operation: Operation name (install, uninstall, etc.)
            addon_name: Name of addon
        """
        self.operation = operation
        self.addon_name = addon_name
        self.start_time = None

    def __enter__(self):
        """Start tracking."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record metrics on exit."""
        duration = time.time() - self.start_time

        # Record duration
        addon_operation_duration_seconds.labels(
            operation=self.operation,
            addon_name=self.addon_name
        ).observe(duration)

        # Record success/failure
        success = exc_type is None
        if self.operation == 'install':
            record_installation(self.addon_name, success)
        elif self.operation == 'uninstall':
            record_uninstallation(self.addon_name, success)
        elif self.operation == 'configure':
            record_configuration(self.addon_name, success)

        # Record error if failed
        if exc_type is not None:
            error_type = exc_type.__name__
            record_error(self.addon_name, self.operation, error_type)

        return False  # Don't suppress exceptions
