"""
Node Executors for different workflow node types.

Each executor handles the execution logic for a specific node type.
"""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime
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
        from apps.core.integrations.services import GoogleIntegrationService
        
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
            
            # Check if response is JSON before trying to parse it
            content_type = response.headers.get('content-type', '').lower()
            
            if response.status_code == 200:
                # Only try to parse JSON if content-type indicates JSON
                if 'application/json' in content_type:
                    try:
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
                    except ValueError as e:
                        # If JSON parsing fails, log the response content for debugging
                        logger.error(f"Failed to parse Google Docs API response as JSON. Response content: {response.text[:500]}")
                        raise ValueError(f"Invalid response from Google Docs API. The API returned HTML instead of JSON. This usually indicates an authentication or permission issue.")
                else:
                    # If not JSON, log the response content
                    logger.error(f"Google Docs API returned non-JSON response. Content-Type: {content_type}, Response: {response.text[:500]}")
                    raise ValueError(f"Google Docs API returned an unexpected response format. Content-Type: {content_type}")
            elif response.status_code == 403:
                raise ValueError(f"Access denied to Google Doc {doc_id}. Please check document permissions.")
            elif response.status_code == 404:
                raise ValueError(f"Google Doc {doc_id} not found.")
            else:
                # For other error codes, try to get error message from response
                try:
                    error_data = response.json() if 'application/json' in content_type else {}
                    error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
                except:
                    error_msg = f"HTTP {response.status_code}"
                raise ValueError(f"Failed to fetch Google Doc: {error_msg}")
                
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
        
        # Validate URL to prevent SSRF attacks
        self._validate_url(url)

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
                # Response is not JSON - could be HTML error page or plain text
                response_text = response.text
                if response_text.strip().startswith('<!DOCTYPE') or response_text.strip().startswith('<html'):
                    logger.warning(f"URL {url} returned HTML content instead of JSON. Status: {response.status_code}")
                    return {
                        'data': response_text[:500],  # Truncate HTML
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'warning': 'Received HTML response instead of expected JSON format'
                    }
                else:
                    return {
                        'data': response_text,
                        'status_code': response.status_code,
                        'headers': dict(response.headers)
                    }

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code} error from URL {url}"
            
            # Try to extract meaningful error message from response
            try:
                if e.response.headers.get('content-type', '').lower().startswith('application/json'):
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                    elif isinstance(error_data, dict) and 'message' in error_data:
                        error_msg += f": {error_data['message']}"
                    else:
                        error_msg += f": {str(error_data)}"
                else:
                    # For non-JSON responses, include first 200 chars of response
                    error_text = e.response.text[:200]
                    if error_text.startswith('<!DOCTYPE') or error_text.startswith('<html'):
                        error_msg += ": Received HTML error page (check URL endpoint)"
                    else:
                        error_msg += f": {error_text}"
            except Exception:
                # If we can't parse the error response, just include basic info
                error_msg += f" (response parsing failed)"
            
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch from URL {url}: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _validate_url(self, url: str) -> None:
        """
        Validate URL to prevent SSRF attacks.
        
        Only allows HTTP/HTTPS to external services, blocking internal network access.
        """
        from urllib.parse import urlparse
        import ipaddress
        import socket
        
        try:
            parsed = urlparse(url)
            
            # Only allow HTTP and HTTPS schemes
            if parsed.scheme not in ('http', 'https'):
                raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are permitted.")
            
            # Resolve hostname to IP address
            if parsed.hostname:
                # Block localhost and private IP ranges
                try:
                    ip = socket.gethostbyname(parsed.hostname)
                    ip_obj = ipaddress.ip_address(ip)
                    
                    # Check if IP is private or localhost
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                        raise ValueError(f"Access to internal network address '{ip}' is not allowed")
                    
                    # Block common internal infrastructure IPs
                    blocked_ranges = [
                        ipaddress.ip_network('169.254.169.254/32'),  # AWS metadata
                        ipaddress.ip_network('metadata.google.internal/32'),  # GCP metadata
                    ]
                    
                    for blocked_range in blocked_ranges:
                        if ip_obj in blocked_range:
                            raise ValueError(f"Access to infrastructure address '{ip}' is not allowed")
                
                except socket.gaierror:
                    # If hostname can't be resolved, allow it (might be a DNS name)
                    pass
                
                # Block certain hostname patterns
                blocked_hostnames = [
                    'localhost',
                    'metadata.google.internal',
                    '169.254.169.254',
                ]
                
                if parsed.hostname.lower() in blocked_hostnames:
                    raise ValueError(f"Access to '{parsed.hostname}' is not allowed")
            
        except ValueError:
            # Re-raise our custom validation errors
            raise
        except Exception as e:
            # For any other parsing errors, block the request
            raise ValueError(f"Invalid URL format: {e}")


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

        # Safe parameter substitution - never use string formatting for SQL
        final_query, final_params = self._prepare_query_with_params(query, input_data, params)

        with connection.cursor() as cursor:
            cursor.execute(final_query, final_params)

            if final_query.strip().upper().startswith('SELECT'):
                columns = [col[0] for col in cursor.description]
                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]
                return {'data': results, 'count': len(results)}
            else:
                return {'affected_rows': cursor.rowcount}
    
    def _prepare_query_with_params(self, query: str, input_data: Dict[str, Any], params: list) -> tuple:
        """
        Safely prepare query with parameters.
        
        Uses parameterized queries instead of string formatting.
        """
        # Don't allow string formatting in SQL queries
        if '{' in query:
            raise ValueError("Direct string formatting in SQL queries is not allowed for security reasons")
        
        # If input_data should be used, convert to parameters
        if input_data and not params:
            # Create a parameterized query from input_data
            # This is a simplified approach - in production, you might want more sophisticated handling
            param_list = []
            param_dict = {}
            
            # Extract values from input_data
            for key, value in input_data.items():
                if isinstance(value, (str, int, float, bool)):
                    param_dict[f"param_{key}"] = value
                    param_list.append(value)
            
            # Replace named parameters with %s for PostgreSQL
            # Note: This is a simplified approach and might need adjustment based on database
            modified_query = query
            for key in param_dict.keys():
                modified_query = modified_query.replace(f"%({key})s", "%s")
            
            return modified_query, param_list
        
        return query, params


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

        except openai.error.AuthenticationError as e:
            logger.error(f"OpenAI API authentication failed: {e}")
            raise ValueError("OpenAI API key is invalid or expired")
        except openai.error.RateLimitError as e:
            logger.error(f"OpenAI API rate limit exceeded: {e}")
            raise ValueError("OpenAI API rate limit exceeded. Please try again later.")
        except openai.error.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                # Try to extract error message from response
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    raise ValueError(f"OpenAI API error: {error_msg}")
                except (ValueError, AttributeError):
                    # If response is not JSON (e.g., HTML error page)
                    error_content = getattr(e.response, 'text', str(e))[:200]
                    if error_content.startswith('<!DOCTYPE') or error_content.startswith('<html'):
                        raise ValueError("OpenAI API returned an HTML error page instead of JSON. This may indicate a service issue or network problem.")
                    else:
                        raise ValueError(f"OpenAI API error: {error_content}")
            else:
                raise ValueError(f"OpenAI API error: {str(e)}")
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise ValueError(f"LLM API call failed: {str(e)}")


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
            # Execute Python code transformation using a safe executor
            code = config.get('code')
            return self._safe_execute_transform(code, input_data)

        return {'data': input_data}
    
    def _safe_execute_transform(self, code: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely execute transformation code without using exec().
        
        Supports limited data transformation operations.
        """
        import ast
        import json
        import re
        
        # First, check for dangerous patterns using regex as a first line of defense
        dangerous_patterns = [
            r'\bimport\s+\w+',  # import statements
            r'\bfrom\s+\w+\s+import',  # from imports
            r'\bexec\s*\(',  # exec function
            r'\beval\s*\(',  # eval function
            r'\bcompile\s*\(',  # compile function
            r'\b__import__\s*\(',  # __import__ function
            r'\bos\.system\s*\(',  # os.system calls
            r'\bsubprocess\.',  # subprocess module
            r'\bopen\s*\(',  # file operations
            r'\bfile\s*\(',  # file constructor
            r'\binput\s*\(',  # input function
            r'\braw_input\s*\(',  # raw_input function (Python 2)
            r'\bglobals\s*\(',  # globals function
            r'\blocals\s*\(',  # locals function
            r'\bvars\s*\(',  # vars function
            r'\bdir\s*\(',  # dir function
            r'\bgetattr\s*\(',  # getattr function
            r'\bhasattr\s*\(',  # hasattr function
            r'\bsetattr\s*\(',  # setattr function
            r'\bdelattr\s*\(',  # delattr function
            r'\btype\s*\(',  # type function (can be dangerous)
            r'\bsuper\s*\(',  # super function
            r'\bclass\s+\w+',  # class definitions
            r'\bdef\s+\w+',  # function definitions
            r';',  # semicolon (multiple statements)
            r'\bwhile\s+',  # while loops
            r'\bfor\s+.*\bin\s+',  # for loops
            r'\btry\s*:',  # try blocks
            r'\bexcept\s*:',  # except blocks
            r'\bfinally\s*:',  # finally blocks
            r'\bwith\s+',  # with statements
            r'\blambda\s+',  # lambda functions
            r'\byield',  # yield statements
            r'\bassert\s+',  # assert statements
            r'\bprint\s*\(',  # print function (allowed but logged)
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                if pattern == r';':
                    raise ValueError("Multiple statements (semicolon) are not allowed")
                else:
                    match = re.search(pattern, code, re.IGNORECASE)
                    dangerous_code = match.group(0) if match else pattern
                    raise ValueError(f"Dangerous code pattern '{dangerous_code}' is not allowed")
        
        # Parse the code to check for safety using AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")
        
        # Check for dangerous operations in AST
        for node in ast.walk(tree):
            # Disallow function definitions, imports, exec, eval, etc.
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                raise ValueError("Function definitions, classes, and imports are not allowed")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ['exec', 'eval', 'compile', '__import__']:
                    raise ValueError(f"Dangerous function '{node.func.id}' is not allowed")
            # Disallow control flow statements
            if isinstance(node, (ast.While, ast.For, ast.If, ast.With, ast.Try, ast.ExceptHandler)):
                raise ValueError(f"Control flow statements like '{type(node).__name__}' are not allowed")
            # Disallow lambda expressions
            if isinstance(node, ast.Lambda):
                raise ValueError("Lambda expressions are not allowed")
        
        # For now, implement a simple transformation based on common patterns
        # In a production system, you might want to use a library like RestrictedPython
        
        # Extract common transformation patterns
        output = {}
        
        # Pattern 1: output['field'] = input_data['field'] or some transformation
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Subscript) and
                        isinstance(target.value, ast.Name) and
                        target.value.id == 'output' and
                        isinstance(target.slice, ast.Constant)):
                        
                        field_name = target.slice.value
                        
                        # Simple assignment from input_data
                        if (isinstance(node.value, ast.Subscript) and
                            isinstance(node.value.value, ast.Name) and
                            node.value.value.id == 'input_data' and
                            isinstance(node.value.slice, ast.Constant)):
                            
                            input_field = node.value.slice.value
                            if isinstance(input_data, dict):
                                output[field_name] = input_data.get(input_field)
                        
                        # String formatting
                        elif (isinstance(node.value, ast.BinOp) and
                              isinstance(node.value.op, ast.Add) and
                              isinstance(node.value.left, ast.Constant) and
                              isinstance(node.value.right, ast.Subscript) and
                              isinstance(node.value.right.value, ast.Name) and
                              node.value.right.value.id == 'input_data'):
                            
                            template = node.value.left.value
                            if isinstance(node.value.right.slice, ast.Constant):
                                input_field = node.value.right.slice.value
                                if isinstance(input_data, dict):
                                    value = input_data.get(input_field, '')
                                    output[field_name] = template + str(value)
        
        # If no valid transformations found, return a copy of input_data
        if not output:
            return {'data': input_data}
        
        return {'data': output}


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
                if self._safe_eval_filter(expression, item)
            ]

            return {'data': filtered, 'count': len(filtered)}

        return {'data': input_data}
    
    def _safe_eval_filter(self, expression: str, item: Any) -> bool:
        """
        Safely evaluate a filter expression without using eval().
        
        Supports basic comparisons on item fields.
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
                # Allow access to 'item' variable
                if node.id == 'item':
                    return item
                else:
                    raise ValueError(f"Unknown variable: {node.id}")
                    
            elif isinstance(node, ast.Constant):
                return node.value
                
            elif isinstance(node, ast.Attribute):
                # Allow simple attribute access on item
                if isinstance(node.value, ast.Name) and node.value.id == 'item':
                    if isinstance(item, dict):
                        return item.get(node.attr)
                    else:
                        return getattr(item, node.attr, None)
                else:
                    raise ValueError("Only attribute access on 'item' is allowed")
                    
            elif isinstance(node, ast.Subscript):
                # Allow dictionary/list access on item
                if isinstance(node.value, ast.Name) and node.value.id == 'item':
                    item_val = item
                    if isinstance(node.slice, ast.Constant):
                        key = node.slice.value
                    elif isinstance(node.slice, ast.Name):
                        key = _eval(node.slice)
                    else:
                        raise ValueError("Only simple indexing is allowed")
                    
                    if isinstance(item_val, dict):
                        return item_val.get(key)
                    elif isinstance(item_val, (list, tuple)):
                        return item_val[key] if isinstance(key, int) else None
                    else:
                        return None
                else:
                    raise ValueError("Only subscript access on 'item' is allowed")
                    
            else:
                raise ValueError(f"Unsupported expression: {ast.dump(node)}")
        
        try:
            # Parse the expression
            tree = ast.parse(expression, mode='eval')
            return _eval(tree.body)
        except Exception as e:
            logger.error(f"Filter expression evaluation error: {e}")
            return False


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
        
        # Validate URL to prevent SSRF attacks
        self._validate_url(url)

        try:
            response = requests.request(
                method=method,
                url=url,
                json=input_data,
                headers=headers,
                timeout=node.timeout_seconds
            )
            response.raise_for_status()

            # Check if response is HTML (error page) instead of expected data
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                logger.warning(f"Webhook {url} returned HTML content instead of expected format. Status: {response.status_code}")
                return {
                    'sent': True,
                    'status_code': response.status_code,
                    'response': response.text[:500],  # Truncate HTML response
                    'warning': 'Received HTML response instead of expected format'
                }

            return {
                'sent': True,
                'status_code': response.status_code,
                'response': response.text[:1000]  # Truncate response
            }

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {e.response.status_code} error from webhook {url}"
            
            # Try to extract meaningful error message from response
            try:
                if e.response.headers.get('content-type', '').lower().startswith('application/json'):
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and 'error' in error_data:
                        error_msg += f": {error_data['error']}"
                    elif isinstance(error_data, dict) and 'message' in error_data:
                        error_msg += f": {error_data['message']}"
                    else:
                        error_msg += f": {str(error_data)}"
                else:
                    # For non-JSON responses, include first 200 chars of response
                    error_text = e.response.text[:200]
                    if error_text.startswith('<!DOCTYPE') or error_text.startswith('<html'):
                        error_msg += ": Received HTML error page (check webhook endpoint)"
                    else:
                        error_msg += f": {error_text}"
            except Exception:
                # If we can't parse the error response, just include basic info
                error_msg += f" (response parsing failed)"
            
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Webhook request to {url} failed: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _validate_url(self, url: str) -> None:
        """
        Validate URL to prevent SSRF attacks.
        
        Only allows HTTP/HTTPS to external services, blocking internal network access.
        """
        from urllib.parse import urlparse
        import ipaddress
        import socket
        
        try:
            parsed = urlparse(url)
            
            # Only allow HTTP and HTTPS schemes
            if parsed.scheme not in ('http', 'https'):
                raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are permitted.")
            
            # Resolve hostname to IP address
            if parsed.hostname:
                # Block localhost and private IP ranges
                try:
                    ip = socket.gethostbyname(parsed.hostname)
                    ip_obj = ipaddress.ip_address(ip)
                    
                    # Check if IP is private or localhost
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                        raise ValueError(f"Access to internal network address '{ip}' is not allowed")
                    
                    # Block common internal infrastructure IPs
                    blocked_ranges = [
                        ipaddress.ip_network('169.254.169.254/32'),  # AWS metadata
                        ipaddress.ip_network('metadata.google.internal/32'),  # GCP metadata
                    ]
                    
                    for blocked_range in blocked_ranges:
                        if ip_obj in blocked_range:
                            raise ValueError(f"Access to infrastructure address '{ip}' is not allowed")
                
                except socket.gaierror:
                    # If hostname can't be resolved, allow it (might be a DNS name)
                    pass
                
                # Block certain hostname patterns
                blocked_hostnames = [
                    'localhost',
                    'metadata.google.internal',
                    '169.254.169.254',
                ]
                
                if parsed.hostname.lower() in blocked_hostnames:
                    raise ValueError(f"Access to '{parsed.hostname}' is not allowed")
            
        except ValueError:
            # Re-raise our custom validation errors
            raise
        except Exception as e:
            # For any other parsing errors, block the request
            raise ValueError(f"Invalid URL format: {e}")


class DatabaseWriteExecutor(BaseNodeExecutor):
    """Write data to database."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from django.db import connection

        config = node.config
        query = config.get('query')
        data = input_data.get('data', input_data)

        if not query:
            raise ValueError("Query not configured")

        # Don't allow string formatting in SQL queries
        if '{' in query:
            raise ValueError("Direct string formatting in SQL queries is not allowed for security reasons")

        with connection.cursor() as cursor:
            if isinstance(data, list):
                # Batch insert with proper parameterization
                for item in data:
                    if isinstance(item, dict):
                        # For dict items, extract values in the order they appear in the query
                        # This is a simplified approach - in production, you'd want more robust handling
                        values = list(item.values())
                        cursor.execute(query, values)
                    else:
                        # For simple values, use as-is
                        cursor.execute(query, [item] if not isinstance(item, (list, tuple)) else item)
                return {'inserted': len(data)}
            else:
                if isinstance(data, dict):
                    # For dict items, extract values in the order they appear in the query
                    values = list(data.values())
                    cursor.execute(query, values)
                else:
                    # For simple values, use as-is
                    cursor.execute(query, [data] if not isinstance(data, (list, tuple)) else data)
                return {'affected_rows': cursor.rowcount}


# =============================================================================
# AGENT INTEGRATION EXECUTORS
# =============================================================================

class AgentTaskExecutor(BaseNodeExecutor):
    """Execute a task using an AI agent."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from apps.services.background.factory import get_background_processor

        config = node.config
        agent_id = config.get('agent_id')
        task_description = config.get('task_description', '')
        task_params = config.get('task_params', {})
        wait_for_completion = config.get('wait_for_completion', True)
        timeout_seconds = config.get('timeout_seconds', 300)

        if not agent_id:
            raise ValueError("Agent ID not configured")

        # Format task description with input data
        task_description = task_description.format(**input_data) if '{' in task_description else task_description

        # Merge task params with input data
        merged_params = {**task_params, **input_data}

        try:
            # Submit task to agent via background processor
            bg_processor = get_background_processor()
            task_handle = bg_processor.submit(
                'agent_execute_task',
                agent_id=agent_id,
                task_description=task_description,
                task_params=merged_params,
                workflow_execution_id=execution.id
            )

            if wait_for_completion:
                # Wait for agent to complete task
                result = bg_processor.result(task_handle, timeout=timeout_seconds)

                return {
                    'agent_id': agent_id,
                    'task_id': task_handle,
                    'status': 'completed',
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # Return task ID immediately
                return {
                    'agent_id': agent_id,
                    'task_id': task_handle,
                    'status': 'queued',
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Agent task execution failed: {e}")
            raise ValueError(f"Agent task execution failed: {str(e)}")


class AgentQueryExecutor(BaseNodeExecutor):
    """Query an AI agent for information or decisions."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from apps.services.background.factory import get_background_processor

        config = node.config
        agent_id = config.get('agent_id')
        query_text = config.get('query_text', '')
        query_context = config.get('query_context', {})
        expected_format = config.get('expected_format', 'text')  # text, json, structured
        timeout_seconds = config.get('timeout_seconds', 60)

        if not agent_id:
            raise ValueError("Agent ID not configured")

        # Format query with input data
        query_text = query_text.format(**input_data) if '{' in query_text else query_text

        # Merge context with input data
        merged_context = {**query_context, **input_data}

        try:
            # Submit query to agent
            bg_processor = get_background_processor()
            task_handle = bg_processor.submit(
                'agent_process_query',
                agent_id=agent_id,
                query=query_text,
                context=merged_context,
                expected_format=expected_format,
                workflow_execution_id=execution.id
            )

            # Wait for agent response
            response = bg_processor.result(task_handle, timeout=timeout_seconds)

            return {
                'agent_id': agent_id,
                'query': query_text,
                'response': response.get('answer'),
                'confidence': response.get('confidence', 1.0),
                'reasoning': response.get('reasoning'),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Agent query failed: {e}")
            raise ValueError(f"Agent query failed: {str(e)}")


class AgentMemoryExecutor(BaseNodeExecutor):
    """Store or retrieve information from agent's memory."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        config = node.config
        agent_id = config.get('agent_id')
        operation = config.get('operation', 'store')  # store, retrieve, search
        memory_type = config.get('memory_type', 'episodic')  # episodic, semantic, procedural, working
        content = config.get('content', {})

        if not agent_id:
            raise ValueError("Agent ID not configured")

        # Merge content with input data
        merged_content = {**content, **input_data}

        try:
            if operation == 'store':
                # Store information in agent memory
                return self._store_memory(agent_id, memory_type, merged_content, execution)
            elif operation == 'retrieve':
                # Retrieve specific memory
                return self._retrieve_memory(agent_id, memory_type, merged_content, execution)
            elif operation == 'search':
                # Search agent memory
                return self._search_memory(agent_id, memory_type, merged_content, execution)
            else:
                raise ValueError(f"Unknown memory operation: {operation}")

        except Exception as e:
            logger.error(f"Agent memory operation failed: {e}")
            raise ValueError(f"Agent memory operation failed: {str(e)}")

    def _store_memory(self, agent_id: str, memory_type: str, content: Dict[str, Any], execution) -> Dict[str, Any]:
        """Store information in agent memory."""
        from apps.services.background.factory import get_background_processor

        bg_processor = get_background_processor()
        task_handle = bg_processor.submit(
            'agent_store_memory',
            agent_id=agent_id,
            memory_type=memory_type,
            content=content,
            workflow_execution_id=execution.id
        )

        result = bg_processor.result(task_handle, timeout=30)

        return {
            'operation': 'store',
            'agent_id': agent_id,
            'memory_type': memory_type,
            'memory_id': result.get('memory_id'),
            'stored': True,
            'timestamp': datetime.now().isoformat()
        }

    def _retrieve_memory(self, agent_id: str, memory_type: str, criteria: Dict[str, Any], execution) -> Dict[str, Any]:
        """Retrieve information from agent memory."""
        from apps.services.background.factory import get_background_processor

        bg_processor = get_background_processor()
        task_handle = bg_processor.submit(
            'agent_retrieve_memory',
            agent_id=agent_id,
            memory_type=memory_type,
            criteria=criteria,
            workflow_execution_id=execution.id
        )

        result = bg_processor.result(task_handle, timeout=30)

        return {
            'operation': 'retrieve',
            'agent_id': agent_id,
            'memory_type': memory_type,
            'data': result.get('data'),
            'count': result.get('count', 0),
            'timestamp': datetime.now().isoformat()
        }

    def _search_memory(self, agent_id: str, memory_type: str, criteria: Dict[str, Any], execution) -> Dict[str, Any]:
        """Search agent memory."""
        from apps.services.background.factory import get_background_processor

        bg_processor = get_background_processor()
        task_handle = bg_processor.submit(
            'agent_search_memory',
            agent_id=agent_id,
            memory_type=memory_type,
            query=criteria.get('query', ''),
            filters=criteria.get('filters', {}),
            limit=criteria.get('limit', 10),
            workflow_execution_id=execution.id
        )

        result = bg_processor.result(task_handle, timeout=30)

        return {
            'operation': 'search',
            'agent_id': agent_id,
            'memory_type': memory_type,
            'results': result.get('results', []),
            'count': result.get('count', 0),
            'timestamp': datetime.now().isoformat()
        }


class AgentDecisionExecutor(BaseNodeExecutor):
    """Request a decision from an AI agent."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from apps.services.background.factory import get_background_processor

        config = node.config
        agent_id = config.get('agent_id')
        decision_context = config.get('decision_context', {})
        options = config.get('options', [])
        criteria = config.get('criteria', [])
        timeout_seconds = config.get('timeout_seconds', 120)

        if not agent_id:
            raise ValueError("Agent ID not configured")

        if not options:
            raise ValueError("Decision options not configured")

        # Merge context with input data
        merged_context = {**decision_context, **input_data}

        try:
            bg_processor = get_background_processor()
            task_handle = bg_processor.submit(
                'agent_make_decision',
                agent_id=agent_id,
                context=merged_context,
                options=options,
                criteria=criteria,
                workflow_execution_id=execution.id
            )

            result = bg_processor.result(task_handle, timeout=timeout_seconds)

            return {
                'agent_id': agent_id,
                'decision': result.get('selected_option'),
                'confidence': result.get('confidence'),
                'reasoning': result.get('reasoning'),
                'analysis': result.get('analysis'),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Agent decision failed: {e}")
            raise ValueError(f"Agent decision failed: {str(e)}")


class AgentLearningExecutor(BaseNodeExecutor):
    """Provide learning feedback to an AI agent."""

    def execute(self, node, input_data: Dict[str, Any], execution) -> Dict[str, Any]:
        from apps.services.background.factory import get_background_processor

        config = node.config
        agent_id = config.get('agent_id')
        feedback_type = config.get('feedback_type', 'outcome')  # outcome, correction, reinforcement
        feedback_data = config.get('feedback_data', {})

        if not agent_id:
            raise ValueError("Agent ID not configured")

        # Merge feedback data with input data
        merged_feedback = {**feedback_data, **input_data}

        try:
            bg_processor = get_background_processor()
            task_handle = bg_processor.submit(
                'agent_process_learning',
                agent_id=agent_id,
                feedback_type=feedback_type,
                feedback_data=merged_feedback,
                workflow_execution_id=execution.id
            )

            result = bg_processor.result(task_handle, timeout=30)

            return {
                'agent_id': agent_id,
                'feedback_type': feedback_type,
                'processed': True,
                'learning_impact': result.get('learning_impact'),
                'adjustments_made': result.get('adjustments_made'),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Agent learning failed: {e}")
            raise ValueError(f"Agent learning failed: {str(e)}")


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

            # Control Flow
            'condition': PassthroughExecutor(),
            'CONTROL_CONDITION': PassthroughExecutor(),
            'error_handler': PassthroughExecutor(),
            'CONTROL_ERROR_HANDLER': PassthroughExecutor(),
            'delay': PassthroughExecutor(),
            'CONTROL_DELAY': PassthroughExecutor(),
            'loop': PassthroughExecutor(),
            'CONTROL_LOOP': PassthroughExecutor(),

            # Outputs
            'email': EmailOutputExecutor(),
            'OUTPUT_EMAIL': EmailOutputExecutor(),
            'webhook_output': WebhookOutputExecutor(),
            'OUTPUT_WEBHOOK': WebhookOutputExecutor(),
            'database_output': DatabaseWriteExecutor(),
            'OUTPUT_DATABASE': DatabaseWriteExecutor(),

            # Agent Integration
            'agent_task': AgentTaskExecutor(),
            'AGENT_TASK': AgentTaskExecutor(),
            'agent_query': AgentQueryExecutor(),
            'AGENT_QUERY': AgentQueryExecutor(),
            'agent_memory': AgentMemoryExecutor(),
            'AGENT_MEMORY': AgentMemoryExecutor(),
            'agent_decision': AgentDecisionExecutor(),
            'AGENT_DECISION': AgentDecisionExecutor(),
            'agent_learning': AgentLearningExecutor(),
            'AGENT_LEARNING': AgentLearningExecutor(),
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
