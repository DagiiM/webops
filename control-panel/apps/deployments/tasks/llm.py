"""
Celery tasks for LLM deployments.

Background task processing for LLM model deployments with vLLM.
"""

from typing import Dict, Any
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


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
    from ..models import LLMDeployment, DeploymentLog
    from ..services import LLMDeploymentService

    try:
        deployment = LLMDeployment.objects.get(id=deployment_id)
        logger.info(f"Starting LLM deployment {deployment.name} (Model: {deployment.model_name})")

        # Verify this is an LLM deployment
        if deployment.project_type != LLMDeployment.ProjectType.LLM:
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

    except LLMDeployment.DoesNotExist:
        error_msg = f"Deployment {deployment_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

    except Exception as exc:
        error_msg = f"LLM deployment {deployment_id} failed: {exc}"
        logger.error(error_msg)

        # Update deployment status
        try:
            deployment = LLMDeployment.objects.get(id=deployment_id)
            deployment.status = LLMDeployment.Status.FAILED
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
