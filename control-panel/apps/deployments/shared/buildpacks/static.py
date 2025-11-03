"""Static site buildpack."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class StaticBuildpack(Buildpack):
    name = 'static'
    display_name = 'Static Site'

    def detect(self, repo_path: Path) -> BuildpackResult:
        # Look for HTML files
        html_files = self._find_files(repo_path, '*.html')

        # Common static site patterns
        static_indicators = [
            repo_path / 'index.html',
            repo_path / 'public' / 'index.html',
            repo_path / 'dist' / 'index.html',
            repo_path / 'build' / 'index.html',
        ]

        has_static = any(path.exists() for path in static_indicators)

        if not (html_files or has_static):
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='static', confidence=0.0)

        # Determine static site root
        static_root = 'public' if (repo_path / 'public' / 'index.html').exists() else \
                      'dist' if (repo_path / 'dist' / 'index.html').exists() else \
                      'build' if (repo_path / 'build' / 'index.html').exists() else '.'

        return BuildpackResult(
            detected=True, buildpack_name=self.name, project_type='static',
            confidence=0.50,  # Low confidence as it's the fallback
            framework='static-html',
            build_command='',  # No build for plain static
            start_command='',  # Nginx will serve it
            install_command='',
            requires_build=False,
            port=8080,
            env_vars={},
            metadata={'static_root': static_root}
        )
