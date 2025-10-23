"""
Environment Variable Management Utility

This module provides intelligent parsing of .env.example files and automatic
generation of .env files with proper values for different variable types.

Features:
- Parse .env.example files with comments and structure preservation
- Auto-detect variable types (SECRET_KEY, DATABASE_URL, API keys, etc.)
- Generate appropriate values for different variable types
- Support for Django, Flask, Node.js, and generic applications
- Preserve comments and formatting from .env.example
"""

import os
import re
import secrets
import string
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class VarType(Enum):
    """Types of environment variables."""
    SECRET_KEY = "secret_key"
    ENCRYPTION_KEY = "encryption_key"
    DATABASE_URL = "database_url"
    REDIS_URL = "redis_url"
    API_KEY = "api_key"
    API_SECRET = "api_secret"
    JWT_SECRET = "jwt_secret"
    ALLOWED_HOSTS = "allowed_hosts"
    DEBUG = "debug"
    PORT = "port"
    DOMAIN = "domain"
    EMAIL = "email"
    PASSWORD = "password"
    BOOLEAN = "boolean"
    NUMBER = "number"
    STRING = "string"
    URL = "url"
    UNKNOWN = "unknown"


@dataclass
class EnvVariable:
    """Represents a single environment variable."""
    key: str
    value: str
    var_type: VarType
    comment: Optional[str] = None
    required: bool = True
    example_value: Optional[str] = None


class EnvParser:
    """Parse .env.example files and detect variable types."""

    # Patterns for detecting variable types
    PATTERNS = {
        VarType.SECRET_KEY: [
            r'SECRET_KEY',
            r'SESSION_SECRET',
            r'APP_SECRET',
        ],
        VarType.ENCRYPTION_KEY: [
            r'ENCRYPTION_KEY',
            r'FERNET_KEY',
            r'CRYPTO_KEY',
        ],
        VarType.DATABASE_URL: [
            r'DATABASE_URL',
            r'DB_URL',
            r'POSTGRES_URL',
            r'MYSQL_URL',
        ],
        VarType.REDIS_URL: [
            r'REDIS_URL',
            r'CACHE_URL',
            r'CELERY_BROKER',
        ],
        VarType.API_KEY: [
            r'API_KEY',
            r'.*_API_KEY',
            r'.*_KEY$',
        ],
        VarType.API_SECRET: [
            r'API_SECRET',
            r'.*_API_SECRET',
            r'.*_SECRET$',
        ],
        VarType.JWT_SECRET: [
            r'JWT_SECRET',
            r'TOKEN_SECRET',
        ],
        VarType.ALLOWED_HOSTS: [
            r'ALLOWED_HOSTS',
            r'CORS_ORIGINS',
        ],
        VarType.DEBUG: [
            r'^DEBUG$',
            r'.*_DEBUG$',
        ],
        VarType.PORT: [
            r'PORT',
            r'.*_PORT$',
        ],
        VarType.DOMAIN: [
            r'DOMAIN',
            r'HOST',
            r'HOSTNAME',
        ],
        VarType.EMAIL: [
            r'EMAIL',
            r'.*_EMAIL$',
        ],
        VarType.PASSWORD: [
            r'PASSWORD',
            r'.*_PASSWORD$',
            r'.*_PASS$',
        ],
        VarType.URL: [
            r'.*_URL$',
            r'WEBHOOK',
        ],
    }

    def __init__(self, env_example_path: Path):
        """Initialize parser with .env.example file path."""
        self.env_example_path = Path(env_example_path)
        self.variables: List[EnvVariable] = []
        self.comments: List[str] = []

    def parse(self) -> List[EnvVariable]:
        """Parse .env.example file and return list of variables."""
        if not self.env_example_path.exists():
            raise FileNotFoundError(f".env.example not found: {self.env_example_path}")

        with open(self.env_example_path, 'r') as f:
            lines = f.readlines()

        current_comment = []

        for line in lines:
            line = line.rstrip()

            # Skip empty lines
            if not line.strip():
                if current_comment:
                    current_comment.append("")
                continue

            # Comment line
            if line.strip().startswith('#'):
                current_comment.append(line)
                continue

            # Variable line
            if '=' in line:
                key, value = self._parse_line(line)
                if key:
                    var_type = self._detect_type(key, value)
                    required = self._is_required(key, value, current_comment)

                    env_var = EnvVariable(
                        key=key,
                        value=value,
                        var_type=var_type,
                        comment='\n'.join(current_comment) if current_comment else None,
                        required=required,
                        example_value=value if value else None
                    )

                    self.variables.append(env_var)
                    current_comment = []

        return self.variables

    def _parse_line(self, line: str) -> Tuple[str, str]:
        """Parse a single line into key and value."""
        # Remove inline comments
        if '#' in line:
            # But not if # is inside quotes
            parts = line.split('#')
            if len(parts) > 1:
                # Check if # is inside quotes
                quote_count = parts[0].count('"') + parts[0].count("'")
                if quote_count % 2 == 0:
                    line = parts[0]

        # Split on first =
        if '=' not in line:
            return '', ''

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        # Remove quotes from value
        if value:
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

        return key, value

    def _detect_type(self, key: str, value: str) -> VarType:
        """Detect the type of variable based on key and value."""
        key_upper = key.upper()

        # Check against patterns
        for var_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, key_upper):
                    return var_type

        # Check value patterns
        if value:
            if value.lower() in ('true', 'false'):
                return VarType.BOOLEAN
            if value.isdigit():
                return VarType.NUMBER
            if value.startswith('http://') or value.startswith('https://'):
                return VarType.URL

        return VarType.UNKNOWN

    def _is_required(self, key: str, value: str, comments: List[str]) -> bool:
        """Determine if variable is required."""
        # Check comments for optional indicator
        comment_text = ' '.join(comments).lower()
        if 'optional' in comment_text or 'leave blank' in comment_text:
            return False

        # If has no default value, likely required
        if not value or value == '':
            return True

        # If has placeholder value, required
        placeholders = ['your-', 'change-', 'replace-', 'insert-', '<', 'xxx', 'todo']
        if any(p in value.lower() for p in placeholders):
            return True

        return False


class EnvGenerator:
    """Generate .env files with appropriate values."""

    def __init__(
        self,
        deployment_name: str,
        domain: Optional[str] = None,
        database_info: Optional[Dict[str, str]] = None,
        redis_url: str = "redis://localhost:6379/0",
        debug: bool = False
    ):
        """
        Initialize generator with deployment context.

        Args:
            deployment_name: Name of the deployment
            domain: Domain name for the deployment
            database_info: Dict with db_name, db_user, db_password, db_host, db_port
            redis_url: Redis URL
            debug: Whether to enable debug mode
        """
        self.deployment_name = deployment_name
        self.domain = domain or f"{deployment_name}.localhost"
        self.database_info = database_info or {}
        self.redis_url = redis_url
        self.debug = debug

    def generate(self, variables: List[EnvVariable]) -> str:
        """Generate .env content from parsed variables."""
        lines = []

        for var in variables:
            # Add comment if exists
            if var.comment:
                lines.append(var.comment)

            # Generate value
            generated_value = self._generate_value(var)

            # Add variable line
            if generated_value is not None:
                # Quote value if it contains spaces or special chars
                if ' ' in str(generated_value) or any(c in str(generated_value) for c in ['#', '$', '&']):
                    lines.append(f'{var.key}="{generated_value}"')
                else:
                    lines.append(f'{var.key}={generated_value}')
            else:
                lines.append(f'{var.key}=')

            # Add blank line after each variable for readability
            lines.append('')

        return '\n'.join(lines)

    def _generate_value(self, var: EnvVariable) -> Optional[str]:
        """Generate appropriate value for variable type."""
        # If not required and no example, leave empty
        if not var.required and not var.example_value:
            return None

        # Generate based on type
        if var.var_type == VarType.SECRET_KEY:
            return self._generate_secret_key()

        elif var.var_type == VarType.ENCRYPTION_KEY:
            return self._generate_encryption_key()

        elif var.var_type == VarType.DATABASE_URL:
            return self._generate_database_url()

        elif var.var_type == VarType.REDIS_URL:
            return self.redis_url

        elif var.var_type == VarType.API_KEY:
            return self._generate_api_key()

        elif var.var_type == VarType.API_SECRET:
            return self._generate_api_secret()

        elif var.var_type == VarType.JWT_SECRET:
            return self._generate_jwt_secret()

        elif var.var_type == VarType.ALLOWED_HOSTS:
            return self.domain

        elif var.var_type == VarType.DEBUG:
            return 'True' if self.debug else 'False'

        elif var.var_type == VarType.PORT:
            # Will be assigned by deployment system
            return var.example_value or '8000'

        elif var.var_type == VarType.DOMAIN:
            return self.domain

        elif var.var_type == VarType.EMAIL:
            return f"admin@{self.domain}"

        elif var.var_type == VarType.PASSWORD:
            return self._generate_password()

        elif var.var_type == VarType.BOOLEAN:
            return 'False'

        elif var.var_type == VarType.NUMBER:
            return var.example_value or '0'

        elif var.var_type == VarType.URL:
            return var.example_value or ''

        else:
            # Unknown type - keep example value or leave empty
            return var.example_value or ''

    def _generate_secret_key(self, length: int = 64) -> str:
        """Generate Django/Flask secret key."""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        # Remove quotes to avoid escaping issues
        alphabet = alphabet.replace('"', '').replace("'", '').replace('\\', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _generate_encryption_key(self) -> str:
        """Generate Fernet encryption key."""
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()

    def _generate_database_url(self) -> str:
        """Generate PostgreSQL database URL."""
        if not self.database_info:
            return 'postgresql://user:password@localhost:5432/dbname'

        db_name = self.database_info.get('db_name', self.deployment_name)
        db_user = self.database_info.get('db_user', self.deployment_name)
        db_password = self.database_info.get('db_password', '')
        db_host = self.database_info.get('db_host', 'localhost')
        db_port = self.database_info.get('db_port', '5432')

        if db_password:
            return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            return f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

    def _generate_api_key(self, length: int = 32) -> str:
        """Generate API key."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _generate_api_secret(self, length: int = 64) -> str:
        """Generate API secret."""
        return secrets.token_urlsafe(length)

    def _generate_jwt_secret(self, length: int = 64) -> str:
        """Generate JWT secret."""
        return secrets.token_urlsafe(length)

    def _generate_password(self, length: int = 32) -> str:
        """Generate secure password."""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        # Remove confusing characters
        alphabet = alphabet.replace('l', '').replace('1', '').replace('O', '').replace('0', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class EnvManager:
    """High-level interface for environment variable management."""

    @staticmethod
    def process_env_file(
        repo_path: Path,
        deployment_name: str,
        domain: Optional[str] = None,
        database_info: Optional[Dict[str, str]] = None,
        redis_url: str = "redis://localhost:6379/0",
        debug: bool = False,
        custom_values: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str]:
        """
        Process .env.example and generate .env file.

        Args:
            repo_path: Path to repository root
            deployment_name: Name of the deployment
            domain: Domain name
            database_info: Database connection info
            redis_url: Redis connection URL
            debug: Debug mode flag
            custom_values: Custom key-value pairs to override

        Returns:
            Tuple of (success: bool, message: str)
        """
        repo_path = Path(repo_path)
        env_example = repo_path / '.env.example'
        env_file = repo_path / '.env'

        # Check if .env.example exists
        if not env_example.exists():
            # Check for alternative names
            alternatives = [
                repo_path / 'env.example',
                repo_path / '.env.sample',
                repo_path / 'env.sample',
            ]

            for alt in alternatives:
                if alt.exists():
                    env_example = alt
                    break
            else:
                return False, "No .env.example file found in repository"

        try:
            # Parse .env.example
            parser = EnvParser(env_example)
            variables = parser.parse()

            # Generate .env content
            generator = EnvGenerator(
                deployment_name=deployment_name,
                domain=domain,
                database_info=database_info,
                redis_url=redis_url,
                debug=debug
            )

            env_content = generator.generate(variables)

            # Apply custom values if provided
            if custom_values:
                env_content = EnvManager._apply_custom_values(env_content, custom_values)

            # Write .env file
            with open(env_file, 'w') as f:
                f.write(env_content)

            # Set secure permissions
            env_file.chmod(0o600)

            # Report on variables
            required_vars = [v for v in variables if v.required]
            optional_vars = [v for v in variables if not v.required]

            message = (
                f"Generated .env file with {len(variables)} variables:\n"
                f"  - {len(required_vars)} required\n"
                f"  - {len(optional_vars)} optional\n"
                f"File: {env_file}"
            )

            return True, message

        except Exception as e:
            return False, f"Error processing env file: {str(e)}"

    @staticmethod
    def _apply_custom_values(env_content: str, custom_values: Dict[str, str]) -> str:
        """Apply custom values to generated .env content."""
        lines = env_content.split('\n')
        result = []

        for line in lines:
            if '=' in line and not line.strip().startswith('#'):
                key = line.split('=', 1)[0].strip()
                if key in custom_values:
                    value = custom_values[key]
                    # Quote if necessary
                    if ' ' in value or any(c in value for c in ['#', '$', '&']):
                        result.append(f'{key}="{value}"')
                    else:
                        result.append(f'{key}={value}')
                else:
                    result.append(line)
            else:
                result.append(line)

        return '\n'.join(result)

    @staticmethod
    def validate_env_file(repo_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate that all required variables are set in .env file.

        Returns:
            Tuple of (is_valid: bool, missing_vars: List[str])
        """
        repo_path = Path(repo_path)
        env_example = repo_path / '.env.example'
        env_file = repo_path / '.env'

        if not env_file.exists():
            return False, [".env file not found"]

        if not env_example.exists():
            return True, []  # No .env.example to validate against

        try:
            # Parse .env.example
            parser = EnvParser(env_example)
            variables = parser.parse()

            # Load .env file
            env_vars = {}
            with open(env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()

            # Check required variables
            missing = []
            for var in variables:
                if var.required and var.key not in env_vars:
                    missing.append(var.key)
                elif var.required and not env_vars.get(var.key):
                    missing.append(f"{var.key} (empty)")

            return len(missing) == 0, missing

        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
