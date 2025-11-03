"""
Backend selector for LLM deployments.

Recommends the optimal backend (vLLM, Transformers, Ollama, TGI) based on
model characteristics and available hardware.
"""

from dataclasses import dataclass, field
from typing import Optional, List
import logging

from .model_analyzer import ModelInfo

logger = logging.getLogger(__name__)


@dataclass
class BackendRecommendation:
    """Recommendation for which backend to use."""

    backend: str  # 'transformers', 'vllm', 'ollama', 'tgi'
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Human-readable explanation

    # Hardware requirements
    requires_gpu: bool = False
    min_vram_gb: float = 0.0
    min_ram_gb: float = 4.0

    # Warnings
    warnings: List[str] = field(default_factory=list)


class BackendSelector:
    """Selects optimal LLM serving backend."""

    def recommend_backend(
        self,
        model_info: ModelInfo,
        target_backend: Optional[str] = None,
        available_gpu: bool = False,
        available_vram_gb: float = 0.0
    ) -> BackendRecommendation:
        """
        Recommend optimal backend for a model.

        Decision Matrix:
        - Small models (<1B params) → Transformers (fast setup, good for CPU)
        - Medium models (1B-13B) → Transformers or vLLM based on GPU availability
        - Large models (>13B) → vLLM with GPU preferred
        - Very large models (>70B) → vLLM with tensor parallelism

        Args:
            model_info: Analyzed model information
            target_backend: Optional backend override
            available_gpu: Whether GPU is available
            available_vram_gb: Available GPU VRAM in GB

        Returns:
            BackendRecommendation with optimal choice
        """
        # If user specified a backend, validate and use it
        if target_backend:
            return self._validate_target_backend(target_backend, model_info, available_gpu, available_vram_gb)

        # Get parameter count (estimate if needed)
        params = model_info.parameter_count
        if not params and model_info.model_size_gb:
            # Rough estimate: 2 bytes per param for fp16
            params = int(model_info.model_size_gb * (1024**3) / 2)

        # Categorize by size
        if params:
            params_billions = params / 1e9

            # Very small models (<500M params)
            if params_billions < 0.5:
                return BackendRecommendation(
                    backend='transformers',
                    confidence=0.95,
                    reasoning=f'Model is very small ({params_billions:.1f}B params). Transformers provides fast setup and excellent CPU performance for small models.',
                    requires_gpu=False,
                    min_ram_gb=4.0
                )

            # Small models (500M-1B params)
            elif params_billions < 1.0:
                return BackendRecommendation(
                    backend='transformers',
                    confidence=0.90,
                    reasoning=f'Model size ({params_billions:.1f}B params) is ideal for Transformers backend with quick setup and good CPU inference.',
                    requires_gpu=False,
                    min_ram_gb=6.0
                )

            # Medium-small models (1B-3B params)
            elif params_billions < 3.0:
                if available_gpu and available_vram_gb >= 8:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.85,
                        reasoning=f'Model size ({params_billions:.1f}B params) with GPU available. vLLM provides better throughput and batching.',
                        requires_gpu=True,
                        min_vram_gb=8.0,
                        min_ram_gb=8.0
                    )
                else:
                    return BackendRecommendation(
                        backend='transformers',
                        confidence=0.85,
                        reasoning=f'Model size ({params_billions:.1f}B params). Transformers recommended for CPU deployment with reasonable performance.',
                        requires_gpu=False,
                        min_ram_gb=8.0,
                        warnings=['GPU would improve inference speed significantly']
                    )

            # Medium models (3B-7B params)
            elif params_billions < 7.0:
                if available_gpu and available_vram_gb >= 12:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.90,
                        reasoning=f'Model size ({params_billions:.1f}B params) benefits from vLLM optimization. GPU acceleration recommended.',
                        requires_gpu=True,
                        min_vram_gb=12.0,
                        min_ram_gb=12.0
                    )
                else:
                    return BackendRecommendation(
                        backend='transformers',
                        confidence=0.70,
                        reasoning=f'Model size ({params_billions:.1f}B params) can run on CPU but will be slow. Consider GPU for production use.',
                        requires_gpu=False,
                        min_ram_gb=16.0,
                        warnings=['This model may be slow on CPU. GPU strongly recommended for production.']
                    )

            # Large models (7B-13B params)
            elif params_billions < 13.0:
                if available_gpu and available_vram_gb >= 16:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.95,
                        reasoning=f'Model size ({params_billions:.1f}B params) requires GPU for practical use. vLLM provides excellent throughput.',
                        requires_gpu=True,
                        min_vram_gb=16.0,
                        min_ram_gb=16.0
                    )
                else:
                    return BackendRecommendation(
                        backend='transformers',
                        confidence=0.50,
                        reasoning=f'Model size ({params_billions:.1f}B params) is very slow on CPU. Only recommended for testing.',
                        requires_gpu=False,
                        min_ram_gb=24.0,
                        warnings=[
                            'This model is likely too large for CPU-only deployment.',
                            'Expect very slow inference (minutes per request).',
                            'GPU with 16GB+ VRAM strongly recommended.'
                        ]
                    )

            # Very large models (13B-70B params)
            elif params_billions < 70.0:
                if available_gpu and available_vram_gb >= 24:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.95,
                        reasoning=f'Large model ({params_billions:.1f}B params) requires high-end GPU. vLLM provides optimal performance.',
                        requires_gpu=True,
                        min_vram_gb=24.0,
                        min_ram_gb=32.0
                    )
                else:
                    return BackendRecommendation(
                        backend='transformers',
                        confidence=0.30,
                        reasoning=f'Model size ({params_billions:.1f}B params) is too large for practical CPU deployment.',
                        requires_gpu=False,
                        min_ram_gb=48.0,
                        warnings=[
                            f'This {params_billions:.0f}B parameter model requires significant GPU resources.',
                            'CPU deployment will be extremely slow (10+ minutes per request).',
                            'Minimum 24GB VRAM GPU strongly recommended.',
                            'Consider using quantization (AWQ/GPTQ) or smaller model variant.'
                        ]
                    )

            # Extremely large models (>70B params)
            else:
                if available_gpu and available_vram_gb >= 40:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.90,
                        reasoning=f'Extremely large model ({params_billions:.0f}B params) requires multi-GPU setup. vLLM supports tensor parallelism.',
                        requires_gpu=True,
                        min_vram_gb=40.0,
                        min_ram_gb=64.0,
                        warnings=[
                            'This model may require tensor parallelism across multiple GPUs.',
                            'Consider using quantized versions (AWQ/GPTQ) to reduce memory requirements.'
                        ]
                    )
                else:
                    return BackendRecommendation(
                        backend='vllm',
                        confidence=0.20,
                        reasoning=f'Extremely large model ({params_billions:.0f}B params). Deployment not recommended without significant GPU resources.',
                        requires_gpu=True,
                        min_vram_gb=40.0,
                        min_ram_gb=64.0,
                        warnings=[
                            f'This {params_billions:.0f}B parameter model requires professional-grade hardware.',
                            'Minimum 40GB VRAM (A100 or better) or multiple GPUs required.',
                            'CPU deployment is not feasible.',
                            'Consider using smaller model variants or heavily quantized versions.'
                        ]
                    )

        # Fallback: no parameter count available
        # Use model type and size estimate
        else:
            logger.warning("Parameter count unknown, using conservative defaults")

            if model_info.model_size_gb and model_info.model_size_gb < 2.0:
                return BackendRecommendation(
                    backend='transformers',
                    confidence=0.70,
                    reasoning='Model appears small (based on file size). Transformers recommended for quick setup.',
                    requires_gpu=False,
                    min_ram_gb=8.0,
                    warnings=['Parameter count unknown - this is a best guess based on file size.']
                )
            else:
                return BackendRecommendation(
                    backend='transformers',
                    confidence=0.60,
                    reasoning='Model size unknown. Transformers chosen as safe default with CPU support.',
                    requires_gpu=False,
                    min_ram_gb=16.0,
                    warnings=[
                        'Could not determine model size accurately.',
                        'Starting with Transformers backend as safe default.',
                        'Monitor performance and consider vLLM if GPU is available.'
                    ]
                )

    def _validate_target_backend(
        self,
        target_backend: str,
        model_info: ModelInfo,
        available_gpu: bool,
        available_vram_gb: float
    ) -> BackendRecommendation:
        """Validate user-specified backend and provide warnings if needed."""

        # Get natural recommendation for comparison
        natural_rec = self.recommend_backend(model_info, None, available_gpu, available_vram_gb)

        rec = BackendRecommendation(
            backend=target_backend,
            confidence=0.90,  # User knows what they want
            reasoning=f'User selected {target_backend} backend (auto-recommendation was {natural_rec.backend}).',
            requires_gpu=natural_rec.requires_gpu,
            min_vram_gb=natural_rec.min_vram_gb,
            min_ram_gb=natural_rec.min_ram_gb
        )

        # Add warnings if user choice differs from recommendation
        if target_backend != natural_rec.backend:
            rec.warnings.append(
                f'Auto-detection recommended {natural_rec.backend} backend. '
                f'Reason: {natural_rec.reasoning}'
            )

        # Add natural warnings
        rec.warnings.extend(natural_rec.warnings)

        return rec
