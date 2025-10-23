"""LLM deployment model."""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .base import BaseDeployment


class LLMDeployment(BaseDeployment):
    """LLM model deployment using vLLM."""

    class ProjectType(models.TextChoices):
        LLM = 'llm', 'Large Language Model'

    project_type = models.CharField(
        max_length=20,
        choices=ProjectType.choices,
        default=ProjectType.LLM
    )

    model_name = models.CharField(max_length=255)
    
    tensor_parallel_size = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    gpu_memory_utilization = models.FloatField(
        default=0.9,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    max_model_len = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])

    quantization = models.CharField(
        max_length=20,
        blank=True,
        choices=[('', 'None'), ('awq', 'AWQ'), ('gptq', 'GPTQ'), ('squeezellm', 'SqueezeLLM')]
    )
    dtype = models.CharField(
        max_length=20,
        default='auto',
        choices=[('auto', 'Auto'), ('float16', 'Float16'), ('bfloat16', 'BFloat16'), ('float32', 'Float32')]
    )

    vllm_args = models.JSONField(default=dict, blank=True)
    model_size_gb = models.FloatField(null=True, blank=True)
    download_completed = models.BooleanField(default=False)
    enable_trust_remote_code = models.BooleanField(default=False)

    class Meta:
        db_table = 'llm_deployments'
        verbose_name = 'LLM Deployment'
        verbose_name_plural = 'LLM Deployments'
        ordering = ['-created_at']

    def get_service_manager(self):
        """Return the LLM deployment service."""
        from apps.deployments.services.llm import LLMDeploymentService
        return LLMDeploymentService()

    def estimate_memory_requirements_gb(self) -> float:
        """Estimate VRAM requirements."""
        if self.model_size_gb:
            base_memory = self.model_size_gb
        else:
            import re
            match = re.search(r'(\d+)b', self.model_name.lower())
            base_memory = int(match.group(1)) * 2 if match else 10.0

        if self.quantization in ['awq', 'gptq']:
            base_memory *= 0.5
        elif self.quantization == 'squeezellm':
            base_memory *= 0.4

        if self.dtype == 'float32':
            base_memory *= 2.0

        total_memory = base_memory * 1.4
        return round(total_memory / self.tensor_parallel_size, 2)
