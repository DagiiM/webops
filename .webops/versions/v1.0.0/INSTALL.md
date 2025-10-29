# WebOps Platform Installation Guide

Complete step-by-step installation guide for WebOps Platform v1.0.0.

## Table of Contents

1. [Pre-Installation](#pre-installation)
2. [Installation Methods](#installation-methods)
3. [Post-Installation](#post-installation)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Next Steps](#next-steps)

## Pre-Installation

### System Requirements Check

Before installation, verify your system meets the requirements:

```bash
# Check OS version
lsb_release -a

# Check CPU cores
nproc

# Check available memory (should show 2GB+ free)
free -h

# Check available disk space (should show 20GB+ free)
df -h /

# Check systemd
systemctl --version

# Check internet connectivity
ping -c 3 google.com
```

### Required Packages

Most packages will be installed automatically, but ensure these are available:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y curl wget git

# Rocky/AlmaLinux
sudo dnf install -y curl wget git
```

### Network Requirements

Ensure these ports are available:

- **22** - SSH (must remain open!)
- **80** - HTTP
- **443** - HTTPS
- **8000** - Control panel (can be customized)

Check port availability:

```bash
# Check if ports are in use
sudo ss -tulpn | grep -E ':(22|80|443|8000) '
```

## Installation Methods

### Method 1: Quick Install (Recommended for First-Time Users)

This installs the base system with default configuration:

```bash
# Step 1: Navigate to project directory
cd /home/douglas/webops

# Step 2: Run installer with sudo
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh
```

The installer will:
- Validate system requirements
- Install base system packages
- Apply security hardening
- Configure firewall
- Set up PostgreSQL database
- Create webops system user
- Configure services

**Duration:** 10-15 minutes

### Method 2: Custom Installation

For advanced users who want to customize the installation:

#### Step 1: Create Configuration

```bash
cd /home/douglas/webops/.webops

# Copy template
cp versions/v1.0.0/config.env.template config.env

# Edit configuration
nano config.env
```

**Key settings to customize:**

```bash
# Installation location
WEBOPS_ROOT=/opt/webops  # Change if needed

# Control panel
CONTROL_PANEL_PORT=8000  # Change if port conflict
DEBUG=false              # Keep false for production

# Database credentials
DB_PASSWORD=your-secure-password

# Security keys (generate new ones!)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SECRET_KEY=$(openssl rand -hex 32)

# Feature flags
FEATURE_KUBERNETES=true    # Enable if you need K8s
FEATURE_MONITORING=true    # Enable monitoring stack
```

#### Step 2: Run Installation

```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/install.sh
```

### Method 3: Component-by-Component Installation

Install base system first, then add components as needed:

#### Step 1: Install Base System

```bash
# Run validation
sudo /home/douglas/webops/.webops/versions/v1.0.0/setup/validate.sh

# Install base hardening
sudo /home/douglas/webops/.webops/versions/v1.0.0/setup/base.sh
```

#### Step 2: Install Django Control Panel

```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/setup/django.sh
```

#### Step 3: Add Optional Components

```bash
# PostgreSQL database
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply postgresql

# Monitoring stack
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply monitoring

# High availability (requires etcd + postgresql first)
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply etcd
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply patroni

# Kubernetes support
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply kubernetes

# KVM virtualization
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply kvm
```

## Post-Installation

### Step 1: Create Django Superuser

```bash
cd /home/douglas/webops/control-panel

# Option 1: Interactive
sudo -u webops ./venv/bin/python manage.py createsuperuser

# Option 2: Non-interactive (for automation)
DJANGO_SUPERUSER_USERNAME=admin \
DJANGO_SUPERUSER_EMAIL=admin@example.com \
DJANGO_SUPERUSER_PASSWORD=changeme \
sudo -u webops ./venv/bin/python manage.py createsuperuser --noinput
```

### Step 2: Configure Firewall (if needed)

If you changed the default port, update firewall rules:

```bash
# Ubuntu/Debian
sudo ufw allow 8000/tcp

# Rocky/AlmaLinux
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### Step 3: Configure Domain and SSL (Optional)

If you have a domain name:

```bash
# Update ALLOWED_HOSTS
sudo nano /home/douglas/webops/control-panel/.env

# Add your domain
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com

# Configure Let's Encrypt
sudo certbot --nginx -d yourdomain.com
```

## Configuration

### Environment Variables

Key environment variables in `/home/douglas/webops/control-panel/.env`:

```bash
# Django
DEBUG=False
SECRET_KEY=<auto-generated>
ALLOWED_HOSTS=localhost,127.0.0.1,your-ip

# Database
DATABASE_URL=postgresql://webops:webops@localhost:5432/webops

# Celery & Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
REDIS_URL=redis://localhost:6379/3

# Security
ENCRYPTION_KEY=<auto-generated>

# WebOps
WEBOPS_INSTALL_PATH=/home/douglas/webops
MIN_PORT=8001
MAX_PORT=9000
```

### Service Configuration

Services are managed by systemd:

```bash
# Check status
sudo systemctl status webops-web
sudo systemctl status webops-worker
sudo systemctl status webops-beat

# Start/stop/restart
sudo systemctl start webops-web
sudo systemctl stop webops-web
sudo systemctl restart webops-web

# Enable/disable autostart
sudo systemctl enable webops-web
sudo systemctl disable webops-web

# View logs
sudo journalctl -u webops-web -f
sudo journalctl -u webops-worker -f
```

## Verification

### Step 1: Check Service Status

```bash
# All services should show "active (running)"
sudo systemctl status webops-web webops-worker webops-beat
```

### Step 2: Check Installation State

```bash
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops state
```

Expected output:
```
WebOps Installation State
========================

Installed Components:
  base-system          version: 1.0.0      installed: 2024-10-29T...
  django-control-panel version: 1.0.0      installed: 2024-10-29T...
  postgresql           version: 15         installed: 2024-10-29T...
```

### Step 3: Test Web Access

```bash
# Get your server IP
hostname -I | awk '{print $1}'

# Test HTTP access
curl http://localhost:8000/

# Or open in browser:
# http://YOUR_IP:8000/
```

### Step 4: Test Database Connection

```bash
# Connect to PostgreSQL
sudo -u postgres psql webops -c "SELECT version();"

# Check tables
sudo -u postgres psql webops -c "\dt"
```

### Step 5: Test Celery

```bash
# Check Celery workers
cd /home/douglas/webops/control-panel
sudo -u webops ./venv/bin/celery -A config.celery_app inspect active

# Check registered tasks
sudo -u webops ./venv/bin/celery -A config.celery_app inspect registered
```

## Common Installation Issues

### Issue 1: Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find what's using the port
sudo ss -tulpn | grep :8000

# Stop the conflicting service
sudo systemctl stop <service-name>

# Or change WebOps port in config.env
CONTROL_PANEL_PORT=8001
```

### Issue 2: PostgreSQL Connection Failed

**Error:** `could not connect to server`

**Solution:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Check if database exists
sudo -u postgres psql -l | grep webops
```

### Issue 3: Permission Denied

**Error:** `Permission denied` when accessing files

**Solution:**
```bash
# Fix ownership
sudo chown -R webops:webops /home/douglas/webops/control-panel

# Fix permissions
sudo chmod -R 755 /home/douglas/webops/control-panel
```

### Issue 4: Static Files Not Loading

**Problem:** CSS/JS not loading in browser

**Solution:**
```bash
cd /home/douglas/webops/control-panel

# Collect static files
sudo -u webops ./venv/bin/python manage.py collectstatic --noinput

# Restart web service
sudo systemctl restart webops-web
```

## Resuming Interrupted Installation

If installation is interrupted:

```bash
# Check where it stopped
cat /home/douglas/webops/.webops/.install_state

# Resume installation
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/resume.sh

# Or force restart
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/resume.sh --force
```

## Repairing Broken Installation

If installation is broken:

```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/repair.sh
```

## Next Steps

After successful installation:

1. **Secure Your Installation**
   - Change default passwords
   - Configure SSL/TLS
   - Enable 2FA
   - Set up firewall rules

2. **Configure Backups**
   ```bash
   # Edit backup configuration
   nano /home/douglas/webops/.webops/config.env

   # Enable backups
   BACKUP_ENABLED=true
   BACKUP_SCHEDULE="0 3 * * *"
   ```

3. **Set Up Monitoring**
   ```bash
   sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply monitoring
   ```

4. **Deploy Your First Application**
   - Access control panel: http://YOUR_IP:8000/
   - Login with superuser credentials
   - Create your first deployment

5. **Read the Documentation**
   - Main README: `/home/douglas/webops/README.md`
   - Control Panel docs: `/home/douglas/webops/control-panel/CLAUDE.md`
   - API documentation: http://YOUR_IP:8000/api/docs/

## Uninstallation

To remove WebOps completely:

```bash
# Uninstall keeping data
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh

# Complete removal including data (DANGER!)
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh --purge
```

## Getting Help

If you encounter issues:

1. Check logs: `sudo journalctl -xe -u webops-web`
2. Review troubleshooting guide: `TROUBLESHOOTING.md`
3. Run validation: `sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops validate`
4. Check platform state: `/home/douglas/webops/.webops/versions/v1.0.0/bin/webops state`
5. Report issues: https://github.com/DagiiM/webops/issues

---

**Installation complete!** Enjoy using WebOps Platform v1.0.0.
