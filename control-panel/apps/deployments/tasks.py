"""
Celery tasks for WebOps deployments.

Reference: CLAUDE.md "Celery Tasks" section
Architecture: Background task processing for deployments

This module implements async tasks for:
- Deployment processing
- Service management
- Status updates
"""

from typing import Dict, Any
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def deploy_application(
    self,
    deployment_id: int
) -> Dict[str, Any]:
    """
    Deploy application in background.

    Args:
        deployment_id: Database ID of deployment

    Returns:
        Dictionary with deployment result
    """
    from .models import Deployment, DeploymentLog
    from .services import DeploymentService

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        logger.info(f"Starting deployment {deployment.name} (ID: {deployment_id})")

        service = DeploymentService()
        result = service.deploy(deployment)

        if result['success']:
            logger.info(f"Deployment {deployment.name} completed successfully")
        else:
            logger.error(f"Deployment {deployment.name} failed: {result.get('error')}")

        return result

    except Deployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"Deployment {deployment_id} failed: {exc}"
        logger.error(error_msg)

        # Update deployment status
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])

            DeploymentLog.objects.create(
                deployment=deployment,
                level=DeploymentLog.Level.ERROR,
                message=f"Task failed: {str(exc)}"
            )
        except:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True)
def restart_deployment(
    self,
    deployment_id: int
) -> Dict[str, Any]:
    """
    Restart deployment service.

    Args:
        deployment_id: Database ID of deployment

    Returns:
        Dictionary with restart result
    """
    from .models import Deployment, DeploymentLog

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        logger.info(f"Restarting deployment {deployment.name}")

        # TODO: Implement service restart logic (Phase 2.5)
        # For now, just log it
        DeploymentLog.objects.create(
            deployment=deployment,
            level=DeploymentLog.Level.INFO,
            message="Restart requested (pending implementation)"
        )

        return {
            'success': True,
            'deployment_id': deployment_id,
            'message': 'Restart queued (implementation pending)'
        }

    except Deployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"Failed to restart deployment {deployment_id}: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}


@shared_task(bind=True)
def stop_deployment(
    self,
    deployment_id: int
) -> Dict[str, Any]:
    """
    Stop deployment service.

    Args:
        deployment_id: Database ID of deployment

    Returns:
        Dictionary with stop result
    """
    from .models import Deployment, DeploymentLog

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        logger.info(f"Stopping deployment {deployment.name}")

        # TODO: Implement service stop logic (Phase 2.5)
        # For now, just update status
        deployment.status = Deployment.Status.STOPPED
        deployment.save(update_fields=['status'])

        DeploymentLog.objects.create(
            deployment=deployment,
            level=DeploymentLog.Level.INFO,
            message="Service stopped (pending full implementation)"
        )

        return {
            'success': True,
            'deployment_id': deployment_id,
            'status': deployment.status
        }

    except Deployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"Failed to stop deployment {deployment_id}: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}


@shared_task(bind=True)
def delete_deployment(
    self,
    deployment_id: int
) -> Dict[str, Any]:
    """
    Delete deployment and cleanup resources.

    Args:
        deployment_id: Database ID of deployment

    Returns:
        Dictionary with deletion result
    """
    from .models import Deployment, DeploymentLog
    from .services import DeploymentService
    from .service_manager import ServiceManager
    import shutil

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        deployment_name = deployment.name
        logger.info(f"Deleting deployment {deployment_name}")

        service = DeploymentService()
        service_manager = ServiceManager()

        # Stop and remove service
        service_manager.stop_service(deployment)
        service_manager.remove_service(deployment)

        # Remove Nginx config
        service_manager.remove_nginx_config(deployment)

        # Remove deployment directory
        deployment_path = service.get_deployment_path(deployment)
        if deployment_path.exists():
            shutil.rmtree(deployment_path)
            logger.info(f"Removed deployment directory: {deployment_path}")

        # Delete from database
        deployment.delete()

        logger.info(f"Deployment {deployment_name} deleted successfully")

        return {
            'success': True,
            'deployment_id': deployment_id,
            'message': f'Deployment {deployment_name} deleted'
        }

    except Deployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"Failed to delete deployment {deployment_id}: {exc}"
        logger.error(error_msg)
        return {'success': False, 'error': str(exc)}


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
    from .models import Deployment, HealthCheckRecord
    from .health_check import perform_health_check

    try:
        deployment = Deployment.objects.get(id=deployment_id)
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

    except Deployment.DoesNotExist:
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
    from .models import Deployment

    try:
        running_deployments = Deployment.objects.filter(
            status=Deployment.Status.RUNNING
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
    from .models import HealthCheckRecord
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


@shared_task(bind=True, max_retries=2)
def deploy_llm_model(
    self,
    deployment_id: int
) -> Dict[str, Any]:
    """
    Deploy LLM model with vLLM in background.

    This task handles the full LLM deployment workflow:
    - Download model from Hugging Face
    - Set up vLLM environment
    - Configure systemd service
    - Start model server

    Args:
        deployment_id: Database ID of LLM deployment

    Returns:
        Dictionary with deployment result
    """
    from .models import Deployment, DeploymentLog
    from .llm_service import LLMDeploymentService

    try:
        deployment = Deployment.objects.get(id=deployment_id)
        logger.info(f"Starting LLM deployment {deployment.name} (Model: {deployment.model_name})")

        # Verify this is an LLM deployment
        if deployment.project_type != Deployment.ProjectType.LLM:
            error_msg = f"Deployment {deployment.name} is not an LLM deployment"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

        # Use LLM deployment service
        llm_service = LLMDeploymentService()
        result = llm_service.deploy_llm(deployment)

        if result['success']:
            logger.info(
                f"LLM deployment {deployment.name} completed successfully. "
                f"Model {deployment.model_name} is now serving on port {deployment.port}"
            )
        else:
            logger.error(f"LLM deployment {deployment.name} failed: {result.get('error')}")

        return result

    except Deployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"LLM deployment {deployment_id} failed: {exc}"
        logger.error(error_msg)

        # Update deployment status
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])

            DeploymentLog.objects.create(
                deployment=deployment,
                level=DeploymentLog.Level.ERROR,
                message=f"LLM deployment task failed: {str(exc)}"
            )
        except:
            pass

        # Retry with exponential backoff (but only twice for LLM - downloads are expensive)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
        else:
            return {'success': False, 'error': error_msg}