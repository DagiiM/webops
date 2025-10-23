"""
Django management command to generate .env files from .env.example.

Usage:
    python manage.py generate_env /path/to/repo --deployment myapp
    python manage.py generate_env /path/to/repo --deployment myapp --domain example.com --debug
"""

from django.core.management.base import BaseCommand, CommandError
from pathlib import Path
from apps.core.managers.env_manager import EnvManager
import sys


class Command(BaseCommand):
    help = 'Generate .env file from .env.example with intelligent value generation'

    def add_arguments(self, parser):
        parser.add_argument(
            'repo_path',
            type=str,
            help='Path to repository containing .env.example'
        )
        parser.add_argument(
            '--deployment',
            type=str,
            required=True,
            help='Deployment name'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain name (default: deployment-name.localhost)'
        )
        parser.add_argument(
            '--db-name',
            type=str,
            help='Database name'
        )
        parser.add_argument(
            '--db-user',
            type=str,
            help='Database user'
        )
        parser.add_argument(
            '--db-password',
            type=str,
            help='Database password'
        )
        parser.add_argument(
            '--db-host',
            type=str,
            default='localhost',
            help='Database host (default: localhost)'
        )
        parser.add_argument(
            '--db-port',
            type=str,
            default='5432',
            help='Database port (default: 5432)'
        )
        parser.add_argument(
            '--redis-url',
            type=str,
            default='redis://localhost:6379/0',
            help='Redis URL (default: redis://localhost:6379/0)'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Enable debug mode'
        )
        parser.add_argument(
            '--set',
            action='append',
            metavar='KEY=VALUE',
            help='Set custom environment variable (can be used multiple times)'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate existing .env file without generating'
        )

    def handle(self, *args, **options):
        repo_path = Path(options['repo_path'])
        deployment_name = options['deployment']

        # Validate repo path
        if not repo_path.exists():
            raise CommandError(f"Repository path does not exist: {repo_path}")

        if not repo_path.is_dir():
            raise CommandError(f"Repository path is not a directory: {repo_path}")

        # Validate only mode
        if options['validate_only']:
            self.stdout.write("Validating existing .env file...")
            is_valid, missing = EnvManager.validate_env_file(repo_path)

            if is_valid:
                self.stdout.write(self.style.SUCCESS("✓ .env file is valid"))
                sys.exit(0)
            else:
                self.stdout.write(self.style.ERROR("✗ .env file validation failed"))
                self.stdout.write(self.style.ERROR("Missing or empty variables:"))
                for var in missing:
                    self.stdout.write(f"  - {var}")
                sys.exit(1)

        # Build database info
        database_info = None
        if any([options.get('db_name'), options.get('db_user'), options.get('db_password')]):
            database_info = {
                'db_name': options.get('db_name') or deployment_name,
                'db_user': options.get('db_user') or deployment_name,
                'db_password': options.get('db_password', ''),
                'db_host': options.get('db_host', 'localhost'),
                'db_port': options.get('db_port', '5432'),
            }

        # Parse custom values
        custom_values = {}
        if options.get('set'):
            for item in options['set']:
                if '=' not in item:
                    raise CommandError(f"Invalid --set format: {item}. Use KEY=VALUE")
                key, value = item.split('=', 1)
                custom_values[key.strip()] = value.strip()

        # Generate .env file
        self.stdout.write(f"Processing repository: {repo_path}")
        self.stdout.write(f"Deployment name: {deployment_name}")

        success, message = EnvManager.process_env_file(
            repo_path=repo_path,
            deployment_name=deployment_name,
            domain=options.get('domain'),
            database_info=database_info,
            redis_url=options.get('redis_url', 'redis://localhost:6379/0'),
            debug=options.get('debug', False),
            custom_values=custom_values if custom_values else None
        )

        if success:
            self.stdout.write(self.style.SUCCESS(f"\n✓ {message}"))

            # Show custom values that were applied
            if custom_values:
                self.stdout.write("\nCustom values applied:")
                for key, value in custom_values.items():
                    # Mask sensitive values
                    if any(s in key.upper() for s in ['SECRET', 'PASSWORD', 'KEY', 'TOKEN']):
                        masked = value[:4] + '*' * (len(value) - 4) if len(value) > 4 else '****'
                        self.stdout.write(f"  {key} = {masked}")
                    else:
                        self.stdout.write(f"  {key} = {value}")

            # Validate the generated file
            self.stdout.write("\nValidating generated .env file...")
            is_valid, missing = EnvManager.validate_env_file(repo_path)

            if is_valid:
                self.stdout.write(self.style.SUCCESS("✓ All required variables are set"))
            else:
                self.stdout.write(self.style.WARNING("⚠ Some required variables may need attention:"))
                for var in missing:
                    self.stdout.write(f"  - {var}")

            sys.exit(0)
        else:
            self.stdout.write(self.style.ERROR(f"\n✗ {message}"))
            sys.exit(1)
