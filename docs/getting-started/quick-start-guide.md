# WebOps Quick Start Guide

**Get WebOps up and running quickly - from installation to first deployment**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/dagiim/webops](https://github.com/dagiim/webops)

---

## Overview

This guide covers:
- **MVP Setup**: Get the control panel running in development
- **Production Setup**: Full WebOps installation with `webops` user
- **First Deployment**: Create and manage your first application
- **Common Tasks**: Essential commands and troubleshooting

---

## Development Setup (MVP)

### Prerequisites

- Python 3.11 or higher
- Git
- 2GB RAM minimum

### Quick Installation

```bash
# Navigate to control panel
cd $WEBOPS_DIR/control-panel

# Run quick setup
./quickstart.sh

# Start development server
source venv/bin/activate
python manage.py runserver
```

### Access the Control Panel

- **Control Panel**: Start the development server and access at the default port
- **Admin Interface**: Access the admin interface after starting the server

**Login Credentials:**
- Username: `admin`
- Password: `admin123`

### What's Included in MVP

✅ **Core Functionality**
- Django control panel with authentication
- Deployment model and database schema
- Clean, responsive web interface (pure CSS, no frameworks)
- Dashboard with deployment statistics
- Deployment creation and viewing
- Deployment logs tracking
- Admin interface for managing data

✅ **Technology Stack**
- Python 3.11+ with Django 5.0+
- SQLite database (for development)
- Pure HTML5/CSS3/JavaScript (no npm, no build tools)
- Virtual environment for dependencies
- Pyright strict type checking enabled

---

## Production Setup

### Full Installation

```bash
sudo ./setup.sh
```

This automatically:
- Creates `webops` system user
- Sets up secure directory structure
- Configures limited sudo access
- Installs all services to run as `webops`
- Sets up PostgreSQL database
- Configures nginx and systemd services

### Validation

Verify everything is set up correctly:

```bash
sudo ./scripts/validate-user-setup.sh
```

### Security Audit

Run comprehensive security checks:

```bash
sudo ./scripts/webops-security-check.sh
```

---

## WebOps User Quick Reference

### Key Information

**User:** `webops`  
**Home:** `/opt/webops`  
**Shell:** `/bin/bash`  
**Groups:** `webops`, `www-data`, `postgres`  
**Password:** None (no login)  
**SSH:** Not allowed  
**Sudo:** Limited (specific commands only)

### Security Features

- ✅ Services run as `webops`, not root
- ✅ Limited sudo (nginx, systemd, certbot only)
- ✅ All actions logged to `/var/log/auth.log`
- ✅ Secure permissions (700/750)
- ✅ Complete audit trail

### Common Administration Tasks

```bash
# Check status
sudo ./scripts/webops-admin.sh status

# Open shell as webops
sudo ./scripts/webops-admin.sh shell

# View logs
sudo ./scripts/webops-admin.sh logs webops-web

# Fix permissions
sudo ./scripts/webops-admin.sh fix-permissions

# Audit sudo usage
sudo ./scripts/webops-admin.sh sudo-audit
```

---

## Creating Your First Deployment

### Via Web Interface

1. Log in to the control panel
2. Click **"New Deployment"** in the navigation
3. Fill in the form:
   - **Name**: `my-app` (lowercase, hyphens/underscores allowed)
   - **Repository URL**: `https://github.com/username/repo`
   - **Branch**: `main` (or your branch name)
   - **Domain**: (optional)
4. Click **"Create Deployment"**

### Via Command Line (Production)

```bash
# Switch to webops user
sudo -u webops -i

# Navigate to control panel
cd $WEBOPS_DIR/control-panel
source venv/bin/activate

# Create deployment
python manage.py deploy_app \
    --name myproject \
    --repo https://github.com/user/repo \
    --branch main
```

---

## Essential Commands

### Development (MVP)

```bash
# Start development server
python manage.py runserver

# Run on different port
python manage.py runserver 8001

# Create admin user
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic

# Access Django shell
python manage.py shell
```

### Production

```bash
# Service management
sudo systemctl restart webops-web          # Restart web service
sudo systemctl status webops-web           # Check service status
sudo systemctl status 'webops-*'           # All WebOps services

# View logs
sudo journalctl -u webops-web -f           # Live logs
tail -f /opt/webops/logs/gunicorn-error.log # Application logs

# Working as webops user
sudo -u webops -i                          # Interactive shell
sudo -u webops python manage.py shell      # Django shell

# Monitor processes
ps aux | grep webops                       # Show all webops processes
```

---

## Project Structure

```
webops/
├── control-panel/           # Django application
│   ├── apps/
│   │   ├── core/           # Shared utilities and base models
│   │   ├── deployments/    # Deployment management
│   │   ├── databases/      # Database credentials
│   │   └── services/       # Service monitoring
│   ├── config/             # Django settings
│   ├── static/             # CSS and JavaScript
│   ├── templates/          # HTML templates
│   ├── venv/              # Python virtual environment
│   ├── manage.py          # Django management
│   └── quickstart.sh      # Quick setup script
├── docs/                   # Documentation
├── scripts/                # Helper scripts
├── .env                    # Environment configuration
├── setup.sh               # Production setup script
└── README.md              # Main documentation
```

---

## Environment Variables

The `.env` file contains:

```bash
SECRET_KEY          # Django secret key (auto-generated)
DEBUG               # Debug mode (True for dev, False for production)
ALLOWED_HOSTS       # Comma-separated hostnames
DATABASE_URL        # Database connection string
ENCRYPTION_KEY      # Fernet key for password encryption
WEBOPS_INSTALL_PATH # Base installation path (/opt/webops)
MIN_PORT            # Minimum port for deployments (8001)
MAX_PORT            # Maximum port for deployments (9000)
```

---

## Troubleshooting

### Development Issues

#### Port Already in Use
```bash
python manage.py runserver 8001
```

#### Database Locked
```bash
# Stop any running instances
pkill -f "manage.py runserver"

# Restart
python manage.py runserver
```

#### Static Files Not Loading
```bash
python manage.py collectstatic --clear
```

#### Reset Everything
```bash
# Delete database and start fresh
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Production Issues

#### Permission Denied
```bash
sudo ./scripts/webops-admin.sh fix-permissions
```

#### Sudo Access Denied
```bash
sudo visudo -c -f /etc/sudoers.d/webops
```

#### Service Won't Start
```bash
sudo journalctl -u webops-web -n 50
systemctl show webops-web -p User
```

#### Database Connection Issues
```bash
# Test connection
sudo -u webops psql -d webops_control_panel

# Check configuration
sudo cat /etc/postgresql/15/main/pg_hba.conf | grep webops
```

---

## Monitoring & Security

### Monitor Sudo Usage

```bash
# All sudo commands by webops
sudo grep "webops.*sudo" /var/log/auth.log

# Today's commands only
sudo grep "webops.*sudo" /var/log/auth.log | grep "$(date +%b\ %d)"

# Failed attempts (security concern!)
sudo grep "webops.*NOT in sudoers" /var/log/auth.log
```

### Security Checks

```bash
# Run full security audit
sudo ./scripts/webops-security-check.sh

# Check for world-readable secrets
find /opt/webops -name ".env" -perm /o+r

# Check for setuid files
find /opt/webops -type f -perm -4000
```

---

## What's Not Yet Implemented (MVP)

The MVP is a working foundation. The following features are planned:

⏳ **Deployment Pipeline**
- Actual Git repository cloning
- Dependency installation
- Systemd service creation
- Nginx configuration
- SSL certificate management

⏳ **Service Management**
- Start/Stop/Restart actions
- Real-time status monitoring
- System resource monitoring

⏳ **Database Management**
- PostgreSQL database creation
- Credential encryption/decryption
- Connection string generation

⏳ **Background Tasks**
- Celery worker for async deployments
- Real-time log streaming
- Task queue management

---

## Next Steps

### For Development

1. **Implement Deployment Service**: Add Git cloning and dependency installation
2. **Add Celery Tasks**: Background deployment processing
3. **Create System Templates**: Nginx and systemd configuration templates
4. **Build Setup Script**: One-command VPS installation

### For Production

1. **Configure Domain**: Set up your domain and SSL certificates
2. **Set Up Monitoring**: Configure log monitoring and alerts
3. **Create Backups**: Set up automated database and file backups
4. **Security Hardening**: Review and implement additional security measures

---

## Documentation

- **[webops-user-guide.md](./webops-user-guide.md)** - Complete WebOps user guide
- **[security-features.md](./security-features.md)** - Security architecture
- **[deployment-guide.md](./deployment-guide.md)** - Deployment procedures
- **[installation.md](./installation.md)** - Installation instructions
- **[troubleshooting.md](./troubleshooting.md)** - Common issues and solutions

---

## Support

### Getting Help

1. Check this quick start guide
2. Run validation: `sudo ./scripts/validate-user-setup.sh`
3. Run security audit: `sudo ./scripts/webops-security-check.sh`
4. Review logs: `sudo journalctl -u webops-web -n 100`

### Reporting Issues

Include the following information:

```bash
# System info
uname -a
cat /etc/os-release

# User status
id webops
sudo -u webops sudo -l

# Service status
sudo systemctl status 'webops-*' --no-pager

# Validation report
sudo ./scripts/validate-user-setup.sh
```

---

**Current Version**: v0.1.0-mvp (Minimal Working Version)

**Status**: ✅ MVP Complete - Ready for feature development

**Next Milestone**: Phase 2 - Deployment Pipeline Implementation

---

**Everything you need to get started with WebOps!**