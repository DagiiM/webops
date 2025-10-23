"""
Celery tasks for health checks and maintenance.

Background tasks for monitoring deployment health and cleanup.
"""

from typing import Dict, Any
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True)
def run_health_check(
    self,
    deployment_id: int,
    auto_restart: bool = True
) -> Dict[str, Any]:
    """
    Run health check on deployment.

    Args:
        deployment_id: Database ID of deployment
        auto_restart: Whether to attempt auto-restart on failure

    Returns:
        Dictionary with health check results
    """
    from ..models import ApplicationDeployment, HealthCheckRecord
    from ..shared import perform_health_check

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        logger.info(f"Running health check for {deployment.name}")

        # Perform health check
        results = perform_health_check(deployment, auto_restart=auto_restart)

        # Save health check record
        overall = results.get('overall', {})
        process = results.get('process', {})
        http = results.get('http', {})
        resources = results.get('resources', {})
        disk = results.get('disk', {})

        # Extract metrics
        cpu_percent = resources.get('details', {}).get('cpu_percent')
        memory_mb = resources.get('details', {}).get('memory_mb')
        disk_free_gb = disk.get('details', {}).get('free_gb')
        response_time = http.get('details', {}).get('response_time')
        http_status = http.get('details', {}).get('status_code')

        # Convert response_time to milliseconds if present
        response_time_ms = response_time * 1000 if response_time else None

        record = HealthCheckRecord.objects.create(
            deployment=deployment,
            overall_healthy=overall.get('healthy', False),
            process_healthy=process.get('healthy', False),
            http_healthy=http.get('healthy', False),
            resources_healthy=resources.get('healthy', False),
            disk_healthy=disk.get('healthy', False),
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            disk_free_gb=disk_free_gb,
            response_time_ms=response_time_ms,
            http_status_code=http_status,
            results=results,
            auto_restart_attempted=results.get('auto_restart_attempted', False)
        )

        logger.info(
            f"Health check completed for {deployment.name}: "
            f"{'healthy' if overall.get('healthy') else 'unhealthy'}"
        )

        return {
            'success': True,
            'deployment_id': deployment_id,
            'healthy': overall.get('healthy', False),
            'record_id': record.id
        }

    except ApplicationDeployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"Health check failed for deployment {deployment_id}: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}


@shared_task
def run_all_health_checks(auto_restart: bool = True) -> Dict[str, Any]:
    """
    Run health checks on all running deployments.

    Args:
        auto_restart: Whether to attempt auto-restart on failures

    Returns:
        Dictionary with summary of health checks
    """
    from ..models import ApplicationDeployment

    try:
        running_deployments = ApplicationDeployment.objects.filter(
            status=ApplicationDeployment.Status.RUNNING
        )

        total = running_deployments.count()
        logger.info(f"Running health checks on {total} deployments")

        results = []
        for deployment in running_deployments:
            result = run_health_check.delay(deployment.id, auto_restart=auto_restart)
            results.append({
                'deployment_id': deployment.id,
                'deployment_name': deployment.name,
                'task_id': result.id
            })

        return {
            'success': True,
            'total_deployments': total,
            'checks_queued': len(results),
            'results': results
        }

    except Exception as exc:
        error_msg = f"Failed to run health checks: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}


@shared_task
def cleanup_old_health_records(days: int = 30) -> Dict[str, Any]:
    """
    Clean up old health check records.

    Args:
        days: Delete records older than this many days

    Returns:
        Dictionary with cleanup results
    """
    from ..models import HealthCheckRecord
    from django.utils import timezone
    from datetime import timedelta

    try:
        cutoff_date = timezone.now() - timedelta(days=days)

        deleted_count, _ = HealthCheckRecord.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        logger.info(f"Deleted {deleted_count} old health check records")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as exc:
        error_msg = f"Failed to cleanup health records: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}
