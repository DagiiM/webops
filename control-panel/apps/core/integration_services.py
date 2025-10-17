"""
Integration services for GitHub and Hugging Face.

Reference: CLAUDE.md "Security Best Practices" section
Architecture: OAuth integration, API token management, credential encryption
"""

import logging
from typing import Dict, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
import requests

from apps.core.models import GitHubConnection, HuggingFaceConnection, GoogleConnection
from apps.core.utils import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)


class GitHubIntegrationService:
    """Service for managing GitHub integration (OAuth and Personal Access Tokens)."""

    GITHUB_API_URL = "https://api.github.com"
    GITHUB_OAUTH_URL = "https://github.com/login/oauth"

    def __init__(self):
        self.client_id = settings.GITHUB_OAUTH_CLIENT_ID
        self.client_secret = settings.GITHUB_OAUTH_CLIENT_SECRET

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate GitHub OAuth authorization URL.

        Args:
            redirect_uri: Callback URL after authorization
            state: CSRF protection state token

        Returns:
            Authorization URL
        """
        scopes = "repo,read:user,user:email"
        return (
            f"{self.GITHUB_OAUTH_URL}/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope={scopes}&"
            f"state={state}"
        )

    def exchange_code_for_token(
        self, code: str, redirect_uri: str
    ) -> Optional[Dict[str, Any]]:
        """
        Exchange OAuth code for access token.

        Args:
            code: OAuth authorization code
            redirect_uri: Callback URL (must match authorization)

        Returns:
            Token data or None if failed
        """
        try:
            response = requests.post(
                f"{self.GITHUB_OAUTH_URL}/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    return data
                logger.error(f"GitHub token exchange failed: {data}")
            else:
                logger.error(
                    f"GitHub token exchange HTTP {response.status_code}: {response.text}"
                )

        except Exception as e:
            logger.error(f"GitHub token exchange exception: {e}")

        return None

    def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get GitHub user information.

        Args:
            access_token: GitHub access token

        Returns:
            User data or None if failed
        """
        try:
            response = requests.get(
                f"{self.GITHUB_API_URL}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"GitHub user info HTTP {response.status_code}: {response.text}"
                )

        except Exception as e:
            logger.error(f"GitHub user info exception: {e}")

        return None

    def validate_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate GitHub Personal Access Token and get user info.

        This is an alternative to OAuth for simpler self-hosted setups.

        Args:
            token: GitHub Personal Access Token

        Returns:
            Tuple of (is_valid, user_data)
        """
        user_info = self.get_user_info(token)
        if user_info:
            return True, user_info
        return False, None

    def save_connection_with_pat(
        self, user: User, token: str
    ) -> Optional[GitHubConnection]:
        """
        Save GitHub connection using Personal Access Token.

        This method provides a simpler alternative to OAuth for self-hosted setups.
        Users can generate a PAT at https://github.com/settings/tokens

        Args:
            user: Django user
            token: GitHub Personal Access Token

        Returns:
            GitHubConnection instance or None if validation failed
        """
        # Validate token first
        is_valid, user_data = self.validate_token(token)

        if not is_valid or not user_data:
            logger.warning(f"Invalid GitHub token for user {user.username}")
            return None

        # Use the main save_connection method
        return self.save_connection(user, token, user_data)

    def save_connection(
        self, user: User, access_token: str, user_data: Dict[str, Any]
    ) -> GitHubConnection:
        """
        Save GitHub connection to database.

        Args:
            user: Django user
            access_token: GitHub access token (OAuth or PAT)
            user_data: GitHub user data

        Returns:
            GitHubConnection instance
        """
        # Encrypt the access token
        encrypted_token = encrypt_password(access_token)

        # Create or update connection
        connection, created = GitHubConnection.objects.update_or_create(
            user=user,
            defaults={
                "github_user_id": user_data["id"],
                "username": user_data["login"],
                "access_token": encrypted_token,
                "scopes": ["repo", "read:user", "user:email"],
                "last_synced": timezone.now(),
            },
        )

        action = "created" if created else "updated"
        logger.info(
            f"GitHub connection {action} for {user.username} → @{user_data['login']}"
        )

        return connection

    def get_connection(self, user: User) -> Optional[GitHubConnection]:
        """
        Get GitHub connection for user.

        Args:
            user: Django user

        Returns:
            GitHubConnection or None
        """
        try:
            return GitHubConnection.objects.get(user=user)
        except GitHubConnection.DoesNotExist:
            return None

    def get_access_token(self, user: User) -> Optional[str]:
        """
        Get decrypted GitHub access token for user.

        Args:
            user: Django user

        Returns:
            Access token or None
        """
        connection = self.get_connection(user)
        if connection:
            return decrypt_password(connection.access_token)
        return None

    def disconnect(self, user: User) -> bool:
        """
        Disconnect GitHub account.

        Args:
            user: Django user

        Returns:
            True if disconnected, False if no connection existed
        """
        try:
            connection = GitHubConnection.objects.get(user=user)
            connection.delete()
            logger.info(f"GitHub connection deleted for {user.username}")
            return True
        except GitHubConnection.DoesNotExist:
            return False

    def test_connection(self, user: User) -> Tuple[bool, str]:
        """
        Test if GitHub connection is valid.

        Args:
            user: Django user

        Returns:
            Tuple of (is_valid, message)
        """
        access_token = self.get_access_token(user)
        if not access_token:
            return False, "No GitHub connection found"

        user_info = self.get_user_info(access_token)
        if user_info:
            return True, f"Connected as @{user_info['login']}"
        else:
            return False, "Invalid or expired GitHub token"

    def list_repositories(
        self, user: User, per_page: int = 100, sort: str = "updated"
    ) -> Optional[list[Dict[str, Any]]]:
        """
        List all repositories accessible to the user.

        Args:
            user: Django user
            per_page: Number of repos per page (max 100)
            sort: Sort order (created, updated, pushed, full_name)

        Returns:
            List of repository data or None if failed
        """
        access_token = self.get_access_token(user)
        if not access_token:
            logger.warning(f"No GitHub token for user {user.username}")
            return None

        try:
            # Fetch user's repositories (both owned and accessible)
            response = requests.get(
                f"{self.GITHUB_API_URL}/user/repos",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={
                    "per_page": per_page,
                    "sort": sort,
                    "affiliation": "owner,collaborator,organization_member",
                },
                timeout=30,
            )

            if response.status_code == 200:
                repos = response.json()
                logger.info(f"Fetched {len(repos)} repositories for {user.username}")
                return repos
            else:
                logger.error(
                    f"GitHub repo list HTTP {response.status_code}: {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"GitHub repo list exception: {e}")
            return None

    def list_branches(
        self, user: User, repo_full_name: str
    ) -> Optional[list[Dict[str, Any]]]:
        """
        List branches for a specific repository.

        Args:
            user: Django user
            repo_full_name: Repository name in format 'owner/repo'

        Returns:
            List of branch data or None if failed
        """
        access_token = self.get_access_token(user)
        if not access_token:
            return None

        try:
            response = requests.get(
                f"{self.GITHUB_API_URL}/repos/{repo_full_name}/branches",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"GitHub branch list HTTP {response.status_code}: {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"GitHub branch list exception: {e}")
            return None


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
        encrypted_token = encrypt_password(token)

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
            return decrypt_password(connection.access_token)
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

        token = decrypt_password(connection.access_token)
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
    ) -> Optional[list[Dict[str, Any]]]:
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

            encrypted_access = encrypt_password(access_token) if access_token else ""
            encrypted_refresh = encrypt_password(refresh_token) if refresh_token else ""
            encrypted_id = encrypt_password(id_token) if id_token else ""

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
                return decrypt_password(connection.access_token)
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
