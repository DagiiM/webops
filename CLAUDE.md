# CLAUDE.md - WebOps Development Guide

## Project Overview

**WebOps** is a minimal, self-hosted VPS hosting platform for deploying and managing web applications. This guide is specifically for Claude Code agent to understand the project structure, conventions, and development workflows.

## Core Principles

1. **Minimal Dependencies**: Zero npm/Node.js dependencies. Pure HTML5/CSS3/vanilla JavaScript only.
2. **One-Command Setup**: Everything orchestrated through `setup.sh`
3. **Battle-Tested Stack**: Django, PostgreSQL, Nginx, Celery, Redis, systemd
4. **Self-Contained**: No external services or APIs required
5. **Security First**: Encrypted credentials, isolated processes, minimal attack surface

## Project Structure

```
webops/
├── setup.sh                    # Main orchestration script (Bash)
├── control-panel/              # Django application
│   ├── manage.py
│   ├── config/                 # Django project settings
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── apps/
│   │   ├── core/               # Shared utilities, base models
│   │   ├── deployments/        # Deployment management
│   │   ├── databases/          # Database credential management
│   │   └── services/           # Service monitoring
│   ├── templates/              # Django templates (minimal HTML)
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── deployments/
│   │   └── databases/
│   ├── static/
│   │   ├── css/
│   │   │   └── main.css       # Single CSS file
│   │   └── js/
│   │       └── main.js        # Single vanilla JS file
│   ├── celery_app.py          # Celery configuration
│   └── requirements.txt
├── cli/                        # CLI tool (Python)
│   ├── webops_cli/
│   │   ├── __init__.py
│   │   ├── commands.py        # Click/Typer commands
│   │   ├── api.py             # API client
│   │   └── config.py          # Config management
│   ├── setup.py
│   └── requirements.txt
├── templates/                  # System-level templates
│   ├── nginx/
│   │   ├── webops-panel.conf  # Nginx config for control panel
│   │   └── app.conf.j2        # Jinja2 template for user apps
│   ├── systemd/
│   │   ├── webops-web.service
│   │   ├── webops-celery.service
│   │   ├── webops-celerybeat.service
│   │   └── app.service.j2     # Template for user app services
│   └── env.j2                 # Environment file template
├── scripts/
│   ├── backup.sh              # Database backup script
│   ├── update.sh              # Self-update script
│   └── helpers.sh             # Shared functions
├── docs/
│   ├── installation.md
│   ├── deployment-guide.md
│   ├── api-reference.md
│   └── troubleshooting.md
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── .env.example
├── .gitignore
├── README.md
├── LICENSE
└── CLAUDE.md                   # This file
```

## Technology Stack

### Backend
- **Python**: 3.11+ (type hints required)
- **Django**: 5.x (latest stable)
- **Celery**: 5.x with Redis broker
- **PostgreSQL**: 15+ (via psycopg2-binary)
- **Gunicorn**: WSGI server

### Frontend
- **HTML5**: Semantic markup
- **CSS3**: Custom styles, CSS Grid, Flexbox (NO frameworks like Tailwind/Bootstrap)
- **JavaScript**: Vanilla ES6+ only (NO frameworks, NO build tools)

### Infrastructure
- **Nginx**: Reverse proxy and static file serving
- **Redis**: Message broker for Celery
- **systemd**: Process management
- **Certbot**: SSL certificate management

### Deployment Target
- **OS**: Ubuntu 22.04 LTS (primary), Debian 11+ (secondary)
- **Requirements**: 2GB RAM minimum, 2 CPU cores

## Development Conventions

### Python Code Style
- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Import order: stdlib, third-party, local (separated by blank lines)

Example:
```python
from typing import Optional, Dict, Any
from pathlib import Path

from django.db import models
from celery import shared_task

from apps.core.models import BaseModel


def deploy_application(
    repo_url: str,
    branch: str = "main",
    env_vars: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Deploy application from GitHub repository.
    
    Args:
        repo_url: GitHub repository URL
        branch: Git branch to deploy
        env_vars: Environment variables for the application
        
    Returns:
        Deployment result with status and metadata
    """
    if env_vars is None:
        env_vars = {}
    
    # Implementation here
    return {"status": "success", "deployment_id": "abc123"}
```

### Django App Structure
Each Django app should follow this structure:
```
app_name/
├── __init__.py
├── admin.py           # Django admin configuration
├── apps.py            # App configuration
├── models.py          # Database models
├── views.py           # View functions/classes
├── urls.py            # URL routing
├── forms.py           # Django forms (if needed)
├── tasks.py           # Celery tasks
├── services.py        # Business logic (NOT in views)
├── utils.py           # Helper functions
├── tests.py           # Unit tests
└── migrations/        # Database migrations
```

### Frontend Code Style

#### HTML
- Use semantic HTML5 elements
- Include proper meta tags
- All forms must have CSRF tokens: `{% csrf_token %}`
- Progressive enhancement: works without JS

Example:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}WebOps{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/main.css' %}">
</head>
<body>
    <nav class="navbar">
        <!-- Navigation -->
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    <script src="{% static 'js/main.js' %}" defer></script>
</body>
</html>
```

#### CSS
- Use CSS custom properties for theming
- Mobile-first responsive design
- BEM-like naming convention
- No preprocessors (pure CSS only)

Example:
```css
:root {
    --color-primary: #3b82f6;
    --color-danger: #ef4444;
    --spacing-unit: 8px;
    --border-radius: 4px;
}

.deployment-card {
    padding: calc(var(--spacing-unit) * 2);
    border-radius: var(--border-radius);
    background: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.deployment-card__title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: var(--spacing-unit);
}

.deployment-card__status--running {
    color: var(--webops-color-success);
}
```

#### JavaScript
- Use ES6+ features (const/let, arrow functions, async/await)
- No build step required
- Use fetch API for AJAX requests
- Include CSRF token in all POST requests

Example:
```javascript
// main.js
'use strict';

class DeploymentManager {
    constructor() {
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    async deployApp(formData) {
        try {
            const response = await fetch('/api/deployments/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Deployment failed:', error);
            throw error;
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const manager = new DeploymentManager();
    // Event listeners here
});
```

### Bash Script Style (setup.sh)
- Use `#!/bin/bash` shebang
- Enable strict mode: `set -euo pipefail`
- Use functions for organization
- Include error handling and logging
- Idempotent operations (safe to run multiple times)

Example:
```bash
#!/bin/bash
set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_requirements() {
    log_info "Checking system requirements..."
    
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    if ! command -v apt-get &> /dev/null; then
        log_error "This script requires apt-get (Ubuntu/Debian)"
        exit 1
    fi
}

main() {
    log_info "Starting WebOps installation..."
    check_requirements
    # More setup steps
}

main "$@"
```

## Database Models

### Base Model
All models should inherit from a base model with common fields:

```python
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """Abstract base model with common fields."""
    
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
```

### Example Models

```python
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import BaseModel


class Deployment(BaseModel):
    """Represents a deployed application."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        BUILDING = 'building', 'Building'
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        FAILED = 'failed', 'Failed'
    
    name = models.CharField(max_length=100, unique=True)
    repo_url = models.URLField()
    branch = models.CharField(max_length=100, default='main')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    port = models.IntegerField(unique=True)
    domain = models.CharField(max_length=255, blank=True)
    env_vars = models.JSONField(default=dict)
    deployed_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self) -> str:
        return f"{self.name} ({self.status})"
    
    class Meta:
        db_table = 'deployments'
        verbose_name = 'Deployment'
        verbose_name_plural = 'Deployments'


class Database(BaseModel):
    """PostgreSQL database credentials."""
    
    name = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)  # Encrypted
    host = models.CharField(max_length=255, default='localhost')
    port = models.IntegerField(default=5432)
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='databases'
    )
    
    def __str__(self) -> str:
        return self.name
    
    class Meta:
        db_table = 'databases'
```

## Celery Tasks

### Task Structure
All Celery tasks should be in `tasks.py` within each app:

```python
from typing import Dict, Any
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def deploy_django_app(
    self,
    deployment_id: int,
    repo_url: str,
    branch: str
) -> Dict[str, Any]:
    """Deploy Django application from GitHub.
    
    Args:
        deployment_id: Database ID of deployment
        repo_url: GitHub repository URL
        branch: Git branch to deploy
        
    Returns:
        Dictionary with deployment status and logs
    """
    from apps.deployments.services import DeploymentService
    
    try:
        logger.info(f"Starting deployment {deployment_id}")
        
        service = DeploymentService()
        result = service.deploy(
            deployment_id=deployment_id,
            repo_url=repo_url,
            branch=branch
        )
        
        logger.info(f"Deployment {deployment_id} completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Deployment {deployment_id} failed: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

## API Design

### REST API Endpoints
Use Django REST Framework (DRF) or simple Django views with JSON responses:

```python
from typing import Dict, Any
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from apps.deployments.models import Deployment
from apps.deployments.tasks import deploy_django_app


@login_required
@require_http_methods(["POST"])
def create_deployment(request) -> JsonResponse:
    """Create new deployment from GitHub repository."""
    import json
    
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['name', 'repo_url']
        if not all(field in data for field in required_fields):
            return JsonResponse(
                {'error': 'Missing required fields'},
                status=400
            )
        
        # Create deployment
        deployment = Deployment.objects.create(
            name=data['name'],
            repo_url=data['repo_url'],
            branch=data.get('branch', 'main'),
            deployed_by=request.user,
            status=Deployment.Status.PENDING
        )
        
        # Queue deployment task
        deploy_django_app.delay(
            deployment_id=deployment.id,
            repo_url=deployment.repo_url,
            branch=deployment.branch
        )
        
        return JsonResponse({
            'id': deployment.id,
            'name': deployment.name,
            'status': deployment.status,
            'message': 'Deployment queued successfully'
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
```

## File System Layout

WebOps creates this structure on the VPS:

```
$WEBOPS_DIR/
├── control-panel/              # WebOps control panel
│   ├── venv/                   # Python virtual environment
│   ├── static/                 # Collected static files
│   ├── media/                  # Uploaded files
│   └── logs/                   # Application logs
├── deployments/                # User applications
│   ├── app1/
│   │   ├── venv/
│   │   ├── repo/               # Git repository
│   │   ├── .env                # Environment variables
│   │   └── logs/
│   └── app2/
├── backups/                    # Database backups
│   ├── postgres/
│   └── control-panel/
└── tmp/                        # Temporary files

/etc/nginx/
├── sites-available/
│   ├── webops-panel.conf
│   ├── app1.conf
│   └── app2.conf
└── sites-enabled/              # Symlinks

/etc/systemd/system/
├── webops-web.service
├── webops-celery.service
├── webops-celerybeat.service
├── app1.service
└── app2.service
```

## Security Best Practices

### Credential Management
1. Store database passwords encrypted using Django's encryption utilities
2. Generate secure random passwords using `secrets` module
3. Never log credentials
4. Use environment variables for sensitive config

```python
import secrets
import string
from django.conf import settings
from cryptography.fernet import Fernet


def generate_password(length: int = 32) -> str:
    """Generate cryptographically secure password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def encrypt_password(password: str) -> str:
    """Encrypt password for storage."""
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted: str) -> str:
    """Decrypt password from storage."""
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    return fernet.decrypt(encrypted.encode()).decode()
```

### GitHub Access
- Support both public and private repositories
- Use deploy keys for private repos
- Support personal access tokens
- Never store tokens in plain text

## Testing

### Unit Tests
```python
from django.test import TestCase
from apps.deployments.models import Deployment
from apps.deployments.services import DeploymentService


class DeploymentServiceTest(TestCase):
    def setUp(self):
        self.service = DeploymentService()
        self.deployment = Deployment.objects.create(
            name='test-app',
            repo_url='https://github.com/user/repo',
            branch='main'
        )
    
    def test_validate_repo_url(self):
        """Test repository URL validation."""
        valid_urls = [
            'https://github.com/user/repo',
            'https://github.com/user/repo.git',
        ]
        for url in valid_urls:
            self.assertTrue(self.service.validate_repo_url(url))
    
    def test_generate_port(self):
        """Test port generation for new deployment."""
        port = self.service.generate_port()
        self.assertGreaterEqual(port, 8001)
        self.assertLessEqual(port, 9000)
```

### Integration Tests
Test complete deployment workflows in isolated environment.

## Common Tasks for Claude Code Agent

### 1. Adding a New Feature
1. Create or modify models in appropriate app
2. Create database migration: `python manage.py makemigrations`
3. Add business logic to `services.py`
4. Create/update views in `views.py`
5. Add URL routing in `urls.py`
6. Create templates if needed
7. Add Celery tasks if background processing required
8. Write tests
9. Update documentation

### 2. Creating a New Django App
```bash
cd control-panel
python manage.py startapp app_name
# Move to apps/ directory
mv app_name apps/
# Update apps/app_name/apps.py name to 'apps.app_name'
# Add to INSTALLED_APPS in config/settings.py
```

### 3. Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.deployments

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### 5. Deployment Workflow Implementation
Key files to modify:
- `apps/deployments/services.py` - Core deployment logic
- `apps/deployments/tasks.py` - Celery background tasks
- `templates/systemd/app.service.j2` - systemd service template
- `templates/nginx/app.conf.j2` - Nginx configuration template

## Environment Variables

### Control Panel (.env)
```bash
# Django settings
SECRET_KEY=generated-secret-key
DEBUG=False
ALLOWED_HOSTS=webops.yourdomain.com,192.168.1.100

# Database
DATABASE_URL=postgresql://webops:password@localhost:5432/webops_db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
ENCRYPTION_KEY=generated-fernet-key

# GitHub
GITHUB_TOKEN=ghp_optional_for_private_repos
```

## Logging

### Log Configuration
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{os.environ.get("WEBOPS_DIR", "/opt/webops")}/control-panel/logs/webops.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

## Common Pitfalls to Avoid

1. **Don't use npm or any JavaScript build tools** - Everything must be vanilla JS
2. **Don't use CSS frameworks** - Write custom CSS
3. **Don't store credentials in plain text** - Always encrypt
4. **Don't run as root** - Use dedicated `hosting` user
5. **Don't skip CSRF protection** - Include tokens in all forms
6. **Don't hardcode paths** - Use Django's `settings` and `Path`
7. **Don't ignore error handling** - Always handle exceptions
8. **Don't skip input validation** - Validate all user input
9. **Don't forget migrations** - Run makemigrations after model changes
10. **Don't skip tests** - Write tests for all new features

## Questions? Check These First

1. **Django documentation**: https://docs.djangoproject.com/
2. **Celery documentation**: https://docs.celeryq.dev/
3. **Nginx documentation**: https://nginx.org/en/docs/
4. **PostgreSQL documentation**: https://www.postgresql.org/docs/

## Development Workflow

1. **Understand the requirement** - Read the issue/feature request carefully
2. **Plan the implementation** - Identify affected files and components
3. **Write the code** - Follow conventions in this document
4. **Test locally** - Ensure it works in development environment
5. **Write tests** - Add unit and integration tests
6. **Update documentation** - Update relevant .md files
7. **Review changes** - Ensure code quality and security

---

**Remember**: WebOps is about simplicity, security, and reliability. Every line of code should serve a clear purpose. When in doubt, choose the simpler solution.