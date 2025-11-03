"""
Buildpack-style framework detectors.

Inspired by Railway, Heroku, and other PaaS providers.
Each buildpack can detect if a project uses its framework and provide
build/start configuration.
"""

from .base import Buildpack, BuildpackResult
from .nodejs import NodeJSBuildpack
from .python import PythonBuildpack
from .django import DjangoBuildpack
from .go import GoBuildpack
from .rust import RustBuildpack
from .php import PHPBuildpack
from .ruby import RubyBuildpack
from .static import StaticBuildpack
from .docker import DockerBuildpack
from .dotnet import DotNetBuildpack
from .java import JavaBuildpack
from .elixir import ElixirBuildpack

__all__ = [
    'Buildpack',
    'BuildpackResult',
    'NodeJSBuildpack',
    'PythonBuildpack',
    'DjangoBuildpack',
    'GoBuildpack',
    'RustBuildpack',
    'PHPBuildpack',
    'RubyBuildpack',
    'StaticBuildpack',
    'DockerBuildpack',
    'DotNetBuildpack',
    'JavaBuildpack',
    'ElixirBuildpack',
    'ALL_BUILDPACKS',
    'detect_project'
]

# Buildpacks in priority order (more specific first)
ALL_BUILDPACKS = [
    DockerBuildpack(),      # Highest priority - explicit Docker
    DjangoBuildpack(),      # Django before generic Python
    NodeJSBuildpack(),
    JavaBuildpack(),        # Java/Spring
    DotNetBuildpack(),      # .NET/C#
    ElixirBuildpack(),      # Elixir/Phoenix
    GoBuildpack(),
    RustBuildpack(),
    PHPBuildpack(),
    RubyBuildpack(),
    PythonBuildpack(),     # Generic Python (FastAPI, Flask, etc.)
    StaticBuildpack(),     # Lowest priority - fallback
]


def detect_project(repo_path: str) -> BuildpackResult:
    """
    Detect project type using buildpacks.

    Args:
        repo_path: Path to repository

    Returns:
        BuildpackResult with detected configuration
    """
    from pathlib import Path

    repo = Path(repo_path)

    for buildpack in ALL_BUILDPACKS:
        result = buildpack.detect(repo)
        if result.detected:
            return result

    # Fallback to static if nothing detected
    return BuildpackResult(
        detected=True,
        buildpack_name='static',
        project_type='static',
        confidence=0.3,
        framework='static-html',
        build_command='',
        start_command='',
        env_vars={},
        install_command='',
        port=8080,
        metadata={}
    )
