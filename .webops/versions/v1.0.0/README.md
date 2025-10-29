# WebOps Platform Installation Package v1.0.0

A production-ready, self-hosted VPS hosting platform with enterprise-grade security, high availability addons, and comprehensive automation.

## Quick Start

```bash
# As root or with sudo
cd /home/douglas/webops
sudo ./.webops/versions/v1.0.0/lifecycle/install.sh
```

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Addons](#addons)
- [Management](#management)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## Overview

WebOps Platform v1.0.0 is a mission-critical hosting infrastructure that transforms a fresh VPS into a fully-functional deployment system with:

- **Base System Hardening**: SSH hardening, firewall, kernel tuning, security updates
- **PostgreSQL Database**: Standalone or HA with Patroni
- **Django Control Panel**: Web-based management interface
- **Celery Task Queue**: Background job processing with Redis
- **Nginx Reverse Proxy**: Automatic SSL with Let's Encrypt
- **High Availability**: etcd, Patroni, Kubernetes addons
- **Monitoring Stack**: Prometheus, Grafana, node exporter
- **Virtualization**: KVM support for nested deployments

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| OS | Ubuntu 20.04/22.04/24.04, Debian 11/12, Rocky/AlmaLinux 8/9 |
| CPU | 2 cores |
| RAM | 2 GB |
| Disk | 20 GB free space |
| Network | Internet connectivity, DNS resolution |
| Init | systemd (required) |

### Recommended for Production

| Component | Recommendation |
|-----------|----------------|
| CPU | 4+ cores |
| RAM | 8+ GB |
| Disk | 100+ GB SSD |
| Network | Static IP, domain name |

### Required System Features

- systemd for service management
- Root or sudo access
- Internet connectivity for package installation
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)

## Installation Methods

### Method 1: Full Installation (Recommended)

Installs base system + all enabled addons from configuration:

```bash
# 1. Configure your installation
cd /home/douglas/webops/.webops
cp versions/v1.0.0/config.env.template config.env
nano config.env  # Edit configuration

# 2. Run installation
sudo versions/v1.0.0/lifecycle/install.sh
```

### Method 2: Minimal Installation

Install base system only, add components later:

```bash
# Install with minimal config
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops install
```

### Method 3: Custom Installation

Install base + specific addons:

```bash
# Install base system
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops install

# Add specific addons
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply postgresql
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply monitoring
```

### Resume Interrupted Installation

If installation is interrupted:

```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/resume.sh
```

## Architecture

### Directory Structure

```
/home/douglas/webops/.webops/versions/v1.0.0/
├── bin/
│   └── webops              # Main CLI interface
├── lifecycle/
│   ├── install.sh          # Main installer
│   ├── resume.sh           # Resume interrupted install
│   ├── repair.sh           # Repair broken installation
│   └── uninstall.sh        # Clean uninstall
├── setup/
│   ├── base.sh             # Base system hardening
│   └── validate.sh         # Pre-flight checks
├── lib/
│   ├── common.sh           # Shared utilities
│   ├── state.sh            # State management
│   ├── os.sh               # OS abstraction layer
│   └── addon-contract.sh   # Addon security contracts
├── os/
│   ├── ubuntu.sh           # Ubuntu-specific handlers
│   ├── debian.sh           # Debian-specific handlers
│   └── rocky.sh            # Rocky Linux handlers
├── addons/
│   ├── postgresql.sh       # PostgreSQL database
│   ├── etcd.sh            # Distributed key-value store
│   ├── patroni.sh         # PostgreSQL HA
│   ├── kubernetes.sh      # K3s Kubernetes
│   ├── kvm.sh             # Hardware virtualization
│   ├── monitoring.sh      # Prometheus + Grafana
│   └── autorecovery.sh    # Auto-recovery system
├── systemd/               # Systemd service templates
├── contracts/             # Addon security contracts
└── config.env.template    # Configuration template
```

### Installation Flow

1. **Pre-flight Validation** - Check system requirements
2. **Base System Setup** - Install essential packages
3. **Security Hardening** - SSH, firewall, kernel tuning
4. **User & Permissions** - Create webops system user
5. **Addon Installation** - Install enabled addons
6. **Service Configuration** - Setup and start services
7. **State Recording** - Track installation status

## Configuration

### Quick Configuration

Edit `config.env` to customize your installation:

```bash
# Copy template
cp /home/douglas/webops/.webops/versions/v1.0.0/config.env.template \
   /home/douglas/webops/.webops/config.env

# Edit configuration
nano /home/douglas/webops/.webops/config.env
```

### Key Configuration Options

#### Platform Settings

```bash
WEBOPS_VERSION=v1.0.0
WEBOPS_ROOT=/webops
WEBOPS_DATA_DIR=/webops/data
WEBOPS_LOG_DIR=/webops/logs
WEBOPS_BACKUP_DIR=/webops/backups
```

#### Security Settings

```bash
ENCRYPTION_KEY=your-32-char-encryption-key
JWT_SECRET=your-32-char-jwt-secret
ENABLE_2FA=false
PASSWORD_MIN_LENGTH=12
```

#### Database Configuration

```bash
DATABASE_BACKEND=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=webops
DB_USER=webops
DB_PASSWORD=change-this-password
```

#### Control Panel

```bash
CONTROL_PANEL_PORT=8009
CONTROL_PANEL_HOST=0.0.0.0
CONTROL_PANEL_SSL=false
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1
```

#### Feature Flags

```bash
FEATURE_AUTOMATION=true
FEATURE_LLM_DEPLOYMENT=true
FEATURE_KUBERNETES=true
FEATURE_MONITORING=true
FEATURE_BACKUP=true
```

### Generate Secrets

```bash
# Encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT secret
openssl rand -hex 32

# Django secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Addons

### Available Addons

| Addon | Description | Dependencies |
|-------|-------------|--------------|
| **postgresql** | PostgreSQL 15 database | None |
| **etcd** | Distributed key-value store | None |
| **patroni** | PostgreSQL HA with Patroni + PgBouncer | postgresql, etcd |
| **kubernetes** | K3s lightweight Kubernetes | etcd |
| **kvm** | Hardware virtualization support | None |
| **monitoring** | Prometheus + Grafana + Node Exporter | None |
| **autorecovery** | Automatic service recovery | None |

### Installing Addons

```bash
# List available addons
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops help

# Install a specific addon
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply <addon-name>

# Examples
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply postgresql
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply monitoring
```

### Removing Addons

```bash
# Remove addon (keep data)
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops uninstall <addon-name>

# Remove addon and data (use with caution)
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops uninstall <addon-name> --purge
```

### Addon Dependencies

Some addons have dependencies that must be installed first:

```bash
# For Patroni HA setup
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply postgresql
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply etcd
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply patroni

# For Kubernetes
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply etcd
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply kubernetes
```

## Management

### WebOps CLI

The `webops` CLI provides comprehensive platform management:

```bash
# Check installation status
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops state

# Validate system
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops validate

# Show version
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops version

# Get help
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops help
```

### Common Management Tasks

#### Check System Status

```bash
# Platform state
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops state

# Service status
sudo systemctl status webops-web
sudo systemctl status webops-worker
sudo systemctl status webops-beat
```

#### View Logs

```bash
# Installation logs
cat /var/log/webops/install-*.log

# Service logs
sudo journalctl -u webops-web -f
sudo journalctl -u webops-worker -f
```

#### Restart Services

```bash
# Restart all WebOps services
sudo systemctl restart webops-web
sudo systemctl restart webops-worker
sudo systemctl restart webops-beat
```

### Version Management

```bash
# Check current version
/home/douglas/webops/.webops/versions/v1.0.0/bin/webops version

# Rollback to previous version (when available)
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops rollback <version>
```

## Troubleshooting

### Common Issues

#### Installation Fails

```bash
# Run validation
sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops validate

# Check logs
cat /var/log/webops/install-*.log
```

#### Service Won't Start

```bash
# Check service status
sudo systemctl status webops-web

# View detailed logs
sudo journalctl -xe -u webops-web
```

#### Port Already in Use

```bash
# Check what's using port 80/443
sudo ss -tulpn | grep :80
sudo ss -tulpn | grep :443

# Stop conflicting service
sudo systemctl stop apache2  # or nginx
```

#### Database Connection Fails

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -c "SELECT version();"
```

### Repair Installation

If installation is broken:

```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/repair.sh
```

### Clean Uninstall

```bash
# Uninstall platform (keep data)
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh

# Complete removal including data
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/uninstall.sh --purge
```

## Security

### Security Hardening Applied

The installation automatically applies:

1. **SSH Hardening**
   - Disable root login
   - Disable password authentication
   - Limit max auth tries
   - Enable public key authentication only

2. **Firewall Configuration**
   - Default deny incoming
   - Allow SSH, HTTP, HTTPS
   - UFW (Ubuntu/Debian) or firewalld (RHEL-based)

3. **Kernel Hardening**
   - Disable IP forwarding
   - Enable SYN cookies
   - Disable source routing
   - Enable reverse path filtering

4. **System Limits**
   - Increase file descriptor limits
   - Configure process limits
   - Memory limits for webops user

5. **Automatic Updates**
   - Security updates (Ubuntu/Debian)
   - Configurable via ENABLE_AUTO_UPDATES

### Security Best Practices

1. **Change Default Passwords**
   ```bash
   # Generate strong passwords
   openssl rand -base64 32
   ```

2. **Enable 2FA**
   ```bash
   # In config.env
   ENABLE_2FA=true
   ```

3. **Configure SSL**
   ```bash
   # In config.env
   CONTROL_PANEL_SSL=true
   LETSENCRYPT_EMAIL=admin@yourdomain.com
   ```

4. **Regular Backups**
   ```bash
   # In config.env
   BACKUP_ENABLED=true
   BACKUP_SCHEDULE="0 3 * * *"
   ```

5. **Monitor Logs**
   ```bash
   # Enable monitoring addon
   sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops apply monitoring
   ```

## Additional Resources

- **Main Project**: `/home/douglas/webops/README.md`
- **Contributing**: `/home/douglas/webops/CONTRIBUTING.md`
- **Documentation**: `/home/douglas/webops/docs/`
- **Control Panel**: `/home/douglas/webops/control-panel/`
- **CLI Tool**: `/home/douglas/webops/cli/`

## Support

For issues, questions, or contributions:

1. Check the troubleshooting section above
2. Review `/home/douglas/webops/docs/` for detailed documentation
3. Check logs in `/var/log/webops/`
4. Report issues on GitHub: https://github.com/DagiiM/webops

## License

See the main project LICENSE file for details.

---

**WebOps Platform v1.0.0** - Enterprise-grade VPS hosting infrastructure
