"""Django buildpack detector."""

from pathlib import Path
from typing import Optional
from .base import Buildpack, BuildpackResult


class DjangoBuildpack(Buildpack):
    """Detect and configure Django projects."""

    name = 'django'
    display_name = 'Django'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Django project."""
        # Check for manage.py
        manage_py_files = self._find_files(repo_path, 'manage.py')

        if not manage_py_files:
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='django',
                confidence=0.0
            )

        # Check for requirements.txt with Django
        has_django_in_requirements = self._check_django_in_requirements(repo_path)

        if not has_django_in_requirements:
            # Might be Poetry or Pipenv
            if not self._file_exists(repo_path, 'pyproject.toml', 'Pipfile'):
                # No Python dependency file found
                return BuildpackResult(
                    detected=False,
                    buildpack_name=self.name,
                    project_type='django',
                    confidence=0.0
                )

        # Detect Django features
        has_drf = self._check_django_rest_framework(repo_path)
        has_channels = self._check_django_channels(repo_path)
        has_celery = self._check_celery(repo_path)

        # Detect Python version
        python_version = self._detect_python_version(repo_path)

        # Determine framework variant
        framework = 'django'
        if has_drf:
            framework = 'django-rest-framework'
        elif has_channels:
            framework = 'django-channels'

        # Get dependency manager
        dep_manager = self._detect_dependency_manager(repo_path)

        # Build install command
        install_cmd = self._get_install_command(dep_manager, repo_path)

        # Django typically needs these steps
        build_cmd = self._get_build_command()
        start_cmd = self._get_start_command(has_channels)

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='django',
            confidence=0.95,
            framework=framework,
            version=python_version,
            build_command=build_cmd,
            start_command=start_cmd,
            install_command=install_cmd,
            package_manager=dep_manager,
            port=8000,
            env_vars={
                'DJANGO_SETTINGS_MODULE': '',  # Will be auto-detected
                'PYTHONUNBUFFERED': '1',
                'PYTHONDONTWRITEBYTECODE': '1',
            },
            metadata={
                'has_drf': has_drf,
                'has_channels': has_channels,
                'has_celery': has_celery,
                'manage_py_path': str(manage_py_files[0]),
            }
        )

    def _check_django_in_requirements(self, repo_path: Path) -> bool:
        """Check if Django is in requirements files."""
        req_files = [
            'requirements.txt',
            'requirements/base.txt',
            'requirements/production.txt',
        ]

        for req_file in req_files:
            path = repo_path / req_file
            if path.exists():
                content = self._read_file(path)
                if content and 'django' in content.lower():
                    return True

        return False

    def _check_django_rest_framework(self, repo_path: Path) -> bool:
        """Check for Django REST Framework."""
        req_files = self._find_files(repo_path, 'requirements*.txt')

        for req_file in req_files:
            content = self._read_file(req_file)
            if content and ('djangorestframework' in content.lower() or 'rest_framework' in content.lower()):
                return True

        return False

    def _check_django_channels(self, repo_path: Path) -> bool:
        """Check for Django Channels."""
        req_files = self._find_files(repo_path, 'requirements*.txt')

        for req_file in req_files:
            content = self._read_file(req_file)
            if content and 'channels' in content.lower():
                return True

        return False

    def _check_celery(self, repo_path: Path) -> bool:
        """Check for Celery."""
        req_files = self._find_files(repo_path, 'requirements*.txt')

        for req_file in req_files:
            content = self._read_file(req_file)
            if content and 'celery' in content.lower():
                return True

        return False

    def _detect_python_version(self, repo_path: Path) -> str:
        """Detect Python version from runtime.txt or pyproject.toml."""
        # Check runtime.txt (Heroku style)
        runtime_txt = repo_path / 'runtime.txt'
        if runtime_txt.exists():
            content = self._read_file(runtime_txt)
            if content:
                # Format: python-3.11.0
                version = content.strip().replace('python-', '')
                return version

        # Check pyproject.toml
        pyproject = repo_path / 'pyproject.toml'
        if pyproject.exists():
            content = self._read_file(pyproject)
            if content and 'python' in content:
                # Try to extract version
                import re
                match = re.search(r'python\s*=\s*["\'][\^~>=<]*(\d+\.\d+)', content)
                if match:
                    return match.group(1)

        # Default to Python 3.11
        return '3.11'

    def _detect_dependency_manager(self, repo_path: Path) -> str:
        """Detect Python dependency manager."""
        if (repo_path / 'poetry.lock').exists():
            return 'poetry'
        if (repo_path / 'Pipfile.lock').exists():
            return 'pipenv'
        if (repo_path / 'pdm.lock').exists():
            return 'pdm'
        return 'pip'

    def _get_install_command(self, dep_manager: str, repo_path: Path) -> str:
        """Get install command based on dependency manager."""
        if dep_manager == 'poetry':
            return 'poetry install --no-dev'
        elif dep_manager == 'pipenv':
            return 'pipenv install --deploy'
        elif dep_manager == 'pdm':
            return 'pdm install --prod'
        else:  # pip
            # Find requirements file
            if (repo_path / 'requirements.txt').exists():
                return 'pip install -r requirements.txt'
            elif (repo_path / 'requirements' / 'production.txt').exists():
                return 'pip install -r requirements/production.txt'
            elif (repo_path / 'requirements' / 'base.txt').exists():
                return 'pip install -r requirements/base.txt'
            else:
                return 'pip install -r requirements.txt'

    def _get_build_command(self) -> str:
        """Get build command for Django."""
        # Django build steps (will be run by deployment service)
        # We don't include migrations here as they're handled separately
        return 'python manage.py collectstatic --noinput'

    def _get_start_command(self, has_channels: bool) -> str:
        """Get start command for Django."""
        if has_channels:
            # Use Daphne for ASGI/Channels
            return 'daphne -b 0.0.0.0 -p $PORT ${DJANGO_SETTINGS_MODULE%.*}.asgi:application'
        else:
            # Use Gunicorn for WSGI
            return 'gunicorn ${DJANGO_SETTINGS_MODULE%.*}.wsgi:application --bind 0.0.0.0:$PORT --workers 4'
