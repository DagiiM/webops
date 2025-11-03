"""
LLM Model Auto-Detection System.

Railway-style auto-detection for LLM deployments that analyzes HuggingFace models
and automatically configures optimal deployment settings.

Usage:
    from apps.deployments.shared.llm_detection import detect_model

    result = detect_model("meta-llama/Llama-2-7b-chat-hf", hf_token=token)

    if result.detected:
        print(f"Model type: {result.model_type}")
        print(f"Recommended backend: {result.recommended_backend}")
        print(f"Model size: {result.model_size_gb}GB")
"""

from .detector import detect_model, ModelDetectionResult
from .model_analyzer import HuggingFaceModelAnalyzer
from .backend_selector import BackendSelector
from .config_generator import ConfigGenerator

__all__ = [
    'detect_model',
    'ModelDetectionResult',
    'HuggingFaceModelAnalyzer',
    'BackendSelector',
    'ConfigGenerator',
]
