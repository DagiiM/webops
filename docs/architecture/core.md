# Core App Architecture

**Version**: 2.0 (Post Phase 2 Refactoring)
**Last Updated**: 2025-10-20
**Status**: Domain-Based Organization

---

## Overview

The `apps/core` application provides foundational functionality for WebOps, including authentication, security, integrations, and configuration management. After Phase 2 refactoring, the app is organized into clear domain boundaries with proper separation of concerns.

---

## Architecture Principles

### 1. Domain-Driven Design
Each domain represents a cohesive set of related functionality:
- **Auth**: User authentication, registration, password management, 2FA
- **Security**: Encryption, audit logging, access control
- **Integrations**: OAuth providers (GitHub, Google, HuggingFace)
- **Branding**: Theme and visual customization
- **Webhooks**: Event-driven HTTP notifications
- **Notifications**: Multi-channel alerting (email, webhooks)
- **Common**: Shared utilities and base models

### 2. Service Layer Pattern
Business logic is encapsulated in service classes, separated from views and models:
```python
# Service handles business logic
class TwoFactorService:
    @staticmethod
    def setup_2fa(user: User) -> Tuple[TwoFactorAuth, str, List[str]]:
        # Business logic here
        pass

# View delegates to service
def two_factor_setup(request):
    two_factor, uri, backup_codes = TwoFactorService.setup_2fa(request.user)
    return render(request, 'auth/two_factor_setup.html', {...})
```

### 3. Clean Imports
Each domain exports its public API through `__init__.py`:
```python
# ✅ Clean import
from apps.core.auth import TwoFactorAuth, TOTPService

# ❌ Avoid
from apps.core.auth.models import TwoFactorAuth
from apps.core.auth.services import TOTPService
```

---

## Directory Structure

```
apps/core/
├── auth/                      # Authentication & 2FA
│   ├── __init__.py           # Public API exports
│   ├── models.py             # TwoFactorAuth
│   ├── forms.py              # Login, Registration, 2FA forms
│   ├── services.py           # TOTPService, TwoFactorService
│   ├── views.py              # Auth views
│   ├── urls.py               # URL routing
│   └── tests.py              # 300+ LOC test suite
│
├── security/                  # Security & Audit Logging
│   ├── __init__.py
│   ├── models.py             # SecurityAuditLog
│   ├── services.py           # EncryptionService, SecurityAuditService
│   ├── middleware.py         # Security middleware
│   └── tests.py              # 250+ LOC test suite
│
├── integrations/              # OAuth Integrations
│   ├── __init__.py
│   ├── models.py             # GitHub, Google, HuggingFace connections
│   ├── forms.py              # OAuth configuration forms
│   ├── views.py              # OAuth callback views
│   ├── urls.py               # OAuth URL patterns
│   ├── services/
│   │   ├── github.py         # GitHubIntegrationService
│   │   ├── google.py         # GoogleIntegrationService
│   │   └── huggingface.py    # HuggingFaceIntegrationService
│   └── tests/
│       ├── test_github.py
│       ├── test_google.py
│       └── test_huggingface.py
│
├── branding/                  # Theme Management
│   ├── __init__.py
│   ├── models.py             # BrandingSettings
│   ├── forms.py              # BrandingSettingsForm
│   ├── services.py           # BrandingService (color, accessibility)
│   ├── views.py              # Branding views
│   ├── urls.py               # Branding URL patterns
│   └── tests.py              # 300+ LOC test suite
│
├── webhooks/                  # Webhook System
│   ├── __init__.py
│   ├── models.py             # Webhook, WebhookDelivery
│   ├── forms.py              # WebhookForm
│   ├── services.py           # WebhookService
│   ├── views.py              # Webhook management views
│   ├── urls.py               # Webhook URL patterns
│   └── tests.py
│
├── notifications/             # Notification Channels
│   ├── __init__.py
│   ├── models.py             # NotificationChannel, NotificationLog
│   ├── forms.py              # NotificationChannelForm
│   ├── services.py           # NotificationService
│   ├── views.py              # Channel management views
│   ├── urls.py               # Notification URL patterns
│   └── tests.py
│
├── common/                    # Shared Components
│   ├── __init__.py
│   ├── models.py             # BaseModel, Configuration, SystemHealthCheck
│   ├── context_processors.py # Template context
│   ├── utils/
│   │   ├── encryption.py     # Encryption utilities
│   │   ├── validators.py     # Custom validators
│   │   └── generators.py     # ID/token generators
│   └── tests.py
│
├── migrations/                # Database migrations
├── templates/                 # (Still in root for now)
└── static/                    # (Still in root for now)
```

---

## Domain Breakdown

### Auth Domain
**Purpose**: User authentication, registration, and Two-Factor Authentication

**Models**:
- `TwoFactorAuth`: TOTP-based 2FA settings

**Services**:
- `TOTPService`: Pure Python TOTP implementation (RFC 6238)
  - `generate_secret()`: Create base32-encoded secret
  - `get_totp_token()`: Generate 6-digit token
  - `verify_token()`: Validate token with time window
  - `get_provisioning_uri()`: QR code URI for authenticator apps

- `TwoFactorService`: 2FA lifecycle management
  - `setup_2fa()`: Initialize 2FA for user
  - `enable_2fa()`: Enable after verification
  - `verify_2fa()`: Verify TOTP or backup code
  - `disable_2fa()`: Disable 2FA

**Views**:
- `login_view()`: Enhanced login with 2FA support
- `register_view()`: User registration
- `two_factor_setup()`: 2FA setup with QR code
- `two_factor_verify()`: 2FA verification during login
- `two_factor_disable()`: Disable 2FA
- `password_reset_request()`: Password reset request
- `password_reset_confirm()`: Password reset confirmation
- `logout_view()`: Logout with audit logging

**Key Features**:
- Compatible with Google Authenticator, Authy, etc.
- Backup codes for account recovery
- Session management (remember me)
- Security audit logging integration
- IP address tracking

---

### Security Domain
**Purpose**: Encryption, audit logging, and security monitoring

**Models**:
- `SecurityAuditLog`: Security event logging with severity levels

**Services**:
- `EncryptionService`: Fernet symmetric encryption
  - `encrypt()`: Encrypt sensitive data
  - `decrypt()`: Decrypt sensitive data
  - Uses Django SECRET_KEY with PBKDF2 key derivation

- `SecurityAuditService`: Audit logging
  - `log_event()`: Log security events
  - `get_failed_login_attempts()`: Count failed logins
  - `is_ip_blocked()`: IP-based rate limiting

**Event Types**:
- `LOGIN_SUCCESS`, `LOGIN_FAILED`
- `LOGOUT`
- `TFA_ENABLED`, `TFA_DISABLED`, `TFA_SUCCESS`, `TFA_FAILED`
- `PASSWORD_CHANGE`
- `OAUTH_CONNECTED`, `OAUTH_DISCONNECTED`

**Key Features**:
- All sensitive operations logged
- IP address and user agent tracking
- Time-based query filters
- Severity levels (info, warning, error, critical)
- Metadata storage (JSON field)

---

### Common Domain
**Purpose**: Shared utilities and base models

**Models**:
- `BaseModel`: Abstract base with `created_at`, `updated_at`
- `Configuration`: Dynamic key-value settings storage
- `SystemHealthCheck`: System health monitoring
- `SSLCertificate`: SSL certificate management

**Utils**:
- `encryption.py`: Encryption helpers
- `validators.py`: Custom Django validators
- `generators.py`: ID and token generation

**Context Processors**:
- `branding_context()`: Inject branding settings into templates

---

## Data Flow Diagrams

### Authentication Flow (Without 2FA)
```
User → login_view()
    ├→ WebOpsLoginForm validation
    ├→ Django authenticate()
    ├→ SecurityAuditService.log_event()
    ├→ Django login()
    └→ Redirect to dashboard
```

### Authentication Flow (With 2FA)
```
User → login_view()
    ├→ WebOpsLoginForm validation
    ├→ Django authenticate()
    ├→ Check TwoFactorAuth.is_enabled
    ├→ SecurityAuditService.log_event()
    ├→ Store user_id in session
    └→ Redirect to two_factor_verify()
        ├→ TwoFactorVerifyForm validation
        ├→ TwoFactorService.verify_2fa()
        ├→ SecurityAuditService.log_event()
        ├→ Django login()
        └→ Redirect to dashboard
```

### 2FA Setup Flow
```
User → two_factor_setup()
    ├→ TwoFactorService.setup_2fa()
    │   ├→ TOTPService.generate_secret()
    │   ├→ Generate backup codes
    │   └→ Create TwoFactorAuth (disabled)
    ├→ Display QR code
    ├→ User scans with authenticator app
    └→ User submits verification code
        ├→ TwoFactorService.enable_2fa()
        ├→ TOTPService.verify_token()
        ├→ Enable 2FA
        ├→ SecurityAuditService.log_event()
        └→ Show backup codes
```

### Security Audit Logging Flow
```
Any Security Event
    ├→ SecurityAuditService.log_event()
    │   ├→ Extract IP address (X-Forwarded-For aware)
    │   ├→ Extract user agent
    │   ├→ Get authenticated user (if any)
    │   └→ Create SecurityAuditLog entry
    └→ Log persisted to database
```

---

## Service Layer Architecture

### Service Pattern
All business logic is encapsulated in service classes:

```python
class MyService:
    """Service for my domain."""

    @staticmethod
    def perform_action(user: User, data: dict) -> Result:
        """
        Perform business logic.

        Args:
            user: User performing action
            data: Action data

        Returns:
            Result object

        Raises:
            ValidationError: If data is invalid
        """
        # 1. Validate input
        if not data:
            raise ValidationError("Data required")

        # 2. Perform business logic
        result = do_something(user, data)

        # 3. Log action (if security-relevant)
        SecurityAuditService.log_event(...)

        # 4. Return result
        return result
```

### Service Benefits
- **Testable**: Easy to unit test without HTTP
- **Reusable**: Services can be called from views, management commands, Celery tasks
- **Maintainable**: Business logic separate from presentation
- **Documented**: Services have clear APIs with type hints

---

## Import Patterns

### Recommended Imports
```python
# ✅ Domain-level imports (preferred)
from apps.core.auth import TwoFactorAuth, TOTPService, TwoFactorService
from apps.core.security import SecurityAuditLog, EncryptionService
from apps.core.common import BaseModel, Configuration

# ✅ Specific imports (when needed)
from apps.core.auth.models import TwoFactorAuth
from apps.core.auth.services import TOTPService
```

### Avoid
```python
# ❌ Wildcard imports
from apps.core.auth import *

# ❌ Circular imports
# Don't import views in models, or models in services if avoidable
```

### Backward Compatibility
Old import paths still work during transition:
```python
# Still works, but deprecated
from apps.core.models import TwoFactorAuth

# Issues DeprecationWarning
```

---

## Testing Architecture

### Test Organization
Each domain has its own test file:
```
apps/core/
├── auth/tests.py              # Auth domain tests
├── security/tests.py          # Security domain tests
├── branding/tests.py          # Branding tests
├── integrations/tests/        # Integration tests (by provider)
├── webhooks/tests.py          # Webhook tests
├── notifications/tests.py     # Notification tests
└── common/tests.py            # Common utility tests
```

### Test Coverage Goals
- **Overall**: 70%+ coverage
- **Critical paths** (auth, security): 80%+ coverage
- **Services**: 90%+ coverage (easiest to test)
- **Views**: 60%+ coverage (harder to test)

### Test Types
1. **Unit Tests**: Test individual functions/methods
2. **Integration Tests**: Test multiple components together
3. **End-to-End Tests**: Test complete user flows

---

## Migration Strategy

### Phase 2 → Production
1. **Complete domain extraction** (branding, integrations, webhooks, notifications)
2. **Remove old models** from root `models.py`
3. **Update all imports** across codebase
4. **Run all tests** and fix issues
5. **Deploy to staging**
6. **Run integration tests**
7. **Deploy to production**

### Rollback Plan
If issues arise:
1. Revert to old import paths
2. Keep old `models.py` as fallback
3. Fix issues incrementally
4. Retry deployment

---

## Performance Considerations

### Database
- Use `select_related()` for foreign keys
- Use `prefetch_related()` for many-to-many
- Add indexes to frequently queried fields

### Caching
- Cache branding settings (changes infrequently)
- Cache OAuth tokens (with expiry)
- Use Django's cache framework

### Security
- Use constant-time comparison for tokens
- Rate limit sensitive endpoints
- Use database transactions for critical operations

---

## Security Best Practices

### Authentication
- Always use Django's `authenticate()` function
- Never store passwords in plain text
- Use strong password validators
- Implement rate limiting on login

### 2FA
- Use time-based window for token validation
- Invalidate backup codes after use
- Log all 2FA events
- Require 2FA for admin users

### Audit Logging
- Log all security-relevant events
- Capture IP address and user agent
- Store metadata for forensics
- Implement log retention policy

### Encryption
- Use Django SECRET_KEY for key derivation
- Rotate encryption keys periodically
- Never log decrypted values
- Use constant-time comparison for encrypted values

---

## Future Enhancements

### Short-term
- Complete Phase 2 domain extraction
- Achieve 70%+ test coverage
- Add API documentation (Swagger/OpenAPI)
- Implement BaseService pattern

### Medium-term
- Add WebAuthn/FIDO2 support
- Implement session management dashboard
- Add security headers middleware
- Create admin dashboard for audit logs

### Long-term
- Multi-tenancy support
- Advanced role-based access control (RBAC)
- Compliance reporting (GDPR, SOC2)
- Real-time security monitoring

---

## Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **TOTP RFC 6238**: https://tools.ietf.org/html/rfc6238
- **WCAG Guidelines**: https://www.w3.org/WAI/WCAG21/quickref/
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/

---

## Glossary

- **2FA**: Two-Factor Authentication
- **TOTP**: Time-based One-Time Password
- **HSL**: Hue, Saturation, Lightness (color model)
- **WCAG**: Web Content Accessibility Guidelines
- **RBAC**: Role-Based Access Control
- **OAuth**: Open Authorization protocol
- **Fernet**: Symmetric encryption specification
- **PBKDF2**: Password-Based Key Derivation Function 2

---

**Maintained by**: WebOps Core Team
**Questions**: See CLAUDE.md or open an issue
