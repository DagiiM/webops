"""
Tests for workflow validators.
"""

import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import Mock, patch

from apps.automation.models import Workflow, WorkflowNode, WorkflowConnection
from apps.automation.validators import WorkflowValidator, WorkflowValidationError


class WorkflowValidatorTest(TestCase):
    """Test the WorkflowValidator class."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user,
            status=Workflow.Status.DRAFT
        )
    
    def test_validate_empty_workflow(self):
        """Test validation of empty workflow."""
        # Empty workflow should be invalid
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertIn("Workflow must have at least one node", errors)
    
    def test_validate_workflow_with_nodes(self):
        """Test validation of workflow with nodes."""
        # Add a node
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node1',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Test Node'
        )
        
        # Workflow with one node should be valid
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_node_without_id(self):
        """Test validation of node without ID."""
        node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='',  # Empty ID
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Test Node'
        )
        
        # Update node to have empty ID
        node.node_id = ''
        node.save()
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("has no ID" in error for error in errors))
    
    def test_validate_url_node_with_invalid_url(self):
        """Test validation of URL node with invalid URL."""
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='url_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_CUSTOM_URL,
            label='URL Node',
            config={'url': 'not-a-url'}
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("invalid URL" in error for error in errors))
    
    def test_validate_database_node_with_unsafe_sql(self):
        """Test validation of database node with unsafe SQL."""
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='db_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_DATABASE,
            label='DB Node',
            config={'query': 'DROP TABLE users;'}
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("unsafe SQL" in error for error in errors))
    
    def test_validate_email_node_with_invalid_email(self):
        """Test validation of email node with invalid email."""
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='email_node',
            node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
            label='Email Node',
            config={'to_emails': ['not-an-email']}
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("invalid email" in error for error in errors))
    
    def test_validate_transform_node_with_unsafe_python(self):
        """Test validation of transform node with unsafe Python."""
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='transform_node',
            node_type=WorkflowNode.NodeType.PROCESSOR_TRANSFORM,
            label='Transform Node',
            config={
                'transform_type': 'python',
                'code': 'import os; os.system("rm -rf /")'
            }
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("unsafe Python" in error for error in errors))
    
    def test_validate_workflow_with_cycles(self):
        """Test validation of workflow with cycles."""
        # Create two nodes
        node1 = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node1',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Node 1'
        )
        
        node2 = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node2',
            node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
            label='Node 2'
        )
        
        # Create connections that form a cycle
        WorkflowConnection.objects.create(
            workflow=self.workflow,
            source_node=node1,
            target_node=node2
        )
        
        WorkflowConnection.objects.create(
            workflow=self.workflow,
            source_node=node2,
            target_node=node1
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("cycles" in error for error in errors))
    
    def test_validate_workflow_with_isolated_nodes(self):
        """Test validation of workflow with isolated nodes."""
        # Create two nodes
        node1 = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node1',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Node 1'
        )
        
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node2',
            node_type=WorkflowNode.NodeType.OUTPUT_EMAIL,
            label='Node 2'
        )
        
        # Create a connection for only one node
        WorkflowConnection.objects.create(
            workflow=self.workflow,
            source_node=node1,
            target_node=node1  # Self-connection
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("isolated nodes" in error for error in errors))
    
    def test_validate_scheduled_workflow_without_cron(self):
        """Test validation of scheduled workflow without cron expression."""
        self.workflow.trigger_type = Workflow.TriggerType.SCHEDULE
        self.workflow.schedule_cron = ''  # Empty cron
        self.workflow.save()
        
        # Add a node
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node1',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Test Node'
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("cron expression" in error for error in errors))
    
    @patch('croniter.croniter')
    def test_validate_scheduled_workflow_with_invalid_cron(self, mock_croniter):
        """Test validation of scheduled workflow with invalid cron expression."""
        mock_croniter.side_effect = Exception("Invalid cron")
        
        self.workflow.trigger_type = Workflow.TriggerType.SCHEDULE
        self.workflow.schedule_cron = 'invalid cron'
        self.workflow.save()
        
        # Add a node
        WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='node1',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_WEBHOOK,
            label='Test Node'
        )
        
        is_valid, errors = WorkflowValidator.validate_workflow(self.workflow)
        
        self.assertFalse(is_valid)
        self.assertTrue(any("Invalid cron" in error for error in errors))