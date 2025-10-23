"""
Common domain for WebOps.

Provides shared utilities and components used across all domains.
"""

from .utils import (
    generate_password,
    generate_secret_key,
    encrypt_value,
    decrypt_value,
    generate_port,
    validate_repo_url,
    get_client_ip,
    validate_domain_name,
    sanitize_deployment_name,
    format_bytes,
    format_uptime,
)

__all__ = [
    'generate_password',
    'generate_secret_key',
    'encrypt_value',
    'decrypt_value',
    'generate_port',
    'validate_repo_url',
    'get_client_ip',
    'validate_domain_name',
    'sanitize_deployment_name',
    'format_bytes',
    'format_uptime',
]
