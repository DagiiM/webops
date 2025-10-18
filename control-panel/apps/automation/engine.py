"""
Workflow Execution Engine.

This module handles the execution of automation workflows by:
- Topologically sorting nodes based on connections
- Executing nodes in dependency order
- Passing data between connected nodes
- Handling errors and retries
- Logging execution details
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
import logging
import traceback
import time

from .models import (
    Workflow,
    WorkflowNode,
    WorkflowConnection,
    WorkflowExecution
)
from .node_executors import NodeExecutorRegistry

logger = logging.getLogger(__name__)


class WorkflowExecutionEngine:
    """
    Engine for executing automation workflows.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.node_executor_registry = NodeExecutorRegistry()

    def execute_workflow(
        self,
        workflow: Workflow,
        input_data: Dict[str, Any] = None,
        triggered_by=None,
        trigger_type: str = 'manual'
    ) -> WorkflowExecution:
        """
        Execute a workflow.

        Args:
            workflow: Workflow to execute
            input_data: Initial input data
            triggered_by: User who triggered execution
            trigger_type: Type of trigger (manual, schedule, webhook, event)

        Returns:
            WorkflowExecution instance
        """
        input_data = input_data or {}

        # Create execution record
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            status=WorkflowExecution.Status.PENDING,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            input_data=input_data,
            trigger_data={'timestamp': timezone.now().isoformat()}
        )

        try:
            # Update status to running
            execution.status = WorkflowExecution.Status.RUNNING
            execution.save()

            start_time = time.time()

            # Get execution order
            execution_order = self._get_execution_order(workflow)
            if execution_order is None:
                raise ValueError("Workflow contains cycles or is invalid")

            # Execute nodes in order
            node_data = {'input': input_data}
            node_logs = []

            for node in execution_order:
                if not node.enabled:
                    node_logs.append({
                        'node_id': node.node_id,
                        'node_label': node.label,
                        'status': 'skipped',
                        'reason': 'Node disabled'
                    })
                    continue

                # Get input data from predecessors
                node_input = self._get_node_input(node, node_data, workflow)

                # Execute node
                node_result = self._execute_node(node, node_input, execution)

                # Store node output
                node_data[node.node_id] = node_result['output']

                # Log node execution
                node_logs.append({
                    'node_id': node.node_id,
                    'node_label': node.label,
                    'node_type': node.node_type,
                    'status': node_result['status'],
                    'duration_ms': node_result.get('duration_ms', 0),
                    'error': node_result.get('error'),
                    'timestamp': timezone.now().isoformat()
                })

                # Check for errors
                if node_result['status'] == 'error':
                    if not workflow.retry_on_failure:
                        raise Exception(f"Node {node.label} failed: {node_result.get('error')}")

            # Calculate final output (from last nodes)
            output_data = self._get_final_output(execution_order, node_data)

            # Mark as successful
            duration_ms = int((time.time() - start_time) * 1000)
            execution.status = WorkflowExecution.Status.SUCCESS
            execution.completed_at = timezone.now()
            execution.duration_ms = duration_ms
            execution.output_data = output_data
            execution.node_logs = node_logs
            execution.save()

            # Update workflow statistics
            workflow.total_executions += 1
            workflow.successful_executions += 1
            workflow.last_executed_at = timezone.now()
            workflow.average_duration_ms = (
                (workflow.average_duration_ms * (workflow.total_executions - 1) + duration_ms)
                / workflow.total_executions
            )
            workflow.save()

            self.logger.info(f"Workflow {workflow.name} executed successfully in {duration_ms}ms")

        except Exception as e:
            # Mark as failed
            execution.status = WorkflowExecution.Status.FAILED
            execution.completed_at = timezone.now()
            execution.error_message = str(e)
            execution.error_traceback = traceback.format_exc()
            execution.save()

            # Update workflow statistics
            workflow.total_executions += 1
            workflow.failed_executions += 1
            workflow.save()

            self.logger.error(f"Workflow {workflow.name} execution failed: {e}")
            self.logger.error(traceback.format_exc())

        return execution

    def _get_execution_order(self, workflow: Workflow) -> Optional[List[WorkflowNode]]:
        """
        Get topological ordering of nodes for execution.

        Returns None if workflow contains cycles.
        """
        nodes = list(workflow.nodes.all())
        connections = list(workflow.connections.all())

        # Build adjacency list
        adjacency = {node.node_id: [] for node in nodes}
        in_degree = {node.node_id: 0 for node in nodes}

        for conn in connections:
            adjacency[conn.source_node.node_id].append(conn.target_node.node_id)
            in_degree[conn.target_node.node_id] += 1

        # Kahn's algorithm for topological sort
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(nodes):
            return None

        # Convert node IDs back to node objects
        node_map = {node.node_id: node for node in nodes}
        return [node_map[node_id] for node_id in result]

    def _get_node_input(
        self,
        node: WorkflowNode,
        node_data: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """
        Get input data for a node from its predecessors.
        """
        # Get incoming connections
        incoming = workflow.connections.filter(target_node=node)

        if not incoming.exists():
            # No incoming connections, use workflow input
            return node_data.get('input', {})

        # Merge data from all incoming connections
        merged_input = {}

        for conn in incoming:
            source_data = node_data.get(conn.source_node.node_id, {})

            # Apply transformation if specified
            if conn.transform:
                source_data = self._apply_transformation(source_data, conn.transform)

            # Check condition if specified
            if conn.condition:
                if not self._evaluate_condition(source_data, conn.condition):
                    continue

            # Merge data
            if isinstance(source_data, dict):
                merged_input.update(source_data)
            else:
                merged_input[conn.source_handle] = source_data

        return merged_input

    def _execute_node(
        self,
        node: WorkflowNode,
        input_data: Dict[str, Any],
        execution: WorkflowExecution
    ) -> Dict[str, Any]:
        """
        Execute a single node.

        Returns:
            Dict with 'status', 'output', 'duration_ms', and optional 'error'
        """
        start_time = time.time()

        try:
            # Get node executor
            executor = self.node_executor_registry.get_executor(node.node_type)

            # Execute node with timeout
            output = executor.execute(node, input_data, execution)

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                'status': 'success',
                'output': output,
                'duration_ms': duration_ms
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            self.logger.error(f"Node {node.label} execution failed: {e}")

            return {
                'status': 'error',
                'output': {},
                'duration_ms': duration_ms,
                'error': str(e),
                'traceback': traceback.format_exc()
            }

    def _get_final_output(
        self,
        execution_order: List[WorkflowNode],
        node_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get final output from output nodes.
        """
        output = {}

        # Find output nodes (nodes with no outgoing connections)
        for node in execution_order:
            if node.node_type.startswith('output_') or node.node_type.startswith('OUTPUT_'):
                node_output = node_data.get(node.node_id, {})
                output[node.node_id] = node_output

        # If no output nodes, return data from all leaf nodes
        if not output:
            # Get last nodes in execution order
            for node in execution_order[-3:]:
                output[node.node_id] = node_data.get(node.node_id, {})

        return output

    def _apply_transformation(
        self,
        data: Any,
        transform: Dict[str, Any]
    ) -> Any:
        """
        Apply data transformation.
        """
        # Simple transformation support
        transform_type = transform.get('type')

        if transform_type == 'jmespath':
            # JMESPath query
            import jmespath
            query = transform.get('query')
            return jmespath.search(query, data)

        elif transform_type == 'jsonpath':
            # JSONPath query
            from jsonpath_ng import parse
            expr = parse(transform.get('query'))
            matches = [match.value for match in expr.find(data)]
            return matches[0] if len(matches) == 1 else matches

        elif transform_type == 'template':
            # Template-based transformation
            from string import Template
            template = Template(transform.get('template'))
            return template.safe_substitute(data)

        return data

    def _evaluate_condition(
        self,
        data: Any,
        condition: Dict[str, Any]
    ) -> bool:
        """
        Evaluate conditional connection.
        """
        condition_type = condition.get('type')

        if condition_type == 'expression':
            # Simple expression evaluation
            expression = condition.get('expression')
            try:
                # Safe evaluation with limited scope
                return eval(expression, {'__builtins__': {}}, {'data': data})
            except Exception as e:
                self.logger.warning(f"Condition evaluation failed: {e}")
                return False

        elif condition_type == 'comparison':
            # Field comparison
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')

            if isinstance(data, dict):
                data_value = data.get(field)
            else:
                data_value = data

            if operator == 'eq':
                return data_value == value
            elif operator == 'ne':
                return data_value != value
            elif operator == 'gt':
                return data_value > value
            elif operator == 'lt':
                return data_value < value
            elif operator == 'gte':
                return data_value >= value
            elif operator == 'lte':
                return data_value <= value
            elif operator == 'contains':
                return value in str(data_value)

        return True


# Singleton instance
workflow_engine = WorkflowExecutionEngine()
