"""Node.js buildpack detector."""

import json
from pathlib import Path
from typing import Optional
from .base import Buildpack, BuildpackResult


class NodeJSBuildpack(Buildpack):
    """Detect and configure Node.js projects."""

    name = 'nodejs'
    display_name = 'Node.js'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect Node.js project."""
        package_json = repo_path / 'package.json'

        if not package_json.exists():
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='nodejs',
                confidence=0.0
            )

        # Read package.json
        package_data = self._read_package_json(package_json)
        if not package_data:
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='nodejs',
                confidence=0.0
            )

        # Detect framework
        framework, confidence = self._detect_framework(package_data, repo_path)

        # Detect package manager
        package_manager = self._detect_package_manager(repo_path)

        # Get build and start commands
        build_cmd = self._get_build_command(package_data, package_manager, framework)
        start_cmd = self._get_start_command(package_data, framework)
        install_cmd = self._get_install_command(package_manager)

        # Detect port
        port = self._detect_port(repo_path, package_data)

        # Get Node version
        node_version = package_data.get('engines', {}).get('node', 'lts')

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='nodejs',
            confidence=confidence,
            framework=framework,
            version=node_version,
            build_command=build_cmd,
            start_command=start_cmd,
            install_command=install_cmd,
            package_manager=package_manager,
            port=port,
            env_vars={
                'NODE_ENV': 'production',
                'NPM_CONFIG_PRODUCTION': 'false',  # Install devDependencies for build
            },
            metadata={
                'package_json': package_data,
                'has_lock_file': self._has_lock_file(repo_path, package_manager),
            }
        )

    def _read_package_json(self, path: Path) -> Optional[dict]:
        """Read and parse package.json."""
        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _detect_framework(self, package_data: dict, repo_path: Path) -> tuple[str, float]:
        """
        Detect Node.js framework.

        Returns:
            Tuple of (framework_name, confidence)
        """
        deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}

        # Check for Next.js
        if 'next' in deps:
            return 'nextjs', 0.95

        # Check for Nuxt.js
        if 'nuxt' in deps or 'nuxt3' in deps:
            return 'nuxtjs', 0.95

        # Check for Remix
        if '@remix-run/react' in deps:
            return 'remix', 0.95

        # Check for SvelteKit
        if '@sveltejs/kit' in deps:
            return 'sveltekit', 0.95

        # Check for Astro
        if 'astro' in deps:
            return 'astro', 0.95

        # Check for Vite
        if 'vite' in deps:
            # Could be React, Vue, Svelte with Vite
            if 'react' in deps:
                return 'react-vite', 0.90
            elif 'vue' in deps:
                return 'vue-vite', 0.90
            elif 'svelte' in deps:
                return 'svelte-vite', 0.90
            return 'vite', 0.85

        # Check for Create React App
        if 'react-scripts' in deps:
            return 'create-react-app', 0.90

        # Check for Vue CLI
        if '@vue/cli-service' in deps:
            return 'vue-cli', 0.90

        # Check for Express
        if 'express' in deps:
            return 'express', 0.85

        # Check for NestJS
        if '@nestjs/core' in deps:
            return 'nestjs', 0.90

        # Check for Fastify
        if 'fastify' in deps:
            return 'fastify', 0.85

        # Check for Koa
        if 'koa' in deps:
            return 'koa', 0.85

        # Generic React
        if 'react' in deps:
            return 'react', 0.70

        # Generic Vue
        if 'vue' in deps:
            return 'vue', 0.70

        # Generic Node.js
        return 'nodejs', 0.60

    def _detect_package_manager(self, repo_path: Path) -> str:
        """Detect package manager (npm, yarn, pnpm, bun)."""
        if (repo_path / 'pnpm-lock.yaml').exists():
            return 'pnpm'
        if (repo_path / 'yarn.lock').exists():
            return 'yarn'
        if (repo_path / 'bun.lockb').exists():
            return 'bun'
        return 'npm'

    def _has_lock_file(self, repo_path: Path, package_manager: str) -> bool:
        """Check if lock file exists."""
        lock_files = {
            'npm': 'package-lock.json',
            'yarn': 'yarn.lock',
            'pnpm': 'pnpm-lock.yaml',
            'bun': 'bun.lockb'
        }
        lock_file = lock_files.get(package_manager, 'package-lock.json')
        return (repo_path / lock_file).exists()

    def _get_install_command(self, package_manager: str) -> str:
        """Get install command for package manager."""
        commands = {
            'npm': 'npm install',
            'yarn': 'yarn install',
            'pnpm': 'pnpm install',
            'bun': 'bun install'
        }
        return commands.get(package_manager, 'npm install')

    def _get_build_command(self, package_data: dict, package_manager: str, framework: str) -> str:
        """Get build command."""
        scripts = package_data.get('scripts', {})

        # Check for explicit build script
        if 'build' in scripts:
            if package_manager == 'npm':
                return 'npm run build'
            elif package_manager == 'yarn':
                return 'yarn build'
            elif package_manager == 'pnpm':
                return 'pnpm build'
            elif package_manager == 'bun':
                return 'bun run build'

        # Framework-specific defaults (if no build script)
        if framework in ['nextjs', 'remix', 'sveltekit', 'astro']:
            # These frameworks require build
            return f'{package_manager} run build' if package_manager != 'npm' else 'npm run build'

        # No build needed
        return ''

    def _get_start_command(self, package_data: dict, framework: str) -> str:
        """Get start command."""
        scripts = package_data.get('scripts', {})

        # Framework-specific start commands
        if framework == 'nextjs':
            return scripts.get('start', 'npm start')

        # Check for start script
        if 'start' in scripts:
            return 'npm start'

        # Check for serve script
        if 'serve' in scripts:
            return 'npm run serve'

        # Check for main entry point
        main = package_data.get('main', 'index.js')
        if main:
            return f'node {main}'

        # Default
        return 'node index.js'

    def _detect_port(self, repo_path: Path, package_data: dict) -> int:
        """Try to detect default port from common files."""
        # Check common entry points for PORT configuration
        entry_files = ['index.js', 'server.js', 'app.js', 'src/index.js', 'src/server.js']

        for entry_file in entry_files:
            file_path = repo_path / entry_file
            if file_path.exists():
                content = self._read_file(file_path)
                if content:
                    # Look for common port patterns
                    if '3000' in content:
                        return 3000
                    if '8080' in content:
                        return 8080
                    if '5000' in content:
                        return 5000

        # Framework defaults
        framework = self._detect_framework(package_data, repo_path)[0]
        if framework == 'nextjs':
            return 3000
        elif framework in ['react-vite', 'vue-vite', 'vite']:
            return 5173
        elif framework == 'create-react-app':
            return 3000
        elif framework == 'express':
            return 3000

        # Default Node.js port
        return 3000
