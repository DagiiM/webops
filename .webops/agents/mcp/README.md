# WebOps MCP (Model Context Protocol) Server

## 🌟 Overview

The WebOps MCP Server provides a standardized, AI-agent-friendly interface to all WebOps platform services through the Model Context Protocol (MCP). This allows AI agents, development tools, and integrations to seamlessly interact with WebOps deployments, monitoring, and management capabilities.

## 🎯 Benefits

- **🔌 Universal AI Compatibility**: Works with any MCP-compatible AI agent or tool
- **🔒 Secure & Authenticated**: Built-in authentication and permission management
- **⚡ Fast & Efficient**: Optimized for real-time operations and monitoring
- **🛡️ Enterprise Ready**: Audit logging, rate limiting, and security features
- **📊 Comprehensive Coverage**: Access to all WebOps platform features

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install the MCP package
pip install mcp>=1.0.0
```

### Basic Usage

```python
from mcp.webops_server import WebOpsMCPServer
import asyncio

# Initialize the MCP server
config = {
    'llm_config': {
        'llm_provider': 'openai',
        'llm_model': 'gpt-4',
        'llm_api_key': 'your-api-key'
    },
    'webops_config': {
        'api_url': 'http://localhost:8000'
    }
}

server = WebOpsMCPServer(config)

# Authenticate a user
auth_context = {
    'user_id': 'admin',
    'permissions': ['deploy:read', 'deploy:create', 'system:read']
}
server.set_auth_context('admin', auth_context)

# Execute a tool
result = await server.handle_tool_call(
    'webops_list_deployments',
    {'environment': 'production', 'limit': 10},
    auth_context
)
```

## 📋 Available Tools

### 🚀 Deployment Management

#### `webops_deploy_app`
Deploy a new application to WebOps hosting platform.

**Parameters:**
- `app_name` (required): Name of the application
- `repository` (required): Git repository URL
- `branch` (optional): Git branch (default: main)
- `environment` (optional): Target environment (development/staging/production)
- `python_version` (optional): Python version (3.9-3.12)
- `database_type` (optional): Database type (postgresql/mysql/sqlite)
- `ssl_enabled` (optional): Enable SSL certificate (default: true)

**Example:**
```json
{
  "app_name": "my-django-app",
  "repository": "https://github.com/user/django-app.git",
  "branch": "main",
  "environment": "production",
  "python_version": "3.11"
}
```

### 📊 Monitoring & Status

#### `webops_get_status`
Get the status of specific WebOps deployments.

**Parameters:**
- `deployment_id` (optional): Specific deployment ID
- `include_logs` (optional): Include deployment logs
- `include_metrics` (optional): Include performance metrics

#### `webops_list_deployments`
List all WebOps deployments with filtering.

**Parameters:**
- `environment` (optional): Filter by environment
- `status` (optional): Filter by status (running/stopped/error/pending)
- `limit` (optional): Maximum results (1-200, default: 50)

#### `webops_get_logs`
Retrieve logs from WebOps deployments.

**Parameters:**
- `deployment_id` (required): Deployment ID
- `log_type` (optional): Log type (application/access/error/deployment)
- `lines` (optional): Number of lines (10-1000, default: 100)
- `since` (optional): Get logs since timestamp (ISO format)

### 🔧 Service Management

#### `webops_manage_service`
Start, stop, restart, or scale a WebOps service.

**Parameters:**
- `deployment_id` (required): Deployment ID to manage
- `action` (required): Action (start/stop/restart/scale_up/scale_down)
- `instances` (optional): Number of instances for scaling (1-10)

### 🔒 Security

#### `webops_security_audit`
Run security audit on WebOps deployments.

**Parameters:**
- `deployment_id` (optional): Specific deployment to audit
- `audit_type` (optional): Audit type (basic/comprehensive/compliance)
- `include_recommendations` (optional): Include security recommendations

### 🏥 System Health

#### `webops_system_health`
Check WebOps system health and metrics.

**Parameters:**
- `include_deployments` (optional): Include deployment health data
- `include_resources` (optional): Include resource usage data
- `time_range` (optional): Time range (1h/6h/24h/7d)

## 🔐 Authentication

The MCP server supports multiple authentication methods:

### Bearer Token Authentication
```python
auth_context = {
    'user_id': 'user123',
    'token': 'your-jwt-token',
    'permissions': ['deploy:read', 'deploy:create']
}
```

### API Key Authentication
```python
auth_context = {
    'user_id': 'user123',
    'api_key': 'your-api-key',
    'permissions': ['deploy:read']
}
```

### Basic Authentication
```python
auth_context = {
    'user_id': 'user123',
    'username': 'admin',
    'password': 'secure-password',
    'permissions': ['deploy:read', 'deploy:create', 'deploy:manage']
}
```

## 🛡️ Permissions

### Available Permissions
- `deploy:read` - View deployment information
- `deploy:create` - Create new deployments
- `deploy:manage` - Manage deployments (start/stop/restart/scale)
- `deploy:delete` - Delete deployments
- `system:read` - View system health and metrics
- `security:audit` - Run security audits
- `logs:read` - Access deployment logs
- `admin:*` - Full administrative access

### Permission-based Access Control
```python
# User with limited permissions
limited_user = {
    'user_id': 'developer',
    'permissions': ['deploy:read', 'logs:read']
}

# User with full permissions
admin_user = {
    'user_id': 'admin',
    'permissions': ['deploy:read', 'deploy:create', 'deploy:manage', 'system:read', 'security:audit']
}
```

## 🤖 AI Agent Integration

### Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "webops": {
      "command": "python",
      "args": ["-m", "mcp.webops_server"],
      "env": {
        "WEBOPS_API_URL": "http://localhost:8000",
        "WEBOPS_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Custom AI Agent Integration

```python
from mcp import ClientSession, ServerSession
import asyncio

async def integrate_with_ai_agent():
    # Initialize MCP client
    client = ClientSession()
    
    # Connect to WebOps MCP server
    await client.connect("mcp://localhost:8000")
    
    # List available tools
    tools = await client.list_tools()
    
    # Execute a deployment
    result = await client.call_tool("webops_deploy_app", {
        "app_name": "test-app",
        "repository": "https://github.com/user/repo.git"
    })
    
    return result
```

## 📊 Response Format

All tool calls return standardized responses:

### Success Response
```json
{
  "content": [
    {
      "type": "text",
      "text": "✅ Deployment started successfully\n\nDeployment ID: abc123\nStatus: Running\nURL: https://app.example.com"
    }
  ],
  "is_error": false
}
```

### Error Response
```json
{
  "content": [
    {
      "type": "text",
      "text": "❌ Deployment failed: Insufficient permissions\nPlease contact your administrator."
    }
  ],
  "is_error": true
}
```

## 🔧 Configuration

### Environment Variables
```bash
# WebOps API Configuration
WEBOPS_API_URL=http://localhost:8000
WEBOPS_API_VERSION=v1
WEBOPS_API_KEY=your-api-key

# LLM Configuration (optional)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
LLM_API_KEY=your-llm-api-key

# Security Configuration
JWT_SECRET=your-jwt-secret
ENCRYPTION_KEY=your-encryption-key
```

### Server Configuration
```python
config = {
    'webops_config': {
        'api_url': 'http://localhost:8000',
        'api_version': 'v1',
        'timeout': 30,
        'max_retries': 3
    },
    'llm_config': {
        'llm_provider': 'openai',
        'llm_model': 'gpt-4',
        'llm_api_key': 'your-api-key',
        'temperature': 0.1
    },
    'security_config': {
        'rate_limit_per_minute': 100,
        'max_concurrent_requests': 50,
        'audit_logging': True
    }
}
```

## 📈 Monitoring & Logging

### Built-in Metrics
- Request rate and response times
- Tool execution success/failure rates
- Authentication attempts and failures
- Resource usage and performance

### Audit Logging
All actions are logged with:
- User ID and permissions
- Tool called and parameters
- Success/failure status
- Timestamp and execution time

### Health Checks
```bash
# Check server health
curl http://localhost:8080/health

# Get server metrics
curl http://localhost:8080/metrics
```

## 🚀 Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "-m", "mcp.webops_server"]
```

### Systemd Service
```ini
[Unit]
Description=WebOps MCP Server
After=network.target

[Service]
Type=simple
User=webops
WorkingDirectory=/opt/webops-mcp
ExecStart=/opt/webops-mcp/venv/bin/python -m mcp.webops_server
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx Reverse Proxy
```nginx
server {
    listen 443 ssl;
    server_name mcp.webops.example.com;

    ssl_certificate /etc/ssl/certs/webops.crt;
    ssl_certificate_key /etc/ssl/private/webops.key;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🧪 Testing

### Unit Tests
```bash
pytest tests/ -v --cov=mcp.webops_server
```

### Integration Tests
```bash
# Test with mock WebOps API
pytest tests/integration/ -v

# Test authentication
pytest tests/auth/ -v

# Test tool execution
pytest tests/tools/ -v
```

### Load Testing
```bash
# Test concurrent requests
python tests/load_test.py --concurrent-users 10 --duration 60s
```

## 🔍 Troubleshooting

### Common Issues

**Authentication Failures**
```python
# Check authentication context
auth_context = server.get_auth_context('user_id')
print(f"Auth context: {auth_context}")

# Verify permissions
permissions = auth_context.get('permissions', [])
required_permission = 'deploy:create'
if required_permission not in permissions:
    print(f"Missing permission: {required_permission}")
```

**API Connection Issues**
```python
# Test WebOps API connectivity
import aiohttp

async def test_api_connection():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8000/health') as resp:
            return resp.status == 200
```

**Tool Execution Errors**
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check tool definitions
tools = server.get_mcp_tools()
print(f"Available tools: {[tool['name'] for tool in tools]}")
```

## 🤝 Contributing

### Development Setup
```bash
git clone https://github.com/dagiim/webops
cd webops/.webops/agents/mcp
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Adding New Tools
```python
# Add new tool to _setup_mcp_tools()
self.tools["new_webops_tool"] = MCPToolDefinition(
    name="new_webops_tool",
    description="Description of the new tool",
    input_schema={...},
    handler=self._handle_new_tool,
    category="new_category"
)

# Implement handler
async def _handle_new_tool(self, auth_context, **params):
    # Tool implementation
    return {"content": [...], "is_error": False}
```

## 📚 API Reference

### Core Classes

#### `WebOpsMCPServer`
Main MCP server class that wraps WebOps services.

#### `MCPToolDefinition`
Definition class for MCP tools with metadata and validation.

#### `WebOpsActionLibrary`
Action library that manages WebOps service interactions.

### Key Methods

#### `handle_tool_call(name, arguments, auth_context)`
Handle MCP tool execution with authentication and validation.

#### `get_mcp_tools()`
Return list of available MCP tools.

#### `set_auth_context(user_id, auth_context)`
Set authentication context for a user.

#### `get_auth_context(user_id)`
Get authentication context for a user.

## 📄 License

This MCP server is part of the WebOps platform and is licensed under the same terms as the main WebOps project.

## 🆘 Support

For support and questions:
- 📧 Email: support@eleso-solutions.com
- 💬 Discord: [WebOps Community](https://discord.gg/webops)
- 🐛 Issues: [GitHub Issues](https://github.com/dagiim/webops/issues)
- 📖 Docs: [WebOps Documentation](https://docs.webops.example.com)

---

**Built with ❤️ by Eleso Solutions**