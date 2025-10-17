"""
Deployment service for WebOps.

Reference: CLAUDE.md "Business Logic" section
Architecture: PROPOSAL.md section 5.1 "Deployment Workflow"

This module implements the core deployment logic:
- Repository cloning
- Project type detection
- Virtual environment creation
- Dependency installation
- Service configuration
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple
from django.conf import settings
from git import Repo, GitCommandError
from jinja2 import Environment, FileSystemLoader
import logging

from apps.core.utils import generate_port, validate_repo_url, generate_secret_key
from .models import Deployment, DeploymentLog
from .validators import validate_project

logger = logging.getLogger(__name__)


class DeploymentService:
    """Service for managing application deployments."""

    def __init__(self):
        self.base_path = Path(settings.WEBOPS_INSTALL_PATH) / "deployments"

        # Set up Jinja2 for template rendering
        template_path = Path(__file__).parent.parent.parent.parent / "system-templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_path)))

    def ensure_base_path(self) -> bool:
        """
        Ensure base deployment path exists.

        Returns:
            True if path exists or was created successfully, False otherwise
        """
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            return True
        except PermissionError:
            logger.error(
                f"Permission denied creating {self.base_path}. "
                f"Run 'sudo python manage.py init_webops_dirs' or update "
                f"WEBOPS_INSTALL_PATH in .env to a writable location."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to create base path {self.base_path}: {e}")
            return False

    def get_deployment_path(self, deployment: Deployment) -> Path:
        """Get the file system path for a deployment."""
        self.ensure_base_path()
        return self.base_path / deployment.name

    def get_repo_path(self, deployment: Deployment) -> Path:
        """Get the repository path for a deployment."""
        return self.get_deployment_path(deployment) / "repo"

    def get_venv_path(self, deployment: Deployment) -> Path:
        """Get the virtual environment path for a deployment."""
        return self.get_deployment_path(deployment) / "venv"

    def log(
        self,
        deployment: Deployment,
        message: str,
        level: str = DeploymentLog.Level.INFO
    ) -> None:
        """
        Log a deployment message.

        Args:
            deployment: Deployment instance
            message: Log message
            level: Log level (info, warning, error, success)
        """
        DeploymentLog.objects.create(
            deployment=deployment,
            level=level,
            message=message
        )
        logger.info(f"[{deployment.name}] {message}")

    def validate_repo_url(self, repo_url: str) -> bool:
        """
        Validate repository URL.

        Args:
            repo_url: Repository URL to validate

        Returns:
            True if valid, False otherwise
        """
        return validate_repo_url(repo_url)

    def get_used_ports(self) -> Set[int]:
        """
        Get all currently used ports.

        Returns:
            Set of port numbers in use
        """
        return set(
            Deployment.objects
            .exclude(port__isnull=True)
            .values_list('port', flat=True)
        )

    def allocate_port(self, deployment: Deployment) -> int:
        """
        Allocate a port for a deployment.

        Args:
            deployment: Deployment instance

        Returns:
            Allocated port number

        Raises:
            ValueError: If no ports available
        """
        if deployment.port:
            return deployment.port

        used_ports = self.get_used_ports()
        port = generate_port(used_ports)
        deployment.port = port
        deployment.save(update_fields=['port'])

        self.log(deployment, f"Allocated port: {port}")
        return port

    def clone_repository(
        self,
        deployment: Deployment,
        force: bool = False
    ) -> Path:
        """
        Clone Git repository with improved error handling.

        Args:
            deployment: Deployment instance
            force: If True, remove existing repo first

        Returns:
            Path to cloned repository

        Raises:
            GitCommandError: If cloning fails
        """
        # Ensure base directory exists
        if not self.ensure_base_path():
            raise PermissionError(
                f"Cannot create deployment directory at {self.base_path}. "
                "Check permissions or update WEBOPS_INSTALL_PATH in .env"
            )

        repo_path = self.get_repo_path(deployment)

        # Remove existing repo if force is True
        if force and repo_path.exists():
            self.log(deployment, f"Removing existing repository at {repo_path}")
            shutil.rmtree(repo_path)

        # Clone repository
        if not repo_path.exists():
            self.log(deployment, f"Cloning repository: {deployment.repo_url}")
            
            # Handle private repositories that might need authentication
            repo_url = deployment.repo_url
            if repo_url.startswith('https://github.com/') and not repo_url.endswith('.git'):
                repo_url += '.git'
            
            try:
                # For public repositories, try HTTPS first
                repo = Repo.clone_from(
                    repo_url,
                    repo_path,
                    branch=deployment.branch,
                    depth=1  # Shallow clone for faster cloning
                )
                self.log(
                    deployment,
                    f"Repository cloned successfully (branch: {deployment.branch})",
                    DeploymentLog.Level.SUCCESS
                )
                return repo_path
                
            except GitCommandError as e:
                error_msg = str(e)
                
                # Handle common errors with helpful messages
                if "could not read Username" in error_msg:
                    self.log(
                        deployment,
                        "Repository appears to be private or requires authentication. "
                        "For private repos, ensure you've added a GitHub token in settings.",
                        DeploymentLog.Level.ERROR
                    )
                elif "Repository not found" in error_msg:
                    self.log(
                        deployment,
                        "Repository not found. Check the URL is correct and the repository is public.",
                        DeploymentLog.Level.ERROR
                    )
                elif "branch" in error_msg.lower() and deployment.branch not in ['main', 'master']:
                    self.log(
                        deployment,
                        f"Branch '{deployment.branch}' not found. Trying 'main' branch instead.",
                        DeploymentLog.Level.WARNING
                    )
                    try:
                        repo = Repo.clone_from(repo_url, repo_path, branch='main', depth=1)
                        deployment.branch = 'main'
                        deployment.save(update_fields=['branch'])
                        self.log(
                            deployment,
                            "Repository cloned successfully using 'main' branch",
                            DeploymentLog.Level.SUCCESS
                        )
                        return repo_path
                    except GitCommandError:
                        self.log(
                            deployment,
                            f"Branch 'main' also not found. Trying 'master' branch.",
                            DeploymentLog.Level.WARNING
                        )
                        try:
                            repo = Repo.clone_from(repo_url, repo_path, branch='master', depth=1)
                            deployment.branch = 'master'
                            deployment.save(update_fields=['branch'])
                            self.log(
                                deployment,
                                "Repository cloned successfully using 'master' branch",
                                DeploymentLog.Level.SUCCESS
                            )
                            return repo_path
                        except GitCommandError as final_error:
                            self.log(
                                deployment,
                                f"Failed to clone repository with any branch: {final_error}",
                                DeploymentLog.Level.ERROR
                            )
                            raise final_error
                else:
                    self.log(
                        deployment,
                        f"Failed to clone repository: {error_msg}",
                        DeploymentLog.Level.ERROR
                    )
                    raise e
        else:
            self.log(deployment, "Repository already exists, pulling latest changes")
            try:
                repo = Repo(repo_path)
                origin = repo.remotes.origin
                origin.pull()
                self.log(
                    deployment,
                    "Repository updated successfully",
                    DeploymentLog.Level.SUCCESS
                )
                return repo_path
            except GitCommandError as e:
                self.log(
                    deployment,
                    f"Failed to update repository: {e}",
                    DeploymentLog.Level.ERROR
                )
                raise

    def detect_project_type(self, deployment: Deployment) -> str:
        """
        Detect project type (Django or static site).

        Args:
            deployment: Deployment instance

        Returns:
            Project type ('django' or 'static')
        """
        repo_path = self.get_repo_path(deployment)

        # Check for Django project - multiple indicators
        manage_py = repo_path / "manage.py"
        settings_py_patterns = [
            repo_path / "settings.py",
            repo_path / "*/settings.py",
            repo_path / "config/settings.py",
            repo_path / "**/settings/*.py"
        ]
        
        # Check requirements.txt for Django
        requirements_file = repo_path / "requirements.txt"
        has_django_in_requirements = False
        
        if requirements_file.exists():
            try:
                content = requirements_file.read_text()
                has_django_in_requirements = 'django' in content.lower()
            except:
                pass

        if manage_py.exists() or has_django_in_requirements:
            # Additional validation for Django structure
            import glob
            settings_files = glob.glob(str(repo_path / "**/settings.py"), recursive=True)
            if settings_files or has_django_in_requirements:
                self.log(deployment, "Detected Django project")
                return Deployment.ProjectType.DJANGO

        # Check for static site indicators
        static_files = [
            repo_path / "index.html",
            repo_path / "index.htm",
            repo_path / "public/index.html",
            repo_path / "dist/index.html",
            repo_path / "build/index.html"
        ]
        
        for static_file in static_files:
            if static_file.exists():
                self.log(deployment, f"Detected static site ({static_file.name} found)")
                return Deployment.ProjectType.STATIC

        # Check if it's a Django project without manage.py (some tutorials)
        wsgi_files = list(repo_path.glob("**/wsgi.py"))
        asgi_files = list(repo_path.glob("**/asgi.py"))
        
        if wsgi_files or asgi_files:
            self.log(deployment, "Detected Django project (WSGI/ASGI files found)")
            return Deployment.ProjectType.DJANGO

        # Default to Django for repositories with Python files and no clear static indicators
        python_files = list(repo_path.glob("**/*.py"))
        if python_files and not any(static_file.exists() for static_file in static_files):
            self.log(
                deployment,
                "Detected Python files, defaulting to Django project type",
                DeploymentLog.Level.WARNING
            )
            return Deployment.ProjectType.DJANGO

        # Final fallback to static
        self.log(
            deployment,
            "Could not determine project type, defaulting to static site",
            DeploymentLog.Level.WARNING
        )
        return Deployment.ProjectType.STATIC

    def create_virtualenv(self, deployment: Deployment) -> Path:
        """
        Create Python virtual environment.

        Args:
            deployment: Deployment instance

        Returns:
            Path to virtual environment

        Raises:
            subprocess.CalledProcessError: If venv creation fails
        """
        # Ensure deployment directory exists
        deployment_path = self.get_deployment_path(deployment)
        deployment_path.mkdir(parents=True, exist_ok=True)

        venv_path = self.get_venv_path(deployment)

        if venv_path.exists():
            self.log(deployment, "Virtual environment already exists")
            return venv_path

        self.log(deployment, "Creating virtual environment")
        try:
            subprocess.run(
                ["python3", "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True
            )
            self.log(
                deployment,
                "Virtual environment created successfully",
                DeploymentLog.Level.SUCCESS
            )
            return venv_path
        except subprocess.CalledProcessError as e:
            self.log(
                deployment,
                f"Failed to create virtual environment: {e.stderr}",
                DeploymentLog.Level.ERROR
            )
            raise

    def install_dependencies(self, deployment: Deployment) -> bool:
        """
        Install Python dependencies from requirements.txt.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful, False otherwise
        """
        repo_path = self.get_repo_path(deployment)
        venv_path = self.get_venv_path(deployment)
        requirements_file = repo_path / "requirements.txt"

        if not requirements_file.exists():
            self.log(
                deployment,
                "No requirements.txt found, skipping dependency installation",
                DeploymentLog.Level.WARNING
            )
            return True

        pip_path = venv_path / "bin" / "pip"
        self.log(deployment, "Upgrading pip first")
        
        # Upgrade pip first
        try:
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=300
            )
        except subprocess.CalledProcessError as e:
            self.log(
                deployment,
                f"Failed to upgrade pip: {e.stderr}",
                DeploymentLog.Level.WARNING
            )

        self.log(deployment, "Installing dependencies from requirements.txt")

        try:
            # Install with better error handling and timeout
            result = subprocess.run(
                [str(pip_path), "install", "-r", str(requirements_file), "--no-cache-dir"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(repo_path),
                timeout=600  # 10 minute timeout
            )
            self.log(
                deployment,
                "Dependencies installed successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True
        except subprocess.TimeoutExpired:
            self.log(
                deployment,
                "Dependency installation timed out after 10 minutes",
                DeploymentLog.Level.ERROR
            )
            return False
        except subprocess.CalledProcessError as e:
            # Try to provide more helpful error messages
            error_msg = e.stderr.strip()
            
            if "libpq-fe.h" in error_msg:
                self.log(
                    deployment,
                    "PostgreSQL development headers missing. Run: sudo apt-get install libpq-dev",
                    DeploymentLog.Level.ERROR
                )
            elif "psycopg2" in error_msg:
                self.log(
                    deployment,
                    "Trying to install psycopg2-binary instead of psycopg2",
                    DeploymentLog.Level.WARNING
                )
                # Try installing psycopg2-binary as fallback
                try:
                    subprocess.run(
                        [str(pip_path), "install", "psycopg2-binary", "--no-cache-dir"],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    self.log(deployment, "Installed psycopg2-binary successfully", DeploymentLog.Level.SUCCESS)
                    return True
                except:
                    pass
            
            self.log(
                deployment,
                f"Failed to install dependencies: {error_msg}",
                DeploymentLog.Level.ERROR
            )
            return False

    def setup_django_environment(self, deployment: Deployment) -> bool:
        """
        Set up Django environment variables and configuration.

        Uses intelligent .env.example parsing to automatically generate
        appropriate values for all environment variables.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful, False otherwise
        """
        repo_path = self.get_repo_path(deployment)
        env_file_path = repo_path / ".env"

        # If .env already exists, keep it (don't overwrite user modifications)
        if env_file_path.exists():
            self.log(
                deployment,
                ".env file already exists, skipping generation",
                DeploymentLog.Level.INFO
            )
            return True

        self.log(deployment, "Setting up Django environment")

        # Generate database credentials
        from apps.databases.models import Database
        from apps.core.utils import generate_password, encrypt_password
        from apps.core.env_manager import EnvManager

        db_password = generate_password()
        db_name = f"{deployment.name}_db".replace('-', '_')

        # Create database entry
        try:
            database = Database.objects.create(
                deployment=deployment,
                name=db_name,
                username=deployment.name,
                password=encrypt_password(db_password),
                host='localhost',
                port=5432
            )
            self.log(deployment, f"Database created: {db_name}")
        except Exception as e:
            self.log(
                deployment,
                f"Failed to create database entry: {e}",
                DeploymentLog.Level.WARNING
            )
            # Use defaults
            db_password = "defaultpass"

        # Prepare database info for env manager
        database_info = {
            'db_name': db_name,
            'db_user': deployment.name,
            'db_password': db_password,
            'db_host': 'localhost',
            'db_port': '5432'
        }

        # Try to use intelligent env management
        try:
            self.log(deployment, "Looking for .env.example file")

            # Process .env.example with intelligent value generation
            success, message = EnvManager.process_env_file(
                repo_path=repo_path,
                deployment_name=deployment.name,
                domain=deployment.domain if deployment.domain else f"{deployment.name}.localhost",
                database_info=database_info,
                redis_url="redis://localhost:6379/0",
                debug=False,
                custom_values=deployment.env_vars if deployment.env_vars else None
            )

            if success:
                self.log(
                    deployment,
                    f"Environment file generated from .env.example: {message}",
                    DeploymentLog.Level.SUCCESS
                )
                return True
            else:
                self.log(
                    deployment,
                    f".env.example processing: {message}",
                    DeploymentLog.Level.WARNING
                )
                # Fall back to manual creation

        except Exception as e:
            self.log(
                deployment,
                f"Error using EnvManager: {e}",
                DeploymentLog.Level.WARNING
            )
            # Fall back to manual creation

        # Fallback: Create basic .env file manually
        self.log(deployment, "Creating basic .env file (no .env.example found)")

        env_content = f"""# WebOps Generated Environment File
# Generated automatically on {deployment.created_at.strftime('%Y-%m-%d %H:%M:%S')}

# Django Core Settings
DEBUG=False
SECRET_KEY={generate_secret_key()}
ALLOWED_HOSTS=localhost,127.0.0.1,{deployment.domain if deployment.domain else '*'}

# Database Configuration
DATABASE_URL=postgresql://{deployment.name}:{db_password}@localhost:5432/{db_name}

# Redis/Cache Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Application Settings
PORT={deployment.port}
"""

        # Add any custom env vars from deployment
        if deployment.env_vars:
            env_content += "\n# Custom Environment Variables\n"
            for key, value in deployment.env_vars.items():
                env_content += f"{key}={value}\n"

        try:
            env_file_path.write_text(env_content)
            # Secure the file
            env_file_path.chmod(0o600)
            self.log(deployment, ".env file created successfully")
            return True
        except Exception as e:
            self.log(
                deployment,
                f"Failed to create .env file: {e}",
                DeploymentLog.Level.ERROR
            )
            return False

    def detect_django_settings_module(self, deployment: Deployment) -> str:
        """
        Intelligently detect the correct Django settings module path.
        
        Args:
            deployment: Deployment instance
            
        Returns:
            The Django settings module path (e.g., 'myproject.settings')
        """
        repo_path = self.get_repo_path(deployment)
        
        # Find all settings.py files
        settings_files = list(repo_path.rglob("settings.py"))
        
        if not settings_files:
            self.log(
                deployment,
                "No settings.py files found in project",
                DeploymentLog.Level.WARNING
            )
            return "settings"  # Fallback
        
        # Filter out settings files in migrations, tests, or venv directories
        valid_settings = []
        for settings_file in settings_files:
            relative_path = settings_file.relative_to(repo_path)
            path_parts = relative_path.parts
            
            # Skip if in excluded directories
            excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
            if any(part in excluded_dirs for part in path_parts):
                continue
                
            valid_settings.append(settings_file)
        
        if not valid_settings:
            self.log(
                deployment,
                "No valid settings.py files found (excluding migrations/tests/venv)",
                DeploymentLog.Level.WARNING
            )
            return "settings"
        
        # Prioritize settings files based on common Django patterns
        best_settings = None
        best_score = -1
        
        for settings_file in valid_settings:
            relative_path = settings_file.relative_to(repo_path)
            path_parts = relative_path.parts[:-1]  # Exclude 'settings.py' filename
            
            score = 0
            
            # Higher score for common Django project structure patterns
            if 'config' in path_parts:
                score += 10
            elif deployment.name in path_parts:
                score += 8
            elif 'core' in path_parts:
                score += 6
            elif 'project' in path_parts:
                score += 5
            elif len(path_parts) == 1:  # Direct subdirectory of repo
                score += 4
            
            # Prefer shorter paths (closer to root)
            score += max(0, 5 - len(path_parts))
            
            # Check if there's an __init__.py in the same directory (proper Python package)
            init_file = settings_file.parent / "__init__.py"
            if init_file.exists():
                score += 3
            
            if score > best_score:
                best_score = score
                best_settings = settings_file
        
        if best_settings:
            # Convert file path to Python module path
            relative_path = best_settings.relative_to(repo_path)
            module_parts = relative_path.parts[:-1]  # Remove 'settings.py'
            
            if module_parts:
                module_path = '.'.join(module_parts) + '.settings'
            else:
                module_path = 'settings'
            
            self.log(
                deployment,
                f"Detected Django settings module: {module_path}",
                DeploymentLog.Level.INFO
            )
            return module_path
        
        # Final fallback
        return "settings"

    def run_django_migrations(self, deployment: Deployment) -> bool:
        """
        Run Django migrations with improved error handling.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful, False otherwise
        """
        repo_path = self.get_repo_path(deployment)
        venv_path = self.get_venv_path(deployment)
        python_path = venv_path / "bin" / "python"

        # Set up environment first
        if not self.setup_django_environment(deployment):
            return False

        self.log(deployment, "Running Django migrations")

        # Use smart settings detection
        settings_module = self.detect_django_settings_module(deployment)

        # Enhanced environment variables
        env = {
            **os.environ,
            "PYTHONPATH": str(repo_path),
            "DJANGO_SETTINGS_MODULE": settings_module,
        }

        try:
            result = subprocess.run(
                [str(python_path), "manage.py", "migrate", "--noinput"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(repo_path),
                env=env,
                timeout=300  # 5 minute timeout
            )
            self.log(
                deployment,
                "Migrations completed successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True
        except subprocess.TimeoutExpired:
            self.log(
                deployment,
                "Migration timed out after 5 minutes",
                DeploymentLog.Level.ERROR
            )
            return False
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()
            
            # Handle common Django setup errors
            if "ModuleNotFoundError" in error_msg and "settings" in error_msg.lower():
                self.log(
                    deployment,
                    f"Django settings module '{settings_module}' not found. Trying fallback patterns.",
                    DeploymentLog.Level.WARNING
                )
                
                # Try common alternative settings patterns as fallback
                alt_settings = [
                    "settings",
                    f"{deployment.name}.settings",
                    "config.settings",
                    "core.settings",
                    "mysite.settings"
                ]
                
                # Remove the already tried settings module from alternatives
                if settings_module in alt_settings:
                    alt_settings.remove(settings_module)
                
                for alt_setting in alt_settings:
                    try:
                        self.log(
                            deployment,
                            f"Trying alternative settings module: {alt_setting}",
                            DeploymentLog.Level.INFO
                        )
                        alt_env = {**env, "DJANGO_SETTINGS_MODULE": alt_setting}
                        subprocess.run(
                            [str(python_path), "manage.py", "migrate", "--noinput"],
                            check=True,
                            capture_output=True,
                            text=True,
                            cwd=str(repo_path),
                            env=alt_env,
                            timeout=300
                        )
                        self.log(
                            deployment,
                            f"Migrations completed with settings: {alt_setting}",
                            DeploymentLog.Level.SUCCESS
                        )
                        return True
                    except subprocess.CalledProcessError as alt_e:
                        self.log(
                            deployment,
                            f"Failed with {alt_setting}: {alt_e.stderr.strip() if alt_e.stderr else 'Unknown error'}",
                            DeploymentLog.Level.DEBUG
                        )
                        continue
                
                self.log(
                    deployment,
                    "Could not find valid Django settings module after trying all patterns",
                    DeploymentLog.Level.ERROR
                )
            elif "ModuleNotFoundError" in error_msg:
                self.log(
                    deployment,
                    f"Missing Python module: {error_msg}",
                    DeploymentLog.Level.ERROR
                )
            elif "DATABASES" in error_msg or "database" in error_msg.lower():
                self.log(
                    deployment,
                    "Database configuration error. Check Django settings and database connectivity.",
                    DeploymentLog.Level.ERROR
                )
            else:
                self.log(
                    deployment,
                    f"Migration failed: {error_msg}",
                    DeploymentLog.Level.ERROR
                )
            return False

    def collect_static_files(self, deployment: Deployment) -> bool:
        """
        Collect Django static files.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful, False otherwise
        """
        repo_path = self.get_repo_path(deployment)
        venv_path = self.get_venv_path(deployment)
        python_path = venv_path / "bin" / "python"

        self.log(deployment, "Collecting static files")

        try:
            result = subprocess.run(
                [str(python_path), "manage.py", "collectstatic", "--noinput"],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(repo_path),
                env={**os.environ, "PYTHONPATH": str(repo_path)}
            )
            self.log(
                deployment,
                "Static files collected successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True
        except subprocess.CalledProcessError as e:
            self.log(
                deployment,
                f"Static file collection failed: {e.stderr}",
                DeploymentLog.Level.WARNING
            )
            # Not a critical error, continue anyway
            return True

    def render_nginx_config(self, deployment: Deployment) -> str:
        """
        Render Nginx configuration from template.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered Nginx configuration
        """
        repo_path = self.get_repo_path(deployment)
        template = self.jinja_env.get_template('nginx/app.conf.j2')

        context = {
            'app_name': deployment.name,
            'domain': deployment.domain,
            'port': deployment.port,
            'project_type': deployment.project_type,
            'repo_path': str(repo_path),
            'static_root': str(repo_path / 'staticfiles'),
            'media_root': str(repo_path / 'media'),
            'csp': (deployment.env_vars or {}).get('CSP')
        }

        return template.render(**context)

    def render_systemd_service(self, deployment: Deployment) -> str:
        """
        Render systemd service file from template.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered systemd service configuration
        """
        repo_path = self.get_repo_path(deployment)
        venv_path = self.get_venv_path(deployment)
        template = self.jinja_env.get_template('systemd/app.service.j2')

        # Detect ASGI/WSGI module paths
        excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}

        def _find_module(filename: str):
            files = list(repo_path.rglob(filename))
            valid = [f for f in files if not any(part in excluded_dirs for part in f.relative_to(repo_path).parts)]
            if not valid:
                return None
            rel = valid[0].relative_to(repo_path)
            dotted = ".".join(rel.with_suffix('').parts)
            return f"{dotted}:application"

        asgi_module = _find_module('asgi.py')
        wsgi_module = _find_module('wsgi.py')

        is_asgi = asgi_module is not None
        app_module = asgi_module if is_asgi else (wsgi_module or f"{deployment.name}.wsgi:application")
        worker_class = 'uvicorn.workers.UvicornWorker' if is_asgi else None
        extra_gunicorn_args = f"--worker-class {worker_class}" if worker_class else ""

        if is_asgi:
            self.log(deployment, f"ASGI module detected: {asgi_module}. Using UvicornWorker.")
        else:
            self.log(deployment, f"ASGI module not found. Using WSGI: {app_module}")

        context = {
            'app_name': deployment.name,
            'webops_user': settings.WEBOPS_USER,
            'repo_path': str(repo_path),
            'venv_path': str(venv_path),
            'port': deployment.port,
            'workers': 2,
            'app_module': app_module,
            'extra_gunicorn_args': extra_gunicorn_args,
            'log_path': str(self.get_deployment_path(deployment) / 'logs'),
            'env_vars': deployment.env_vars or {},
        }

        return template.render(**context)

    def create_nginx_config(self, deployment: Deployment) -> tuple[bool, str]:
        """
        Create Nginx configuration file.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, path or error message)
        """
        nginx_config = self.render_nginx_config(deployment)
        config_path = Path(f"/etc/nginx/sites-available/{deployment.name}")

        try:
            # Write config file (requires sudo in production)
            config_path.write_text(nginx_config)

            # Create symlink to sites-enabled
            enabled_path = Path(f"/etc/nginx/sites-enabled/{deployment.name}")
            if not enabled_path.exists():
                enabled_path.symlink_to(config_path)

            self.log(
                deployment,
                f"Nginx configuration created: {config_path}",
                DeploymentLog.Level.SUCCESS
            )
            return True, str(config_path)

        except PermissionError:
            error_msg = "Permission denied: requires sudo for Nginx config"
            self.log(deployment, error_msg, DeploymentLog.Level.WARNING)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to create Nginx config: {e}"
            self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def create_systemd_service(self, deployment: Deployment) -> tuple[bool, str]:
        """
        Create systemd service file.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, path or error message)
        """
        service_config = self.render_systemd_service(deployment)
        service_path = Path(f"/etc/systemd/system/{deployment.name}.service")

        try:
            # Write service file (requires sudo in production)
            service_path.write_text(service_config)

            # Reload systemd
            subprocess.run(
                ["sudo", "systemctl", "daemon-reload"],
                check=True,
                capture_output=True
            )

            self.log(
                deployment,
                f"Systemd service created: {service_path}",
                DeploymentLog.Level.SUCCESS
            )
            return True, str(service_path)

        except PermissionError:
            error_msg = "Permission denied: requires sudo for systemd service"
            self.log(deployment, error_msg, DeploymentLog.Level.WARNING)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to create systemd service: {e}"
            self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def prepare_deployment(self, deployment: Deployment) -> Tuple[bool, str]:
        """
        Prepare deployment (clone repo, install deps, etc.).

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Trigger pre-deployment hooks
            try:
                from apps.addons.manager import addon_manager, HookContext
                ctx = HookContext(
                    event='pre_deployment',
                    deployment_id=deployment.id,
                    deployment_name=deployment.name,
                    project_type=deployment.project_type,
                    metadata={'repo_url': deployment.repo_url, 'branch': deployment.branch},
                )
                addon_manager.trigger('pre_deployment', ctx, fail_fast=False)
            except Exception:
                pass

            # Update status
            deployment.status = Deployment.Status.BUILDING
            deployment.save(update_fields=['status'])

            # Clone repository
            repo_path = self.clone_repository(deployment)

            # Detect project type
            project_type = self.detect_project_type(deployment)
            if deployment.project_type != project_type:
                deployment.project_type = project_type
                deployment.save(update_fields=['project_type'])

            # Allocate port
            self.allocate_port(deployment)

            # For Django projects
            if deployment.project_type == Deployment.ProjectType.DJANGO:
                # Create virtual environment
                self.create_virtualenv(deployment)

                # Install dependencies
                if not self.install_dependencies(deployment):
                    return False, "Failed to install dependencies"

                # Run migrations
                if not self.run_django_migrations(deployment):
                    return False, "Failed to run migrations"

                # Collect static files
                self.collect_static_files(deployment)

            self.log(
                deployment,
                "Deployment prepared successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, ""

        except Exception as e:
            error_msg = f"Deployment preparation failed: {str(e)}"
            self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])
            return False, error_msg

    def deploy(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Complete deployment process.

        Args:
            deployment: Deployment instance

        Returns:
            Dictionary with deployment result
        """
        from .service_manager import ServiceManager

        self.log(deployment, "Starting deployment process")

        # Prepare deployment
        success, error = self.prepare_deployment(deployment)

        if not success:
            return {
                'success': False,
                'error': error,
                'deployment_id': deployment.id
            }

        # Run project validation before creating services
        try:
            repo_path = self.get_repo_path(deployment)
            all_passed, results = validate_project(repo_path)

            # Log all validation results
            for r in results:
                log_level = (
                    DeploymentLog.Level.ERROR if r.level == 'error' else
                    DeploymentLog.Level.WARNING if r.level == 'warning' else
                    DeploymentLog.Level.INFO
                )
                self.log(deployment, f"[validation] {r.message}", log_level)

            if not all_passed:
                self.log(
                    deployment,
                    "Project validation failed; aborting service creation",
                    DeploymentLog.Level.ERROR
                )
                deployment.status = Deployment.Status.FAILED
                deployment.save(update_fields=['status'])
                return {
                    'success': False,
                    'error': 'Project validation failed. Fix errors and retry.',
                    'deployment_id': deployment.id
                }
        except Exception as e:
            # If validation unexpectedly errors, log and continue (non-blocking)
            self.log(deployment, f"Validation step encountered an error: {e}", DeploymentLog.Level.WARNING)

        # Create service manager
        service_manager = ServiceManager()

        # For Django projects, create and start services
        if deployment.project_type == Deployment.ProjectType.DJANGO:
            # Create Nginx configuration
            self.log(deployment, "Creating Nginx configuration")
            nginx_config = self.render_nginx_config(deployment)
            nginx_success, nginx_msg = service_manager.install_nginx_config(
                deployment,
                nginx_config
            )

            if not nginx_success:
                self.log(
                    deployment,
                    f"Nginx config creation skipped (dev mode): {nginx_msg}",
                    DeploymentLog.Level.WARNING
                )
            else:
                # Reload Nginx
                service_manager.reload_nginx(deployment)

            # Create systemd service
            self.log(deployment, "Creating systemd service")
            service_config = self.render_systemd_service(deployment)
            service_success, service_msg = service_manager.install_service(
                deployment,
                service_config
            )

            if not service_success:
                self.log(
                    deployment,
                    f"Service creation skipped (dev mode): {service_msg}",
                    DeploymentLog.Level.WARNING
                )
                # In dev mode, mark as pending
                deployment.status = Deployment.Status.PENDING
                deployment.save(update_fields=['status'])

                # Trigger post-deployment hooks even in pending dev mode
                try:
                    from apps.addons.manager import addon_manager, HookContext
                    ctx = HookContext(
                        event='post_deployment',
                        deployment_id=deployment.id,
                        deployment_name=deployment.name,
                        project_type=deployment.project_type,
                        metadata={'port': deployment.port, 'status': deployment.status},
                    )
                    addon_manager.trigger('post_deployment', ctx, fail_fast=False)
                except Exception:
                    pass

                return {
                    'success': True,
                    'deployment_id': deployment.id,
                    'port': deployment.port,
                    'status': deployment.status,
                    'message': 'Deployment prepared (service creation requires sudo)'
                }

            # Enable service
            service_manager.enable_service(deployment)

            # Start service
            start_success, start_msg = service_manager.start_service(deployment)

            if not start_success:
                self.log(
                    deployment,
                    f"Failed to start service: {start_msg}",
                    DeploymentLog.Level.ERROR
                )
                deployment.status = Deployment.Status.FAILED
                deployment.save(update_fields=['status'])

                return {
                    'success': False,
                    'error': start_msg,
                    'deployment_id': deployment.id
                }

            self.log(
                deployment,
                "Deployment completed successfully!",
                DeploymentLog.Level.SUCCESS
            )

            # Trigger post-deployment hooks
            try:
                from apps.addons.manager import addon_manager, HookContext
                ctx = HookContext(
                    event='post_deployment',
                    deployment_id=deployment.id,
                    deployment_name=deployment.name,
                    project_type=deployment.project_type,
                    metadata={'port': deployment.port, 'status': deployment.status},
                )
                addon_manager.trigger('post_deployment', ctx, fail_fast=False)
            except Exception:
                pass

            return {
                'success': True,
                'deployment_id': deployment.id,
                'port': deployment.port,
                'status': deployment.status,
                'message': f'Deployment running on port {deployment.port}'
            }

        else:
            # For static sites, just create Nginx config
            self.log(deployment, "Creating Nginx configuration for static site")
            nginx_config = self.render_nginx_config(deployment)
            nginx_success, nginx_msg = service_manager.install_nginx_config(
                deployment,
                nginx_config
            )

            if nginx_success:
                service_manager.reload_nginx(deployment)
                deployment.status = Deployment.Status.RUNNING
                deployment.save(update_fields=['status'])

                self.log(
                    deployment,
                    "Static site deployed successfully!",
                    DeploymentLog.Level.SUCCESS
                )
            else:
                self.log(
                    deployment,
                    f"Nginx config creation skipped (dev mode): {nginx_msg}",
                    DeploymentLog.Level.WARNING
                )
                deployment.status = Deployment.Status.PENDING
                deployment.save(update_fields=['status'])

            # Trigger post-deployment hooks
            try:
                from apps.addons.manager import addon_manager, HookContext
                ctx = HookContext(
                    event='post_deployment',
                    deployment_id=deployment.id,
                    deployment_name=deployment.name,
                    project_type=deployment.project_type,
                    metadata={'port': deployment.port, 'status': deployment.status},
                )
                addon_manager.trigger('post_deployment', ctx, fail_fast=False)
            except Exception:
                pass

            return {
                'success': True,
                'deployment_id': deployment.id,
                'status': deployment.status
            }