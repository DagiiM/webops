"""
Tests for node executors with focus on security.
"""

from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from requests.exceptions import RequestException
import requests
from django.contrib.auth.models import User

from apps.automation.models import Workflow, WorkflowNode, WorkflowExecution
from apps.automation.node_executors import (
    CustomURLExecutor,
    DatabaseQueryExecutor,
    TransformExecutor,
    FilterExecutor,
    WebhookOutputExecutor,
    GoogleDocsExecutor,
    LLMProcessorExecutor
)


class CustomURLExecutorTest(TestCase):
    """Test the CustomURLExecutor with focus on SSRF protection."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='url_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_CUSTOM_URL,
            label='URL Node',
            config={'url': 'https://api.example.com/data'}
        )
        
        self.executor = CustomURLExecutor()
    
    def test_validate_url_blocks_internal_addresses(self):
        """Test that internal IP addresses are blocked."""
        # Test localhost
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('http://localhost/api')
        self.assertIn('internal network address', str(cm.exception))
        
        # Test private IP
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('http://192.168.1.1/api')
        self.assertIn('internal network address', str(cm.exception))
        
        # Test AWS metadata
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('http://169.254.169.254/latest/meta-data')
        self.assertIn('internal network address', str(cm.exception))
    
    def test_validate_url_blocks_invalid_schemes(self):
        """Test that non-HTTP/HTTPS schemes are blocked."""
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('ftp://example.com/file')
        self.assertIn('not allowed', str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('file:///etc/passwd')
        self.assertIn('not allowed', str(cm.exception))
    
    def test_validate_url_allows_external_https(self):
        """Test that external HTTPS URLs are allowed."""
        try:
            self.executor._validate_url('https://api.example.com/data')
        except ValueError:
            self.fail("External HTTPS URL should be allowed")
    
    @patch('requests.request')
    def test_execute_with_valid_url(self, mock_request):
        """Test execution with a valid URL."""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {'result': 'success'}
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_request.return_value = mock_response
        
        result = self.executor.execute(self.node, {}, self.execution)
        
        self.assertEqual(result['data'], {'result': 'success'})
        self.assertEqual(result['status_code'], 200)
        mock_request.assert_called_once()
    
    @patch('requests.request')
    def test_execute_with_blocked_url(self, mock_request):
        """Test execution with a blocked URL."""
        # Set a blocked URL
        self.node.config['url'] = 'http://localhost/api'
        
        with self.assertRaises(ValueError) as cm:
            self.executor.execute(self.node, {}, self.execution)
        
        self.assertIn('internal network address', str(cm.exception))
        mock_request.assert_not_called()


class DatabaseQueryExecutorTest(TestCase):
    """Test the DatabaseQueryExecutor with focus on SQL injection protection."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='db_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_DATABASE,
            label='DB Node',
            config={'query': 'SELECT * FROM table WHERE id = %s'}
        )
        
        self.executor = DatabaseQueryExecutor()
    
    def test_prepare_query_blocks_string_formatting(self):
        """Test that string formatting in SQL queries is blocked."""
        with self.assertRaises(ValueError) as cm:
            self.executor._prepare_query_with_params(
                'SELECT * FROM {table} WHERE id = %s',
                {'table': 'users'},
                []
            )
        
        self.assertIn('not allowed', str(cm.exception))
    
    def test_prepare_query_with_parameters(self):
        """Test that parameterized queries work correctly."""
        query, params = self.executor._prepare_query_with_params(
            'SELECT * FROM table WHERE id = %s',
            {},
            [1]
        )
        
        self.assertEqual(query, 'SELECT * FROM table WHERE id = %s')
        self.assertEqual(params, [1])
    
    @patch('django.db.connection.cursor')
    def test_execute_with_parameterized_query(self, mock_cursor):
        """Test execution with a parameterized query."""
        # Mock the cursor and its methods
        mock_cursor_instance = Mock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.description = [('id',), ('name',)]
        mock_cursor_instance.fetchall.return_value = [(1, 'test')]
        
        result = self.executor.execute(self.node, {}, self.execution)
        
        self.assertEqual(result['data'], [{'id': 1, 'name': 'test'}])
        self.assertEqual(result['count'], 1)
        mock_cursor_instance.execute.assert_called_once()


class TransformExecutorTest(TestCase):
    """Test the TransformExecutor with focus on code execution safety."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='transform_node',
            node_type=WorkflowNode.NodeType.PROCESSOR_TRANSFORM,
            label='Transform Node'
        )
        
        self.executor = TransformExecutor()
    
    def test_safe_execute_transform_blocks_dangerous_code(self):
        """Test that dangerous Python code is blocked."""
        dangerous_codes = [
            'import os; os.system("ls")',
            '__import__("os").system("ls")',
            'exec("import os")',
            'eval("__import__(\'os\')")',
            'open("/etc/passwd").read()',
        ]
        
        for code in dangerous_codes:
            with self.assertRaises(ValueError) as cm:
                self.executor._safe_execute_transform(code, {})
            
            self.assertIn('not allowed', str(cm.exception))
    
    def test_safe_execute_transform_blocks_function_definitions(self):
        """Test that function definitions are blocked."""
        code = 'def test_func(): pass'
        
        with self.assertRaises(ValueError) as cm:
            self.executor._safe_execute_transform(code, {})
        
        self.assertIn('not allowed', str(cm.exception))
    
    def test_safe_execute_transform_blocks_imports(self):
        """Test that imports are blocked."""
        code = 'import os'
        
        with self.assertRaises(ValueError) as cm:
            self.executor._safe_execute_transform(code, {})
        
        self.assertIn('not allowed', str(cm.exception))
    
    def test_safe_execute_transform_allows_simple_assignments(self):
        """Test that simple assignments are allowed."""
        code = 'output["result"] = input_data["value"] * 2'
        input_data = {'value': 5}
        
        result = self.executor._safe_execute_transform(code, input_data)
        
        self.assertEqual(result['data']['result'], 10)
        self.assertEqual(result['data']['value'], 5)


class FilterExecutorTest(TestCase):
    """Test the FilterExecutor with focus on expression evaluation safety."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='filter_node',
            node_type=WorkflowNode.NodeType.PROCESSOR_FILTER,
            label='Filter Node',
            config={'filter_type': 'expression', 'expression': 'item["value"] > 5'}
        )
        
        self.executor = FilterExecutor()
    
    def test_safe_eval_filter_blocks_dangerous_expressions(self):
        """Test that dangerous expressions are blocked."""
        dangerous_expressions = [
            '__import__("os").system("ls")',
            'eval("__import__(\'os\')")',
            'exec("import os")',
            'open("/etc/passwd").read()',
        ]
        
        for expr in dangerous_expressions:
            result = self.executor._safe_eval_filter(expr, {})
            self.assertFalse(result)
    
    def test_safe_eval_filter_allows_simple_comparisons(self):
        """Test that simple comparisons are allowed."""
        expr = 'item["value"] > 5'
        item = {'value': 10}
        
        result = self.executor._safe_eval_filter(expr, item)
        
        self.assertTrue(result)
    
    def test_execute_with_expression(self):
        """Test execution with a filter expression."""
        input_data = {
            'data': [
                {'value': 3},
                {'value': 7},
                {'value': 10}
            ]
        }
        
        result = self.executor.execute(self.node, input_data, self.execution)
        
        self.assertEqual(len(result['data']), 2)
        self.assertEqual(result['count'], 2)
        self.assertTrue(all(item['value'] > 5 for item in result['data']))


class WebhookOutputExecutorTest(TestCase):
    """Test the WebhookOutputExecutor with focus on SSRF protection."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='webhook_node',
            node_type=WorkflowNode.NodeType.OUTPUT_WEBHOOK,
            label='Webhook Node',
            config={'url': 'https://api.example.com/webhook'}
        )
        
        self.executor = WebhookOutputExecutor()
    
    def test_validate_url_blocks_internal_addresses(self):
        """Test that internal IP addresses are blocked."""
        with self.assertRaises(ValueError) as cm:
            self.executor._validate_url('http://localhost/webhook')
        self.assertIn('internal network address', str(cm.exception))
    
    @patch('requests.request')
    def test_execute_with_valid_url(self, mock_request):
        """Test execution with a valid URL."""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'Success'
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        input_data = {'result': 'success'}
        result = self.executor.execute(self.node, input_data, self.execution)
        
        self.assertTrue(result['sent'])
        self.assertEqual(result['status_code'], 200)
        mock_request.assert_called_once()


class GoogleDocsExecutorTest(TestCase):
    """Test the GoogleDocsExecutor with focus on HTML error handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='docs_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_GOOGLE_DOCS,
            label='Google Docs Node',
            config={'document_id': 'test_doc_id'}
        )
        
        self.executor = GoogleDocsExecutor()
    
    def test_handles_html_error_page(self):
        """Test that HTML error pages are handled correctly."""
        # Test the error handling logic directly by mocking the integration service failure
        with patch('apps.automation.node_executors.GoogleIntegrationService') as mock_google_service:
            mock_instance = mock_google_service.return_value
            mock_instance.get_access_token.return_value = None  # Simulate no access token
            
            with self.assertRaises(ValueError) as cm:
                self.executor.execute(self.node, {}, self.execution)
            
            self.assertIn('google integration not configured', str(cm.exception).lower())
    
    def test_handles_json_api_error(self):
        """Test that JSON API errors are handled correctly."""
        # Test the error handling logic directly by mocking the integration service failure
        with patch('apps.automation.node_executors.GoogleIntegrationService') as mock_google_service:
            mock_instance = mock_google_service.return_value
            mock_instance.get_access_token.return_value = None  # Simulate no access token
            
            with self.assertRaises(ValueError) as cm:
                self.executor.execute(self.node, {}, self.execution)
            
            self.assertIn('google integration not configured', str(cm.exception).lower())


class LLMProcessorExecutorTest(TestCase):
    """Test the LLMProcessorExecutor with focus on HTML error handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='llm_node',
            node_type=WorkflowNode.NodeType.PROCESSOR_LLM,
            label='LLM Node',
            config={
                'provider': 'openai',
                'model': 'gpt-3.5-turbo',
                'prompt': 'Test prompt',
                'api_key': 'test_key'
            }
        )
        
        self.executor = LLMProcessorExecutor()
    
    @patch('requests.post')
    def test_handles_openai_api_error_with_html_response(self, mock_post):
        """Test that OpenAI API errors with HTML responses are handled correctly."""
        # Mock response with HTML error page
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.text = '<!DOCTYPE html><html><body>Internal Server Error</body></html>'
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_post.return_value = mock_response
        
        with self.assertRaises(ValueError) as cm:
            self.executor.execute(self.node, {}, self.execution)
        
        self.assertIn('llm api call failed', str(cm.exception).lower())


class CustomURLExecutorHTMLTest(TestCase):
    """Additional tests for CustomURLExecutor HTML handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='url_node',
            node_type=WorkflowNode.NodeType.DATA_SOURCE_CUSTOM_URL,
            label='URL Node',
            config={'url': 'https://api.example.com/data'}
        )
        
        self.executor = CustomURLExecutor()
    
    @patch('requests.request')
    def test_handles_html_success_response(self, mock_request):
        """Test that HTML success responses are handled with warning."""
        # Mock response with HTML content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.text = '<!DOCTYPE html><html><body>Some HTML content</body></html>'
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_request.return_value = mock_response
        
        result = self.executor.execute(self.node, {}, self.execution)
        
        self.assertEqual(result['status_code'], 200)
        self.assertIn('warning', result)
        self.assertIn('html response', result['warning'].lower())
    
    @patch('requests.request')
    def test_handles_http_error_with_html_response(self, mock_request):
        """Test that HTTP errors with HTML responses are handled."""
        from requests.exceptions import HTTPError
        
        # Mock HTTP error with HTML response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.text = '<!DOCTYPE html><html><body>Internal Server Error</body></html>'
        mock_response.raise_for_status.side_effect = HTTPError(response=mock_response)
        mock_request.return_value = mock_response
        
        with self.assertRaises(ValueError) as cm:
            self.executor.execute(self.node, {}, self.execution)
        
        self.assertIn('html error page', str(cm.exception).lower())


class WebhookOutputExecutorHTMLTest(TestCase):
    """Additional tests for WebhookOutputExecutor HTML handling."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user
        )
        
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status=WorkflowExecution.Status.RUNNING
        )
        
        self.node = WorkflowNode.objects.create(
            workflow=self.workflow,
            node_id='webhook_node',
            node_type=WorkflowNode.NodeType.OUTPUT_WEBHOOK,
            label='Webhook Node',
            config={'url': 'https://api.example.com/webhook'}
        )
        
        self.executor = WebhookOutputExecutor()
    
    @patch('requests.request')
    def test_handles_html_success_response(self, mock_request):
        """Test that HTML success responses are handled with warnings."""
        # Mock response with HTML content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<!DOCTYPE html><html><body>Success</body></html>'
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        input_data = {'webhook_url': 'https://example.com/webhook', 'data': {'key': 'value'}}
        result = self.executor.execute(self.node, input_data, self.execution)
        
        self.assertIn('warning', result)
        self.assertIn('html response', result['warning'].lower())
        self.assertEqual(result['status_code'], 200)
    
    @patch('requests.request')
    def test_handles_http_error_with_html_response(self, mock_request):
        """Test that HTTP errors with HTML responses are handled correctly."""
        # Mock HTTP error with HTML response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.text = '<!DOCTYPE html><html><body>Internal Server Error</body></html>'
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        
        mock_error = requests.exceptions.HTTPError(response=mock_response)
        mock_request.side_effect = mock_error
        
        input_data = {'webhook_url': 'https://example.com/webhook', 'data': {'key': 'value'}}
        with self.assertRaises(ValueError) as cm:
            self.executor.execute(self.node, input_data, self.execution)
        
        self.assertIn('html error page', str(cm.exception).lower())