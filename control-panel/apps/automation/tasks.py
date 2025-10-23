"""
Celery tasks for automation workflow execution.

This module provides asynchronous execution of workflows using Celery.
"""

from celery import shared_task
from typing import Dict, Any, Optional
import logging
import traceback

from .models import Workflow, WorkflowExecution
from .engine import WorkflowExecutionEngine

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def execute_workflow_async(
    self,
    workflow_id: int,
    input_data: Dict[str, Any] = None,
    triggered_by_id: Optional[int] = None,
    trigger_type: str = 'manual'
) -> Dict[str, Any]:
    """
    Execute a workflow asynchronously using Celery.
    
    Args:
        workflow_id: ID of the workflow to execute
        input_data: Input data for the workflow
        triggered_by_id: ID of the user who triggered the execution
        trigger_type: Type of trigger (manual, schedule, webhook, event)
        
    Returns:
        Dict with execution results
    """
    try:
        # Get workflow
        workflow = Workflow.objects.get(id=workflow_id)
        
        # Get user if specified
        triggered_by = None
        if triggered_by_id:
            from django.contrib.auth.models import User
            try:
                triggered_by = User.objects.get(id=triggered_by_id)
            except User.DoesNotExist:
                logger.warning(f"User with ID {triggered_by_id} not found")
        
        # Execute workflow
        engine = WorkflowExecutionEngine()
        execution = engine.execute_workflow(
            workflow=workflow,
            input_data=input_data or {},
            triggered_by=triggered_by,
            trigger_type=trigger_type
        )
        
        return {
            'success': True,
            'execution_id': execution.id,
            'status': execution.status,
            'duration_ms': execution.duration_ms,
            'error': execution.error_message
        }
        
    except Workflow.DoesNotExist:
        logger.error(f"Workflow with ID {workflow_id} not found")
        return {
            'success': False,
            'error': f'Workflow with ID {workflow_id} not found'
        }
        
    except Exception as exc:
        logger.error(f"Workflow execution failed: {exc}")
        logger.error(traceback.format_exc())
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying workflow execution in {countdown} seconds")
            raise self.retry(exc=exc, countdown=countdown)
        
        return {
            'success': False,
            'error': str(exc),
            'retries_exhausted': True
        }


@shared_task
def execute_scheduled_workflows():
    """
    Find and execute workflows scheduled to run.
    
    This task should be scheduled to run periodically (e.g., every minute).
    """
    from django.utils import timezone
    from croniter import croniter
    
    now = timezone.now()
    executed_count = 0
    
    # Get all active scheduled workflows
    scheduled_workflows = Workflow.objects.filter(
        status=Workflow.Status.ACTIVE,
        trigger_type=Workflow.TriggerType.SCHEDULE,
        schedule_cron__isnull=False
    )
    
    for workflow in scheduled_workflows:
        try:
            # Check if workflow should run now
            cron = croniter(workflow.schedule_cron, now)
            next_run = cron.get_next(timezone.datetime)
            
            # If the next run time is very close to now (within 1 minute), execute it
            if 0 <= (next_run - now).total_seconds() <= 60:
                logger.info(f"Executing scheduled workflow: {workflow.name}")
                
                # Execute asynchronously
                execute_workflow_async.delay(
                    workflow_id=workflow.id,
                    trigger_type='schedule'
                )
                
                executed_count += 1
                
        except Exception as e:
            logger.error(f"Error checking scheduled workflow {workflow.name}: {e}")
    
    return {
        'executed_count': executed_count,
        'timestamp': now.isoformat()
    }


@shared_task(bind=True, max_retries=2)
def retry_failed_execution(self, execution_id: int) -> Dict[str, Any]:
    """
    Retry a failed workflow execution.
    
    Args:
        execution_id: ID of the failed execution to retry
        
    Returns:
        Dict with retry results
    """
    try:
        # Get the original execution
        execution = WorkflowExecution.objects.get(id=execution_id)
        
        if execution.status != WorkflowExecution.Status.FAILED:
            return {
                'success': False,
                'error': f'Execution {execution_id} is not in FAILED status'
            }
        
        # Check if we haven't exceeded max retries
        if execution.workflow.max_retries <= 0:
            return {
                'success': False,
                'error': 'Workflow does not allow retries'
            }
        
        # Count previous retries for this workflow
        retry_count = WorkflowExecution.objects.filter(
            workflow=execution.workflow,
            trigger_type='retry',
            started_at__gt=execution.started_at
        ).count()
        
        if retry_count >= execution.workflow.max_retries:
            return {
                'success': False,
                'error': f'Maximum retries ({execution.workflow.max_retries}) exceeded'
            }
        
        # Execute the workflow again with the same input
        engine = WorkflowExecutionEngine()
        new_execution = engine.execute_workflow(
            workflow=execution.workflow,
            input_data=execution.input_data,
            triggered_by=execution.triggered_by,
            trigger_type='retry'
        )
        
        return {
            'success': True,
            'execution_id': new_execution.id,
            'status': new_execution.status,
            'retry_count': retry_count + 1
        }
        
    except WorkflowExecution.DoesNotExist:
        logger.error(f"Execution with ID {execution_id} not found")
        return {
            'success': False,
            'error': f'Execution with ID {execution_id} not found'
        }
        
    except Exception as exc:
        logger.error(f"Failed to retry execution {execution_id}: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        
        return {
            'success': False,
            'error': str(exc),
            'retries_exhausted': True
        }


@shared_task
def cleanup_old_executions():
    """
    Clean up old workflow execution logs.
    
    Keeps only the last 1000 executions per workflow.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    cleaned_count = 0
    
    # Get all workflows
    workflows = Workflow.objects.all()
    
    for workflow in workflows:
        # Delete old executions (older than 30 days)
        old_executions = WorkflowExecution.objects.filter(
            workflow=workflow,
            started_at__lt=cutoff_date
        )
        
        # Keep the last 1000 executions even if they're old
        if old_executions.count() > 1000:
            # Get the IDs of the 1000 most recent executions
            recent_ids = WorkflowExecution.objects.filter(
                workflow=workflow
            ).order_by('-started_at').values_list('id', flat=True)[:1000]
            
            # Delete all old executions except the recent ones
            deleted_count = old_executions.exclude(id__in=recent_ids).delete()[0]
            cleaned_count += deleted_count
        else:
            # Delete all old executions
            deleted_count = old_executions.delete()[0]
            cleaned_count += deleted_count
    
    return {
        'cleaned_count': cleaned_count,
        'cutoff_date': cutoff_date.isoformat()
    }


@shared_task
def validate_all_workflows():
    """
    Validate all workflows and report any issues.
    """
    from .validators import WorkflowValidator
    
    workflows = Workflow.objects.all()
    validation_results = []
    
    for workflow in workflows:
        is_valid, errors = WorkflowValidator.validate_workflow(workflow)
        
        validation_results.append({
            'workflow_id': workflow.id,
            'workflow_name': workflow.name,
            'is_valid': is_valid,
            'errors': errors
        })
        
        # If workflow is invalid and active, deactivate it
        if not is_valid and workflow.status == Workflow.Status.ACTIVE:
            workflow.status = Workflow.Status.DISABLED
            workflow.save()
            logger.warning(f"Deactivated invalid workflow: {workflow.name}")
    
    # Count valid vs invalid workflows
    valid_count = sum(1 for result in validation_results if result['is_valid'])
    invalid_count = len(validation_results) - valid_count
    
    return {
        'total_workflows': len(validation_results),
        'valid_workflows': valid_count,
        'invalid_workflows': invalid_count,
        'validation_results': validation_results
    }