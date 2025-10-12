# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Currently supported versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :x:                |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@webops.dev** (or your actual security contact)

You should receive a response within 48 hours. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information:

* Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
* Full paths of source file(s) related to the manifestation of the issue
* The location of the affected source code (tag/branch/commit or direct URL)
* Any special configuration required to reproduce the issue
* Step-by-step instructions to reproduce the issue
* Proof-of-concept or exploit code (if possible)
* Impact of the issue, including how an attacker might exploit it

This information will help us triage your report more quickly.

## Security Best Practices

WebOps is designed with security as a core principle. Here are the security measures in place:

### Authentication & Authorization

* **Session-based authentication** using Django's robust session framework
* **CSRF protection** on all state-changing operations
* **API token authentication** with configurable expiration
* **User isolation** - users can only access their own deployments

### Data Protection

* **Encrypted credentials** - Database passwords stored encrypted using Fernet (symmetric encryption)
* **Environment variable protection** - Sensitive env vars never logged
* **Secure secret generation** - Using Python's `secrets` module for cryptographically secure random values

### Application Security

* **Input validation** - All user inputs validated and sanitized
* **SQL injection protection** - Using Django ORM (parameterized queries)
* **XSS protection** - Django template auto-escaping enabled
* **Path traversal prevention** - File access restricted to deployment directories
* **Command injection prevention** - No shell=True in subprocess calls

### Infrastructure Security

* **Process isolation** - Each deployment runs as isolated systemd service
* **Minimal permissions** - Services run with least privilege principle
* **Port management** - Dynamic port allocation to prevent conflicts
* **File system isolation** - Deployments contained in separate directories

### Code Security

* **No eval() or exec()** - Never executing arbitrary code
* **Dependency scanning** - Regular security audits of dependencies
* **Static code analysis** - Automated security scanning in CI/CD
* **Secret scanning** - Pre-commit hooks to prevent credential commits

## Security Checklist for Deployments

When deploying WebOps in production:

- [ ] Change default `SECRET_KEY` in Django settings
- [ ] Set `DEBUG=False` in production
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Use HTTPS with valid SSL certificates (Certbot)
- [ ] Enable firewall and restrict ports (only 22, 80, 443)
- [ ] Set up regular automated backups
- [ ] Keep system packages updated
- [ ] Use strong passwords for all accounts
- [ ] Configure fail2ban for SSH protection
- [ ] Enable audit logging
- [ ] Regularly review user access
- [ ] Monitor system logs for suspicious activity

## Vulnerability Disclosure Timeline

1. **Day 0**: Vulnerability reported to security team
2. **Day 1-2**: Acknowledgment sent to reporter
3. **Day 3-7**: Investigation and patch development
4. **Day 8-14**: Testing and validation
5. **Day 15**: Security advisory published and patch released
6. **Day 30**: Full disclosure (if patch has been available for 14+ days)

We aim to:

* Acknowledge reports within 48 hours
* Provide regular updates every 7 days
* Release patches within 30 days for critical issues
* Provide workarounds if patch development takes longer

## Security Updates

Security updates are released as:

* **Critical**: Immediate release, version bump (e.g., 0.3.1)
* **High**: Release within 7 days
* **Medium**: Release within 30 days
* **Low**: Included in next regular release

Subscribe to security advisories:

* Watch this repository for releases
* Follow [@WebOpsProject](https://twitter.com/webopsproject) (example)
* Subscribe to our mailing list

## Known Security Considerations

### Self-Hosted Nature

WebOps is designed to be self-hosted, which means:

* **You are responsible** for securing the host system
* **You control** all data and credentials
* **You must** keep the system updated and patched

### GitHub Repository Access

For private repositories:

* **Use deploy keys** instead of personal access tokens when possible
* **Limit token scopes** to minimum required permissions
* **Rotate tokens** regularly
* **Revoke tokens** immediately if compromised

### Database Credentials

* Credentials are **encrypted at rest** using Fernet
* Encryption key is stored in Django settings (protect this!)
* Consider using **hardware security modules** (HSM) for production
* Regularly **rotate database passwords**

## Security Acknowledgments

We'd like to thank the following security researchers for responsibly disclosing vulnerabilities:

* (None reported yet - you could be first!)

## Contact

For security concerns, please contact:

* **Email**: security@webops.dev
* **PGP Key**: (If available)

For general questions:

* **GitHub Issues**: https://github.com/yourusername/webops/issues
* **Discussions**: https://github.com/yourusername/webops/discussions

---

Last updated: October 2025
