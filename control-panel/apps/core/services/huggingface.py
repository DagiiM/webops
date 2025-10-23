"""
Hugging Face integration service.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from django.contrib.auth.models import User
from django.utils import timezone
import requests

from apps.core.integrations.models import HuggingFaceConnection
from apps.core.common.utils.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)


class HuggingFaceIntegrationService:
    """Service for managing Hugging Face API token integration."""

    HF_API_URL = "https://huggingface.co/api"

    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate Hugging Face API token and get user info.

        Args:
            token: Hugging Face API token

        Returns:
            Tuple of (is_valid, user_data)
        """
        try:
            response = requests.get(
                f"{self.HF_API_URL}/whoami-v2",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )

            if response.status_code == 200:
                user_data = response.json()
                return True, user_data
            elif response.status_code == 401:
                logger.warning("Invalid Hugging Face token")
                return False, None
            else:
                logger.error(
                    f"Hugging Face validation HTTP {response.status_code}: {response.text}"
                )
                return False, None

        except Exception as e:
            logger.error(f"Hugging Face validation exception: {e}")
            return False, None

    def save_connection(
        self, user: User, token: str, token_type: str = "read"
    ) -> Optional[HuggingFaceConnection]:
        """
        Save Hugging Face connection to database.

        Args:
            user: Django user
            token: Hugging Face API token
            token_type: Token type (read, write, fine-grained)

        Returns:
            HuggingFaceConnection instance or None if validation failed
        """
        # Validate token first
        is_valid, user_data = self.validate_token(token)

        if not is_valid or not user_data:
            return None

        # Encrypt the token
        encrypted_token = encrypt_value(token)

        # Create or update connection
        connection, created = HuggingFaceConnection.objects.update_or_create(
            user=user,
            defaults={
                "username": user_data.get("name", "unknown"),
                "access_token": encrypted_token,
                "token_type": token_type,
                "is_valid": True,
                "last_synced": timezone.now(),
                "last_validation_error": "",
            },
        )

        action = "created" if created else "updated"
        logger.info(
            f"Hugging Face connection {action} for {user.username} → @{user_data.get('name')}"
        )

        return connection

    def get_connection(self, user: User) -> Optional[HuggingFaceConnection]:
        """
        Get Hugging Face connection for user.

        Args:
            user: Django user

        Returns:
            HuggingFaceConnection or None
        """
        try:
            return HuggingFaceConnection.objects.get(user=user)
        except HuggingFaceConnection.DoesNotExist:
            return None

    def get_access_token(self, user: User) -> Optional[str]:
        """
        Get decrypted Hugging Face API token for user.

        Args:
            user: Django user

        Returns:
            API token or None
        """
        connection = self.get_connection(user)
        if connection and connection.is_valid:
            return decrypt_value(connection.access_token)
        return None

    def disconnect(self, user: User) -> bool:
        """
        Disconnect Hugging Face account.

        Args:
            user: Django user

        Returns:
            True if disconnected, False if no connection existed
        """
        try:
            connection = HuggingFaceConnection.objects.get(user=user)
            connection.delete()
            logger.info(f"Hugging Face connection deleted for {user.username}")
            return True
        except HuggingFaceConnection.DoesNotExist:
            return False

    def test_connection(self, user: User) -> Tuple[bool, str]:
        """
        Test if Hugging Face connection is valid.

        Args:
            user: Django user

        Returns:
            Tuple of (is_valid, message)
        """
        connection = self.get_connection(user)
        if not connection:
            return False, "No Hugging Face connection found"

        token = decrypt_value(connection.access_token)
        is_valid, user_data = self.validate_token(token)

        if is_valid and user_data:
            # Update connection status
            connection.is_valid = True
            connection.last_synced = timezone.now()
            connection.last_validation_error = ""
            connection.save()

            return True, f"Connected as @{user_data.get('name')}"
        else:
            # Mark connection as invalid
            connection.is_valid = False
            connection.last_validation_error = "Token validation failed"
            connection.save()

            return False, "Invalid or expired Hugging Face token"

    def list_user_models(
        self, user: User, limit: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        List models accessible to the user (including private models).

        Args:
            user: Django user
            limit: Maximum number of models to return

        Returns:
            List of model data or None if failed
        """
        token = self.get_access_token(user)
        if not token:
            return None

        try:
            response = requests.get(
                f"{self.HF_API_URL}/models",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": limit, "author": self.get_connection(user).username},
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Hugging Face model list HTTP {response.status_code}: {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Hugging Face model list exception: {e}")
            return None