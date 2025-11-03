"""Ruby buildpack."""

from pathlib import Path
from .base import Buildpack, BuildpackResult


class RubyBuildpack(Buildpack):
    name = 'ruby'
    display_name = 'Ruby'

    def detect(self, repo_path: Path) -> BuildpackResult:
        gemfile = repo_path / 'Gemfile'
        if not gemfile.exists():
            return BuildpackResult(detected=False, buildpack_name=self.name,
                                   project_type='ruby', confidence=0.0)

        framework = 'ruby'
        if (repo_path / 'config.ru').exists():
            framework = 'rack'
        if (repo_path / 'config' / 'application.rb').exists():
            framework = 'rails'

        start_cmd = 'bundle exec puma -C config/puma.rb' if framework == 'rails' else 'bundle exec rackup -o 0.0.0.0 -p $PORT'

        return BuildpackResult(
            detected=True, buildpack_name=self.name, project_type='ruby',
            confidence=0.90, framework=framework,
            build_command='bundle exec rails assets:precompile' if framework == 'rails' else '',
            start_command=start_cmd,
            install_command='bundle install --without development test',
            port=3000, env_vars={'RAILS_ENV': 'production'} if framework == 'rails' else {},
            metadata={}
        )
