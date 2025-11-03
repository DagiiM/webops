"""
HuggingFace model analyzer.

Fetches and analyzes model information from HuggingFace Hub API.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about an LLM model from HuggingFace."""

    success: bool = False
    error_message: str = ''

    # Basic info
    model_id: str = ''
    model_type: str = ''  # 'gpt', 'llama', 'bert', etc.
    architecture: str = ''  # Full architecture class name
    task_type: str = ''  # Task this model is designed for

    # Size and parameters
    parameter_count: Optional[int] = None
    model_size_gb: Optional[float] = None
    context_length: Optional[int] = None

    # Metadata
    author: str = ''
    license: str = ''
    downloads: int = 0
    likes: int = 0
    tags: List[str] = field(default_factory=list)
    pipeline_tag: str = ''

    # Model characteristics
    is_gated: bool = False  # Requires authentication
    is_private: bool = False
    safetensors_available: bool = False

    # Raw data for advanced usage
    config_data: Dict[str, Any] = field(default_factory=dict)


class HuggingFaceModelAnalyzer:
    """Analyzes LLM models from HuggingFace Hub."""

    def __init__(self, hf_token: Optional[str] = None):
        """
        Initialize analyzer.

        Args:
            hf_token: Optional HuggingFace API token for private/gated models
        """
        self.hf_token = hf_token

    def analyze_model(self, model_id: str) -> ModelInfo:
        """
        Analyze a model from HuggingFace Hub.

        Args:
            model_id: HuggingFace model identifier (e.g., 'gpt2', 'meta-llama/Llama-2-7b')

        Returns:
            ModelInfo with complete model analysis
        """
        info = ModelInfo(model_id=model_id)

        try:
            from huggingface_hub import model_info, hf_hub_download
            from huggingface_hub.utils import RepositoryNotFoundError, GatedRepoError

            logger.info(f"Fetching model info for: {model_id}")

            # Fetch model metadata from Hub
            try:
                model_data = model_info(
                    model_id,
                    token=self.hf_token,
                    files_metadata=True
                )
            except GatedRepoError:
                info.error_message = "Model is gated and requires authentication or access approval"
                info.is_gated = True
                logger.warning(f"Model {model_id} is gated")
                return info
            except RepositoryNotFoundError:
                info.error_message = f"Model '{model_id}' not found on HuggingFace Hub"
                logger.error(f"Model {model_id} not found")
                return info

            # Extract basic metadata
            info.author = model_data.author or ''
            info.likes = getattr(model_data, 'likes', 0)
            info.downloads = getattr(model_data, 'downloads', 0)
            info.is_private = getattr(model_data, 'private', False)
            info.pipeline_tag = getattr(model_data, 'pipeline_tag', '')
            info.tags = list(getattr(model_data, 'tags', []))

            # Get model card data for additional metadata
            if hasattr(model_data, 'card_data') and model_data.card_data:
                card = model_data.card_data
                info.license = getattr(card, 'license', '')

            # Calculate total model size
            if hasattr(model_data, 'siblings') and model_data.siblings:
                total_size = sum(
                    getattr(sibling, 'size', 0)
                    for sibling in model_data.siblings
                    if hasattr(sibling, 'size')
                )
                info.model_size_gb = round(total_size / (1024**3), 2) if total_size > 0 else None

                # Check for safetensors
                info.safetensors_available = any(
                    'safetensors' in getattr(sibling, 'rfilename', '')
                    for sibling in model_data.siblings
                )

            # Try to get config.json for detailed model information
            try:
                import json
                config_path = hf_hub_download(
                    model_id,
                    filename="config.json",
                    token=self.hf_token,
                    cache_dir=None
                )

                with open(config_path, 'r') as f:
                    config = json.load(f)
                    info.config_data = config

                # Extract architecture
                if 'architectures' in config and config['architectures']:
                    info.architecture = config['architectures'][0]
                    # Extract model type from architecture
                    info.model_type = self._extract_model_type(info.architecture)

                # Extract context length
                context_keys = ['max_position_embeddings', 'n_positions', 'max_sequence_length', 'seq_length']
                for key in context_keys:
                    if key in config:
                        info.context_length = config[key]
                        break

                # Try to extract parameter count from config
                info.parameter_count = self._estimate_parameters(config)

            except Exception as e:
                logger.warning(f"Could not fetch config.json for {model_id}: {e}")
                # Try to infer from model ID
                info.model_type = self._infer_model_type_from_id(model_id)

            # Determine task type
            info.task_type = self._determine_task_type(info)

            # If we couldn't get size from files, try to estimate from name
            if not info.model_size_gb and info.parameter_count:
                # Rough estimate: 2 bytes per param for fp16
                info.model_size_gb = round((info.parameter_count * 2) / (1024**3), 2)
            elif not info.model_size_gb:
                # Try to parse from model name (e.g., "7b", "13b")
                info.model_size_gb = self._estimate_size_from_name(model_id)

            info.success = True
            logger.info(f"✅ Model analysis complete: {info.model_type}, {info.parameter_count or 'unknown'} params")

            return info

        except Exception as e:
            logger.exception(f"Error analyzing model {model_id}")
            info.error_message = f"Analysis failed: {str(e)}"
            return info

    def _extract_model_type(self, architecture: str) -> str:
        """
        Extract model type from architecture name.

        Args:
            architecture: Architecture class name (e.g., 'GPT2LMHeadModel')

        Returns:
            Model type string (e.g., 'gpt2')
        """
        arch_lower = architecture.lower()

        # Common architecture patterns
        if 'gpt2' in arch_lower or 'gptneo' in arch_lower or 'gptj' in arch_lower:
            return 'gpt'
        elif 'llama' in arch_lower:
            return 'llama'
        elif 'mistral' in arch_lower:
            return 'mistral'
        elif 'mixtral' in arch_lower:
            return 'mixtral'
        elif 'falcon' in arch_lower:
            return 'falcon'
        elif 'mpt' in arch_lower:
            return 'mpt'
        elif 'bloom' in arch_lower:
            return 'bloom'
        elif 'bert' in arch_lower:
            return 'bert'
        elif 't5' in arch_lower:
            return 't5'
        elif 'bart' in arch_lower:
            return 'bart'
        elif 'roberta' in arch_lower:
            return 'roberta'
        elif 'electra' in arch_lower:
            return 'electra'
        elif 'xlnet' in arch_lower:
            return 'xlnet'
        elif 'gpt' in arch_lower:
            return 'gpt'
        else:
            # Generic extraction: take first word before "For"
            match = re.match(r'([A-Z][a-z]+)', architecture)
            return match.group(1).lower() if match else 'unknown'

    def _infer_model_type_from_id(self, model_id: str) -> str:
        """Infer model type from model ID when config is unavailable."""
        model_lower = model_id.lower()

        if 'gpt' in model_lower:
            return 'gpt'
        elif 'llama' in model_lower:
            return 'llama'
        elif 'mistral' in model_lower:
            return 'mistral'
        elif 'falcon' in model_lower:
            return 'falcon'
        elif 'bert' in model_lower:
            return 'bert'
        elif 't5' in model_lower:
            return 't5'
        else:
            return 'unknown'

    def _determine_task_type(self, info: ModelInfo) -> str:
        """Determine the primary task type for the model."""
        # Use pipeline_tag if available
        if info.pipeline_tag:
            return info.pipeline_tag

        # Infer from architecture
        arch_lower = info.architecture.lower()

        if 'causallm' in arch_lower:
            return 'text-generation'
        elif 'seq2seq' in arch_lower or 'conditional' in arch_lower:
            return 'text2text-generation'
        elif 'questionanswering' in arch_lower:
            return 'question-answering'
        elif 'sequenceclassification' in arch_lower:
            return 'text-classification'
        elif 'tokenclassification' in arch_lower:
            return 'token-classification'
        elif 'maskedlm' in arch_lower:
            return 'fill-mask'
        else:
            # Default based on model type
            if info.model_type in ['gpt', 'llama', 'mistral', 'falcon', 'mpt']:
                return 'text-generation'
            elif info.model_type in ['t5', 'bart']:
                return 'text2text-generation'
            elif info.model_type in ['bert', 'roberta']:
                return 'fill-mask'
            else:
                return 'unknown'

    def _estimate_parameters(self, config: Dict[str, Any]) -> Optional[int]:
        """
        Estimate parameter count from model config.

        Args:
            config: Model configuration dictionary

        Returns:
            Estimated parameter count or None
        """
        try:
            # Common config keys that indicate size
            if 'n_params' in config:
                return config['n_params']

            # For transformer models, try to calculate from architecture
            hidden_size = config.get('hidden_size', config.get('d_model', 0))
            num_layers = config.get('num_hidden_layers', config.get('n_layer', config.get('num_layers', 0)))
            vocab_size = config.get('vocab_size', 0)

            if all([hidden_size, num_layers, vocab_size]):
                # Rough estimate for transformer architecture
                # embedding: vocab_size * hidden_size
                # layers: num_layers * (4 * hidden_size^2 + other params)
                embedding_params = vocab_size * hidden_size
                layer_params = num_layers * (4 * hidden_size * hidden_size)
                return embedding_params + layer_params

            return None

        except Exception as e:
            logger.debug(f"Could not estimate parameters: {e}")
            return None

    def _estimate_size_from_name(self, model_id: str) -> Optional[float]:
        """
        Try to extract model size from name (e.g., "7b" means 7 billion parameters).

        Args:
            model_id: Model identifier

        Returns:
            Estimated size in GB or None
        """
        # Look for patterns like "7b", "13b", "70b", "1.5b", etc.
        match = re.search(r'(\d+\.?\d*)\s*b(?:illion)?', model_id.lower())

        if match:
            billions = float(match.group(1))
            # Estimate: ~2 bytes per param for fp16
            gb = (billions * 1e9 * 2) / (1024**3)
            return round(gb, 2)

        return None
