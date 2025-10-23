"""
Project validation utilities for WebOps deployments.

Validates project constraints before deployment to ensure smooth execution.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    message: str
    level: str  # 'error', 'warning', 'info'
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class ProjectValidator:
    """Validates project structure and requirements."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.results: List[ValidationResult] = []

    def validate_all(self) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all validation checks.

        Returns:
            Tuple of (all_passed, results_list)
        """
        self.results = []

        # Structure validation
        self.validate_project_structure()

        # Requirements validation
        self.validate_requirements()

        # Environment validation
        self.validate_environment_config()

        # Django-specific validation
        if self.is_django_project():
            self.validate_django_settings()
            self.validate_django_wsgi()

        # Check for common issues
        self.check_common_issues()

        # Determine if all critical checks passed
        all_passed = all(
            result.passed or result.level != 'error'
            for result in self.results
        )

        return all_passed, self.results

    def is_django_project(self) -> bool:
        """Check if this is a Django project."""
        return (self.repo_path / "manage.py").exists()

    def validate_project_structure(self) -> None:
        """Validate basic project structure."""
        # Check for essential files
        if self.is_django_project():
            if (self.repo_path / "manage.py").exists():
                self.results.append(ValidationResult(
                    passed=True,
                    message="Django project detected (manage.py found)",
                    level='info',
                    details={'project_type': 'django'}
                ))

            # Check for requirements.txt
            if not (self.repo_path / "requirements.txt").exists():
                self.results.append(ValidationResult(
                    passed=False,
                    message="requirements.txt not found - dependencies won't be installed",
                    level='warning',
                    details={'missing_file': 'requirements.txt'}
                ))
        else:
            # Static site checks
            if (self.repo_path / "index.html").exists():
                self.results.append(ValidationResult(
                    passed=True,
                    message="Static site detected (index.html found)",
                    level='info',
                    details={'project_type': 'static'}
                ))
            else:
                self.results.append(ValidationResult(
                    passed=False,
                    message="No index.html found for static site",
                    level='warning'
                ))

    def validate_requirements(self) -> None:
        """Validate requirements.txt if present."""
        req_file = self.repo_path / "requirements.txt"

        if not req_file.exists():
            return

        try:
            content = req_file.read_text()
            lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')]

            if not lines:
                self.results.append(ValidationResult(
                    passed=False,
                    message="requirements.txt is empty",
                    level='warning'
                ))
                return

            # Check for common dependencies
            deps = [line.split('==')[0].split('>=')[0].split('<=')[0].lower() for line in lines]

            if self.is_django_project():
                if 'django' not in deps:
                    self.results.append(ValidationResult(
                        passed=False,
                        message="Django not found in requirements.txt",
                        level='error',
                        details={'suggestion': 'Add Django>=4.0 to requirements.txt'}
                    ))
                else:
                    self.results.append(ValidationResult(
                        passed=True,
                        message=f"Found {len(lines)} dependencies in requirements.txt",
                        level='info',
                        details={'dependency_count': len(lines)}
                    ))

            # Check for gunicorn (needed for production)
            if 'gunicorn' not in deps and self.is_django_project():
                self.results.append(ValidationResult(
                    passed=False,
                    message="gunicorn not found in requirements.txt - required for production deployment",
                    level='warning',
                    details={'suggestion': 'Add gunicorn>=20.0 to requirements.txt'}
                ))

            # ASGI detection: require uvicorn if asgi.py is present
            try:
                asgi_files = list(self.repo_path.rglob("asgi.py"))
                excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
                valid_asgi = [f for f in asgi_files if not any(part in excluded_dirs for part in f.relative_to(self.repo_path).parts)]

                if valid_asgi:
                    if 'uvicorn' not in deps:
                        self.results.append(ValidationResult(
                            passed=False,
                            message="ASGI detected but 'uvicorn' missing in requirements.txt",
                            level='error',
                            details={'suggestion': "Add uvicorn[standard]>=0.22 to requirements.txt"}
                        ))
                    else:
                        self.results.append(ValidationResult(
                            passed=True,
                            message="ASGI detected and uvicorn present",
                            level='info'
                        ))
            except Exception as e:
                self.results.append(ValidationResult(
                    passed=False,
                    message=f"Error checking ASGI/uvicorn: {str(e)}",
                    level='warning'
                ))

        except Exception as e:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Error reading requirements.txt: {str(e)}",
                level='error'
            ))

    def validate_environment_config(self) -> None:
        """Validate .env.example and environment configuration."""
        env_example = self.repo_path / ".env.example"
        env_file = self.repo_path / ".env"

        if env_example.exists():
            try:
                content = env_example.read_text()
                env_vars = self._parse_env_file(content)

                self.results.append(ValidationResult(
                    passed=True,
                    message=f"Found .env.example with {len(env_vars)} variables",
                    level='info',
                    details={'env_vars': list(env_vars.keys()), 'count': len(env_vars)}
                ))

                # Check for critical environment variables
                critical_vars = ['SECRET_KEY', 'DATABASE_URL', 'ALLOWED_HOSTS']
                missing_critical = [var for var in critical_vars if var not in env_vars]

                if missing_critical and self.is_django_project():
                    self.results.append(ValidationResult(
                        passed=False,
                        message=f"Missing recommended env vars in .env.example: {', '.join(missing_critical)}",
                        level='warning',
                        details={'missing_vars': missing_critical}
                    ))

            except Exception as e:
                self.results.append(ValidationResult(
                    passed=False,
                    message=f"Error parsing .env.example: {str(e)}",
                    level='warning'
                ))
        else:
            if self.is_django_project():
                self.results.append(ValidationResult(
                    passed=False,
                    message="No .env.example file found - consider adding one for easier configuration",
                    level='info'
                ))

        # Check if .env exists (should not be committed)
        if env_file.exists():
            self.results.append(ValidationResult(
                passed=False,
                message=".env file found in repository - this should be in .gitignore",
                level='warning',
                details={'security_risk': True}
            ))

    def detect_django_settings_module(self) -> str:
        """
        Intelligently detect the correct Django settings module path.
        
        Returns:
            The Django settings module path (e.g., 'myproject.settings')
        """
        # Find all settings.py files
        settings_files = list(self.repo_path.rglob("settings.py"))
        
        if not settings_files:
            return "settings"  # Fallback
        
        # Filter out settings files in migrations, tests, or venv directories
        valid_settings = []
        for settings_file in settings_files:
            relative_path = settings_file.relative_to(self.repo_path)
            path_parts = relative_path.parts
            
            # Skip if in excluded directories
            excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
            if any(part in excluded_dirs for part in path_parts):
                continue
                
            valid_settings.append(settings_file)
        
        if not valid_settings:
            return "settings"
        
        # Prioritize settings files based on common Django patterns
        best_settings = None
        best_score = -1
        
        for settings_file in valid_settings:
            relative_path = settings_file.relative_to(self.repo_path)
            path_parts = relative_path.parts[:-1]  # Exclude 'settings.py' filename
            
            score = 0
            
            # Higher score for common Django project structure patterns
            if 'config' in path_parts:
                score += 10
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
            relative_path = best_settings.relative_to(self.repo_path)
            module_parts = relative_path.parts[:-1]  # Remove 'settings.py'
            
            if module_parts:
                module_path = '.'.join(module_parts) + '.settings'
            else:
                module_path = 'settings'
            
            return module_path
        
        # Final fallback
        return "settings"

    def validate_django_settings(self) -> None:
        """Validate Django settings configuration."""
        # Use smart detection to find settings.py
        settings_module = self.detect_django_settings_module()
        
        # Find the actual settings file
        settings_files = list(self.repo_path.rglob("settings.py"))
        
        # Filter out excluded directories
        valid_settings = []
        for settings_file in settings_files:
            relative_path = settings_file.relative_to(self.repo_path)
            path_parts = relative_path.parts
            
            excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
            if any(part in excluded_dirs for part in path_parts):
                continue
                
            valid_settings.append(settings_file)

        if not valid_settings:
            self.results.append(ValidationResult(
                passed=False,
                message="No settings.py found in Django project",
                level='error'
            ))
            return

        # Use the first valid settings file (should match our detection)
        settings_file = valid_settings[0]
        
        self.results.append(ValidationResult(
            passed=True,
            message=f"Django settings detected: {settings_module}",
            level='info',
            details={'settings_module': settings_module, 'settings_file': str(settings_file.relative_to(self.repo_path))}
        ))

        try:
            content = settings_file.read_text()

            # Check for environment-based configuration
            if 'os.environ' in content or 'env(' in content or 'config(' in content:
                self.results.append(ValidationResult(
                    passed=True,
                    message="Settings configured to read from environment variables",
                    level='info'
                ))
            else:
                self.results.append(ValidationResult(
                    passed=False,
                    message="Settings may not support environment variables properly",
                    level='warning',
                    details={'suggestion': 'Use python-decouple or django-environ for env config'}
                ))

            # Check for DEBUG setting
            if 'DEBUG = True' in content:
                self.results.append(ValidationResult(
                    passed=False,
                    message="DEBUG=True hardcoded in settings.py - should be configurable via env",
                    level='warning',
                    details={'security_risk': True}
                ))

            # Check for SECRET_KEY
            if "SECRET_KEY = '" in content or 'SECRET_KEY = "' in content:
                self.results.append(ValidationResult(
                    passed=False,
                    message="SECRET_KEY hardcoded in settings.py - should be in environment",
                    level='error',
                    details={'security_risk': True}
                ))

            # Check for ALLOWED_HOSTS
            if 'ALLOWED_HOSTS' in content:
                self.results.append(ValidationResult(
                    passed=True,
                    message="ALLOWED_HOSTS configured",
                    level='info'
                ))

        except Exception as e:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Error reading settings.py: {str(e)}",
                level='warning'
            ))

    def validate_django_wsgi(self) -> None:
        """Validate WSGI configuration for Django."""
        wsgi_files = list(self.repo_path.rglob("wsgi.py"))

        if not wsgi_files:
            self.results.append(ValidationResult(
                passed=False,
                message="No wsgi.py found - required for production deployment",
                level='error'
            ))
        else:
            self.results.append(ValidationResult(
                passed=True,
                message="WSGI configuration found",
                level='info',
                details={'wsgi_path': str(wsgi_files[0].relative_to(self.repo_path))}
            ))

    def check_common_issues(self) -> None:
        """Check for common deployment issues."""
        # Check for __pycache__ and .pyc files (should be in .gitignore)
        pycache_dirs = list(self.repo_path.rglob("__pycache__"))
        if pycache_dirs:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Found {len(pycache_dirs)} __pycache__ directories - add to .gitignore",
                level='info'
            ))

        # Check for .gitignore
        if not (self.repo_path / ".gitignore").exists():
            self.results.append(ValidationResult(
                passed=False,
                message="No .gitignore file found",
                level='info'
            ))

        # Check for very large files (>10MB)
        large_files = []
        for file in self.repo_path.rglob("*"):
            if file.is_file():
                try:
                    size_mb = file.stat().st_size / (1024 * 1024)
                    if size_mb > 10:
                        large_files.append((str(file.relative_to(self.repo_path)), size_mb))
                except:
                    pass

        if large_files:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Found {len(large_files)} large files (>10MB) - may slow deployment",
                level='warning',
                details={'large_files': large_files}
            ))

        # Check for database files (should not be committed)
        db_files = list(self.repo_path.glob("*.sqlite*")) + list(self.repo_path.glob("*.db"))
        if db_files:
            self.results.append(ValidationResult(
                passed=False,
                message=f"Found {len(db_files)} database files in repository - should be in .gitignore",
                level='warning',
                details={'db_files': [str(f.name) for f in db_files]}
            ))

    def _parse_env_file(self, content: str) -> Dict[str, str]:
        """
        Parse .env file content into dictionary.

        Args:
            content: Content of .env file

        Returns:
            Dictionary of environment variables
        """
        env_vars = {}

        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=value
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value

        return env_vars


def validate_project(repo_path: Path) -> Tuple[bool, List[ValidationResult]]:
    """
    Validate a project for deployment readiness.

    Args:
        repo_path: Path to project repository

    Returns:
        Tuple of (all_passed, validation_results)
    """
    validator = ProjectValidator(repo_path)
    return validator.validate_all()
