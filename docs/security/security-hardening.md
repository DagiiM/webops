# WebOps Security Hardening Guide

**Comprehensive Security Best Practices and Configuration**

## Overview

This guide provides detailed security hardening procedures for WebOps deployments, covering infrastructure, application, network, and operational security best practices.

## Infrastructure Security

### Operating System Hardening

#### Ubuntu/Debian Hardening
```bash
# Update and upgrade system
sudo apt update && sudo apt upgrade -y

# Install security tools
sudo apt install -y fail2ban unattended-upgrades apt-listchanges

# Configure automatic security updates
sudo dpkg-reconfigure -plow unattended-upgrades

# Remove unnecessary packages
sudo apt purge -y telnet rsh-client rsh-redone-client yp-tools
sudo apt purge -y telnetd nis ypbind rsh-server

# Configure firewall (UFW)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

#### System Service Hardening
```bash
# Disable unnecessary services
sudo systemctl disable avahi-daemon
sudo systemctl disable cups
sudo systemctl disable isc-dhcp-server
sudo systemctl disable isc-dhcp-server6
sudo systemctl disable slapd
sudo systemctl disable nfs-kernel-server
sudo systemctl disable rpcbind
sudo systemctl disable dovecot
sudo systemctl disable squid
sudo systemctl disable snmpd

# SSH Server Hardening
sudo sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sudo sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
sudo sed -i 's/#ClientAliveInterval 0/ClientAliveInterval 300/' /etc/ssh/sshd_config
sudo sed -i 's/#ClientAliveCountMax 3/ClientAliveCountMax 2/' /etc/ssh/sshd_config

sudo systemctl restart sshd
```

### Docker Security Hardening

#### Docker Daemon Configuration
```bash
# Create docker daemon config
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "userns-remap": "default",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 64000,
      "Soft": 64000
    }
  },
  "live-restore": true
}
EOF

# Apply user namespace remapping
echo "dockremap:165536:65536" | sudo tee -a /etc/subuid
echo "dockremap:165536:65536" | sudo tee -a /etc/subgid

# Restart docker
sudo systemctl restart docker
```

#### Container Security Best Practices
```dockerfile
# Security-hardened Dockerfile
FROM python:3.13-slim

# Security scanning tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r webops && useradd -r -g webops -d /app webops

# Set working directory
WORKDIR /app

# Copy application files
COPY --chown=webops:webops . .

# Switch to non-root user
USER webops

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Run application
CMD ["gunicorn", "webops.wsgi:application", "--bind", "0.0.0.0:8000"]
```

## Application Security

### Django Security Configuration

#### Settings.py Security Hardening
```python
# security.py - Security-specific settings
import os
from django.core.management.utils import get_random_secret_key

# Generate secret key if not set
SECRET_KEY = os.environ.get('SECRET_KEY', get_random_secret_key())

# Security middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',  # Content Security Policy
    # ... other middleware
]

# HTTPS settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security Policy
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'"]
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'"]
CSP_IMG_SRC = ["'self'", "data:"]
CSP_FONT_SRC = ["'self'"]
CSP_CONNECT_SRC = ["'self'"]
CSP_OBJECT_SRC = ["'none'"]
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]
CSP_FRAME_ANCESTORS = ["'self'"]
CSP_UPGRADE_INSECURE_REQUESTS = True

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# File upload security
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Database connection security
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'sslrootcert': '/path/to/ca-certificate.crt',
        },
        'CONN_MAX_AGE': 300,
        'CONN_HEALTH_CHECKS': True,
    }
}
```

### Django Security Middleware

#### Custom Security Headers
```python
# middleware/security_headers.py
from django.utils.deprecation import MiddlewareMixin

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to all responses."""
    
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Feature Policy (legacy)
        response['Feature-Policy'] = (
            "geolocation 'none'; microphone 'none'; camera 'none';"
        )
        
        return response
```

#### Rate Limiting Middleware
```python
# middleware/rate_limiting.py
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone

class RateLimitMiddleware:
    """Rate limiting middleware for API endpoints."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit = 100  # requests per minute
        self.window_size = 60  # seconds

    def __call__(self, request):
        # Only apply to API endpoints
        if request.path.startswith('/api/'):
            client_ip = self.get_client_ip(request)
            endpoint = request.path
            
            current_time = timezone.now().timestamp()
            window_start = current_time - self.window_size
            
            # Get request count for this window
            key = f"rate_limit:{client_ip}:{endpoint}"
            requests = cache.get(key, [])
            
            # Remove old requests
            requests = [t for t in requests if t > window_start]
            
            if len(requests) >= self.rate_limit:
                return JsonResponse(
                    {'error': 'Rate limit exceeded'},
                    status=429
                )
            
            # Add current request
            requests.append(current_time)
            cache.set(key, requests, self.window_size)
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```

## Database Security

### PostgreSQL Hardening

#### PostgreSQL Configuration
```sql
-- PostgreSQL security configuration
ALTER SYSTEM SET listen_addresses = 'localhost';
ALTER SYSTEM SET password_encryption = 'scram-sha-256';
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem';
ALTER SYSTEM SET ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key';
ALTER SYSTEM SET ssl_ca_file = '/etc/ssl/certs/ca-certificates.crt';

-- Connection security
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET superuser_reserved_connections = 3;

-- Authentication
ALTER SYSTEM SET auth_delay.milliseconds = 1000;

-- Logging
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_statement = 'ddl';
ALTER SYSTEM SET log_duration = on;

-- Apply changes
SELECT pg_reload_conf();

-- Create application user with minimal privileges
CREATE USER webops_app WITH PASSWORD 'secure_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE webops TO webops_app;
GRANT USAGE ON SCHEMA public TO webops_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO webops_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO webops_app;

-- Revoke public privileges
REVOKE ALL ON DATABASE webops FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
```

#### Database Connection Pooling
```python
# database/pooling.py
from django.db import connections
from django.db.utils import OperationalError
import threading
import time

class ConnectionHealthCheck:
    """Database connection health monitoring."""
    
    def __init__(self):
        self.health_check_interval = 300  # 5 minutes
        self.running = False
        self.thread = None
    
    def start(self):
        """Start health check thread."""
        self.running = True
        self.thread = threading.Thread(target=self._health_check_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop health check thread."""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _health_check_loop(self):
        """Health check loop."""
        while self.running:
            self.check_connections()
            time.sleep(self.health_check_interval)
    
    def check_connections(self):
        """Check all database connections."""
        for conn_name in connections:
            try:
                conn = connections[conn_name]
                if conn.connection is not None:
                    # Execute simple query to check connection
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT 1')
                        cursor.fetchone()
            except OperationalError:
                # Connection is bad, close it
                conn.close_if_unusable_or_obsolete()
```

## Network Security

### Network Hardening

#### Firewall Rules
```bash
# Advanced UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow specific services
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# Allow specific IP ranges for administration
sudo ufw allow from 192.168.1.0/24 to any port 22
sudo ufw allow from 10.0.0.0/8 to any port 22

# Rate limiting for SSH
sudo ufw limit ssh

# Enable logging
sudo ufw logging on
```

#### Network Monitoring
```bash
# Install network monitoring tools
sudo apt install -y tcpdump nethogs iftop

# Monitor network traffic
sudo tcpdump -i eth0 -n not port 22

# Monitor bandwidth usage
nethogs eth0

# Monitor connections
iftop -i eth0
```

### SSL/TLS Configuration

#### Nginx SSL Configuration
```nginx
# nginx/ssl.conf
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;

# HSTS (1 year)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;

# SSL session cache
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;

# DH parameters (generate with: openssl dhparam -out /etc/ssl/certs/dhparam.pem 2048)
ssl_dhparam /etc/ssl/certs/dhparam.pem;

# SSL buffer size
ssl_buffer_size 4k;

# Early data
ssl_early_data on;
```

#### Certificate Management
```bash
# Automate certificate renewal with certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test renewal
sudo certbot renew --dry-run

# Set up automatic renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Authentication and Authorization

### Advanced Authentication

#### Multi-Factor Authentication
```python
# auth/mfa.py
import pyotp
import qrcode
from io import BytesIO
import base64

class MFAService:
    """Multi-Factor Authentication service."""
    
    def generate_secret_key(self):
        """Generate a new TOTP secret key."""
        return pyotp.random_base32()
    
    def generate_provisioning_uri(self, user, secret_key):
        """Generate provisioning URI for authenticator apps."""
        return pyotp.totp.TOTP(secret_key).provisioning_uri(
            name=user.email,
            issuer_name="WebOps"
        )
    
    def generate_qr_code(self, provisioning_uri):
        """Generate QR code for authenticator setup."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for embedding in HTML
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_code(self, secret_key, code):
        """Verify TOTP code."""
        totp = pyotp.TOTP(secret_key)
        return totp.verify(code)
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes."""
        import secrets
        return [secrets.token_hex(4).upper() for _ in range(count)]
```

#### Password Policy Enforcement
```python
# auth/password_policy.py
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class PasswordValidator:
    """Custom password validation with advanced policies."""
    
    def validate(self, password, user=None):
        """Validate password against policy."""
        errors = []
        
        # Minimum length
        if len(password) < 12:
            errors.append(_("Password must be at least 12 characters long."))
        
        # Complexity requirements
        if not re.search(r'[A-Z]', password):
            errors.append(_("Password must contain at least one uppercase letter."))
        
        if not re.search(r'[a-z]', password):
            errors.append(_("Password must contain at least one lowercase letter."))
        
        if not re.search(r'\d', password):
            errors.append(_("Password must contain at least one digit."))
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_("Password must contain at least one special character."))
        
        # Common password check
        common_passwords = ['password', '123456', 'qwerty', 'letmein']
        if password.lower() in common_passwords:
            errors.append(_("Password is too common."))
        
        # Sequential characters check
        if self.has_sequential_chars(password):
            errors.append(_("Password contains sequential characters."))
        
        if errors:
            raise ValidationError(errors)
    
    def has_sequential_chars(self, password):
        """Check for sequential characters."""
        for i in range(len(password) - 2):
            # Check ascending sequence
            if (ord(password[i]) + 1 == ord(password[i+1]) and
                ord(password[i]) + 2 == ord(password[i+2])):
                return True
            # Check descending sequence
            if (ord(password[i]) - 1 == ord(password[i+1]) and
                ord(password[i]) - 2 == ord(password[i+2])):
                return True
        return False
    
    def get_help_text(self):
        """Help text for password requirements."""
        return _(
            "Your password must contain at least 12 characters, "
            "including uppercase, lowercase, digits, and special characters. "
            "Avoid sequential characters and common passwords."
        )
```

## Monitoring and Logging

### Security Monitoring

#### Audit Logging
```python
# logging/audit.py
import logging
from django.db import models
from django.contrib.auth.models import User

class AuditLog(models.Model):
    """Comprehensive security audit logging."""
    
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('create', 'Resource Created'),
        ('update', 'Resource Updated'),
        ('delete', 'Resource Deleted'),
        ('access', 'Resource Accessed'),
        ('config_change', 'Configuration Changed'),
        ('security_event', 'Security Event'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='success')
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]
        ordering = ['-timestamp']

class AuditLogger:
    """Audit logging service."""
    
    def log_event(self, action, resource_type, resource_id='', 
                 user=None, ip_address=None, user_agent=None, 
                 details=None, status='success'):
        """Log an audit event."""
        AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            status=status
        )
```

#### Security Event Monitoring
```python
# monitoring/security.py
import logging
from datetime import datetime, timedelta
from django.db.models import Count

class SecurityMonitor:
    """Real-time security event monitoring."""
    
    def __init__(self):
        self.logger = logging.getLogger('security')
    
    def monitor_failed_logins(self):
        """Monitor failed login attempts."""
        threshold = 5  # Failed attempts threshold
        window_minutes = 15  # Time window
        
        recent_failures = AuditLog.objects.filter(
            action='login',
            status='failure',
            timestamp__gte=datetime.now() - timedelta(minutes=window_minutes)
        ).values('ip_address').annotate(count=Count('id')).filter(count__gte=threshold)
        
        for failure in recent_failures:
            self.logger.warning(
                f"Brute force attempt detected from {failure['ip_address']}: "
                f"{failure['count']} failed login attempts in {window_minutes} minutes"
            )
            
            # Implement automatic blocking
            self.block_ip(failure['ip_address'])
    
    def monitor_suspicious_activity(self):
        """Monitor for suspicious activity patterns."""
        # Monitor rapid resource creation
        rapid_creations = AuditLog.objects.filter(
            action='create',
            timestamp__gte=datetime.now() - timedelta(minutes=5)
        ).values('user').annotate(count=Count('id')).filter(count__gte=10)
        
        for creation in rapid_creations:
            self.logger.warning(
                f"Rapid resource creation by user {creation['user']}: "
                f"{creation['count']} creations in 5 minutes"
            )
    
    def block_ip(self, ip_address):
        """Block IP address using fail2ban or similar."""
        # Implement IP blocking logic
        # This could interact with fail2ban, iptables, or cloud firewall
        pass
```

## Incident Response

### Security Incident Handling

#### Incident Response Plan
```python
# incident/response.py
class IncidentResponse:
    """Security incident response procedures."""
    
    def handle_security_incident(self, incident_type, severity, details):
        """Handle security incident according to type and severity."""
        
        incident_handlers = {
            'brute_force': self.handle_brute_force,
            'data_breach': self.handle_data_breach,
            'malware': self.handle_malware,
            'dos': self.handle_dos,
        }
        
        handler = incident_handlers.get(incident_type, self.handle_generic)
        handler(severity, details)
    
    def handle_brute_force(self, severity, details):
        """Handle brute force attack."""
        # Immediate actions
        self.block_attacker_ip(details['ip_address'])
        self.increase_logging()
        self.notify_security_team(severity, details)
        
        # Investigation
        self.analyze_attack_pattern(details)
        self.review_affected_accounts(details)
        
        # Recovery
        self.reset_compromised_passwords()
        self.implement_additional_protections()
    
    def handle_data_breach(self, severity, details):
        """Handle data breach incident."""
        # Containment
        self.isolate_affected_systems()
        self.preserve_evidence()
        
        # Assessment
        self.assess_breach_scope()
        self.identify_affected_data()
        
        # Notification
        if severity in ['high', 'critical']:
            self.notify_affected_parties()
            self.report_to_authorities()
        
        # Recovery
        self.secure_vulnerabilities()
        self.implement_preventive_measures()
    
    def handle_dos(self, severity, details):
        """Handle Denial of Service attack."""
        # Mitigation
        self.enable_dos_protection()
        self.block_malicious_traffic()
        
        # Monitoring
        self.monitor_traffic_patterns()
        self.analyze_attack_vectors()
        
        # Recovery
        self.restore_normal_operations()
        self.implement_dos_protections()
```

#### Forensics and Investigation
```python
# incident/forensics.py
import hashlib
import json
from datetime import datetime

class ForensicInvestigator:
    """Digital forensics and investigation tools."""
    
    def collect_evidence(self, incident_id):
        """Collect digital evidence for investigation."""
        evidence = {
            'timestamp': datetime.now().isoformat(),
            'incident_id': incident_id,
            'system_info': self.collect_system_info(),
            'network_info': self.collect_network_info(),
            'process_info': self.collect_process_info(),
            'log_files': self.collect_log_files(),
            'database_state': self.collect_database_state(),
        }
        
        # Create evidence hash for integrity
        evidence_hash = self.calculate_evidence_hash(evidence)
        evidence['integrity_hash'] = evidence_hash
        
        return evidence
    
    def calculate_evidence_hash(self, evidence):
        """Calculate hash for evidence integrity verification."""
        evidence_str = json.dumps(evidence, sort_keys=True)
        return hashlib.sha256(evidence_str.encode()).hexdigest()
    
    def collect_system_info(self):
        """Collect system information."""
        import platform
        import psutil
        
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'boot_time': psutil.boot_time(),
            'users': psutil.users(),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': psutil.disk_usage('/')._asdict(),
        }
    
    def collect_network_info(self):
        """Collect network information."""
        import psutil
        
        return {
            'connections': [conn._asdict() for conn in psutil.net_connections()],
            'interfaces': psutil.net_if_addrs(),
            'io_counters': psutil.net_io_counters()._asdict(),
        }
```

## Compliance and Regulations

### GDPR Compliance

#### Data Protection Implementation
```python
# compliance/gdpr.py
from django.db.models import Q

class GDPRCompliance:
    """GDPR compliance implementation."""
    
    def process_right_to_be_forgotten(self, user):
        """Process right to be forgotten request."""
        # Anonymize personal data
        self.anonymize_user_data(user)
        
        # Delete or anonymize associated data
        self.process_user_associated_data(user)
        
        # Log the request
        self.log_compliance_action(user, 'right_to_be_forgotten')
    
    def process_data_portability(self, user):
        """Process data portability request."""
        # Gather all user data
        user_data = self.gather_user_data(user)
        
        # Format for portability
        export_data = self.format_export_data(user_data)
        
        # Generate export file
        export_file = self.generate_export_file(export_data)
        
        # Log the request
        self.log_compliance_action(user, 'data_portability')
        
        return export_file
    
    def anonymize_user_data(self, user):
        """Anonymize user personal data."""
        # Anonymize user profile
        user.email = f"anon_{user.id}@example.com"
        user.first_name = "Anonymous"
        user.last_name = "User"
        user.username = f"anon_{user.id}"
        user.save()
        
        # Anonymize related data
        self.anonymize_related_data(user)
    
    def gather_user_data(self, user):
        """Gather all data related to a user."""
        user_data = {
            'profile': self.get_user_profile_data(user),
            'activity': self.get_user_activity_data(user),
            'preferences': self.get_user_preferences(user),
            'content': self.get_user_content(user),
        }
        
        return user_data
```

### PCI DSS Compliance

#### Payment Card Security
```python
# compliance/pci.py
import re

class PCISecurity:
    """PCI DSS compliance implementation."""
    
    def validate_card_number(self, card_number):
        """Validate credit card number using Luhn algorithm."""
        # Remove non-digit characters
        card_number = re.sub(r'\D', '', card_number)
        
        # Check length
        if not 13 <= len(card_number) <= 19:
            return False
        
        # Luhn algorithm
        total = 0
        reverse_digits = card_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        return total % 10 == 0
    
    def mask_card_number(self, card_number):
        """Mask credit card number for display."""
        if len(card_number) <= 4:
            return card_number
        return '*' * (len(card_number) - 4) + card_number[-4:]
    
    def is_card_number_stored(self, card_number):
        """Check if card number is already stored (prevent duplicates)."""
        # Implement duplicate checking logic
        # This should use secure hashing for comparison
        pass

    def encrypt_card_data(self, card_data):
        """Encrypt card data using strong encryption."""
        # Implement encryption using cryptography library
        # Use AES-256-GCM or similar strong algorithm
        pass

    def decrypt_card_data(self, encrypted_data):
        """Decrypt card data."""
        # Implement decryption
        pass

## Backup and Disaster Recovery

### Secure Backup Procedures

#### Encrypted Backups
```bash
# Create encrypted backups
#!/bin/bash

# Configuration
BACKUP_DIR="/backups"
ENCRYPTION_KEY="/etc/backup-key.key"
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate encryption key if not exists
if [ ! -f "$ENCRYPTION_KEY" ]; then
    openssl rand -base64 32 > "$ENCRYPTION_KEY"
    chmod 600 "$ENCRYPTION_KEY"
fi

# Backup database with encryption
pg_dump -h localhost -U webops webops | \
    gzip | \
    openssl enc -aes-256-cbc -salt -pass file:"$ENCRYPTION_KEY" \
    -out "$BACKUP_DIR/db-backup-$(date +%Y%m%d-%H%M%S).sql.gz.enc"

# Backup application files
tar czf - /app | \
    openssl enc -aes-256-cbc -salt -pass file:"$ENCRYPTION_KEY" \
    -out "$BACKUP_DIR/app-backup-$(date +%Y%m%d-%H%M%S).tar.gz.enc"

# Clean up old backups
find "$BACKUP_DIR" -name "*.enc" -mtime +$RETENTION_DAYS -delete

# Verify backup integrity
for backup_file in "$BACKUP_DIR"/*.enc; do
    if openssl enc -d -aes-256-cbc -pass file:"$ENCRYPTION_KEY" \
       -in "$backup_file" 2>/dev/null | gunzip | head -1 >/dev/null; then
        echo "Backup $backup_file is valid"
    else
        echo "Backup $backup_file is corrupted"
        rm -f "$backup_file"
    fi
done
```

#### Backup Verification
```python
# backup/verification.py
import subprocess
import os
from datetime import datetime, timedelta

class BackupVerifier:
    """Backup verification and integrity checking."""
    
    def verify_backup_integrity(self, backup_file, encryption_key):
        """Verify backup file integrity."""
        try:
            # Test decryption
            cmd = [
                'openssl', 'enc', '-d', '-aes-256-cbc',
                '-pass', f'file:{encryption_key}',
                '-in', backup_file
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            
            return result.returncode == 0
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False
    
    def verify_backup_completeness(self, backup_file, expected_content):
        """Verify backup contains expected content."""
        # Implement content verification logic
        # This could check for specific files, database tables, etc.
        pass
    
    def run_backup_health_check(self):
        """Run comprehensive backup health check."""
        checks = {
            'recent_backups': self.check_recent_backups(),
            'backup_integrity': self.check_backup_integrity(),
            'storage_space': self.check_storage_space(),
            'encryption_keys': self.check_encryption_keys(),
        }
        
        return all(checks.values()), checks
```

### Disaster Recovery Plan

#### Recovery Procedures
```python
# recovery/plan.py
class DisasterRecovery:
    """Disaster recovery procedures and automation."""
    
    def execute_recovery_plan(self, disaster_type):
        """Execute appropriate recovery plan."""
        recovery_plans = {
            'database_failure': self.recover_database,
            'storage_failure': self.recover_storage,
            'network_outage': self.recover_network,
            'security_breach': self.recover_security_breach,
        }
        
        plan = recovery_plans.get(disaster_type, self.recover_generic)
        return plan()
    
    def recover_database(self):
        """Recover from database failure."""
        steps = [
            self.assess_database_damage,
            self.restore_from_backup,
            self.verify_data_integrity,
            self.resume_operations,
        ]
        
        return self.execute_recovery_steps(steps)
    
    def recover_security_breach(self):
        """Recover from security breach."""
        steps = [
            self.isolate_affected_systems,
            self.assess_breach_scope,
            self.eradicate_malware,
            self.restore_from_clean_backup,
            self.implement_security_enhancements,
        ]
        
        return self.execute_recovery_steps(steps)
    
    def execute_recovery_steps(self, steps):
        """Execute recovery steps with logging."""
        results = {}
        
        for step in steps:
            try:
                result = step()
                results[step.__name__] = {'success': True, 'result': result}
            except Exception as e:
                results[step.__name__] = {'success': False, 'error': str(e)}
                # Decide whether to continue or abort
                if self.is_critical_step(step):
                    break
        
        return results
```

## Security Testing and Validation

### Automated Security Testing

#### Security Scanning
```bash
# Security scanning script
#!/bin/bash

# Dependency scanning
npm audit --audit-level moderate
pip-audit

# Static code analysis
bandit -r . -ll
safety check

# Container scanning
docker scan webops-app:latest

# Network vulnerability scanning
nmap -sV -sC -O localhost

# SSL/TLS testing
sslscan localhost
testssl.sh localhost

# Generate security report
{
    echo "Security Scan Report"
    echo "==================="
    echo "Date: $(date)"
    echo ""
    echo "Dependency Vulnerabilities:"
    npm audit --json | jq '.metadata.vulnerabilities'
    echo ""
    echo "Python Security Issues:"
    safety check --json
    echo ""
    echo "Container Vulnerabilities:"
    docker scan webops-app:latest --json | jq '.vulnerabilities'
} > security-report.txt
```

#### Penetration Testing
```python
# security/penetration_test.py
import requests
from urllib.parse import urljoin

class PenetrationTester:
    """Automated penetration testing utilities."""
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_sql_injection(self, endpoints):
        """Test for SQL injection vulnerabilities."""
        payloads = [
            "' OR '1'='1",
            "; DROP TABLE users; --",
            "' UNION SELECT NULL, username, password FROM users --",
        ]
        
        vulnerabilities = []
        
        for endpoint in endpoints:
            for payload in payloads:
                test_url = urljoin(self.base_url, endpoint)
                
                # Test GET parameters
                if '?' in endpoint:
                    response = self.session.get(test_url + payload)
                    if self.is_sql_error(response.text):
                        vulnerabilities.append({
                            'endpoint': endpoint,
                            'payload': payload,
                            'type': 'SQL Injection',
                            'method': 'GET'
                        })
                
                # Test POST data
                else:
                    data = {'input': payload}
                    response = self.session.post(test_url, data=data)
                    if self.is_sql_error(response.text):
                        vulnerabilities.append({
                            'endpoint': endpoint,
                            'payload': payload,
                            'type': 'SQL Injection',
                            'method': 'POST'
                        })
        
        return vulnerabilities
    
    def test_xss(self, endpoints):
        """Test for Cross-Site Scripting vulnerabilities."""
        payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "onerror=alert('XSS')",
        ]
        
        vulnerabilities = []
        
        for endpoint in endpoints:
            for payload in payloads:
                test_url = urljoin(self.base_url, endpoint)
                
                response = self.session.get(test_url + payload)
                if payload in response.text and '&lt;script&gt;' not in response.text:
                    vulnerabilities.append({
                        'endpoint': endpoint,
                        'payload': payload,
                        'type': 'XSS',
                        'method': 'GET'
                    })
        
        return vulnerabilities
    
    def is_sql_error(self, response_text):
        """Check if response contains SQL error messages."""
        sql_errors = [
            'sql syntax',
            'mysql_fetch_array',
            'postgresql exception',
            'ora-',
            'microsoft odbc',
        ]
        
        return any(error in response_text.lower() for error in sql_errors)
```

### Security Validation

#### Configuration Validation
```python
# security/validation.py
import yaml
import json
from django.conf import settings

class SecurityValidator:
    """Security configuration validation."""
    
    def validate_django_settings(self):
        """Validate Django security settings."""
        checks = {
            'debug_mode': not settings.DEBUG,
            'https_redirect': settings.SECURE_SSL_REDIRECT,
            'secure_cookies': settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE,
            'hsts_enabled': settings.SECURE_HSTS_SECONDS > 0,
            'xss_protection': settings.SECURE_BROWSER_XSS_FILTER,
            'content_type_nosniff': settings.SECURE_CONTENT_TYPE_NOSNIFF,
            'frame_options': settings.X_FRAME_OPTIONS == 'DENY',
        }
        
        return checks, all(checks.values())
    
    def validate_database_config(self):
        """Validate database security configuration."""
        db_config = settings.DATABASES['default']
        
        checks = {
            'ssl_required': db_config.get('OPTIONS', {}).get('sslmode') == 'require',
            'no_plaintext_passwords': 'password' not in str(db_config).lower(),
            'connection_limit': db_config.get('CONN_MAX_AGE', 0) <= 300,
            'connection_pooling': 'CONN_MAX_AGE' in db_config,
        }
        
        return checks, all(checks.values())
    
    def validate_file_permissions(self):
        """Validate file and directory permissions."""
        import os
        import stat
        
        critical_paths = [
            settings.MEDIA_ROOT,
            settings.STATIC_ROOT,
            settings.BASE_DIR,
        ]
        
        checks = {}
        
        for path in critical_paths:
            if os.path.exists(path):
                mode = os.stat(path).st_mode
                checks[f'{path}_group_write'] = not (mode & stat.S_IWGRP)
                checks[f'{path}_other_write'] = not (mode & stat.S_IWOTH)
        
        return checks, all(checks.values())
```

## Continuous Security Monitoring

### Real-time Security Monitoring

#### Security Dashboard
```python
# monitoring/dashboard.py
from datetime import datetime, timedelta
from django.db.models import Count, Q

class SecurityDashboard:
    """Real-time security monitoring dashboard."""
    
    def get_security_overview(self):
        """Get comprehensive security overview."""
        return {
            'failed_logins': self.get_failed_login_stats(),
            'security_events': self.get_security_event_stats(),
            'vulnerability_scan': self.get_vulnerability_scan_results(),
            'system_health': self.get_system_health(),
            'compliance_status': self.get_compliance_status(),
        }
    
    def get_failed_login_stats(self):
        """Get failed login statistics."""
        last_hour = datetime.now() - timedelta(hours=1)
        
        stats = AuditLog.objects.filter(
            action='login',
            status='failure',
            timestamp__gte=last_hour
        ).aggregate(
            total=Count('id'),
            by_ip=Count('ip_address', distinct=True),
            by_user=Count('user', distinct=True)
        )
        
        return {
            'total_failures': stats['total'],
            'unique_ips': stats['by_ip'],
            'unique_users': stats['by_user'],
            'time_period': 'last_hour',
        }
    
    def get_security_event_stats(self):
        """Get security event statistics."""
        last_24h = datetime.now() - timedelta(hours=24)
        
        events = AuditLog.objects.filter(
            timestamp__gte=last_24h
        ).exclude(
            Q(action='login') | Q(action='logout')
        ).values('action').annotate(count=Count('id'))
        
        return {
            'events_by_type': {item['action']: item['count'] for item in events},
            'time_period': 'last_24h',
        }
    
    def get_vulnerability_scan_results(self):
        """Get latest vulnerability scan results."""
        # This would integrate with your vulnerability scanning tools
        # For example: Snyk, Nessus, OpenVAS, etc.
        
        return {
            'last_scan': datetime.now().isoformat(),
            'critical_vulnerabilities': 0,
            'high_vulnerabilities': 0,
            'medium_vulnerabilities': 0,
            'low_vulnerabilities': 0,
            'scan_status': 'completed',
        }
    
    def get_system_health(self):
        """Get system health status."""
        import psutil
        
        return {
            'cpu_usage': psutil.cpu_percent(),
            'memory_usage': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'network_io': psutil.net_io_counters()._asdict(),
            'uptime': psutil.boot_time(),
        }
```

#### Alerting System
```python
# monitoring/alerts.py
import smtplib
from email.mime.text import MIMEText
from django.conf import settings

class SecurityAlertSystem:
    """Security alert and notification system."""
    
    def send_alert(self, alert_type, severity, message, details=None):
        """Send security alert."""
        recipients = self.get_alert_recipients(severity)
        
        # Email alert
        if 'email' in recipients:
            self.send_email_alert(alert_type, severity, message, details, recipients['email'])
        
        # Slack alert
        if 'slack' in recipients:
            self.send_slack_alert(alert_type, severity, message, details, recipients['slack'])
        
        # SMS alert (for critical issues)
        if severity == 'critical' and 'sms' in recipients:
            self.send_sms_alert(alert_type, message, recipients['sms'])
    
    def send_email_alert(self, alert_type, severity, message, details, recipients):
        """Send email alert."""
        subject = f"[{severity.upper()}] {alert_type} - {message}"
        
        body = f"""
Security Alert
=============

Type: {alert_type}
Severity: {severity}
Message: {message}

Time: {datetime.now().isoformat()}

Details:
{json.dumps(details, indent=2) if details else 'No additional details'}

Please investigate immediately.
"""
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = settings.EMAIL_HOST_USER
        msg['To'] = ', '.join(recipients)
        
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            if settings.EMAIL_USE_TLS:
                server.starttls()
            if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)
    
    def get_alert_recipients(self, severity):
        """Get appropriate alert recipients based on severity."""
        recipients = {
            'critical': {
                'email': ['security-team@example.com', 'admin@example.com'],
                'slack': ['#security-critical'],
                'sms': ['+1234567890'],
            },
            'high': {
                'email': ['security-team@example.com'],
                'slack': ['#security-alerts'],
            },
            'medium': {
                'email': ['security-team@example.com'],
            },
            'low': {
                'email': ['security-team@example.com'],
            },
        }
        
        return recipients.get(severity, recipients['low'])
```

## Security Training and Awareness

### Security Best Practices

#### Developer Security Guidelines
```markdown
# WebOps Developer Security Guidelines

## Authentication and Session Management

### Password Security
- Use strong, unique passwords (min 12 characters)
- Implement proper password hashing (bcrypt, Argon2)
- Enforce password complexity requirements
- Implement account lockout after multiple failed attempts

### Session Management
- Use secure, HTTP-only cookies
- Implement session expiration
- Regenerate session IDs after login
- Store sessions in secure, server-side storage

## Input Validation

### SQL Injection Prevention
- Use parameterized queries exclusively
- Never concatenate user input into SQL queries
- Use ORM methods instead of raw SQL when possible

### Cross-Site Scripting (XSS) Prevention
- Validate and sanitize all user input
- Use context-aware output encoding
- Implement Content Security Policy (CSP)
- Avoid using `innerHTML` with user content

### Cross-Site Request Forgery (CSRF) Protection
- Use Django's built-in CSRF protection
- Implement double-submit cookie pattern for APIs
- Validate Origin and Referer headers

## Data Protection

### Sensitive Data Handling
- Never log sensitive data (passwords, tokens, PII)
- Encrypt sensitive data at rest and in transit
- Implement proper key management
- Follow data minimization principles

### File Upload Security
- Validate file types and extensions
- Scan uploaded files for malware
- Store uploaded files outside web root
- Implement proper access controls

## Error Handling and Logging

### Error Messages
- Never expose sensitive information in error messages
- Use generic error messages for users
- Log detailed errors for developers

### Security Logging
- Log all security-relevant events
- Include sufficient context in log messages
- Protect log files from unauthorized access
- Implement log rotation and retention

## Infrastructure Security

### Container Security
- Use minimal base images
- Run as non-root user
- Remove unnecessary packages
- Scan images for vulnerabilities

### Network Security
- Use firewalls to restrict access
- Implement network segmentation
- Use VPN for administrative access
- Monitor network traffic

## Compliance Requirements

### GDPR Compliance
- Implement right to be forgotten
- Provide data portability
- Conduct Data Protection Impact Assessments
- Appoint Data Protection Officer if required

### PCI DSS Compliance
- Encrypt cardholder data
- Restrict access to need-to-know basis
- Implement strong access control measures
- Regularly test security systems

## Continuous Security

### Code Review
- Conduct security-focused code reviews
- Use automated security scanning tools
- Train developers on security best practices

### Security Testing
- Implement automated security tests
- Conduct regular penetration testing
- Perform vulnerability assessments
- Monitor for new security threats

### Incident Response
- Develop incident response plan
- Conduct regular security drills
- Establish communication protocols
- Learn from security incidents
```

#### Security Awareness Training
```python
# training/security_awareness.py
from datetime import datetime, timedelta

class SecurityAwarenessProgram:
    """Security awareness training program."""
    
    def schedule_training(self, user, training_type):
        """Schedule security awareness training."""
        training_modules = {
            'basic': {
                'title': 'Basic Security Awareness',
                'duration': timedelta(hours=1),
                'topics': [
                    'Password Security',
                    'Phishing Awareness',
                    'Social Engineering',
                    'Data Protection',
                ]
            },
            'advanced': {
                'title': 'Advanced Security Training',
                'duration': timedelta(hours=2),
                'topics': [
                    'Secure Coding Practices',
                    'Incident Response',
                    'Compliance Requirements',
                    'Threat Modeling',
                ]
            },
            'compliance': {
                'title': 'Compliance Training',
                'duration': timedelta(hours=1.5),
                'topics': [
                    'GDPR Requirements',
                    'PCI DSS Standards',
                    'Data Privacy Laws',
                    'Audit Preparedness',
                ]
            },
        }
        
        module = training_modules.get(training_type, training_modules['basic'])
        
        return {
            'user': user.id,
            'training_type': training_type,
            'title': module['title'],
            'scheduled_date': datetime.now() + timedelta(days=7),
            'due_date': datetime.now() + timedelta(days=30),
            'duration': module['duration'],
            'topics': module['topics'],
            'status': 'scheduled',
        }
    
    def track_completion(self, user):
        """Track training completion status."""
        # Implement training completion tracking
        # This could integrate with your LMS or training platform
        pass
    
    def send_reminders(self):
        """Send training reminders."""
        # Send reminders for overdue training
        # This could be integrated with your email system
        pass
```

## Conclusion

### Security Maintenance

#### Regular Security Tasks
```bash
# Weekly security maintenance script
#!/bin/bash

echo "Starting weekly security maintenance"
echo "=================================="

# Update system packages
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Update application dependencies
echo "Updating application dependencies..."
npm update
pip install -U -r requirements.txt

# Run security scans
echo "Running security scans..."
npm audit
pip-audit
bandit -r . -ll

# Check for compromised passwords
echo "Checking for compromised passwords..."
# Implement password breach checking

# Review access logs
echo "Reviewing access logs..."
sudo grep "Failed password" /var/log/auth.log
sudo grep "Invalid user" /var/log/auth.log

# Backup verification
echo "Verifying backups..."
# Implement backup verification

echo "Weekly security maintenance completed"
```

#### Security Health Check
```python
# security/health_check.py
from datetime import datetime

class SecurityHealthCheck:
    """Comprehensive security health checking."""
    
    def run_full_health_check(self):
        """Run complete security health check."""
        checks = {
            'system_security': self.check_system_security(),
            'application_security': self.check_application_security(),
            'network_security': self.check_network_security(),
            'data_security': self.check_data_security(),
            'compliance': self.check_compliance(),
            'monitoring': self.check_monitoring(),
        }
        
        overall_status = all(check['status'] == 'healthy' for check in checks.values())
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy' if overall_status else 'unhealthy',
            'checks': checks,
            'recommendations': self.generate_recommendations(checks),
        }
    
    def check_system_security(self):
        """Check system-level security."""
        # Implement system security checks
        return {
            'status': 'healthy',
            'details': {},
            'issues': []
        }
    
    def generate_recommendations(self, checks):
        """Generate security recommendations."""
        recommendations = []
        
        for check_name, check_result in checks.items():
            if check_result['status'] != 'healthy':
                recommendations.append(f"Address issues in {check_name}")
        
        return recommendations
```

### Continuous Improvement

#### Security Metrics and Reporting
```python
# security/metrics.py
from datetime import datetime, timedelta

class SecurityMetrics:
    """Security performance metrics and reporting."""
    
    def calculate_metrics(self, period='30d'):
        """Calculate security metrics for reporting."""
        start_date = datetime.now() - self.parse_period(period)
        
        metrics = {
            'vulnerability_metrics': self.calculate_vulnerability_metrics(start_date),
            'incident_metrics': self.calculate_incident_metrics(start_date),
            'compliance_metrics': self.calculate_compliance_metrics(start_date),
            'training_metrics': self.calculate_training_metrics(start_date),
        }
        
        return metrics
    
    def calculate_vulnerability_metrics(self, start_date):
        """Calculate vulnerability-related metrics."""
        # Implement vulnerability metrics calculation
        return {
            'total_vulnerabilities': 0,
            'critical_vulnerabilities': 0,
            'mean_time_to_remediate': timedelta(days=0),
            'vulnerability_trend': 'stable',
        }
    
    def generate_security_report(self):
        """Generate comprehensive security report."""
        metrics = self.calculate_metrics()
        
        report = {
            'report_date': datetime.now().isoformat(),
            'period': '30d',
            'executive_summary': self.generate_executive_summary(metrics),
            'detailed_metrics': metrics,
            'key_findings': self.identify_key_findings(metrics),
            'action_items': self.generate_action_items(metrics),
        }
        
        return report
```

---

**WebOps Security Hardening Guide** - *Comprehensive security best practices for production deployments* 🔒

This guide provides detailed security hardening procedures covering infrastructure, application, network, and operational security. Regular review and implementation of these practices will help maintain a secure WebOps deployment.