# WebOps

> A minimal, self-hosted VPS hosting platform for deploying and managing web applications

WebOps is a lightweight, security-first hosting platform that transforms a fresh VPS into a fully-functional web application deployment system. Deploy Django applications, static sites, and LLM models through a modern Django web interface or feature-rich CLI with interactive wizards.

## Features

- **Security-First Design** - Minimal dependencies, encrypted credentials, isolated processes
- **Pure Frontend** - Zero npm dependencies, pure HTML/CSS/JS frontend
- **PostgreSQL Included** - Automatic database creation per application
- **Background Tasks** - Celery + Redis integration for async operations
- **Built-in Web Server** - Gunicorn with WebSocket support via Daphne
- **Modern Web UI** - Clean Django interface for all operations
- **Feature-Rich CLI** - Interactive wizards, WebSocket monitoring, real-time logs
- **LLM Support** - Deploy vLLM models with GPU allocation
- **Automation System** - Workflow automation with node-based execution
- **Plugin Architecture** - Extensible hook-based addons system

## Use Cases

- Personal project hosting
- Development/staging environments
- Small team deployments
- Learning DevOps practices
- LLM model deployment and hosting
- Alternative to Heroku/Railway/Render for small projects

## Prerequisites

### Production Prerequisites
- Fresh VPS or dedicated server
- Ubuntu 22.04 LTS (or Debian 11+)
- Minimum 2GB RAM, 2 CPU cores
- Root or sudo access
- Domain name (optional, but recommended for SSL)

### Development Prerequisites
Before setting up the development environment, ensure you have:

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip \
    build-essential libpq-dev python3-dev git redis-server
```

**Rocky/AlmaLinux:**
```bash
sudo dnf install -y python3 python3-devel gcc make \
    postgresql-devel git redis
```

**Minimum Requirements:**
- Python 3.11+ (checked during setup)
- 1GB+ free disk space
- Git for version control

**Optional but Recommended:**
- Redis (for Celery background tasks - without it, in-memory processor is used)
- PostgreSQL 14+ (for production-like dev environment - SQLite used by default)

## Quick Start

**IMPORTANT: Two Setup Paths**

WebOps has **TWO distinct setup paths** - choose the one appropriate for your use case:

### 1️⃣ Development Setup (Django Control Panel)

**Use this if:** You're developing/testing WebOps itself or contributing to the project.

**This will:**
- Set up the Django control panel for local development
- Use SQLite database by default
- Run on http://127.0.0.1:8000
- Create admin user with randomly generated password (shown during setup)

#### Option 1: Using Makefile (Recommended)

```bash
# One command to setup everything
make install

# Start development server
make dev
```

Then visit http://127.0.0.1:8000 (admin credentials shown during setup)

See all available commands:
```bash
make help
```

#### Option 2: Using Quickstart Script

```bash
cd control-panel
./quickstart.sh  # Handles venv creation, dependencies, migrations, etc.
./start_dev.sh   # Starts Django + Celery + Beat
```

Then visit http://127.0.0.1:8000 (admin credentials shown during setup)

#### Option 3: Manual Setup

```bash
cd control-panel
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit http://127.0.0.1:8000

### 2️⃣ Production Infrastructure Setup

**Use this if:** You're deploying WebOps as a hosting platform on a VPS.

**This will:**
- Install system-wide infrastructure components
- Set up Nginx, PostgreSQL, Redis, systemd services
- Harden SSH and configure firewall
- Require root/sudo access

**⚠️  WARNING: Do NOT run production installer in development!**

The production installer modifies system SSH configuration, installs system packages, and requires root access. Only use this when deploying to a production VPS.

```bash
# Production installation (requires sudo)
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh

# Or customize installation
cd .webops
cp versions/v1.0.0/config.env.template config.env
# Edit config.env to customize settings
sudo versions/v1.0.0/lifecycle/install.sh
```

See the [Infrastructure Platform](#infrastructure-platform) section below for advanced production setup options.

## Usage

### Via Web Interface

1. **Login** to the WebOps control panel
2. **Navigate** to "Deployments" → "New Deployment"
3. **Fill in** the deployment form:
   - Service name: `my-django-app`
   - Repository URL: `https://github.com/username/django-project`
   - Branch: `main`
   - Domain: `myapp.example.com` (optional)
4. **Click** "Deploy" and monitor progress in real-time
5. **Access** your application at the configured domain

### Via CLI

Install the CLI:
```bash
cd cli
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
webops --help
```

Configure:
```bash
webops config --url https://panel.yourdomain.com --token YOUR_API_TOKEN --role admin
```

Deploy an application:
```bash
webops deploy --repo https://github.com/user/repo --name myapp --domain myapp.com
```

Enhanced CLI features:
```bash
# Interactive deployment wizard
webops deploy-wizard

# Real-time deployment monitoring
webops watch

# Environment management
webops env:generate myapp
webops env:validate myapp
webops env:set myapp DEBUG True

# Project setup and validation
webops project:setup --repo https://github.com/user/repo
webops project:validate myapp

# Interactive management
webops manage
webops interactive-logs myapp
```

## Infrastructure Platform

WebOps includes a comprehensive enterprise infrastructure platform that transforms a fresh VPS into a production-ready hosting environment with enterprise-grade security and high availability features.

### Infrastructure Installation

```bash
# Quick installation (with sudo)
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh

# Or customize installation
cd .webops
cp versions/v1.0.0/config.env.template config.env
# Edit config.env to customize settings
sudo versions/v1.0.0/lifecycle/install.sh

# Add specific infrastructure components
sudo ./.webops/versions/v1.0.0/bin/webops apply postgresql
sudo ./.webops/versions/v1.0.0/bin/webops apply monitoring
sudo ./.webops/versions/v1.0.0/bin/webops apply kubernetes
```

### Infrastructure Addons

- **postgresql**: PostgreSQL 15 database (standalone or HA)
- **etcd**: Distributed key-value store for high availability
- **patroni**: PostgreSQL HA with Patroni + PgBouncer
- **kubernetes**: K3s lightweight Kubernetes distribution
- **kvm**: Hardware virtualization support
- **monitoring**: Prometheus + Grafana + Node Exporter
- **autorecovery**: Automatic service recovery system

### Infrastructure Features

- **System Hardening**: SSH hardening, firewall, kernel tuning, security updates
- **High Availability**: etcd, Patroni, Kubernetes addons for enterprise deployments
- **Monitoring Stack**: Prometheus, Grafana, node exporter for comprehensive monitoring
- **Virtualization**: KVM support for nested deployments
- **Security Contracts**: Cryptographically signed addon contracts for security validation
- **Lifecycle Management**: Install, update, rollback, and repair automation

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 VPS Server                       │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │   WebOps Panel (Gunicorn + Daphne)        │ │
│  │         Django 5.0 Control Panel           │ │
│  └──────┬─────────────────────────────────────┘ │
│         │                                        │
│  ┌──────▼──────────┐    ┌──────────────────┐   │
│  │   PostgreSQL    │    │  User Apps       │   │
│  │   (Database)    │    │  - Django Apps   │   │
│  └─────────────────┘    │  - Static Sites  │   │
│                         │  - LLM Models    │   │
│  ┌─────────────────┐    └──────────────────┘   │
│  │  Redis          │                            │
│  │  (Message Broker)│   ┌──────────────────┐   │
│  └────────┬────────┘    │  Celery Workers  │   │
│           └─────────────►  (Background Jobs)│   │
│                         └──────────────────┘   │
└─────────────────────────────────────────────────┘
```

**WebOps Tech Stack:**
- **Backend**: Django 5.0+, Python 3.11+ with domain-driven architecture
- **Frontend**: Pure HTML5/CSS3/Vanilla JavaScript (zero npm dependencies, no build tools)
- **Database**: PostgreSQL 14+ with encrypted credentials at rest
- **Web Server**: Gunicorn (WSGI) + Daphne (WebSocket/ASGI) - no external web server required
- **Task Queue**: Celery + Redis for background deployment tasks
- **Process Manager**: systemd with security isolation per deployment
- **Security**: Fernet encryption, CSRF protection, rate limiting
- **CLI**: Rich-powered interface with interactive wizards and WebSocket monitoring
- **Authentication**: Token-based with role-based access control
- **WebSocket**: Django Channels + Daphne for real-time log streaming
- **LLM Support**: vLLM integration for AI model deployment

## Project Structure

```
webops/
├── .webops/                          # Enterprise infrastructure platform
│   ├── versions/                     # Version management
│   │   └── v1.0.0/                  # Current platform version
│   │       ├── bin/webops            # Platform CLI (infrastructure management)
│   │       ├── lifecycle/            # Installation lifecycle scripts
│   │       ├── setup/               # Base system setup
│   │       ├── addons/              # Infrastructure addons
│   │       ├── os/                  # OS-specific handlers
│   │       ├── systemd/             # Service templates
│   │       └── contracts/           # Security contracts
│   └── config.env                    # Platform configuration
├── cli/                              # WebOps CLI with enhanced features
│   ├── webops_cli/
│   │   ├── api.py                    # API client for control panel
│   │   ├── config.py                 # Configuration management
│   │   ├── encryption.py             # Credential encryption
│   │   ├── security_logging.py       # Security audit logging
│   │   ├── ui/                       # Interactive UI components
│   │   ├── wizards/                  # Deployment & troubleshooting wizards
│   │   ├── validators.py             # Input validation
│   │   └── system-templates/         # Systemd/Nginx templates
│   ├── tests/                        # CLI test suite with security tests
│   └── setup.py                      # Package setup
├── control-panel/                    # Django control panel
│   ├── apps/
│   │   ├── core/                     # Base models, auth, security
│   │   │   ├── auth/                 # Authentication with 2FA
│   │   │   ├── security/             # Security middleware & audit
│   │   │   ├── services/             # Core business logic
│   │   │   └── integrations/         # GitHub, Hugging Face integrations
│   │   ├── deployments/              # Deployment management
│   │   │   ├── api/                  # REST API endpoints
│   │   │   ├── services/             # Deployment & LLM services
│   │   │   └── tasks/                # Celery background tasks
│   │   ├── databases/                # PostgreSQL management
│   │   ├── services/                 # Monitoring & health checks
│   │   ├── api/                      # API framework with docs
│   │   ├── automation/               # Workflow automation system
│   │   ├── addons/                   # Hook-based plugin system
│   │   ├── compliance/               # Compliance monitoring
│   │   └── trash/                    # Soft delete management
│   ├── templates/                    # Pure HTML templates (no build)
│   └── static/                       # CSS/JS (zero npm, pure vanilla)
└── docs/                             # Comprehensive documentation
```

## Configuration

WebOps uses environment variables for configuration. After installation, edit `control-panel/.env`:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/webops_db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# WebSocket
CHANNEL_LAYERS=redis://localhost:6379/1

# Security
ENCRYPTION_KEY=your-encryption-key
```

## Development Workflow

### Common Development Tasks

WebOps includes a Makefile for streamlined development. See all available commands:

```bash
make help
```

#### Essential Commands

```bash
# Setup and Installation
make install              # Complete development setup
make install-deps         # Install Python dependencies only

# Development Server
make dev                  # Start Django + Celery + Beat
make dev-web              # Start Django only
make dev-worker           # Start Celery worker only

# Testing
make test                 # Run all tests
make test-fast            # Run tests in parallel
make test-app APP=deployments  # Test specific app
make test-coverage        # Generate coverage report

# Code Quality
make lint                 # Run all linters (bash + python)
make lint-bash            # Lint bash scripts only
make format               # Format Python code with black
make type-check           # Run type checking

# Database
make migrate              # Run migrations
make makemigrations       # Create new migrations
make db-reset             # Reset database (with confirmation)
make superuser            # Create Django superuser

# Utilities
make shell                # Django shell
make logs                 # View recent logs
make clean                # Clean caches and artifacts
make info                 # Show environment info
```

#### CI/CD Integration

```bash
make ci                   # Run complete CI pipeline
make pre-commit           # Quick pre-commit checks
```

**For production operations**, use the webops CLI:
```bash
.webops/versions/v1.0.0/bin/webops install
.webops/versions/v1.0.0/bin/webops restore-ssh
```

See `MAKEFILE_STRATEGY.md` for detailed information about the Makefile approach.

## Deploying Applications

### Django Applications

Your Django project should have:
- `requirements.txt` - Python dependencies
- `manage.py` - Django management script
- Proper `ALLOWED_HOSTS` configuration
- Static files configuration

WebOps will automatically:
1. Clone your repository with encrypted token support
2. Create a virtual environment with security isolation
3. Install dependencies with vulnerability scanning
4. Create a PostgreSQL database with unique credentials
5. Run migrations with secure database connections
6. Collect static files with security headers
7. Configure Gunicorn as WSGI server with resource limits
8. Create systemd service with process isolation
9. Start your application with full audit logging
10. (Optional) Configure reverse proxy (Nginx, Caddy, etc.) for SSL termination

### LLM Models & Static Sites

WebOps supports multiple deployment types:
- **Static Sites**: HTML/CSS/JS with automatic optimization
- **Django Applications**: Full-stack with database integration
- **LLM Models**: vLLM-powered models with GPU allocation
- **Custom Applications**: Generic deployment with templates

Each deployment type includes security hardening, automated backups, and monitoring.

## CLI Features

### Enhanced Environment Management
```bash
# Generate environment files from templates
webops env:generate myapp --debug --domain example.com
webops env:generate myapp --set API_KEY=secret123 --set SMTP_HOST=smtp.gmail.com

# Validate environment configuration
webops env:validate myapp

# Show environment variables (with masking)
webops env:show myapp
webops env:show myapp --show-secrets

# Set/unset environment variables
webops env:set myapp DEBUG True --restart
webops env:unset myapp TEMP_KEY --restart
```

### Interactive Wizards
```bash
# Interactive deployment wizard
webops deploy-wizard

# Setup wizard for new installations
webops setup

# Troubleshooting wizard
webops troubleshoot

# Interactive management dashboard
webops manage
```

### Real-time Monitoring
```bash
# Watch all deployments
webops watch --all

# Watch specific deployment
webops watch myapp

# Interactive logs with real-time updates
webops interactive-logs myapp
```

### Project Management
```bash
# Complete project setup workflow
webops project:setup --repo https://github.com/user/repo.git
webops project:setup --repo github.com/user/project --name myproject

# Validate project structure
webops project:validate myapp
```

## Database Management

Each deployed application gets its own PostgreSQL database with unique, encrypted credentials.

**View credentials:**
- Web UI: Navigate to "Databases" → Select your database
- CLI: `webops db:credentials myapp`

**Security Features:**
- Database passwords encrypted at rest using Fernet
- Automatic backup with retention policies
- Connection monitoring and alerting
- Isolated database per deployment

**Connection string format:**
```
postgresql://username:password@localhost:5432/database_name
```

## Monitoring & Logs

### Web Interface
- Real-time system health monitoring
- Service status indicators with auto-healing
- Live log streaming with search and filtering
- Security audit dashboard with threat detection
- Performance metrics with predictive alerts

### Enhanced CLI Monitoring
```bash
# View deployment logs with filtering
webops logs myapp --tail 100 --level=error

# Follow logs in real-time
webops logs myapp --follow

# Interactive status dashboard
webops interactive-status --refresh-rate 2

# System health check
webops system health
```

### Log Management
- **Control panel**: Centralized logging with rotation
- **Applications**: Per-deployment log isolation
- **Security**: All operations logged with immutable audit trail
- **Monitoring**: Automated alerting for security events
- **WebSocket**: Real-time log streaming to CLI

## Security Architecture

WebOps implements enterprise-grade security with multiple defense layers:

### Core Security Features
- **Dedicated System User**: All services run as `webops` user (not root)
- **Minimal Sudo Access**: Passwordless sudo only for specific deployment commands
- **SSL/TLS**: Automatic HTTPS with Let's Encrypt and certificate monitoring
- **Firewall**: UFW configured (ports 80, 443, 22 only) with fail2ban
- **Process Isolation**: Each app isolated via systemd with resource limits
- **Encrypted Credentials**: Database passwords encrypted at rest using Fernet
- **CSRF Protection**: All forms protected with Django security middleware
- **Session Security**: Secure cookies, configurable timeout, and session hijacking protection
- **Audit Trail**: All sudo commands logged to /var/log/auth.log with correlation
- **Input Validation**: Multi-layer validation with SSRF protection
- **RBAC**: Role-based access control for users and API tokens
- **2FA Support**: TOTP-based two-factor authentication

### Security Validation & Monitoring
```bash
# Validate webops user setup
sudo ./cli/webops_cli/scripts/validate-user-setup.sh

# Run comprehensive security audit
sudo ./cli/webops_cli/scripts/webops-security-check.sh

# Audit sudo usage with correlation analysis
sudo ./cli/webops_cli/scripts/webops-admin.sh sudo-audit

# CLI security audit
webops security audit
```

## Development

### Control Panel Development
```bash
cd control-panel
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python manage.py test
python run_tests.py

# Start Celery workers
./start_celery.sh

# Start development server
python manage.py runserver
```

### CLI Development
```bash
cd cli
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Run tests
python -m pytest tests/

# Test CLI
webops --help
```

## Testing

### Control Panel Tests
```bash
# Run all tests with coverage
cd control-panel
python manage.py test --coverage

# Run security-specific tests
python manage.py test apps.core.security.tests

# Run deployment tests with isolation validation
python manage.py test apps.deployments.tests
```

### CLI Tests
```bash
# Run CLI tests
cd cli
python -m pytest tests/ --cov=webops_cli

# Run security features tests
python -m pytest tests/test_security_features.py

# Run enhanced CLI tests
python -m pytest tests/test_enhanced_cli.py
```

## Troubleshooting

### Control Panel Issues
```bash
# Check Django server status
python manage.py check

# Test Celery connectivity
python manage.py test_celery

# View Django logs
tail -f control-panel/logs/webops.log
```

### Deployment Issues
```bash
# Check deployment logs with security context
webops logs myapp --level=error

# Verify systemd service status
systemctl status myapp

# Check Celery worker health
webops system status
```

### CLI Issues
```bash
# Verify API connectivity
webops status

# Check configuration
webops config

# Run troubleshooting wizard
webops troubleshoot

# Validate system setup
webops system validate
```

## Key Features

### Automation System
- **Workflow Automation**: Node-based execution engine for complex deployment scenarios
- **Template System**: Reusable automation patterns
- **Event-Driven**: Trigger workflows based on deployment events
- **Validation**: Built-in validators for workflow integrity

### Addons System
- **Plugin Architecture**: Extensible hook-based plugin system
- **Auto-Discovery**: Automatic addon discovery from configured directories
- **Hook Support**: `pre_deployment`, `post_deployment`, `service_health_check`, etc.
- **Priority-Based**: Priority-based execution with retry logic and timeouts

### LLM Deployment
- **vLLM Integration**: Deploy LLM models from Hugging Face
- **GPU Allocation**: Intelligent GPU resource management
- **Model Quantization**: Support for quantized models
- **OpenAI API**: Compatible API endpoints for existing applications

## Documentation

**Getting Started:**
- [Quick Start Guide](control-panel/CHANGELOG.md) - Latest updates and features
- [CLI Documentation](cli/webops_cli/ui/README.md) - Interactive CLI features
- [Development Guide](docs/development/development.md) - Developer setup

**API & Architecture:**
- [API Reference](control-panel/apps/api/docs/) - Complete API documentation
- [Core Architecture](docs/architecture/core.md) - Security-first design patterns
- [Automation Guide](docs/automation/) - Workflow automation system

**Operations:**
- [Operations Guide](docs/operations/) - Production deployment
- [Security Features](docs/security/security-features.md) - Complete security implementation
- [Troubleshooting](docs/operations/troubleshooting.md) - Common issues and solutions

## Contributing

WebOps welcomes contributions that align with our security-first philosophy:

1. Fork the repository at https://github.com/dagiim/webops
2. Create a feature branch with security considerations
3. Implement changes with security validation
4. Add comprehensive tests including security tests
5. Update documentation reflecting security implications
6. Submit pull request with security checklist

**Development Setup:**
```bash
# Clone repository
git clone https://github.com/dagiim/webops.git
cd webops

# Set up development environment with security
python -m venv venv
source venv/bin/activate
pip install -r control-panel/requirements.txt

# Run comprehensive tests including security
cd control-panel
python manage.py test --with-security-tests

# Run development server
python manage.py runserver
```

## Roadmap

**Core Platform:**
- [x] Security-first deployment system
- [x] Django application support with enterprise security
- [x] Static site deployment with optimization
- [x] PostgreSQL management with encryption
- [x] Feature-rich CLI tool with interactive wizards
- [x] LLM model deployment via vLLM
- [x] Real-time monitoring with WebSocket support
- [x] Automation system with workflow management
- [x] Addon system with plugin architecture

**Advanced Features:**
- [ ] Docker container support with security scanning
- [ ] Multi-user support with enhanced RBAC
- [ ] GitLab/Bitbucket integration with OAuth security
- [ ] Webhook auto-deployments with security validation
- [ ] Advanced monitoring with anomaly detection
- [ ] Database clustering with encryption at rest
- [ ] Advanced backup and disaster recovery

## FAQ

**Q: Can I host multiple applications securely on one server?**
A: Yes! WebOps uses systemd isolation, resource limits, and security boundaries per deployment.

**Q: Do I need a domain name for security?**
A: SSL certificates provide security for data in transit. IP addresses work for internal applications.

**Q: Can I use my own SSL certificates with security validation?**
A: Yes, with automatic security header generation and certificate monitoring.

**Q: What security measures are in place for deployment failures?**
A: Rollback to previous deployment, security isolation, and comprehensive audit logging.

**Q: How does WebOps handle security in multi-tenant scenarios?**
A: Process isolation, resource limits, encrypted credentials, and RBAC.

**Q: How do I backup data with security?**
A: Encrypted backups with retention policies and integrity verification.

**Q: Can I use WebOps for enterprise production?**
A: Yes, with enterprise security features, compliance tools, and security monitoring.

**Q: Is there a migration path with security preservation?**
A: Yes! WebOps maintains security context during migrations and provides validation tools.

**Q: What makes WebOps different from other hosting platforms?**
A: Security-first design, zero build tools, pure frontend, comprehensive CLI, and enterprise-grade features.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security & Support

For security issues: **security@eleso.com** (Do not create public issues)

**General Support:**
- **Issues**: [GitHub Issues](https://github.com/dagiim/webops/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dagiim/webops/discussions)
- **Documentation**: Comprehensive docs in `/docs` directory
- **Developer**: Douglas Mutethia ([GitHub](https://github.com/dagiim))
- **Company**: [Eleso Solutions](https://eleso.com)

**Enterprise Support:**
- Priority security updates
- Custom security audits
- Enterprise deployment consulting
- 24/7 security monitoring support

---

**WebOps: Security-first hosting platform for developers who demand enterprise-grade reliability without complexity.**

Built with pure HTML, CSS, and vanilla JavaScript - zero build tools, maximum security.

Modern Django 5.0+ backend with comprehensive CLI tooling and real-time monitoring capabilities.