"""
WebOps-specific actions for AI Agent

Provides authenticated actions that allow the AI agent to interact with
the WebOps control panel and CLI systems.
"""

import asyncio
import json
import logging
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
import subprocess
import os

from .action_library import (
    BaseAction, ActionDefinition, ActionParameter, ActionType, 
    AuthenticationMethod
)


class WebOpsAPIAction(BaseAction):
    """Base class for WebOps API actions."""
    
    def __init__(self, definition: ActionDefinition, api_base_url: str = None):
        super().__init__(definition)
        self.api_base_url = api_base_url or os.getenv('WEBOPS_API_URL', 'http://localhost:8000')
        self.session = None
    
    async def _init_session(self, auth_context: Dict[str, Any]) -> aiohttp.ClientSession:
        """Initialize HTTP session with authentication."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'WebOps-AI-Agent/1.0'
        }
        
        # Add authentication headers
        auth_method = self.definition.authentication_method
        
        if auth_method == AuthenticationMethod.BEARER_TOKEN:
            token = auth_context.get('bearer_token')
            if token:
                headers['Authorization'] = f'Bearer {token}'
        
        elif auth_method == AuthenticationMethod.API_KEY:
            api_key = auth_context.get('api_key')
            if api_key:
                headers['X-API-Key'] = api_key
        
        elif auth_method == AuthenticationMethod.BASIC_AUTH:
            username = auth_context.get('username')
            password = auth_context.get('password')
            if username and password:
                import base64
                credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
        
        # Create session
        timeout = aiohttp.ClientTimeout(total=self.definition.timeout_seconds)
        self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session
    
    async def _close_session(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to WebOps API."""
        if not self.session:
            raise ValueError("Session not initialized")
        
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, json=data) as response:
                response_data = await response.json()
                
                if response.status == 200:
                    return {
                        'success': True,
                        'data': response_data,
                        'status_code': response.status
                    }
                else:
                    return {
                        'success': False,
                        'error': response_data.get('error', f'HTTP {response.status}'),
                        'status_code': response.status,
                        'data': response_data
                    }
        
        except aiohttp.ClientError as e:
            return {
                'success': False,
                'error': f'Connection error: {str(e)}',
                'status_code': 0
            }
    
    async def authenticate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with WebOps API."""
        auth_info = await super().authenticate(context)
        
        # Initialize session for authenticated requests
        if auth_info['authenticated']:
            await self._init_session(context)
        
        return auth_info


class DeployApplicationAction(WebOpsAPIAction):
    """Deploy a new application using WebOps."""
    
    def __init__(self):
        definition = ActionDefinition(
            name="deploy_application",
            description="Deploy a new application to WebOps",
            action_type=ActionType.DEPLOYMENT,
            category="deployment",
            parameters=[
                ActionParameter("app_name", "string", "Name of the application", True),
                ActionParameter("repository", "string", "Git repository URL", True),
                ActionParameter("branch", "string", "Git branch to deploy", False, "main"),
                ActionParameter("environment", "string", "Target environment", False, "production"),
                ActionParameter("python_version", "string", "Python version", False, "3.11"),
                ActionParameter("database_type", "string", "Database type", False, "postgresql"),
                ActionParameter("memory_limit", "string", "Memory limit", False, "512M"),
                ActionParameter("cpu_limit", "string", "CPU limit", False, "1"),
                ActionParameter("auto_scale", "boolean", "Enable auto-scaling", False, False),
                ActionParameter("health_check", "boolean", "Enable health checks", False, True),
                ActionParameter("ssl_enabled", "boolean", "Enable SSL", False, True),
                ActionParameter("notifications_enabled", "boolean", "Enable notifications", False, True),
                ActionParameter("custom_env", "dict", "Custom environment variables", False, {}),
                ActionParameter("requirements", "list", "Python requirements", False, [])
            ],
            authentication_method=AuthenticationMethod.BEARER_TOKEN,
            required_permissions=["deploy:create"],
            timeout_seconds=300,
            cost=10.0,
            tags=["deployment", "application", "git", "production"],
            examples=[
                {
                    "description": "Deploy a Django application",
                    "parameters": {
                        "app_name": "my-django-app",
                        "repository": "https://github.com/user/django-app.git",
                        "branch": "main",
                        "environment": "production",
                        "python_version": "3.11",
                        "database_type": "postgresql"
                    }
                }
            ]
        )
        super().__init__(definition)
    
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the deployment action."""
        try:
            # Prepare deployment payload
            deployment_data = {
                "name": params["app_name"],
                "repository": {
                    "url": params["repository"],
                    "branch": params["branch"]
                },
                "environment": params["environment"],
                "runtime": {
                    "type": "python",
                    "version": params["python_version"]
                },
                "database": {
                    "type": params["database_type"]
                },
                "resources": {
                    "memory_limit": params["memory_limit"],
                    "cpu_limit": params["cpu_limit"],
                    "auto_scale": params["auto_scale"]
                },
                "features": {
                    "health_check": params["health_check"],
                    "ssl_enabled": params["ssl_enabled"],
                    "notifications_enabled": params["notifications_enabled"]
                },
                "configuration": {
                    "custom_env": params["custom_env"],
                    "requirements": params["requirements"]
                }
            }
            
            # Make API request
            response = await self._make_request("POST", "/api/deployments/", deployment_data)
            
            if response["success"]:
                deployment_id = response["data"]["id"]
                
                # Start deployment process
                await self._make_request("POST", f"/api/deployments/{deployment_id}/start/")
                
                return {
                    'success': True,
                    'deployment_id': deployment_id,
                    'status': 'deployment_started',
                    'message': f'Deployment started for {params["app_name"]}',
                    'data': response["data"]
                }
            else:
                return {
                    'success': False,
                    'error': response["error"],
                    'message': f'Failed to start deployment: {response["error"]}'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Error during deployment: {str(e)}'
            }
        finally:
            await self._close_session()


class GetDeploymentStatusAction(WebOpsAPIAction):
    """Get deployment status from WebOps."""
    
    def __init__(self):
        definition = ActionDefinition(
            name="get_deployment_status",
            description="Get status of a deployed application",
            action_type=ActionType.DEPLOYMENT,
            category="monitoring",
            parameters=[
                ActionParameter("deployment_id", "string", "Deployment ID", True),
                ActionParameter("include_logs", "boolean", "Include deployment logs", False, False),
