"""
MCP (Model Context Protocol) Server for WebOps

This MCP server wraps all WebOps services and makes them available
through the standardized MCP protocol for AI agents and clients.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid
import subprocess
import os
import aiohttp
from dataclasses import dataclass, field

# MCP protocol imports
try:
    from mcp import ClientSession, ServerSession, NotificationOptions
    from mcp.server import Server
    from mcp.server.models import Tool, Resource, Prompt
    from mcp.types import ToolCall
except ImportError:
    # Fallback if MCP is not installed
    ClientSession = None
    ServerSession = None
    NotificationOptions = None
    Tool = None
    Resource = None
    Prompt = None
    ToolCall = None


# Import our action library and WebOps actions
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from actions.action_library import WebOpsActionLibrary
from actions.webops_actions import DeployApplicationAction, GetDeploymentStatusAction
from llm.tool_selector import LLMToolSelector


@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool."""
    
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    category: str = "general"
    examples: List[Dict[str, Any]] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


class WebOpsMCPServer:
    """MCP Server that wraps WebOps services."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the MCP server."""
        self.config = config
        self.logger = logging.getLogger("webops_mcp_server")
        
        # Initialize WebOps components
        self.action_library = WebOpsActionLibrary()
        self.tool_selector = LLMToolSelector(config.get('llm_config', {}))
        
        # MCP server setup
        self.server = None
        self.tools: Dict[str, MCPToolDefinition] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, Any]] = {}
        
        # Setup components
        self._setup_webops_actions()
        self._setup_mcp_tools()
        self.tool_selector.set_action_library(self.action_library)
        
        # Authentication context
        self.auth_contexts: Dict[str, Dict[str, Any]] = {}
    
    def _setup_webops_actions(self):
        """Setup WebOps actions in the action library."""
        # Register WebOps actions
        deploy_action = DeployApplicationAction()
        status_action = GetDeploymentStatusAction()
        
        self.action_library.register_action(deploy_action)
        self.action_library.register_action(status_action)
        
        # Add more actions as needed
        self.logger.info(f"Initialized action library with {len(self.action_library._actions)} actions")
    
    def _setup_mcp_tools(self):
        """Setup MCP tools based on available actions."""
        
        # Deploy Application Tool
        self.tools["webops_deploy_app"] = MCPToolDefinition(
            name="webops_deploy_app",
            description="Deploy a new application to WebOps hosting platform",
            input_schema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to deploy"
                    },
                    "repository": {
                        "type": "string",
                        "description": "Git repository URL (https://github.com/user/repo.git)"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Git branch to deploy from",
                        "default": "main"
                    },
                    "environment": {
                        "type": "string",
                        "description": "Target environment",
                        "enum": ["development", "staging", "production"],
                        "default": "production"
                    },
                    "python_version": {
                        "type": "string",
                        "description": "Python version to use",
                        "enum": ["3.9", "3.10", "3.11", "3.12"],
                        "default": "3.11"
                    },
                    "database_type": {
                        "type": "string",
                        "description": "Database type",
                        "enum": ["postgresql", "mysql", "sqlite"],
                        "default": "postgresql"
                    },
                    "memory_limit": {
                        "type": "string",
                        "description": "Memory limit (e.g., '512M', '1G')",
                        "default": "512M"
                    },
                    "ssl_enabled": {
                        "type": "boolean",
                        "description": "Enable SSL certificate",
                        "default": True
                    }
                },
                "required": ["app_name", "repository"]
            },
            handler=self._handle_deploy_app,
            category="deployment",
            examples=[
                {
                    "name": "Deploy Django App",
                    "description": "Deploy a Django application",
                    "arguments": {
                        "app_name": "my-django-app",
                        "repository": "https://github.com/user/django-app.git",
                        "branch": "main",
                        "environment": "production"
                    }
                }
            ],
            permissions=["deploy:create"]
        )
        
        # Get Deployment Status Tool
        self.tools["webops_get_status"] = MCPToolDefinition(
            name="webops_get_status",
            description="Get the status of WebOps deployments",
            input_schema={
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Specific deployment ID to check"
                    },
                    "include_logs": {
                        "type": "boolean",
                        "description": "Include deployment logs in response",
                        "default": False
                    },
                    "include_metrics": {
                        "type": "boolean",
                        "description": "Include performance metrics",
                        "default": False
                    }
                },
                "required": []
            },
            handler=self._handle_get_status,
            category="monitoring",
            examples=[
                {
                    "name": "Check All Deployments",
                    "description": "Get status of all active deployments",
                    "arguments": {}
                },
                {
                    "name": "Check Specific Deployment",
                    "description": "Get detailed status of one deployment",
                    "arguments": {
                        "deployment_id": "abc123",
                        "include_logs": True
                    }
                }
            ],
            permissions=["deploy:read"]
        )
        
        # List Deployments Tool
        self.tools["webops_list_deployments"] = MCPToolDefinition(
            name="webops_list_deployments",
            description="List all WebOps deployments",
            input_schema={
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "Filter by environment",
                        "enum": ["development", "staging", "production"]
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by deployment status",
                        "enum": ["running", "stopped", "error", "pending"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of deployments to return",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200
                    }
                },
                "required": []
            },
            handler=self._handle_list_deployments,
            category="monitoring",
            examples=[
                {
                    "name": "List All Production",
                    "description": "List all production deployments",
                    "arguments": {
                        "environment": "production",
                        "limit": 20
                    }
                }
            ],
            permissions=["deploy:read"]
        )
        
        # Start/Stop Service Tool
        self.tools["webops_manage_service"] = MCPToolDefinition(
            name="webops_manage_service",
            description="Start, stop, restart, or scale a WebOps service",
            input_schema={
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Deployment ID to manage"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform",
                        "enum": ["start", "stop", "restart", "scale_up", "scale_down"]
                    },
                    "instances": {
                        "type": "integer",
                        "description": "Number of instances (for scaling)",
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["deployment_id", "action"]
            },
            handler=self._handle_manage_service,
            category="management",
            examples=[
                {
                    "name": "Restart Service",
                    "description": "Restart a deployment",
                    "arguments": {
                        "deployment_id": "abc123",
                        "action": "restart"
                    }
                },
                {
                    "name": "Scale Service",
                    "description": "Scale up a deployment",
                    "arguments": {
                        "deployment_id": "abc123",
                        "action": "scale_up",
                        "instances": 3
                    }
                }
            ],
            permissions=["deploy:manage"]
        )
        
        # Get Logs Tool
        self.tools["webops_get_logs"] = MCPToolDefinition(
            name="webops_get_logs",
            description="Retrieve logs from WebOps deployments",
            input_schema={
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Deployment ID to get logs for"
                    },
                    "log_type": {
                        "type": "string",
                        "description": "Type of logs to retrieve",
                        "enum": ["application", "access", "error", "deployment"],
                        "default": "application"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to retrieve",
                        "default": 100,
                        "minimum": 10,
                        "maximum": 1000
                    },
                    "since": {
                        "type": "string",
                        "description": "Get logs since timestamp (ISO format)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}"
                    }
                },
                "required": ["deployment_id"]
            },
            handler=self._handle_get_logs,
            category="monitoring",
            examples=[
                {
                    "name": "Get Application Logs",
                    "description": "Get recent application logs",
                    "arguments": {
                        "deployment_id": "abc123",
                        "log_type": "application",
                        "lines": 50
                    }
                }
            ],
            permissions=["deploy:read"]
        )
        
        # Security Audit Tool
        self.tools["webops_security_audit"] = MCPToolDefinition(
            name="webops_security_audit",
            description="Run security audit on WebOps deployments",
            input_schema={
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Specific deployment to audit"
                    },
                    "audit_type": {
                        "type": "string",
                        "description": "Type of security audit",
                        "enum": ["basic", "comprehensive", "compliance"],
                        "default": "basic"
                    },
                    "include_recommendations": {
                        "type": "boolean",
                        "description": "Include security recommendations",
                        "default": True
                    }
                },
                "required": []
            },
            handler=self._handle_security_audit,
            category="security",
            examples=[
                {
                    "name": "Basic Security Audit",
                    "description": "Run basic security check",
                    "arguments": {}
                },
                {
                    "name": "Comprehensive Audit",
                    "description": "Run comprehensive security audit",
                    "arguments": {
                        "audit_type": "comprehensive",
                        "include_recommendations": True
                    }
                }
            ],
            permissions=["security:audit"]
        )
        
        # System Health Tool
        self.tools["webops_system_health"] = MCPToolDefinition(
            name="webops_system_health",
            description="Check WebOps system health and metrics",
            input_schema={
                "type": "object",
                "properties": {
                    "include_deployments": {
                        "type": "boolean",
                        "description": "Include deployment health data",
                        "default": True
                    },
                    "include_resources": {
                        "type": "boolean",
                        "description": "Include resource usage data",
                        "default": True
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range for metrics",
                        "enum": ["1h", "6h", "24h", "7d"],
                        "default": "1h"
                    }
                },
                "required": []
            },
            handler=self._handle_system_health,
            category="monitoring",
            examples=[
                {
                    "name": "Quick Health Check",
                    "description": "Get basic system health",
                    "arguments": {}
                },
                {
                    "name": "Detailed Health Report",
                    "description": "Get detailed health metrics",
                    "arguments": {
                        "include_deployments": True,
                        "include_resources": True,
                        "time_range": "24h"
                    }
                }
            ],
            permissions=["system:read"]
        )
        
        self.logger.info(f"Created {len(self.tools)} MCP tools")
    
    async def _handle_deploy_app(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle deploy application tool call."""
        try:
            # Execute the deploy action
            result = await self.action_library.execute_action(
                action_id="deploy_application",
                params=params,
                context=auth_context
            )
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"✅ Deployment started for '{params['app_name']}'\n\nDeployment ID: {result.get('deployment_id', 'N/A')}\nStatus: {result.get('status', 'Unknown')}\n\n{result.get('message', '')}"
                    }
                ],
                "is_error": not result.get('success', False)
            }
        
        except Exception as e:
            self.logger.error(f"Error deploying app: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Deployment failed: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_get_status(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle get status tool call."""
        try:
            # Execute the status action
            result = await self.action_library.execute_action(
                action_id="get_deployment_status",
                params=params,
                context=auth_context
            )
            
            if result.get('success', False):
                data = result.get('data', {})
                
                # Format status response
                status_text = f"📊 Deployment Status\n\n"
                
                if params.get('deployment_id'):
                    # Specific deployment
                    status_text += f"Deployment: {data.get('name', 'Unknown')}\n"
                    status_text += f"Status: {data.get('status', 'Unknown')}\n"
                    status_text += f"Environment: {data.get('environment', 'Unknown')}\n"
                    status_text += f"URL: {data.get('url', 'N/A')}\n"
                    status_text += f"Last Updated: {data.get('updated_at', 'Unknown')}\n"
                else:
                    # Multiple deployments
                    deployments = data.get('deployments', [])
                    status_text += f"Found {len(deployments)} deployments:\n\n"
                    for deployment in deployments:
                        status_text += f"• {deployment.get('name', 'Unknown')} ({deployment.get('status', 'Unknown')})\n"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": status_text
                        }
                    ],
                    "is_error": False
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Failed to get status: {result.get('error', 'Unknown error')}"
                        }
                    ],
                    "is_error": True
                }
        
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error getting status: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_list_deployments(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle list deployments tool call."""
        try:
            # Simulate listing deployments (would call actual WebOps API)
            deployments = [
                {
                    "id": "abc123",
                    "name": "user-api",
                    "status": "running",
                    "environment": "production",
                    "url": "https://user-api.example.com",
                    "updated_at": "2024-01-15T10:30:00Z"
                },
                {
                    "id": "def456",
                    "name": "payment-service",
                    "status": "running",
                    "environment": "production",
                    "url": "https://payment.example.com",
                    "updated_at": "2024-01-15T09:45:00Z"
                }
            ]
            
            # Filter deployments based on parameters
            if params.get('environment'):
                deployments = [d for d in deployments if d['environment'] == params['environment']]
            
            if params.get('status'):
                deployments = [d for d in deployments if d['status'] == params['status']]
            
            limit = params.get('limit', 50)
            deployments = deployments[:limit]
            
            # Format response
            if deployments:
                response_text = f"📋 WebOps Deployments ({len(deployments)} found)\n\n"
                for deployment in deployments:
                    status_emoji = "✅" if deployment['status'] == 'running' else "⚠️"
                    response_text += f"{status_emoji} {deployment['name']} ({deployment['environment']})\n"
                    response_text += f"   ID: {deployment['id']}\n"
                    response_text += f"   Status: {deployment['status']}\n"
                    response_text += f"   URL: {deployment['url']}\n\n"
            else:
                response_text = "📋 No deployments found matching the criteria."
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "is_error": False
            }
        
        except Exception as e:
            self.logger.error(f"Error listing deployments: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error listing deployments: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_manage_service(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle manage service tool call."""
        try:
            deployment_id = params['deployment_id']
            action = params['action']
            
            # Simulate service management
            actions = {
                "start": "starting",
                "stop": "stopping",
                "restart": "restarting",
                "scale_up": "scaling up",
                "scale_down": "scaling down"
            }
            
            status = actions.get(action, action)
            instances = params.get('instances', 1)
            
            response_text = f"🔄 {status.title()} deployment '{deployment_id}'\n\n"
            
            if action in ["scale_up", "scale_down"]:
                response_text += f"Target instances: {instances}\n"
            
            response_text += f"Action: {action}\n"
            response_text += f"Status: Initiated\n"
            response_text += f"Timestamp: {datetime.now().isoformat()}\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "is_error": False
            }
        
        except Exception as e:
            self.logger.error(f"Error managing service: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error managing service: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_get_logs(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle get logs tool call."""
        try:
            deployment_id = params['deployment_id']
            log_type = params.get('log_type', 'application')
            lines = params.get('lines', 100)
            
            # Simulate log retrieval
            mock_logs = [
                "2024-01-15T10:30:15Z INFO Application started successfully",
                "2024-01-15T10:30:16Z INFO Database connection established",
                "2024-01-15T10:30:17Z INFO Ready to accept requests",
                "2024-01-15T10:30:25Z INFO Request: GET /health - 200 OK",
                "2024-01-15T10:30:30Z INFO Request: POST /api/users - 201 Created"
            ]
            
            logs = mock_logs[:lines]
            
            response_text = f"📜 Logs for deployment '{deployment_id}' ({log_type})\n\n"
            response_text += f"Showing last {len(logs)} lines:\n\n"
            
            for log in logs:
                response_text += f"{log}\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "is_error": False
            }
        
        except Exception as e:
            self.logger.error(f"Error getting logs: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ Error retrieving logs"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_security_audit(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle security audit tool call."""
        try:
            audit_type = params.get('audit_type', 'basic')
            include_recommendations = params.get('include_recommendations', True)
            
            # Simulate security audit
            audit_results = {
                "basic": {
                    "score": 85,
                    "issues": ["No critical issues found"],
                    "recommendations": ["Enable 2FA for admin accounts"]
                },
                "comprehensive": {
                    "score": 78,
                    "issues": [
                        "Outdated SSL certificate detected",
                        "Missing security headers"
                    ],
                    "recommendations": [
                        "Update SSL certificate",
                        "Add security headers (HSTS, CSP)",
                        "Enable rate limiting"
                    ]
                },
                "compliance": {
                    "score": 72,
                    "issues": [
                        "Data encryption not enabled",
                        "Audit logging incomplete"
                    ],
                    "recommendations": [
                        "Enable data encryption at rest",
                        "Implement comprehensive audit logging",
                        "Create data retention policy"
                    ]
                }
            }
            
            result = audit_results.get(audit_type, audit_results['basic'])
            
            response_text = f"🔒 Security Audit ({audit_type.title()})\n\n"
            response_text += f"Security Score: {result['score']}/100\n\n"
            
            if result['issues']:
                response_text += "Issues Found:\n"
                for issue in result['issues']:
                    response_text += f"• {issue}\n"
                response_text += "\n"
            
            if include_recommendations and result['recommendations']:
                response_text += "Recommendations:\n"
                for rec in result['recommendations']:
                    response_text += f"• {rec}\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "is_error": False
            }
        
        except Exception as e:
            self.logger.error(f"Error running security audit: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error running security audit: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    async def _handle_system_health(self, auth_context: Dict[str, Any], **params) -> Dict[str, Any]:
        """Handle system health tool call."""
        try:
            include_deployments = params.get('include_deployments', True)
            include_resources = params.get('include_resources', True)
            time_range = params.get('time_range', '1h')
            
            # Simulate system health data
            response_text = f"🏥 WebOps System Health ({time_range})\n\n"
            
            if include_resources:
                response_text += "📊 Resource Usage:\n"
                response_text += "• CPU: 45% (Optimal)\n"
                response_text += "• Memory: 62% (Good)\n"
                response_text += "• Disk: 34% (Good)\n"
                response_text += "• Network: 23% (Good)\n\n"
            
            if include_deployments:
                response_text += "🚀 Deployment Status:\n"
                response_text += "• Total Deployments: 15\n"
                response_text += "• Running: 12 (80%)\n"
                response_text += "• Error: 2 (13%)\n"
                response_text += "• Stopped: 1 (7%)\n\n"
            
            response_text += "⚡ Services:\n"
            response_text += "• WebOps API: ✅ Healthy\n"
            response_text += "• Database: ✅ Healthy\n"
            response_text += "• Redis: ✅ Healthy\n"
            response_text += "• Nginx: ✅ Healthy\n\n"
            
            response_text += "Overall Health: 🟢 Good\n"
            response_text += f"Last Check: {datetime.now().isoformat()}\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "is_error": False
            }
        
        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error checking system health: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get list of MCP tools."""
        tools = []
        for tool_def in self.tools.values():
            tools.append({
                "name": tool_def.name,
                "description": tool_def.description,
                "inputSchema": tool_def.input_schema
            })
        return tools
    
    async def handle_tool_call(
        self,
        name: str,
        arguments: Dict[str, Any],
        auth_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle MCP tool call."""
        if name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Unknown tool: {name}"
                    }
                ],
                "is_error": True
            }
        
        tool_def = self.tools[name]
        
        try:
            # Check permissions
            if tool_def.permissions:
                user_permissions = auth_context.get('permissions', [])
                if not any(perm in user_permissions for perm in tool_def.permissions):
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"❌ Insufficient permissions for tool: {name}"
                            }
                        ],
                        "is_error": True
                    }
            
            # Execute tool
            result = await tool_def.handler(auth_context, **arguments)
            return result
        
        except Exception as e:
            self.logger.error(f"Error executing tool {name}: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Tool execution error: {str(e)}"
                    }
                ],
                "is_error": True
            }
    
    def set_auth_context(self, user_id: str, auth_context: Dict[str, Any]):
        """Set authentication context for a user."""
        self.auth_contexts[user_id] = auth_context
    
    def get_auth_context(self, user_id: str) -> Dict[str, Any]:
        """Get authentication context for a user."""
        return self.auth_contexts.get(user_id, {})


# Example MCP client integration
async def create_mcp_client_example():
    """Example of how to use the MCP server with an MCP client."""
    print("🌐 WebOps MCP Server - Client Example")
    print("=" * 50)
    
    # Server configuration
    config = {
        'llm_config': {
            'llm_provider': 'openai',
            'llm_model': 'gpt-4',
            'llm_api_key': 'your-api-key-here'
        },
        'webops_config': {
            'api_url': 'http://localhost:8000'
        }
    }
    
    # Initialize MCP server
    server = WebOpsMCPServer(config)
    
    # Example tool calls
    tool_calls = [
        {
            "name": "webops_list_deployments",
            "arguments": {"environment": "production", "limit": 10}
        },
        {
            "name": "webops_system_health",
            "arguments": {}
        },
        {
            "name": "webops_deploy_app",
            "arguments": {
                "app_name": "test-app",
                "repository": "https://github.com/user/test-app.git",
                "branch": "main"
            }
        }
    ]
    
    # Mock auth context
    auth_context = {
        "user_id": "test_user",
        "permissions": ["deploy:read", "deploy:create", "system:read"]
    }
    
    print("🤖 Executing MCP Tool Calls:")
    for i, tool_call in enumerate(tool_calls, 1):
        print(f"\n--- Tool Call {i} ---")
        print(f"Tool: {tool_call['name']}")
        print(f"Arguments: {json.dumps(tool_call['arguments'], indent=2)}")
        
        try:
            result = await server.handle_tool_call(
                tool_call['name'],
                tool_call['arguments'],
                auth_context
            )
            
            print(f"Result:")
            print(json.dumps(result, indent=2))
            
        except Exception as e:
            print(f"Error: {str(e)}")
    
    # Show available tools
    print(f"\n📋 Available Tools ({len(server.get_mcp_tools())}):")
    for tool in server.get_mcp_tools():
        print(f"• {tool['name']}: {tool['description']}")


if __name__ == "__main__":
    # Run the example
    asyncio.run(create_mcp_client_example())