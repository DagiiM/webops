# WebOps Security Fix Implementation Plan
## Structured Approach - Phase 1: Critical Fixes

**Date:** November 6, 2025
**Status:** IN PROGRESS
**Approach:** Test-Driven Security Fixes

---

## Project Structure

```
control-panel/
├── apps/
│   └── core/
│       └── security/
│           ├── __init__.py
│           ├── decorators.py          # Security decorators
│           ├── middleware.py          # Security middleware
│           ├── validators.py          # Input validators
│           ├── encryption.py          # Encryption utilities
│           └── tests/
│               ├── test_ownership.py  # IDOR tests
│               ├── test_encryption.py # Encryption tests
│               └── test_validators.py # Validation tests
```

---

## Phase 1: Critical Security Fixes (P0)

### Module 1: Authorization & Access Control (IDOR Fixes)
**Target Score:** 45/100 → 95/100
**Status:** 40% Complete

#### 1.1 ✅ COMPLETED: Deployment Views
- [x] Fix deployment_list() - Filter by user
- [x] Fix deployment_detail() - Verify ownership
- [x] Test: Users can only see their deployments
- [x] Commit: a501c29

#### 1.2 ✅ COMPLETED: Database Views
- [x] Fix database_list() - Filter by user
- [x] Fix database_detail() - Verify ownership
- [x] Test: Users can only access their databases
- [x] Commit: a501c29

#### 1.3 TODO: Services Views
- [ ] Audit all service views
- [ ] Add ownership filters
- [ ] Add ownership verification
- [ ] Write security tests

#### 1.4 TODO: API Endpoints
- [ ] Audit all API endpoints
- [ ] Fix /api/deployments/
- [ ] Fix /api/databases/
- [ ] Add authentication checks
- [ ] Write API security tests

#### 1.5 TODO: Create Reusable Security Utilities
- [ ] Create @require_resource_ownership decorator
- [ ] Create ResourceOwnershipMiddleware
- [ ] Create get_user_resources() helper
- [ ] Document usage patterns

**Deliverables:**
- Reusable security decorators
- Middleware for automatic ownership checks
- Comprehensive test suite
- Security documentation

---

### Module 2: Encryption & Key Management
**Target Score:** 60/100 → 95/100
**Status:** 0% Complete

#### 2.1 TODO: Key Rotation Infrastructure
- [ ] Create key rotation script
- [ ] Generate new encryption keys
- [ ] Update .env.example (remove hardcoded key)
- [ ] Document key rotation process

#### 2.2 TODO: Encrypt 2FA Secrets
- [ ] Audit TwoFactorAuth model
- [ ] Create migration to encrypt existing secrets
- [ ] Update model save() method
- [ ] Test encryption/decryption
- [ ] Verify TOTP still works

#### 2.3 TODO: Encrypt Webhook Secrets
- [ ] Audit Webhook model
- [ ] Create migration to encrypt existing secrets
- [ ] Update model save() method
- [ ] Test webhook verification
- [ ] Verify GitHub webhooks work

#### 2.4 TODO: Separate Keys by Purpose
- [ ] Create ENCRYPTION_KEY_AUTH
- [ ] Create ENCRYPTION_KEY_DATA
- [ ] Create ENCRYPTION_KEY_TOKENS
- [ ] Update encryption utilities
- [ ] Test all encryption points

**Deliverables:**
- Encrypted authentication secrets
- Key rotation mechanism
- Separate encryption keys
- Migration scripts
- Encryption test suite

---

### Module 3: Dependency Security
**Target Score:** 55/100 → 95/100
**Status:** 0% Complete

#### 3.1 TODO: Remove Malicious Package
- [ ] Remove tkinter-dev from requirements.txt
- [ ] Verify no code imports it
- [ ] Document why removed
- [ ] Update installation guide

#### 3.2 TODO: Update Vulnerable Dependencies
- [ ] Update psutil to 6.0.1
- [ ] Remove deprecated aioredis
- [ ] Update all packages to latest
- [ ] Run pip-audit
- [ ] Test all functionality

#### 3.3 TODO: Pin All Dependencies
- [ ] Generate requirements-lock.txt
- [ ] Pin exact versions with ==
- [ ] Document pinning policy
- [ ] Add to CI/CD

#### 3.4 TODO: Implement Dependency Scanning
- [ ] Add pip-audit to CI/CD
- [ ] Add bandit SAST scanning
- [ ] Create security.yml workflow
- [ ] Configure alerts

**Deliverables:**
- Clean, pinned dependencies
- Automated security scanning
- CI/CD security checks
- Dependency update policy

---

### Module 4: Command Injection Prevention
**Target Score:** CRITICAL → SECURE
**Status:** 0% Complete

#### 4.1 TODO: Remove shell=True Usage
- [ ] Audit all subprocess calls
- [ ] Convert to list-based execution
- [ ] Implement command whitelisting
- [ ] Test deployment operations

#### 4.2 TODO: Command Validation
- [ ] Create CommandValidator class
- [ ] Whitelist allowed commands
- [ ] Validate arguments
- [ ] Test with malicious input

#### 4.3 TODO: Sandboxed Execution
- [ ] Implement subprocess sandboxing
- [ ] Clear environment variables
- [ ] Run as unprivileged user
- [ ] Test isolation

**Deliverables:**
- No shell=True in codebase
- Command whitelist validator
- Sandboxed execution utilities
- Command injection tests

---

### Module 5: Default Credentials & Configuration
**Target Score:** CRITICAL → SECURE
**Status:** 0% Complete

#### 5.1 TODO: Remove Hardcoded Passwords
- [ ] Fix quickstart.sh admin password
- [ ] Generate random passwords
- [ ] Store securely in .secrets/
- [ ] Test setup process

#### 5.2 TODO: Fix Redis Configuration
- [ ] Add password requirement
- [ ] Use rediss:// (TLS)
- [ ] Update .env.example
- [ ] Test Redis connection

#### 5.3 TODO: Fix ALLOWED_HOSTS
- [ ] Never use wildcard
- [ ] Validate domains
- [ ] Update deployment logic
- [ ] Test host header validation

**Deliverables:**
- No default credentials
- Secure configuration defaults
- Password generation utilities
- Configuration validation

---

## Implementation Strategy

### Step 1: Create Security Infrastructure (Today)
```bash
# Create security module structure
mkdir -p control-panel/apps/core/security/tests/
touch control-panel/apps/core/security/{__init__.py,decorators.py,middleware.py,validators.py,encryption.py}
touch control-panel/apps/core/security/tests/{__init__.py,test_ownership.py,test_encryption.py}
```

### Step 2: Implement Reusable Components (Today)
- Create ownership verification decorator
- Create encryption utilities
- Create validation helpers
- Write unit tests

### Step 3: Apply Fixes Systematically (Today-Tomorrow)
- Fix one module at a time
- Test each fix
- Commit incrementally
- Document changes

### Step 4: Verification (Tomorrow)
- Run full test suite
- Manual penetration testing
- Security scan with bandit
- Dependency audit with pip-audit

---

## Testing Strategy

### Unit Tests
```python
# test_ownership.py
class OwnershipTestCase(TestCase):
    def test_user_cannot_access_other_deployment(self):
        # Verify IDOR protection
        pass

    def test_user_can_access_own_deployment(self):
        # Verify legitimate access
        pass
```

### Integration Tests
```python
# test_api_security.py
class APISecurityTestCase(TestCase):
    def test_api_requires_authentication(self):
        # Verify auth requirement
        pass

    def test_api_enforces_ownership(self):
        # Verify IDOR protection
        pass
```

### Security Tests
```python
# test_command_injection.py
class CommandInjectionTestCase(TestCase):
    def test_malicious_command_blocked(self):
        # Test with "; rm -rf /"
        pass
```

---

## Success Criteria

### Module 1: Authorization ✓ when:
- [ ] No IDOR vulnerabilities (verified)
- [ ] All resources filtered by user
- [ ] Test coverage > 90%
- [ ] Security scan passes

### Module 2: Encryption ✓ when:
- [ ] All secrets encrypted
- [ ] Key rotation tested
- [ ] No hardcoded keys
- [ ] Test coverage > 90%

### Module 3: Dependencies ✓ when:
- [ ] pip-audit shows no HIGH/CRITICAL
- [ ] All deps pinned
- [ ] CI/CD scanning active
- [ ] Documentation complete

### Module 4: Command Injection ✓ when:
- [ ] No shell=True in codebase
- [ ] Command whitelist enforced
- [ ] Penetration test passes
- [ ] Test coverage > 90%

### Module 5: Configuration ✓ when:
- [ ] No default passwords
- [ ] All config validated
- [ ] Setup wizard tested
- [ ] Documentation complete

---

## Progress Tracking

### Daily Progress (Nov 6, 2025)
- [x] Created TODO.md roadmap
- [x] Completed Palantir-level audit
- [x] Fixed deployment IDOR (40% Module 1)
- [x] Fixed database IDOR (40% Module 1)
- [ ] Create security infrastructure
- [ ] Implement ownership decorator
- [ ] Fix services IDOR
- [ ] Fix API IDOR

### Week 1 Goals
- [ ] Complete Module 1 (Authorization) - 100%
- [ ] Complete Module 2 (Encryption) - 100%
- [ ] Complete Module 3 (Dependencies) - 100%
- [ ] Start Module 4 (Command Injection) - 50%

---

## Documentation Standards

### Code Comments
```python
# SECURITY FIX: IDOR vulnerability
# CVE: N/A (internal finding)
# Severity: CRITICAL (CVSS 8.6)
# Date: 2025-11-06
# Description: Added ownership verification to prevent unauthorized access
# Before: ApplicationDeployment.objects.all()
# After: ApplicationDeployment.objects.filter(deployed_by=request.user)
```

### Commit Messages
```
Fix CRITICAL IDOR in [component]

Security fix for Insecure Direct Object Reference:
- Component: [name]
- Severity: CRITICAL
- CVSS: 8.6

Changes:
- [specific change 1]
- [specific change 2]

Impact:
- [impact description]

Testing:
- [test description]

Addresses: TODO.md Phase 1.1
```

---

## Next Steps (Immediate)

1. **Create security module structure** (5 min)
2. **Implement ownership decorator** (15 min)
3. **Create security tests** (20 min)
4. **Fix services IDOR** (15 min)
5. **Fix API IDOR** (20 min)
6. **Test and commit** (10 min)

**Total Time:** ~85 minutes to complete Module 1

---

## Risk Management

### Risks
1. **Breaking existing functionality** - Mitigate with tests
2. **Performance degradation** - Mitigate with query optimization
3. **Incomplete fixes** - Mitigate with security scan
4. **Deployment issues** - Mitigate with staging environment

### Rollback Plan
- Keep detailed commit history
- Tag working versions
- Document all changes
- Test rollback procedure

---

**Status:** Ready to begin structured implementation
**Next Action:** Create security module structure
**Timeline:** Complete Phase 1 in 2 days
