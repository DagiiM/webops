"""Generic Python buildpack (FastAPI, Flask, etc.)."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class PythonBuildpack(Buildpack):
    """Detect generic Python projects (FastAPI, Flask, etc.)."""

    name = 'python'
    display_name = 'Python'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Python project."""
        # Check for Python files
        py_files = self._find_files(repo_path, '*.py')
        if not py_files:
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='python', confidence=0.0)

        # Check for dependency files
        has_requirements = (repo_path / 'requirements.txt').exists()
        has_pyproject = (repo_path / 'pyproject.toml').exists()
        has_pipfile = (repo_path / 'Pipfile').exists()

        if not (has_requirements or has_pyproject or has_pipfile):
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='python', confidence=0.0)

        # Detect framework
        framework, confidence = self._detect_framework(repo_path)

        # Get commands
        dep_manager = self._detect_dependency_manager(repo_path)
        install_cmd = self._get_install_command(dep_manager, repo_path)
        start_cmd = self._get_start_command(framework, repo_path)

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='python',
            confidence=confidence,
            framework=framework,
            build_command='',  # Python apps usually don't need build step
            start_command=start_cmd,
            install_command=install_cmd,
            package_manager=dep_manager,
            port=8000,
            env_vars={'PYTHONUNBUFFERED': '1'},
            metadata={'has_requirements': has_requirements}
        )

    def _detect_framework(self, repo_path: Path) -> tuple[str, float]:
        """Detect Python web framework."""
        req_content = ''
        if (repo_path / 'requirements.txt').exists():
            req_content = self._read_file(repo_path / 'requirements.txt') or ''

        # FastAPI
        if 'fastapi' in req_content.lower():
            return 'fastapi', 0.90
        # Flask
        if 'flask' in req_content.lower():
            return 'flask', 0.90
        # Streamlit
        if 'streamlit' in req_content.lower():
            return 'streamlit', 0.90
        # Generic Python
        return 'python', 0.60

    def _detect_dependency_manager(self, repo_path: Path) -> str:
        """Detect dependency manager."""
        if (repo_path / 'poetry.lock').exists():
            return 'poetry'
        if (repo_path / 'Pipfile.lock').exists():
            return 'pipenv'
        return 'pip'

    def _get_install_command(self, dep_manager: str, repo_path: Path) -> str:
        """Get install command."""
        if dep_manager == 'poetry':
            return 'poetry install --no-dev'
        elif dep_manager == 'pipenv':
            return 'pipenv install --deploy'
        return 'pip install -r requirements.txt'

    def _get_start_command(self, framework: str, repo_path: Path) -> str:
        """Get start command."""
        if framework == 'fastapi':
            # Look for main.py or app.py
            if (repo_path / 'main.py').exists():
                return 'uvicorn main:app --host 0.0.0.0 --port $PORT'
            return 'uvicorn app:app --host 0.0.0.0 --port $PORT'
        elif framework == 'flask':
            return 'gunicorn app:app --bind 0.0.0.0:$PORT'
        elif framework == 'streamlit':
            return 'streamlit run app.py --server.port $PORT'
        return 'python main.py'
