"""
Node Executors for different workflow node types.

Each executor handles the execution logic for a specific node type.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class BaseNodeExecutor(ABC):
    """Base class for node executors."""

    @abstractmethod
    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        """
        Execute the node logic.

        Args:
            node: WorkflowNode instance
            input_data: Input data from predecessor nodes
            execution: WorkflowExecution instance

        Returns:
            Output data dict
        """
        pass


# =============================================================================
# DATA SOURCE EXECUTORS
# =============================================================================

class GoogleDocsExecutor(BaseNodeExecutor):
    """Fetch data from Google Docs."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from apps.core.integration_services import GoogleIntegrationService
        
        config = node.config
        doc_id = config.get('document_id')

        if not doc_id:
            raise ValueError("document_id not configured")

        # Get Google access token using existing integration service
        google_service = GoogleIntegrationService()
        access_token = google_service.get_access_token(execution.workflow.owner)
        
        if not access_token:
            raise ValueError("Google integration not configured or token expired. Please connect your Google account in Settings > Integrations.")

        # Fetch document content using Google Docs API
        try:
            import requests
            
            # Use Google Docs API to fetch document content
            docs_api_url = f"https://docs.googleapis.com/v1/documents/{doc_id}"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(docs_api_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                doc_data = response.json()
                
                # Extract text content from the document structure
                content = self._extract_text_from_doc(doc_data)
                
                return {
                    'content': content,
                    'document_id': doc_id,
                    'title': doc_data.get('title', 'Untitled Document'),
                    'revision_id': doc_data.get('revisionId'),
                    'document_url': f"https://docs.google.com/document/d/{doc_id}"
                }
            elif response.status_code == 403:
                raise ValueError(f"Access denied to Google Doc {doc_id}. Please check document permissions.")
            elif response.status_code == 404:
                raise ValueError(f"Google Doc {doc_id} not found.")
            else:
                raise ValueError(f"Failed to fetch Google Doc: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to fetch Google Doc {doc_id}: {e}")
            raise
    
    def _extract_text_from_doc(self, doc_data: Dict[str, Any]) -> str:
        """Extract plain text content from Google Docs API response."""
        content = []
        
        body = doc_data.get('body', {})
        content_elements = body.get('content', [])
        
        for element in content_elements:
            if 'paragraph' in element:
                paragraph = element['paragraph']
                paragraph_elements = paragraph.get('elements', [])
                
                for para_element in paragraph_elements:
                    if 'textRun' in para_element:
                        text_run = para_element['textRun']
                        text_content = text_run.get('content', '')
                        content.append(text_content)
        
        return ''.join(content).strip()


class CustomURLExecutor(BaseNodeExecutor):
    """Fetch data from a custom URL."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        url = config.get('url')
        method = config.get('method', 'GET')
        headers = config.get('headers', {})
        params = config.get('params', {})
        body = config.get('body', {})

        if not url:
            raise ValueError("URL not configured")

        # Replace variables in URL with input data
        url = url.format(**input_data) if '{' in url else url

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if method in ['POST', 'PUT', 'PATCH'] else None,
                timeout=node.timeout_seconds
            )
            response.raise_for_status()

            # Try to parse JSON response
            try:
                return {
                    'data': response.json(),
                    'status_code': response.status_code,
                    'headers': dict(response.headers)
                }
            except ValueError:
                return {
                    'data': response.text,
                    'status_code': response.status_code,
                    'headers': dict(response.headers)
                }

        except requests.RequestException as e:
            logger.error(f"Failed to fetch from URL {url}: {e}")
            raise


class WebhookInputExecutor(BaseNodeExecutor):
    """Receive data from webhook."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        # For webhook inputs, data comes from the trigger
        trigger_data = execution.trigger_data

        if execution.trigger_type != 'webhook':
            return {'data': input_data}

        return {
            'data': trigger_data.get('payload', {}),
            'headers': trigger_data.get('headers', {}),
            'method': trigger_data.get('method', 'POST')
        }


class DatabaseQueryExecutor(BaseNodeExecutor):
    """Execute database query."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from django.db import connection

        config = node.config
        query = config.get('query')
        params = config.get('params', [])

        if not query:
            raise ValueError("Query not configured")

        # Replace variables in query with input data
        query = query.format(**input_data) if '{' in query else query

        with connection.cursor() as cursor:
            cursor.execute(query, params)

            if query.strip().upper().startswith('SELECT'):
                columns = [col[0] for col in cursor.description]
                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
                return {'data': results, 'count': len(results)}
            else:
                return {'affected_rows': cursor.rowcount}


# =============================================================================
# PROCESSOR EXECUTORS
# =============================================================================

class LLMProcessorExecutor(BaseNodeExecutor):
    """Process data using LLM."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        prompt_template = config.get('prompt_template', '')
        model = config.get('model', 'gpt-3.5-turbo')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 1000)

        # Format prompt with input data
        prompt = prompt_template.format(**input_data) if '{' in prompt_template else prompt_template

        # Check if using local LLM or API
        llm_provider = config.get('provider', 'openai')

        if llm_provider == 'local':
            # Use local LLM (e.g., deployed in platform)
            return self._execute_local_llm(prompt, config)
        else:
            # Use external API (OpenAI, Anthropic, etc.)
            return self._execute_api_llm(prompt, model, temperature, max_tokens, config)

    def _execute_local_llm(self, prompt: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute using local LLM deployed in platform."""
        # This would integrate with a locally deployed LLM service
        # For now, return placeholder
        return {
            'response': f"[Local LLM Response to: {prompt[:50]}...]",
            'model': 'local',
            'tokens_used': 0
        }

    def _execute_api_llm(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute using external LLM API."""
        api_key = config.get('api_key') or getattr(settings, 'OPENAI_API_KEY', None)

        if not api_key:
            raise ValueError("API key not configured for LLM")

        # Example OpenAI API call
        try:
            import openai
            openai.api_key = api_key

            response = openai.ChatCompletion.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            return {
                'response': response.choices[0].message.content,
                'model': model,
                'tokens_used': response.usage.total_tokens,
                'finish_reason': response.choices[0].finish_reason
            }

        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise


class TransformExecutor(BaseNodeExecutor):
    """Transform data using various methods."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        transform_type = config.get('transform_type', 'jmespath')

        if transform_type == 'jmespath':
            import jmespath
            query = config.get('query')
            result = jmespath.search(query, input_data)
            return {'data': result}

        elif transform_type == 'jsonpath':
            from jsonpath_ng import parse
            query = config.get('query')
            expr = parse(query)
            matches = [match.value for match in expr.find(input_data)]
            return {'data': matches}

        elif transform_type == 'python':
            # Execute Python code transformation
            code = config.get('code')
            local_vars = {'input_data': input_data, 'output': {}}

            exec(code, {'__builtins__': {}}, local_vars)

            return local_vars.get('output', {})

        return {'data': input_data}


class FilterExecutor(BaseNodeExecutor):
    """Filter data based on conditions."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        filter_type = config.get('filter_type', 'expression')

        if filter_type == 'expression':
            expression = config.get('expression')
            data_list = input_data.get('data', [])

            if not isinstance(data_list, list):
                data_list = [data_list]

            filtered = [
                item for item in data_list
                if eval(expression, {'__builtins__': {}}, {'item': item})
            ]

            return {'data': filtered, 'count': len(filtered)}

        return {'data': input_data}


# =============================================================================
# OUTPUT EXECUTORS
# =============================================================================

class EmailOutputExecutor(BaseNodeExecutor):
    """Send email output."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from django.core.mail import send_mail

        config = node.config
        to_emails = config.get('to_emails', [])
        subject = config.get('subject', 'Workflow Output')
        body_template = config.get('body_template', '')

        # Format body with input data
        body = body_template.format(**input_data) if '{' in body_template else str(input_data)

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to_emails,
            fail_silently=False
        )

        return {
            'sent': True,
            'recipients': to_emails,
            'subject': subject
        }


class WebhookOutputExecutor(BaseNodeExecutor):
    """Send data to webhook."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        url = config.get('url')
        method = config.get('method', 'POST')
        headers = config.get('headers', {})

        if not url:
            raise ValueError("Webhook URL not configured")

        response = requests.request(
            method=method,
            url=url,
            json=input_data,
            headers=headers,
            timeout=node.timeout_seconds
        )
        response.raise_for_status()

        return {
            'sent': True,
            'status_code': response.status_code,
            'response': response.text[:1000]  # Truncate response
        }


class DatabaseWriteExecutor(BaseNodeExecutor):
    """Write data to database."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from django.db import connection

        config = node.config
        query = config.get('query')
        data = input_data.get('data', input_data)

        if not query:
            raise ValueError("Query not configured")

        with connection.cursor() as cursor:
            if isinstance(data, list):
                # Batch insert
                for item in data:
                    cursor.execute(query, item)
                return {'inserted': len(data)}
            else:
                cursor.execute(query, data)
                return {'affected_rows': cursor.rowcount}


# =============================================================================
# NODE EXECUTOR REGISTRY
# =============================================================================

class NodeExecutorRegistry:
    """Registry for node executors."""

    def __init__(self):
        self._executors = {
            # Data Sources
            'google_docs': GoogleDocsExecutor(),
            'DATA_SOURCE_GOOGLE_DOCS': GoogleDocsExecutor(),
            'custom_url': CustomURLExecutor(),
            'DATA_SOURCE_CUSTOM_URL': CustomURLExecutor(),
            'webhook': WebhookInputExecutor(),
            'DATA_SOURCE_WEBHOOK': WebhookInputExecutor(),
            'database': DatabaseQueryExecutor(),
            'DATA_SOURCE_DATABASE': DatabaseQueryExecutor(),

            # Processors
            'llm': LLMProcessorExecutor(),
            'PROCESSOR_LLM': LLMProcessorExecutor(),
            'transform': TransformExecutor(),
            'PROCESSOR_TRANSFORM': TransformExecutor(),
            'filter': FilterExecutor(),
            'PROCESSOR_FILTER': FilterExecutor(),

            # Outputs
            'email': EmailOutputExecutor(),
            'OUTPUT_EMAIL': EmailOutputExecutor(),
            'webhook_output': WebhookOutputExecutor(),
            'OUTPUT_WEBHOOK': WebhookOutputExecutor(),
            'database_output': DatabaseWriteExecutor(),
            'OUTPUT_DATABASE': DatabaseWriteExecutor(),
        }

    def get_executor(self, node_type: str) -> BaseNodeExecutor:
        """Get executor for node type."""
        executor = self._executors.get(node_type)

        if not executor:
            # Default executor that passes through data
            logger.warning(f"No executor found for node type {node_type}, using passthrough")
            return PassthroughExecutor()

        return executor

    def register_executor(self, node_type: str, executor: BaseNodeExecutor):
        """Register custom executor."""
        self._executors[node_type] = executor


class PassthroughExecutor(BaseNodeExecutor):
    """Default executor that passes data through unchanged."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        return input_data
