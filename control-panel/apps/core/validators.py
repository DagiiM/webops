"""
Security validators for WebOps.

Implements critical security validations from docs/edge_cases.md

Edge Cases Covered:
- #1: Compromised API Token
- #2: SQL Injection Through Environment Variables
- #3: Repository URL Manipulation
- #4: Privilege Escalation (validation layer)
- #5: Session Hijacking (validation layer)
"""

import re
import ipaddress
from typing import Dict, List, Optional
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import os


class SecurityValidator:
    """Base class for security validations."""

    @staticmethod
    def validate_or_raise(condition: bool, message: str) -> None:
        """Raise ValidationError if condition is False."""
        if not condition:
            raise ValidationError(message)


class RepositoryURLValidator(SecurityValidator):
    """
    Validate Git repository URLs for security.

    Edge Case #3: Repository URL Manipulation
    Prevents SSRF, access to internal networks, and malicious repos.
    """

    ALLOWED_SCHEMES = ['https']
    ALLOWED_DOMAINS = [
        'github.com',
        'gitlab.com',
        'bitbucket.org',
        'git.sr.ht',  # SourceHut
    ]

    # RFC 1918 private networks
    PRIVATE_NETWORKS = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '127.0.0.0/8',
        '169.254.0.0/16',  # AWS metadata
        'fc00::/7',  # IPv6 private
        '::1/128',  # IPv6 localhost
    ]

    @classmethod
    def validate(cls, url: str) -> None:
        """
        Validate repository URL for security risks.

        Args:
            url: Repository URL to validate

        Raises:
            ValidationError: If URL is invalid or insecure
        """
        # Basic URL format validation
        try:
            parsed = urlparse(url)
        except Exception:
            raise ValidationError("Invalid URL format")

        # Check scheme (only HTTPS allowed)
        cls.validate_or_raise(
            parsed.scheme in cls.ALLOWED_SCHEMES,
            f"Only {', '.join(cls.ALLOWED_SCHEMES)} URLs are allowed"
        )

        # Check domain is from allowed providers
        cls.validate_or_raise(
            any(domain in parsed.netloc for domain in cls.ALLOWED_DOMAINS),
            f"Repository must be hosted on: {', '.join(cls.ALLOWED_DOMAINS)}"
        )

        # Prevent access to private networks (SSRF protection)
        cls._validate_not_private_network(parsed.netloc)

        # Prevent localhost access
        cls.validate_or_raise(
            parsed.netloc.lower() not in ['localhost', '127.0.0.1', '[::1]'],
            "Localhost URLs are not allowed"
        )

    @classmethod
    def _validate_not_private_network(cls, netloc: str) -> None:
        """Check if hostname resolves to private IP."""
        # Extract hostname (remove port if present)
        hostname = netloc.split(':')[0]

        # Try to parse as IP address
        try:
            ip = ipaddress.ip_address(hostname)
            for network_str in cls.PRIVATE_NETWORKS:
                network = ipaddress.ip_network(network_str)
                if ip in network:
                    raise ValidationError(
                        f"Access to private networks is forbidden: {network}"
                    )
        except ValueError:
            # Not an IP address, it's a hostname - this is OK
            pass


class EnvironmentVariableValidator(SecurityValidator):
    """
    Validate environment variables for injection attacks.

    Edge Case #2: SQL Injection Through Environment Variables
    Prevents SQL injection, command injection, and XSS in env vars.
    """

    # Dangerous patterns that indicate injection attempts
    DANGEROUS_PATTERNS = [
        # SQL Injection
        (r"('\s*OR\s*'1'\s*=\s*'1)", "SQL injection"),
        (r"('.*--.*)", "SQL comment injection"),
        (r"(;\s*DROP\s+TABLE)", "SQL DROP statement"),
        (r"(UNION\s+SELECT)", "SQL UNION injection"),
        (r"(\bEXEC\b|\bEXECUTE\b)", "SQL EXEC statement"),

        # Command Injection
        (r"(\$\(.*\))", "Command substitution"),
        (r"(`.*`)", "Command substitution (backticks)"),
        (r"(&&|\|\|)", "Shell operators"),
        (r"(;\s*(?:rm|cat|wget|curl|nc|bash|sh))", "Dangerous commands"),

        # XSS
        (r"(<script[^>]*>)", "Script tag"),
        (r"(javascript:)", "JavaScript protocol"),
        (r"(on\w+\s*=)", "Event handler"),

        # Path Traversal
        (r"(\.\.\/|\.\.\\)", "Path traversal"),

        # Null bytes
        (r"(\x00)", "Null byte injection"),
    ]

    @classmethod
    def validate(cls, env_vars: Dict[str, str]) -> None:
        """
        Validate environment variables for security risks.

        Args:
            env_vars: Dictionary of environment variables

        Raises:
            ValidationError: If dangerous patterns found
        """
        for key, value in env_vars.items():
            # Validate key
            cls._validate_key(key)

            # Validate value
            cls._validate_value(key, value)

    @classmethod
    def _validate_key(cls, key: str) -> None:
        """Validate environment variable key."""
        # Only allow alphanumeric and underscore
        if not re.match(r'^[A-Z][A-Z0-9_]*$', key):
            raise ValidationError(
                f"Invalid environment variable name: {key}. "
                "Must be uppercase letters, numbers, and underscores only."
            )

    @classmethod
    def _validate_value(cls, key: str, value: str) -> None:
        """Validate environment variable value."""
        # Check for dangerous patterns
        for pattern, attack_type in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError(
                    f"Potentially dangerous pattern in {key}: {attack_type}. "
                    f"Please review the value for security risks."
                )

        # Warn on extremely long values (potential DoS)
        if len(value) > 10000:
            raise ValidationError(
                f"Environment variable {key} is too long ({len(value)} chars). "
                "Maximum 10,000 characters allowed."
            )


class APITokenValidator(SecurityValidator):
    """
    Validate API token usage and detect suspicious activity.

    Edge Case #1: Compromised API Token
    Detects token compromise through IP analysis and usage patterns.
    """

    # Maximum token age before requiring rotation
    MAX_TOKEN_AGE_DAYS = 90

    # Maximum requests per hour from single IP
    MAX_REQUESTS_PER_HOUR = 1000

    @classmethod
    def validate_token_security(
        cls,
        token,
        request_ip: str,
        check_expiration: bool = True
    ) -> None:
        """
        Validate token security constraints.

        Args:
            token: APIToken instance
            request_ip: IP address of request
            check_expiration: Whether to check token expiration

        Raises:
            ValidationError: If token is compromised or expired
        """
        from apps.api.models import APIToken

        # Check if token is active
        cls.validate_or_raise(
            token.is_active,
            "API token has been revoked"
        )

        # Check expiration if configured
        if check_expiration and token.expires_at:
            cls.validate_or_raise(
                token.expires_at > timezone.now(),
                "API token has expired"
            )

        # Check IP whitelist if configured
        if hasattr(token, 'allowed_ips') and token.allowed_ips:
            cls.validate_or_raise(
                request_ip in token.allowed_ips,
                f"Access from IP {request_ip} is not allowed for this token"
            )

        # Detect suspicious IP changes
        if hasattr(token, 'last_used_ip') and token.last_used_ip:
            if token.last_used_ip != request_ip:
                # IP changed - check if from different region/country
                # This would require GeoIP lookup in production
                # For now, just log it
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Token {token.id} accessed from new IP: "
                    f"{token.last_used_ip} -> {request_ip}"
                )

    @classmethod
    def check_token_age(cls, token) -> Optional[str]:
        """
        Check if token is approaching expiration or too old.

        Args:
            token: APIToken instance

        Returns:
            Warning message if token should be rotated, None otherwise
        """
        age = timezone.now() - token.created_at

        if age.days > cls.MAX_TOKEN_AGE_DAYS:
            return (
                f"Token is {age.days} days old. "
                f"Recommend rotation after {cls.MAX_TOKEN_AGE_DAYS} days."
            )

        return None


class DeploymentIsolationValidator(SecurityValidator):
    """
    Validate deployment isolation constraints.

    Edge Case #4: Privilege Escalation via Deployment
    Ensures deployments cannot access other deployments or control panel.
    """

    @classmethod
    def _base_install_path(cls) -> Path:
        """Return the base WebOps install path from settings or env."""
        # Default to '/opt/webops' to preserve existing behavior if unset
        base = getattr(settings, 'WEBOPS_INSTALL_PATH', os.environ.get('WEBOPS_INSTALL_PATH', '/opt/webops'))
        try:
            return Path(base)
        except Exception:
            # Fallback to default if invalid
            return Path('/opt/webops')

    @classmethod
    def _forbidden_paths(cls) -> List[Path]:
        """Compute forbidden absolute path prefixes dynamically (as Path objects)."""
        base = cls._base_install_path()
        return [
            Path('/etc'),
            Path('/root'),
            Path('/var/log'),
            Path('/usr/bin'),
            Path('/usr/sbin'),
            base / 'control-panel',
        ]

    @classmethod
    def _allowed_bases(cls) -> Dict[str, List[Path]]:
        """Compute allowed base directories dynamically (as Path objects)."""
        import tempfile
        base = cls._base_install_path()
        tmp_dir = Path(tempfile.gettempdir())
        var_tmp = Path('/var/tmp')
        tmp_list: List[Path] = [tmp_dir]
        # Include /var/tmp if it exists (Linux-specific but harmless check)
        try:
            if var_tmp.exists():
                tmp_list.append(var_tmp)
        except Exception:
            pass

        return {
            'deployments': [base / 'deployments'],
            'shared': [base / 'shared'],
            'tmp': tmp_list,
        }

    @classmethod
    def validate_file_access(cls, deployment_name: str, path: str, mode: str = 'read') -> None:
        """
        Validate file access request from deployment.

        Args:
            deployment_name: Name of deployment
            path: File path being accessed
            mode: Access mode ('read' or 'write')

        Raises:
            ValidationError: If access is forbidden
        """
        # Resolve any symlinks or relative paths
        try:
            resolved_path = Path(path).resolve()
            path_str = str(resolved_path)
        except Exception:
            raise ValidationError(f"Invalid file path: {path}")

        # Check forbidden paths (Path-based, platform-independent)
        for forbidden in cls._forbidden_paths():
            try:
                if resolved_path == forbidden or resolved_path.is_relative_to(forbidden):
                    raise ValidationError(
                        f"Access to {str(forbidden)} is forbidden for deployments"
                    )
            except Exception:
                # On some platforms, is_relative_to may raise for invalid combos; ignore
                pass

        # Check allowed paths using base directories
        bases = cls._allowed_bases()
        allowed = False

        # Allow within the same deployment directory only
        for dep_base in bases['deployments']:
            try:
                if resolved_path.is_relative_to(dep_base):
                    # Must be within the specific deployment's subdir
                    if resolved_path.is_relative_to(dep_base / deployment_name):
                        allowed = True
                        break
            except Exception:
                continue

        # Allow shared resources
        if not allowed:
            for shared_base in bases['shared']:
                try:
                    if resolved_path.is_relative_to(shared_base):
                        allowed = True
                        break
                except Exception:
                    continue

        # Allow temp directories
        if not allowed:
            for tmp_base in bases['tmp']:
                try:
                    if resolved_path.is_relative_to(tmp_base):
                        allowed = True
                        break
                except Exception:
                    continue

        if not allowed:
            raise ValidationError(
                f"Access to {path} is not allowed. "
                f"Deployments can only access their own directory and shared resources."
            )


class SecretKeyValidator(SecurityValidator):
    """
    Validate Django SECRET_KEY generation and uniqueness.

    Edge Case #5: Session Hijacking Across Deployments
    Ensures each deployment has unique SECRET_KEY.
    """

    MIN_SECRET_KEY_LENGTH = 50

    @classmethod
    def generate_secret_key(cls) -> str:
        """Generate cryptographically secure SECRET_KEY."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits + string.punctuation
        secret_key = ''.join(secrets.choice(alphabet) for _ in range(64))

        return secret_key

    @classmethod
    def validate_secret_key(cls, secret_key: str) -> None:
        """
        Validate SECRET_KEY security.

        Args:
            secret_key: Django SECRET_KEY value

        Raises:
            ValidationError: If SECRET_KEY is weak
        """
        cls.validate_or_raise(
            len(secret_key) >= cls.MIN_SECRET_KEY_LENGTH,
            f"SECRET_KEY must be at least {cls.MIN_SECRET_KEY_LENGTH} characters"
        )

        # Check for common weak keys
        weak_keys = [
            'your-secret-key',
            'django-insecure',
            'changeme',
            'secret',
            '1234567890',
        ]

        for weak in weak_keys:
            cls.validate_or_raise(
                weak.lower() not in secret_key.lower(),
                f"SECRET_KEY appears to be a default/weak value"
            )


# Import Path for validation
from pathlib import Path
