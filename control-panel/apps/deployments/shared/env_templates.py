"""
Environment variable templates for different frameworks.

Provides sensible default environment variables and their descriptions
for each supported framework.
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class EnvVar:
    """Environment variable definition."""
    key: str
    default: str
    description: str
    required: bool = False
    secret: bool = False


class EnvTemplates:
    """Environment variable templates for all frameworks."""

    # Django
    DJANGO = [
        EnvVar('SECRET_KEY', '${DJANGO_SECRET_KEY}', 'Django secret key (auto-generated)', required=True, secret=True),
        EnvVar('DEBUG', 'False', 'Debug mode (should be False in production)', required=True),
        EnvVar('ALLOWED_HOSTS', '*', 'Comma-separated list of allowed hosts', required=True),
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database connection string', required=True),
        EnvVar('REDIS_URL', 'redis://localhost:6379/0', 'Redis connection string for caching', required=False),
        EnvVar('CELERY_BROKER_URL', 'redis://localhost:6379/0', 'Celery broker URL', required=False),
        EnvVar('DJANGO_SETTINGS_MODULE', 'config.settings.production', 'Django settings module', required=True),
    ]

    # FastAPI
    FASTAPI = [
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database connection string', required=False),
        EnvVar('REDIS_URL', 'redis://localhost:6379/0', 'Redis connection string', required=False),
        EnvVar('SECRET_KEY', '${SECRET_KEY}', 'JWT secret key', required=True, secret=True),
        EnvVar('API_V1_STR', '/api/v1', 'API version prefix', required=False),
        EnvVar('PROJECT_NAME', 'MyAPI', 'Project name', required=False),
        EnvVar('BACKEND_CORS_ORIGINS', '[]', 'CORS origins (JSON array)', required=False),
    ]

    # Next.js
    NEXTJS = [
        EnvVar('NODE_ENV', 'production', 'Node environment', required=True),
        EnvVar('NEXT_PUBLIC_API_URL', 'https://api.example.com', 'Public API URL', required=False),
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database URL (if using Prisma)', required=False),
        EnvVar('NEXTAUTH_URL', 'https://example.com', 'NextAuth URL for authentication', required=False),
        EnvVar('NEXTAUTH_SECRET', '${NEXTAUTH_SECRET}', 'NextAuth secret', required=False, secret=True),
    ]

    # Spring Boot
    SPRING_BOOT = [
        EnvVar('SPRING_PROFILES_ACTIVE', 'prod', 'Active Spring profiles', required=True),
        EnvVar('SPRING_DATASOURCE_URL', 'jdbc:postgresql://localhost:5432/dbname', 'Database URL', required=True),
        EnvVar('SPRING_DATASOURCE_USERNAME', 'user', 'Database username', required=True),
        EnvVar('SPRING_DATASOURCE_PASSWORD', 'password', 'Database password', required=True, secret=True),
        EnvVar('SERVER_PORT', '8080', 'Server port', required=False),
        EnvVar('JAVA_OPTS', '-Xmx512m -Xms256m', 'JVM options', required=False),
    ]

    # ASP.NET Core
    ASPNET_CORE = [
        EnvVar('ASPNETCORE_ENVIRONMENT', 'Production', 'ASP.NET Core environment', required=True),
        EnvVar('ASPNETCORE_URLS', 'http://+:5000', 'URLs to bind to', required=True),
        EnvVar('ConnectionStrings__DefaultConnection', 'Server=localhost;Database=mydb;User=sa;Password=pass;', 'Database connection string', required=True),
        EnvVar('JWT__Secret', '${JWT_SECRET}', 'JWT secret key', required=False, secret=True),
        EnvVar('JWT__Issuer', 'https://example.com', 'JWT issuer', required=False),
    ]

    # Phoenix (Elixir)
    PHOENIX = [
        EnvVar('MIX_ENV', 'prod', 'Mix environment', required=True),
        EnvVar('SECRET_KEY_BASE', '${SECRET_KEY_BASE}', 'Phoenix secret key base', required=True, secret=True),
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database URL', required=True),
        EnvVar('PORT', '4000', 'Port to run on', required=True),
        EnvVar('PHX_HOST', 'example.com', 'Phoenix host', required=False),
        EnvVar('PHX_SERVER', 'true', 'Start Phoenix server', required=True),
    ]

    # Go
    GO = [
        EnvVar('PORT', '8080', 'Port to run on', required=False),
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database URL', required=False),
        EnvVar('REDIS_URL', 'redis://localhost:6379/0', 'Redis URL', required=False),
        EnvVar('JWT_SECRET', '${JWT_SECRET}', 'JWT secret', required=False, secret=True),
    ]

    # Ruby on Rails
    RAILS = [
        EnvVar('RAILS_ENV', 'production', 'Rails environment', required=True),
        EnvVar('RACK_ENV', 'production', 'Rack environment', required=True),
        EnvVar('SECRET_KEY_BASE', '${SECRET_KEY_BASE}', 'Rails secret key base', required=True, secret=True),
        EnvVar('DATABASE_URL', 'postgresql://user:pass@localhost:5432/dbname', 'Database URL', required=True),
        EnvVar('REDIS_URL', 'redis://localhost:6379/0', 'Redis URL', required=False),
        EnvVar('RAILS_SERVE_STATIC_FILES', 'true', 'Serve static files', required=False),
        EnvVar('RAILS_LOG_TO_STDOUT', 'true', 'Log to stdout', required=False),
    ]

    # Laravel
    LARAVEL = [
        EnvVar('APP_ENV', 'production', 'Application environment', required=True),
        EnvVar('APP_KEY', '${APP_KEY}', 'Application encryption key', required=True, secret=True),
        EnvVar('APP_DEBUG', 'false', 'Debug mode', required=True),
        EnvVar('APP_URL', 'https://example.com', 'Application URL', required=True),
        EnvVar('DB_CONNECTION', 'pgsql', 'Database connection type', required=True),
        EnvVar('DB_HOST', 'localhost', 'Database host', required=True),
        EnvVar('DB_PORT', '5432', 'Database port', required=True),
        EnvVar('DB_DATABASE', 'laravel', 'Database name', required=True),
        EnvVar('DB_USERNAME', 'user', 'Database username', required=True),
        EnvVar('DB_PASSWORD', 'password', 'Database password', required=True, secret=True),
    ]

    # Express.js
    EXPRESS = [
        EnvVar('NODE_ENV', 'production', 'Node environment', required=True),
        EnvVar('PORT', '3000', 'Port to run on', required=False),
        EnvVar('DATABASE_URL', 'mongodb://localhost:27017/mydb', 'Database URL', required=False),
        EnvVar('REDIS_URL', 'redis://localhost:6379/0', 'Redis URL', required=False),
        EnvVar('JWT_SECRET', '${JWT_SECRET}', 'JWT secret', required=False, secret=True),
        EnvVar('SESSION_SECRET', '${SESSION_SECRET}', 'Session secret', required=False, secret=True),
    ]

    # Generic Node.js
    NODEJS = [
        EnvVar('NODE_ENV', 'production', 'Node environment', required=True),
        EnvVar('PORT', '3000', 'Port to run on', required=False),
    ]

    # Python (generic)
    PYTHON = [
        EnvVar('PYTHONUNBUFFERED', '1', 'Unbuffered Python output', required=False),
        EnvVar('PORT', '8000', 'Port to run on', required=False),
    ]

    @classmethod
    def get_template(cls, framework: str) -> List[EnvVar]:
        """
        Get environment variable template for a framework.

        Args:
            framework: Framework name (e.g., 'django', 'nextjs', 'spring-boot')

        Returns:
            List of EnvVar objects
        """
        framework_map = {
            'django': cls.DJANGO,
            'django-rest-framework': cls.DJANGO,
            'fastapi': cls.FASTAPI,
            'flask': cls.PYTHON + [
                EnvVar('FLASK_ENV', 'production', 'Flask environment', required=True),
                EnvVar('SECRET_KEY', '${SECRET_KEY}', 'Flask secret key', required=True, secret=True),
            ],
            'nextjs': cls.NEXTJS,
            'react': cls.NODEJS,
            'vue': cls.NODEJS,
            'express': cls.EXPRESS,
            'nestjs': cls.EXPRESS,
            'spring-boot': cls.SPRING_BOOT,
            'aspnet-core': cls.ASPNET_CORE,
            'phoenix': cls.PHOENIX,
            'go': cls.GO,
            'rails': cls.RAILS,
            'laravel': cls.LARAVEL,
            'nodejs': cls.NODEJS,
            'python': cls.PYTHON,
        }

        return framework_map.get(framework, [])

    @classmethod
    def get_template_dict(cls, framework: str, include_secrets: bool = True) -> Dict[str, str]:
        """
        Get environment variables as a dictionary.

        Args:
            framework: Framework name
            include_secrets: Whether to include secret placeholders

        Returns:
            Dictionary of env vars
        """
        env_vars = cls.get_template(framework)

        result = {}
        for var in env_vars:
            if var.secret and not include_secrets:
                continue
            result[var.key] = var.default

        return result

    @classmethod
    def generate_secrets(cls) -> Dict[str, str]:
        """Generate random secrets for common secret keys."""
        import secrets
        import string

        def generate_key(length: int = 50) -> str:
            alphabet = string.ascii_letters + string.digits
            return ''.join(secrets.choice(alphabet) for _ in range(length))

        return {
            'DJANGO_SECRET_KEY': generate_key(50),
            'SECRET_KEY': generate_key(50),
            'NEXTAUTH_SECRET': generate_key(32),
            'JWT_SECRET': generate_key(32),
            'SESSION_SECRET': generate_key(32),
            'SECRET_KEY_BASE': generate_key(64),
            'APP_KEY': 'base64:' + generate_key(32),
        }

    @classmethod
    def apply_template(cls, framework: str, existing_env: Dict[str, str] = None) -> Dict[str, str]:
        """
        Apply template to existing environment variables.

        Generates secrets and merges with existing vars (existing takes precedence).

        Args:
            framework: Framework name
            existing_env: Existing environment variables

        Returns:
            Merged environment variables
        """
        existing_env = existing_env or {}

        # Get template
        template = cls.get_template_dict(framework, include_secrets=True)

        # Generate secrets
        secrets_map = cls.generate_secrets()

        # Replace placeholders with generated secrets
        for key, value in template.items():
            if '${' in value:
                # Extract placeholder name
                import re
                match = re.search(r'\$\{([^}]+)\}', value)
                if match:
                    placeholder = match.group(1)
                    if placeholder in secrets_map:
                        template[key] = value.replace(f'${{{placeholder}}}', secrets_map[placeholder])

        # Merge with existing (existing takes precedence)
        result = {**template, **existing_env}

        return result
