## WebOps Security Features - Implementation Complete

**Enterprise-grade security with zero compromise on simplicity**

**Project Owner:** [Douglas Mutethia](https://github.com/DagiiM) | **Company:** Eleso Solutions  
**Repository:** [https://github.com/DagiiM/webops](https://github.com/DagiiM/webops)

---

## 🔐 Authentication & Authorization

### 1. **Two-Factor Authentication (2FA)**

**Implementation:** Pure Python TOTP - zero external service dependencies

**Features:**
- ✅ Compatible with Google Authenticator, Authy, Microsoft Authenticator
- ✅ QR code generation for easy setup
- ✅ 10 backup recovery codes per user
- ✅ Time-based one-time passwords (30-second window)
- ✅ Secure secret generation (base32-encoded, 128-bit entropy)

**Files:**
- `control-panel/apps/core/models.py` - `TwoFactorAuth` model
- `control-panel/apps/core/security_services.py` - `TOTPService`, `TwoFactorService`

**Usage:**
```python
from apps.core.security_services import TwoFactorService

# Setup 2FA for user
two_factor, uri, backup_codes = TwoFactorService.setup_2fa(user)

# User scans QR code from URI, enters token to verify
if TwoFactorService.enable_2fa(user, token):
    print("2FA enabled successfully")

# During login, verify 2FA token
if TwoFactorService.verify_2fa(user, token):
    # Allow login
    pass
```

**Security Guarantees:**
- Secrets never transmitted in plain text
- HMAC-SHA1 for token generation (RFC 6238)
- Constant-time comparison prevents timing attacks
- Backup codes one-time use only

---

### 2. **GitHub OAuth Integration**

**Implementation:** OAuth 2.0 flow with encrypted token storage

**Features:**
- ✅ Deploy from private repositories
- ✅ Token encryption using Fernet (symmetric encryption)
- ✅ Automatic token refresh
- ✅ Scope-based permissions
- ✅ User connection tracking

**Files:**
- `control-panel/apps/core/models.py` - `GitHubConnection` model
- `control-panel/apps/core/security_services.py` - `GitHubOAuthService`

**Setup:**
1. Create GitHub OAuth App at https://github.com/settings/developers
2. Add to `.env`:
```bash
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
```

**OAuth Flow:**
```python
from apps.core.security_services import GitHubOAuthService

# 1. Get authorization URL
auth_url = GitHubOAuthService.get_authorization_url(redirect_uri)

# 2. User authorizes, GitHub redirects with code

# 3. Exchange code for token
token_data = GitHubOAuthService.exchange_code_for_token(code)

# 4. Get user info and create connection
user_info = GitHubOAuthService.get_user_info(token_data['access_token'])
connection = GitHubOAuthService.create_connection(user, access_token, user_info)
```

---

## 📊 Security Monitoring

### 3. **Comprehensive Audit Logging**

**Implementation:** Database-backed security event logging

**Events Tracked:**
- ✅ Login attempts (success/failure)
- ✅ 2FA events (enabled/disabled/verification)
- ✅ API token operations
- ✅ Deployment operations
- ✅ Database credential access
- ✅ Suspicious activity
- ✅ Unauthorized access attempts

**Features:**
- IP address tracking
- User agent logging
- Severity levels (info/warning/error/critical)
- Metadata storage (JSON)
- Indexed for fast queries
- Retention policies

**Files:**
- `control-panel/apps/core/models.py` - `SecurityAuditLog` model
- `control-panel/apps/core/security_services.py` - `SecurityAuditService`

**Usage:**
```python
from apps.core.security_services import SecurityAuditService

# Log security event
SecurityAuditService.log_event(
    event_type='login_success',
    request=request,
    description='User logged in successfully',
    severity='info',
    metadata={'method': '2fa'}
)

# Check for suspicious activity
failed_attempts = SecurityAuditService.get_failed_login_attempts(ip_address)
if failed_attempts >= 5:
    # Block IP or require CAPTCHA
    pass
```

**Attack Prevention:**
- Brute force detection (rate limiting based on failed attempts)
- IP blocking after threshold
- Geographic anomaly detection (new IP locations)

---

### 4. **System Health Monitoring**

**Implementation:** Real-time system metrics collection

**Metrics Tracked:**
- ✅ CPU usage percentage
- ✅ Memory usage (used/total, percentage)
- ✅ Disk usage (used/total, percentage)
- ✅ Active/failed deployments count
- ✅ PostgreSQL connections
- ✅ Redis memory usage
- ✅ Nginx request rates
- ✅ Failed login attempts
- ✅ Blocked IPs

**Files:**
- `control-panel/apps/core/models.py` - `SystemHealthCheck` model
- `control-panel/apps/core/security_services.py` - `SystemHealthService`

**Automated Checks:**
- Runs every 5 minutes via Celery Beat
- Issues flagged when:
  - CPU > 90%
  - Memory > 90%
  - Disk > 90%
- Historical trend analysis (24-hour window)

**Usage:**
```python
from apps.core.security_services import SystemHealthService

# Run health check
health = SystemHealthService.run_health_check()

if not health.is_healthy:
    for issue in health.issues:
        send_alert(issue)

# Get trend
trend = SystemHealthService.get_health_trend(hours=24)
avg_cpu = trend['avg_cpu']
```

---

## 🔒 SSL/TLS Management

### 5. **Automated SSL Certificates**

**Implementation:** Let's Encrypt integration with automatic renewal

**Features:**
- ✅ Automatic certificate issuance
- ✅ 90-day certificates (industry standard)
- ✅ Auto-renewal 30 days before expiry
- ✅ HTTP-01 challenge (webroot)
- ✅ Multi-domain support
- ✅ Certificate monitoring
- ✅ Failure alerts

**Files:**
- `scripts/ssl-manager.sh` - Certificate management
- `control-panel/apps/core/models.py` - `SSLCertificate` model

**Commands:**
```bash
# Issue new certificate
sudo ./scripts/ssl-manager.sh issue example.com admin@example.com

# Renew specific certificate
sudo ./scripts/ssl-manager.sh renew example.com

# Renew all certificates
sudo ./scripts/ssl-manager.sh renew

# Check certificate status
sudo ./scripts/ssl-manager.sh check

# Auto-renew (for cron)
sudo ./scripts/ssl-manager.sh auto-renew
```

**Cron Setup:**
```bash
# Add to /etc/cron.d/webops-ssl
0 0,12 * * * root /opt/webops/scripts/ssl-manager.sh auto-renew >> /var/log/webops-ssl.log 2>&1
```

**Certificate Tracking:**
- Database storage of all certificates
- Expiry date monitoring
- Renewal attempt tracking
- Failure count for alerting
- Status updates (active/expiring_soon/expired/renewal_failed)

---

## 🛡️ Security Auditing

### 6. **Comprehensive Security Audit Script**

**Implementation:** Bash-based system security scanner

**Checks Performed:**

**System Hardening:**
- ✅ Automatic security updates configuration
- ✅ SSH hardening (root login, password auth)
- ✅ Firewall status (UFW)
- ✅ Fail2Ban intrusion prevention
- ✅ Available security updates

**Service Security:**
- ✅ PostgreSQL localhost binding
- ✅ Redis password protection
- ✅ Redis localhost binding
- ✅ Nginx server tokens
- ✅ WebOps service status

**SSL/TLS:**
- ✅ Certbot installation
- ✅ Certificate expiry dates
- ✅ TLS protocol versions
- ✅ SSL cipher strength

**Permissions:**
- ✅ User privilege audit
- ✅ Directory permissions
- ✅ World-writable files
- ✅ .env file security
- ✅ Deployment user isolation

**Network:**
- ✅ Open ports inventory
- ✅ Internet-exposed services
- ✅ IP forwarding status
- ✅ SYN cookie protection

**Resources:**
- ✅ CPU usage
- ✅ Memory usage
- ✅ Disk usage

**Compliance:**
- ✅ Log rotation
- ✅ Backup scripts
- ✅ Default password detection
- ✅ Django DEBUG mode

**Files:**
- `scripts/security-audit.sh` - Main audit script

**Usage:**
```bash
# Text report
sudo ./scripts/security-audit.sh

# JSON output
sudo ./scripts/security-audit.sh --format=json

# Save to file
sudo ./scripts/security-audit.sh --output=/var/log/security-audit.log
```

**Output Example:**
```
═══════════════════════════════════════
  Security Audit Summary
═══════════════════════════════════════

Total Findings:
  Critical: 0
  High: 1
  Medium: 3
  Low: 2
  Info: 45

Overall security is acceptable with minor issues
```

**Scheduled Audits:**
```bash
# Add to /etc/cron.weekly/webops-security-audit
#!/bin/bash
/opt/webops/scripts/security-audit.sh --output=/var/log/webops-audit-$(date +%Y%m%d).log
```

---

## 🔑 Input Validation & Sanitization

### 7. **Multi-Layer Security Validators**

**Implementation:** Pure Python validators with zero external dependencies

**Validators:**

**Repository URL Validator:**
- Prevents SSRF attacks
- Blocks private networks (RFC 1918)
- Whitelist: GitHub, GitLab, Bitbucket only
- HTTPS-only enforcement
- Localhost blocking

**Environment Variable Validator:**
- SQL injection prevention
- Command injection detection
- XSS pattern blocking
- Path traversal prevention
- Null byte injection blocking
- Maximum length enforcement (10,000 chars)

**API Token Validator:**
- Expiration checks
- IP whitelisting
- Anomaly detection (IP changes)
- Usage tracking
- Age-based rotation warnings

**Deployment Isolation Validator:**
- Filesystem access control
- Forbidden path blocking
- Cross-deployment access prevention

**Files:**
- `control-panel/apps/core/validators.py` - All validators

**Usage:**
```python
from apps.core.validators import (
    RepositoryURLValidator,
    EnvironmentVariableValidator,
    APITokenValidator
)

# Validate repository URL
try:
    RepositoryURLValidator.validate(repo_url)
except ValidationError as e:
    # Handle invalid URL
    pass

# Validate environment variables
try:
    EnvironmentVariableValidator.validate(env_vars)
except ValidationError as e:
    # Handle dangerous patterns
    pass

# Validate API token
try:
    APITokenValidator.validate_token_security(token, request_ip)
except ValidationError as e:
    # Token compromised or expired
    pass
```

---

## 📦 Deployment Isolation

### 8. **Per-Deployment Security Containers**

**Implementation:** systemd + cgroups + Linux security modules

**Isolation Features:**

**User Isolation:**
- Dedicated system user per deployment (`webops-appname`)
- No shell access (`/bin/false`)
- No sudo privileges
- Home directory = deployment directory

**Resource Limits (systemd):**
```ini
MemoryMax=512M              # Hard memory limit
MemoryHigh=400M             # Soft limit (80%)
CPUQuota=50%                # 0.5 CPU cores
TasksMax=50                 # Max processes
LimitNOFILE=10000          # Max file descriptors
```

**Filesystem Restrictions:**
```ini
ProtectSystem=strict        # Read-only /usr, /boot, /etc
ProtectHome=true            # No access to /home
PrivateTmp=true             # Isolated /tmp
ReadWritePaths=/opt/webops/deployments/appname  # Only write to own dir
```

**Network Restrictions:**
```ini
RestrictAddressFamilies=AF_INET AF_INET6  # Only IPv4/IPv6
IPAddressDeny=10.0.0.0/8 172.16.0.0/12 192.168.0.0/16  # Block internal networks
```

**Security Hardening:**
```ini
NoNewPrivileges=true        # Prevent privilege escalation
ProtectKernelTunables=true  # Protect /proc/sys
ProtectKernelModules=true   # No kernel module loading
SystemCallFilter=@system-service  # Restrict syscalls
CapabilityBoundingSet=      # Drop all capabilities
```

**Files:**
- `scripts/create-isolated-deployment.sh` - Deployment creation

**Usage:**
```bash
sudo ./scripts/create-isolated-deployment.sh myapp 512M 50 2
# Args: name, memory, cpu_quota, disk_quota_gb
```

---

## 👤 WebOps System User & Privilege Management

### 9. **Dedicated System User with Limited Sudo Access**

**Implementation:** Secure service isolation with principle of least privilege

**User Configuration:**
- User: `webops` (system user)
- Shell: `/bin/bash` (required for deployment tasks)
- Home: `/opt/webops`
- Groups: `webops` (primary), `www-data`, `postgres`
- Type: System user (no password login)

**Directory Ownership:**
```bash
/opt/webops/
├── control-panel/      # WebOps application (750, webops:webops)
├── deployments/        # User applications (750, webops:webops)
├── backups/            # Backups (700, webops:webops)
├── .secrets/           # Credentials (700, webops:webops)
└── logs/               # Application logs (755, webops:webops)
```

**Sudo Access (Limited & Auditable):**

The `webops` user has **passwordless sudo** for specific commands only:

```bash
# Nginx management (for deployment configuration updates)
/bin/systemctl reload nginx
/bin/systemctl restart nginx
/usr/bin/nginx -t

# WebOps service management
/bin/systemctl {start,stop,restart,reload,enable,disable,status} webops-*

# Deployed application service management
/bin/systemctl {start,stop,restart,reload,enable,disable,status} app-*

# Systemd configuration
/bin/systemctl daemon-reload

# Configuration deployment
/bin/cp /opt/webops/deployments/*/systemd/*.service /etc/systemd/system/
/bin/cp /opt/webops/deployments/*/nginx/*.conf /etc/nginx/sites-available/
/bin/ln -sf /etc/nginx/sites-available/* /etc/nginx/sites-enabled/

# SSL certificate management
/usr/bin/certbot certonly *
/usr/bin/certbot renew *
/usr/bin/certbot delete *
```

**Security Rationale:**
1. **No Root Access:** Services run as `webops`, not root
2. **Command Whitelisting:** Only specific commands allowed via sudo
3. **Path Restrictions:** File operations limited to `/opt/webops/*`
4. **No Password Required:** `NOPASSWD` for automation, but limited scope
5. **Audit Trail:** All sudo commands logged to `/var/log/auth.log`
6. **Service Isolation:** Each deployment runs as `webops`, isolated via systemd

**Why Not Run as Root?**
- Compromised deployment doesn't grant root access
- Limits blast radius of vulnerabilities
- Industry best practice (least privilege)
- Better process isolation
- Easier auditing

**Why Bash Shell?**
- Required for running deployment scripts
- Git operations during deployment
- Environment variable processing
- Process management via systemd

**Group Memberships:**
- `www-data`: Read/write access to nginx directories for serving static files
- `postgres`: Create databases for deployed applications

**Sudoers File Location:**
```bash
/etc/sudoers.d/webops  # Mode: 0440 (read-only, validated syntax)
```

**Validation:**
```bash
# Setup validates sudoers syntax automatically
visudo -c -f /etc/sudoers.d/webops
```

**Attack Surface Reduction:**
- ✅ No shell login (no password set)
- ✅ No SSH access (system account)
- ✅ No home directory access from other users
- ✅ Systemd security restrictions (NoNewPrivileges, PrivateTmp, ProtectSystem)
- ✅ Limited sudo commands (specific paths only)
- ✅ All actions logged

**Monitoring:**
```bash
# View sudo usage by webops user
sudo grep "webops.*sudo" /var/log/auth.log

# Check current processes
ps aux | grep webops

# View systemd service status
systemctl status webops-*
```

**Files:**
- `setup.sh` - `create_webops_user()`, `configure_sudo_access()`
- `/etc/sudoers.d/webops` - Sudo configuration

---

## 📋 Security Best Practices Enforced

### Application Layer
- ✅ CSRF protection on all forms
- ✅ XSS prevention via Django templates
- ✅ SQL injection prevention (parameterized queries)
- ✅ Unique SECRET_KEY per deployment
- ✅ Session security (secure, httponly, samesite cookies)
- ✅ Password hashing (PBKDF2-SHA256)
- ✅ Rate limiting on API endpoints
- ✅ Input validation on all user data

### Network Layer
- ✅ HTTPS-only (Let's Encrypt)
- ✅ TLS 1.2+ only
- ✅ Strong cipher suites
- ✅ HSTS headers
- ✅ X-Frame-Options: DENY
- ✅ X-Content-Type-Options: nosniff
- ✅ Nginx security headers

### System Layer
- ✅ Minimal attack surface (no unnecessary services)
- ✅ Automatic security updates
- ✅ Firewall (UFW) - only ports 22, 80, 443
- ✅ Fail2Ban intrusion prevention
- ✅ SELinux/AppArmor profiles
- ✅ Log rotation and retention
- ✅ Regular backups

---

## 🚀 Quick Start - Secure Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/webops.git
cd webops

# 2. Run setup (installs everything with security hardening)
sudo ./setup.sh

# 3. Enable 2FA for admin
# Login to control panel → Settings → Security → Enable 2FA

# 4. Connect GitHub (optional)
# Settings → Integrations → Connect GitHub

# 5. Run security audit
sudo ./scripts/security-audit.sh

# 6. Setup SSL for control panel
sudo ./scripts/ssl-manager.sh issue panel.yourdomain.com admin@yourdomain.com

# 7. Schedule automated tasks
sudo crontab -e
# Add:
0 0,12 * * * /opt/webops/scripts/ssl-manager.sh auto-renew
0 0 * * 0 /opt/webops/scripts/security-audit.sh --output=/var/log/audit-$(date +\%Y\%m\%d).log
```

---

## 📊 Security Metrics Dashboard

All security metrics available via Django admin and API:

- Real-time system health
- Security audit logs (searchable, filterable)
- SSL certificate status
- Failed login attempts by IP
- API token usage
- Deployment resource usage
- 2FA adoption rate

**API Endpoints:**
```
GET /api/security/health/          # Latest health check
GET /api/security/audit-logs/      # Security events
GET /api/security/ssl-certs/       # Certificate status
GET /api/security/metrics/         # Security metrics
```

---

## 🔄 Continuous Security

**Automated:**
- SSL renewal every 12 hours (certbot)
- Security audits weekly
- System health checks every 5 minutes
- Log rotation daily
- Database backups daily
- Security update checks daily

**Manual:**
- Review audit logs monthly
- Update GitHub access tokens when needed
- Rotate API tokens every 90 days
- Review deployment user permissions quarterly

---

## 🎯 Security Compliance

**Standards Addressed:**
- CIS Benchmarks (partial)
- OWASP Top 10 (web application security)
- NIST Cybersecurity Framework (identify, protect, detect)
- PCI DSS principles (data protection, access control)

---

## 📚 Additional Resources

- **Edge Cases:** `/docs/edge_cases.md` - 33 security scenarios
- **App Contracts:** `/docs/APP-CONTRACT.md` - Resource isolation
- **Development:** `/docs/DEVELOPMENT.md` - Secure coding practices
- **Security Policy:** `/SECURITY.md` - Vulnerability reporting

---

**Built with security-first mindset. Zero compromises.**
