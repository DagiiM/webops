"""
Service Declaration Enforcement for WebOps.

Ensures all deployments properly declare required services:
- nginx (default webserver)
- postgresql (default database)
- redis (for caching/sessions)
- gunicorn (for Django projects)
- celery (for background processing)

Reference: CLAUDE.md and docs/APP-CONTRACT.md
"""

from typing import Dict, List, Tuple, Optional
from pathlib import Path
from .contract import AppContract, ContractParser


class ServiceEnforcer:
    """
    Enforces service declaration requirements for deployments.

    Validates that apps declare all required services and
    prevents deployment if requirements are not met.
    """

    # Default services required for different project types
    REQUIRED_SERVICES = {
        'django': {
            'webserver': 'nginx',
            'app_server': 'gunicorn',
            'database': 'postgresql'
        },
        'flask': {
            'webserver': 'nginx',
            'app_server': 'gunicorn',
            'database': 'postgresql'
        },
        'static': {
            'webserver': 'nginx'
        },
        'nodejs': {
            'webserver': 'nginx'
        }
    }

    # Optional services that can be declared
    OPTIONAL_SERVICES = {
        'cache': ['redis'],
        'background_tasks': ['celery'],
        'storage': ['local', 's3']
    }

    @staticmethod
    def validate_service_declarations(
        contract: AppContract,
        repo_path: Path
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all required services are declared.

        Args:
            contract: Parsed app contract
            repo_path: Path to repository

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        project_type = contract.type

        # Get required services for project type
        required = ServiceEnforcer.REQUIRED_SERVICES.get(project_type, {})

        # Check webserver declaration
        if 'webserver' in required:
            if not contract.network.http_port:
                errors.append(
                    f"Project type '{project_type}' requires HTTP service but "
                    f"network.http_port is not enabled in webops.yml"
                )

        # Check database declaration
        if 'database' in required:
            if not contract.services.database.enabled:
                errors.append(
                    f"Project type '{project_type}' requires database service. "
                    f"Add 'services.database.enabled: true' to webops.yml"
                )
            elif contract.services.database.type != required['database']:
                errors.append(
                    f"Default database is {required['database']} but "
                    f"{contract.services.database.type} was declared"
                )

        # Check app server (gunicorn for Django/Flask)
        if 'app_server' in required:
            # For Django/Flask, gunicorn is implicit
            # Validate that requirements.txt exists
            requirements_file = repo_path / 'requirements.txt'
            if not requirements_file.exists():
                errors.append(
                    f"Project type '{project_type}' requires requirements.txt file"
                )
            else:
                # Check if gunicorn is in requirements
                try:
                    requirements = requirements_file.read_text()
                    if 'gunicorn' not in requirements.lower():
                        errors.append(
                            f"Add 'gunicorn' to requirements.txt for {project_type} projects"
                        )
                except Exception as e:
                    errors.append(f"Failed to read requirements.txt: {str(e)}")

        # Validate optional services if declared
        if contract.services.cache.enabled:
            if contract.services.cache.type not in ServiceEnforcer.OPTIONAL_SERVICES['cache']:
                errors.append(
                    f"Unsupported cache type: {contract.services.cache.type}. "
                    f"Supported: {', '.join(ServiceEnforcer.OPTIONAL_SERVICES['cache'])}"
                )

        if contract.services.background_tasks.enabled:
            bg_type = contract.services.background_tasks.type
            if bg_type not in ServiceEnforcer.OPTIONAL_SERVICES['background_tasks']:
                errors.append(
                    f"Unsupported background tasks type: {bg_type}. "
                    f"Supported: {', '.join(ServiceEnforcer.OPTIONAL_SERVICES['background_tasks'])}"
                )

            # If Celery is declared, Redis should also be declared
            if bg_type == 'celery' and not contract.services.cache.enabled:
                errors.append(
                    "Celery requires Redis as message broker. "
                    "Enable cache service with type 'redis' in webops.yml"
                )

        # Validate storage service
        if contract.services.storage.enabled:
            storage_type = contract.services.storage.type
            if storage_type not in ServiceEnforcer.OPTIONAL_SERVICES['storage']:
                errors.append(
                    f"Unsupported storage type: {storage_type}. "
                    f"Supported: {', '.join(ServiceEnforcer.OPTIONAL_SERVICES['storage'])}"
                )

        return (len(errors) == 0, errors)

    @staticmethod
    def get_service_dependencies(contract: AppContract) -> Dict[str, List[str]]:
        """
        Get all service dependencies for the deployment.

        Returns:
            Dictionary mapping service types to their configurations
        """
        dependencies = {
            'webserver': [],
            'database': [],
            'cache': [],
            'background_tasks': [],
            'storage': []
        }

        # Add nginx for HTTP projects
        if contract.network.http_port:
            dependencies['webserver'].append('nginx')

        # Add database if enabled
        if contract.services.database.enabled:
            db_type = contract.services.database.type
            version = contract.services.database.version or 'latest'
            dependencies['database'].append(f'{db_type}:{version}')

        # Add cache if enabled
        if contract.services.cache.enabled:
            cache_type = contract.services.cache.type
            dependencies['cache'].append(cache_type)

        # Add background tasks if enabled
        if contract.services.background_tasks.enabled:
            bg_type = contract.services.background_tasks.type
            workers = contract.services.background_tasks.workers
            dependencies['background_tasks'].append(f'{bg_type}:workers={workers}')

        # Add storage if enabled
        if contract.services.storage.enabled:
            storage_type = contract.services.storage.type
            quota = contract.services.storage.quota
            dependencies['storage'].append(f'{storage_type}:quota={quota}')

        # Remove empty categories
        return {k: v for k, v in dependencies.items() if v}

    @staticmethod
    def generate_default_contract(
        project_type: str,
        name: str
    ) -> str:
        """
        Generate a default webops.yml contract for a project type.

        Args:
            project_type: Type of project (django, flask, static, nodejs)
            name: Name of the project

        Returns:
            YAML string for webops.yml
        """
        templates = {
            'django': """version: "1.0"
name: "{name}"
type: "django"

resources:
  memory: "512M"
  cpu: "0.5"
  disk: "2G"

services:
  # PostgreSQL database (default for Django)
  database:
    enabled: true
    type: "postgresql"
    version: "15"

  # Redis for caching and sessions (recommended)
  cache:
    enabled: true
    type: "redis"

  # Celery for background tasks (optional)
  background_tasks:
    enabled: false
    type: "celery"
    workers: 2
    beat: false

  # Local file storage
  storage:
    enabled: true
    type: "local"
    quota: "5G"

network:
  http_port: true
  https: true
  domains: []

permissions:
  allow_network: true
  allow_filesystem: true
  read_only: false
""",
            'static': """version: "1.0"
name: "{name}"
type: "static"

resources:
  memory: "128M"
  cpu: "0.1"
  disk: "500M"

services:
  database:
    enabled: false

  cache:
    enabled: false

  storage:
    enabled: true
    type: "local"
    quota: "1G"

network:
  http_port: true
  https: true
  domains: []

permissions:
  allow_network: false
  allow_filesystem: false
  read_only: true
""",
            'nodejs': """version: "1.0"
name: "{name}"
type: "nodejs"

resources:
  memory: "512M"
  cpu: "0.5"
  disk: "2G"

services:
  # Database (optional for Node.js)
  database:
    enabled: false
    type: "postgresql"

  # Redis for caching (optional)
  cache:
    enabled: false
    type: "redis"

  storage:
    enabled: true
    type: "local"
    quota: "2G"

network:
  http_port: true
  https: true
  domains: []

permissions:
  allow_network: true
  allow_filesystem: true
  read_only: false
"""
        }

        template = templates.get(project_type, templates['django'])
        return template.format(name=name)

    @staticmethod
    def check_and_create_contract(
        repo_path: Path,
        project_type: str,
        name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if webops.yml exists, create default if missing.

        Args:
            repo_path: Path to repository
            project_type: Type of project
            name: Name of deployment

        Returns:
            Tuple of (contract_exists, error_message)
        """
        contract_path = repo_path / 'webops.yml'

        if not contract_path.exists():
            # Generate and write default contract
            default_contract = ServiceEnforcer.generate_default_contract(
                project_type,
                name
            )

            try:
                contract_path.write_text(default_contract)
                return (
                    True,
                    f"Created default webops.yml for {project_type} project. "
                    f"Review and adjust as needed."
                )
            except Exception as e:
                return (
                    False,
                    f"Failed to create webops.yml: {str(e)}"
                )

        return (True, None)
