"""PHP buildpack."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class PHPBuildpack(Buildpack):
    name = 'php'
    display_name = 'PHP'

    def detect(self, repo_path: Path) -> BuildpackResult:
        composer_json = repo_path / 'composer.json'
        if not composer_json.exists() and not self._find_files(repo_path, '*.php'):
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='php', confidence=0.0)

        framework = 'php'
        if (repo_path / 'artisan').exists():
            framework = 'laravel'
        elif (repo_path / 'wp-config.php').exists() or (repo_path / 'wp-config-sample.php').exists():
            framework = 'wordpress'

        return BuildpackResult(
            detected=True, buildpack_name=self.name, project_type='php',
            confidence=0.85, framework=framework,
            build_command='composer install --no-dev --optimize-autoloader' if composer_json.exists() else '',
            start_command='php -S 0.0.0.0:$PORT -t public' if framework == 'laravel' else 'php -S 0.0.0.0:$PORT',
            install_command='composer install' if composer_json.exists() else '',
            port=8080, env_vars={}, metadata={}
        )
