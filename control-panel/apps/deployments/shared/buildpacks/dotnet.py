""".NET/C# buildpack detector."""

from pathlib import Path
from typing import Optional
from .base import Buildpack, BuildpackResult


class DotNetBuildpack(Buildpack):
    """Detect and configure .NET applications."""

    name = 'dotnet'
    display_name = '.NET'

    def detect(self, repo_path: Path) -> BuildpackResult:
        """Detect .NET project."""
        # Look for .csproj or .sln files
        csproj_files = list(repo_path.glob('*.csproj')) + list(repo_path.glob('**/*.csproj'))
        sln_files = list(repo_path.glob('*.sln'))

        if not csproj_files and not sln_files:
            return BuildpackResult(
                detected=False,
                buildpack_name=self.name,
                project_type='dotnet',
                confidence=0.0
            )

        # Detect .NET version and framework
        framework, version = self._detect_framework_and_version(csproj_files)

        # Detect if it's a web application
        is_web_app = self._is_web_application(csproj_files)

        # Get project name for build output
        project_name = self._get_project_name(csproj_files)

        # Determine commands
        build_cmd = self._get_build_command(sln_files, csproj_files)
        start_cmd = self._get_start_command(is_web_app, project_name)

        return BuildpackResult(
            detected=True,
            buildpack_name=self.name,
            project_type='dotnet',
            confidence=0.95,
            framework=framework,
            version=version,
            build_command=build_cmd,
            start_command=start_cmd,
            install_command='dotnet restore',
            port=5000 if is_web_app else 8080,
            env_vars={
                'ASPNETCORE_ENVIRONMENT': 'Production',
                'ASPNETCORE_URLS': 'http://+:$PORT',
            } if is_web_app else {},
            metadata={
                'is_web_app': is_web_app,
                'project_name': project_name,
                'has_solution': len(sln_files) > 0,
            }
        )

    def _detect_framework_and_version(self, csproj_files: list) -> tuple[str, str]:
        """Detect .NET framework and version."""
        if not csproj_files:
            return 'dotnet', '8.0'

        # Read first csproj file
        content = self._read_file(csproj_files[0])
        if not content:
            return 'dotnet', '8.0'

        # Check for ASP.NET Core
        if 'Microsoft.AspNetCore' in content or 'Microsoft.NET.Sdk.Web' in content:
            framework = 'aspnet-core'
        # Check for Blazor
        elif 'Microsoft.AspNetCore.Components.WebAssembly' in content:
            framework = 'blazor-wasm'
        elif 'Microsoft.AspNetCore.Components.Server' in content:
            framework = 'blazor-server'
        # Check for .NET MAUI
        elif 'Microsoft.Maui' in content:
            framework = 'dotnet-maui'
        else:
            framework = 'dotnet'

        # Extract version
        import re
        version_match = re.search(r'<TargetFramework>net(\d+\.\d+)</TargetFramework>', content)
        if version_match:
            version = version_match.group(1)
        else:
            version = '8.0'

        return framework, version

    def _is_web_application(self, csproj_files: list) -> bool:
        """Check if it's a web application."""
        if not csproj_files:
            return False

        content = self._read_file(csproj_files[0])
        if not content:
            return False

        web_indicators = [
            'Microsoft.NET.Sdk.Web',
            'Microsoft.AspNetCore',
            'Microsoft.AspNetCore.App',
            '<PackageReference Include="Swashbuckle',
        ]

        return any(indicator in content for indicator in web_indicators)

    def _get_project_name(self, csproj_files: list) -> str:
        """Extract project name from .csproj file."""
        if not csproj_files:
            return 'app'

        # Use filename without extension
        return csproj_files[0].stem

    def _get_build_command(self, sln_files: list, csproj_files: list) -> str:
        """Get build command."""
        if sln_files:
            # Build solution
            return f'dotnet build {sln_files[0].name} --configuration Release'
        elif csproj_files:
            # Build project
            return f'dotnet build {csproj_files[0].name} --configuration Release'
        return 'dotnet build --configuration Release'

    def _get_start_command(self, is_web_app: bool, project_name: str) -> str:
        """Get start command."""
        if is_web_app:
            # For web apps, run the published DLL
            return f'dotnet {project_name}.dll'
        return f'dotnet run --project {project_name}.csproj'
