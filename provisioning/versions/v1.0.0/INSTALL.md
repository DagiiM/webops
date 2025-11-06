# WebOps Platform Installation Guide

Complete step-by-step installation guide for WebOps Platform v1.0.0.

## Table of Contents

1. [Pre-Installation](#pre-installation)
2. [Quick Start](#quick-start)
3. [Installation Process](#installation-process)
4. [Post-Installation](#post-installation)
5. [Configuration](#configuration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Topics](#advanced-topics)

## Pre-Installation

### System Requirements

**Minimum Requirements:**
- **OS**: Ubuntu 22.04 LTS, Debian 11+, Rocky Linux 8+, or AlmaLinux 8+
- **CPU**: 2 cores
- **RAM**: 2GB
- **Disk**: 20GB free space
- **Network**: Internet connectivity for package installation
- **Access**: Root or sudo privileges

**Recommended for Production:**
- **CPU**: 4+ cores
- **RAM**: 4GB+
- **Disk**: 50GB+ SSD storage
- **Network**: Static IP address
- **Domain**: Registered domain name (optional)

### System Requirements Check

Before installation, verify your system meets the requirements:

```bash
# Check OS version
lsb_release -a

# Check CPU cores (should show 2+)
nproc

# Check available memory (should show 2GB+ free)
free -h

# Check available disk space (should show 20GB+ free)
df -h /

# Check systemd version
systemctl --version

# Check internet connectivity
ping -c 3 google.com
```

### Required Packages

The installer will automatically install all required packages. For a preview:

```bash
# Ubuntu/Debian packages installed automatically:
# - git, curl, wget, build-essential
# - python3.11+, python3-pip, python3-venv
# - postgresql-14, postgresql-contrib
# - redis-server
# - ufw (firewall)

# Rocky/AlmaLinux packages installed automatically:
# - git, curl, wget, gcc, make
# - python3.11+, python3-pip
# - postgresql-14, postgresql-contrib
# - redis
# - firewalld
```

**Manual prerequisites (minimal):**
```bash
# Ubuntu/Debian - Only if not already installed
sudo apt-get update
sudo apt-get install -y git

# Rocky/AlmaLinux - Only if not already installed
sudo dnf install -y git
```

### Network Requirements

Ensure these ports are available and will be configured by the installer:

- **22** - SSH (must remain open!)
- **80** - HTTP (optional, for web applications)
- **443** - HTTPS (optional, for web applications)
- **8000** - Control panel (default, can be customized)
- **5432** - PostgreSQL (localhost only, not exposed)
- **6379** - Redis (localhost only, not exposed)

Check port availability:

```bash
# Check if ports are in use
sudo ss -tulpn | grep -E ':(22|80|443|8000) '
```

### SSH Security Requirements

**CRITICAL: The installer configures SSH for key-only authentication by default.**

Before proceeding, ensure you have:
- ✓ SSH key-based authentication configured and tested
- ✓ Console/VNC access as a backup (in case SSH configuration fails)
- ✓ SSH key copied to the server: `ssh-copy-id user@server`

Test your SSH key access:
```bash
ssh -i ~/.ssh/your_key user@your_server
```

## Quick Start

### Recommended Installation Method

The simplest and recommended way to install WebOps:

```bash
# Step 1: Clone the repository
git clone https://github.com/DagiiM/webops.git
cd webops

# Step 2: Run the installer (it handles everything automatically)
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh
```

**What happens during installation:**

1. **Auto-Relocation**: The installer automatically copies the repository to `/opt/webops` and continues from there
2. **System Validation**: Checks OS compatibility, root access, and system resources
3. **Base System Installation**: Installs and configures essential packages
4. **Security Hardening**: Configures firewall, SSH hardening, and system security
5. **PostgreSQL Setup**: Installs PostgreSQL 14 with production configuration
6. **Redis Setup**: Installs and configures Redis for Celery message broker
7. **Control Panel Installation**: Sets up the Django control panel automatically
8. **Service Configuration**: Creates and starts systemd services
9. **Health Verification**: Runs automated health checks to verify installation
10. **Credentials Generation**: Creates admin credentials and saves them securely

**Installation Duration:** 10-15 minutes on a standard VPS

**Installation Location:** The repository will be automatically relocated to `/opt/webops` during installation.

## Installation Process

### Understanding Auto-Relocation

WebOps uses an auto-relocation feature for convenience:

1. Clone the repository anywhere (e.g., `/home/user/webops`, `/root/webops`, `/tmp/webops`)
2. Run the installer from that location
3. The installer automatically:
   - Detects it's not running from `/opt/webops`
   - Copies the entire repository to `/opt/webops`
   - Re-executes itself from `/opt/webops`
   - Continues installation from the new location

This means you can clone and run from anywhere, and WebOps will install itself correctly.

**Example:**
```bash
# Clone anywhere you like
cd /home/myuser
git clone https://github.com/DagiiM/webops.git
cd webops

# Run installer
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh

# Output will show:
# [STEP] Copying WebOps to installation directory...
# [INFO] Source: /home/myuser/webops
# [INFO] Target: /opt/webops
# [INFO] Re-executing installer from /opt/webops...
# [STEP] Starting WebOps platform installation...
```

**Custom Installation Location:**

To install in a different location (not recommended):

```bash
# Set custom installation root before running installer
export WEBOPS_INSTALL_ROOT=/custom/path
sudo -E ./.webops/versions/v1.0.0/lifecycle/install.sh
```

### Installation Steps Explained

#### Step 1: Welcome and Confirmation

The installer shows a welcome screen explaining what will be installed and configured. It includes important warnings about SSH security changes.

**You will be prompted to confirm:**
- Understanding SSH will be configured for key-only authentication
- Having console/VNC backup access
- Agreement to proceed with installation

Type `yes` to continue.

#### Step 2: Environment Validation

The installer validates:
- ✓ Running as root (via sudo)
- ✓ WebOps platform structure exists
- ✓ System meets minimum requirements
- ✓ No conflicting installations

**Idempotency Protection:**

If the installer detects an existing installation (by checking for `config.env`), it will:
- Show a warning about the existing installation
- Explain consequences of running install again (may overwrite config, reset SSH, restart services)
- Suggest alternatives:
  - Use `webops update` for updates
  - Use `repair.sh` for fixing broken installations
  - Remove `config.env` to force fresh installation
- Require explicit `yes` confirmation to proceed

This prevents accidentally overwriting a working installation.

#### Step 3: Auto-Relocation (if needed)

If not already at `/opt/webops`, the installer:
- Creates `/opt` directory if needed
- Copies the repository to `/opt/webops`
- Sets proper permissions
- Re-executes itself from the new location

#### Step 4: Configuration Creation

Creates `/opt/webops/.webops/config.env` with default settings:

```bash
# Key configuration values:
WEBOPS_VERSION=v1.0.0
WEBOPS_ROOT=/opt/webops
CONTROL_PANEL_DIR=/opt/webops/control-panel
DEPLOYMENTS_DIR=/opt/webops/deployments
POSTGRES_ENABLED=true
CONTROL_PANEL_ENABLED=true
ENABLE_SSH_HARDENING=true
ENABLE_FIREWALL=true
```

#### Step 5: Base System Installation

Installs and configures:
- Essential build tools (gcc, make, build-essential)
- Python 3.11+ with pip and venv
- PostgreSQL 14 with contrib extensions
- Redis server for Celery message broker
- Firewall (ufw or firewalld depending on OS)
- Security tools (fail2ban, optional)

**Redis Configuration:**
- Bound to localhost only (127.0.0.1)
- Memory limit: 256MB
- Eviction policy: allkeys-lru
- Used as Celery broker and result backend

#### Step 6: Security Hardening

Applies security configurations:
- **SSH Hardening** (if enabled):
  - Sets `PermitRootLogin prohibit-password`
  - Sets `PasswordAuthentication no`
  - Sets `MaxAuthTries 3`
  - Restarts SSH service
- **Firewall Configuration**:
  - Allows SSH (22), HTTP (80), HTTPS (443)
  - Allows control panel port (default: 8000)
  - Denies all other incoming traffic
- **System Hardening**:
  - Kernel parameter tuning
  - Resource limits configuration

#### Step 7: PostgreSQL Configuration

Sets up PostgreSQL for production:
- Creates `webops` system user
- Initializes database cluster (if fresh install)
- Configures authentication (peer + md5)
- Creates `webops` database
- Enables and starts PostgreSQL service
- Verifies connectivity

#### Step 8: Django Control Panel Installation

**Automatically installs the Django control panel** (no manual step required):
- Creates Python virtual environment at `/opt/webops/control-panel/venv`
- Installs all dependencies from `requirements.txt`
- Creates `.env` file with secure settings
- Generates SECRET_KEY and ENCRYPTION_KEY automatically
- Runs database migrations
- Collects static files
- Creates admin superuser with random password
- Saves credentials to `/opt/webops/.secrets/admin_credentials.txt`

**Services created:**
- `webops-web.service` - Gunicorn web server (port 8000)
- `webops-worker.service` - Celery worker for background tasks
- `webops-beat.service` - Celery beat for scheduled tasks
- `webops-channels.service` - Daphne for WebSocket support

#### Step 9: Health Verification

Automated health checks verify:
- ✓ PostgreSQL service is running
- ✓ PostgreSQL is accepting connections
- ✓ Redis service is running
- ✓ Redis responds to PING
- ✓ webops-web service is running
- ✓ webops-worker service is running
- ✓ Control panel is listening on port 8000

**Results:**
- All checks passed: Installation successful
- Some checks failed: Installation completed with warnings (manual investigation needed)

#### Step 10: Completion

Shows completion message with:
- Admin credentials location
- Control panel URL
- Platform management commands
- Next steps

## Post-Installation

### Step 1: Access Admin Credentials

The installer creates a random admin password for security. Retrieve it:

```bash
# View admin credentials
sudo cat /opt/webops/.secrets/admin_credentials.txt
```

**Output example:**
```
WebOps Control Panel Admin Credentials
======================================
Created: 2024-11-06 10:30:45

Username: admin
Password: xK9#mP2$vL8@qR5!
Email: admin@localhost

Control Panel URL: http://YOUR_IP:8000/
```

**IMPORTANT:** Change this password after first login!

### Step 2: Access the Control Panel

```bash
# Get your server IP
hostname -I | awk '{print $1}'

# Example: 192.168.1.100
```

Open in browser: `http://YOUR_IP:8000/`

Login with credentials from Step 1.

### Step 3: Change Admin Password

1. Login to control panel
2. Navigate to profile/settings
3. Change password to something secure
4. Enable 2FA (recommended)

### Step 4: Configure Allowed Hosts (Production)

For production deployments with a domain:

```bash
# Edit control panel environment
sudo nano /opt/webops/control-panel/.env

# Update ALLOWED_HOSTS
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,YOUR_IP

# Restart web service
sudo systemctl restart webops-web
```

### Step 5: Configure Domain and SSL (Optional)

**Note:** WebOps follows a minimal dependencies philosophy. SSL/TLS setup is optional and not included by default.

For production with a domain, you have options:
1. Use a reverse proxy (Nginx, Caddy) with automatic SSL
2. Run behind a load balancer with SSL termination
3. Use Cloudflare or similar CDN for SSL

Example with Nginx (not included, install separately if desired):
```bash
# Install Nginx separately (not part of WebOps)
sudo apt-get install nginx

# Configure Nginx as reverse proxy
# Point to http://localhost:8000
```

## Configuration

### Primary Configuration File

Location: `/opt/webops/.webops/config.env`

**System Configuration:**
```bash
WEBOPS_ROOT=/opt/webops
CONTROL_PANEL_DIR=/opt/webops/control-panel
DEPLOYMENTS_DIR=/opt/webops/deployments
SHARED_DIR=/opt/webops/shared
BACKUPS_DIR=/opt/webops/backups
WEBOPS_LOG_DIR=/var/log/webops
```

**Database Configuration:**
```bash
POSTGRES_ENABLED=true
POSTGRES_VERSION=14
POSTGRES_DATA_DIR=/opt/webops/postgresql/data
```

**Control Panel Configuration:**
```bash
CONTROL_PANEL_ENABLED=true
CONTROL_PANEL_PORT=8000
CONTROL_PANEL_HOST=0.0.0.0
```

**Security Configuration:**
```bash
# Firewall
ENABLE_FIREWALL=true

# SSH Hardening
ENABLE_SSH_HARDENING=true
PERMIT_ROOT_LOGIN=prohibit-password  # Options: no, yes, prohibit-password
SSH_PASSWORD_AUTH=no                  # Options: yes, no
SSH_MAX_AUTH_TRIES=3

# Automatic Updates
ENABLE_AUTO_UPDATES=false
```

**Feature Flags:**
```bash
ENABLE_KUBERNETES=false
ENABLE_KVM=false
ENABLE_PATRONI=false
```

### Control Panel Environment

Location: `/opt/webops/control-panel/.env`

**Key environment variables:**
```bash
# Django
DEBUG=False
SECRET_KEY=<auto-generated>
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://webops:webops@localhost:5432/webops

# Celery & Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
REDIS_URL=redis://localhost:6379/3

# Security
ENCRYPTION_KEY=<auto-generated>

# WebOps
WEBOPS_INSTALL_PATH=/opt/webops
MIN_PORT=8001
MAX_PORT=9000
```

### Service Configuration

WebOps services are managed by systemd.

**Service Locations:**
- Service files: `/etc/systemd/system/webops-*.service`
- Logs: `sudo journalctl -u webops-web`

**Common service operations:**
```bash
# Check status
sudo systemctl status webops-web
sudo systemctl status webops-worker
sudo systemctl status webops-beat
sudo systemctl status webops-channels

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

# View recent errors
sudo journalctl -u webops-web -p err -n 50
```

## Verification

### Automated Verification

The installer runs automated health checks. To manually verify:

```bash
# Run platform validation
/opt/webops/.webops/versions/v1.0.0/bin/webops validate

# Check installation state
/opt/webops/.webops/versions/v1.0.0/bin/webops state
```

**Expected output:**
```
WebOps Installation State
========================

Installation Root: /opt/webops
Version: v1.0.0

Installed Components:
  base-system          ✓ installed
  postgresql           ✓ installed (version 14)
  redis                ✓ installed
  django-control-panel ✓ installed

Service Status:
  postgresql           ✓ running
  redis-server         ✓ running
  webops-web           ✓ running
  webops-worker        ✓ running
  webops-beat          ✓ running
  webops-channels      ✓ running

Health Checks:
  PostgreSQL connectivity   ✓ passed
  Redis connectivity        ✓ passed
  Control panel port 8000   ✓ listening
  Database migrations       ✓ up to date
```

### Manual Verification Steps

#### Step 1: Check Service Status

```bash
# All services should show "active (running)"
sudo systemctl status postgresql
sudo systemctl status redis-server
sudo systemctl status webops-web
sudo systemctl status webops-worker
sudo systemctl status webops-beat
```

#### Step 2: Test PostgreSQL Connection

```bash
# Connect to PostgreSQL
sudo -u postgres psql webops -c "SELECT version();"

# Check tables exist
sudo -u postgres psql webops -c "\dt"

# Should show Django tables (auth_user, django_migrations, etc.)
```

#### Step 3: Test Redis Connection

```bash
# Ping Redis
redis-cli ping
# Expected: PONG

# Check Redis info
redis-cli info server
```

#### Step 4: Test Web Access

```bash
# Get your server IP
hostname -I | awk '{print $1}'

# Test HTTP access (should return HTML)
curl http://localhost:8000/

# Check from external machine (replace YOUR_IP)
curl http://YOUR_IP:8000/

# Or open in browser:
# http://YOUR_IP:8000/
```

#### Step 5: Test Celery Workers

```bash
cd /opt/webops/control-panel

# Check Celery workers
sudo -u webops ./venv/bin/celery -A config.celery_app inspect active

# Check registered tasks
sudo -u webops ./venv/bin/celery -A config.celery_app inspect registered

# Should show tasks like:
# apps.deployments.tasks.deploy_service
# apps.deployments.tasks.health_check
```

#### Step 6: Check Firewall

```bash
# Ubuntu/Debian
sudo ufw status verbose

# Rocky/AlmaLinux
sudo firewall-cmd --list-all

# Should show:
# - 22/tcp (SSH) ALLOW
# - 80/tcp (HTTP) ALLOW
# - 443/tcp (HTTPS) ALLOW
# - 8000/tcp (Control Panel) ALLOW
```

#### Step 7: Check Disk Usage

```bash
# Check installation size
du -sh /opt/webops

# Check available space
df -h /opt
```

## Troubleshooting

### Common Installation Issues

#### Issue 1: Port Already in Use

**Error:** `Address already in use: ('0.0.0.0', 8000)`

**Diagnosis:**
```bash
# Find what's using the port
sudo ss -tulpn | grep :8000
```

**Solutions:**

**Option 1: Stop conflicting service**
```bash
sudo systemctl stop <conflicting-service>
sudo systemctl restart webops-web
```

**Option 2: Change WebOps port**
```bash
# Edit config
sudo nano /opt/webops/.webops/config.env

# Change port
CONTROL_PANEL_PORT=8001

# Update control panel .env
sudo nano /opt/webops/control-panel/.env
# Update any port references

# Update firewall
sudo ufw allow 8001/tcp  # Ubuntu/Debian
sudo firewall-cmd --add-port=8001/tcp --permanent && sudo firewall-cmd --reload  # Rocky/AlmaLinux

# Restart service
sudo systemctl restart webops-web
```

#### Issue 2: PostgreSQL Connection Failed

**Error:** `could not connect to server: Connection refused`

**Diagnosis:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check if PostgreSQL is listening
sudo ss -tulpn | grep 5432

# Check logs
sudo journalctl -u postgresql -n 50
```

**Solutions:**

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Enable autostart
sudo systemctl enable postgresql

# Check if database exists
sudo -u postgres psql -l | grep webops

# Create database if missing
sudo -u postgres createdb webops

# Test connection
sudo -u postgres psql webops -c "SELECT 1;"
```

#### Issue 3: Redis Connection Failed

**Error:** `Error connecting to Redis`

**Diagnosis:**
```bash
# Check Redis status
sudo systemctl status redis-server  # Ubuntu/Debian
sudo systemctl status redis          # Rocky/AlmaLinux

# Test connection
redis-cli ping
```

**Solutions:**
```bash
# Start Redis
sudo systemctl start redis-server  # Ubuntu/Debian
sudo systemctl start redis          # Rocky/AlmaLinux

# Enable autostart
sudo systemctl enable redis-server

# Check Redis configuration
sudo nano /etc/redis/redis.conf
# Ensure: bind 127.0.0.1
```

#### Issue 4: Permission Denied Errors

**Error:** `Permission denied` when accessing files

**Diagnosis:**
```bash
# Check ownership
ls -la /opt/webops/control-panel/

# Check webops user exists
id webops
```

**Solutions:**
```bash
# Fix ownership
sudo chown -R webops:webops /opt/webops/control-panel
sudo chown -R webops:webops /opt/webops/deployments
sudo chown -R webops:webops /opt/webops/data

# Fix permissions
sudo chmod -R 755 /opt/webops/control-panel
sudo chmod -R 750 /opt/webops/.secrets

# Restart services
sudo systemctl restart webops-web webops-worker
```

#### Issue 5: Static Files Not Loading

**Problem:** CSS/JS not loading, admin panel looks broken

**Solutions:**
```bash
cd /opt/webops/control-panel

# Collect static files
sudo -u webops ./venv/bin/python manage.py collectstatic --noinput

# Check static files directory
ls -la /opt/webops/control-panel/staticfiles/

# Restart web service
sudo systemctl restart webops-web
```

#### Issue 6: Celery Workers Not Running

**Problem:** Background tasks not processing

**Diagnosis:**
```bash
# Check worker status
sudo systemctl status webops-worker

# Check worker logs
sudo journalctl -u webops-worker -n 50
```

**Solutions:**
```bash
# Restart worker
sudo systemctl restart webops-worker

# Check Redis connectivity
redis-cli ping

# Verify Celery can connect to Redis
cd /opt/webops/control-panel
sudo -u webops ./venv/bin/python manage.py shell
>>> from django.conf import settings
>>> print(settings.CELERY_BROKER_URL)
>>> exit()
```

#### Issue 7: SSH Locked Out

**Problem:** Cannot connect via SSH after installation

**Solutions:**

**Option 1: Use console/VNC access**
```bash
# Login via console
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Temporarily allow password auth
PasswordAuthentication yes

# Restart SSH
sudo systemctl restart sshd

# Re-setup SSH keys
# Then disable password auth again
```

**Option 2: Use SSH recovery script**
```bash
# From console/VNC
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops restore-ssh

# This restores SSH to defaults
```

#### Issue 8: Installation Interrupted

**Problem:** Installation was stopped mid-way

**Solution:**
```bash
# Check install state
cat /opt/webops/.webops/.install_state

# Resume installation
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/resume.sh

# Or force restart from beginning
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/resume.sh --force
```

### Health Check Failed

If automated health checks fail during installation:

**PostgreSQL not running:**
```bash
sudo systemctl start postgresql
sudo systemctl status postgresql
```

**Redis not responding:**
```bash
sudo systemctl start redis-server
sudo systemctl status redis-server
redis-cli ping
```

**Control panel not listening:**
```bash
sudo systemctl status webops-web
sudo journalctl -u webops-web -n 50
sudo systemctl restart webops-web
```

**Services not running:**
```bash
# Restart all WebOps services
sudo systemctl restart webops-web webops-worker webops-beat webops-channels

# Check status
sudo systemctl status webops-web webops-worker webops-beat webops-channels
```

### Getting Help

If issues persist:

1. **Check logs:**
   ```bash
   # Installation log
   sudo tail -100 /var/log/webops/install-*.log

   # Service logs
   sudo journalctl -u webops-web -n 100
   sudo journalctl -u webops-worker -n 100
   ```

2. **Run validation:**
   ```bash
   sudo /opt/webops/.webops/versions/v1.0.0/bin/webops validate
   ```

3. **Check platform state:**
   ```bash
   /opt/webops/.webops/versions/v1.0.0/bin/webops state
   ```

4. **Use repair script:**
   ```bash
   sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/repair.sh
   ```

5. **Report issues:**
   - GitHub: https://github.com/DagiiM/webops/issues
   - Include: OS version, installation log, error messages

## Advanced Topics

### Custom Installation Location

To install in a custom location (not recommended):

```bash
# Set custom installation root
export WEBOPS_INSTALL_ROOT=/custom/path

# Run installer with environment preserved
sudo -E ./.webops/versions/v1.0.0/lifecycle/install.sh
```

**Important:** All paths in config.env will use the custom location.

### Customizing Security Settings

Before running the installer, you can customize security settings:

**Option 1: Set environment variables**
```bash
export ENABLE_SSH_HARDENING=false
export PERMIT_ROOT_LOGIN=yes
export SSH_PASSWORD_AUTH=yes
sudo -E ./.webops/versions/v1.0.0/lifecycle/install.sh
```

**Option 2: Edit config after installation**
```bash
# Let installer create config.env
# Then edit before components are installed
sudo nano /opt/webops/.webops/config.env
```

**SSH Hardening Options:**

```bash
# Disable SSH hardening completely
ENABLE_SSH_HARDENING=false

# Allow root login with password
PERMIT_ROOT_LOGIN=yes
SSH_PASSWORD_AUTH=yes

# Allow root login with keys only (default)
PERMIT_ROOT_LOGIN=prohibit-password
SSH_PASSWORD_AUTH=no

# Disable root login entirely
PERMIT_ROOT_LOGIN=no
SSH_PASSWORD_AUTH=no
```

### Skipping Auto-Relocation

If you want to install from the current location without relocation:

```bash
# Set flag to skip relocation
export WEBOPS_ALREADY_RELOCATED=true

# Run installer
sudo -E ./.webops/versions/v1.0.0/lifecycle/install.sh
```

**Warning:** This is not recommended unless you have a specific reason. Paths in config.env will be based on the current directory.

### Component-by-Component Installation

For advanced users who want granular control:

```bash
# Step 1: Create configuration
sudo mkdir -p /opt/webops/.webops
sudo cp .webops/versions/v1.0.0/config.env.template /opt/webops/.webops/config.env
sudo nano /opt/webops/.webops/config.env

# Step 2: Run validation
sudo /opt/webops/.webops/versions/v1.0.0/setup/validate.sh

# Step 3: Install base system
sudo /opt/webops/.webops/versions/v1.0.0/setup/base.sh

# Step 4: Install Django control panel
sudo /opt/webops/.webops/versions/v1.0.0/setup/django.sh

# Step 5: Add optional components
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops apply postgresql
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops apply monitoring
```

### Re-running Installation

If you need to re-run the installer on an existing installation:

**The installer will detect the existing installation and warn you:**
```
⚠️  WARNING: Existing WebOps installation detected
Config file exists: /opt/webops/.webops/config.env

Running install again may:
  • Overwrite existing configuration
  • Reset SSH settings
  • Restart services (causing downtime)

If you want to:
  • Update: Use '/opt/webops/.webops/versions/v1.0.0/bin/webops update' instead
  • Repair: Use '/opt/webops/.webops/versions/v1.0.0/lifecycle/repair.sh' instead
  • Reinstall: Remove /opt/webops/.webops/config.env first

Continue anyway? (type 'yes' to proceed):
```

**To proceed with re-installation:**
1. Type `yes` when prompted, OR
2. Remove the config file: `sudo rm /opt/webops/.webops/config.env`

**Recommended alternatives:**
```bash
# For updates
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops update

# For repairs
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/repair.sh

# For complete removal and fresh install
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh
sudo rm -rf /opt/webops
# Then run installer again
```

## Uninstallation

### Standard Uninstallation

Removes WebOps but keeps data and configurations:

```bash
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh
```

**What is removed:**
- All systemd services
- Firewall rules
- WebOps user (services only, data kept)

**What is kept:**
- PostgreSQL database and data
- Deployed applications
- Configuration files
- Backup data

### Complete Removal

**WARNING: This deletes ALL data including databases and deployments!**

```bash
# Complete removal including all data
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh --purge

# This removes:
# - All services
# - All databases
# - All deployed applications
# - All configuration files
# - All backup data
# - The entire /opt/webops directory
```

### Manual Cleanup

If uninstall script fails, manual cleanup:

```bash
# Stop all services
sudo systemctl stop webops-*
sudo systemctl disable webops-*

# Remove service files
sudo rm /etc/systemd/system/webops-*.service
sudo systemctl daemon-reload

# Remove WebOps directory
sudo rm -rf /opt/webops

# Remove PostgreSQL database (optional)
sudo -u postgres dropdb webops

# Remove webops user (optional)
sudo userdel webops

# Remove firewall rules (optional)
sudo ufw delete allow 8000/tcp
```

## Next Steps

After successful installation:

### 1. Secure Your Installation

```bash
# Change admin password (via web UI)
# - Login to http://YOUR_IP:8000/
# - Navigate to profile settings
# - Change password

# Enable 2FA (recommended)
# - Navigate to security settings
# - Enable Two-Factor Authentication
# - Scan QR code with authenticator app

# Configure secure session timeout
sudo nano /opt/webops/control-panel/.env
# Set: SESSION_COOKIE_AGE=3600  # 1 hour
```

### 2. Configure Backups

```bash
# Edit backup configuration
sudo nano /opt/webops/.webops/config.env

# Enable and configure backups
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 3 * * *"  # Daily at 3 AM
BACKUP_RETENTION_DAYS=30

# Restart services to apply
sudo systemctl restart webops-worker
```

### 3. Deploy Your First Application

**Via Web Interface:**
1. Login to control panel: http://YOUR_IP:8000/
2. Navigate to "Deployments" → "New Deployment"
3. Fill in deployment form:
   - Service name: `my-app`
   - Repository URL: `https://github.com/username/repo`
   - Branch: `main`
   - Domain: `app.example.com` (optional)
4. Click "Deploy" and monitor progress

**Via CLI (if installed):**
```bash
webops deploy \
  --name my-app \
  --repo https://github.com/username/repo \
  --branch main \
  --domain app.example.com
```

### 4. Set Up Monitoring (Optional)

```bash
# Install monitoring stack
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops apply monitoring

# Access monitoring:
# - Prometheus: http://YOUR_IP:9090/
# - Grafana: http://YOUR_IP:3000/
```

### 5. Read the Documentation

- **Main README**: `/opt/webops/README.md` - Complete feature overview
- **Control Panel Docs**: `/opt/webops/control-panel/CLAUDE.md` - Development guide
- **API Documentation**: `http://YOUR_IP:8000/api/docs/` - REST API reference
- **CLI Documentation**: `/opt/webops/cli/README.md` - CLI usage guide

### 6. Platform Management

```bash
# Check platform status
/opt/webops/.webops/versions/v1.0.0/bin/webops state

# Validate installation
/opt/webops/.webops/versions/v1.0.0/bin/webops validate

# Update platform
/opt/webops/.webops/versions/v1.0.0/bin/webops update

# Rollback to previous version
/opt/webops/.webops/versions/v1.0.0/bin/webops rollback

# Repair broken installation
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/repair.sh
```

## Platform Management Commands

Quick reference for managing your WebOps installation:

```bash
# Status and validation
/opt/webops/.webops/versions/v1.0.0/bin/webops state      # Check installation state
/opt/webops/.webops/versions/v1.0.0/bin/webops validate   # Validate configuration

# Service management
sudo systemctl status webops-web          # Check web service
sudo systemctl restart webops-web         # Restart web service
sudo systemctl status webops-worker       # Check worker service
sudo systemctl restart webops-worker      # Restart worker service

# Logs
sudo journalctl -u webops-web -f          # Follow web logs
sudo journalctl -u webops-worker -f       # Follow worker logs
sudo journalctl -u webops-web -p err      # Show errors only

# Lifecycle
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops update        # Update platform
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops rollback      # Rollback version
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/repair.sh      # Repair installation
sudo /opt/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh   # Uninstall

# SSH recovery
sudo /opt/webops/.webops/versions/v1.0.0/bin/webops restore-ssh   # Restore SSH config
```

---

## Installation Complete!

**You have successfully installed WebOps Platform v1.0.0!**

**Access your control panel:** http://YOUR_IP:8000/

**Admin credentials:** `sudo cat /opt/webops/.secrets/admin_credentials.txt`

**Platform location:** `/opt/webops/`

**Need help?**
- Documentation: `/opt/webops/README.md`
- Issues: https://github.com/DagiiM/webops/issues
- Logs: `sudo journalctl -u webops-web -f`

**Enjoy using WebOps! 🚀**
