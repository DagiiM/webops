"""
LLM deployment service for vLLM models.

Reference: CLAUDE.md "Business Logic" section
Architecture: LLM model deployment using vLLM for efficient inference

This module implements LLM-specific deployment logic:
- Hugging Face model downloading
- vLLM configuration and setup
- GPU resource management
- Model serving with OpenAI-compatible API
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from django.conf import settings
from jinja2 import Environment, FileSystemLoader
import logging

from apps.core.utils import generate_port
from apps.core.integration_services import HuggingFaceIntegrationService
from .models import Deployment, DeploymentLog

logger = logging.getLogger(__name__)


class LLMDeploymentService:
    """Service for managing LLM model deployments with vLLM."""

    def __init__(self):
        self.base_path = Path(settings.WEBOPS_INSTALL_PATH) / "llm-deployments"
        self.hf_service = HuggingFaceIntegrationService()

        # Set up Jinja2 for template rendering (use control-panel templates)
        template_path = Path(__file__).parent.parent.parent / "system-templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_path)))

    def ensure_base_path(self) -> bool:
        """
        Ensure base LLM deployment path exists.

        Returns:
            True if path exists or was created successfully
        """
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            return True
        except PermissionError:
            logger.error(f"Permission denied creating {self.base_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to create base path {self.base_path}: {e}")
            return False

    def get_deployment_path(self, deployment: Deployment) -> Path:
        """Get the file system path for an LLM deployment."""
        self.ensure_base_path()
        return self.base_path / deployment.name

    def get_model_cache_path(self, deployment: Deployment) -> Path:
        """Get the model cache path (where HF models are downloaded)."""
        return self.get_deployment_path(deployment) / "model_cache"

    def get_venv_path(self, deployment: Deployment) -> Path:
        """Get the virtual environment path for vLLM."""
        return self.get_deployment_path(deployment) / "venv"

    def log(
        self,
        deployment: Deployment,
        message: str,
        level: str = DeploymentLog.Level.INFO
    ) -> None:
        """
        Log a deployment message.

        Args:
            deployment: Deployment instance
            message: Log message
            level: Log level (info, warning, error, success)
        """
        DeploymentLog.objects.create(
            deployment=deployment,
            level=level,
            message=message
        )
        logger.info(f"[LLM:{deployment.name}] {message}")

    def validate_model_name(self, model_name: str) -> bool:
        """
        Validate Hugging Face model name format.

        Accepts both formats:
        - Simple: 'gpt2', 'bert-base-uncased' (community/popular models)
        - Full: 'organization/model-name' (e.g., meta-llama/Llama-2-7b-chat-hf)

        Args:
            model_name: Model identifier

        Returns:
            True if valid format
        """
        if not model_name or not model_name.strip():
            return False

        # Check for basic validity (alphanumeric, hyphens, underscores, slashes, dots)
        import re
        if not re.match(r'^[a-zA-Z0-9\-_./]+$', model_name):
            return False

        # If it contains a slash, validate organization/model format
        if '/' in model_name:
            parts = model_name.split('/')
            if len(parts) != 2:
                return False

            org, model = parts
            if not org or not model:
                return False

        return True

    def create_vllm_environment(self, deployment: Deployment) -> bool:
        """
        Create Python virtual environment with vLLM.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful
        """
        deployment_path = self.get_deployment_path(deployment)
        deployment_path.mkdir(parents=True, exist_ok=True)

        venv_path = self.get_venv_path(deployment)

        if venv_path.exists():
            self.log(deployment, "Virtual environment already exists")
            return True

        self.log(deployment, "Creating vLLM virtual environment (CPU build)")

        try:
            # Create virtual environment
            subprocess.run(
                ["python3", "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True
            )

            # Upgrade pip
            pip_path = venv_path / "bin" / "pip"
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            self.log(deployment, "Installing CPU PyTorch and building vLLM from source")

            # Install CPU-only PyTorch and torchvision from the CPU wheel index
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=600
            )

            subprocess.run(
                [str(pip_path), "install", "--extra-index-url", "https://download.pytorch.org/whl/cpu", "torch", "torchvision"],
                check=True,
                capture_output=True,
                text=True,
                timeout=1800
            )

            # Hugging Face utilities
            subprocess.run(
                [str(pip_path), "install", "huggingface_hub"],
                check=True,
                capture_output=True,
                text=True,
                timeout=600
            )

            # Clone vLLM source and build for CPU
            deployment_path = self.get_deployment_path(deployment)
            repo_dir = deployment_path / "vllm_source"

            if not repo_dir.exists():
                subprocess.run(
                    ["git", "clone", "https://github.com/vllm-project/vllm.git", str(repo_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600
                )

            # Install build requirements for CPU (prefer repo's cpu requirements if present)
            req_dir = repo_dir / "requirements"
            cpu_build_req = req_dir / "cpu-build.txt"
            cpu_req = req_dir / "cpu.txt"

            if cpu_build_req.exists():
                subprocess.run(
                    [str(pip_path), "install", "-v", "-r", str(cpu_build_req), "--extra-index-url", "https://download.pytorch.org/whl/cpu"],
                    cwd=str(repo_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1800
                )
            else:
                # Fallback: install baseline build toolchain commonly required
                subprocess.run(
                    [str(pip_path), "install", "setuptools", "wheel", "numpy", "pybind11", "protobuf", "cmake", "ninja"],
                    cwd=str(repo_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1200
                )

            if cpu_req.exists():
                subprocess.run(
                    [str(pip_path), "install", "-v", "-r", str(cpu_req), "--extra-index-url", "https://download.pytorch.org/whl/cpu"],
                    cwd=str(repo_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1800
                )
            else:
                # Fallback: install minimal runtime deps typically needed
                subprocess.run(
                    [str(pip_path), "install", "fastapi", "uvicorn", "pydantic", "transformers", "sentencepiece"],
                    cwd=str(repo_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=1200
                )

            # Build and install vLLM for CPU, disabling CUDA detection
            build_env = os.environ.copy()
            build_env["VLLM_TARGET_DEVICE"] = "cpu"
            build_env["CMAKE_DISABLE_FIND_PACKAGE_CUDA"] = "ON"

            subprocess.run(
                [str(pip_path), "install", ".", "--no-build-isolation"],
                cwd=str(repo_dir),
                env=build_env,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600
            )

            self.log(
                deployment,
                "vLLM CPU environment created successfully from source",
                DeploymentLog.Level.SUCCESS
            )
            return True

        except subprocess.TimeoutExpired:
            self.log(
                deployment,
                "vLLM installation timed out",
                DeploymentLog.Level.ERROR
            )
            return False
        except subprocess.CalledProcessError as e:
            self.log(
                deployment,
                f"Failed to create vLLM environment: {e.stderr}",
                DeploymentLog.Level.ERROR
            )
            return False

    def download_model(self, deployment: Deployment) -> bool:
        """
        Download Hugging Face model with authentication if needed.

        Args:
            deployment: Deployment instance

        Returns:
            True if successful
        """
        self.log(deployment, f"Preparing to download model: {deployment.model_name}")

        # Get HF token if user has connected their account
        hf_token = self.hf_service.get_access_token(deployment.deployed_by)

        # Set up environment for download
        env = os.environ.copy()
        model_cache_path = self.get_model_cache_path(deployment)
        model_cache_path.mkdir(parents=True, exist_ok=True)

        env['HF_HOME'] = str(model_cache_path)
        env['TRANSFORMERS_CACHE'] = str(model_cache_path)

        if hf_token:
            env['HF_TOKEN'] = hf_token
            self.log(deployment, "Using authenticated Hugging Face access")
        else:
            self.log(
                deployment,
                "No Hugging Face token found - only public models can be downloaded",
                DeploymentLog.Level.WARNING
            )

        # Use huggingface-cli to download model
        venv_path = self.get_venv_path(deployment)
        python_path = venv_path / "bin" / "python"

        self.log(deployment, "Downloading model files (this may take a while)...")

        try:
            # Download model using Python
            download_script = f"""
import os
from huggingface_hub import snapshot_download

try:
    model_path = snapshot_download(
        repo_id="{deployment.model_name}",
        cache_dir="{model_cache_path}",
        token=os.environ.get('HF_TOKEN')
    )
    print(f"Model downloaded successfully to {{model_path}}")
except Exception as e:
    print(f"Download failed: {{e}}")
    raise
"""

            result = subprocess.run(
                [str(python_path), "-c", download_script],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout for large models
            )

            self.log(
                deployment,
                f"Model {deployment.model_name} downloaded successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True

        except subprocess.TimeoutExpired:
            self.log(
                deployment,
                "Model download timed out (model may be too large)",
                DeploymentLog.Level.ERROR
            )
            return False
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)

            if "401" in error_msg or "authentication" in error_msg.lower():
                self.log(
                    deployment,
                    "Model requires authentication. Please connect your Hugging Face account.",
                    DeploymentLog.Level.ERROR
                )
            elif "404" in error_msg or "not found" in error_msg.lower():
                self.log(
                    deployment,
                    f"Model {deployment.model_name} not found on Hugging Face",
                    DeploymentLog.Level.ERROR
                )
            else:
                self.log(
                    deployment,
                    f"Model download failed: {error_msg}",
                    DeploymentLog.Level.ERROR
                )
            return False

    def render_vllm_systemd_service(self, deployment: Deployment) -> str:
        """
        Render systemd service file for vLLM server.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered systemd service configuration
        """
        venv_path = self.get_venv_path(deployment)
        model_cache_path = self.get_model_cache_path(deployment)
        template = self.jinja_env.get_template('systemd/vllm_cpu.service.j2')

        # Build vLLM command arguments (CPU runtime)
        # Use a safe default dtype for CPU if 'auto' is selected
        dtype = deployment.dtype if deployment.dtype != 'auto' else 'float32'

        vllm_args = [
            f"--model {deployment.model_name}",
            f"--port {deployment.port}",
            "--device cpu",
            f"--dtype {dtype}",
        ]

        if deployment.max_model_len:
            vllm_args.append(f"--max-model-len {deployment.max_model_len}")

        # Quantization methods like AWQ/GPTQ are GPU-focused; skip on CPU
        if deployment.quantization:
            self.log(
                deployment,
                f"Quantization '{deployment.quantization}' is not applied for CPU runtime",
                DeploymentLog.Level.WARNING
            )

        # Add trust-remote-code for certain models
        vllm_args.append("--trust-remote-code")

        # Detect allocator library for better CPU performance (optional)
        def _find_allocator() -> Optional[str]:
            candidates = [
                "/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4",
                "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2",
                "/usr/lib/x86_64-linux-gnu/libjemalloc.so.1",
                "/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4",
                "/lib/x86_64-linux-gnu/libjemalloc.so.2",
                "/usr/lib/libjemalloc.so",
                "/usr/lib/libtcmalloc_minimal.so",
                "/lib/libjemalloc.so",
                "/lib/libtcmalloc_minimal.so",
            ]
            for p in candidates:
                try:
                    if os.path.exists(p):
                        return p
                except Exception:
                    continue
            return None

        ld_preload = _find_allocator()

        context = {
            'app_name': deployment.name,
            'webops_user': settings.WEBOPS_USER,
            'venv_path': str(venv_path),
            'python_path': str(venv_path / "bin" / "python"),
            'model_name': deployment.model_name,
            'port': deployment.port,
            'model_cache_path': str(model_cache_path),
            'vllm_args': ' '.join(vllm_args),
            'log_path': str(self.get_deployment_path(deployment) / 'logs'),
            'logging_level': 'DEBUG',
            'work_dir': str(self.get_deployment_path(deployment)),
            'ld_preload': ld_preload,
        }

        return template.render(**context)

    def render_nginx_config(self, deployment: Deployment) -> str:
        """
        Render Nginx configuration for LLM API endpoint.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered Nginx configuration
        """
        template = self.jinja_env.get_template('nginx/llm.conf.j2')

        context = {
            'app_name': deployment.name,
            'domain': deployment.domain,
            'port': deployment.port,
            'model_name': deployment.model_name,
        }

        return template.render(**context)

    def get_used_ports(self) -> set:
        """Get all currently used ports."""
        return set(
            Deployment.objects
            .exclude(port__isnull=True)
            .values_list('port', flat=True)
        )

    def allocate_port(self, deployment: Deployment) -> int:
        """
        Allocate a port for the LLM deployment.

        Args:
            deployment: Deployment instance

        Returns:
            Allocated port number
        """
        if deployment.port:
            return deployment.port

        used_ports = self.get_used_ports()
        port = generate_port(used_ports, min_port=9001, max_port=9999)
        deployment.port = port
        deployment.save(update_fields=['port'])

        self.log(deployment, f"Allocated port: {port}")
        return port

    def prepare_llm_deployment(self, deployment: Deployment) -> Tuple[bool, str]:
        """
        Prepare LLM deployment (setup environment, download model).

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Update status
            deployment.status = Deployment.Status.BUILDING
            deployment.save(update_fields=['status'])

            # Validate model name
            if not self.validate_model_name(deployment.model_name):
                error_msg = f"Invalid model name format: {deployment.model_name}"
                self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
                return False, error_msg

            # Allocate port
            self.allocate_port(deployment)

            # Create vLLM environment
            if not self.create_vllm_environment(deployment):
                return False, "Failed to create vLLM environment"

            # Download model
            if not self.download_model(deployment):
                return False, "Failed to download model"

            self.log(
                deployment,
                "LLM deployment prepared successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, ""

        except Exception as e:
            error_msg = f"LLM deployment preparation failed: {str(e)}"
            self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])
            return False, error_msg

    def deploy_llm(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Complete LLM deployment process.

        Args:
            deployment: Deployment instance

        Returns:
            Dictionary with deployment result
        """
        from .service_manager import ServiceManager

        self.log(deployment, "Starting LLM deployment process")

        # Prepare deployment
        success, error = self.prepare_llm_deployment(deployment)

        if not success:
            return {
                'success': False,
                'error': error,
                'deployment_id': deployment.id
            }

        # Create service manager
        service_manager = ServiceManager()

        # Create systemd service
        self.log(deployment, "Creating vLLM systemd service")
        service_config = self.render_vllm_systemd_service(deployment)
        service_success, service_msg = service_manager.install_service(
            deployment,
            service_config
        )

        if not service_success:
            self.log(
                deployment,
                f"Service creation skipped (dev mode): {service_msg}",
                DeploymentLog.Level.WARNING
            )
            deployment.status = Deployment.Status.PENDING
            deployment.save(update_fields=['status'])

            return {
                'success': True,
                'deployment_id': deployment.id,
                'port': deployment.port,
                'status': deployment.status,
                'message': 'LLM deployment prepared (service creation requires sudo)'
            }

        # Create Nginx configuration for API access
        self.log(deployment, "Creating Nginx configuration")
        nginx_config = self.render_nginx_config(deployment)
        nginx_success, nginx_msg = service_manager.install_nginx_config(
            deployment,
            nginx_config
        )

        if nginx_success:
            service_manager.reload_nginx(deployment)

        # Enable and start service
        service_manager.enable_service(deployment)
        start_success, start_msg = service_manager.start_service(deployment)

        if not start_success:
            self.log(
                deployment,
                f"Failed to start vLLM service: {start_msg}",
                DeploymentLog.Level.ERROR
            )
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])

            return {
                'success': False,
                'error': start_msg,
                'deployment_id': deployment.id
            }

        self.log(
            deployment,
            f"LLM model {deployment.model_name} deployed successfully!",
            DeploymentLog.Level.SUCCESS
        )

        return {
            'success': True,
            'deployment_id': deployment.id,
            'port': deployment.port,
            'status': deployment.status,
            'model_name': deployment.model_name,
            'message': f'LLM model serving on port {deployment.port}'
        }
