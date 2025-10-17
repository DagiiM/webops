# WebOps Troubleshooting Guide 🔧

**Comprehensive solutions for common issues and advanced troubleshooting**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

This guide covers troubleshooting for WebOps v2.0 with enterprise features. Most issues can be resolved quickly with the solutions below.

---

## 🚨 **Quick Diagnostics**

### **Health Check Command**
```bash
# Run comprehensive health check
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py health_check --report --fix-deployments

# Check system services
sudo systemctl status webops-web webops-celery nginx postgresql redis
```

### **Common Quick Fixes**
```bash
# Restart WebOps services
sudo systemctl restart webops-web webops-celery

# Clear cache and sessions
python manage.py clearsessions
redis-cli FLUSHDB

# Fix permissions
sudo chown -R webops:webops /opt/webops
sudo chmod +x /opt/webops/scripts/*.sh
```

---

## 🚀 **Installation Issues**

### **Issue: Installation Script Fails**

**Symptoms:**
- Installation script exits with error
- Missing dependencies
- Permission denied errors

**Solutions:**

1. **Check System Requirements:**
```bash
# Verify OS version
lsb_release -a  # Should be Ubuntu 22.04+ or Debian 11+

# Check available space
df -h  # Need at least 20GB free

# Verify internet connectivity
curl -I https://github.com
```

2. **Run with Proper Permissions:**
```bash
# Run as root or with sudo
sudo ./install.sh

# Or grant execute permissions
chmod +x install.sh
sudo ./install.sh
```

3. **Manual Dependency Installation:**
```bash
# Update package lists
sudo apt update

# Install required packages manually
sudo apt install -y python3.13 python3.13-venv python3-pip \
    postgresql postgresql-contrib redis-server nginx git

# Verify Python version
python3.13 --version  # Should be 3.13+
```

### **Issue: Database Connection Failed**

**Symptoms:**
- PostgreSQL connection errors
- Database authentication failures
- Migration errors

**Solutions:**

1. **Check PostgreSQL Status:**
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql  # If not running
```

2. **Verify Database Configuration:**
```bash
# Switch to postgres user
sudo -u postgres psql

# List databases and users
\l
\du

# Create database if missing
CREATE DATABASE webops_db;
CREATE USER webops WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE webops_db TO webops;
```

3. **Fix .env Configuration:**
```bash
# Check .env file
cat /opt/webops/control-panel/.env

# Correct DATABASE_URL format
DATABASE_URL=postgresql://webops:password@localhost:5432/webops_db
```

---

## 🌐 **Server Access Issues**

### **Issue: Server Returns 500 Error**

**Symptoms:**
- HTTP 500 Internal Server Error
- Django debug page (if DEBUG=True)
- Application won't start

**Solutions:**

1. **Check Application Logs:**
```bash
# View real-time logs
sudo journalctl -u webops-web -f

# Check specific log files
tail -f /opt/webops/control-panel/logs/webops.log
tail -f /var/log/nginx/error.log
```

2. **Common 500 Error Causes:**

**Missing Static Files:**
```bash
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py collectstatic --noinput
sudo systemctl restart webops-web
```

**Cache Issues:**
```bash
# Clear application cache
python manage.py clearsessions
redis-cli FLUSHDB

# Restart cache services
sudo systemctl restart redis-server
```

**Permission Issues:**
```bash
sudo chown -R webops:webops /opt/webops
sudo chmod 755 /opt/webops/control-panel/static
```

### **Issue: Can't Access WebOps Interface**

**Symptoms:**
- Connection refused
- Timeout errors
- DNS resolution failures

**Solutions:**

1. **Check Service Status:**
```bash
# Verify all services are running
sudo systemctl status webops-web nginx

# Check port bindings
sudo netstat -tlnp | grep :8000
sudo netstat -tlnp | grep :80
```

2. **Firewall Configuration:**
```bash
# Check UFW status
sudo ufw status

# Allow HTTP/HTTPS if blocked
sudo ufw allow 80
sudo ufw allow 443
sudo ufw reload
```

3. **Nginx Configuration:**
```bash
# Test nginx configuration
sudo nginx -t

# Check nginx logs
sudo tail -f /var/log/nginx/error.log

# Restart nginx if needed
sudo systemctl restart nginx
```

---

## 🚀 **Deployment Issues**

### **Issue: Deployment Stuck in "Building" Status**

**Symptoms:**
- Deployment shows "building" for extended time
- No progress in logs
- Process appears frozen

**Solutions:**

1. **Automatic Fix:**
```bash
# Use health check to fix stuck deployments
python manage.py health_check --fix-deployments
```

2. **Manual Investigation:**
```bash
# Check Celery worker status
sudo systemctl status webops-celery

# View Celery logs
sudo journalctl -u webops-celery -f

# Restart Celery workers
sudo systemctl restart webops-celery
```

3. **Reset Deployment:**
```bash
# Via management command
python manage.py reset_deployment deployment_name

# Or via admin interface
# Go to: https://webops.yourdomain.com/admin/deployments/deployment/
```

### **Issue: Git Clone Failures**

**Symptoms:**
- "Repository not found" errors
- "Permission denied" for private repos
- "Could not read Username" errors

**Solutions:**

1. **Public Repository Issues:**
```bash
# Test git clone manually
cd /tmp
git clone https://github.com/user/repo.git

# If fails, check internet connectivity
curl -I https://github.com
```

2. **Private Repository Setup:**
```bash
# Generate SSH key for webops user
sudo -u webops ssh-keygen -t ed25519 -C "webops@yourdomain.com"

# Add public key to GitHub
sudo -u webops cat /home/webops/.ssh/id_ed25519.pub
```

3. **Repository URL Validation:**
```python
# Use WebOps validation
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py shell

>>> from apps.core.utils import validate_repo_url
>>> validate_repo_url("https://github.com/user/repo")
True  # Should return True for valid URLs
```

### **Issue: Dependency Installation Failures**

**Symptoms:**
- pip install errors
- Missing system packages
- Compilation failures

**Solutions:**

1. **Common System Dependencies:**
```bash
# Install development headers
sudo apt install -y python3-dev libpq-dev build-essential

# For specific packages
sudo apt install -y libjpeg-dev zlib1g-dev  # Pillow
sudo apt install -y libxml2-dev libxslt1-dev  # lxml
sudo apt install -y libffi-dev  # cryptography
```

2. **Python Package Issues:**
```bash
# Update pip in virtual environment
cd /opt/webops/deployments/app-name
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# Clear pip cache
pip cache purge
```

3. **PostgreSQL Adapter Issues:**
```bash
# Install PostgreSQL development packages
sudo apt install -y postgresql-server-dev-all

# Alternative: Use psycopg2-binary
pip install psycopg2-binary
```

---

## 🗄️ **Database Issues**

### **Issue: Database Migration Failures**

**Symptoms:**
- Migration errors during deployment
- "relation does not exist" errors
- Schema inconsistencies

**Solutions:**

1. **Check Migration Status:**
```bash
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py showmigrations
```

2. **Force Migration:**
```bash
# Reset migrations (development only)
python manage.py migrate --fake-initial

# Or run specific migration
python manage.py migrate app_name migration_name
```

3. **Database Repair:**
```bash
# Backup first
pg_dump webops_db > backup.sql

# Drop and recreate (if safe)
sudo -u postgres dropdb webops_db
sudo -u postgres createdb webops_db -O webops
python manage.py migrate
```

### **Issue: Database Connection Pool Exhaustion**

**Symptoms:**
- "too many clients already" errors
- Connection timeouts
- Slow database responses

**Solutions:**

1. **Check Active Connections:**
```sql
-- Connect to PostgreSQL
sudo -u postgres psql webops_db

-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Kill idle connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname = 'webops_db' AND state = 'idle' AND query_start < now() - interval '1 hour';
```

2. **Optimize Connection Settings:**
```bash
# Edit PostgreSQL configuration
sudo nano /etc/postgresql/14/main/postgresql.conf

# Increase connection limits
max_connections = 200
shared_buffers = 256MB
```

---

## 🔐 **Security & Access Issues**

### **Issue: 2FA Setup Problems**

**Symptoms:**
- QR code doesn't work
- Invalid token errors
- Can't complete 2FA setup

**Solutions:**

1. **Verify Time Synchronization:**
```bash
# Check system time
timedatectl status

# Sync time if needed
sudo timedatectl set-ntp true
sudo systemctl restart systemd-timesyncd
```

2. **Reset 2FA:**
```bash
# Via Django admin
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from apps.core.models import TwoFactorAuth
>>> user = User.objects.get(username='admin')
>>> TwoFactorAuth.objects.filter(user=user).delete()
```

### **Issue: Rate Limiting Blocks Legitimate Users**

**Symptoms:**
- HTTP 429 Too Many Requests
- Unable to access after multiple attempts
- API calls rejected

**Solutions:**

1. **Check Rate Limit Status:**
```bash
# View current limits in admin panel
# Go to: https://webops.yourdomain.com/admin/

# Or check Redis cache
redis-cli keys "rate_limit:*"
redis-cli del "rate_limit:ip:192.168.1.100"
```

2. **Adjust Rate Limits:**
```bash
# Edit .env file
nano /opt/webops/control-panel/.env

# Modify limits (requests/window)
RATE_LIMIT_LOGIN=10/15min
RATE_LIMIT_API=200/hour
RATE_LIMIT_DEPLOYMENTS=20/hour
```

---

## 📊 **Performance Issues**

### **Issue: Slow Dashboard Loading**

**Symptoms:**
- Dashboard takes >5 seconds to load
- High CPU usage
- Database query timeouts

**Solutions:**

1. **Database Optimization:**
```sql
-- Connect to PostgreSQL
sudo -u postgres psql webops_db

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_deployment_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployment_created ON deployments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_deployment ON deployment_logs(deployment_id, created_at DESC);

-- Update statistics
ANALYZE;
```

2. **Enable Query Optimization:**
```python
# In settings.py
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['file'],
    'level': 'DEBUG',
    'propagate': False,
}
```

3. **Cache Configuration:**
```bash
# Increase Redis memory if needed
sudo nano /etc/redis/redis.conf
# maxmemory 256mb
sudo systemctl restart redis-server
```

### **Issue: High Memory Usage**

**Symptoms:**
- System runs out of memory
- Processes killed by OOM killer
- Swap usage high

**Solutions:**

1. **Monitor Memory Usage:**
```bash
# Check current usage
free -h
ps aux --sort=-%mem | head -10

# Check for memory leaks
sudo journalctl --since "1 hour ago" | grep -i "killed process"
```

2. **Optimize Django Settings:**
```python
# In settings.py
DATABASES['default']['CONN_MAX_AGE'] = 60
CONN_HEALTH_CHECKS = True

# Limit concurrent deployments
CELERY_WORKER_CONCURRENCY = 2
```

3. **Add Swap Space:**
```bash
# Create swap file (if needed)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 🌐 **SSL Certificate Issues**

### **Issue: SSL Certificate Renewal Fails**

**Symptoms:**
- Certificate expired warnings
- HTTPS not working
- Certbot renewal errors

**Solutions:**

1. **Manual Renewal:**
```bash
# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Check certificate status
sudo certbot certificates
```

2. **Fix Nginx Configuration:**
```bash
# Test nginx config
sudo nginx -t

# Check well-known path
sudo ls -la /var/www/html/.well-known/

# Create if missing
sudo mkdir -p /var/www/html/.well-known/acme-challenge
sudo chown www-data:www-data /var/www/html/.well-known/
```

3. **DNS Verification:**
```bash
# Check DNS propagation
nslookup webops.yourdomain.com
dig webops.yourdomain.com

# Verify domain ownership
curl -I http://webops.yourdomain.com/.well-known/acme-challenge/test
```

---

## 🧰 **Advanced Troubleshooting**

### **Debug Mode for Development**

```bash
# Enable debug mode (development only)
cd /opt/webops/control-panel
nano .env
# Set DEBUG=True

# View detailed error pages
python manage.py runserver --settings=config.settings_debug
```

### **Database Debugging**

```python
# Django shell debugging
python manage.py shell

# Check model integrity
>>> from apps.deployments.models import Deployment
>>> deployments = Deployment.objects.all()
>>> for d in deployments:
...     print(f"{d.name}: {d.status}")

# Raw SQL queries
>>> from django.db import connection
>>> cursor = connection.cursor()
>>> cursor.execute("SELECT COUNT(*) FROM deployments")
>>> cursor.fetchone()
```

### **Network Debugging**

```bash
# Check port bindings
sudo ss -tlnp

# Test internal connections
curl -v http://localhost:8000/health/
curl -v http://127.0.0.1:6379/  # Redis

# Check DNS resolution
nslookup webops.yourdomain.com
ping webops.yourdomain.com
```

### **Log Analysis**

```bash
# Comprehensive log analysis
sudo journalctl -u webops-web --since "1 hour ago" --no-pager

# Search for specific errors
sudo grep -r "ERROR" /opt/webops/control-panel/logs/
sudo grep -r "CRITICAL" /var/log/nginx/

# Real-time monitoring
sudo tail -f /opt/webops/control-panel/logs/webops.log \
    /var/log/nginx/access.log \
    /var/log/nginx/error.log
```

---

## 📞 **Getting Additional Help**

### **Collect System Information**
```bash
# Generate diagnostic report
cd /opt/webops/control-panel
python manage.py system_info > system_report.txt

# Include in support request:
cat system_report.txt
```

### **Support Channels**

1. **Documentation**: Check other guides in `/docs/`
2. **Community Forum**: Community support and discussions
3. **Issue Tracker**: Bug reports and feature requests  
4. **Enterprise Support**: Professional support for enterprise customers

### **Creating a Support Ticket**

Include this information:
- **WebOps version**: `cat /opt/webops/VERSION`
- **OS version**: `lsb_release -a`
- **Error logs**: Relevant log excerpts
- **Steps to reproduce**: What actions trigger the issue
- **Expected vs actual behavior**: What should happen vs what happens

---

## 🔄 **Maintenance Tasks**

### **Weekly Maintenance**
```bash
#!/bin/bash
# Weekly maintenance script

# Update system packages
sudo apt update && sudo apt upgrade -y

# Clear old logs
sudo journalctl --vacuum-time=30d

# Check disk space
df -h

# Backup database
pg_dump webops_db > /opt/webops/backups/weekly_$(date +%Y%m%d).sql

# Restart services for memory cleanup
sudo systemctl restart webops-celery
```

### **Monthly Maintenance**
- Review security audit logs
- Update WebOps to latest version
- Check SSL certificate expiration
- Performance optimization review

---

**Most issues can be resolved with the solutions above. For persistent problems, use the diagnostic tools and support channels provided.** 🔧