"""
Workflow validation utilities.

This module provides validation for workflows and their components.
"""

from typing import Dict, List, Any, Tuple, Optional
import re
import logging

from .models import Workflow, WorkflowNode, WorkflowConnection

logger = logging.getLogger(__name__)


class WorkflowValidationError(Exception):
    """Exception raised when workflow validation fails."""
    pass


class WorkflowValidator:
    """
    Validates workflow structure and node configurations.
    """
    
    @staticmethod
    def validate_workflow(workflow: Workflow) -> Tuple[bool, List[str]]:
        """
        Validate a workflow for structural and configuration issues.
        
        Args:
            workflow: Workflow instance to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Basic validation
        if not workflow.name:
            errors.append("Workflow name is required")
        
        # Check if workflow has nodes
        nodes = list(workflow.nodes.all())
        if not nodes:
            errors.append("Workflow must have at least one node")
            return False, errors
        
        # Validate each node
        node_errors = WorkflowValidator._validate_nodes(nodes)
        errors.extend(node_errors)
        
        # Check for cycles
        from .engine import WorkflowExecutionEngine
        engine = WorkflowExecutionEngine()
        execution_order = engine._get_execution_order(workflow)
        if execution_order is None:
            errors.append("Workflow contains cycles")
        
        # Validate connections
        connections = list(workflow.connections.all())
        connection_errors = WorkflowValidator._validate_connections(connections, nodes)
        errors.extend(connection_errors)
        
        # Check for isolated nodes (nodes with no connections)
        if WorkflowValidator._has_isolated_nodes(nodes, connections):
            errors.append("Workflow has isolated nodes (nodes with no connections)")
        
        # Validate trigger configuration
        trigger_errors = WorkflowValidator._validate_trigger_config(workflow)
        errors.extend(trigger_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_nodes(nodes: List[WorkflowNode]) -> List[str]:
        """Validate individual nodes."""
        errors = []
        
        for node in nodes:
            # Check node has a valid ID
            if not node.node_id:
                errors.append(f"Node {node.label or '(unnamed)'} has no ID")
                continue
            
            # Check node type is valid
            if not node.node_type:
                errors.append(f"Node {node.node_id} has no type")
                continue
            
            # Validate node configuration based on type
            config_errors = WorkflowValidator._validate_node_config(node)
            errors.extend(config_errors)
        
        return errors
    
    @staticmethod
    def _validate_node_config(node: WorkflowNode) -> List[str]:
        """Validate node-specific configuration."""
        errors = []
        config = node.config or {}
        
        # URL nodes must have a valid URL
        if node.node_type in ['custom_url', 'DATA_SOURCE_CUSTOM_URL']:
            url = config.get('url')
            if not url:
                errors.append(f"URL node '{node.node_id}' has no URL configured")
            elif not WorkflowValidator._is_valid_url(url):
                errors.append(f"URL node '{node.node_id}' has invalid URL: {url}")
        
        # Database nodes must have a query
        elif node.node_type in ['database', 'DATA_SOURCE_DATABASE']:
            query = config.get('query')
            if not query:
                errors.append(f"Database node '{node.node_id}' has no query configured")
            elif WorkflowValidator._has_unsafe_sql_patterns(query):
                errors.append(f"Database node '{node.node_id}' contains potentially unsafe SQL patterns")
        
        # Email nodes must have recipients
        elif node.node_type in ['email', 'OUTPUT_EMAIL']:
            to_emails = config.get('to_emails', [])
            if not to_emails:
                errors.append(f"Email node '{node.node_id}' has no recipients configured")
            else:
                for email in to_emails:
                    if not WorkflowValidator._is_valid_email(email):
                        errors.append(f"Email node '{node.node_id}' has invalid email address: {email}")
        
        # LLM nodes must have a prompt template
        elif node.node_type in ['llm', 'PROCESSOR_LLM']:
            prompt = config.get('prompt_template')
            if not prompt:
                errors.append(f"LLM node '{node.node_id}' has no prompt template configured")
        
        # Transform nodes must have valid configuration
        elif node.node_type in ['transform', 'PROCESSOR_TRANSFORM']:
            transform_type = config.get('transform_type')
            if not transform_type:
                errors.append(f"Transform node '{node.node_id}' has no transform type configured")
            elif transform_type == 'python':
                code = config.get('code')
                if not code:
                    errors.append(f"Transform node '{node.node_id}' has no Python code configured")
                elif WorkflowValidator._has_unsafe_python_patterns(code):
                    errors.append(f"Transform node '{node.node_id}' contains potentially unsafe Python code")
            elif transform_type in ['jmespath', 'jsonpath']:
                query = config.get('query')
                if not query:
                    errors.append(f"Transform node '{node.node_id}' has no query configured")
        
        # Filter nodes must have a valid expression
        elif node.node_type in ['filter', 'PROCESSOR_FILTER']:
            filter_type = config.get('filter_type')
            if not filter_type:
                errors.append(f"Filter node '{node.node_id}' has no filter type configured")
            elif filter_type == 'expression':
                expression = config.get('expression')
                if not expression:
                    errors.append(f"Filter node '{node.node_id}' has no expression configured")
        
        return errors
    
    @staticmethod
    def _validate_connections(connections: List[WorkflowConnection], nodes: List[WorkflowNode]) -> List[str]:
        """Validate connections between nodes."""
        errors = []
        node_ids = {node.node_id for node in nodes}
        
        for conn in connections:
            # Check source and target nodes exist
            if conn.source_node.node_id not in node_ids:
                errors.append(f"Connection references non-existent source node: {conn.source_node.node_id}")
            
            if conn.target_node.node_id not in node_ids:
                errors.append(f"Connection references non-existent target node: {conn.target_node.node_id}")
            
            # Check for self-connections
            if conn.source_node.node_id == conn.target_node.node_id:
                errors.append(f"Node {conn.source_node.node_id} has a self-connection")
        
        return errors
    
    @staticmethod
    def _has_isolated_nodes(nodes: List[WorkflowNode], connections: List[WorkflowConnection]) -> bool:
        """Check if any nodes are isolated (no connections)."""
        if not connections:
            return len(nodes) > 1  # Single node workflows are OK
        
        connected_nodes = set()
        for conn in connections:
            connected_nodes.add(conn.source_node.node_id)
            connected_nodes.add(conn.target_node.node_id)
        
        # Check if any nodes are not connected
        for node in nodes:
            if node.node_id not in connected_nodes:
                return True
        
        return False
    
    @staticmethod
    def _validate_trigger_config(workflow: Workflow) -> List[str]:
        """Validate workflow trigger configuration."""
        errors = []
        
        if workflow.trigger_type == Workflow.TriggerType.SCHEDULE:
            if not workflow.schedule_cron:
                errors.append("Scheduled workflow must have a cron expression")
            else:
                # Validate cron expression
                try:
                    from croniter import croniter
                    croniter(workflow.schedule_cron)
                except Exception as e:
                    errors.append(f"Invalid cron expression: {e}")
        
        return errors
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if URL is valid and safe."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Check if email address is valid."""
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        return email_pattern.match(email) is not None
    
    @staticmethod
    def _has_unsafe_sql_patterns(query: str) -> bool:
        """Check for potentially unsafe SQL patterns."""
        # Convert to lowercase for case-insensitive matching
        query_lower = query.lower()
        
        # Check for dangerous patterns
        dangerous_patterns = [
            'drop table',
            'truncate table',
            'delete from',
            'update set',
            'insert into',
            'create table',
            'alter table',
            'exec(',
            'xp_cmdshell',
            'sp_executesql',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                return True
        
        return False
    
    @staticmethod
    def _has_unsafe_python_patterns(code: str) -> bool:
        """Check for potentially unsafe Python code patterns."""
        # Parse the code to check for dangerous operations
        import ast
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True  # Invalid syntax is considered unsafe
        
        # Check for dangerous operations
        for node in ast.walk(tree):
            # Disallow imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return True
            
            # Disallow function definitions
            if isinstance(node, ast.FunctionDef):
                return True
            
            # Disallow calls to dangerous functions
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['exec', 'eval', 'compile', '__import__', 'open', 'file']:
                    return True
        
        return False