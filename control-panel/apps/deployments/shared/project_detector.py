"""
Smart project structure detection for deployments.

Intelligently detects Django project structure including:
- Project root (where manage.py lives)
- Settings module location
- Requirements files
- WSGI/ASGI modules
- Static/media directories
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ProjectStructureDetector:
    """Intelligently detect Django project structure."""

    def __init__(self, repo_path: Path):
        """
        Initialize detector with repository path.

        Args:
            repo_path: Path to the cloned repository
        """
        self.repo_path = Path(repo_path)
        self.structure = {}

    def detect_all(self) -> Dict[str, Any]:
        """
        Detect all project structure components.

        Returns:
            Dictionary with detected paths and configuration
        """
        self.structure = {
            'repo_path': str(self.repo_path),
            'project_root': None,
            'manage_py_path': None,
            'settings_module': None,
            'settings_path': None,
            'requirements_files': [],
            'wsgi_module': None,
            'asgi_module': None,
            'is_django': False,
            'is_monorepo': False,
            'has_backend_dir': False,
            'project_type': 'unknown',
        }

        # Detect manage.py and project root
        self._detect_manage_py()

        # Detect settings module
        if self.structure['project_root']:
            self._detect_settings()
            self._detect_wsgi_asgi()
            self._detect_requirements()
            self._detect_project_type()

        return self.structure

    def _detect_manage_py(self) -> None:
        """Find manage.py in the repository."""
        # Search for manage.py anywhere in the repo
        manage_py_files = list(self.repo_path.rglob('manage.py'))

        if not manage_py_files:
            logger.warning(f"No manage.py found in {self.repo_path}")
            return

        # Filter out files in venv, .git, node_modules, etc.
        excluded_dirs = {'venv', 'env', '.venv', '.git', 'node_modules', '__pycache__', '.tox'}
        valid_manage_files = []

        for manage_file in manage_py_files:
            parts = manage_file.relative_to(self.repo_path).parts
            if not any(excluded in parts for excluded in excluded_dirs):
                valid_manage_files.append(manage_file)

        if not valid_manage_files:
            logger.warning("manage.py found only in excluded directories")
            return

        # If multiple manage.py files, choose the most likely one
        if len(valid_manage_files) > 1:
            # Prefer one closer to root or in 'backend' directory
            for manage_file in valid_manage_files:
                parts = manage_file.relative_to(self.repo_path).parts
                if 'backend' in parts or len(parts) == 1:
                    self.structure['manage_py_path'] = str(manage_file)
                    self.structure['project_root'] = str(manage_file.parent)
                    break
        else:
            manage_file = valid_manage_files[0]
            self.structure['manage_py_path'] = str(manage_file)
            self.structure['project_root'] = str(manage_file.parent)

        # Check if it's a monorepo with backend directory
        if self.structure['project_root']:
            project_root = Path(self.structure['project_root'])
            if project_root.name == 'backend' or 'backend' in str(project_root.relative_to(self.repo_path)):
                self.structure['has_backend_dir'] = True
                self.structure['is_monorepo'] = True

        self.structure['is_django'] = True
        logger.info(f"Detected Django project at: {self.structure['project_root']}")

    def _detect_settings(self) -> None:
        """Detect Django settings module location."""
        if not self.structure['project_root']:
            return

        project_root = Path(self.structure['project_root'])
        settings_files = []

        # Search for settings files
        for pattern in ['**/settings.py', '**/settings/*.py', '**/settings/base.py']:
            settings_files.extend(project_root.glob(pattern))

        # Filter out excluded directories
        excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
        valid_settings = []

        for settings_file in settings_files:
            parts = settings_file.relative_to(project_root).parts
            if not any(excluded in parts for excluded in excluded_dirs):
                valid_settings.append(settings_file)

        if not valid_settings:
            logger.warning("No settings.py found in project")
            return

        # Prioritize settings files
        best_settings = self._prioritize_settings(valid_settings, project_root)

        if best_settings:
            self.structure['settings_path'] = str(best_settings)

            # Convert file path to Python module path
            relative_path = best_settings.relative_to(project_root)
            module_parts = list(relative_path.parts[:-1])  # Remove filename

            # If settings is in a directory (like config/settings/), include it
            if best_settings.name != 'settings.py':
                # It's in a settings package (e.g., config/settings/base.py)
                module_parts.append('settings')
                # For split settings, we'll use the base module
                # User can override with specific environment (production, development)
                settings_module = '.'.join(module_parts)
            else:
                # Single settings.py file
                if module_parts:
                    settings_module = '.'.join(module_parts) + '.settings'
                else:
                    settings_module = 'settings'

            self.structure['settings_module'] = settings_module
            logger.info(f"Detected settings module: {settings_module}")

            # Check for split settings (development, production, etc.)
            if best_settings.parent.name == 'settings':
                # It's a settings package
                env_settings = list(best_settings.parent.glob('*.py'))
                env_names = [f.stem for f in env_settings if f.stem not in ['__init__', 'base']]
                if env_names:
                    self.structure['settings_environments'] = env_names
                    logger.info(f"Found environment settings: {', '.join(env_names)}")

    def _prioritize_settings(self, settings_files: List[Path], project_root: Path) -> Optional[Path]:
        """
        Choose the best settings file from multiple candidates.

        Args:
            settings_files: List of found settings files
            project_root: Project root path

        Returns:
            Best settings file path
        """
        if not settings_files:
            return None

        if len(settings_files) == 1:
            return settings_files[0]

        # Scoring system
        best_settings = None
        best_score = -1

        for settings_file in settings_files:
            score = 0
            relative_path = settings_file.relative_to(project_root)
            parts = list(relative_path.parts)

            # Prefer 'config' directory
            if 'config' in parts:
                score += 10

            # Prefer 'settings' directory with base.py
            if settings_file.name == 'base.py' and settings_file.parent.name == 'settings':
                score += 8

            # Prefer shorter paths (closer to root)
            score += max(0, 5 - len(parts))

            # Prefer if it has __init__.py in same directory (proper package)
            init_file = settings_file.parent / '__init__.py'
            if init_file.exists():
                score += 3

            if score > best_score:
                best_score = score
                best_settings = settings_file

        return best_settings

    def _detect_wsgi_asgi(self) -> None:
        """Detect WSGI and ASGI module locations."""
        if not self.structure['project_root']:
            return

        project_root = Path(self.structure['project_root'])
        excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}

        # Find ASGI files
        asgi_files = list(project_root.rglob('asgi.py'))
        valid_asgi = [
            f for f in asgi_files
            if not any(excluded in f.relative_to(project_root).parts for excluded in excluded_dirs)
        ]

        if valid_asgi:
            asgi_file = valid_asgi[0]
            relative_path = asgi_file.relative_to(project_root)
            module_parts = list(relative_path.with_suffix('').parts)
            asgi_module = '.'.join(module_parts) + ':application'
            self.structure['asgi_module'] = asgi_module
            logger.info(f"Detected ASGI module: {asgi_module}")

        # Find WSGI files
        wsgi_files = list(project_root.rglob('wsgi.py'))
        valid_wsgi = [
            f for f in wsgi_files
            if not any(excluded in f.relative_to(project_root).parts for excluded in excluded_dirs)
        ]

        if valid_wsgi:
            wsgi_file = valid_wsgi[0]
            relative_path = wsgi_file.relative_to(project_root)
            module_parts = list(relative_path.with_suffix('').parts)
            wsgi_module = '.'.join(module_parts) + ':application'
            self.structure['wsgi_module'] = wsgi_module
            logger.info(f"Detected WSGI module: {wsgi_module}")

    def _detect_requirements(self) -> None:
        """Detect requirements files."""
        if not self.structure['project_root']:
            # Check repo root as fallback
            search_paths = [self.repo_path]
        else:
            # Search both project root and repo root
            search_paths = [Path(self.structure['project_root']), self.repo_path]

        requirements_files = []

        for search_path in search_paths:
            # Standard requirements.txt
            req_file = search_path / 'requirements.txt'
            if req_file.exists():
                requirements_files.append({
                    'path': str(req_file),
                    'type': 'main',
                    'priority': 1
                })

            # Requirements directory (Django Cookiecutter pattern)
            req_dir = search_path / 'requirements'
            if req_dir.exists() and req_dir.is_dir():
                for req in ['base.txt', 'production.txt', 'local.txt', 'development.txt']:
                    req_path = req_dir / req
                    if req_path.exists():
                        requirements_files.append({
                            'path': str(req_path),
                            'type': req.replace('.txt', ''),
                            'priority': 0 if req == 'base.txt' else 2
                        })

        # Sort by priority (base.txt first)
        requirements_files.sort(key=lambda x: x['priority'])
        self.structure['requirements_files'] = requirements_files

        if requirements_files:
            logger.info(f"Found {len(requirements_files)} requirements file(s)")

    def _detect_project_type(self) -> None:
        """Detect overall project type."""
        if self.structure['is_django']:
            self.structure['project_type'] = 'django'

            # Check for Django REST Framework
            if self.structure['requirements_files']:
                req_file = self.structure['requirements_files'][0]['path']
                try:
                    with open(req_file, 'r') as f:
                        content = f.read().lower()
                        if 'djangorestframework' in content or 'rest_framework' in content:
                            self.structure['project_type'] = 'django_rest'
                except Exception:
                    pass

        # Check for other project types
        project_root = Path(self.structure['project_root']) if self.structure['project_root'] else self.repo_path

        # Check for FastAPI
        if (project_root / 'main.py').exists():
            try:
                with open(project_root / 'main.py', 'r') as f:
                    content = f.read()
                    if 'fastapi' in content.lower():
                        self.structure['project_type'] = 'fastapi'
            except Exception:
                pass

    def get_project_root(self) -> Optional[Path]:
        """Get the detected project root."""
        if self.structure.get('project_root'):
            return Path(self.structure['project_root'])
        return None

    def get_settings_module(self, environment: str = 'production') -> Optional[str]:
        """
        Get the settings module for a specific environment.

        Args:
            environment: Environment name (production, development, staging, etc.)

        Returns:
            Settings module path
        """
        base_module = self.structure.get('settings_module')
        if not base_module:
            return None

        # Check if split settings exist
        if 'settings_environments' in self.structure:
            env_names = self.structure['settings_environments']
            if environment in env_names:
                # Return environment-specific settings
                return f"{base_module}.{environment}"
            elif 'production' in env_names and environment == 'production':
                return f"{base_module}.production"
            elif 'base' in env_names:
                return f"{base_module}.base"

        return base_module

    def get_requirements_file(self, environment: str = 'production') -> Optional[str]:
        """
        Get the requirements file for a specific environment.

        Args:
            environment: Environment name

        Returns:
            Path to requirements file
        """
        req_files = self.structure.get('requirements_files', [])
        if not req_files:
            return None

        # Look for environment-specific requirements
        for req in req_files:
            if req['type'] == environment:
                return req['path']

        # Fallback to base or main requirements
        for req in req_files:
            if req['type'] in ['base', 'main']:
                return req['path']

        # Return the first one
        return req_files[0]['path']

    def to_dict(self) -> Dict[str, Any]:
        """Return structure as dictionary."""
        return self.structure

    def __repr__(self) -> str:
        """String representation."""
        return f"ProjectStructureDetector(repo={self.repo_path}, detected={self.structure.get('is_django', False)})"
