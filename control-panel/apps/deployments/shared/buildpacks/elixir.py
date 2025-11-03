"""Elixir buildpack detector."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class ElixirBuildpack(Buildpack):
    """Detect and configure Elixir applications."""

    name = 'elixir'
    display_name = 'Elixir'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Elixir project."""
        mix_exs = repo_path / 'mix.exs'

        if not mix_exs.exists():
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='elixir',
                confidence=0.0
            )

        # Read mix.exs to detect framework
        mix_content = self._read_file(mix_exs)
        framework, confidence = self._detect_framework(mix_content)

        # Detect Elixir and Erlang versions
        elixir_version = self._detect_elixir_version(repo_path)
        erlang_version = self._detect_erlang_version(repo_path)

        # Determine commands based on framework
        if framework == 'phoenix':
            install_cmd = 'mix deps.get --only prod && cd assets && npm install && cd ..'
            build_cmd = 'mix deps.compile && cd assets && npm run deploy && cd .. && mix phx.digest && mix compile'
            start_cmd = 'mix phx.server'
            port = 4000
            env_vars = {
                'MIX_ENV': 'prod',
                'PORT': '$PORT',
                'SECRET_KEY_BASE': '${SECRET_KEY_BASE:-$(mix phx.gen.secret)}',
            }
        else:
            # Generic Elixir application
            install_cmd = 'mix deps.get --only prod'
            build_cmd = 'mix compile'
            start_cmd = 'mix run --no-halt'
            port = 4000
            env_vars = {
                'MIX_ENV': 'prod',
            }

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='elixir',
            confidence=confidence,
            framework=framework,
            version=elixir_version,
            build_command=build_cmd,
            start_command=start_cmd,
            install_command=install_cmd,
            package_manager='mix',
            port=port,
            env_vars=env_vars,
            metadata={
                'erlang_version': erlang_version,
            }
        )

    def _detect_framework(self, mix_content: str) -> tuple[str, float]:
        """Detect Elixir framework from mix.exs."""
        if not mix_content:
            return 'elixir', 0.80

        # Check for Phoenix
        if ':phoenix,' in mix_content or '"phoenix"' in mix_content:
            return 'phoenix', 0.95

        # Check for Nerves (IoT)
        if ':nerves,' in mix_content:
            return 'nerves', 0.95

        # Check for Phoenix LiveView
        if ':phoenix_live_view,' in mix_content:
            return 'phoenix-liveview', 0.95

        # Generic Elixir
        return 'elixir', 0.80

    def _detect_elixir_version(self, repo_path: Path) -> str:
        """Detect Elixir version."""
        # Check .tool-versions (asdf)
        tool_versions = repo_path / '.tool-versions'
        if tool_versions.exists():
            content = self._read_file(tool_versions)
            if content:
                import re
                match = re.search(r'elixir\s+([\d.]+)', content)
                if match:
                    return match.group(1)

        # Check elixir_buildpack.config
        buildpack_config = repo_path / 'elixir_buildpack.config'
        if buildpack_config.exists():
            content = self._read_file(buildpack_config)
            if content:
                import re
                match = re.search(r'elixir_version=([\d.]+)', content)
                if match:
                    return match.group(1)

        # Default to latest stable
        return '1.15'

    def _detect_erlang_version(self, repo_path: Path) -> str:
        """Detect Erlang/OTP version."""
        # Check .tool-versions (asdf)
        tool_versions = repo_path / '.tool-versions'
        if tool_versions.exists():
            content = self._read_file(tool_versions)
            if content:
                import re
                match = re.search(r'erlang\s+([\d.]+)', content)
                if match:
                    return match.group(1)

        # Check elixir_buildpack.config
        buildpack_config = repo_path / 'elixir_buildpack.config'
        if buildpack_config.exists():
            content = self._read_file(buildpack_config)
            if content:
                import re
                match = re.search(r'erlang_version=([\d.]+)', content)
                if match:
                    return match.group(1)

        # Default to latest OTP
        return '26'
