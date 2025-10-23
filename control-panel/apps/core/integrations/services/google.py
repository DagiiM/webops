"""
Google integration service.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.utils import timezone
import requests

from apps.core.integrations.models import GoogleConnection
from apps.core.common.utils.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)


class GoogleIntegrationService:
    """Service for managing Google OAuth integration."""

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

    def __init__(self):
        from config.dynamic_settings import dynamic_settings
        self.client_id = dynamic_settings.GOOGLE_OAUTH_CLIENT_ID
        self.client_secret = dynamic_settings.GOOGLE_OAUTH_CLIENT_SECRET

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: CSRF protection state token

        Returns:
            Authorization URL
        """
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",  # Request refresh token
            "include_granted_scopes": "true",
            "prompt": "consent",  # Ensure refresh token on each consent
        }
        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchange OAuth code for access/refresh/id tokens.

        Args:
            code: OAuth authorization code
            redirect_uri: Callback URL

        Returns:
            Token data or None if failed
        """
        try:
            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            response = requests.post(self.GOOGLE_TOKEN_URL, data=data, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception:
            logger.exception("Google token exchange failed")
        return None

    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Google user info via OpenID Connect userinfo endpoint.
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(self.GOOGLE_USERINFO_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.error(f"Google userinfo failed HTTP {response.status_code}: {response.text}")
        except Exception:
            logger.exception("Google userinfo request failed")
        return None

    def save_connection(self, user: User, token_data: Dict[str, Any], user_info: Dict[str, Any]) -> Optional[GoogleConnection]:
        """
        Save or update Google connection for the user, encrypting all sensitive tokens.
        """
        try:
            access_token = token_data.get("access_token", "")
            refresh_token = token_data.get("refresh_token", "")
            id_token = token_data.get("id_token", "")
            expires_in = token_data.get("expires_in", 0)
            scopes = token_data.get("scope", "").split() if token_data.get("scope") else ["openid", "email", "profile"]

            encrypted_access = encrypt_value(access_token) if access_token else ""
            encrypted_refresh = encrypt_value(refresh_token) if refresh_token else ""
            encrypted_id = encrypt_value(id_token) if id_token else ""

            token_expires_at = timezone.now() + timezone.timedelta(seconds=int(expires_in or 0)) if expires_in else None

            connection, _created = GoogleConnection.objects.update_or_create(
                user=user,
                defaults={
                    "google_user_id": user_info.get("sub", ""),
                    "email": user_info.get("email", ""),
                    "name": user_info.get("name", ""),
                    "access_token": encrypted_access,
                    "refresh_token": encrypted_refresh,
                    "id_token": encrypted_id,
                    "token_expires_at": token_expires_at,
                    "scopes": scopes,
                    "last_synced": timezone.now(),
                    "is_valid": True,
                    "last_validation_error": "",
                },
            )
            return connection
        except Exception:
            logger.exception("Failed to save Google connection")
            return None

    def get_connection(self, user: User) -> Optional[GoogleConnection]:
        return getattr(user, "google_connection", None)

    def disconnect(self, user: User) -> bool:
        connection = self.get_connection(user)
        if connection:
            try:
                connection.delete()
                return True
            except Exception:
                logger.exception("Failed to disconnect Google connection")
        return False

    def get_access_token(self, user: User) -> Optional[str]:
        connection = self.get_connection(user)
        if connection:
            try:
                return decrypt_value(connection.access_token)
            except Exception:
                logger.exception("Failed to decrypt Google access token")
        return None

    def test_connection(self, user: User) -> Tuple[bool, str]:
        """Validate connection by calling userinfo endpoint."""
        token = self.get_access_token(user)
        if not token:
            return False, "No Google access token found"

        info = self.get_user_info(token)
        if info and info.get("email"):
            return True, f"Connected as {info.get('email')}"
        return False, "Failed to validate Google token"

    def test_oauth_config(self) -> Tuple[bool, str]:
        """Test OAuth configuration by validating client credentials."""
        if not self.client_id or not self.client_secret:
            return False, "Google OAuth client ID or secret not configured"
        
        # Basic validation of client ID format
        if not self.client_id.endswith('.apps.googleusercontent.com'):
            return False, "Invalid Google OAuth client ID format"
        
        # Test by making a request to the token endpoint with invalid grant
        # This will validate that the client credentials are recognized by Google
        try:
            response = requests.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type': 'authorization_code',
                    'code': 'invalid_code_for_testing',
                    'redirect_uri': 'http://localhost:8000/auth/google/callback/'
                },
                timeout=10
            )
            
            # If we get a 400 with "invalid_grant", it means the credentials are valid
            # but the code is invalid (which is expected)
            if response.status_code == 400:
                error_data = response.json()
                if error_data.get('error') == 'invalid_grant':
                    return True, "Google OAuth configuration is valid"
                elif error_data.get('error') == 'invalid_client':
                    return False, "Invalid Google OAuth client credentials"
            
            return False, f"Unexpected response from Google: {response.status_code}"
            
        except requests.RequestException as e:
            return False, f"Failed to connect to Google OAuth: {str(e)}"