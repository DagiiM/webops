# WebOps

> A minimal, self-hosted VPS hosting platform for deploying and managing web applications

WebOps is a lightweight hosting platform that transforms a fresh VPS into a fully-functional web application deployment system with a single command. Deploy Django applications, static sites, and LLM models through a clean web interface or CLI.

## Features

- **One-Command Setup** - Complete VPS orchestration via `./setup.sh`
- **Minimal & Fast** - Zero npm dependencies, pure HTML/CSS/JS frontend
- **Secure by Default** - Automated SSL, encrypted credentials, isolated processes
- **PostgreSQL Included** - Automatic database creation per application
- **Background Tasks** - Celery integration for async operations
- **Nginx Powered** - Automatic reverse proxy and virtual host configuration
- **Simple Management** - Clean web UI for all operations
- **CLI Available** - Command-line tool for power users
- **Real-time Logs** - Stream application logs from the dashboard

## Use Cases

- Personal project hosting
- Development/staging environments
- Small team deployments
- Learning DevOps practices
- Alternative to Heroku/Railway/Render for small projects

## Prerequisites

- Fresh VPS or dedicated server
- Ubuntu 22.04 LTS (or Debian 11+)
- Minimum 2GB RAM, 2 CPU cores
- Root or sudo access
- Domain name (optional, but recommended for SSL)

## Quick Start

### Development (MVP)

**Current Status**: Production Ready - Complete WebOps platform with security-first design

For development and testing:

```bash
cd control-panel
./quickstart.sh
source venv/bin/activate
python manage.py runserver
```

Then visit http://127.0.0.1:8000 (login: `admin` / `admin123`)

See **[docs/getting-started/quick-start-guide.md](docs/getting-started/quick-start-guide.md)** for detailed development setup.

### Production Installation

1. **SSH into your server**:
```bash
ssh root@your-server-ip
```

2. **Clone the repository**:
```bash
git clone https://github.com/dagiim/webops.git
cd webops
```

3. **Run the setup script**:
```bash
chmod +x setup.sh
sudo ./setup.sh
```

4. **Follow the prompts**:
   - Enter domain name for control panel (or use IP)
   - Create admin username and password
   - Confirm installation

5. **Access WebOps**:
   - Open browser and navigate to: `https://your-domain.com` or `http://your-server-ip:8009`
   - Login with the admin credentials you created

That's it! Your VPS is now ready to host applications with enterprise-grade security.

## Usage

### Via Web Interface

1. **Login** to the WebOps control panel
2. **Navigate** to "New Deployment"
3. **Fill in** the deployment form:
   - Service name: `my-django-app`
   - Repository URL: `https://github.com/username/django-project`
   - Branch: `main`
   - Domain: `myapp.example.com` (optional)
4. **Click** "Deploy" and watch the progress
5. **Access** your application at the configured domain

### Via CLI

Install the CLI tool:
```bash
pip install webops-cli
```

Configure:
```bash
webops config --url https://panel.yourdomain.com --token YOUR_API_TOKEN
```

Deploy an application:
```bash
webops deploy --repo https://github.com/user/repo --name myapp --domain myapp.com
```

List deployments:
```bash
webops list
```

View logs:
```bash
webops logs myapp --tail 100 --follow
```

Restart service:
```bash
webops restart myapp
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 VPS Server                       │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │      Nginx (Reverse Proxy + SSL)          │ │
│  └──────┬─────────────────────────────────────┘ │
│         │                                        │
│  ┌──────▼──────────┐    ┌──────────────────┐   │
│  │  WebOps Panel   │    │  User Apps       │   │
│  │   (Django)      │    │  - Django Apps   │   │
│  └────────┬────────┘    │  - Static Sites  │   │
│           │             │  - LLM Models    │   │
│  ┌────────▼────────┐    └─────────┬────────┘   │
│  │   PostgreSQL    │◄─────────────┘            │
│  └─────────────────┘                           │
│                                                  │
│  ┌─────────────────┐    ┌──────────────────┐   │
│  │  Redis          │    │  Celery Workers  │   │
│  └─────────────────┘    └──────────────────┘   │
└─────────────────────────────────────────────────┘
```

**WebOps Tech Stack:**
- **Backend**: Django 5.0+, Python 3.11+ with domain-driven architecture
- **Frontend**: Pure HTML5/CSS3/Vanilla JavaScript (zero npm dependencies, no build tools)
- **Database**: PostgreSQL 14+ with encrypted credentials at rest
- **Web Server**: Nginx with automatic SSL via Let's Encrypt
- **Task Queue**: Celery + Redis for background deployment tasks
- **Process Manager**: systemd with security isolation per deployment
- **Security**: Fernet encryption, CSRF protection, rate limiting
- **Authentication**: Token-based with RBAC and 2FA support

## Project Structure

```
webops/
├── cli/                              # WebOps CLI with interactive wizards
│   ├── webops_cli/
│   │   ├── api.py                    # API client for control panel
│   │   ├── config.py                 # Configuration management
│   │   ├── ui/                       # Interactive UI components
│   │   ├── wizards/                  # Deployment & troubleshooting wizards
│   │   └── system-templates/         # Systemd/Nginx templates
│   └── tests/
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
│   │   ├── automation/               # Workflow automation system
│   │   └── addons/                   # Hook-based plugin system
│   ├── templates/                    # Pure HTML templates (no build)
│   └── static/                       # CSS/JS (zero npm, pure vanilla)
└── docs/                             # Comprehensive documentation
```

## Configuration

WebOps uses environment variables for configuration. After installation, edit `$WEBOPS_DIR/control-panel/.env`:

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/webops_db

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=your-encryption-key
```

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
7. Configure Nginx with rate limiting and security policies
8. Obtain SSL certificate via Let's Encrypt
9. Create systemd service with resource limits
10. Start your application with full audit logging

### Static Sites & LLM Models

WebOps supports multiple deployment types:
- **Static Sites**: HTML/CSS/JS with automatic optimization
- **Django Applications**: Full-stack with database integration
- **LLM Models**: vLLM-powered models with GPU allocation
- **Custom Applications**: Generic deployment with templates

Each deployment type includes security hardening, automated backups, and monitoring.

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

### CLI
```bash
# View deployment logs with filtering
webops logs myapp --tail 100 --level=error

# Follow logs in real-time
webops logs myapp --follow

# System health check
webops system health

# Security audit
webops security audit
```

### Log Management
- **Control panel**: Centralized logging with rotation
- **Applications**: Per-deployment log isolation
- **Security**: All operations logged with immutable audit trail
- **Monitoring**: Automated alerting for security events

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

### Security Validation & Monitoring
```bash
# Validate webops user setup
sudo ./scripts/validate-user-setup.sh

# Run comprehensive security audit
sudo ./scripts/webops-security-check.sh

# Audit sudo usage with correlation analysis
sudo ./scripts/webops-admin.sh sudo-audit

# Check security headers and SSL configuration
webops security scan --deployment myapp
```

## Updates & Maintenance

Update WebOps to the latest version with security patches:

```bash
cd webops
sudo ./update.sh  # Automated update with rollback capability
```

Or via CLI with validation:
```bash
webops self-update --validate --backup
```

## Troubleshooting

### Setup Issues
```bash
# Check system requirements and compatibility
webops system validate

# Review setup logs with security context
tail -f /var/log/webops-setup.log

# Verify system resources
webops system resources
```

### Deployment Issues
```bash
# Check deployment logs with security context
webops logs myapp --security-context

# Verify systemd service status
systemctl status myapp

# Check Celery worker health
webops celery status
```

### Application Startup Issues
```bash
# Check systemd service with security context
systemctl status myapp --no-pager

# Review application logs with security filtering
journalctl -u myapp -n 50 --no-pager

# Run health checks with security validation
webops health myapp --security-check
```

### Infrastructure Issues
```bash
# Test Nginx configuration
nginx -t

# Check PostgreSQL health
webops database health

# Verify SSL certificates
webops ssl status
```

## Documentation

**Getting Started:**
- [Installation Guide](docs/getting-started/installation.md)
- [Quick Start Guide](docs/getting-started/quick-start-guide.md)
- [Onboarding](docs/getting-started/onboarding.md)

**Security:**
- [Security Features](docs/security/security-features.md) - Complete security implementation
- [Security Hardening](docs/security/security-hardening.md) - Advanced security practices
- [Core Architecture](docs/architecture/core.md) - Security-first design patterns

**Development & Operations:**
- [Development Guide](docs/development/development.md)
- [API Reference](docs/reference/api-reference.md)
- [Operations Guide](docs/operations/)
- [Troubleshooting](docs/operations/troubleshooting.md)

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

## Testing

```bash
# Run all tests with security coverage
python manage.py test --coverage

# Run security-specific tests
python manage.py test apps.security

# Run deployment tests with isolation validation
python manage.py test apps.deployments.tests
```

## Roadmap

**Core Platform:**
- [x] Security-first deployment system
- [x] Django application support with enterprise security
- [x] Static site deployment with optimization
- [x] PostgreSQL management with encryption
- [x] CLI tool with security auditing
- [x] LLM model deployment via vLLM

**Advanced Features:**
- [ ] Docker container support with security scanning
- [ ] Automated backups with encryption and retention
- [ ] Multi-user support with RBAC
- [ ] GitLab/Bitbucket integration with OAuth security
- [ ] Webhook auto-deployments with security validation
- [ ] Resource usage alerts with anomaly detection
- [ ] Blue-green deployments with security validation
- [ ] Database clustering with encryption at rest

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security & Support

For security issues: **security@eleso.com** (Do not create public issues)

**General Support:**
- **Issues**: [GitHub Issues](https://github.com/dagiim/webops/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dagiim/webops/discussions)
- **Documentation**: Comprehensive docs at [docs/](docs/)
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