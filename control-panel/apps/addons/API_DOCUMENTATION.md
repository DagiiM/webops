# WebOps Addon Management API

Complete REST API documentation for managing WebOps addons through HTTP endpoints.

## Table of Contents

1. [Authentication](#authentication)
2. [Response Format](#response-format)
3. [Endpoints](#endpoints)
4. [Usage Examples](#usage-examples)
5. [Error Handling](#error-handling)

## Authentication

All API endpoints require authentication. Include your session cookie or use Django's authentication system.

```bash
# Login first
curl -X POST http://localhost:8000/accounts/login/ \
  -d "username=admin&password=admin123" \
  -c cookies.txt

# Then use the cookie for API requests
curl -b cookies.txt http://localhost:8000/addons/api/addons/
```

## Response Format

All responses are JSON with the following structure:

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {...}
}
```

### Error Response
```json
{
  "error": "Error message describing what went wrong"
}
```

## Endpoints

### List All Addons

**GET** `/addons/api/addons/`

List all available addons (both system and application).

**Query Parameters:**
- `type` (optional): Filter by addon type (`system` or `application`)
- `status` (optional): Filter by status
- `category` (optional): Filter by category
- `page` (default: 1): Page number
- `per_page` (default: 20): Items per page

**Response:**
```json
{
  "addons": [
    {
      "id": 1,
      "name": "postgresql",
      "display_name": "PostgreSQL Database",
      "type": "system",
      "version": "14.0.0",
      "status": "installed",
      "health": "healthy",
      "enabled": true,
      "category": "database",
      "description": "PostgreSQL relational database server",
      "created_at": "2025-11-01T12:00:00Z",
      "updated_at": "2025-11-02T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 7,
    "pages": 1
  }
}
```

**Example:**
```bash
# List all addons
curl -b cookies.txt http://localhost:8000/addons/api/addons/

# List only system addons
curl -b cookies.txt "http://localhost:8000/addons/api/addons/?type=system"

# List installed system addons
curl -b cookies.txt "http://localhost:8000/addons/api/addons/?type=system&status=installed"
```

---

### Get Addon Details

**GET** `/addons/api/addons/<name>/`

Get detailed information about a specific addon.

**Response:**
```json
{
  "id": 1,
  "name": "postgresql",
  "display_name": "PostgreSQL Database",
  "type": "system",
  "version": "14.0.0",
  "status": "installed",
  "health": "healthy",
  "enabled": true,
  "category": "database",
  "description": "PostgreSQL relational database server",
  "script_path": "/path/to/postgresql.sh",
  "depends_on": [],
  "provides": ["postgresql"],
  "conflicts_with": ["mysql"],
  "config": {"port": 5432, "max_connections": 100},
  "installed_at": "2025-11-01T12:00:00Z",
  "installed_by": "admin",
  "success_count": 15,
  "failure_count": 1,
  "last_duration_ms": 2500
}
```

**Example:**
```bash
curl -b cookies.txt http://localhost:8000/addons/api/addons/postgresql/
```

---

### Discover Addons

**POST** `/addons/api/addons/discover/`

Trigger addon discovery process to find all system addons.

**Response:**
```json
{
  "success": true,
  "message": "Discovered 7 system addon(s)",
  "count": 7
}
```

**Example:**
```bash
curl -X POST -b cookies.txt http://localhost:8000/addons/api/addons/discover/
```

---

### Install System Addon

**POST** `/addons/api/addons/<name>/install/`

Install a system addon asynchronously.

**Request Body:**
```json
{
  "config": {
    "port": 5432,
    "max_connections": 200
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Installation of postgresql started",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "addon": {...}
}
```

**Example:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"config": {"port": 5432}}' \
  http://localhost:8000/addons/api/addons/postgresql/install/
```

---

### Uninstall System Addon

**POST** `/addons/api/addons/<name>/uninstall/`

Uninstall a system addon asynchronously.

**Request Body:**
```json
{
  "keep_data": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Uninstallation of postgresql started",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "addon": {...}
}
```

**Example:**
```bash
# Uninstall but keep data
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"keep_data": true}' \
  http://localhost:8000/addons/api/addons/postgresql/uninstall/

# Uninstall and delete data
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"keep_data": false}' \
  http://localhost:8000/addons/api/addons/postgresql/uninstall/
```

---

### Configure System Addon

**POST** `/addons/api/addons/<name>/configure/`

Configure a system addon with new settings.

**Request Body:**
```json
{
  "config": {
    "port": 5433,
    "max_connections": 300,
    "shared_buffers": "256MB"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration of postgresql started",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "addon": {...}
}
```

**Example:**
```bash
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"config": {"port": 5433, "max_connections": 300}}' \
  http://localhost:8000/addons/api/addons/postgresql/configure/
```

---

### Toggle Addon Enabled Status

**POST** `/addons/api/addons/<name>/toggle/`

Enable or disable an addon (both system and application).

**Request Body:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Addon postgresql enabled",
  "addon": {
    "name": "postgresql",
    "enabled": true,
    "type": "system"
  }
}
```

**Example:**
```bash
# Enable addon
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}' \
  http://localhost:8000/addons/api/addons/postgresql/toggle/

# Disable addon
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  http://localhost:8000/addons/api/addons/postgresql/toggle/
```

---

### Get Addon Status

**GET** `/addons/api/addons/<name>/status/`

Get current installation and health status of an addon.

**Response:**
```json
{
  "name": "postgresql",
  "status": "installed",
  "health": "healthy",
  "version": "14.0.0",
  "installed_at": "2025-11-01T12:00:00Z",
  "last_error": null
}
```

**Example:**
```bash
curl -b cookies.txt http://localhost:8000/addons/api/addons/postgresql/status/
```

---

### Sync Addon Status

**POST** `/addons/api/addons/<name>/sync/`

Sync addon status from the system to the database.

**Response:**
```json
{
  "success": true,
  "message": "Status sync for postgresql started",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Example:**
```bash
curl -X POST -b cookies.txt \
  http://localhost:8000/addons/api/addons/postgresql/sync/
```

---

### Health Check All Addons

**POST** `/addons/api/addons/health-check/`

Trigger health check for all installed system addons.

**Response:**
```json
{
  "success": true,
  "message": "Health check started for all addons",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Example:**
```bash
curl -X POST -b cookies.txt \
  http://localhost:8000/addons/api/addons/health-check/
```

---

### Get Addon Execution History

**GET** `/addons/api/addons/<name>/executions/`

Get execution history for a system addon.

**Query Parameters:**
- `page` (default: 1): Page number
- `per_page` (default: 20): Items per page
- `operation` (optional): Filter by operation (`install`, `uninstall`, `configure`, etc.)
- `status` (optional): Filter by status (`success`, `failed`, `running`)

**Response:**
```json
{
  "executions": [
    {
      "id": 123,
      "operation": "install",
      "status": "success",
      "started_at": "2025-11-01T12:00:00Z",
      "completed_at": "2025-11-01T12:02:30Z",
      "duration_ms": 150000,
      "requested_by": "admin",
      "error_message": null,
      "celery_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 15,
    "pages": 1
  }
}
```

**Example:**
```bash
# Get all executions
curl -b cookies.txt \
  http://localhost:8000/addons/api/addons/postgresql/executions/

# Get failed executions
curl -b cookies.txt \
  "http://localhost:8000/addons/api/addons/postgresql/executions/?status=failed"
```

---

### Get Execution Details

**GET** `/addons/api/executions/<execution_id>/`

Get detailed information about a specific execution.

**Response:**
```json
{
  "id": 123,
  "addon": "postgresql",
  "operation": "install",
  "status": "success",
  "started_at": "2025-11-01T12:00:00Z",
  "completed_at": "2025-11-01T12:02:30Z",
  "duration_ms": 150000,
  "requested_by": "admin",
  "input_data": {"config": {"port": 5432}},
  "output_data": {"version": "14.0.0"},
  "error_message": null,
  "stdout": "Installation log output...",
  "stderr": "",
  "celery_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Example:**
```bash
curl -b cookies.txt http://localhost:8000/addons/api/executions/123/
```

---

### Get Addon Statistics

**GET** `/addons/api/addons/stats/`

Get overall statistics for all addons.

**Response:**
```json
{
  "system_addons": {
    "total": 7,
    "installed": 5,
    "healthy": 4,
    "unhealthy": 0,
    "degraded": 1
  },
  "application_addons": {
    "total": 2,
    "enabled": 2
  },
  "executions_24h": {
    "total": 45,
    "success": 42,
    "failed": 2,
    "running": 1
  }
}
```

**Example:**
```bash
curl -b cookies.txt http://localhost:8000/addons/api/addons/stats/
```

## Usage Examples

### Complete Workflow: Install PostgreSQL

```bash
# 1. Discover available addons
curl -X POST -b cookies.txt \
  http://localhost:8000/addons/api/addons/discover/

# 2. List system addons
curl -b cookies.txt \
  "http://localhost:8000/addons/api/addons/?type=system"

# 3. Get PostgreSQL details
curl -b cookies.txt \
  http://localhost:8000/addons/api/addons/postgresql/

# 4. Install PostgreSQL with custom config
curl -X POST -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"config": {"port": 5432, "max_connections": 200}}' \
  http://localhost:8000/addons/api/addons/postgresql/install/

# 5. Check installation status
curl -b cookies.txt \
  http://localhost:8000/addons/api/addons/postgresql/status/

# 6. View execution history
curl -b cookies.txt \
  http://localhost:8000/addons/api/addons/postgresql/executions/
```

### Python Client Example

```python
import requests

# Setup session
session = requests.Session()
session.post('http://localhost:8000/accounts/login/', data={
    'username': 'admin',
    'password': 'admin123'
})

# List all addons
response = session.get('http://localhost:8000/addons/api/addons/')
addons = response.json()['addons']
print(f"Found {len(addons)} addons")

# Install PostgreSQL
response = session.post(
    'http://localhost:8000/addons/api/addons/postgresql/install/',
    json={'config': {'port': 5432}}
)
task_id = response.json()['task_id']
print(f"Installation started: {task_id}")

# Check status
response = session.get('http://localhost:8000/addons/api/addons/postgresql/status/')
status = response.json()
print(f"Status: {status['status']}, Health: {status['health']}")
```

### JavaScript Fetch Example

```javascript
// Install addon
async function installAddon(name, config) {
  const response = await fetch(`/addons/api/addons/${name}/install/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({config})
  });

  const data = await response.json();
  console.log('Installation started:', data.task_id);
  return data;
}

// Get addon status
async function getAddonStatus(name) {
  const response = await fetch(`/addons/api/addons/${name}/status/`);
  const status = await response.json();
  console.log(`${name}: ${status.status} (${status.health})`);
  return status;
}

// Usage
await installAddon('postgresql', {port: 5432});
await getAddonStatus('postgresql');
```

## Error Handling

### Common HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request data (missing parameters, invalid JSON)
- `404 Not Found`: Addon or resource not found
- `500 Internal Server Error`: Server error during operation

### Error Response Examples

**Addon Not Found:**
```json
{
  "error": "Addon postgresql not found"
}
```

**Invalid JSON:**
```json
{
  "error": "Invalid JSON"
}
```

**Missing Configuration:**
```json
{
  "error": "Configuration required"
}
```

## Rate Limiting

API endpoints use Django's authentication system. For production use, consider implementing rate limiting using:

- Django Rate Limit
- Django REST Framework throttling
- Nginx rate limiting

## Best Practices

1. **Always check task status**: Install/uninstall operations are asynchronous. Monitor task status or execution history.

2. **Use proper error handling**: Check response status codes and handle errors gracefully.

3. **Keep data by default**: When uninstalling, use `keep_data: true` unless you're sure you want to delete data.

4. **Run health checks regularly**: Use the health check endpoint periodically to monitor addon health.

5. **Discover before installing**: Always run discovery to ensure the latest addons are available.

6. **Monitor execution history**: Check execution logs for debugging failed operations.

## Security Considerations

1. **Authentication Required**: All endpoints require authentication
2. **CSRF Protection**: POST requests require CSRF token
3. **Input Validation**: All input is validated before processing
4. **Audit Trail**: All operations are logged in execution history
5. **Least Privilege**: Addon operations run with minimal required permissions

## Support

- API Documentation: `/control-panel/apps/addons/API_DOCUMENTATION.md`
- Unified System Docs: `/control-panel/apps/addons/UNIFIED_ADDON_SYSTEM.md`
- Django Admin: `/admin/addons/`
- Issues: https://github.com/anthropics/webops/issues
