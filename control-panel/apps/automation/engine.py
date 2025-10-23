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
                    # Handle node failure with retry logic
                    if self._should_retry_node(node, node_result, execution):
                        # Retry the node
                        retry_result = self._retry_node(node, node_input, execution)
                        if retry_result['status'] == 'error':
                            # Still failed after retry
                            if not workflow.retry_on_failure:
                                raise Exception(f"Node {node.label} failed after retry: {retry_result.get('error')}")
                            node_result = retry_result
                        else:
                            # Retry succeeded
                            node_result = retry_result
                            node_data[node.node_id] = node_result['output']
                    elif not workflow.retry_on_failure:
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

            # Update workflow statistics atomically
            from django.db.models import F
            from django.db import transaction
            
            with transaction.atomic():
                # Lock the workflow row to prevent race conditions
                workflow = Workflow.objects.select_for_update().get(pk=workflow.pk)
                
                # Update statistics atomically
                workflow.total_executions = F('total_executions') + 1
                workflow.successful_executions = F('successful_executions') + 1
                workflow.last_executed_at = timezone.now()
                
                # Calculate new average duration
                # We need to fetch the current values first for the calculation
                current_total = workflow.total_executions
                current_avg = workflow.average_duration_ms
                
                # Save the atomic updates
                workflow.save()
                
                # Refresh to get the updated values
                workflow.refresh_from_db()
                
                # Now update the average duration
                new_avg = (
                    (current_avg * (workflow.total_executions - 1) + duration_ms)
                    / workflow.total_executions
                )
                workflow.average_duration_ms = new_avg
                workflow.save()

            self.logger.info(f"Workflow {workflow.name} executed successfully in {duration_ms}ms")

        except Exception as e:
            # Mark as failed
            execution.status = WorkflowExecution.Status.FAILED
            execution.completed_at = timezone.now()
            execution.error_message = str(e)
            execution.error_traceback = traceback.format_exc()
            execution.save()

            # Update workflow statistics atomically
            from django.db.models import F
            from django.db import transaction
            
            with transaction.atomic():
                # Lock the workflow row to prevent race conditions
                workflow = Workflow.objects.select_for_update().get(pk=workflow.pk)
                
                # Update statistics atomically
                workflow.total_executions = F('total_executions') + 1
                workflow.failed_executions = F('failed_executions') + 1
                
                workflow.save()

            self.logger.error(f"Workflow {workflow.name} execution failed: {e}")
            self.logger.error(traceback.format_exc())

        return execution

    def _get_execution_order(self, workflow: Workflow) -> Optional[List[WorkflowNode]]:
        """
        Get topological ordering of nodes for execution.

        Returns None if workflow contains cycles.
        """
        from collections import deque
        
        # Optimize query with prefetch_related
        nodes = list(workflow.nodes.all())
        connections = list(workflow.connections.select_related('source_node', 'target_node').all())

        # Build adjacency list
        adjacency = {node.node_id: [] for node in nodes}
        in_degree = {node.node_id: 0 for node in nodes}

        for conn in connections:
            adjacency[conn.source_node.node_id].append(conn.target_node.node_id)
            in_degree[conn.target_node.node_id] += 1

        # Kahn's algorithm for topological sort using deque for O(1) operations
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            node_id = queue.popleft()  # O(1) operation with deque
            result.append(node_id)

            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles and provide detailed information
        if len(result) != len(nodes):
            # Find nodes involved in cycles
            cycle_nodes = [node_id for node_id in in_degree if in_degree[node_id] > 0]
            node_labels = [next((n.label for n in nodes if n.node_id == node_id), node_id)
                          for node_id in cycle_nodes]
            
            self.logger.error(f"Workflow contains cycles involving nodes: {', '.join(node_labels)}")
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
        # Get incoming connections (optimized by using cached connections from execution_order)
        # In a real implementation, we'd pass the connections list to avoid another query
        incoming = [conn for conn in workflow.connections.all() if conn.target_node_id == node.id]

        if not incoming:
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
                # Safe evaluation using a simple expression parser
                return self._safe_eval_expression(expression, data)
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

    def _should_retry_node(self, node: WorkflowNode, node_result: Dict[str, Any], execution: WorkflowExecution) -> bool:
        """
        Determine if a node should be retried based on configuration and error type.
        """
        # Check if node has retry enabled
        if not node.retry_on_failure:
            return False
        
        # Check if we've exceeded max retries
        retry_count = execution.node_logs.count()
        if retry_count >= node.max_retries:
            return False
        
        # Check error type - some errors shouldn't be retried
        error_message = node_result.get('error', '').lower()
        
        # Don't retry configuration errors
        non_retryable_errors = [
            'not configured',
            'not found',
            'permission denied',
            'authentication',
            'invalid',
            'malformed'
        ]
        
        for error_type in non_retryable_errors:
            if error_type in error_message:
                return False
        
        # Retry for network errors, timeouts, etc.
        retryable_errors = [
            'timeout',
            'connection',
            'network',
            'temporary',
            'rate limit'
        ]
        
        for error_type in retryable_errors:
            if error_type in error_message:
                return True
        
        # Default to retry for unknown errors if retries are enabled
        return True
    
    def _retry_node(self, node: WorkflowNode, input_data: Dict[str, Any], execution: WorkflowExecution) -> Dict[str, Any]:
        """
        Retry a node execution with exponential backoff.
        """
        import time
        
        # Calculate backoff delay (exponential with jitter)
        retry_count = len([log for log in execution.node_logs if log.get('node_id') == node.node_id])
        base_delay = 2  # seconds
        max_delay = 30  # seconds
        delay = min(base_delay * (2 ** retry_count), max_delay)
        
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, 0.1 * delay)
        time.sleep(delay + jitter)
        
        self.logger.info(f"Retrying node {node.label} (attempt {retry_count + 1}) after {delay:.2f}s delay")
        
        # Execute the node again
        return self._execute_node(node, input_data, execution)

    def _safe_eval_expression(self, expression: str, data: Any) -> bool:
        """
        Safely evaluate a simple expression without using eval().
        
        Supports basic comparisons and logical operations on data fields.
        """
        import ast
        import operator
        
        # Define safe operators
        operators = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.And: lambda a, b: a and b,
            ast.Or: lambda a, b: a or b,
            ast.Not: lambda a: not a,
            ast.In: lambda a, b: a in b,
            ast.NotIn: lambda a, b: a not in b,
        }
        
        def _eval(node):
            if isinstance(node, ast.BoolOp):
                result = True
                if isinstance(node.op, ast.And):
                    for value in node.values:
                        result = result and _eval(value)
                        if not result:
                            break
                elif isinstance(node.op, ast.Or):
                    for value in node.values:
                        result = result or _eval(value)
                        if result:
                            break
                return result
                
            elif isinstance(node, ast.UnaryOp):
                if isinstance(node.op, ast.Not):
                    return not _eval(node.operand)
                else:
                    raise ValueError(f"Unsupported unary operator: {node.op}")
                    
            elif isinstance(node, ast.Compare):
                left = _eval(node.left)
                for op, right in zip(node.ops, node.comparators):
                    right_val = _eval(right)
                    if not isinstance(op, (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)):
                        raise ValueError(f"Unsupported comparison operator: {op}")
                    if not operators[type(op)](left, right_val):
                        return False
                    left = right_val
                return True
                
            elif isinstance(node, ast.Name):
                # Allow access to 'data' variable
                if node.id == 'data':
                    return data
                else:
                    raise ValueError(f"Unknown variable: {node.id}")
                    
            elif isinstance(node, ast.Constant):
                return node.value
                
            elif isinstance(node, ast.Attribute):
                # Allow simple attribute access on data
                if isinstance(node.value, ast.Name) and node.value.id == 'data':
                    if isinstance(data, dict):
                        return data.get(node.attr)
                    else:
                        return getattr(data, node.attr, None)
                else:
                    raise ValueError("Only attribute access on 'data' is allowed")
                    
            elif isinstance(node, ast.Subscript):
                # Allow dictionary/list access on data
                if isinstance(node.value, ast.Name) and node.value.id == 'data':
                    data_val = data
                    if isinstance(node.slice, ast.Constant):
                        key = node.slice.value
                    elif isinstance(node.slice, ast.Name):
                        key = _eval(node.slice)
                    else:
                        raise ValueError("Only simple indexing is allowed")
                    
                    if isinstance(data_val, dict):
                        return data_val.get(key)
                    elif isinstance(data_val, (list, tuple)):
                        return data_val[key] if isinstance(key, int) else None
                    else:
                        return None
                else:
                    raise ValueError("Only subscript access on 'data' is allowed")
                    
            else:
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")
        
        try:
            # Parse the expression
            tree = ast.parse(expression, mode='eval')
            return _eval(tree.body)
        except Exception as e:
            self.logger.error(f"Expression evaluation error: {e}")
            return False


# Singleton instance
workflow_engine = WorkflowExecutionEngine()
