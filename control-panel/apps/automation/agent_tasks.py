"""
Celery tasks for agent-workflow integration.

Provides background tasks that bridge workflows with the AI agent system.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='agent_execute_task', bind=True, max_retries=3)
def agent_execute_task(
    self,
    agent_id: str,
    task_description: str,
    task_params: Dict[str, Any],
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Execute a task using an AI agent.

    Args:
        agent_id: ID of the agent to use
        task_description: Description of the task
        task_params: Additional parameters for the task
        workflow_execution_id: ID of the workflow execution

    Returns:
        Task execution result
    """
    try:
        logger.info(f"Agent {agent_id} executing task for workflow {workflow_execution_id}")

        # Import agent system (import here to avoid circular dependencies)
        # In production, this would connect to the actual agent system
        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.execute_task(agent_id, task_description, task_params)

        logger.info(f"Agent task completed successfully: {result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"Agent task execution failed: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 300))


@shared_task(name='agent_process_query', bind=True)
def agent_process_query(
    self,
    agent_id: str,
    query: str,
    context: Dict[str, Any],
    expected_format: str,
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Process a query using an AI agent.

    Args:
        agent_id: ID of the agent to use
        query: Query text
        context: Additional context
        expected_format: Expected response format (text, json, structured)
        workflow_execution_id: ID of the workflow execution

    Returns:
        Agent response with answer, confidence, and reasoning
    """
    try:
        logger.info(f"Agent {agent_id} processing query for workflow {workflow_execution_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        response = bridge.process_query(agent_id, query, context, expected_format)

        return response

    except Exception as e:
        logger.error(f"Agent query failed: {e}", exc_info=True)
        raise


@shared_task(name='agent_store_memory')
def agent_store_memory(
    agent_id: str,
    memory_type: str,
    content: Dict[str, Any],
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Store information in agent memory.

    Args:
        agent_id: ID of the agent
        memory_type: Type of memory (episodic, semantic, procedural, working)
        content: Content to store
        workflow_execution_id: ID of the workflow execution

    Returns:
        Storage result with memory ID
    """
    try:
        logger.info(f"Storing {memory_type} memory for agent {agent_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.store_memory(agent_id, memory_type, content)

        return result

    except Exception as e:
        logger.error(f"Memory storage failed: {e}", exc_info=True)
        raise


@shared_task(name='agent_retrieve_memory')
def agent_retrieve_memory(
    agent_id: str,
    memory_type: str,
    criteria: Dict[str, Any],
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Retrieve information from agent memory.

    Args:
        agent_id: ID of the agent
        memory_type: Type of memory
        criteria: Retrieval criteria
        workflow_execution_id: ID of the workflow execution

    Returns:
        Retrieved memory data
    """
    try:
        logger.info(f"Retrieving {memory_type} memory for agent {agent_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.retrieve_memory(agent_id, memory_type, criteria)

        return result

    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}", exc_info=True)
        raise


@shared_task(name='agent_search_memory')
def agent_search_memory(
    agent_id: str,
    memory_type: str,
    query: str,
    filters: Dict[str, Any],
    limit: int,
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Search agent memory.

    Args:
        agent_id: ID of the agent
        memory_type: Type of memory
        query: Search query
        filters: Search filters
        limit: Maximum results
        workflow_execution_id: ID of the workflow execution

    Returns:
        Search results
    """
    try:
        logger.info(f"Searching {memory_type} memory for agent {agent_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.search_memory(agent_id, memory_type, query, filters, limit)

        return result

    except Exception as e:
        logger.error(f"Memory search failed: {e}", exc_info=True)
        raise


@shared_task(name='agent_make_decision')
def agent_make_decision(
    agent_id: str,
    context: Dict[str, Any],
    options: List[str],
    criteria: List[str],
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Request a decision from an AI agent.

    Args:
        agent_id: ID of the agent
        context: Decision context
        options: Available options
        criteria: Decision criteria
        workflow_execution_id: ID of the workflow execution

    Returns:
        Decision result with selected option, confidence, and reasoning
    """
    try:
        logger.info(f"Agent {agent_id} making decision for workflow {workflow_execution_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.make_decision(agent_id, context, options, criteria)

        return result

    except Exception as e:
        logger.error(f"Agent decision failed: {e}", exc_info=True)
        raise


@shared_task(name='agent_process_learning')
def agent_process_learning(
    agent_id: str,
    feedback_type: str,
    feedback_data: Dict[str, Any],
    workflow_execution_id: int
) -> Dict[str, Any]:
    """
    Provide learning feedback to an AI agent.

    Args:
        agent_id: ID of the agent
        feedback_type: Type of feedback (outcome, correction, reinforcement)
        feedback_data: Feedback information
        workflow_execution_id: ID of the workflow execution

    Returns:
        Learning processing result
    """
    try:
        logger.info(f"Processing {feedback_type} learning for agent {agent_id}")

        from apps.automation.agent_integration import AgentBridge

        bridge = AgentBridge()
        result = bridge.process_learning(agent_id, feedback_type, feedback_data)

        return result

    except Exception as e:
        logger.error(f"Learning processing failed: {e}", exc_info=True)
        raise


@shared_task(name='trigger_workflow_from_agent_event')
def trigger_workflow_from_agent_event(
    agent_id: str,
    event_type: str,
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Trigger workflows based on agent events.

    This task is called by the agent system when significant events occur,
    such as task completion, decision making, or learning milestones.

    Args:
        agent_id: ID of the agent that generated the event
        event_type: Type of event (task_completed, decision_made, learning_milestone, etc.)
        event_data: Event-specific data

    Returns:
        Information about triggered workflows
    """
    try:
        logger.info(f"Agent {agent_id} triggered event: {event_type}")

        from apps.automation.models import Workflow, WorkflowExecution
        from apps.automation.engine import workflow_engine

        # Find workflows configured to trigger on this agent event
        matching_workflows = Workflow.objects.filter(
            status=Workflow.Status.ACTIVE,
            trigger_type=Workflow.TriggerType.EVENT,
            canvas_data__trigger_config__event_type=event_type,
            canvas_data__trigger_config__agent_id=agent_id
        )

        triggered = []
        for workflow in matching_workflows:
            try:
                execution = workflow_engine.execute_workflow(
                    workflow=workflow,
                    input_data={
                        'agent_id': agent_id,
                        'event_type': event_type,
                        'event_data': event_data,
                        'triggered_at': timezone.now().isoformat()
                    },
                    trigger_type='event'
                )

                triggered.append({
                    'workflow_id': workflow.id,
                    'workflow_name': workflow.name,
                    'execution_id': execution.id,
                    'status': execution.status
                })

                logger.info(f"Triggered workflow {workflow.name} (execution: {execution.id})")

            except Exception as e:
                logger.error(f"Failed to trigger workflow {workflow.name}: {e}")
                continue

        return {
            'agent_id': agent_id,
            'event_type': event_type,
            'workflows_triggered': len(triggered),
            'triggered_workflows': triggered
        }

    except Exception as e:
        logger.error(f"Failed to process agent event: {e}", exc_info=True)
        raise
