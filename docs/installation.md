# WebOps Production Installation Guide 🚀

**Deploy WebOps on your VPS for production workloads**

This guide covers installing WebOps on Ubuntu/Debian servers for production use with all enterprise features enabled.

---

## 📋 **Prerequisites**

### **Server Requirements**
- **OS**: Ubuntu 22.04 LTS / Debian 11+ (recommended)
- **RAM**: 4GB minimum, 8GB recommended
- **CPU**: 2 cores minimum, 4 cores recommended  
- **Storage**: 20GB minimum, 50GB+ recommended
- **Network**: Public IP with ports 80, 443, 22 accessible

### **Domain Requirements**
- **Primary domain** for WebOps control panel (e.g., `webops.yourdomain.com`)
- **Wildcard DNS** for deployed applications (e.g., `*.apps.yourdomain.com`)
- **SSL certificates** (automatic with Let's Encrypt)

### **Access Requirements**
- **Root access** or sudo privileges
- **SSH access** to the server
- **Domain registrar** access for DNS configuration

---

## 🔧 **Installation Methods**

### **Method 1: One-Command Installation (Recommended)**

```bash
# Download and run the installation script
curl -sSL https://raw.githubusercontent.com/DagiiM/webops/main/install.sh | bash

# Or for more control:
wget https://raw.githubusercontent.com/DagiiM/webops/main/install.sh
chmod +x install.sh
./install.sh
```

**The installer will:**
- ✅ Install all system dependencies (Python, PostgreSQL, Redis, Nginx)
- ✅ Create dedicated `webops` user and directories
- ✅ Configure systemd services for auto-start
- ✅ Set up SSL certificates with Let's Encrypt
- ✅ Configure firewall and security settings
- ✅ Initialize database and create admin user
- ✅ Enable all enterprise features

### **Method 2: Manual Installation**

For custom installations or when you need more control:

#### **1. System Preparation**

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib redis-server nginx \
    git curl wget gnupg2 software-properties-common \
    ufw fail2ban certbot python3-certbot-nginx

# Install Node.js for CLI tools (optional)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### **2. User and Directory Setup**

```bash
# Create dedicated webops user
sudo useradd -m -s /bin/bash webops
sudo usermod -aG sudo webops

# Create directory structure
sudo mkdir -p /opt/webops/{control-panel,deployments,backups,logs}
sudo chown -R webops:webops /opt/webops

# Switch to webops user
sudo su - webops
cd /opt/webops
```

#### **3. WebOps Installation**

```bash
# Clone WebOps repository
git clone https://github.com/DagiiM/webops.git .
cd control-panel

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install CLI tool globally
sudo npm install -g /opt/webops/cli
```

#### **4. Database Configuration**

```bash
# Configure PostgreSQL
sudo -u postgres createuser --interactive webops
sudo -u postgres createdb webops_db -O webops

# Set database password
sudo -u postgres psql -c "ALTER USER webops PASSWORD 'secure_random_password';"
```

#### **5. Environment Configuration**

```bash
# Generate secure configuration
cp .env.example .env
python3 -c "
from django.core.management.utils import get_random_secret_key
from cryptography.fernet import Fernet
print(f'SECRET_KEY={get_random_secret_key()}')
print(f'ENCRYPTION_KEY={Fernet.generate_key().decode()}')
"

# Edit .env with your settings
nano .env
```

**Required `.env` configuration:**
```bash
# Core Django Settings
SECRET_KEY=your_generated_secret_key
DEBUG=False
ALLOWED_HOSTS=webops.yourdomain.com

# Database Configuration
DATABASE_URL=postgresql://webops:secure_password@localhost:5432/webops_db

# Security
ENCRYPTION_KEY=your_generated_fernet_key
CSRF_TRUSTED_ORIGINS=https://webops.yourdomain.com

# Email Configuration (optional)
EMAIL_HOST=smtp.yourdomain.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=webops@yourdomain.com
EMAIL_HOST_PASSWORD=email_password

# Monitoring (optional)
SENTRY_DSN=https://your_sentry_dsn
```

#### **6. Database Migration and Setup**

```bash
# Run database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Load initial data (optional)
python manage.py loaddata initial_data.json
```

#### **7. System Services Configuration**

```bash
# Copy systemd service files
sudo cp /opt/webops/templates/systemd/*.service /etc/systemd/system/

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable webops-web webops-celery webops-celerybeat
sudo systemctl start webops-web webops-celery webops-celerybeat

# Check service status
sudo systemctl status webops-web
```

#### **8. Nginx Configuration**

```bash
# Copy Nginx configuration
sudo cp /opt/webops/templates/nginx/webops.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/webops.conf /etc/nginx/sites-enabled/

# Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx
```

#### **9. SSL Certificate Setup**

```bash
# Obtain SSL certificate
sudo certbot --nginx -d webops.yourdomain.com

# Set up auto-renewal
sudo systemctl enable certbot.timer
```

#### **10. Firewall Configuration**

```bash
# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Configure fail2ban
sudo cp /opt/webops/templates/fail2ban/webops.conf /etc/fail2ban/jail.d/
sudo systemctl restart fail2ban
```

---

## ✅ **Verification & Testing**

### **1. Service Health Check**

```bash
# Check all WebOps services
sudo systemctl status webops-web webops-celery webops-celerybeat

# Check system services
sudo systemctl status nginx postgresql redis-server

# Check logs
sudo journalctl -u webops-web -f
```

### **2. Web Interface Test**

```bash
# Test HTTP access
curl -I http://webops.yourdomain.com

# Test HTTPS access
curl -I https://webops.yourdomain.com

# Test API endpoint
curl -X GET https://webops.yourdomain.com/api/status/
```

### **3. Feature Verification**

Access your WebOps instance: `https://webops.yourdomain.com`

**Login and verify:**
- ✅ Dashboard loads with system metrics
- ✅ Create a test deployment
- ✅ Monitor deployment logs in real-time
- ✅ Check health monitoring page
- ✅ Test accessibility features (keyboard navigation)
- ✅ Verify PWA installation prompt

### **4. Performance Test**

```bash
# Run built-in health check
cd /opt/webops/control-panel
source venv/bin/activate
python manage.py health_check --report

# Test deployment capabilities
python manage.py test_deployment --url https://github.com/django/django-sample
```

---

## 🔐 **Security Hardening**

### **1. System Security**

```bash
# Update SSH configuration
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no, PasswordAuthentication no

# Configure automatic updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

### **2. WebOps Security Features**

**Enable 2FA for admin users:**
```bash
# Access admin panel: https://webops.yourdomain.com/admin/
# Navigate to Two-Factor Authentication setup
# Scan QR code with authenticator app
```

**Configure rate limiting:**
```bash
# Adjust rate limits in .env (optional)
RATE_LIMIT_LOGIN=5/15min
RATE_LIMIT_API=100/hour
RATE_LIMIT_DEPLOYMENTS=10/hour
```

### **3. Backup Configuration**

```bash
# Set up automated backups
sudo crontab -e

# Add daily backup at 2 AM
0 2 * * * /opt/webops/scripts/backup.sh daily

# Test backup system
sudo /opt/webops/scripts/backup.sh test
```

---

## 📊 **Monitoring Setup**

### **1. System Monitoring**

```bash
# Install monitoring tools (optional)
sudo apt install htop iotop nethogs

# Configure log rotation
sudo nano /etc/logrotate.d/webops
```

### **2. Application Monitoring**

**Built-in monitoring features:**
- ✅ Real-time system health dashboard
- ✅ Deployment success/failure tracking
- ✅ Performance metrics (Core Web Vitals)
- ✅ Error logging and alerting
- ✅ Resource usage monitoring

**Access monitoring:**
- Dashboard: `https://webops.yourdomain.com/dashboard/`
- Health Check: `https://webops.yourdomain.com/health/`
- System Monitor: `https://webops.yourdomain.com/monitoring/`

---

## 🚀 **Post-Installation Setup**

### **1. DNS Configuration**

Configure your domain registrar:
```
A     webops.yourdomain.com    → your_server_ip
A     *.apps.yourdomain.com    → your_server_ip
AAAA  webops.yourdomain.com    → your_ipv6 (if available)
```

### **2. First Deployment Test**

1. **Login** to WebOps control panel
2. **Create deployment** with sample Django app
3. **Monitor progress** in real-time logs
4. **Verify deployment** is accessible
5. **Check SSL certificate** is automatically configured

### **3. User Setup**

```bash
# Create additional users via admin panel or CLI
python manage.py create_user --username newuser --email user@domain.com

# Set up user permissions and 2FA
# Access: https://webops.yourdomain.com/admin/auth/user/
```

---

## 🔧 **Maintenance**

### **Daily Operations**
- Monitor system health dashboard
- Review deployment logs for failures
- Check SSL certificate expiration (auto-renewed)

### **Weekly Operations**
- Review security audit logs
- Update system packages
- Check backup integrity
- Monitor resource usage trends

### **Monthly Operations**
- Review and rotate logs
- Update WebOps to latest version
- Security audit and review access logs
- Performance optimization review

---

## 📞 **Getting Help**

### **Documentation**
- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions
- [Configuration Reference](configuration.md) - All configuration options
- [API Documentation](api-reference.md) - REST API reference

### **Support Channels**
- 📖 **Documentation**: Complete guides and references
- 🐛 **Issue Tracker**: Bug reports and feature requests
- 💬 **Community**: Discord/Slack community support
- 🏢 **Enterprise**: Professional support available

---

## 🎯 **What's Next?**

After successful installation:
1. **Deploy your first application** - [Deployment Guide](deployment-guide.md)
2. **Set up monitoring** - [Monitoring Guide](monitoring.md) 
3. **Configure team access** - [User Management](./user-management.md)
4. **Explore enterprise features** - [Enterprise Guide](enterprise.md)

---

**WebOps Production Installation Complete! 🎉**

Your enterprise-grade hosting platform is ready for production workloads.