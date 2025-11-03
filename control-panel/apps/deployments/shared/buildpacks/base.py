"""Base buildpack interface."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


@dataclass
class BuildpackResult:
    """Result from buildpack detection."""

    detected: bool
    buildpack_name: str
    project_type: str
    confidence: float  # 0.0 to 1.0
    framework: Optional[str] = None
    version: Optional[str] = None
    build_command: str = ''
    start_command: str = ''
    install_command: str = ''
    env_vars: Dict[str, str] = field(default_factory=dict)
    port: int = 8000
    requires_build: bool = True
    dockerfile_path: Optional[str] = None
    docker_compose_path: Optional[str] = None
    package_manager: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Buildpack(ABC):
    """Base buildpack class."""

    name: str = 'base'
    display_name: str = 'Base'

    @abstractmethod
    def detect(self, repo_path: Path) -> BuildpackResult:
        """
        Detect if this buildpack applies to the project.

        Args:
            repo_path: Path to repository root

        Returns:
            BuildpackResult with detection results
        """
        pass

    def _file_exists(self, repo_path: Path, *paths: str) -> bool:
        """Check if file exists in repo."""
        for path in paths:
            if (repo_path / path).exists():
                return True
        return False

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Safely read file contents."""
        try:
            return file_path.read_text()
        except Exception:
            return None

    def _find_files(self, repo_path: Path, pattern: str, max_depth: int = 3) -> List[Path]:
        """
        Find files matching pattern.

        Args:
            repo_path: Repository path
            pattern: Glob pattern
            max_depth: Maximum search depth

        Returns:
            List of matching file paths
        """
        excluded_dirs = {'.git', 'node_modules', 'venv', '.venv', 'env', '__pycache__', '.tox'}
        results = []

        for file in repo_path.rglob(pattern):
            # Check depth
            try:
                relative = file.relative_to(repo_path)
                if len(relative.parts) > max_depth:
                    continue

                # Check excluded dirs
                if any(excluded in relative.parts for excluded in excluded_dirs):
                    continue

                results.append(file)
            except ValueError:
                continue

        return results
