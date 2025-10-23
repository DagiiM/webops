"""
Celery tasks for application deployments.

Background task processing for application deployments including:
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
    from ..models import ApplicationDeployment, DeploymentLog
    from ..services import DeploymentService

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
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
            deployment = ApplicationDeployment.objects.get(id=deployment_id)
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
    from ..models import Deployment, DeploymentLog

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
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
    from ..models import Deployment, DeploymentLog

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
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
    from ..models import Deployment, DeploymentLog
    from ..services import DeploymentService
    from ..shared import ServiceManager
    import shutil

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
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
