"""
Docker addon hooks for WebOps.

This module registers hooks that integrate Docker containerization
into the WebOps deployment workflow.
"""

import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Import dependencies
from apps.deployments.models import BaseDeployment, ApplicationDeployment
from .docker_service import DockerService


def _get_deployment_from_context(context: Dict[str, Any]):
    """Helper to get Deployment object from context."""
    deployment_id = context.get('deployment_id')
    if not deployment_id:
        logger.warning("No deployment_id in context")
        return None

    try:
        deployment = ApplicationDeployment.objects.get(id=deployment_id)
        return deployment
    except ApplicationDeployment.DoesNotExist:
        logger.error(f"Deployment {deployment_id} not found")
        return None


def docker_pre_deployment(context: Dict[str, Any]) -> None:
    """
    Pre-deployment hook for Docker addon.

    This hook checks if Docker deployment is enabled and prepares
    the Docker image before the main deployment process.
    """
    deployment = _get_deployment_from_context(context)
    if not deployment or not deployment.use_docker:
        return

    logger.info(f"Docker pre-deployment hook for {deployment.name}")

    # Initialize Docker service
    docker_service = DockerService()

    if not docker_service.docker_available:
        logger.error("Docker is not available on this system")
        raise Exception("Docker is not available. Please install Docker to use Docker deployments.")

    # Get repo path from context or construct it
    from apps.deployments.services import DeploymentService
    deployment_service = DeploymentService()
    repo_path = deployment_service.get_repo_path(deployment)

    # Check if Dockerfile exists
    dockerfile_path = repo_path / deployment.dockerfile_path

    if not dockerfile_path.exists() and deployment.auto_generate_dockerfile:
        logger.info(f"Generating Dockerfile for {deployment.name}")
        success, message = docker_service.generate_dockerfile(
            repo_path,
            project_type=deployment.project_type,
            python_version='3.11'
        )

        if not success:
            logger.error(f"Failed to generate Dockerfile: {message}")
            raise Exception(f"Failed to generate Dockerfile: {message}")

        # Log to deployment
        deployment_service.log(
            deployment,
            f"Auto-generated Dockerfile: {message}",
            'info'
        )
    elif not dockerfile_path.exists():
        error_msg = f"Dockerfile not found at {deployment.dockerfile_path} and auto-generation is disabled"
        logger.error(error_msg)
        raise Exception(error_msg)

    # Store in context for post-deployment hook
    context['docker_enabled'] = True
    context['repo_path'] = str(repo_path)


def docker_post_deployment(context: Dict[str, Any]) -> None:
    """
    Post-deployment hook for Docker addon.

    This hook builds the Docker image and creates/starts the container
    after the repository has been cloned and prepared.
    """
    if not context.get('docker_enabled'):
        return

    deployment = _get_deployment_from_context(context)
    if not deployment or not deployment.use_docker:
        return

    logger.info(f"Docker post-deployment hook for {deployment.name}")

    # Initialize services
    docker_service = DockerService()
    from apps.deployments.services import DeploymentService
    deployment_service = DeploymentService()

    repo_path = Path(context.get('repo_path', ''))
    if not repo_path or not repo_path.exists():
        logger.error("Repository path not available in context")
        return

    # Generate image name if not provided
    image_name = deployment.docker_image_name
    if not image_name:
        image_name = f"webops/{deployment.name}:latest"
        deployment.docker_image_name = image_name
        deployment.save(update_fields=['docker_image_name'])

    # Build Docker image
    deployment_service.log(deployment, "Building Docker image...", 'info')

    build_success, build_result = docker_service.build_image(
        deployment_name=deployment.name,
        repo_path=repo_path,
        dockerfile_path=deployment.dockerfile_path,
        build_args=deployment.docker_build_args or {},
        image_name=image_name
    )

    if not build_success:
        error_msg = f"Docker image build failed: {build_result}"
        deployment_service.log(deployment, error_msg, 'error')
        deployment.status = ApplicationDeployment.Status.FAILED
        deployment.save(update_fields=['status'])
        raise Exception(error_msg)

    deployment_service.log(
        deployment,
        f"Docker image built successfully: {build_result}",
        'success'
    )

    # Prepare environment variables (merge deployment env_vars and docker_env_vars)
    env_vars = {
        **(deployment.env_vars or {}),
        **(deployment.docker_env_vars or {})
    }

    # Create and start container
    deployment_service.log(deployment, "Creating Docker container...", 'info')

    create_success, create_result = docker_service.create_container(
        deployment_name=deployment.name,
        image_name=image_name,
        port=deployment.port,
        env_vars=env_vars,
        volumes=deployment.docker_volumes or [],
        additional_ports=deployment.docker_ports or [],
        network_mode=deployment.docker_network_mode or 'bridge'
    )

    if not create_success:
        error_msg = f"Docker container creation failed: {create_result}"
        deployment_service.log(deployment, error_msg, 'error')
        deployment.status = ApplicationDeployment.Status.FAILED
        deployment.save(update_fields=['status'])
        raise Exception(error_msg)

    deployment_service.log(
        deployment,
        f"Docker container created and started: {create_result}",
        'success'
    )

    # Update deployment status
    deployment.status = ApplicationDeployment.Status.RUNNING
    deployment.save(update_fields=['status'])


def docker_health_check(context: Dict[str, Any]) -> None:
    """
    Health check hook for Docker deployments.

    This hook checks the status of Docker containers and adds
    Docker-specific health information to the context.
    """
    deployment = _get_deployment_from_context(context)
    if not deployment or not deployment.use_docker:
        return

    logger.info(f"Docker health check for {deployment.name}")

    docker_service = DockerService()
    container_status = docker_service.get_container_status(deployment.name)

    # Add Docker health info to context
    context['docker_health'] = {
        'container_exists': container_status.get('exists', False),
        'container_running': container_status.get('running', False),
        'container_status': container_status.get('status', 'unknown'),
        'container_health': container_status.get('health', 'none')
    }

    # If container is not running, mark as unhealthy
    if not container_status.get('running', False):
        context['healthy'] = False
        context['health_issues'] = context.get('health_issues', [])
        context['health_issues'].append('Docker container is not running')
