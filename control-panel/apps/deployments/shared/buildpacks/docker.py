"""Docker buildpack."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class DockerBuildpack(Buildpack):
    name = 'docker'
    display_name = 'Docker'

    def detect(self, repo_path: Path) -> BuildpackResult:
        dockerfile = repo_path / 'Dockerfile'
        docker_compose = repo_path / 'docker-compose.yml'

        if not dockerfile.exists():
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='docker', confidence=0.0)

        # Docker gets highest priority when present
        return BuildpackResult(
            detected=True, buildpack_name=self.name, project_type='docker',
            confidence=1.0,  # Explicit Docker is 100% confident
            framework='docker',
            build_command='docker build -t app .',
            start_command='docker run -p $PORT:$PORT app',
            install_command='',
            dockerfile_path='Dockerfile',
            docker_compose_path='docker-compose.yml' if docker_compose.exists() else None,
            port=8080,
            env_vars={},
            metadata={
                'has_compose': docker_compose.exists()
            }
        )
