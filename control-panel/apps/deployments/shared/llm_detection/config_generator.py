"""
Configuration generator for LLM deployments.

Generates optimal deployment configuration based on model characteristics
and selected backend.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

from .model_analyzer import ModelInfo

logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    """Generated deployment configuration."""

    # Data type settings
    dtype: str = 'auto'  # 'float16', 'bfloat16', 'float32', 'auto'
    quantization: str = ''  # '', 'awq', 'gptq', 'squeezellm'

    # Model settings
    max_model_len: Optional[int] = None  # Max sequence length
    tensor_parallel_size: int = 1  # Number of GPUs for tensor parallelism

    # Memory estimates
    estimated_memory_gb: float = 0.0

    # Environment variables
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Info messages
    info_messages: List[str] = field(default_factory=list)


class ConfigGenerator:
    """Generates optimal configuration for LLM deployments."""

    def generate_config(
        self,
        model_info: ModelInfo,
        backend: str,
        available_gpu: bool = False,
        available_vram_gb: float = 0.0
    ) -> DeploymentConfig:
        """
        Generate optimal deployment configuration.

        Args:
            model_info: Analyzed model information
            backend: Selected backend ('transformers', 'vllm', 'ollama', 'tgi')
            available_gpu: Whether GPU is available
            available_vram_gb: Available GPU VRAM in GB

        Returns:
            DeploymentConfig with optimal settings
        """
        config = DeploymentConfig()

        # Determine optimal dtype
        config.dtype = self._select_dtype(model_info, backend, available_gpu)

        # Determine if quantization is beneficial
        config.quantization = self._select_quantization(
            model_info, backend, available_gpu, available_vram_gb
        )

        # Set max model length
        config.max_model_len = self._select_max_model_len(model_info, backend)

        # Estimate memory requirements
        config.estimated_memory_gb = self._estimate_memory(
            model_info, config.dtype, config.quantization
        )

        # Generate environment variables
        config.env_vars = self._generate_env_vars(model_info, backend, config)

        # Add informational messages
        config.info_messages = self._generate_info_messages(model_info, config, backend)

        return config

    def _select_dtype(self, model_info: ModelInfo, backend: str, available_gpu: bool) -> str:
        """Select optimal data type for model weights."""

        if backend == 'transformers':
            # Transformers handles dtype well automatically
            if available_gpu:
                # GPUs generally prefer float16
                return 'float16'
            else:
                # CPU can handle float32 better
                return 'float32'

        elif backend == 'vllm':
            if available_gpu:
                # vLLM prefers bfloat16 on modern GPUs (Ampere+)
                # but float16 is more compatible
                return 'float16'
            else:
                # vLLM CPU build
                return 'float32'

        else:
            # Ollama, TGI - use auto
            return 'auto'

    def _select_quantization(
        self,
        model_info: ModelInfo,
        backend: str,
        available_gpu: bool,
        available_vram_gb: float
    ) -> str:
        """
        Select quantization method if beneficial.

        Quantization reduces memory but requires compatible model.
        """
        # Quantization only makes sense for GPU deployments
        if not available_gpu:
            return ''

        # Only vLLM supports quantization well
        if backend != 'vllm':
            return ''

        # Get parameter count
        params = model_info.parameter_count
        if not params and model_info.model_size_gb:
            params = int(model_info.model_size_gb * (1024**3) / 2)

        if not params:
            return ''  # Unknown size, skip quantization

        params_billions = params / 1e9

        # Estimate memory needed for full precision
        estimated_memory = model_info.model_size_gb or (params_billions * 2)  # fp16 estimate

        # If model fits comfortably in VRAM, no quantization needed
        if available_vram_gb >= estimated_memory * 1.5:
            return ''

        # If model is tight on VRAM, suggest quantization
        if available_vram_gb < estimated_memory * 1.2:
            # Check if model has pre-quantized versions (common naming patterns)
            model_lower = model_info.model_id.lower()
            if 'awq' in model_lower:
                return 'awq'
            elif 'gptq' in model_lower:
                return 'gptq'
            else:
                # Suggest AWQ as modern standard
                return ''  # Disabled by default - user should use pre-quantized model

        return ''

    def _select_max_model_len(self, model_info: ModelInfo, backend: str) -> Optional[int]:
        """Select maximum model length (context window)."""

        # Use model's native context length if available
        if model_info.context_length:
            return model_info.context_length

        # Defaults based on model type
        model_type_defaults = {
            'gpt': 2048,
            'llama': 4096,
            'mistral': 8192,
            'mixtral': 32768,
            'falcon': 2048,
            'mpt': 2048,
            't5': 512,
            'bert': 512,
        }

        return model_type_defaults.get(model_info.model_type, 2048)

    def _estimate_memory(
        self,
        model_info: ModelInfo,
        dtype: str,
        quantization: str
    ) -> float:
        """
        Estimate memory requirements in GB.

        Args:
            model_info: Model information
            dtype: Selected data type
            quantization: Selected quantization method

        Returns:
            Estimated memory in GB
        """
        # Start with model size
        base_memory = model_info.model_size_gb or 1.0

        # Adjust for dtype
        dtype_multipliers = {
            'float32': 2.0,
            'float16': 1.0,
            'bfloat16': 1.0,
            'auto': 1.0,
        }
        base_memory *= dtype_multipliers.get(dtype, 1.0)

        # Adjust for quantization
        quant_multipliers = {
            '': 1.0,
            'awq': 0.25,  # 4-bit quantization
            'gptq': 0.25,  # 4-bit quantization
            'squeezellm': 0.3,
        }
        base_memory *= quant_multipliers.get(quantization, 1.0)

        # Add overhead for KV cache and activations (~40%)
        total_memory = base_memory * 1.4

        return round(total_memory, 2)

    def _generate_env_vars(
        self,
        model_info: ModelInfo,
        backend: str,
        config: DeploymentConfig
    ) -> Dict[str, str]:
        """Generate environment variables for deployment."""

        env_vars = {}

        # Common HuggingFace settings
        if backend in ['transformers', 'vllm']:
            env_vars['HF_HOME'] = '/var/cache/huggingface'
            env_vars['TRANSFORMERS_CACHE'] = '/var/cache/huggingface'

        # vLLM-specific settings
        if backend == 'vllm':
            env_vars['VLLM_LOGGING_LEVEL'] = 'INFO'

            # CPU-specific settings
            if config.dtype == 'float32':
                env_vars['VLLM_TARGET_DEVICE'] = 'cpu'
                env_vars['CMAKE_DISABLE_FIND_PACKAGE_CUDA'] = 'ON'

        # Transformers-specific settings
        if backend == 'transformers':
            env_vars['TOKENIZERS_PARALLELISM'] = 'false'  # Avoid warnings

        return env_vars

    def _generate_info_messages(
        self,
        model_info: ModelInfo,
        config: DeploymentConfig,
        backend: str
    ) -> List[str]:
        """Generate informational messages about the configuration."""

        messages = []

        # Memory info
        messages.append(f"Estimated memory usage: ~{config.estimated_memory_gb}GB")

        # Context length info
        if config.max_model_len:
            messages.append(f"Maximum context length: {config.max_model_len} tokens")

        # Quantization info
        if config.quantization:
            messages.append(
                f"Using {config.quantization.upper()} quantization to reduce memory usage. "
                "Note: Ensure model supports this quantization method."
            )

        # Backend-specific tips
        if backend == 'transformers':
            messages.append(
                "Transformers backend selected: Fast setup, excellent CPU support, "
                "suitable for development and small-scale production."
            )
        elif backend == 'vllm':
            messages.append(
                "vLLM backend selected: Optimized for high throughput and batching, "
                "best for production workloads with multiple concurrent requests."
            )

        # Model-specific tips
        if model_info.is_gated:
            messages.append(
                "⚠️  This model is gated. Ensure you have HuggingFace access token configured "
                "and have accepted the model's license agreement."
            )

        if model_info.safetensors_available:
            messages.append(
                "✅ SafeTensors format available - faster and safer model loading."
            )

        return messages
