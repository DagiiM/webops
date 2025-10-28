"""
Celery tasks for service control and monitoring.

"Celery Tasks" section
Architecture: Background tasks for periodic monitoring and service management

This module implements:
- Periodic health checks
- Resource monitoring
- Automated service recovery
- Alert management
- Data cleanup
"""

from typing import Dict, Any
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta

logger = get_task_logger(__name__)


@shared_task(name='services.collect_system_metrics')
def collect_system_metrics() -> Dict[str, Any]:
    """
    Collect system resource metrics.

    Scheduled to run every 5 minutes via Celery Beat.

    Returns:
        Dict with metrics
    """
    from .monitoring import SystemMonitor

    try:
        monitor = SystemMonitor()
        metrics = monitor.collect_metrics()

        logger.info(
            f"Collected metrics: CPU={metrics.cpu_percent:.1f}%, "
            f"Memory={metrics.memory_percent:.1f}%, "
            f"Disk={metrics.disk_percent:.1f}%"
        )

        return {
            'success': True,
            'timestamp': metrics.created_at.isoformat(),
            'cpu_percent': metrics.cpu_percent,
            'memory_percent': metrics.memory_percent,
            'disk_percent': metrics.disk_percent
        }

    except Exception as exc:
        logger.error(f"Failed to collect metrics: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.check_all_service_statuses')
def check_all_service_statuses() -> Dict[str, Any]:
    """
    Check status of all deployment services.

    Scheduled to run every 2 minutes.

    Returns:
        Dict with status summary
    """
    from .monitoring import SystemMonitor
    from apps.deployments.models import BaseDeployment, ApplicationDeployment

    try:
        monitor = SystemMonitor()
        deployments = ApplicationDeployment.objects.all()

        results = []
        for deployment in deployments:
            status = monitor.check_service_status(deployment)
            results.append({
                'deployment': deployment.name,
                'status': status.status,
                'pid': status.pid
            })

        # Add Celery worker status
        celery_status = check_celery_health()
        if celery_status['healthy']:
            results.append({
                'deployment': 'Celery Worker',
                'status': 'running',
                'pid': None # PID is not directly available from check_celery_health
            })
        else:
            status = 'failed' if celery_status.get('error') else 'stopped'
            results.append({
                'deployment': 'Celery Worker',
                'status': status,
                'pid': None
            })

        running = len([r for r in results if r['status'] == 'running'])
        stopped = len([r for r in results if r['status'] == 'stopped'])
        failed = len([r for r in results if r['status'] == 'failed'])

        logger.info(
            f"Service status check: {running} running, {stopped} stopped, {failed} failed"
        )

        return {
            'success': True,
            'total': len(results),
            'running': running,
            'stopped': stopped,
            'failed': failed,
            'results': results
        }

    except Exception as exc:
        logger.error(f"Failed to check service statuses: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.perform_health_checks')
def perform_health_checks(auto_restart: bool = True) -> Dict[str, Any]:
    """
    Perform HTTP health checks on all running services.

    Args:
        auto_restart: Whether to automatically restart failed services

    Returns:
        Dict with health check results
    """
    from .service_controller import service_controller

    try:
        results = service_controller.perform_health_checks(auto_restart=auto_restart)

        logger.info(
            f"Health checks completed: {results['healthy']}/{results['total_checked']} healthy"
        )

        if auto_restart and results['restart_results']:
            logger.info(f"Auto-restarted {len(results['restart_results'])} services")

        return results

    except Exception as exc:
        logger.error(f"Failed to perform health checks: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.auto_recover_failed_services')
def auto_recover_failed_services() -> Dict[str, Any]:
    """
    Automatically recover failed services based on restart policies.

    Scheduled to run every 5 minutes.

    Returns:
        Dict with recovery results
    """
    from apps.deployments.models import BaseDeployment, ApplicationDeployment
    from .restart_policy import restart_policy_enforcer
    from .service_controller import service_controller
    import time

    try:
        failed_deployments = ApplicationDeployment.objects.filter(
            status=ApplicationDeployment.Status.FAILED
        )

        recovery_results = []

        for deployment in failed_deployments:
            # Check if we should restart based on policy
            should_restart, reason = restart_policy_enforcer.should_restart(deployment)

            if should_restart:
                # Calculate delay
                delay = restart_policy_enforcer.calculate_restart_delay(deployment)

                logger.info(
                    f"Auto-recovering {deployment.name} after {delay}s delay. Reason: {reason}"
                )

                # Apply delay
                time.sleep(delay)

                # Attempt restart
                started_at = timezone.now()
                result = service_controller.restart_service(deployment)

                # Record attempt
                restart_policy_enforcer.record_restart_attempt(
                    deployment=deployment,
                    success=result['success'],
                    delay_seconds=delay,
                    reason=reason,
                    error_message=result.get('error', '')
                )

                recovery_results.append({
                    'deployment': deployment.name,
                    'success': result['success'],
                    'delay_seconds': delay,
                    'reason': reason
                })
            else:
                logger.debug(f"Skipping auto-recovery for {deployment.name}: {reason}")

        successful = len([r for r in recovery_results if r['success']])

        logger.info(
            f"Auto-recovery completed: {successful}/{len(recovery_results)} successful"
        )

        return {
            'success': True,
            'total_attempted': len(recovery_results),
            'successful': successful,
            'failed': len(recovery_results) - successful,
            'results': recovery_results
        }

    except Exception as exc:
        logger.error(f"Failed to auto-recover services: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.check_celery_health')
def check_celery_health() -> Dict[str, Any]:
    """
    Check health of Celery workers and beat scheduler.

    Scheduled to run every 10 minutes.

    Returns:
        Dict with Celery health status
    """
    from .service_controller import service_controller

    try:
        status = service_controller.check_celery_workers()

        if not status['healthy']:
            logger.warning(
                f"Celery health check failed: {status['worker_count']} workers running"
            )
        else:
            logger.info(
                f"Celery health check passed: {status['worker_count']} workers, "
                f"beat {'running' if status['beat_running'] else 'not running'}"
            )

        return status

    except Exception as exc:
        logger.error(f"Failed to check Celery health: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'healthy': False
        }


@shared_task(name='services.cleanup_old_monitoring_data')
def cleanup_old_monitoring_data(days: int = 7) -> Dict[str, Any]:
    """
    Clean up old monitoring data to prevent database bloat.

    Args:
        days: Delete data older than this many days

    Returns:
        Dict with cleanup results
    """
    from .monitoring import SystemMonitor

    try:
        monitor = SystemMonitor()
        monitor.cleanup_old_data(days=days)

        logger.info(f"Cleaned up monitoring data older than {days} days")

        return {
            'success': True,
            'days': days,
            'message': f'Cleaned up data older than {days} days'
        }

    except Exception as exc:
        logger.error(f"Failed to cleanup old data: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.restart_service_task')
def restart_service_task(deployment_id: int) -> Dict[str, Any]:
    """
    Restart a specific service (background task).

    Args:
        deployment_id: ID of deployment to restart

    Returns:
        Dict with restart result
    """
    from apps.deployments.models import BaseDeployment, ApplicationDeployment
    from .service_controller import service_controller

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        logger.info(f"Restarting service via task: {deployment.name}")

        result = service_controller.restart_service(deployment)

        return result

    except ApplicationDeployment.DoesNotExist:
        error = f"Deployment {deployment_id} not found"
        logger.error(error)
        return {
            'success': False,
            'error': error
        }
    except Exception as exc:
        logger.error(f"Failed to restart service {deployment_id}: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.start_service_task')
def start_service_task(deployment_id: int) -> Dict[str, Any]:
    """
    Start a specific service (background task).

    Args:
        deployment_id: ID of deployment to start

    Returns:
        Dict with start result
    """
    from apps.deployments.models import BaseDeployment, ApplicationDeployment
    from .service_controller import service_controller

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        logger.info(f"Starting service via task: {deployment.name}")

        result = service_controller.start_service(deployment)

        return result

    except ApplicationDeployment.DoesNotExist:
        error = f"Deployment {deployment_id} not found"
        logger.error(error)
        return {
            'success': False,
            'error': error
        }
    except Exception as exc:
        logger.error(f"Failed to start service {deployment_id}: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.stop_service_task')
def stop_service_task(deployment_id: int) -> Dict[str, Any]:
    """
    Stop a specific service (background task).

    Args:
        deployment_id: ID of deployment to stop

    Returns:
        Dict with stop result
    """
    from apps.deployments.models import BaseDeployment, ApplicationDeployment
    from .service_controller import service_controller

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        logger.info(f"Stopping service via task: {deployment.name}")

        result = service_controller.stop_service(deployment)

        return result

    except ApplicationDeployment.DoesNotExist:
        error = f"Deployment {deployment_id} not found"
        logger.error(error)
        return {
            'success': False,
            'error': error
        }
    except Exception as exc:
        logger.error(f"Failed to stop service {deployment_id}: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(name='services.check_system_services')
def check_system_services() -> Dict[str, Any]:
    """
    Check status of critical system services (Nginx, PostgreSQL, Redis).

    Scheduled to run every 10 minutes.

    Returns:
        Dict with system services status
    """
    from .service_controller import service_controller

    try:
        status = service_controller.get_system_services_status()

        if not status['healthy']:
            logger.warning("System services health check failed")

            # Create alert for failed services
            from .models import Alert
            failed_services = [
                name for name, info in status['services'].items()
                if not info['active']
            ]

            if failed_services:
                Alert.objects.create(
                    alert_type=Alert.AlertType.DATABASE_ERROR,
                    severity=Alert.Severity.CRITICAL,
                    title=f"System Services Failed: {', '.join(failed_services)}",
                    message=f"The following critical system services are not running: {', '.join(failed_services)}",
                    metadata={'services': status['services']}
                )
        else:
            logger.info("System services health check passed")

        return status

    except Exception as exc:
        logger.error(f"Failed to check system services: {exc}")
        return {
            'success': False,
            'error': str(exc),
            'healthy': False
        }


@shared_task(name='services.generate_daily_report')
def generate_daily_report() -> Dict[str, Any]:
    """
    Generate daily system report with statistics.

    Scheduled to run daily at midnight.

    Returns:
        Dict with report data
    """
    from .models import ResourceUsage, Alert, ServiceStatus
    from apps.deployments.models import BaseDeployment, ApplicationDeployment
    from django.db.models import Avg, Max, Min, Count

    try:
        # Get yesterday's date range
        yesterday = timezone.now() - timedelta(days=1)
        start_of_day = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Resource usage statistics
        resource_stats = ResourceUsage.objects.filter(
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        ).aggregate(
            avg_cpu=Avg('cpu_percent'),
            max_cpu=Max('cpu_percent'),
            avg_memory=Avg('memory_percent'),
            max_memory=Max('memory_percent'),
            avg_disk=Avg('disk_percent'),
            max_disk=Max('disk_percent')
        )

        # Alert statistics
        alert_stats = Alert.objects.filter(
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        ).values('severity').annotate(count=Count('id'))

        # Service statistics
        total_deployments = ApplicationDeployment.objects.count()
        running_services = ServiceStatus.objects.filter(
            status=ServiceStatus.Status.RUNNING
        ).count()

        report = {
            'date': start_of_day.date().isoformat(),
            'resources': resource_stats,
            'alerts': {item['severity']: item['count'] for item in alert_stats},
            'services': {
                'total_deployments': total_deployments,
                'running_services': running_services
            }
        }

        logger.info(f"Generated daily report for {report['date']}")

        return {
            'success': True,
            'report': report
        }

    except Exception as exc:
        logger.error(f"Failed to generate daily report: {exc}")
        return {
            'success': False,
            'error': str(exc)
        }
