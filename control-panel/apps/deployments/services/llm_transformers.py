"""
Transformers-based LLM deployment service (CPU-optimized, fast setup).

This backend uses HuggingFace Transformers library with a lightweight
FastAPI server for quick deployment on CPU.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
from django.conf import settings
from jinja2 import Environment, FileSystemLoader
import logging

from apps.core.utils import generate_port
from apps.core.integrations.services import HuggingFaceIntegrationService
from ..models import LLMDeployment, DeploymentLog

logger = logging.getLogger(__name__)


class TransformersLLMService:
    """Service for deploying LLMs using Transformers backend."""

    def __init__(self):
        self.base_path = Path(settings.WEBOPS_INSTALL_PATH) / "llm-deployments"
        self.hf_service = HuggingFaceIntegrationService()

        # Set up Jinja2 for template rendering
        template_path = Path(__file__).parent.parent.parent.parent.parent / "cli" / "webops_cli" / "system-templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(template_path)))

    def get_deployment_path(self, deployment: LLMDeployment) -> Path:
        """Get the file system path for deployment."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        return self.base_path / deployment.name

    def get_model_cache_path(self, deployment: LLMDeployment) -> Path:
        """Get the model cache path."""
        return self.get_deployment_path(deployment) / "model_cache"

    def get_venv_path(self, deployment: LLMDeployment) -> Path:
        """Get the virtual environment path."""
        return self.get_deployment_path(deployment) / "venv"

    def log(
        self,
        deployment: LLMDeployment,
        message: str,
        level: str = DeploymentLog.Level.INFO
    ) -> None:
        """Log a deployment message."""
        DeploymentLog.objects.create(
            deployment=deployment,
            level=level,
            message=message
        )
        logger.info(f"[Transformers:{deployment.name}] {message}")

    def create_transformers_environment(self, deployment: LLMDeployment) -> bool:
        """
        Create Python virtual environment with Transformers (fast!).

        Returns:
            True if successful
        """
        deployment_path = self.get_deployment_path(deployment)
        deployment_path.mkdir(parents=True, exist_ok=True)

        venv_path = self.get_venv_path(deployment)

        if venv_path.exists():
            self.log(deployment, "Virtual environment already exists")
            return True

        self.log(deployment, "Creating Transformers virtual environment (this will be quick!)")

        try:
            # Create virtual environment
            self.log(deployment, "Step 1/3 (33%): Creating Python virtual environment")
            subprocess.run(
                ["python3", "-m", "venv", str(venv_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            self.log(deployment, "Step 1/3 completed", DeploymentLog.Level.SUCCESS)

            # Upgrade pip
            pip_path = venv_path / "bin" / "pip"
            self.log(deployment, "Step 2/3 (66%): Installing dependencies")
            subprocess.run(
                [str(pip_path), "install", "--upgrade", "pip"],
                check=True,
                capture_output=True,
                text=True,
                timeout=300
            )

            # Install transformers and dependencies (no torch build, use CPU version)
            self.log(deployment, "Installing transformers, torch (CPU), accelerate, fastapi, uvicorn...")
            subprocess.run(
                [str(pip_path), "install",
                 "transformers",
                 "torch",
                 "accelerate",
                 "sentencepiece",
                 "protobuf",
                 "fastapi",
                 "uvicorn[standard]",
                 "python-multipart",
                 "pydantic"],
                check=True,
                capture_output=True,
                text=True,
                timeout=900  # 15 minutes max
            )
            self.log(deployment, "Step 2/3 completed - Dependencies installed", DeploymentLog.Level.SUCCESS)

            # Create server script
            self.log(deployment, "Step 3/3 (100%): Creating server script")
            self.create_server_script(deployment)
            self.log(deployment, "Step 3/3 completed", DeploymentLog.Level.SUCCESS)

            self.log(
                deployment,
                "Transformers environment created successfully!",
                DeploymentLog.Level.SUCCESS
            )
            return True

        except subprocess.TimeoutExpired:
            self.log(deployment, "Installation timed out", DeploymentLog.Level.ERROR)
            return False
        except subprocess.CalledProcessError as e:
            self.log(
                deployment,
                f"Failed to create environment: {e.stderr if e.stderr else str(e)}",
                DeploymentLog.Level.ERROR
            )
            return False

    def create_server_script(self, deployment: LLMDeployment) -> None:
        """Create a simple FastAPI server script for the model."""
        server_script = self.get_deployment_path(deployment) / "server.py"

        script_content = f'''#!/usr/bin/env python3
"""
Simple FastAPI server for {deployment.model_name}
"""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# Set cache directory
os.environ['HF_HOME'] = '{self.get_model_cache_path(deployment)}'
os.environ['TRANSFORMERS_CACHE'] = '{self.get_model_cache_path(deployment)}'

app = FastAPI(title="{deployment.name}", description="LLM API powered by Transformers")

# Global model and tokenizer
model = None
tokenizer = None
text_generator = None


class CompletionRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 100
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    stop: Optional[List[str]] = None


class CompletionResponse(BaseModel):
    text: str
    model: str
    finish_reason: str


@app.on_event("startup")
async def load_model():
    """Load model on startup."""
    global model, tokenizer, text_generator

    print(f"Loading model: {deployment.model_name}")
    print("This may take a few minutes for large models...")

    try:
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            "{deployment.model_name}",
            cache_dir=os.environ['TRANSFORMERS_CACHE'],
            trust_remote_code=True
        )

        # Load model
        model = AutoModelForCausalLM.from_pretrained(
            "{deployment.model_name}",
            cache_dir=os.environ['TRANSFORMERS_CACHE'],
            torch_dtype=torch.{deployment.dtype if deployment.dtype != 'auto' else 'float32'},
            device_map="cpu",
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )

        # Create pipeline for easier inference
        text_generator = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device="cpu"
        )

        print(f"Model {deployment.model_name} loaded successfully!")

    except Exception as e:
        print(f"Error loading model: {{e}}")
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {{
        "status": "ready",
        "model": "{deployment.model_name}",
        "backend": "transformers"
    }}


@app.get("/health")
async def health():
    """Health check."""
    return {{"status": "healthy", "model_loaded": model is not None}}


@app.post("/v1/completions")
async def create_completion(request: CompletionRequest) -> CompletionResponse:
    """Generate text completion."""
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        # Generate
        outputs = text_generator(
            request.prompt,
            max_new_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

        generated_text = outputs[0]['generated_text']

        # Remove prompt from output
        if generated_text.startswith(request.prompt):
            generated_text = generated_text[len(request.prompt):]

        return CompletionResponse(
            text=generated_text,
            model="{deployment.model_name}",
            finish_reason="stop"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port={deployment.port or 8000})
'''

        server_script.write_text(script_content)
        server_script.chmod(0o755)

    def download_model(self, deployment: LLMDeployment) -> bool:
        """
        Download Hugging Face model.

        Returns:
            True if successful
        """
        self.log(deployment, f"Downloading model: {deployment.model_name}")

        # Get HF token if available
        hf_token = self.hf_service.get_access_token(deployment.deployed_by)

        # Set up environment
        env = os.environ.copy()
        model_cache_path = self.get_model_cache_path(deployment)
        model_cache_path.mkdir(parents=True, exist_ok=True)

        env['HF_HOME'] = str(model_cache_path)
        env['TRANSFORMERS_CACHE'] = str(model_cache_path)

        if hf_token:
            env['HF_TOKEN'] = hf_token
            self.log(deployment, "Using authenticated Hugging Face access")

        venv_path = self.get_venv_path(deployment)
        python_path = venv_path / "bin" / "python"

        self.log(deployment, "Downloading model files...")

        try:
            # Download using transformers
            download_script = f"""
from transformers import AutoTokenizer, AutoModelForCausalLM
import os

print("Downloading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    "{deployment.model_name}",
    cache_dir="{model_cache_path}",
    token=os.environ.get('HF_TOKEN'),
    trust_remote_code=True
)

print("Downloading model (this may take a while)...")
model = AutoModelForCausalLM.from_pretrained(
    "{deployment.model_name}",
    cache_dir="{model_cache_path}",
    token=os.environ.get('HF_TOKEN'),
    trust_remote_code=True
)

print("Model downloaded successfully!")
"""

            subprocess.run(
                [str(python_path), "-c", download_script],
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour for large models
            )

            self.log(
                deployment,
                f"Model {deployment.model_name} downloaded successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True

        except subprocess.TimeoutExpired:
            self.log(deployment, "Model download timed out", DeploymentLog.Level.ERROR)
            return False
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)

            if "401" in error_msg or "authentication" in error_msg.lower():
                self.log(
                    deployment,
                    "Model requires authentication. Please connect your Hugging Face account.",
                    DeploymentLog.Level.ERROR
                )
            else:
                self.log(
                    deployment,
                    f"Model download failed: {error_msg}",
                    DeploymentLog.Level.ERROR
                )
            return False

    def deploy_transformers(self, deployment: LLMDeployment) -> Dict[str, Any]:
        """
        Complete Transformers deployment process.

        Returns:
            Dictionary with deployment result
        """
        from ..shared.service_manager import ServiceManager

        self.log(deployment, "Starting Transformers LLM deployment")

        # Allocate port
        if not deployment.port:
            used_ports = set(
                LLMDeployment.objects
                .exclude(pk=deployment.pk)
                .exclude(port__isnull=True)
                .values_list('port', flat=True)
            )
            port = generate_port(used_ports, min_port=9001, max_port=9999)
            deployment.port = port
            deployment.save(update_fields=['port'])
            self.log(deployment, f"Allocated port: {port}")

        # Update status
        deployment.status = 'building'
        deployment.save(update_fields=['status'])

        # Create environment
        if not self.create_transformers_environment(deployment):
            deployment.status = 'failed'
            deployment.save(update_fields=['status'])
            return {'success': False, 'error': 'Failed to create environment'}

        # Download model
        if not self.download_model(deployment):
            deployment.status = 'failed'
            deployment.save(update_fields=['status'])
            return {'success': False, 'error': 'Failed to download model'}

        # Create systemd service
        service_manager = ServiceManager()
        self.log(deployment, "Creating systemd service")

        service_config = self.render_systemd_service(deployment)
        service_success, service_msg = service_manager.install_service(
            deployment,
            service_config
        )

        if not service_success:
            self.log(deployment, f"Service creation failed: {service_msg}", DeploymentLog.Level.ERROR)
            deployment.status = 'failed'
            deployment.save(update_fields=['status'])
            return {'success': False, 'error': service_msg}

        # Start service
        service_manager.enable_service(deployment)
        start_success, start_msg = service_manager.start_service(deployment)

        if not start_success:
            self.log(deployment, f"Failed to start service: {start_msg}", DeploymentLog.Level.ERROR)
            deployment.status = 'failed'
            deployment.save(update_fields=['status'])
            return {'success': False, 'error': start_msg}

        self.log(
            deployment,
            f"LLM model {deployment.model_name} deployed successfully with Transformers backend!",
            DeploymentLog.Level.SUCCESS
        )

        deployment.status = 'running'
        deployment.save(update_fields=['status'])

        return {
            'success': True,
            'deployment_id': deployment.id,
            'port': deployment.port,
            'status': deployment.status,
            'model_name': deployment.model_name,
            'backend': 'transformers',
            'message': f'LLM model serving on port {deployment.port}'
        }

    def render_systemd_service(self, deployment: LLMDeployment) -> str:
        """Render systemd service file for Transformers server."""
        venv_path = self.get_venv_path(deployment)
        server_script = self.get_deployment_path(deployment) / "server.py"

        # Use simple template
        service_content = f"""[Unit]
Description={deployment.name} - Transformers LLM Server
After=network.target

[Service]
Type=simple
User={settings.WEBOPS_USER}
WorkingDirectory={self.get_deployment_path(deployment)}
Environment="PATH={venv_path}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="HF_HOME={self.get_model_cache_path(deployment)}"
Environment="TRANSFORMERS_CACHE={self.get_model_cache_path(deployment)}"
ExecStart={venv_path}/bin/python {server_script}
Restart=always
RestartSec=10s
StandardOutput=append:/var/log/webops/{deployment.name}.log
StandardError=append:/var/log/webops/{deployment.name}.error.log

[Install]
WantedBy=multi-user.target
"""

        return service_content
