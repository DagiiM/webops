# WebOps A-Grade Security Roadmap
## Plan to Achieve 95+/100 in All Security Metrics

**Current Overall Score:** 72/100 (C+)
**Target Score:** 95+/100 (A)
**Approach:** Minimal frameworks, maximum security
**Timeline:** 12-16 weeks

---

## Current Scores vs Target

| Metric | Current | Target | Gap | Priority |
|--------|---------|--------|-----|----------|
| **Authentication** | 75/100 (B) | 95/100 (A) | +20 | P1 |
| **Authorization** | 45/100 (F) | 95/100 (A) | +50 | P0 |
| **Encryption** | 60/100 (D) | 95/100 (A) | +35 | P0 |
| **Input Validation** | 70/100 (C) | 95/100 (A) | +25 | P1 |
| **Session Management** | 80/100 (B) | 95/100 (A) | +15 | P2 |
| **Access Control** | 50/100 (F) | 95/100 (A) | +45 | P0 |
| **Audit Logging** | 75/100 (B) | 95/100 (A) | +20 | P1 |
| **Infrastructure** | 65/100 (D) | 95/100 (A) | +30 | P1 |
| **Dependencies** | 55/100 (F) | 95/100 (A) | +40 | P0 |
| **Compliance** | 55/100 (F) | 95/100 (A) | +40 | P1 |

---

## Phase 1: CRITICAL FIXES (Week 1-2) - Foundation
**Goal:** Eliminate all CRITICAL vulnerabilities, achieve 80/100 baseline

### 1.1 Authorization & Access Control (45→80) [P0]

**Problem:** IDOR vulnerabilities - users can access ALL resources

#### Tasks:
- [ ] **Add user ownership filters to ALL queries**
  - File: `apps/deployments/views/application_deployment.py`
  - Change: `ApplicationDeployment.objects.all()` → `.filter(deployed_by=request.user)`
  - Apply to: deployments, databases, services, API endpoints
  - No framework needed: Use Django QuerySet filters

- [ ] **Create ownership verification middleware**
  - File: Create `apps/core/middleware/ownership.py`
  - Pure Python implementation using Django request/response cycle
  - Verify resource ownership before view execution
  - No external dependencies

```python
# Minimal implementation - no frameworks
class ResourceOwnershipMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check ownership before view
        if hasattr(request, 'resolver_match'):
            if 'pk' in request.resolver_match.kwargs:
                self.verify_ownership(request)
        return self.get_response(request)
```

- [ ] **Add organization-scoped queries for multi-tenancy**
  - Use existing enterprise RBAC models
  - Filter all queries by organization membership
  - Pure Django ORM, no additional frameworks

- [ ] **Create resource permission decorator**
  - File: `apps/core/decorators/permissions.py`
  - Minimal decorator using functools.wraps
  - Check user permissions before view execution

```python
# Minimal decorator - no frameworks
def require_resource_ownership(model_class):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, pk, *args, **kwargs):
            obj = get_object_or_404(model_class, pk=pk)
            if obj.user != request.user and not request.user.is_superuser:
                raise PermissionDenied
            return view_func(request, pk, *args, **kwargs)
        return wrapper
    return decorator
```

**Target Score After:** 80/100

---

### 1.2 Encryption & Key Management (60→85) [P0]

**Problem:** Hardcoded keys, unencrypted secrets

#### Tasks:
- [ ] **Rotate ALL encryption keys immediately**
  - Generate new Fernet key: `from cryptography.fernet import Fernet; Fernet.generate_key()`
  - Remove key from `.env.example`
  - Update all environments
  - Built-in Python cryptography library only

- [ ] **Encrypt 2FA secrets in database**
  - File: `apps/core/auth/models.py`
  - Migration: Encrypt existing TOTP secrets
  - Use existing Fernet implementation
  - No additional frameworks

```python
# Minimal encryption - already have cryptography
from cryptography.fernet import Fernet
from django.conf import settings

class TwoFactorAuth(models.Model):
    secret = models.CharField(max_length=255)  # Encrypted

    def set_secret(self, value):
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        self.secret = f.encrypt(value.encode()).decode()

    def get_secret(self):
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        return f.decrypt(self.secret.encode()).decode()
```

- [ ] **Encrypt webhook secrets**
  - File: `apps/core/webhooks/models.py`
  - Same Fernet approach as 2FA
  - Migration script to encrypt existing secrets

- [ ] **Implement key rotation mechanism**
  - File: Create `apps/core/management/commands/rotate_keys.py`
  - Django management command (no framework)
  - Re-encrypt all sensitive data with new key
  - Keep old key for 90 days (dual-key support)

```python
# Minimal key rotation - no frameworks
class Command(BaseCommand):
    def handle(self, *args, **options):
        old_key = settings.OLD_ENCRYPTION_KEY
        new_key = settings.ENCRYPTION_KEY

        # Re-encrypt all secrets
        for obj in TwoFactorAuth.objects.all():
            old_secret = decrypt_with_key(obj.secret, old_key)
            obj.secret = encrypt_with_key(old_secret, new_key)
            obj.save()
```

- [ ] **Separate encryption keys by purpose**
  - ENCRYPTION_KEY_AUTH - for authentication secrets
  - ENCRYPTION_KEY_DATA - for user data
  - ENCRYPTION_KEY_TOKENS - for API tokens
  - Store in environment variables only
  - No framework needed

**Target Score After:** 85/100

---

### 1.3 Dependencies & Supply Chain (55→85) [P0]

**Problem:** Malicious package, outdated dependencies, no pinning

#### Tasks:
- [ ] **Remove non-existent package immediately**
  - File: `.webops/agents/requirements.txt`
  - Remove: `tkinter-dev` (doesn't exist on PyPI)
  - tkinter is built-in to Python

- [ ] **Update vulnerable dependencies**
  - `psutil==5.9.8` → `psutil==6.0.1` (CVE-2023-27043)
  - Remove `aioredis` (deprecated, use `redis>=5.0.0`)
  - Update all packages to latest stable versions

- [ ] **Pin ALL dependencies with exact versions**
  - Use `==` instead of `>=` for reproducibility
  - Generate with: `pip freeze > requirements.txt`
  - No additional tools needed

- [ ] **Create requirements lock files**
  - `requirements-lock.txt` with full dependency tree
  - Generate with: `pip list --format=freeze`
  - Pure pip, no poetry/pipenv needed

- [ ] **Implement dependency scanning in CI/CD**
  - File: `.github/workflows/security.yml`
  - Use `pip-audit` (minimal tool, official Python)
  - Run on every commit

```yaml
# Minimal CI/CD security - no heavy frameworks
- name: Security Scan
  run: |
    pip install pip-audit bandit
    pip-audit --desc
    bandit -r control-panel/ -ll
```

- [ ] **Create dependency update policy**
  - File: `DEPENDENCIES.md`
  - Weekly security updates
  - Monthly version updates
  - Automated PR with dependabot (GitHub native)

**Target Score After:** 85/100

---

### 1.4 Command Injection Prevention (CRITICAL) [P0]

**Problem:** User commands executed with shell=True

#### Tasks:
- [ ] **Remove ALL shell=True usage**
  - File: `apps/deployments/services/application.py`
  - Convert strings to lists: `shlex.split(command)`
  - Use `subprocess.run(list)` without shell
  - Built-in shlex module only

```python
# Minimal command execution - no frameworks
import shlex
import subprocess

def safe_execute(command_string, cwd=None):
    # Parse safely without shell
    parts = shlex.split(command_string)

    # Validate command against whitelist
    allowed = ['npm', 'pip', 'cargo', 'composer', 'bundle', 'yarn']
    if parts[0] not in allowed:
        raise ValueError(f"Command not allowed: {parts[0]}")

    # Execute safely
    return subprocess.run(
        parts,  # List, not string
        shell=False,  # NEVER use shell=True
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=600
    )
```

- [ ] **Create command whitelist validator**
  - File: `apps/core/security/command_validator.py`
  - Pure Python validation
  - No regex complexity, simple string matching

- [ ] **Implement command sandboxing**
  - Use `subprocess` with restricted environment
  - Set `env={}` to clear environment variables
  - Use `user=` parameter to run as unprivileged user
  - Built-in subprocess features only

```python
# Minimal sandboxing - no frameworks
import pwd
import os

def execute_sandboxed(command_parts, cwd):
    # Get unprivileged user
    nobody = pwd.getpwnam('nobody')

    # Clear environment
    safe_env = {
        'PATH': '/usr/bin:/bin',
        'HOME': nobody.pw_dir,
    }

    # Execute as nobody user
    subprocess.run(
        command_parts,
        shell=False,
        env=safe_env,
        cwd=cwd,
        user=nobody.pw_uid,
        group=nobody.pw_gid
    )
```

**Target Score After:** Critical vulnerability eliminated

---

### 1.5 Default Credentials Removal [P0]

#### Tasks:
- [ ] **Remove hardcoded admin password**
  - File: `control-panel/quickstart.sh`
  - Generate random password with Python secrets module
  - Built-in secrets module, no frameworks

```bash
# Minimal password generation - no frameworks
ADMIN_PASSWORD=$(python3 -c "import secrets, string; chars=string.ascii_letters+string.digits+string.punctuation; print(''.join(secrets.choice(chars) for _ in range(32)))")
echo "Admin password: $ADMIN_PASSWORD" > /opt/webops/.secrets/admin_password.txt
chmod 600 /opt/webops/.secrets/admin_password.txt
```

- [ ] **Implement first-run setup wizard**
  - File: `apps/core/management/commands/setup.py`
  - Django management command
  - Interactive password creation
  - No web framework needed

**Target Score After:** Critical vulnerability eliminated

---

## Phase 2: HIGH PRIORITY (Week 3-6) - Enhancement
**Goal:** Fix all HIGH severity issues, achieve 90/100

### 2.1 XSS/CSRF Protection (70→95)

#### Tasks:
- [ ] **Fix ALL |safe filter usage**
  - Find: `grep -r "|safe" control-panel/templates/`
  - Replace with: `|escapejs` for JavaScript context
  - Use: `|escape` for HTML context
  - Django built-in filters only

- [ ] **Implement Content-Security-Policy headers**
  - File: `apps/core/middleware/security_headers.py`
  - Pure Django middleware, no frameworks
  - Strict CSP policy

```python
# Minimal CSP - no frameworks
class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self';"
        )
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
```

- [ ] **Add CSRF token validation to ALL APIs**
  - Remove all `@csrf_exempt` decorators
  - Use Django's built-in CSRF middleware
  - Validate tokens in AJAX requests

- [ ] **Implement Subresource Integrity (SRI)**
  - Add integrity hashes to all external scripts/styles
  - Generate with: `openssl dgst -sha384 -binary file.js | openssl base64 -A`
  - No tools needed, just openssl

**Target Score After:** 95/100

---

### 2.2 Input Validation Enhancement (70→95)

#### Tasks:
- [ ] **Fix missing re module import**
  - File: `apps/databases/forms.py`
  - Add: `import re` at top
  - Simple fix

- [ ] **Create comprehensive input validator**
  - File: `apps/core/security/validators.py`
  - Pure Python validators
  - No regex library needed beyond `re`

```python
# Minimal validators - no frameworks
import re
from django.core.exceptions import ValidationError

def validate_deployment_name(name):
    """Alphanumeric, hyphens, underscores only"""
    if not re.match(r'^[a-zA-Z0-9_-]{3,63}$', name):
        raise ValidationError('Invalid deployment name')

    # Prevent path traversal
    if '..' in name or '/' in name:
        raise ValidationError('Invalid characters')

    # Prevent reserved names
    reserved = ['admin', 'root', 'system', 'config']
    if name.lower() in reserved:
        raise ValidationError('Reserved name')

    return name
```

- [ ] **Add validation to ALL user inputs**
  - Forms: Use Django form validators
  - APIs: Create validation decorator
  - File uploads: Validate file types and sizes
  - Built-in Django validation framework

- [ ] **Implement rate limiting per validation failure**
  - Track failed validations per IP
  - Use Django cache (no Redis needed for small scale)
  - Block after 10 failures in 5 minutes

```python
# Minimal rate limiting - no frameworks
from django.core.cache import cache

def check_validation_rate_limit(ip_address):
    key = f"validation_failures:{ip_address}"
    failures = cache.get(key, 0)

    if failures >= 10:
        raise PermissionDenied("Too many validation failures")

    cache.set(key, failures + 1, 300)  # 5 minutes
```

**Target Score After:** 95/100

---

### 2.3 Authentication Hardening (75→95)

#### Tasks:
- [ ] **Implement account lockout**
  - File: `apps/core/auth/services.py`
  - Pure Python tracking with Django cache
  - 5 attempts → 15 minute lockout
  - 10 attempts → 1 hour lockout
  - No external service needed

```python
# Minimal account lockout - no frameworks
def check_login_attempts(username):
    key = f"login_attempts:{username}"
    attempts = cache.get(key, 0)

    if attempts >= 10:
        raise ValidationError("Account locked for 1 hour")
    elif attempts >= 5:
        raise ValidationError("Account locked for 15 minutes")

    return attempts
```

- [ ] **Enforce strong password policy**
  - Minimum 12 characters (update from 8)
  - Require: uppercase, lowercase, digit, special
  - Django built-in password validators
  - Add custom validator for common passwords

```python
# Minimal password validator - no frameworks
class StrongPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 12:
            raise ValidationError("Password must be at least 12 characters")

        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain uppercase")

        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain lowercase")

        if not re.search(r'\d', password):
            raise ValidationError("Password must contain digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain special character")
```

- [ ] **Implement password expiration**
  - Add `password_changed_at` field to User model
  - Require change every 90 days
  - Django ORM field, no framework

- [ ] **Add CAPTCHA for login after failures**
  - Implement simple CAPTCHA in pure Python
  - No reCAPTCHA needed (avoid Google dependency)
  - Use PIL to generate images

```python
# Minimal CAPTCHA - no frameworks (use PIL only)
from PIL import Image, ImageDraw, ImageFont
import random
import string

def generate_captcha():
    text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    img = Image.new('RGB', (200, 80), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(0, 0, 0))
    return img, text
```

- [ ] **Implement session invalidation on password change**
  - Delete all sessions for user on password change
  - Django session framework built-in
  - No additional tools

**Target Score After:** 95/100

---

### 2.4 Audit Logging Enhancement (75→95)

#### Tasks:
- [ ] **Add database access logging**
  - File: `apps/databases/views.py`
  - Use existing `log_audit()` function
  - No framework needed

```python
# Already have audit logging, just call it
@login_required
def database_detail(request, pk):
    database = get_object_or_404(Database, pk=pk, user=request.user)

    # Add this line
    log_audit(
        user=request.user,
        action='database_accessed',
        resource_type='database',
        resource_id=str(database.id),
        request=request
    )

    return render(request, 'databases/detail.html', {'database': database})
```

- [ ] **Log ALL permission checks**
  - Add logging to `PermissionService`
  - Track both granted and denied access
  - Use existing audit log infrastructure

- [ ] **Implement log integrity verification**
  - Add HMAC signature to each log entry
  - Use Python's built-in hmac module
  - Verify on log read

```python
# Minimal log integrity - no frameworks
import hmac
import hashlib

def sign_log_entry(log_entry):
    message = f"{log_entry.user}{log_entry.action}{log_entry.timestamp}"
    signature = hmac.new(
        settings.LOG_SIGNING_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    log_entry.signature = signature
    return log_entry
```

- [ ] **Create log retention policy**
  - File: `apps/core/management/commands/cleanup_logs.py`
  - Django management command
  - Keep logs for 365 days, archive older ones
  - Pure Python file operations

```python
# Minimal log cleanup - no frameworks
import gzip
import shutil
from datetime import timedelta

class Command(BaseCommand):
    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=365)

        # Archive old logs
        old_logs = AuditLog.objects.filter(timestamp__lt=cutoff)

        # Write to compressed file
        with gzip.open(f'/var/backups/audit-{cutoff.date()}.json.gz', 'wt') as f:
            for log in old_logs:
                f.write(json.dumps(log.to_dict()) + '\n')

        # Delete from database
        old_logs.delete()
```

- [ ] **Implement real-time log monitoring**
  - File: `apps/core/monitoring/log_monitor.py`
  - Pure Python script using Django ORM
  - Alert on suspicious patterns
  - No SIEM needed for basic monitoring

```python
# Minimal log monitoring - no frameworks
def monitor_security_events():
    # Check for suspicious patterns
    recent_logs = AuditLog.objects.filter(
        timestamp__gte=timezone.now() - timedelta(minutes=5)
    )

    # Failed login attempts from same IP
    failed_logins = recent_logs.filter(
        action='login_failed'
    ).values('ip_address').annotate(count=Count('id'))

    for item in failed_logins:
        if item['count'] >= 5:
            send_alert(f"Multiple failed logins from {item['ip_address']}")
```

**Target Score After:** 95/100

---

### 2.5 Infrastructure Hardening (65→90)

#### Tasks:
- [ ] **Implement Redis authentication**
  - Update `.env.example` with password requirement
  - Use `rediss://` (TLS) instead of `redis://`
  - Built-in Redis features, no framework

- [ ] **Fix ALLOWED_HOSTS configuration**
  - Never use wildcard `*`
  - Validate domain format before adding
  - Django built-in setting

- [ ] **Add systemd service hardening**
  - File: `cli/webops_cli/system-templates/app/systemd/app.service.j2`
  - Add security restrictions:
    - `ProtectSystem=strict`
    - `ProtectHome=true`
    - `NoNewPrivileges=true`
    - `PrivateTmp=true`
  - Built-in systemd features

- [ ] **Fix file permissions**
  - Temp directories: 0700 (not 1777)
  - Log files: 0600
  - Config files: 0640
  - Pure bash/chmod, no tools

- [ ] **Implement log rotation**
  - Create `/etc/logrotate.d/webops`
  - Rotate daily, keep 30 days
  - Built-in logrotate

```bash
# Minimal logrotate - no frameworks
/opt/webops/logs/*.log {
    daily
    rotate 30
    missingok
    notifempty
    compress
    delaycompress
    postrotate
        systemctl reload webops-web > /dev/null 2>&1 || true
    endscript
}
```

- [ ] **Enhance nginx security configuration**
  - File: `cli/webops_cli/system-templates/control-panel/nginx/nginx-ssl-config.conf`
  - Add OCSP stapling
  - Disable session tickets
  - Update cipher suites
  - Built-in nginx features

**Target Score After:** 90/100

---

## Phase 3: MEDIUM PRIORITY (Week 7-10) - Compliance
**Goal:** Address compliance gaps, achieve 93/100

### 3.1 GDPR Compliance (55→95)

#### Tasks:
- [ ] **Implement data export API**
  - File: Create `apps/api/views/data_export.py`
  - Pure Django views, no framework
  - Export user data as JSON

```python
# Minimal data export - no frameworks
@login_required
def export_user_data(request):
    user = request.user

    data = {
        'profile': {
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
        },
        'preferences': list(UserPreferences.objects.filter(user=user).values()),
        'audit_logs': list(AuditLog.objects.filter(user=user).values()),
    }

    response = JsonResponse(data)
    response['Content-Disposition'] = f'attachment; filename="user-data-{user.username}.json"'
    return response
```

- [ ] **Implement consent management**
  - File: Create `apps/core/models/consent.py`
  - Simple Django model
  - Track consent with timestamps

```python
# Minimal consent tracking - no frameworks
class ConsentRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    consent_type = models.CharField(max_length=50)
    given = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)
    version = models.CharField(max_length=20)  # Policy version
    ip_address = models.GenericIPAddressField()
```

- [ ] **Implement right-to-be-forgotten**
  - File: Create `apps/api/views/data_deletion.py`
  - Django view with confirmation flow
  - Delete all user data after 30-day grace period

```python
# Minimal GDPR deletion - no frameworks
@login_required
def request_deletion(request):
    if request.method == 'POST':
        # Create deletion request
        deletion = DeletionRequest.objects.create(
            user=request.user,
            requested_at=timezone.now(),
            execute_at=timezone.now() + timedelta(days=30),
            status='pending'
        )

        # Send confirmation email
        send_mail(
            'Account Deletion Request',
            f'Your account will be deleted on {deletion.execute_at}',
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email]
        )

        return JsonResponse({'status': 'scheduled'})
```

- [ ] **Create privacy policy with consent tracking**
  - File: `docs/PRIVACY_POLICY.md`
  - Track policy version changes
  - Require re-consent on changes

- [ ] **Implement data breach notification system**
  - File: Create `apps/core/incident/breach_notification.py`
  - Pure Python email notifications
  - Track affected users

**Target Score After:** 95/100

---

### 3.2 SOC 2 Compliance (70→95)

#### Tasks:
- [ ] **Create formal incident response plan**
  - File: `docs/INCIDENT_RESPONSE.md`
  - Define roles and responsibilities
  - SLA: Critical (1hr), High (4hrs), Medium (1 day)
  - No tooling needed, just documentation

- [ ] **Implement change management workflow**
  - File: Create `apps/core/models/change_request.py`
  - Django model for change tracking
  - Approval workflow

```python
# Minimal change management - no frameworks
class ChangeRequest(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('requested', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('implemented', 'Implemented'),
        ('rejected', 'Rejected'),
    ]

    requested_by = models.ForeignKey(User, related_name='changes_requested')
    approved_by = models.ForeignKey(User, null=True, related_name='changes_approved')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    description = models.TextField()
    risk_assessment = models.TextField()
    rollback_plan = models.TextField()
    scheduled_date = models.DateTimeField()
```

- [ ] **Implement access review automation**
  - File: Create `apps/core/management/commands/access_review.py`
  - Django command to generate quarterly reports
  - Pure Python, no frameworks

```python
# Minimal access review - no frameworks
class Command(BaseCommand):
    def handle(self, *args, **options):
        # Generate access report
        users_with_admin = User.objects.filter(
            organizationmember__role__slug='admin',
            organizationmember__is_active=True
        )

        report = []
        for user in users_with_admin:
            report.append({
                'user': user.username,
                'email': user.email,
                'organizations': user.organizationmember_set.count(),
                'last_login': user.last_login,
            })

        # Write to CSV
        with open(f'/var/reports/access-review-{timezone.now().date()}.csv', 'w') as f:
            writer = csv.DictWriter(f, fieldnames=report[0].keys())
            writer.writeheader()
            writer.writerows(report)
```

- [ ] **Create vendor risk assessment template**
  - File: `docs/VENDOR_ASSESSMENT.md`
  - Document third-party services
  - Risk scoring matrix
  - No tools needed

- [ ] **Implement backup verification testing**
  - File: Update `lifecycle/restore.sh`
  - Add automated restore testing
  - Run monthly, verify integrity

**Target Score After:** 95/100

---

### 3.3 Session Management Enhancement (80→95)

#### Tasks:
- [ ] **Reduce remember-me timeout**
  - File: `apps/core/auth/views.py`
  - Change from 14 days to 7 days
  - Simple config change

- [ ] **Implement session activity timeout**
  - Add middleware to track last activity
  - Expire after 30 minutes inactivity
  - Pure Django middleware

```python
# Minimal activity timeout - no frameworks
class SessionActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get('last_activity')

            if last_activity:
                last_time = datetime.fromisoformat(last_activity)
                if timezone.now() - last_time > timedelta(minutes=30):
                    # Session expired due to inactivity
                    logout(request)
                    return redirect('login')

            request.session['last_activity'] = timezone.now().isoformat()

        return self.get_response(request)
```

- [ ] **Implement session binding**
  - Track IP address and User-Agent
  - Invalidate session if changed
  - Pure Python string comparison

```python
# Minimal session binding - no frameworks
def check_session_binding(request):
    stored_ip = request.session.get('ip_address')
    stored_ua = request.session.get('user_agent')

    current_ip = request.META.get('REMOTE_ADDR')
    current_ua = request.META.get('HTTP_USER_AGENT')

    if stored_ip and stored_ip != current_ip:
        logout(request)
        raise PermissionDenied("Session hijacking detected")

    if stored_ua and stored_ua != current_ua:
        logout(request)
        raise PermissionDenied("Session hijacking detected")

    # Store for next check
    request.session['ip_address'] = current_ip
    request.session['user_agent'] = current_ua
```

- [ ] **Invalidate all sessions on password change**
  - Django signal on User.save()
  - Delete all sessions for user
  - Built-in Django sessions

**Target Score After:** 95/100

---

## Phase 4: OPTIMIZATION (Week 11-16) - Excellence
**Goal:** Achieve 95+/100 in all metrics

### 4.1 Advanced Security Monitoring

#### Tasks:
- [ ] **Implement anomaly detection**
  - File: Create `apps/core/monitoring/anomaly_detection.py`
  - Pure Python statistical analysis
  - No ML frameworks needed

```python
# Minimal anomaly detection - no frameworks
import statistics

def detect_login_anomaly(user):
    # Get user's typical login times (hour of day)
    recent_logins = AuditLog.objects.filter(
        user=user,
        action='login',
        timestamp__gte=timezone.now() - timedelta(days=30)
    ).values_list('timestamp', flat=True)

    hours = [dt.hour for dt in recent_logins]

    if len(hours) < 5:
        return False  # Not enough data

    mean = statistics.mean(hours)
    stdev = statistics.stdev(hours)

    current_hour = timezone.now().hour

    # Flag if more than 2 standard deviations from mean
    if abs(current_hour - mean) > 2 * stdev:
        return True  # Anomalous login time

    return False
```

- [ ] **Create security dashboard**
  - File: Create `apps/core/views/security_dashboard.py`
  - Pure Django template rendering
  - Real-time metrics display

- [ ] **Implement automated threat response**
  - Auto-block IPs with suspicious activity
  - Use Django cache for IP blacklist
  - Email alerts on threats

**Target Score After:** 95/100

---

### 4.2 Performance Optimization

#### Tasks:
- [ ] **Optimize database queries**
  - Use `select_related()` and `prefetch_related()`
  - Add database indexes to AuditLog
  - Django ORM optimization only

- [ ] **Implement query result caching**
  - Cache expensive queries for 5 minutes
  - Django's built-in cache framework
  - No Redis needed for small deployments

```python
# Minimal caching - no frameworks
from django.core.cache import cache

def get_user_permissions_cached(user):
    cache_key = f"permissions:{user.id}"
    permissions = cache.get(cache_key)

    if permissions is None:
        permissions = PermissionService(user).get_all_permissions()
        cache.set(cache_key, permissions, 300)  # 5 minutes

    return permissions
```

- [ ] **Optimize static file delivery**
  - Enable gzip compression in nginx
  - Add far-future expires headers
  - Built-in nginx features

**Target Score After:** 95/100

---

### 4.3 Documentation & Training

#### Tasks:
- [ ] **Create security architecture document**
  - File: `docs/SECURITY_ARCHITECTURE.md`
  - Document all security controls
  - Threat model diagrams

- [ ] **Write secure coding guidelines**
  - File: `docs/SECURE_CODING.md`
  - Best practices for developers
  - Code review checklist

- [ ] **Create incident response playbooks**
  - File: `docs/playbooks/`
  - Step-by-step procedures for common incidents
  - No tools needed

- [ ] **Document compliance procedures**
  - File: `docs/COMPLIANCE.md`
  - GDPR, SOC 2 procedures
  - Audit evidence collection

**Target Score After:** 95/100

---

### 4.4 Testing & Validation

#### Tasks:
- [ ] **Create security test suite**
  - File: `control-panel/tests/security/`
  - Test authentication, authorization, encryption
  - Pure Django TestCase, no framework

```python
# Minimal security tests - no frameworks
class SecurityTestCase(TestCase):
    def test_idor_protection(self):
        """Test that users cannot access other users' resources"""
        user1 = User.objects.create_user('user1', password='pass')
        user2 = User.objects.create_user('user2', password='pass')

        deployment = ApplicationDeployment.objects.create(
            name='test',
            deployed_by=user1
        )

        # User2 should not be able to access user1's deployment
        self.client.force_login(user2)
        response = self.client.get(f'/deployments/{deployment.id}/')
        self.assertEqual(response.status_code, 403)
```

- [ ] **Implement automated security scanning**
  - Add to CI/CD pipeline
  - Use bandit (minimal SAST tool)
  - Use pip-audit (official Python tool)

- [ ] **Create penetration testing guide**
  - File: `docs/PENETRATION_TESTING.md`
  - Common attack vectors to test
  - Validation procedures

**Target Score After:** 95/100

---

## Success Criteria

### Metric Targets (95+/100 each):

- **Authentication:** 95/100
  - [x] Strong passwords (12+ chars, complexity)
  - [x] Account lockout (5 attempts)
  - [x] 2FA available and encrypted
  - [x] Session management (activity timeout)
  - [x] Password expiration (90 days)

- **Authorization:** 95/100
  - [x] No IDOR vulnerabilities
  - [x] Resource-level permissions
  - [x] Multi-tenant isolation
  - [x] Ownership verification on ALL queries

- **Encryption:** 95/100
  - [x] All secrets encrypted at rest
  - [x] TLS 1.2+ enforced
  - [x] Separate keys by purpose
  - [x] Key rotation mechanism
  - [x] No hardcoded keys

- **Input Validation:** 95/100
  - [x] All user input validated
  - [x] Whitelist approach for commands
  - [x] Path traversal prevention
  - [x] Rate limiting on failures

- **Session Management:** 95/100
  - [x] Activity timeout (30 min)
  - [x] Session binding (IP/UA)
  - [x] Secure cookies in production
  - [x] Invalidation on password change

- **Access Control:** 95/100
  - [x] RBAC implemented
  - [x] Permission checks logged
  - [x] Least privilege principle
  - [x] Regular access reviews

- **Audit Logging:** 95/100
  - [x] All actions logged
  - [x] Immutable logs
  - [x] Log integrity verification
  - [x] 365-day retention
  - [x] Real-time monitoring

- **Infrastructure:** 95/100
  - [x] Service hardening (systemd)
  - [x] File permissions locked down
  - [x] Network security (TLS, authentication)
  - [x] Log rotation configured

- **Dependencies:** 95/100
  - [x] All dependencies pinned
  - [x] No vulnerable packages
  - [x] Automated scanning in CI/CD
  - [x] Monthly updates

- **Compliance:** 95/100
  - [x] GDPR data export/deletion
  - [x] Consent management
  - [x] SOC 2 controls
  - [x] Incident response plan
  - [x] Change management

---

## Implementation Principles

### 1. Minimal Frameworks Approach

**Use Only:**
- Python standard library (secrets, hmac, hashlib, re, subprocess, shlex)
- Django built-in features (ORM, forms, authentication, cache, sessions)
- cryptography library (already dependency, for Fernet)
- PostgreSQL built-in features
- Nginx built-in features
- systemd built-in features

**AVOID:**
- Heavy security frameworks
- Third-party authentication libraries
- Complex RBAC frameworks (use our own)
- External SaaS services
- Unnecessary dependencies

### 2. Security by Design

- **Default Deny:** Deny all, explicitly allow needed actions
- **Least Privilege:** Minimum permissions required
- **Defense in Depth:** Multiple layers of security
- **Fail Securely:** Errors should be secure by default

### 3. Keep It Simple

- Pure Python implementations
- Clear, readable code
- Comprehensive comments
- No magic or complexity

---

## Timeline Summary

```
Week 1-2:   ████ Phase 1: Critical Fixes (Foundation)
Week 3-6:   ████████ Phase 2: High Priority (Enhancement)
Week 7-10:  ████████ Phase 3: Medium Priority (Compliance)
Week 11-16: ████████████ Phase 4: Optimization (Excellence)
```

**Total Time:** 12-16 weeks
**Total Effort:** ~320 hours
**Team Size:** 2-3 developers

---

## Testing Milestones

- **Week 2:** All P0 vulnerabilities fixed, security scan passes
- **Week 6:** No HIGH vulnerabilities, penetration test phase 1
- **Week 10:** Compliance audit ready, SOC 2 preparation
- **Week 16:** Full security certification, A-grade achieved

---

## Cost Estimate (Minimal Approach)

**Internal Development:** 320 hours @ $150/hr = $48,000

**External Costs:**
- Penetration testing: $10,000
- SOC 2 audit: $15,000
- Total: $25,000

**TOTAL:** $73,000

**vs Framework-Heavy Approach:** $150,000+

**Savings:** $77,000+ (minimal approach)

---

## Monitoring & Maintenance

### Ongoing Tasks (Post-A-Grade):

- **Weekly:** Dependency security scans
- **Monthly:** Access reviews, log analysis
- **Quarterly:** Penetration testing, compliance audit
- **Annually:** Full security assessment

---

## Conclusion

This plan achieves A-grade (95+/100) security across ALL metrics using:
- ✅ Minimal external dependencies
- ✅ Python/Django built-in features
- ✅ Standard library components
- ✅ No heavy frameworks
- ✅ Clear, maintainable code
- ✅ Comprehensive documentation

**Result:** Enterprise-grade security without framework bloat.

**Start Date:** TBD
**Target Completion:** 12-16 weeks from start
**Confidence Level:** HIGH (achievable with focused effort)
