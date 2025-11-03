"""Go buildpack detector."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class GoBuildpack(Buildpack):
    """Detect and configure Go projects."""

    name = 'go'
    display_name = 'Go'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Go project."""
        go_mod = repo_path / 'go.mod'

        if not go_mod.exists():
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='go', confidence=0.0)

        # Read go.mod for module name and version
        content = self._read_file(go_mod)
        module_name = self._extract_module_name(content)
        go_version = self._extract_go_version(content)

        # Detect main package
        main_file = self._find_main_package(repo_path)

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='go',
            confidence=0.95,
            framework='go',
            version=go_version,
            build_command='go build -o app',
            start_command='./app',
            install_command='go mod download',
            port=8080,
            env_vars={},
            metadata={'module_name': module_name, 'main_file': main_file}
        )

    def _extract_module_name(self, content: str) -> str:
        """Extract module name from go.mod."""
        if not content:
            return ''
        for line in content.split('\n'):
            if line.strip().startswith('module '):
                return line.strip().replace('module ', '')
        return ''

    def _extract_go_version(self, content: str) -> str:
        """Extract Go version from go.mod."""
        if not content:
            return '1.21'
        for line in content.split('\n'):
            if line.strip().startswith('go '):
                return line.strip().replace('go ', '')
        return '1.21'

    def _find_main_package(self, repo_path: Path) -> str:
        """Find main.go file."""
        candidates = ['main.go', 'cmd/main.go', 'cmd/server/main.go']
        for candidate in candidates:
            if (repo_path / candidate).exists():
                return candidate
        return 'main.go'
