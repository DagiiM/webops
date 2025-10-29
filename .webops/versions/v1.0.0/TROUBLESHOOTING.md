# WebOps Platform Troubleshooting Guide

Comprehensive troubleshooting guide for WebOps Platform v1.0.0.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Service Issues](#service-issues)
3. [Database Issues](#database-issues)
4. [Network Issues](#network-issues)
5. [Performance Issues](#performance-issues)
6. [Deployment Issues](#deployment-issues)
7. [Diagnostic Commands](#diagnostic-commands)

## Installation Issues

### Installation Fails During Pre-Flight Validation

**Symptoms:**
- Installation stops at validation stage
- Error messages about missing requirements

**Diagnostic:**
```bash
sudo /home/douglas/webops/.webops/versions/v1.0.0/setup/validate.sh
```

**Common Causes & Solutions:**

1. **Insufficient Resources**
   ```bash
   # Check resources
   free -h        # Memory (need 2GB+)
   nproc          # CPUs (need 2+)
   df -h /        # Disk space (need 20GB+)
   ```

2. **systemd Not Available**
   ```bash
   # Check systemd
   systemctl --version
   # If missing, WebOps requires systemd - consider using a different OS
   ```

3. **No Internet Connectivity**
   ```bash
   # Test connectivity
   ping -c 3 8.8.8.8
   # Check DNS
   nslookup google.com
   ```

### Installation Freezes or Hangs

**Symptoms:**
- Installation stops responding
- No progress for 5+ minutes

**Solution:**
```bash
# 1. Cancel installation (Ctrl+C)

# 2. Check what's running
ps aux | grep -E '(apt|yum|dnf|install)'

# 3. Check logs
cat /var/log/webops/install-*.log

# 4. Resume installation
sudo /home/douglas/webops/.webops/versions/v1.0.0/lifecycle/resume.sh
```

### Permission Denied Errors

**Symptoms:**
- `Permission denied` errors during installation
- Cannot create directories or files

**Solution:**
```bash
# Ensure running as root
sudo su

# Check directory permissions
ls -la /home/douglas/webops/.webops/

# Fix permissions if needed
chown -R root:root /home/douglas/webops/.webops/
chmod -R 755 /home/douglas/webops/.webops/
```

### Package Installation Fails

**Symptoms:**
- Errors installing apt/yum packages
- Dependency resolution failures

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -f  # Fix broken dependencies
sudo dpkg --configure -a # Configure pending packages

# Rocky/AlmaLinux
sudo dnf clean all
sudo dnf update
```

## Service Issues

### webops-web Won't Start

**Symptoms:**
- `systemctl status webops-web` shows failed
- Cannot access control panel

**Diagnostic:**
```bash
# Check service status
sudo systemctl status webops-web

# View detailed logs
sudo journalctl -xe -u webops-web

# Check if port is in use
sudo ss -tulpn | grep :8000
```

**Common Causes & Solutions:**

1. **Port Already in Use**
   ```bash
   # Find what's using the port
   sudo lsof -i :8000

   # Stop conflicting service
   sudo systemctl stop <service-name>

   # Or change WebOps port
   sudo nano /home/douglas/webops/.webops/config.env
   # Set: CONTROL_PANEL_PORT=8001

   # Restart service
   sudo systemctl restart webops-web
   ```

2. **Database Not Running**
   ```bash
   # Check PostgreSQL
   sudo systemctl status postgresql

   # Start if stopped
   sudo systemctl start postgresql

   # Restart webops-web
   sudo systemctl restart webops-web
   ```

3. **Virtualenv Issues**
   ```bash
   # Recreate virtualenv
   cd /home/douglas/webops/control-panel
   rm -rf venv
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ./venv/bin/pip install gunicorn

   # Restart service
   sudo systemctl restart webops-web
   ```

4. **Python Import Errors**
   ```bash
   # Test Django manually
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/python manage.py check

   # Check for missing dependencies
   sudo -u webops ./venv/bin/pip list
   ```

### webops-worker Won't Start

**Symptoms:**
- Celery worker service failed
- Background tasks not processing

**Diagnostic:**
```bash
sudo systemctl status webops-worker
sudo journalctl -xe -u webops-worker
```

**Solutions:**

1. **Redis Not Running**
   ```bash
   sudo systemctl status redis-server  # Ubuntu/Debian
   sudo systemctl status redis         # Rocky/AlmaLinux

   # Start Redis
   sudo systemctl start redis-server
   sudo systemctl restart webops-worker
   ```

2. **Celery Configuration Issues**
   ```bash
   # Test Celery manually
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/celery -A config.celery_app inspect ping

   # Check broker connectivity
   redis-cli ping
   ```

### Service Starts But Crashes Immediately

**Symptoms:**
- Service shows active then immediately fails
- Repeated crash loops

**Diagnostic:**
```bash
# Watch service logs in real-time
sudo journalctl -f -u webops-web

# Check system logs
sudo tail -f /var/log/syslog

# Check for OOM killer
sudo dmesg | grep -i "out of memory"
```

**Solutions:**

1. **Out of Memory**
   ```bash
   # Check memory usage
   free -h

   # Adjust service memory limits
   sudo systemctl edit webops-web
   # Add:
   [Service]
   MemoryLimit=4G

   # Reload and restart
   sudo systemctl daemon-reload
   sudo systemctl restart webops-web
   ```

2. **Configuration Errors**
   ```bash
   # Validate Django settings
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/python manage.py check --deploy
   ```

## Database Issues

### Cannot Connect to PostgreSQL

**Symptoms:**
- Database connection refused
- `FATAL: password authentication failed`

**Diagnostic:**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
sudo -u postgres psql -c "SELECT version();"

# Check if webops database exists
sudo -u postgres psql -l | grep webops
```

**Solutions:**

1. **PostgreSQL Not Running**
   ```bash
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

2. **Wrong Credentials**
   ```bash
   # Reset webops user password
   sudo -u postgres psql -c "ALTER USER webops WITH PASSWORD 'newpassword';"

   # Update Django config
   sudo nano /home/douglas/webops/control-panel/.env
   # Update: DATABASE_URL=postgresql://webops:newpassword@localhost:5432/webops
   ```

3. **Database Doesn't Exist**
   ```bash
   sudo -u postgres createdb webops
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE webops TO webops;"
   ```

### Migration Failures

**Symptoms:**
- `python manage.py migrate` fails
- Database state inconsistent

**Solutions:**

1. **Fake Initial Migrations**
   ```bash
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/python manage.py migrate --fake-initial
   ```

2. **Reset Migrations (DANGER: Data Loss)**
   ```bash
   # Backup first!
   sudo -u postgres pg_dump webops > webops_backup.sql

   # Drop and recreate
   sudo -u postgres psql -c "DROP DATABASE webops;"
   sudo -u postgres psql -c "CREATE DATABASE webops OWNER webops;"

   # Run migrations
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/python manage.py migrate
   ```

### Database Disk Space Full

**Symptoms:**
- `ERROR: could not extend file`
- `No space left on device`

**Solutions:**
```bash
# Check disk space
df -h

# Find large files
sudo du -sh /var/lib/postgresql/* | sort -h

# Clean PostgreSQL logs (if safe)
sudo -u postgres psql -c "SELECT pg_rotate_logfile();"

# Vacuum database
sudo -u postgres psql webops -c "VACUUM FULL;"
```

## Network Issues

### Cannot Access Control Panel from Browser

**Symptoms:**
- Browser shows "Connection refused"
- Timeout when accessing control panel

**Diagnostic:**
```bash
# Check if service is listening
sudo ss -tulpn | grep :8000

# Test from server
curl http://localhost:8000/

# Check firewall
sudo ufw status                    # Ubuntu/Debian
sudo firewall-cmd --list-all       # Rocky/AlmaLinux
```

**Solutions:**

1. **Firewall Blocking**
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 8000/tcp
   sudo ufw reload

   # Rocky/AlmaLinux
   sudo firewall-cmd --permanent --add-port=8000/tcp
   sudo firewall-cmd --reload
   ```

2. **Wrong ALLOWED_HOSTS**
   ```bash
   # Update Django settings
   sudo nano /home/douglas/webops/control-panel/.env

   # Add your IP/domain
   ALLOWED_HOSTS=localhost,127.0.0.1,YOUR_IP_HERE

   # Restart service
   sudo systemctl restart webops-web
   ```

3. **Service Not Listening on Correct Interface**
   ```bash
   # Check binding
   sudo ss -tulpn | grep :8000

   # Should show 0.0.0.0:8000, not 127.0.0.1:8000

   # Update if needed
   sudo nano /home/douglas/webops/.webops/config.env
   CONTROL_PANEL_HOST=0.0.0.0
   ```

### SSL/TLS Certificate Issues

**Symptoms:**
- HTTPS not working
- Certificate errors in browser

**Solutions:**

1. **Let's Encrypt Certificate Renewal Failed**
   ```bash
   # Test renewal
   sudo certbot renew --dry-run

   # Force renewal
   sudo certbot renew --force-renewal

   # Check certificate status
   sudo certbot certificates
   ```

2. **Nginx Configuration Issues**
   ```bash
   # Test nginx config
   sudo nginx -t

   # Reload nginx
   sudo systemctl reload nginx
   ```

## Performance Issues

### Control Panel Slow to Respond

**Symptoms:**
- Pages take 5+ seconds to load
- API endpoints timeout

**Diagnostic:**
```bash
# Check system resources
top
htop  # if available
vmstat 1 10

# Check Django logs
tail -f /var/log/webops/gunicorn-access.log

# Check database performance
sudo -u postgres psql webops -c "SELECT * FROM pg_stat_activity;"
```

**Solutions:**

1. **High CPU Usage**
   ```bash
   # Increase Gunicorn workers
   sudo systemctl edit webops-web
   # Update: --workers 8

   # Reload service
   sudo systemctl daemon-reload
   sudo systemctl restart webops-web
   ```

2. **Slow Database Queries**
   ```bash
   # Enable query logging
   sudo nano /etc/postgresql/*/main/postgresql.conf
   # Add:
   log_min_duration_statement = 1000  # Log queries > 1sec

   # Restart PostgreSQL
   sudo systemctl restart postgresql

   # Run ANALYZE
   sudo -u postgres psql webops -c "ANALYZE;"
   ```

3. **Memory Issues**
   ```bash
   # Check for swapping
   vmstat 1 5

   # Add more swap if needed
   sudo fallocate -l 4G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile

   # Make persistent
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

### Celery Workers Slow or Stuck

**Symptoms:**
- Tasks pile up in queue
- Tasks take very long to complete

**Diagnostic:**
```bash
cd /home/douglas/webops/control-panel

# Check active tasks
sudo -u webops ./venv/bin/celery -A config.celery_app inspect active

# Check queue length
redis-cli llen celery

# Check worker stats
sudo -u webops ./venv/bin/celery -A config.celery_app inspect stats
```

**Solutions:**

1. **Increase Concurrency**
   ```bash
   sudo systemctl edit webops-worker
   # Update: --concurrency=8

   sudo systemctl daemon-reload
   sudo systemctl restart webops-worker
   ```

2. **Clear Stuck Tasks**
   ```bash
   # Purge all tasks (CAUTION!)
   cd /home/douglas/webops/control-panel
   sudo -u webops ./venv/bin/celery -A config.celery_app purge
   ```

## Deployment Issues

### Deployment Creation Fails

**Symptoms:**
- Error when creating new deployment
- Deployment stuck in pending state

**Diagnostic:**
```bash
# Check Celery worker logs
sudo journalctl -u webops-worker -f

# Check deployment task status
cd /home/douglas/webops/control-panel
sudo -u webops ./venv/bin/python manage.py shell
>>> from apps.deployments.models import BaseDeployment
>>> BaseDeployment.objects.filter(status='pending')
```

**Solutions:**

1. **Port Range Exhausted**
   ```bash
   # Check available ports
   sudo ss -tulpn | grep -E ':(80[0-9]{2}|90[0-9]{2})' | wc -l

   # Increase port range
   sudo nano /home/douglas/webops/control-panel/.env
   MAX_PORT=9999

   # Restart services
   sudo systemctl restart webops-web webops-worker
   ```

2. **Insufficient Permissions**
   ```bash
   # Check webops user permissions
   sudo -u webops ls -la /home/douglas/webops/deployments

   # Fix if needed
   sudo chown -R webops:webops /home/douglas/webops/deployments
   ```

## Diagnostic Commands

### Quick Health Check

```bash
#!/bin/bash
# WebOps health check script

echo "=== Service Status ==="
sudo systemctl status webops-web webops-worker webops-beat --no-pager

echo -e "\n=== PostgreSQL Status ==="
sudo systemctl status postgresql --no-pager

echo -e "\n=== Redis Status ==="
sudo systemctl status redis-server --no-pager 2>/dev/null || sudo systemctl status redis --no-pager

echo -e "\n=== Disk Space ==="
df -h /

echo -e "\n=== Memory Usage ==="
free -h

echo -e "\n=== Recent Errors ==="
sudo journalctl --since "10 minutes ago" -p err --no-pager | tail -20

echo -e "\n=== Port Status ==="
sudo ss -tulpn | grep -E ':(8000|5432|6379) '
```

### Collect Diagnostic Information

```bash
# Create diagnostic bundle
mkdir -p /tmp/webops-diagnostics

# System info
uname -a > /tmp/webops-diagnostics/system.txt
lsb_release -a >> /tmp/webops-diagnostics/system.txt

# Service status
sudo systemctl status webops-* > /tmp/webops-diagnostics/services.txt

# Logs
sudo journalctl -u webops-web --no-pager > /tmp/webops-diagnostics/webops-web.log
sudo journalctl -u webops-worker --no-pager > /tmp/webops-diagnostics/webops-worker.log

# Configuration (sanitized)
grep -v 'PASSWORD\|SECRET\|KEY' /home/douglas/webops/.webops/config.env > /tmp/webops-diagnostics/config.txt

# Create archive
tar -czf webops-diagnostics-$(date +%Y%m%d-%H%M%S).tar.gz -C /tmp webops-diagnostics/

echo "Diagnostic bundle created: webops-diagnostics-*.tar.gz"
```

## Getting Help

If you cannot resolve the issue:

1. **Check Installation State**
   ```bash
   /home/douglas/webops/.webops/versions/v1.0.0/bin/webops state
   ```

2. **Run Validation**
   ```bash
   sudo /home/douglas/webops/.webops/versions/v1.0.0/bin/webops validate
   ```

3. **Collect Logs**
   ```bash
   # View all WebOps logs
   sudo journalctl -u 'webops-*' --since today

   # Save logs to file
   sudo journalctl -u 'webops-*' --since today > webops-logs.txt
   ```

4. **Report Issue**
   - GitHub Issues: https://github.com/DagiiM/webops/issues
   - Include:
     - OS version
     - Installation method
     - Error messages
     - Relevant logs
     - Steps to reproduce

---

**Need more help?** Check the main documentation in `/home/douglas/webops/docs/`
