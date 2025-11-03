"""
Main LLM model detection orchestrator.

Coordinates model analysis, backend selection, and configuration generation.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from decimal import Decimal
import logging

from .model_analyzer import HuggingFaceModelAnalyzer, ModelInfo
from .backend_selector import BackendSelector, BackendRecommendation
from .config_generator import ConfigGenerator

logger = logging.getLogger(__name__)


@dataclass
class ModelDetectionResult:
    """Result of LLM model auto-detection."""

    # Detection status
    detected: bool
    error_message: str = ''

    # Model information
    model_name: str = ''
    model_type: str = ''  # 'gpt', 'llama', 'bert', 't5', 'mistral', etc.
    architecture: str = ''  # 'GPTNeoXForCausalLM', 'LlamaForCausalLM', etc.
    task_type: str = ''  # 'text-generation', 'text2text-generation', 'question-answering', etc.

    # Model characteristics
    parameter_count: Optional[int] = None  # Total parameters
    model_size_gb: Optional[float] = None  # Estimated model size in GB
    context_length: Optional[int] = None  # Max sequence length

    # Model metadata
    author: str = ''
    license: str = ''
    downloads: int = 0
    likes: int = 0
    tags: List[str] = field(default_factory=list)

    # Backend recommendation
    recommended_backend: str = ''  # 'transformers', 'vllm', 'ollama', 'tgi'
    backend_confidence: float = 0.0  # 0.0 to 1.0
    backend_reasoning: str = ''

    # Optimal configuration
    suggested_dtype: str = 'auto'  # 'float16', 'bfloat16', 'float32'
    suggested_quantization: str = ''  # '', 'awq', 'gptq', 'squeezellm'
    suggested_max_model_len: Optional[int] = None
    estimated_memory_gb: float = 0.0

    # Environment variables
    env_vars: Dict[str, str] = field(default_factory=dict)

    # Hardware requirements
    requires_gpu: bool = False
    min_vram_gb: float = 0.0
    min_ram_gb: float = 4.0

    # Additional metadata
    confidence: float = 0.0  # Overall detection confidence
    warnings: List[str] = field(default_factory=list)
    info_messages: List[str] = field(default_factory=list)


def detect_model(
    model_name: str,
    hf_token: Optional[str] = None,
    target_backend: Optional[str] = None,
    available_gpu: bool = False,
    available_vram_gb: float = 0.0
) -> ModelDetectionResult:
    """
    Detect and analyze an LLM model from HuggingFace Hub.

    This is the main entry point for LLM auto-detection, similar to the buildpack
    detect_project() function for applications.

    Args:
        model_name: HuggingFace model identifier (e.g., 'meta-llama/Llama-2-7b-chat-hf')
        hf_token: Optional HuggingFace API token for private models
        target_backend: Optional backend override ('transformers', 'vllm', 'ollama', 'tgi')
        available_gpu: Whether GPU is available
        available_vram_gb: Available GPU VRAM in GB

    Returns:
        ModelDetectionResult with complete model analysis and recommendations

    Example:
        >>> result = detect_model('gpt2')
        >>> if result.detected:
        ...     print(f"Model: {result.model_type}")
        ...     print(f"Backend: {result.recommended_backend}")
        ...     print(f"Memory: {result.estimated_memory_gb}GB")
    """
    logger.info(f"🔍 Auto-detecting LLM model: {model_name}")

    result = ModelDetectionResult(
        detected=False,
        model_name=model_name
    )

    try:
        # Step 1: Analyze model from HuggingFace Hub
        analyzer = HuggingFaceModelAnalyzer(hf_token=hf_token)
        model_info = analyzer.analyze_model(model_name)

        if not model_info.success:
            result.error_message = model_info.error_message
            result.warnings.append(f"Failed to fetch model info: {model_info.error_message}")
            logger.warning(f"❌ Model detection failed for {model_name}: {model_info.error_message}")
            return result

        # Populate model information
        result.model_type = model_info.model_type
        result.architecture = model_info.architecture
        result.task_type = model_info.task_type
        result.parameter_count = model_info.parameter_count
        result.model_size_gb = model_info.model_size_gb
        result.context_length = model_info.context_length
        result.author = model_info.author
        result.license = model_info.license
        result.downloads = model_info.downloads
        result.likes = model_info.likes
        result.tags = model_info.tags

        # Log model info with proper formatting
        params_str = f"{result.parameter_count:,} params" if result.parameter_count else "unknown params"
        size_str = f"{result.model_size_gb}GB" if result.model_size_gb else "unknown size"
        logger.info(f"📊 Model info: {result.model_type}, {params_str}, {size_str}")

        # Step 2: Select optimal backend
        selector = BackendSelector()
        backend_rec = selector.recommend_backend(
            model_info=model_info,
            target_backend=target_backend,
            available_gpu=available_gpu,
            available_vram_gb=available_vram_gb
        )

        result.recommended_backend = backend_rec.backend
        result.backend_confidence = backend_rec.confidence
        result.backend_reasoning = backend_rec.reasoning
        result.requires_gpu = backend_rec.requires_gpu
        result.min_vram_gb = backend_rec.min_vram_gb
        result.min_ram_gb = backend_rec.min_ram_gb
        result.warnings.extend(backend_rec.warnings)

        logger.info(f"🎯 Recommended backend: {result.recommended_backend} (confidence: {result.backend_confidence:.0%})")
        logger.info(f"💡 Reasoning: {result.backend_reasoning}")

        # Step 3: Generate optimal configuration
        config_gen = ConfigGenerator()
        config = config_gen.generate_config(
            model_info=model_info,
            backend=result.recommended_backend,
            available_gpu=available_gpu,
            available_vram_gb=available_vram_gb
        )

        result.suggested_dtype = config.dtype
        result.suggested_quantization = config.quantization
        result.suggested_max_model_len = config.max_model_len
        result.estimated_memory_gb = config.estimated_memory_gb
        result.env_vars = config.env_vars
        result.info_messages.extend(config.info_messages)

        logger.info(f"⚙️  Config: dtype={result.suggested_dtype}, quant={result.suggested_quantization or 'none'}, memory~{result.estimated_memory_gb}GB")

        # Calculate overall confidence
        # High confidence if we have all key info
        confidence_factors = []

        if model_info.model_type:
            confidence_factors.append(0.3)
        if model_info.parameter_count:
            confidence_factors.append(0.2)
        if model_info.model_size_gb:
            confidence_factors.append(0.2)
        if result.recommended_backend:
            confidence_factors.append(0.3 * backend_rec.confidence)

        result.confidence = sum(confidence_factors)
        result.detected = True

        logger.info(f"✅ Detection complete: confidence={result.confidence:.0%}")

        return result

    except Exception as e:
        logger.exception(f"❌ Unexpected error during model detection: {e}")
        result.error_message = f"Unexpected error: {str(e)}"
        result.warnings.append(f"Detection failed with error: {str(e)}")
        return result
