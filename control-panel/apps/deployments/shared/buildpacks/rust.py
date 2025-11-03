"""Rust buildpack."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class RustBuildpack(Buildpack):
    name = 'rust'
    display_name = 'Rust'

    def detect(self, repo_path: Path) -> BuildpackResult:
        if not (repo_path / 'Cargo.toml').exists():
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='rust', confidence=0.0)

        return BuildpackResult(
            detected=True, buildpack_name=self.name, project_type='rust',
            confidence=0.95, framework='rust',
            build_command='cargo build --release',
            start_command='./target/release/app',
            install_command='cargo fetch',
            port=8080, env_vars={}, metadata={}
        )
