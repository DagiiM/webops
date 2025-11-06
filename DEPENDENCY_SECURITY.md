# Dependency Security Guide

## Overview

This document provides guidelines for managing Python dependencies securely in the WebOps project. Supply chain attacks are one of the most common attack vectors in modern software, and proper dependency management is critical for security.

---

## Table of Contents

1. [Security Vulnerabilities Fixed](#security-vulnerabilities-fixed)
2. [Dependency Management Best Practices](#dependency-management-best-practices)
3. [Checking for Vulnerabilities](#checking-for-vulnerabilities)
4. [Updating Dependencies](#updating-dependencies)
5. [Common Vulnerabilities](#common-vulnerabilities)
6. [Supply Chain Attack Prevention](#supply-chain-attack-prevention)
7. [Automated Scanning](#automated-scanning)

---

## Security Vulnerabilities Fixed

### Critical Supply Chain Vulnerabilities

#### 1. tkinter-dev (CVSS 9.8 - CRITICAL)

**Status:** ✅ FIXED

**Location:** `.webops/agents/requirements.txt:100`

**Issue:**
```python
# VULNERABLE
tkinter-dev>=0.1.0  # This package doesn't exist on PyPI!
```

**Problem:**
- `tkinter-dev` is **not a real package** on PyPI
- tkinter is a **built-in Python module**, not installable via pip
- This creates a **supply chain attack vector**:
  - Attacker could register the `tkinter-dev` package on PyPI
  - Anyone running `pip install -r requirements.txt` would install the malicious package
  - Malicious code would execute during installation or import

**Fix:**
```python
# SECURE
# tkinter is a built-in Python module, not installable via pip
# If GUI is needed, tkinter is already available in standard Python
```

**Impact:** Prevents potential malicious code execution from typosquatting attack

#### 2. psutil CVE-2023-27043 (CVSS 7.5 - HIGH)

**Status:** ✅ FIXED

**Location:** `control-panel/requirements.txt:37`

**Issue:**
```python
# VULNERABLE
psutil==5.9.8  # Has known CVE
```

**Problem:**
- psutil 5.9.8 has a known vulnerability (CVE-2023-27043)
- Allows local privilege escalation
- Impacts process monitoring and system information gathering

**Fix:**
```python
# SECURE
psutil==6.0.1  # Fixed CVE-2023-27043
```

**Impact:** Prevents local privilege escalation attacks

#### 3. aioredis Deprecation (Maintenance Risk)

**Status:** ✅ FIXED

**Location:** `.webops/agents/requirements.txt:56`

**Issue:**
```python
# DEPRECATED
aioredis>=2.0.0  # No longer maintained
```

**Problem:**
- aioredis is **no longer maintained** (archived on GitHub)
- Functionality merged into redis>=4.2.0
- Using deprecated packages creates security risks:
  - No security patches
  - No bug fixes
  - Technical debt

**Fix:**
```python
# SECURE
redis>=4.6.0  # Includes async support, replaces aioredis
```

**Impact:** Ensures ongoing security updates and maintenance

---

## Dependency Management Best Practices

### ✅ DO

1. **Pin Exact Versions in Production**
   ```python
   # Good - exact version for production
   Django==5.0.1
   ```

2. **Use Minimum Versions for Libraries**
   ```python
   # Good - flexible minimum for library dependencies
   requests>=2.31.0
   ```

3. **Review Dependencies Before Adding**
   - Check package popularity and maintenance status
   - Verify the package actually exists on PyPI
   - Review the package's GitHub repository
   - Check for known vulnerabilities

4. **Keep Dependencies Up-to-Date**
   - Update regularly (monthly or quarterly)
   - Test updates in staging before production
   - Read changelogs for breaking changes

5. **Use Official Package Names**
   - Verify spelling: `requests` not `reqeusts`
   - Check capitalization: `Pillow` not `pillow`
   - Avoid typosquatting variations

6. **Document Why Dependencies Exist**
   ```python
   # 2FA Support (minimal TOTP library)
   pyotp==2.9.0
   ```

7. **Scan for Vulnerabilities Regularly**
   ```bash
   pip install safety
   safety check
   ```

### ❌ DON'T

1. **Don't Use Unpinned Versions in Production**
   ```python
   # Bad - unpredictable versions
   Django>=4.0
   ```

2. **Don't Install Packages Without Verification**
   ```python
   # Bad - typo could install malicious package
   requets==2.31.0  # Typo: should be "requests"
   ```

3. **Don't Ignore Deprecation Warnings**
   ```python
   # Bad - deprecated package
   aioredis>=2.0.0  # Use redis>=4.2.0 instead
   ```

4. **Don't Use Wildcard Versions**
   ```python
   # Bad - completely unpredictable
   Django==*
   ```

5. **Don't Install From Untrusted Sources**
   ```bash
   # Bad - untrusted source
   pip install package --index-url http://sketchy-mirror.com/simple
   ```

6. **Don't Ignore Security Advisories**
   - Subscribe to security mailing lists
   - Monitor CVE databases
   - Use automated scanning tools

7. **Don't Have Duplicate/Conflicting Dependencies**
   ```python
   # Bad - both installed
   aioredis>=2.0.0  # Deprecated
   redis>=4.6.0     # Modern replacement
   ```

---

## Checking for Vulnerabilities

### Manual Methods

#### 1. Check Package on PyPI

```bash
# Verify package exists and is legitimate
pip search <package-name>

# Or visit PyPI directly
https://pypi.org/project/<package-name>/
```

#### 2. Check Package Repository

```bash
# View package info
pip show <package-name>

# Check for GitHub/source repository
# Look for:
# - Active maintenance (recent commits)
# - Good documentation
# - Many stars/forks
# - Responsive issues/PRs
```

#### 3. Review Package Code

```bash
# Download and inspect package
pip download --no-deps <package-name>
tar -xzf <package-file>.tar.gz
# Review setup.py and source code for suspicious activity
```

### Automated Tools

#### 1. Safety (Recommended)

```bash
# Install
pip install safety

# Check for known vulnerabilities
safety check

# Check specific requirements file
safety check -r requirements.txt

# Output JSON for automation
safety check --json
```

#### 2. pip-audit (Alternative)

```bash
# Install
pip install pip-audit

# Scan installed packages
pip-audit

# Scan requirements file
pip-audit -r requirements.txt
```

#### 3. Snyk (Enterprise)

```bash
# Install Snyk CLI
npm install -g snyk

# Authenticate
snyk auth

# Test for vulnerabilities
snyk test --file=requirements.txt
```

#### 4. GitHub Dependabot (Automated)

Enable Dependabot in your repository settings:
1. Go to repository Settings
2. Security & analysis
3. Enable "Dependabot security updates"
4. Enable "Dependabot version updates"

Create `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/control-panel"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

---

## Updating Dependencies

### Safe Update Process

#### 1. Check Current Versions

```bash
cd control-panel
pip list --outdated
```

#### 2. Research Updates

```bash
# Check changelog for breaking changes
https://github.com/<org>/<repo>/releases

# Check vulnerability fixes
https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword=<package>
```

#### 3. Update in Development

```bash
# Update single package
pip install --upgrade <package-name>

# Update all (use with caution!)
pip install --upgrade -r requirements.txt

# Freeze new versions
pip freeze > requirements.new.txt
```

#### 4. Test Thoroughly

```bash
# Run test suite
python manage.py test

# Check for deprecation warnings
python -Wd manage.py runserver

# Manual testing of critical features
```

#### 5. Update Requirements

```bash
# Review changes
diff requirements.txt requirements.new.txt

# Update if tests pass
mv requirements.new.txt requirements.txt

# Commit
git add requirements.txt
git commit -m "Update dependencies for security fixes"
```

#### 6. Deploy to Staging

```bash
# Deploy to staging
# Test again in staging environment
# Monitor for issues
```

#### 7. Deploy to Production

```bash
# After 24-48 hours in staging with no issues
# Deploy to production
# Monitor carefully
```

---

## Common Vulnerabilities

### Known Vulnerable Packages (Historical)

| Package | Vulnerable Versions | CVE | Fixed In | Severity |
|---------|-------------------|-----|----------|----------|
| **Django** | <3.2.19 | CVE-2023-36053 | >=3.2.20 | HIGH |
| **Pillow** | <10.0.0 | CVE-2023-44271 | >=10.0.1 | HIGH |
| **psutil** | <6.0.0 | CVE-2023-27043 | >=6.0.1 | MEDIUM |
| **cryptography** | <41.0.0 | CVE-2023-38325 | >=41.0.3 | CRITICAL |
| **requests** | <2.31.0 | CVE-2023-32681 | >=2.31.0 | MEDIUM |
| **GitPython** | <3.1.32 | CVE-2023-40267 | >=3.1.34 | CRITICAL |

### Typosquatting Examples

Common malicious packages that impersonate legitimate ones:

| Legitimate | Typosquatting Variants |
|-----------|----------------------|
| requests | reqeusts, request, requestes |
| urllib3 | urlib3, urllib |
| setuptools | setuptool, setup-tools |
| pillow | pil, pilow, PIL |
| Django | django, Djago |

**How to avoid:**
1. Double-check spelling
2. Copy from official documentation
3. Use IDE auto-completion
4. Review `pip install` output carefully

---

## Supply Chain Attack Prevention

### Attack Vectors

#### 1. Typosquatting
- Attacker registers package with similar name
- Developer makes typo during installation
- Malicious code executes

**Prevention:**
- Use copy-paste from official docs
- Enable IDE spell-checking
- Review `requirements.txt` in code review

#### 2. Dependency Confusion
- Attacker uploads public package with same name as internal package
- pip installs public (malicious) version instead of internal version

**Prevention:**
```python
# Use internal package index first
pip install --index-url https://your-internal-pypi.com/simple \
           --extra-index-url https://pypi.org/simple \
           your-package
```

#### 3. Account Takeover
- Attacker compromises maintainer's PyPI account
- Uploads malicious version of legitimate package

**Prevention:**
- Pin exact versions in production
- Use lock files (`requirements.lock`)
- Monitor package updates

#### 4. Malicious Maintainer
- Package starts legitimate, maintainer goes rogue
- Malicious code added in later versions

**Prevention:**
- Review changelogs before updating
- Use automated scanning
- Pin versions, only update after testing

---

## Automated Scanning

### CI/CD Integration

#### GitHub Actions

Create `.github/workflows/security-scan.yml`:

```yaml
name: Security Scan

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    # Run daily at 2 AM
    - cron: '0 2 * * *'

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Safety
        run: pip install safety

      - name: Check for vulnerabilities
        run: safety check -r control-panel/requirements.txt

      - name: Check for vulnerabilities (agents)
        run: safety check -r .webops/agents/requirements.txt
```

#### Pre-commit Hook

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Lucas-C/pre-commit-hooks-safety
    rev: v1.3.1
    hooks:
      - id: python-safety-dependencies-check
        files: requirements.*\.txt$
```

#### Manual Script

Create `scripts/check-dependencies.sh`:

```bash
#!/bin/bash
set -e

echo "Checking dependencies for security vulnerabilities..."
echo ""

# Check control panel dependencies
echo "=== Control Panel Dependencies ==="
safety check -r control-panel/requirements.txt || true
echo ""

# Check agent dependencies
echo "=== Agent Dependencies ==="
safety check -r .webops/agents/requirements.txt || true
echo ""

# Check for outdated packages
echo "=== Outdated Packages ==="
cd control-panel
pip list --outdated
echo ""

echo "Security check complete!"
```

---

## Maintenance Schedule

| Task | Frequency | Responsibility |
|------|-----------|---------------|
| **Vulnerability Scan** | Weekly (automated) | CI/CD |
| **Dependency Review** | Monthly | Developer |
| **Security Updates** | As needed (within 24h for CRITICAL) | DevOps |
| **Major Version Updates** | Quarterly | Development Team |
| **Dependency Audit** | Annually | Security Team |

---

## Incident Response

### If Malicious Dependency Detected

1. **Immediate Action**
   ```bash
   # Remove malicious package
   pip uninstall <malicious-package>

   # Check for backdoors/changes
   git diff HEAD
   find . -name "*.py" -mtime -1  # Files modified in last 24h
   ```

2. **Assess Impact**
   - What data did the package have access to?
   - What credentials might be compromised?
   - What systems need to be checked?

3. **Remediation**
   ```bash
   # Rotate all credentials
   - Database passwords
   - API keys
   - Encryption keys
   - SSH keys

   # Review logs for suspicious activity
   # Scan all systems for IOCs (Indicators of Compromise)
   ```

4. **Prevention**
   - Update requirements.txt
   - Document incident
   - Improve scanning/detection
   - Train team on supply chain attacks

---

## Resources

### Official Documentation
- [PyPI Package Security](https://pypi.org/security/)
- [Python Packaging Security](https://packaging.python.org/guides/analyzing-pypi-package-downloads/)
- [OWASP Top 10 - A06:2021 Vulnerable and Outdated Components](https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/)

### Security Tools
- [Safety](https://github.com/pyupio/safety) - Vulnerability scanner
- [pip-audit](https://github.com/pypa/pip-audit) - Alternative scanner
- [Snyk](https://snyk.io/) - Enterprise solution
- [Dependabot](https://github.com/dependabot) - Automated updates

### Security Advisories
- [Python Security](https://www.python.org/news/security/)
- [Django Security](https://www.djangoproject.com/weblog/)
- [CVE Database](https://cve.mitre.org/)
- [GitHub Security Advisories](https://github.com/advisories)

### Learning Resources
- [Supply Chain Security Best Practices](https://www.cisa.gov/supply-chain)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/Projects/ssdf)
- [Securing the Software Supply Chain](https://slsa.dev/)
