"""
Integrations domain for WebOps.

Handles OAuth flows and API token management for GitHub, Hugging Face, and Google.
"""

from .models import GitHubConnection, HuggingFaceConnection, GoogleConnection
from .services import (
    GitHubIntegrationService,
    HuggingFaceIntegrationService,
    GoogleIntegrationService
)

__all__ = [
    'GitHubConnection',
    'HuggingFaceConnection',
    'GoogleConnection',
    'GitHubIntegrationService',
    'HuggingFaceIntegrationService',
    'GoogleIntegrationService',
]