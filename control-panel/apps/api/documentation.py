"""
API Documentation Generator for WebOps.

Auto-discovers API endpoints and generates live, interactive examples.
Reference: CLAUDE.md "API Design" section
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from django.urls import get_resolver, URLPattern, URLResolver
from django.conf import settings
import inspect


@dataclass
class APIExample:
    """Example request/response for an API endpoint."""
    description: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    status_code: int = 200


@dataclass
class APIEndpoint:
    """Represents a single API endpoint."""
    path: str
    method: str
    name: str
    description: str
    authentication_required: bool
    parameters: List[Dict[str, Any]]
    request_body: Optional[Dict[str, Any]]
    response: Dict[str, Any]
    examples: List[APIExample]
    error_responses: List[Dict[str, Any]]


class APIDocumentationGenerator:
    """Auto-generates API documentation from Django URL patterns."""

    def __init__(self):
        self.endpoints: List[APIEndpoint] = []
        self._discover_endpoints()

    def _discover_endpoints(self) -> None:
        """Discover all API endpoints from URL patterns."""
        resolver = get_resolver()
        self._parse_url_patterns(resolver.url_patterns, prefix='/api')

    def _parse_url_patterns(
        self,
        patterns: List,
        prefix: str = ''
    ) -> None:
        """Recursively parse URL patterns."""
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                # Nested URL patterns
                new_prefix = prefix + str(pattern.pattern)
                self._parse_url_patterns(pattern.url_patterns, new_prefix)
            elif isinstance(pattern, URLPattern):
                # Extract endpoint info
                path = prefix + str(pattern.pattern)

                # Only include API endpoints
                if not path.startswith('/api/') or path == '/api/docs/':
                    continue

                callback = pattern.callback
                if callback:
                    self._extract_endpoint_info(path, pattern.name, callback)

    def _extract_endpoint_info(
        self,
        path: str,
        name: str,
        callback: Any
    ) -> None:
        """Extract information from view function/class."""
        # Get view function
        view_func = callback
        if hasattr(callback, 'view_class'):
            view_func = callback.view_class

        # Get docstring
        doc = inspect.getdoc(view_func) or "No description available"

        # Detect HTTP methods
        methods = self._get_http_methods(view_func)

        # Check authentication requirement
        auth_required = self._requires_authentication(view_func)

        # Extract parameters from path
        parameters = self._extract_path_parameters(path)

        # Generate examples based on endpoint type
        examples = self._generate_examples(path, name, methods)

        # Create endpoint for each method
        for method in methods:
            endpoint = APIEndpoint(
                path=path,
                method=method,
                name=name or path,
                description=doc,
                authentication_required=auth_required,
                parameters=parameters,
                request_body=self._get_request_body_schema(name, method),
                response=self._get_response_schema(name, method),
                examples=examples.get(method, []),
                error_responses=self._get_error_responses(auth_required)
            )
            self.endpoints.append(endpoint)

    def _get_http_methods(self, view_func: Any) -> List[str]:
        """Extract HTTP methods from view decorators."""
        # Check for @require_http_methods decorator
        if hasattr(view_func, '_allowed_methods'):
            return list(view_func._allowed_methods)

        # Default methods based on common patterns
        func_name = getattr(view_func, '__name__', '')
        if 'list' in func_name or 'detail' in func_name or 'logs' in func_name:
            return ['GET']
        elif 'create' in func_name:
            return ['POST']
        elif 'update' in func_name:
            return ['PUT', 'PATCH']
        elif 'delete' in func_name:
            return ['DELETE']
        elif 'start' in func_name or 'stop' in func_name or 'restart' in func_name:
            return ['POST']

        return ['GET', 'POST']

    def _requires_authentication(self, view_func: Any) -> bool:
        """Check if endpoint requires authentication."""
        # Check for authentication decorators
        func_str = str(view_func)
        if 'api_authentication_required' in func_str:
            return True
        if 'login_required' in func_str:
            return True
        return False

    def _extract_path_parameters(self, path: str) -> List[Dict[str, Any]]:
        """Extract parameters from URL path."""
        import re
        parameters = []

        # Find path parameters like <int:id> or <str:name>
        param_pattern = r'<(\w+):(\w+)>'
        matches = re.finditer(param_pattern, path)

        for match in matches:
            param_type, param_name = match.groups()
            parameters.append({
                'name': param_name,
                'type': param_type,
                'in': 'path',
                'required': True,
                'description': f'{param_name} identifier'
            })

        return parameters

    def _get_request_body_schema(
        self,
        endpoint_name: str,
        method: str
    ) -> Optional[Dict[str, Any]]:
        """Generate request body schema for POST/PUT/PATCH."""
        if method not in ['POST', 'PUT', 'PATCH']:
            return None

        if 'deployment_create' in endpoint_name:
            return {
                'name': {'type': 'string', 'required': True, 'description': 'Deployment name (lowercase, alphanumeric, hyphens)'},
                'repo_url': {'type': 'string', 'required': True, 'description': 'GitHub repository URL (HTTPS)'},
                'branch': {'type': 'string', 'required': False, 'default': 'main', 'description': 'Git branch to deploy'},
                'domain': {'type': 'string', 'required': False, 'description': 'Custom domain (optional)'},
                'env_vars': {'type': 'object', 'required': False, 'description': 'Environment variables as key-value pairs'}
            }
        elif 'file_write' in endpoint_name:
            return {
                'path': {'type': 'string', 'required': True, 'description': 'Relative file path'},
                'content': {'type': 'string', 'required': True, 'description': 'File content'}
            }

        return {}

    def _get_response_schema(
        self,
        endpoint_name: str,
        method: str
    ) -> Dict[str, Any]:
        """Generate response schema."""
        if 'list' in endpoint_name:
            return {
                'deployments' if 'deployment' in endpoint_name else 'databases': {
                    'type': 'array',
                    'description': 'List of items'
                },
                'pagination': {
                    'type': 'object',
                    'description': 'Pagination metadata'
                }
            }
        elif 'detail' in endpoint_name:
            return {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'status': {'type': 'string'},
                'created_at': {'type': 'string', 'format': 'iso8601'}
            }
        elif 'logs' in endpoint_name:
            return {
                'logs': {
                    'type': 'array',
                    'description': 'Log entries'
                }
            }

        return {'success': {'type': 'boolean'}, 'message': {'type': 'string'}}

    def _generate_examples(
        self,
        path: str,
        name: str,
        methods: List[str]
    ) -> Dict[str, List[APIExample]]:
        """Generate live examples for endpoint."""
        examples = {}

        # Deployment List Example
        if 'deployment_list' in name:
            examples['GET'] = [APIExample(
                description="List all deployments with pagination",
                request={
                    'method': 'GET',
                    'url': '/api/deployments/?page=1&per_page=20',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN'
                    }
                },
                response={
                    'deployments': [
                        {
                            'id': 1,
                            'name': 'my-django-app',
                            'repo_url': 'https://github.com/user/repo',
                            'branch': 'main',
                            'status': 'running',
                            'project_type': 'django',
                            'port': 8001,
                            'domain': 'app.example.com',
                            'created_at': '2025-01-15T10:30:00Z',
                            'updated_at': '2025-01-15T10:35:00Z'
                        }
                    ],
                    'pagination': {
                        'page': 1,
                        'per_page': 20,
                        'total': 1,
                        'pages': 1
                    }
                },
                status_code=200
            )]

        # Deployment Create Example
        elif 'deployment_create' in name:
            examples['POST'] = [APIExample(
                description="Create new deployment from GitHub repository",
                request={
                    'method': 'POST',
                    'url': '/api/deployments/create/',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN',
                        'Content-Type': 'application/json'
                    },
                    'body': {
                        'name': 'my-django-app',
                        'repo_url': 'https://github.com/user/django-app',
                        'branch': 'main',
                        'domain': 'app.example.com',
                        'env_vars': {
                            'DEBUG': 'False',
                            'ALLOWED_HOSTS': 'app.example.com'
                        }
                    }
                },
                response={
                    'id': 1,
                    'name': 'my-django-app',
                    'status': 'pending',
                    'message': 'Deployment queued successfully'
                },
                status_code=201
            )]

        # Deployment Detail Example
        elif 'deployment_detail' in name:
            examples['GET'] = [APIExample(
                description="Get deployment details by name",
                request={
                    'method': 'GET',
                    'url': '/api/deployments/my-django-app/',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN'
                    }
                },
                response={
                    'id': 1,
                    'name': 'my-django-app',
                    'repo_url': 'https://github.com/user/repo',
                    'branch': 'main',
                    'status': 'running',
                    'project_type': 'django',
                    'port': 8001,
                    'domain': 'app.example.com',
                    'env_vars': {'DEBUG': 'False'},
                    'created_at': '2025-01-15T10:30:00Z',
                    'updated_at': '2025-01-15T10:35:00Z'
                },
                status_code=200
            )]

        # Deployment Actions (start/stop/restart)
        elif any(action in name for action in ['start', 'stop', 'restart']):
            action = 'start' if 'start' in name else 'stop' if 'stop' in name else 'restart'
            examples['POST'] = [APIExample(
                description=f"{action.capitalize()} deployment service",
                request={
                    'method': 'POST',
                    'url': f'/api/deployments/my-django-app/{action}/',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN'
                    }
                },
                response={
                    'success': True,
                    'message': f'Service {action}ed successfully'
                },
                status_code=200
            )]

        # Database List Example
        elif 'database_list' in name:
            examples['GET'] = [APIExample(
                description="List all databases",
                request={
                    'method': 'GET',
                    'url': '/api/databases/',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN'
                    }
                },
                response={
                    'databases': [
                        {
                            'id': 1,
                            'name': 'myapp_db',
                            'username': 'myapp_user',
                            'host': 'localhost',
                            'port': 5432,
                            'deployment': 'my-django-app',
                            'created_at': '2025-01-15T10:30:00Z'
                        }
                    ]
                },
                status_code=200
            )]

        # Logs Example
        elif 'logs' in name:
            examples['GET'] = [APIExample(
                description="Get deployment logs",
                request={
                    'method': 'GET',
                    'url': '/api/deployments/my-django-app/logs/?tail=100',
                    'headers': {
                        'Authorization': 'Bearer YOUR_API_TOKEN'
                    }
                },
                response={
                    'logs': [
                        {
                            'level': 'info',
                            'message': 'Starting deployment...',
                            'created_at': '2025-01-15T10:30:00Z'
                        },
                        {
                            'level': 'info',
                            'message': 'Cloning repository...',
                            'created_at': '2025-01-15T10:30:05Z'
                        }
                    ]
                },
                status_code=200
            )]

        return examples

    def _get_error_responses(
        self,
        auth_required: bool
    ) -> List[Dict[str, Any]]:
        """Get common error responses."""
        errors = [
            {
                'status': 400,
                'title': 'Bad Request',
                'description': 'Invalid request data',
                'example': {'error': 'Missing required fields', 'message': 'name and repo_url are required'}
            },
            {
                'status': 500,
                'title': 'Internal Server Error',
                'description': 'Server error occurred',
                'example': {'error': 'Internal server error', 'message': 'An unexpected error occurred'}
            }
        ]

        if auth_required:
            errors.insert(0, {
                'status': 401,
                'title': 'Unauthorized',
                'description': 'Authentication required',
                'example': {'error': 'Authentication required', 'message': 'Invalid or missing API token'}
            })
            errors.insert(1, {
                'status': 404,
                'title': 'Not Found',
                'description': 'Resource not found',
                'example': {'error': 'Not found', 'message': 'Deployment not found'}
            })

        return errors

    def get_endpoints_by_group(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group endpoints by resource type."""
        groups = {
            'Deployments': [],
            'Databases': [],
            'Files': [],
            'System': []
        }

        for endpoint in self.endpoints:
            endpoint_dict = {
                'path': endpoint.path,
                'method': endpoint.method,
                'name': endpoint.name,
                'description': endpoint.description,
                'authentication_required': endpoint.authentication_required,
                'parameters': endpoint.parameters,
                'request_body': endpoint.request_body,
                'response': endpoint.response,
                'examples': [asdict(ex) for ex in endpoint.examples],
                'error_responses': endpoint.error_responses
            }

            if '/deployments/' in endpoint.path:
                if '/files/' in endpoint.path:
                    groups['Files'].append(endpoint_dict)
                else:
                    groups['Deployments'].append(endpoint_dict)
            elif '/databases/' in endpoint.path:
                groups['Databases'].append(endpoint_dict)
            else:
                groups['System'].append(endpoint_dict)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'version': '0.3.0',
            'base_url': f'{settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else "localhost"}',
            'authentication': {
                'type': 'Bearer Token',
                'description': 'Include API token in Authorization header',
                'header': 'Authorization: Bearer YOUR_API_TOKEN'
            },
            'endpoints': self.get_endpoints_by_group()
        }
