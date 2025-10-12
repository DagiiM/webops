# WebOps REST API Reference 🔌

**Complete API documentation for WebOps v2.0**

The WebOps REST API provides programmatic access to all platform features with enterprise-grade security and reliability.

---

## 🚀 **Quick Start**

### **Base URL**
```
https://your-webops-domain.com/api/v1/
```

### **Authentication**
```bash
# Create API token in WebOps control panel
curl -X POST https://your-webops-domain.com/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Use token in subsequent requests
curl -H "Authorization: Bearer your_api_token" \
  https://your-webops-domain.com/api/v1/deployments/
```

### **Rate Limits**
- **General API**: 100 requests/hour per token
- **Deployments**: 10 deployments/hour per user
- **Authentication**: 5 attempts/15 minutes per IP

---

## 📝 **API Overview**

### **Endpoints Summary**
| Endpoint | Description | Methods |
|----------|-------------|---------|
| `/auth/` | Authentication and tokens | GET, POST, DELETE |
| `/deployments/` | Application deployments | GET, POST, PUT, DELETE |
| `/databases/` | Database management | GET, POST, PUT, DELETE |
| `/services/` | Service monitoring | GET, POST, PUT |
| `/monitoring/` | System health metrics | GET |
| `/logs/` | Deployment and system logs | GET |
| `/users/` | User management | GET, POST, PUT, DELETE |

### **Response Format**
All API responses follow this format:
```json
{
  "success": true,
  "data": {},
  "message": "Success message",
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### **Error Response**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "name": ["This field is required"],
      "repo_url": ["Enter a valid URL"]
    }
  }
}
```

---

## 🔐 **Authentication**

### **Create API Token**
```http
POST /api/v1/auth/token/
Content-Type: application/json

{
  "username": "admin",
  "password": "your_password",
  "name": "My CLI Token",
  "expires_in": 86400
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "token": "wop_1234567890abcdef",
    "expires_at": "2024-12-15T10:30:00Z",
    "permissions": ["deployments", "databases", "monitoring"]
  }
}
```

### **Verify Token**
```http
GET /api/v1/auth/verify/
Authorization: Bearer wop_1234567890abcdef
```

### **Revoke Token**
```http
DELETE /api/v1/auth/token/wop_1234567890abcdef/
Authorization: Bearer wop_1234567890abcdef
```

---

## 🚀 **Deployments API**

### **List Deployments**
```http
GET /api/v1/deployments/
Authorization: Bearer your_token

# Query parameters
?status=running          # Filter by status
?project_type=django     # Filter by type
?search=my-app          # Search by name
?page=2                 # Pagination
?per_page=10           # Results per page
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "my-django-app",
      "status": "running",
      "project_type": "django",
      "repo_url": "https://github.com/user/repo",
      "branch": "main",
      "domain": "myapp.example.com",
      "port": 8001,
      "created_at": "2024-12-14T10:00:00Z",
      "updated_at": "2024-12-14T10:30:00Z",
      "deployed_by": {
        "id": 1,
        "username": "admin"
      },
      "health": {
        "is_healthy": true,
        "uptime_seconds": 3600,
        "last_check": "2024-12-14T11:00:00Z"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 5,
    "total_pages": 1
  }
}
```

### **Create Deployment**
```http
POST /api/v1/deployments/
Authorization: Bearer your_token
Content-Type: application/json

{
  "name": "my-new-app",
  "repo_url": "https://github.com/user/django-app",
  "branch": "main",
  "project_type": "django",
  "domain": "myapp.example.com",
  "env_vars": {
    "DEBUG": "False",
    "DATABASE_URL": "postgresql://...",
    "CUSTOM_VAR": "value"
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 6,
    "name": "my-new-app",
    "status": "pending",
    "deployment_task_id": "celery-task-uuid",
    "estimated_completion": "2024-12-14T11:10:00Z"
  },
  "message": "Deployment created and queued successfully"
}
```

### **Get Deployment Details**
```http
GET /api/v1/deployments/1/
Authorization: Bearer your_token
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "my-django-app",
    "status": "running",
    "project_type": "django",
    "repo_url": "https://github.com/user/repo",
    "branch": "main",
    "domain": "myapp.example.com",
    "port": 8001,
    "ssl_enabled": true,
    "created_at": "2024-12-14T10:00:00Z",
    "updated_at": "2024-12-14T10:30:00Z",
    "deployed_by": {
      "id": 1,
      "username": "admin"
    },
    "env_vars": {
      "DEBUG": "False",
      "DATABASE_URL": "postgresql://..."
    },
    "metrics": {
      "cpu_usage": 15.2,
      "memory_usage": 45.8,
      "request_count_24h": 1500,
      "error_rate": 0.1
    },
    "health": {
      "is_healthy": true,
      "uptime_seconds": 3600,
      "last_check": "2024-12-14T11:00:00Z",
      "checks": {
        "http_response": true,
        "database_connection": true,
        "disk_space": true
      }
    }
  }
}
```

### **Update Deployment**
```http
PUT /api/v1/deployments/1/
Authorization: Bearer your_token
Content-Type: application/json

{
  "branch": "production",
  "domain": "newdomain.example.com",
  "env_vars": {
    "DEBUG": "False",
    "NEW_VAR": "new_value"
  }
}
```

### **Deployment Actions**
```http
# Start deployment
POST /api/v1/deployments/1/start/

# Stop deployment  
POST /api/v1/deployments/1/stop/

# Restart deployment
POST /api/v1/deployments/1/restart/

# Redeploy (pull latest code)
POST /api/v1/deployments/1/redeploy/

# Get deployment logs
GET /api/v1/deployments/1/logs/?lines=100&follow=true
```

### **Delete Deployment**
```http
DELETE /api/v1/deployments/1/
Authorization: Bearer your_token
```

---

## 🗄️ **Databases API**

### **List Databases**
```http
GET /api/v1/databases/
Authorization: Bearer your_token
```

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "myapp_db",
      "username": "myapp_user",
      "host": "localhost",
      "port": 5432,
      "created_at": "2024-12-14T10:00:00Z",
      "deployment": {
        "id": 1,
        "name": "my-django-app"
      },
      "size_mb": 150.5,
      "connection_count": 5
    }
  ]
}
```

### **Create Database**
```http
POST /api/v1/databases/
Authorization: Bearer your_token
Content-Type: application/json

{
  "name": "my_new_db",
  "username": "db_user",
  "deployment_id": 1
}
```

### **Database Actions**
```http
# Backup database
POST /api/v1/databases/1/backup/

# Restore database
POST /api/v1/databases/1/restore/
{
  "backup_id": "backup-uuid"
}

# Get database metrics
GET /api/v1/databases/1/metrics/
```

---

## 📊 **Monitoring API**

### **System Health**
```http
GET /api/v1/monitoring/health/
Authorization: Bearer your_token
```

**Response:**
```json
{
  "success": true,
  "data": {
    "overall_status": "healthy",
    "timestamp": "2024-12-14T11:00:00Z",
    "system": {
      "cpu_percent": 25.5,
      "memory_percent": 65.2,
      "disk_percent": 40.1,
      "load_average": [0.5, 0.8, 0.9],
      "uptime_seconds": 86400
    },
    "services": {
      "web": "running",
      "celery": "running", 
      "redis": "running",
      "postgresql": "running",
      "nginx": "running"
    },
    "deployments": {
      "total": 5,
      "running": 4,
      "stopped": 1,
      "failed": 0
    }
  }
}
```

### **Performance Metrics**
```http
GET /api/v1/monitoring/metrics/
Authorization: Bearer your_token

# Query parameters
?period=1h              # 1h, 6h, 24h, 7d, 30d
?metrics=cpu,memory     # Specific metrics
?deployment_id=1        # Filter by deployment
```

### **Error Logs**
```http
GET /api/v1/monitoring/errors/
Authorization: Bearer your_token

# Query parameters
?level=error            # debug, info, warning, error, critical
?start_date=2024-12-14  # Filter by date range
?end_date=2024-12-15
?search=django          # Search log messages
```

---

## 📋 **Logs API**

### **Get Deployment Logs**
```http
GET /api/v1/deployments/1/logs/
Authorization: Bearer your_token

# Query parameters
?lines=100              # Number of lines
?follow=true           # Real-time streaming
?level=error           # Filter by log level
?since=2024-12-14      # Logs since date
```

**Response (streaming):**
```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "timestamp": "2024-12-14T11:00:01Z",
        "level": "info",
        "message": "Starting Django application",
        "source": "gunicorn"
      },
      {
        "timestamp": "2024-12-14T11:00:05Z", 
        "level": "info",
        "message": "Application ready on port 8001",
        "source": "webops"
      }
    ],
    "total_lines": 150,
    "is_live": true
  }
}
```

### **System Logs**
```http
GET /api/v1/logs/system/
Authorization: Bearer your_token

# Available log types
?type=nginx             # nginx, postgresql, redis, celery
?lines=50
?follow=false
```

---

## 👥 **Users API** (Admin Only)

### **List Users**
```http
GET /api/v1/users/
Authorization: Bearer admin_token
```

### **Create User**
```http
POST /api/v1/users/
Authorization: Bearer admin_token
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com", 
  "password": "secure_password",
  "is_staff": false,
  "permissions": ["deployments"]
}
```

### **User Permissions**
```http
# Get user permissions
GET /api/v1/users/1/permissions/

# Update user permissions
PUT /api/v1/users/1/permissions/
{
  "permissions": ["deployments", "databases", "monitoring"]
}
```

---

## 🔍 **Advanced Features**

### **Webhooks**
```http
# Create webhook
POST /api/v1/webhooks/
{
  "url": "https://your-app.com/webhook/",
  "events": ["deployment.completed", "deployment.failed"],
  "secret": "webhook_secret"
}

# Test webhook
POST /api/v1/webhooks/1/test/
```

### **Bulk Operations**
```http
# Bulk deployment actions
POST /api/v1/deployments/bulk/
{
  "action": "restart",
  "deployment_ids": [1, 2, 3],
  "async": true
}
```

### **Export Data**
```http
# Export deployments as JSON/CSV
GET /api/v1/deployments/export/?format=json
GET /api/v1/deployments/export/?format=csv

# Export system metrics
GET /api/v1/monitoring/export/?period=24h&format=json
```

---

## 📚 **SDK & Client Libraries**

### **Official Python SDK**
```bash
pip install webops-sdk
```

```python
from webops_sdk import WebOpsClient

client = WebOpsClient(
    base_url="https://your-webops-domain.com",
    token="your_api_token"
)

# Create deployment
deployment = client.deployments.create({
    "name": "my-app",
    "repo_url": "https://github.com/user/repo",
    "branch": "main"
})

# Monitor deployment progress
for log in client.deployments.stream_logs(deployment.id):
    print(f"{log.timestamp}: {log.message}")
```

### **CLI Tool**
```bash
# Install CLI
npm install -g webops-cli

# Configure
webops config set url https://your-webops-domain.com
webops auth login

# Deploy application
webops deploy create \
  --name my-app \
  --repo https://github.com/user/repo \
  --branch main

# Monitor deployment
webops deploy logs my-app --follow
```

---

## 🔧 **Error Codes**

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Invalid input data | 400 |
| `AUTHENTICATION_REQUIRED` | Missing or invalid token | 401 |
| `PERMISSION_DENIED` | Insufficient permissions | 403 |
| `RESOURCE_NOT_FOUND` | Resource doesn't exist | 404 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `DEPLOYMENT_FAILED` | Deployment process failed | 422 |
| `SERVICE_UNAVAILABLE` | System temporarily unavailable | 503 |

---

## 📝 **Examples**

### **Complete Deployment Workflow**
```bash
# 1. Create API token
TOKEN=$(curl -X POST https://webops.example.com/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}' | \
  jq -r '.data.token')

# 2. Create deployment  
DEPLOYMENT_ID=$(curl -X POST https://webops.example.com/api/v1/deployments/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-django-app",
    "repo_url": "https://github.com/user/django-app",
    "branch": "main",
    "env_vars": {"DEBUG": "False"}
  }' | jq -r '.data.id')

# 3. Monitor deployment progress
curl -X GET "https://webops.example.com/api/v1/deployments/$DEPLOYMENT_ID/logs/?follow=true" \
  -H "Authorization: Bearer $TOKEN"

# 4. Check deployment status
curl -X GET "https://webops.example.com/api/v1/deployments/$DEPLOYMENT_ID/" \
  -H "Authorization: Bearer $TOKEN" | \
  jq '.data.status'
```

---

## 🛡️ **Security Best Practices**

### **API Token Security**
- ✅ Use environment variables for tokens
- ✅ Rotate tokens regularly (90 days max)
- ✅ Use specific permissions (least privilege)
- ✅ Monitor token usage in audit logs

### **Rate Limiting**
- ✅ Implement client-side rate limiting
- ✅ Handle 429 responses with exponential backoff
- ✅ Cache responses when possible
- ✅ Use webhooks for real-time updates instead of polling

### **Input Validation**
- ✅ Validate all input data client-side
- ✅ Sanitize repository URLs and domain names
- ✅ Limit environment variable sizes
- ✅ Use HTTPS only for all API calls

---

**WebOps REST API v2.0** - *Enterprise-grade programmatic access to your hosting platform* 🔌