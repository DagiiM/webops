"""
LLM deployment service for vLLM models.

"Business Logic" section
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
from apps.core.integrations.services import HuggingFaceIntegrationService
from ..models import BaseDeployment, ApplicationDeployment, LLMDeployment, DeploymentLog
from .prerequisites import SystemPrerequisitesInstaller
from .autohealing import autohealer, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class LLMDeploymentService:
    """Service for managing LLM model deployments with vLLM."""

    def __init__(self):
        self.base_path = Path(settings.WEBOPS_INSTALL_PATH) / "llm-deployments"
        self.hf_service = HuggingFaceIntegrationService()

        # Set up Jinja2 for template rendering (use CLI templates directory)
        template_path = Path(__file__).parent.parent.parent.parent.parent / "cli" / "webops_cli" / "system-templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_path)))
        
        # Import template registry
        import sys
        sys.path.append(str(template_path))
        from template_registry import template_registry
        self.template_registry = template_registry

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

    def get_deployment_path(self, deployment: LLMDeployment) -> Path:
        """Get the file system path for an LLM deployment."""
        self.ensure_base_path()
        return self.base_path / deployment.name

    def get_model_cache_path(self, deployment: LLMDeployment) -> Path:
        """Get the model cache path (where HF models are downloaded)."""
        return self.get_deployment_path(deployment) / "model_cache"

    def get_venv_path(self, deployment: LLMDeployment) -> Path:
        """Get the virtual environment path for vLLM."""
        return self.get_deployment_path(deployment) / "venv"

    def log(
        self,
        deployment: LLMDeployment,
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

    def run_command_with_progress(
        self,
        deployment: LLMDeployment,
        cmd: list,
        description: str,
        cwd: str = None,
        env: dict = None,
        timeout: int = 3600
    ) -> bool:
        """
        Run command and stream output in real-time with progress logging.

        Args:
            deployment: Deployment instance
            cmd: Command and arguments as list
            description: Description of what's being done
            cwd: Working directory
            env: Environment variables
            timeout: Command timeout in seconds

        Returns:
            True if successful
        """
        import time
        import threading

        self.log(deployment, f"{description}...")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=cwd,
                env=env
            )

            # Keepalive mechanism: log every 60 seconds if no output
            last_output_time = time.time()
            keepalive_interval = 60  # seconds

            def keepalive_thread():
                while process.poll() is None:
                    time.sleep(keepalive_interval)
                    if time.time() - last_output_time > keepalive_interval:
                        elapsed = int(time.time() - last_output_time)
                        logger.info(f"[LLM:{deployment.name}] Still working on {description}... ({elapsed}s since last output)")

            # Start keepalive thread
            keepalive = threading.Thread(target=keepalive_thread, daemon=True)
            keepalive.start()

            # Stream output line by line
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                last_output_time = time.time()  # Update last output time
                line = line.strip()
                if line:
                    # Parse common progress indicators
                    if 'Downloading' in line or 'Installing' in line or 'Building' in line:
                        # Extract percentage if present
                        import re
                        percent_match = re.search(r'(\d+)%', line)
                        if percent_match:
                            self.log(deployment, f"{description}: {percent_match.group(1)}%")
                        else:
                            # Log the action without spamming
                            if any(keyword in line for keyword in ['Downloading', 'Installing collected packages', 'Successfully installed']):
                                logger.info(f"[LLM:{deployment.name}] {line}")
                    elif 'Successfully' in line or 'complete' in line.lower():
                        self.log(deployment, line, DeploymentLog.Level.SUCCESS)
                    elif 'error' in line.lower() or 'failed' in line.lower():
                        self.log(deployment, line, DeploymentLog.Level.ERROR)
                    else:
                        # Log important messages only
                        if any(keyword in line for keyword in ['Collecting', 'Requirement already satisfied', 'Installing', 'Cloning']):
                            logger.info(f"[LLM:{deployment.name}] {line}")

            process.wait(timeout=timeout)

            if process.returncode == 0:
                self.log(deployment, f"{description} completed successfully", DeploymentLog.Level.SUCCESS)
                return True
            else:
                self.log(deployment, f"{description} failed with exit code {process.returncode}", DeploymentLog.Level.ERROR)
                return False

        except subprocess.TimeoutExpired:
            process.kill()
            self.log(deployment, f"{description} timed out after {timeout} seconds", DeploymentLog.Level.ERROR)
            self.log(
                deployment,
                "Timeout occurred. You may need to delete this deployment and try again with a faster network connection or more system resources.",
                DeploymentLog.Level.ERROR
            )
            return False
        except Exception as e:
            self.log(deployment, f"{description} failed: {str(e)}", DeploymentLog.Level.ERROR)
            return False

    def check_build_dependencies(self, deployment: LLMDeployment) -> Tuple[bool, list]:
        """
        Check if required build dependencies are installed.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (all_present, list_of_missing)
        """
        required_tools = {
            'g++': 'C++ compiler (install with: sudo apt-get install build-essential)',
            'gcc': 'C compiler (install with: sudo apt-get install build-essential)',
            'cmake': 'CMake build system (install with: sudo apt-get install cmake)',
            'ninja': 'Ninja build tool (install with: sudo apt-get install ninja-build)',
            'python3': 'Python 3 interpreter',
        }

        missing = []

        for tool, description in required_tools.items():
            try:
                result = subprocess.run(
                    ['which', tool],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    missing.append(f"{tool}: {description}")
                    logger.warning(f"[LLM:{deployment.name}] Missing build tool: {tool}")
            except Exception as e:
                missing.append(f"{tool}: {description} (check failed: {e})")
                logger.error(f"[LLM:{deployment.name}] Error checking for {tool}: {e}")

        # Check for Python development headers
        try:
            import sysconfig
            python_version = f"python{sysconfig.get_python_version()}"
            include_dir = sysconfig.get_path('include')

            if not include_dir or not Path(include_dir).exists():
                missing.append(f"python3-dev: Python development headers (install with: sudo apt-get install {python_version}-dev)")
                logger.warning(f"[LLM:{deployment.name}] Missing Python development headers")
        except Exception as e:
            logger.warning(f"[LLM:{deployment.name}] Could not check Python headers: {e}")

        # Check for required system libraries
        required_packages = {
            'libnuma-dev': '/usr/include/numa.h',
            'libgomp1': '/usr/lib/x86_64-linux-gnu/libgomp.so.1',
        }

        for package, check_path in required_packages.items():
            if not Path(check_path).exists():
                missing.append(f"{package}: Required system library (install with: sudo apt-get install {package})")
                logger.warning(f"[LLM:{deployment.name}] Missing system library: {package}")

        return (len(missing) == 0, missing)

    def _format_size(self, bytes_val: int) -> str:
        """Format bytes into human-readable format."""
        if bytes_val >= 1_000_000_000:
            value = bytes_val / 1_000_000_000
            return f"{value:.1f}GB" if value < 100 else f"{int(value)}GB"
        elif bytes_val >= 1_000_000:
            value = bytes_val / 1_000_000
            return f"{value:.1f}MB" if value < 100 else f"{int(value)}MB"
        elif bytes_val >= 1_000:
            return f"{bytes_val / 1_000:.1f}KB"
        return f"{bytes_val}B"

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

    def create_vllm_environment(self, deployment: LLMDeployment) -> bool:
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

            self.log(deployment, "Installing CPU PyTorch and building vLLM from source")

            # Install CPU-only PyTorch and torchvision from the CPU wheel index
            self.log(deployment, "Step 1/7 (10%): Upgrading pip")
            if not self.run_command_with_progress(
                deployment,
                [str(pip_path), "install", "--upgrade", "pip", "--progress-bar", "on"],
                "Upgrading pip",
                timeout=600
            ):
                return False

            self.log(deployment, "Step 2/7 (20%): Installing CPU PyTorch (this may take 10-20 minutes)")
            if not self.run_command_with_progress(
                deployment,
                [str(pip_path), "install", "--extra-index-url", "https://download.pytorch.org/whl/cpu", "torch", "torchvision", "--progress-bar", "on"],
                "Installing PyTorch",
                timeout=1800
            ):
                return False

            self.log(deployment, "Step 3/7 (35%): Installing Hugging Face utilities")
            if not self.run_command_with_progress(
                deployment,
                [str(pip_path), "install", "huggingface_hub", "--progress-bar", "on"],
                "Installing Hugging Face utilities",
                timeout=600
            ):
                return False

            # Clone vLLM source and build for CPU
            deployment_path = self.get_deployment_path(deployment)
            repo_dir = deployment_path / "vllm_source"

            if not repo_dir.exists():
                self.log(deployment, "Step 4/7 (45%): Cloning vLLM source code")
                if not self.run_command_with_progress(
                    deployment,
                    ["git", "clone", "--progress", "https://github.com/vllm-project/vllm.git", str(repo_dir)],
                    "Cloning vLLM repository",
                    timeout=600
                ):
                    return False
            else:
                self.log(deployment, "Step 4/7 (45%): vLLM source already exists, skipping clone")

            # Install build requirements for CPU (prefer repo's cpu requirements if present)
            req_dir = repo_dir / "requirements"
            cpu_build_req = req_dir / "cpu-build.txt"
            cpu_req = req_dir / "cpu.txt"

            if cpu_build_req.exists():
                self.log(deployment, "Step 5/7 (55%): Installing CPU build requirements (this may take 15-30 minutes)")
                if not self.run_command_with_progress(
                    deployment,
                    [str(pip_path), "install", "-r", str(cpu_build_req), "--extra-index-url", "https://download.pytorch.org/whl/cpu", "--progress-bar", "off"],
                    "Installing CPU build requirements",
                    cwd=str(repo_dir),
                    timeout=2400  # Increased to 40 minutes
                ):
                    return False
            else:
                self.log(deployment, "Step 5/7 (55%): Installing fallback build requirements")
                if not self.run_command_with_progress(
                    deployment,
                    [str(pip_path), "install", "setuptools", "wheel", "numpy", "pybind11", "protobuf", "cmake", "ninja", "--progress-bar", "on"],
                    "Installing build requirements",
                    cwd=str(repo_dir),
                    timeout=1200
                ):
                    return False

            if cpu_req.exists():
                self.log(deployment, "Step 6/7 (70%): Installing CPU runtime requirements (this may take 30-60 minutes)")
                if not self.run_command_with_progress(
                    deployment,
                    [str(pip_path), "install", "-r", str(cpu_req), "--extra-index-url", "https://download.pytorch.org/whl/cpu", "--progress-bar", "off"],
                    "Installing CPU runtime requirements",
                    cwd=str(repo_dir),
                    timeout=3600  # Increased to 1 hour for heavy packages
                ):
                    return False
            else:
                self.log(deployment, "Step 6/7 (70%): Installing fallback runtime requirements")
                if not self.run_command_with_progress(
                    deployment,
                    [str(pip_path), "install", "fastapi", "uvicorn", "pydantic", "transformers", "sentencepiece", "--progress-bar", "on"],
                    "Installing runtime requirements",
                    cwd=str(repo_dir),
                    timeout=1200
                ):
                    return False

            # Build and install vLLM for CPU, disabling CUDA detection
            build_env = os.environ.copy()
            build_env["VLLM_TARGET_DEVICE"] = "cpu"
            build_env["CMAKE_DISABLE_FIND_PACKAGE_CUDA"] = "ON"

            self.log(deployment, "Step 7/7 (85%): Building vLLM from source (this may take 60-90 minutes)")
            if not self.run_command_with_progress(
                deployment,
                [str(pip_path), "install", ".", "--no-build-isolation", "--progress-bar", "off"],
                "Building vLLM from source",
                cwd=str(repo_dir),
                env=build_env,
                timeout=5400  # Increased to 90 minutes for large builds
            ):
                return False

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

    def download_model(self, deployment: LLMDeployment, max_retries: int = 3) -> bool:
        """
        Download Hugging Face model with authentication and auto-retry.

        Args:
            deployment: Deployment instance
            max_retries: Maximum number of retry attempts

        Returns:
            True if successful
        """
        def on_retry(attempt: int, error: Exception):
            """Callback for retry attempts."""
            self.log(
                deployment,
                f"Download attempt {attempt} failed: {error}. Retrying...",
                DeploymentLog.Level.WARNING
            )

        # Configure retry with exponential backoff
        retry_config = RetryConfig(
            max_attempts=max_retries,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=5.0,  # Start with 5 seconds
            max_delay=60.0,  # Cap at 1 minute
            on_retry=on_retry
        )

        # Wrap download in retry logic
        success, result, error = autohealer.retry_with_backoff(
            lambda: self._download_model_impl(deployment),
            retry_config,
            operation_name=f"download_{deployment.model_name}"
        )

        if not success and error:
            # Attempt auto-recovery
            self.log(
                deployment,
                "Attempting automatic recovery...",
                DeploymentLog.Level.INFO
            )
            success, result = autohealer.auto_recover(
                lambda: self._download_model_impl(deployment),
                error,
                operation_name=f"download_{deployment.model_name}"
            )

        return success

    def _download_model_impl(self, deployment: LLMDeployment) -> bool:
        """
        Internal implementation of model download.

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

        # Get total model size from HuggingFace API
        total_size = None
        try:
            from huggingface_hub import model_info

            self.log(deployment, "Fetching model information from HuggingFace...")
            model_info_data = model_info(
                deployment.model_name,
                token=hf_token if hf_token else None,
                files_metadata=True  # Required to get file sizes
            )

            # Sum up all file sizes
            if hasattr(model_info_data, 'siblings') and model_info_data.siblings:
                total_size = sum(
                    sibling.size for sibling in model_info_data.siblings
                    if hasattr(sibling, 'size') and sibling.size
                )

                if total_size:
                    formatted_total = self._format_size(total_size)
                    self.log(
                        deployment,
                        f"Model size: {formatted_total} ({len(model_info_data.siblings)} files)",
                        DeploymentLog.Level.INFO
                    )
        except Exception as e:
            logger.warning(f"Could not fetch model size from HuggingFace: {e}")
            self.log(
                deployment,
                "Could not determine model size in advance (will track progress during download)",
                DeploymentLog.Level.WARNING
            )

        # Check for existing partial download
        existing_size = 0
        try:
            existing_size = sum(f.stat().st_size for f in model_cache_path.rglob('*') if f.is_file())
            if existing_size > 1_000_000:  # More than 1MB exists
                formatted_size = self._format_size(existing_size)
                if total_size:
                    # Show progress with total
                    from decimal import Decimal, ROUND_HALF_UP
                    percentage = (existing_size / total_size * 100) if total_size > 0 else 0
                    percentage = float(Decimal(str(percentage)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
                    formatted_total = self._format_size(total_size)
                    self.log(
                        deployment,
                        f"Found existing download: {formatted_size}/{formatted_total} ({percentage}%). Resuming...",
                        DeploymentLog.Level.INFO
                    )
                else:
                    self.log(
                        deployment,
                        f"Found existing download ({formatted_size}). Resuming...",
                        DeploymentLog.Level.INFO
                    )
        except Exception as e:
            logger.debug(f"Could not check existing files: {e}")

        # Use huggingface-cli to download model
        venv_path = self.get_venv_path(deployment)
        python_path = venv_path / "bin" / "python"

        self.log(deployment, f"Downloading model {deployment.model_name} (this may take 10-60 minutes depending on model size)...")

        try:
            from decimal import Decimal, ROUND_HALF_UP

            # Download model using Python with file-based progress tracking
            download_script = f"""
import os
import sys
import time
from pathlib import Path
from huggingface_hub import snapshot_download

try:
    print("Starting model download...", flush=True)
    print("PROGRESS: 0%", flush=True)

    # Start download
    model_path = snapshot_download(
        repo_id="{deployment.model_name}",
        cache_dir="{model_cache_path}",
        token=os.environ.get('HF_TOKEN'),
        resume_download=True,
        local_files_only=False
    )

    print("PROGRESS: 100%", flush=True)
    print(f"Model downloaded successfully to {{model_path}}", flush=True)
except Exception as e:
    print(f"Download failed: {{e}}", flush=True)
    raise
"""

            # Run download process with environment that forces progress output
            download_env = env.copy()
            download_env['PYTHONUNBUFFERED'] = '1'
            download_env['HF_HUB_DISABLE_PROGRESS_BARS'] = '0'

            process = subprocess.Popen(
                [str(python_path), "-u", "-c", download_script],
                env=download_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Monitor cache directory size for progress estimation
            import threading
            import time

            download_complete = threading.Event()
            last_reported_size = 0
            estimated_total_size = total_size  # From HuggingFace API

            def format_bytes(bytes_val: int, total_bytes: Optional[int] = None) -> str:
                """
                Format bytes into human-readable format with appropriate unit.
                If total_bytes provided, uses the same unit for both for comparison.
                Returns format like "975MB/1.2GB ~ 81.3%" or just "975MB" if no total.
                """
                if total_bytes is None:
                    # Just format the single value
                    if bytes_val >= 1_000_000_000:  # GB
                        value = bytes_val / 1_000_000_000
                        if value >= 100:
                            return f"{int(value)}GB"
                        elif value >= 10:
                            return f"{value:.1f}GB"
                        else:
                            return f"{value:.2f}GB"
                    elif bytes_val >= 1_000_000:  # MB
                        value = bytes_val / 1_000_000
                        if value >= 100:
                            return f"{int(value)}MB"
                        elif value >= 10:
                            return f"{value:.1f}MB"
                        else:
                            return f"{value:.2f}MB"
                    elif bytes_val >= 1_000:  # KB
                        value = bytes_val / 1_000
                        return f"{value:.1f}KB"
                    else:
                        return f"{bytes_val}B"

                # Format each value with the most appropriate unit for readability
                # Example: 975MB/1.2GB ~ 81.3% (not 0.98GB/1.2GB)
                percentage = (bytes_val / total_bytes * 100) if total_bytes > 0 else 0
                # Use standard rounding (round half up) instead of banker's rounding
                percentage = float(Decimal(str(percentage)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))

                def format_single(size: int) -> str:
                    """Format a single size value with appropriate unit."""
                    if size >= 1_000_000_000:  # GB
                        val = size / 1_000_000_000
                        if val >= 100:
                            return f"{int(val)}GB"
                        else:
                            return f"{val:.1f}GB"
                    elif size >= 1_000_000:  # MB
                        val = size / 1_000_000
                        if val >= 100:
                            return f"{int(val)}MB"
                        else:
                            return f"{val:.1f}MB"
                    elif size >= 1_000:  # KB
                        val = size / 1_000
                        if val >= 100:
                            return f"{int(val)}KB"
                        else:
                            return f"{val:.1f}KB"
                    else:
                        return f"{size}B"

                current_str = format_single(bytes_val)
                total_str = format_single(total_bytes)

                return f"{current_str}/{total_str} ~ {percentage}%"

            def monitor_progress():
                nonlocal last_reported_size, estimated_total_size
                cache_path = Path(str(model_cache_path))
                last_size = 0
                no_change_count = 0
                report_threshold = 100 * 1_000_000  # Report every 100MB

                # Wait a bit for download to start
                time.sleep(2)

                while not download_complete.is_set():
                    try:
                        # Calculate total size of cache directory
                        current_size = sum(f.stat().st_size for f in cache_path.rglob('*') if f.is_file())

                        # If size is increasing, report progress
                        if current_size > last_size:
                            # Report if we've downloaded another 100MB since last report
                            if current_size - last_reported_size >= report_threshold:
                                if estimated_total_size:
                                    formatted_size = format_bytes(current_size, estimated_total_size)
                                    self.log(deployment, f"Download progress: {formatted_size}")
                                else:
                                    formatted_size = format_bytes(current_size)
                                    self.log(deployment, f"Downloaded {formatted_size}...")

                                logger.info(f"[LLM:{deployment.name}] Download progress: {formatted_size}")
                                last_reported_size = current_size

                            last_size = current_size
                            no_change_count = 0
                        else:
                            no_change_count += 1
                            # If no change for 60 seconds, log a keepalive
                            if no_change_count >= 12:  # 12 * 5 seconds = 60 seconds
                                current_formatted = format_bytes(current_size)
                                logger.info(f"[LLM:{deployment.name}] Download still in progress... ({current_formatted} downloaded)")
                                no_change_count = 0

                    except Exception as e:
                        logger.debug(f"Progress monitoring error: {e}")

                    time.sleep(5)  # Check every 5 seconds

            # Start progress monitoring thread
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()

            # Read output line by line for status updates
            stdout_lines = []
            stderr_lines = []

            def read_stdout():
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    line = line.strip()
                    stdout_lines.append(line)
                    if line.startswith('PROGRESS:'):
                        percentage = line.split('PROGRESS:')[1].strip()
                        self.log(deployment, f"Downloading model: {percentage}")
                    elif 'Fetching' in line or 'Downloading' in line:
                        logger.info(f"[LLM:{deployment.name}] {line}")
                    elif line:
                        if 'success' in line.lower():
                            self.log(deployment, line, DeploymentLog.Level.SUCCESS)
                        elif 'error' in line.lower() or 'failed' in line.lower():
                            self.log(deployment, line, DeploymentLog.Level.ERROR)
                        else:
                            logger.info(f"[LLM:{deployment.name}] {line}")

            def read_stderr():
                for line in iter(process.stderr.readline, ''):
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        stderr_lines.append(line)
                        # Log stderr (which may contain download progress from tqdm)
                        if 'Downloading' in line or '%' in line or 'B/s' in line:
                            logger.info(f"[LLM:{deployment.name}] {line}")
                        elif 'error' in line.lower() or 'failed' in line.lower():
                            logger.error(f"[LLM:{deployment.name}] {line}")

            # Start reader threads
            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            # Wait for process to complete
            process.wait(timeout=3600)

            # Signal progress monitoring to stop
            download_complete.set()
            monitor_thread.join(timeout=1)

            # Wait for reader threads to finish
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            if process.returncode != 0:
                # Capture error output for detailed error message
                error_output = '\n'.join(stderr_lines[-10:]) if stderr_lines else '\n'.join(stdout_lines[-10:])

                if "401" in error_output or "authentication" in error_output.lower():
                    self.log(
                        deployment,
                        "Model requires authentication. Please connect your Hugging Face account.",
                        DeploymentLog.Level.ERROR
                    )
                elif "404" in error_output or "not found" in error_output.lower():
                    self.log(
                        deployment,
                        f"Model {deployment.model_name} not found on Hugging Face",
                        DeploymentLog.Level.ERROR
                    )
                else:
                    self.log(
                        deployment,
                        f"Model download failed with exit code {process.returncode}",
                        DeploymentLog.Level.ERROR
                    )
                    if error_output:
                        self.log(deployment, f"Error output: {error_output}", DeploymentLog.Level.ERROR)

                return False

            self.log(
                deployment,
                f"Model {deployment.model_name} downloaded successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True

        except subprocess.TimeoutExpired:
            download_complete.set()
            self.log(
                deployment,
                "Model download timed out (model may be too large)",
                DeploymentLog.Level.ERROR
            )
            return False
        except Exception as e:
            download_complete.set()
            self.log(
                deployment,
                f"Model download failed: {str(e)}",
                DeploymentLog.Level.ERROR
            )
            return False

    def render_vllm_systemd_service(self, deployment: LLMDeployment) -> str:
        """
        Render systemd service file for vLLM server.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered systemd service configuration
        """
        venv_path = self.get_venv_path(deployment)
        model_cache_path = self.get_model_cache_path(deployment)
        
        # Use template registry to get appropriate template
        template_path = self.template_registry.get_template_path('vllm_cpu', 'systemd')
        if not template_path:
            # Fallback to unified template
            template_path = 'unified/systemd/unified.service.j2'
        
        template = self.jinja_env.get_template(template_path)

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
            'working_directory': str(self.get_deployment_path(deployment)),
            'ld_preload': ld_preload,
            'service_type_name': 'vllm',
            'service_subtype': 'cpu',
            'app_env_vars': {
                'HF_HOME': str(model_cache_path),
                'TRANSFORMERS_CACHE': str(model_cache_path),
                'VLLM_TARGET_DEVICE': 'cpu',
                'CMAKE_DISABLE_FIND_PACKAGE_CUDA': 'ON',
                'VLLM_LOGGING_LEVEL': 'DEBUG',
                'LD_PRELOAD': ld_preload if ld_preload else '',
            },
            'restart_policy': 'always',
            'restart_sec': '10s',
        }

        return template.render(**context)

    def render_nginx_config(self, deployment: LLMDeployment) -> str:
        """
        Render Nginx configuration for LLM API endpoint.

        Args:
            deployment: Deployment instance

        Returns:
            Rendered Nginx configuration
        """
        # Use template registry for LLM nginx config
        template_path = self.template_registry.get_template_path('vllm_cpu', 'nginx')
        if not template_path:
            # Fallback to unified template
            template_path = 'unified/nginx/unified.conf.j2'
        
        template = self.jinja_env.get_template(template_path)

        context = {
            'app_name': deployment.name,
            'domain': deployment.domain,
            'port': deployment.port,
            'model_name': deployment.model_name,
            'app_type': 'llm',
            'http_port': 80,
            'ssl_enabled': bool(deployment.domain),
            'access_log_path': f'/var/log/nginx/{deployment.name}-access.log',
            'error_log_path': f'/var/log/nginx/{deployment.name}-error.log',
            'proxy_connect_timeout': '60s',
            'proxy_send_timeout': '600s',  # LLMs need longer timeouts for streaming
            'proxy_read_timeout': '600s',  # LLMs need longer timeouts for streaming
        }

        return template.render(**context)

    def get_used_ports(self) -> set:
        """Get all currently used ports."""
        return set(
            ApplicationDeployment.objects
            .exclude(port__isnull=True)
            .values_list('port', flat=True)
        )

    def allocate_port(self, deployment: LLMDeployment) -> int:
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

    def prepare_llm_deployment(self, deployment: LLMDeployment) -> Tuple[bool, str]:
        """
        Prepare LLM deployment (setup environment, download model).

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Update status
            deployment.status = ApplicationDeployment.Status.BUILDING
            deployment.save(update_fields=['status'])

            # Validate model name
            if not self.validate_model_name(deployment.model_name):
                error_msg = f"Invalid model name format: {deployment.model_name}"
                self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
                deployment.status = ApplicationDeployment.Status.FAILED
                deployment.save(update_fields=['status'])
                return False, error_msg

            # Check and install build dependencies
            self.log(deployment, "Checking system build dependencies...")
            installer = SystemPrerequisitesInstaller()
            all_present, missing_packages = installer.check_all_prerequisites()

            if not all_present:
                self.log(
                    deployment,
                    f"Found {len(missing_packages)} missing prerequisites",
                    DeploymentLog.Level.WARNING
                )

                # Attempt automatic installation if sudo is available
                if installer.sudo_available:
                    self.log(
                        deployment,
                        "Attempting automatic installation of missing prerequisites...",
                        DeploymentLog.Level.INFO
                    )

                    success, errors = installer.install_all_prerequisites(missing_packages)

                    if success:
                        self.log(
                            deployment,
                            "All prerequisites installed successfully ✓",
                            DeploymentLog.Level.SUCCESS
                        )
                    else:
                        error_msg = "Failed to install some prerequisites:\n" + "\n".join(errors)
                        self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
                        self.log(
                            deployment,
                            installer.get_installation_instructions(missing_packages),
                            DeploymentLog.Level.ERROR
                        )
                        deployment.status = ApplicationDeployment.Status.FAILED
                        deployment.save(update_fields=['status'])
                        return False, error_msg
                else:
                    # No sudo access - provide manual instructions
                    error_msg = installer.get_installation_instructions(missing_packages)
                    self.log(deployment, "Build dependency check FAILED", DeploymentLog.Level.ERROR)
                    self.log(deployment, error_msg, DeploymentLog.Level.ERROR)
                    self.log(deployment, installer.get_sudo_setup_instructions(), DeploymentLog.Level.INFO)
                    deployment.status = ApplicationDeployment.Status.FAILED
                    deployment.save(update_fields=['status'])
                    return False, error_msg
            else:
                self.log(deployment, "All build dependencies present ✓", DeploymentLog.Level.SUCCESS)

            # Allocate port
            self.allocate_port(deployment)

            # Create vLLM environment
            if not self.create_vllm_environment(deployment):
                deployment.status = ApplicationDeployment.Status.FAILED
                deployment.save(update_fields=['status'])
                return False, "Failed to create vLLM environment"

            # Download model
            if not self.download_model(deployment):
                deployment.status = ApplicationDeployment.Status.FAILED
                deployment.save(update_fields=['status'])
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
            deployment.status = ApplicationDeployment.Status.FAILED
            deployment.save(update_fields=['status'])
            return False, error_msg

    def deploy_llm(self, deployment: LLMDeployment) -> Dict[str, Any]:
        """
        Complete LLM deployment process.

        Args:
            deployment: Deployment instance

        Returns:
            Dictionary with deployment result
        """
        from ..shared.service_manager import ServiceManager

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
                f"Service creation failed: {service_msg}",
                DeploymentLog.Level.ERROR
            )
            deployment.status = ApplicationDeployment.Status.FAILED
            deployment.save(update_fields=['status'])

            return {
                'success': False,
                'error': service_msg,
                'deployment_id': deployment.id
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
            deployment.status = ApplicationDeployment.Status.FAILED
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
