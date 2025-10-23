# WebOps Project Guide for AI Agents

## Project Overview 

WebOps is a self-hosted VPS hosting platform for deploying and managing web applications. It provides a Django-based control panel that orchestrates application deployments, manages PostgreSQL databases, handles SSL certificates, and monitors system health. The platform supports Django applications, static sites, and LLM models (via vLLM).

**Key Philosophy**: Minimal dependencies, security-first design, pure HTML/CSS/JS frontend (zero npm), and automated infrastructure management.

### Key Components

1. **Django Control Panel** (`control-panel/`)
   - REST API and web UI for managing deployments
   - Background task processing via Celery
   - WebSocket support via Django Channels for real-time logs
   - Pure vanilla JavaScript frontend (no build tools)

2. **WebOps CLI** (`cli/`)
   - Command-line interface for system administration
   - Interactive wizards for deployment and troubleshooting
   - Security audit and validation tools
   - System template management for various deployment types

3. **Deployment Service** (`apps.deployments.services.DeploymentService`)
   - Orchestrates Git cloning, dependency installation, and service setup
   - Creates systemd services for each deployment
   - Configures Nginx reverse proxies and SSL certificates

4. **Service Manager** (`apps.deployments.service_manager.ServiceManager`)
   - Manages systemd service lifecycle (start/stop/restart)
   - Configures Nginx virtual hosts
   - Handles port allocation (MIN_PORT to MAX_PORT range)

5. **LLM Service** (`apps.deployments.llm_service.LLMDeploymentService`)
   - Deploys vLLM models from Hugging Face
   - Manages GPU allocation and model quantization
   - Creates OpenAI-compatible API endpoints

6. **Automation System** (`apps.automation/`)
   - Workflow management for complex deployment scenarios
   - Node-based execution engine for multi-step processes
   - Template system for reusable automation patterns

7. **Addons System** (`apps.addons/`)
   - Extensible hook-based plugin architecture
   - Supports `pre_deployment`, `post_deployment`, `service_health_check`, etc.
   - Auto-discovery from `ADDONS_PATH` directory
   - Priority-based execution with retry logic and timeouts

### Architecture

- **Backend**: Django framework with PostgreSQL database
- **Frontend**: Modern HTML5, CSS3, JavaScript with custom theming system (no build tools)
- **CLI**: Python-based command-line interface with interactive wizards
- **Task Queue**: Celery for background job processing
- **API**: RESTful API with WebSocket support for real-time updates
- **Authentication**: Token-based authentication with role-based access control

## Agent Guidelines

### Core Principles

1. **Always use the latest version of the control panel**
2. **No frontend dependencies other than the control panel** - Avoid introducing external JavaScript libraries or frameworks
3. **Always refer to `/home/douglas/webops/control-panel/static/css/variables.css` and `/home/douglas/webops/control-panel/static/css/main.css` whenever styling the control panel**
4. **Always focus on ultra sleek design for our views** - Clean, modern, and intuitive interfaces
5. **Frontends must always align with backend API** - Ensure consistency between frontend and backend
6. **Assume our server is always up and running on port 8009**
7. **Always focus on Best Practices** - Follow industry standards and conventions
8. **Component identity should be clear from the name** - Use descriptive naming conventions

### Project Information

- **Developer**: Douglas Mutethia
- **GitHub Repository**: https://github.com/dagiim/webops
- **Company**: Eleso Solutions

## Development Setup

### Quick Start (Development MVP)

```bash
cd control-panel
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
./quickstart.sh
python manage.py runserver
```

Access at http://127.0.0.1:8000 (default credentials: `admin` / `admin123`)

### CLI Development Setup

```bash
cd cli
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
webops --help
```

### Running Tests

```bash
# From control-panel directory
python manage.py test                    # All tests
python manage.py test apps.deployments   # Specific app
python run_tests.py                      # Custom test runner with coverage

# From CLI directory
python -m pytest tests/                  # CLI tests
```

### Starting Celery Workers

Celery is required for background deployment tasks:

```bash
cd control-panel
./start_celery.sh  # Starts worker and beat scheduler
```

Or manually:
```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info  # For scheduled tasks
```

## Application Structure

```
webops/
├── cli/                              # Command-line interface
│   ├── webops_cli/                   # Main CLI package
│   │   ├── cli.py                    # Main CLI entry point
│   │   ├── api.py                    # API client for control panel
│   │   ├── config.py                 # Configuration management
│   │   ├── system.py                 # System utilities
│   │   ├── security_logging.py       # Security audit logging
│   │   ├── ui/                       # Interactive UI components
│   │   ├── wizards/                  # Interactive wizards
│   │   ├── scripts/                  # Utility scripts
│   │   └── system-templates/         # Systemd/Nginx templates
│   ├── tests/                        # CLI test suite
│   └── setup.py                      # Package setup
│
└── control-panel/                    # Django web application
    ├── apps/
    │   ├── core/                     # Base models, auth, security
    │   │   ├── auth/                 # Authentication system
    │   │   ├── branding/             # Customization features
    │   │   ├── common/               # Shared utilities
    │   │   ├── integrations/         # Third-party integrations
    │   │   ├── notifications/        # Notification system
    │   │   ├── security/             # Security middleware
    │   │   ├── services/             # Core business logic
    │   │   └── webhooks/             # Webhook handling
    │   ├── deployments/              # Deployment management
    │   │   ├── api/                  # REST API endpoints
    │   │   ├── services/             # Deployment services
    │   │   ├── tasks/                # Background tasks
    │   │   ├── models/               # Data models
    │   │   ├── views/                # Web views
    │   │   ├── forms/                # Form definitions
    │   │   └── shared/               # Shared components
    │   ├── databases/                # Database management
    │   │   ├── adapters/             # Database adapters
    │   │   └── migrations/           # Schema migrations
    │   ├── services/                 # Service monitoring
    │   │   ├── background/           # Background task adapters
    │   │   └── monitoring.py         # Service monitoring
    │   ├── api/                      # API framework
    │   │   ├── authentication.py     # API authentication
    │   │   ├── rate_limiting.py      # Rate limiting
    │   │   └── docs/                 # API documentation
    │   ├── automation/               # Workflow automation
    │   │   ├── node_executors.py     # Workflow node executors
    │   │   ├── tasks.py              # Automation tasks
    │   │   └── validators.py         # Workflow validators
    │   └── addons/                   # Plugin system
    │       ├── manager.py            # Addon manager
    │       └── registry.py           # Hook registry
    ├── config/                       # Django configuration
    ├── static/                       # Static assets
    ├── templates/                    # Django templates
    ├── media/                        # User uploads
    └── system-templates/             # System templates
```

## Key Workflows

### Deployment Flow

1. User creates deployment via web UI, API, or CLI
2. `deploy_application` Celery task triggered
3. `DeploymentService.deploy()` executes:
   - Allocates port from available range
   - Clones Git repository
   - Creates virtual environment
   - Installs dependencies
   - Runs migrations (Django) or builds assets
   - Creates systemd service from template
   - Configures Nginx reverse proxy
   - Starts service via `ServiceManager`
4. Deployment status updates logged to `DeploymentLog`
5. Health checks monitor service availability

### CLI Workflow

1. User runs `webops deploy` command
2. CLI wizard collects deployment information
3. CLI sends deployment request to control panel API
4. Control panel processes deployment via background tasks
5. CLI monitors deployment progress and displays results
6. User can manage deployments via CLI commands

### Automation Workflow

1. User creates workflow template via web UI
2. Workflow consists of connected nodes with specific functions
3. Each node has input/output parameters and execution logic
4. Workflow can be triggered manually or by events
5. Automation engine executes nodes in sequence with error handling
6. Results are logged and can trigger notifications

### Addon Hook Execution

Addons are discovered at startup from the `ADDONS_PATH` directory. Each addon can register hooks:

```python
# Example addon structure
addons/
└── my_addon/
    ├── addon.json       # Metadata
    └── hooks.py         # Hook implementations

# hooks.py
from apps.addons.registry import hook_registry

@hook_registry.register('pre_deployment', priority=50)
def my_hook(context):
    deployment_name = context['deployment_name']
    # Custom logic here
```

## Best Practices

### Code Quality

1. **Follow PEP 8** for Python code formatting
2. **Use meaningful variable and function names** that clearly indicate purpose
3. **Write self-documenting code** with clear logic flow
4. **Add appropriate comments** for complex business logic
5. **Keep functions focused** on a single responsibility
6. **DRY principle** - Don't Repeat Yourself
7. **Use type hints** for all function signatures and variables

### Frontend Development

1. **Use semantic HTML5** elements appropriately
2. **Follow BEM methodology** for CSS class naming when applicable
3. **Implement responsive design** using the existing CSS framework
4. **Ensure accessibility** with proper ARIA labels and keyboard navigation
5. **Optimize for performance** with efficient DOM manipulation
6. **Test across different screen sizes** and devices
7. **Zero build tools** - Pure HTML, CSS, and vanilla JavaScript only

### CLI Development

1. **Use Click framework** for command-line interfaces
2. **Implement interactive wizards** with clear prompts
3. **Provide helpful error messages** and suggestions
4. **Support configuration files** for common settings
5. **Include progress indicators** for long-running operations
6. **Implement proper logging** for debugging
7. **Follow CLI conventions** for command structure and options

### Backend Development

1. **Follow Django best practices** and conventions
2. **Use Django's built-in security features** (CSRF protection, XSS prevention, etc.)
3. **Implement proper error handling** with meaningful error messages
4. **Use Django ORM efficiently** with proper query optimization
5. **Implement proper logging** for debugging and monitoring
6. **Validate all user inputs** on both client and server side
7. **Use environment variables** for configuration with `python-decouple`

### Database Operations

1. **Use Django migrations** for all schema changes
2. **Optimize database queries** to avoid N+1 problems
3. **Use appropriate field types** and constraints
4. **Implement proper indexing** for frequently queried fields
5. **Handle database transactions** properly for data integrity

### API Development

1. **Follow RESTful principles** for API design
2. **Use appropriate HTTP methods** (GET, POST, PUT, DELETE)
3. **Implement proper status codes** for different responses
4. **Version APIs** when making breaking changes
5. **Document API endpoints** with clear examples
6. **Implement rate limiting** for public APIs

### Security

1. **Never expose sensitive data** in logs or error messages
2. **Use environment variables** for configuration secrets
3. **Implement proper authentication** and authorization
4. **Validate and sanitize all user inputs**
5. **Use HTTPS** for all communications
6. **Follow the principle of least privilege**
7. **Encrypt sensitive data** at rest using Fernet encryption

### Testing

1. **Write comprehensive tests** for new features
2. **Test edge cases** and error conditions
3. **Use descriptive test names** that explain what is being tested
4. **Maintain test coverage** above 80%
5. **Use fixtures** for consistent test data
6. **Test both positive and negative scenarios**
7. **Mock external services** (Git, systemd, Nginx) in unit tests

### Documentation

1. **Document complex business logic** with clear explanations
2. **Update API documentation** when making changes
3. **Include code examples** in documentation
4. **Maintain README files** for each major component
5. **Document configuration options** with examples

## Important Patterns

### Environment Variables

All configuration via environment variables (loaded by `python-decouple`):

```python
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='')
```

### Encryption

Sensitive data (tokens, passwords) encrypted using Fernet:

```python
from apps.core.utils.encryption import encrypt_value, decrypt_value

encrypted = encrypt_value("secret_token", settings.ENCRYPTION_KEY)
decrypted = decrypt_value(encrypted, settings.ENCRYPTION_KEY)
```

### Background Tasks

Long-running operations use Celery tasks:

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def my_task(self, deployment_id: int):
    try:
        # Task logic
        return {'success': True}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

### Service Management

All deployments run as systemd services created from templates:

```python
from apps.deployments.service_manager import ServiceManager

manager = ServiceManager()
manager.create_service(deployment)    # Creates systemd unit file
manager.start_service(deployment)     # systemctl start <service>
manager.enable_service(deployment)    # systemctl enable <service>
```

### CLI Command Structure

CLI commands follow Click framework patterns:

```python
import click

@click.group()
def cli():
    """WebOps CLI - Manage your deployments from the command line."""
    pass

@cli.command()
@click.option('--name', required=True, help='Deployment name')
@click.option('--repo', required=True, help='Git repository URL')
def deploy(name, repo):
    """Deploy a new application."""
    # Deployment logic here
    pass
```

## Common Commands

### Control Panel Commands

```bash
# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --no-input

# Run Celery worker
celery -A config worker --loglevel=info

# Run Celery beat (scheduled tasks)
celery -A config beat --loglevel=info

# Run tests with coverage
coverage run --source='.' manage.py test
coverage report

# Initialize WebOps directories
python manage.py init_webops_dirs

# Generate .env file
python manage.py generate_env

# Test Celery connectivity
python manage.py test_celery
```

### CLI Commands

```bash
# Install CLI in development mode
cd cli && pip install -e .

# List all deployments
webops list

# Deploy a new application
webops deploy --name myapp --repo https://github.com/user/repo.git

# Get deployment status
webops status myapp

# View deployment logs
webops logs myapp

# Stop a deployment
webops stop myapp

# Start a deployment
webops start myapp

# Run security audit
webops security audit

# Validate system setup
webops system validate

# Interactive deployment wizard
webops wizard deploy

# Interactive troubleshooting wizard
webops wizard troubleshoot
```

## Security Architecture

### The `webops` System User

Production deployments run as dedicated `webops` user (not root):
- Limited sudo access to specific commands (nginx, systemd, certbot)
- All sudo commands logged to `/var/log/auth.log`
- Validation script: `./scripts/validate-user-setup.sh`
- Security audit: `./scripts/webops-security-check.sh`

### Security Features

- CSRF protection on all forms
- Rate limiting via `RateLimitMiddleware`
- API token authentication (`apps.api.authentication.APITokenAuthentication`)
- Encrypted credentials at rest (Fernet symmetric encryption)
- SSL/TLS certificates via Let's Encrypt
- Security audit logs for all sensitive operations
- CLI security audit tools for system validation
- Template-based security scanning for deployments

## Troubleshooting

### Celery not processing tasks
- Verify Redis is running: `redis-cli ping`
- Check worker status: `ps aux | grep celery`
- Review logs: `tail -f control-panel/logs/webops.log`

### Deployment fails
- Check deployment logs in web UI, CLI, or database
- Verify systemd service: `systemctl status <deployment-name>`
- Check Nginx config: `nginx -t`
- Run CLI troubleshooting wizard: `webops wizard troubleshoot`

### Port conflicts
- WebOps allocates ports from `MIN_PORT` to `MAX_PORT` range
- Check allocated ports: `Deployment.objects.values_list('port', flat=True)`

### CLI Issues
- Verify API connectivity: `webops system check`
- Check configuration: `webops config show`
- Run security audit: `webops security audit`

## External Dependencies

### Control Panel Dependencies
- **PostgreSQL**: Primary database (SQLite for development)
- **Redis**: Celery broker and Channels layer
- **Nginx**: Reverse proxy and static file serving
- **systemd**: Process management for deployments
- **Git**: Repository cloning
- **Certbot**: Let's Encrypt SSL certificates (production)

### CLI Dependencies
- **Click**: Command-line interface framework
- **Requests**: HTTP client for API communication
- **Rich**: Terminal formatting and interactive widgets
- **PyYAML**: Configuration file parsing
- **Jinja2**: Template rendering for system templates

## Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)
- [Python Style Guide (PEP 8)](https://pep8.org/)
- [Click Documentation](https://click.palletsprojects.com/)
- [MDN Web Docs](https://developer.mozilla.org/)