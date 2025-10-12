# WebOps App Contract Specification

## Overview

Every application deployed on WebOps must declare its requirements through a contract file (`webops.yml` or `webops.json`). This contract specifies what resources and services the app needs, allowing WebOps to provision them securely and efficiently.

## Contract File Location

Place one of these files in your repository root:
- `webops.yml` (preferred)
- `webops.json`
- `.webops.yml`

If no contract file exists, WebOps will attempt to auto-detect based on project structure.

## Contract Schema

### Basic Example (YAML)

```yaml
# webops.yml
version: "1.0"
name: "my-django-app"
type: "django"  # django | static | nodejs | docker

# Resource Requirements
resources:
  memory: "512M"      # Memory limit (128M - 8G)
  cpu: "0.5"          # CPU cores (0.1 - 4.0)
  disk: "2G"          # Disk quota (100M - 50G)

# Services Required
services:
  database:
    enabled: true
    type: "postgresql"  # postgresql | mysql | sqlite
    version: "15"       # Optional: specific version

  cache:
    enabled: true
    type: "redis"       # redis | memcached

  storage:
    enabled: true
    type: "local"       # local | s3
    quota: "1G"

  background_tasks:
    enabled: true
    type: "celery"      # celery | rq
    workers: 2
    beat: true          # Periodic tasks

# Network Configuration
network:
  http_port: true       # Requires HTTP server (Nginx)
  https: true           # Request SSL certificate
  websockets: false     # Enable WebSocket support

# Security & Permissions
permissions:
  filesystem:
    read: ["/opt/webops/shared"]
    write: ["/opt/webops/deployments/$APP_NAME"]

  network:
    outbound: true      # Allow outbound connections
    allowed_hosts:      # Whitelist (empty = all allowed)
      - "api.github.com"
      - "pypi.org"

  processes:
    max_processes: 10   # Max child processes
    can_fork: true      # Allow process forking

# Build Configuration
build:
  python_version: "3.11"
  system_packages:      # apt packages to install
    - "libpq-dev"
    - "python3-dev"
    - "libjpeg-dev"

  before_install:       # Commands before pip install
    - "apt-get update"

  after_install:        # Commands after pip install
    - "python manage.py collectstatic --noinput"

# Runtime Configuration
runtime:
  command: "gunicorn config.wsgi:application"
  workers: 4
  threads: 2
  timeout: 30

  environment:
    DJANGO_SETTINGS_MODULE: "config.settings"
    PYTHONUNBUFFERED: "1"

  health_check:
    enabled: true
    path: "/health/"
    interval: 30        # seconds
    timeout: 5
    retries: 3

# Deployment Hooks
hooks:
  before_deploy:
    - "python manage.py check --deploy"

  after_deploy:
    - "python manage.py migrate --noinput"
    - "python manage.py createsuperuser --noinput || true"

  before_rollback:
    - "python manage.py dumpdata > backup.json"

# Monitoring & Alerts
monitoring:
  enabled: true
  metrics:
    - "cpu"
    - "memory"
    - "disk"
    - "http_requests"

  alerts:
    memory_threshold: "80%"
    disk_threshold: "90%"
    error_rate: "5%"

# Backup Configuration
backup:
  enabled: true
  database: true
  media: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  retention: 7           # Keep 7 days
```

### JSON Example

```json
{
  "version": "1.0",
  "name": "my-django-app",
  "type": "django",
  "resources": {
    "memory": "512M",
    "cpu": "0.5",
    "disk": "2G"
  },
  "services": {
    "database": {
      "enabled": true,
      "type": "postgresql"
    }
  },
  "network": {
    "http_port": true,
    "https": true
  }
}
```

## Auto-Detection (No Contract File)

If no contract file is present, WebOps will:

1. **Detect Django apps:**
   - Look for `manage.py` and `wsgi.py`
   - Apply Django defaults

2. **Detect Node.js apps:**
   - Look for `package.json`
   - Apply Node.js defaults

3. **Detect static sites:**
   - Look for `index.html`
   - Serve with Nginx only

4. **Default resource limits:**
   - Memory: 256M
   - CPU: 0.25
   - Disk: 1G

## Contract Validation

WebOps validates contracts during deployment:

```python
# apps/deployments/contract.py
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import json
from pydantic import BaseModel, Field, validator

class ResourceLimits(BaseModel):
    memory: str = "256M"
    cpu: str = "0.25"
    disk: str = "1G"

    @validator('memory', 'disk')
    def validate_size(cls, v):
        # Parse and validate size strings
        units = {'M': 1024**2, 'G': 1024**3}
        if v[-1] not in units:
            raise ValueError("Size must end with M or G")
        return v

class DatabaseService(BaseModel):
    enabled: bool = False
    type: str = "postgresql"
    version: Optional[str] = None

class Services(BaseModel):
    database: Optional[DatabaseService] = None
    cache: Optional[dict] = None
    storage: Optional[dict] = None
    background_tasks: Optional[dict] = None

class Network(BaseModel):
    http_port: bool = True
    https: bool = False
    websockets: bool = False

class Permissions(BaseModel):
    filesystem: Optional[dict] = None
    network: Optional[dict] = None
    processes: Optional[dict] = None

class AppContract(BaseModel):
    version: str = "1.0"
    name: str
    type: str = "django"
    resources: ResourceLimits = Field(default_factory=ResourceLimits)
    services: Services = Field(default_factory=Services)
    network: Network = Field(default_factory=Network)
    permissions: Optional[Permissions] = None
    build: Optional[dict] = None
    runtime: Optional[dict] = None
    hooks: Optional[dict] = None
    monitoring: Optional[dict] = None
    backup: Optional[dict] = None

    @validator('type')
    def validate_type(cls, v):
        allowed = ['django', 'static', 'nodejs', 'docker']
        if v not in allowed:
            raise ValueError(f"Type must be one of {allowed}")
        return v
```

## Security Enforcement

WebOps enforces contract permissions using:

1. **systemd service isolation**
2. **Linux namespaces**
3. **cgroups for resource limits**
4. **AppArmor/SELinux profiles**
5. **Network policies (iptables)**

Example systemd service with contract enforcement:

```ini
[Unit]
Description=WebOps - my-django-app
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=webops-my-django-app
Group=webops
WorkingDirectory=/opt/webops/deployments/my-django-app

# Resource Limits (from contract)
MemoryMax=512M
MemoryHigh=400M
CPUQuota=50%
TasksMax=20

# Security Restrictions
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/webops/deployments/my-django-app
ReadOnlyPaths=/opt/webops/shared

# Network
RestrictAddressFamilies=AF_INET AF_INET6
IPAddressAllow=0.0.0.0/0
IPAddressDeny=10.0.0.0/8 172.16.0.0/12 192.168.0.0/16  # Block internal networks

# Filesystem
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true

# Execution
ExecStart=/opt/webops/deployments/my-django-app/venv/bin/gunicorn config.wsgi:application --workers 4
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Resource Quotas

Disk quotas enforced per deployment:

```bash
#!/bin/bash
# Set disk quota for deployment

APP_NAME=$1
QUOTA_GB=$2

# Create quota group
groupadd -r webops-quota-$APP_NAME

# Set quota (requires filesystem with quota support)
setquota -g webops-quota-$APP_NAME ${QUOTA_GB}G ${QUOTA_GB}G 0 0 /dev/vda1

# Add app user to quota group
usermod -a -G webops-quota-$APP_NAME webops-$APP_NAME
```

## Usage Examples

### Minimal Django App

```yaml
version: "1.0"
name: "blog"
type: "django"
services:
  database:
    enabled: true
network:
  https: true
```

### High-Performance Django API

```yaml
version: "1.0"
name: "api"
type: "django"

resources:
  memory: "2G"
  cpu: "2.0"
  disk: "10G"

services:
  database:
    enabled: true
    type: "postgresql"
    version: "15"
  cache:
    enabled: true
    type: "redis"
  background_tasks:
    enabled: true
    type: "celery"
    workers: 4
    beat: true

runtime:
  workers: 8
  threads: 4
  timeout: 60

monitoring:
  enabled: true
  alerts:
    memory_threshold: "85%"
    error_rate: "3%"
```

### Static Site

```yaml
version: "1.0"
name: "portfolio"
type: "static"

resources:
  memory: "128M"
  cpu: "0.1"
  disk: "500M"

network:
  https: true

build:
  before_install:
    - "npm install"
    - "npm run build"
```

## Benefits

1. **Security:** Explicit permissions prevent privilege escalation
2. **Resource Management:** Prevent one app from consuming all resources
3. **Automation:** WebOps knows exactly what to provision
4. **Documentation:** Contract serves as deployment documentation
5. **Validation:** Catch configuration errors before deployment
6. **Isolation:** Apps can't interfere with each other
7. **Scalability:** Easy to identify resource-hungry apps

## Contract Enforcement Flow

```
1. User pushes code with webops.yml
2. WebOps reads and validates contract
3. Check if requested resources available
4. Create isolated user for app
5. Provision requested services (DB, Redis, etc.)
6. Generate systemd service with limits
7. Configure network access rules
8. Set filesystem permissions
9. Deploy app within constraints
10. Monitor compliance with contract
```

## Future Enhancements

- Container support with contracts
- Multi-region deployments
- Auto-scaling based on resource usage
- Cost estimation from contract
- Contract versioning and migrations
