"""
Docker service helper for WebOps Docker addon.

This module provides Docker containerization support for deployments,
including building images, managing containers, and health checking.
"""

import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


class DockerService:
    """Service for managing Docker containers in WebOps deployments."""

    def __init__(self):
        self.docker_available = self._check_docker_available()

    def _check_docker_available(self) -> bool:
        """Check if Docker is available on the system."""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Docker is not available on this system")
            return False

    def build_image(
        self,
        deployment_name: str,
        repo_path: Path,
        dockerfile_path: str = 'Dockerfile',
        build_args: Optional[Dict[str, str]] = None,
        image_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Build Docker image for deployment.

        Args:
            deployment_name: Name of the deployment
            repo_path: Path to repository
            dockerfile_path: Path to Dockerfile relative to repo
            build_args: Docker build arguments
            image_name: Custom image name (auto-generated if None)

        Returns:
            Tuple of (success, message/error)
        """
        if not self.docker_available:
            return False, "Docker is not available on this system"

        # Generate image name if not provided
        if not image_name:
            image_name = f"webops/{deployment_name}:latest"

        # Build Dockerfile path
        dockerfile_full_path = repo_path / dockerfile_path

        if not dockerfile_full_path.exists():
            return False, f"Dockerfile not found at {dockerfile_path}"

        # Prepare build command
        build_cmd = ['docker', 'build', '-t', image_name, '-f', str(dockerfile_full_path)]

        # Add build args
        if build_args:
            for key, value in build_args.items():
                build_cmd.extend(['--build-arg', f'{key}={value}'])

        # Add context (repo root)
        build_cmd.append(str(repo_path))

        logger.info(f"Building Docker image: {image_name}")

        try:
            result = subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=str(repo_path)
            )

            if result.returncode == 0:
                logger.info(f"Docker image built successfully: {image_name}")
                return True, image_name
            else:
                error_msg = f"Docker build failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg

        except subprocess.TimeoutExpired:
            error_msg = "Docker build timed out after 10 minutes"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Docker build error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def create_container(
        self,
        deployment_name: str,
        image_name: str,
        port: int,
        env_vars: Optional[Dict[str, str]] = None,
        volumes: Optional[List[Dict[str, str]]] = None,
        additional_ports: Optional[List[Dict[str, int]]] = None,
        network_mode: str = 'bridge'
    ) -> Tuple[bool, str]:
        """
        Create and start Docker container.

        Args:
            deployment_name: Name of the deployment
            image_name: Docker image name
            port: Main application port
            env_vars: Environment variables
            volumes: Volume mounts [{"host": "/path", "container": "/path"}]
            additional_ports: Additional port mappings
            network_mode: Docker network mode

        Returns:
            Tuple of (success, container_id/error)
        """
        if not self.docker_available:
            return False, "Docker is not available"

        container_name = f"webops-{deployment_name}"

        # Stop and remove existing container if exists
        self._stop_container(container_name)
        self._remove_container(container_name)

        # Prepare run command
        run_cmd = [
            'docker', 'run', '-d',
            '--name', container_name,
            '--restart', 'unless-stopped',
            '--network', network_mode,
            '-p', f'{port}:{port}'
        ]

        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                run_cmd.extend(['-e', f'{key}={value}'])

        # Add port to env vars
        run_cmd.extend(['-e', f'PORT={port}'])

        # Add volume mounts
        if volumes:
            for volume in volumes:
                host_path = volume.get('host', '')
                container_path = volume.get('container', '')
                if host_path and container_path:
                    run_cmd.extend(['-v', f'{host_path}:{container_path}'])

        # Add additional ports
        if additional_ports:
            for port_mapping in additional_ports:
                host_port = port_mapping.get('host')
                container_port = port_mapping.get('container')
                if host_port and container_port:
                    run_cmd.extend(['-p', f'{host_port}:{container_port}'])

        # Add image name
        run_cmd.append(image_name)

        logger.info(f"Creating Docker container: {container_name}")

        try:
            result = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                container_id = result.stdout.strip()
                logger.info(f"Docker container created: {container_id}")
                return True, container_id
            else:
                error_msg = f"Docker run failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Docker run error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _stop_container(self, container_name: str) -> bool:
        """Stop a Docker container."""
        try:
            subprocess.run(
                ['docker', 'stop', container_name],
                capture_output=True,
                timeout=30
            )
            return True
        except:
            return False

    def _remove_container(self, container_name: str) -> bool:
        """Remove a Docker container."""
        try:
            subprocess.run(
                ['docker', 'rm', container_name],
                capture_output=True,
                timeout=30
            )
            return True
        except:
            return False

    def get_container_status(self, deployment_name: str) -> Dict[str, Any]:
        """
        Get Docker container status.

        Args:
            deployment_name: Name of the deployment

        Returns:
            Dictionary with container status information
        """
        container_name = f"webops-{deployment_name}"

        try:
            result = subprocess.run(
                ['docker', 'inspect', container_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                inspect_data = json.loads(result.stdout)
                if inspect_data:
                    container_info = inspect_data[0]
                    state = container_info.get('State', {})

                    return {
                        'exists': True,
                        'running': state.get('Running', False),
                        'status': state.get('Status', 'unknown'),
                        'started_at': state.get('StartedAt'),
                        'finished_at': state.get('FinishedAt'),
                        'exit_code': state.get('ExitCode'),
                        'error': state.get('Error', ''),
                        'health': state.get('Health', {}).get('Status', 'none')
                    }

            return {
                'exists': False,
                'running': False,
                'status': 'not_found'
            }

        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return {
                'exists': False,
                'running': False,
                'status': 'error',
                'error': str(e)
            }

    def stop_container(self, deployment_name: str) -> Tuple[bool, str]:
        """Stop Docker container for deployment."""
        container_name = f"webops-{deployment_name}"

        try:
            result = subprocess.run(
                ['docker', 'stop', container_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, f"Container {container_name} stopped"
            else:
                return False, f"Failed to stop container: {result.stderr}"

        except Exception as e:
            return False, f"Error stopping container: {str(e)}"

    def start_container(self, deployment_name: str) -> Tuple[bool, str]:
        """Start Docker container for deployment."""
        container_name = f"webops-{deployment_name}"

        try:
            result = subprocess.run(
                ['docker', 'start', container_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, f"Container {container_name} started"
            else:
                return False, f"Failed to start container: {result.stderr}"

        except Exception as e:
            return False, f"Error starting container: {str(e)}"

    def restart_container(self, deployment_name: str) -> Tuple[bool, str]:
        """Restart Docker container for deployment."""
        container_name = f"webops-{deployment_name}"

        try:
            result = subprocess.run(
                ['docker', 'restart', container_name],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return True, f"Container {container_name} restarted"
            else:
                return False, f"Failed to restart container: {result.stderr}"

        except Exception as e:
            return False, f"Error restarting container: {str(e)}"

    def get_container_logs(
        self,
        deployment_name: str,
        tail: int = 100
    ) -> Tuple[bool, str]:
        """
        Get Docker container logs.

        Args:
            deployment_name: Name of the deployment
            tail: Number of lines to retrieve

        Returns:
            Tuple of (success, logs/error)
        """
        container_name = f"webops-{deployment_name}"

        try:
            result = subprocess.run(
                ['docker', 'logs', '--tail', str(tail), container_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Failed to get logs: {result.stderr}"

        except Exception as e:
            return False, f"Error getting logs: {str(e)}"

    def generate_dockerfile(
        self,
        repo_path: Path,
        project_type: str = 'django',
        python_version: str = '3.11'
    ) -> Tuple[bool, str]:
        """
        Generate a Dockerfile for the project.

        Args:
            repo_path: Path to repository
            project_type: Type of project (django, static, etc.)
            python_version: Python version to use

        Returns:
            Tuple of (success, message)
        """
        dockerfile_path = repo_path / 'Dockerfile'

        if dockerfile_path.exists():
            return False, "Dockerfile already exists"

        if project_type == 'django':
            dockerfile_content = self._generate_django_dockerfile(python_version)
        elif project_type == 'static':
            dockerfile_content = self._generate_static_dockerfile()
        else:
            dockerfile_content = self._generate_django_dockerfile(python_version)

        try:
            dockerfile_path.write_text(dockerfile_content)
            logger.info(f"Generated Dockerfile at {dockerfile_path}")
            return True, "Dockerfile generated successfully"
        except Exception as e:
            error_msg = f"Failed to write Dockerfile: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _generate_django_dockerfile(self, python_version: str) -> str:
        """Generate Dockerfile for Django projects."""
        return f"""# Auto-generated Dockerfile by WebOps Docker Addon
FROM python:{python_version}-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    postgresql-client \\
    libpq-dev \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files (if needed)
RUN python manage.py collectstatic --noinput || true

# Expose port (will be overridden by PORT env var)
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:${{PORT:-8000}}", "--workers", "2", "--timeout", "120", "config.wsgi:application"]
"""

    def _generate_static_dockerfile(self) -> str:
        """Generate Dockerfile for static sites."""
        return """# Auto-generated Dockerfile by WebOps Docker Addon
FROM nginx:alpine

# Copy static files to nginx
COPY . /usr/share/nginx/html

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
"""
