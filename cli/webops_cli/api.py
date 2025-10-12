"""API client for WebOps."""

from typing import Dict, Any, Optional, List
import requests
from requests.exceptions import RequestException


class WebOpsAPIError(Exception):
    """Base exception for API errors."""
    pass


class WebOpsAPIClient:
    """Client for WebOps REST API."""

    def __init__(self, base_url: str, token: str):
        """
        Initialize API client.

        Args:
            base_url: Base URL of WebOps panel (e.g., https://panel.example.com)
            token: API authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            JSON response as dictionary

        Raises:
            WebOpsAPIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except RequestException as e:
            error_msg = f"API request failed: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', error_msg)
                except ValueError:
                    error_msg = e.response.text or error_msg
            raise WebOpsAPIError(error_msg)

    # Status
    def get_status(self) -> Dict[str, Any]:
        """Get API status."""
        return self._request('GET', '/api/status/')

    # Deployments
    def list_deployments(
        self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all deployments."""
        params = {'page': page, 'per_page': per_page}
        if status:
            params['status'] = status
        return self._request('GET', '/api/deployments/', params=params)

    def get_deployment(self, name: str) -> Dict[str, Any]:
        """Get deployment details by name."""
        return self._request('GET', f'/api/deployments/{name}/')

    def create_deployment(
        self,
        name: str,
        repo_url: str,
        branch: str = 'main',
        domain: str = '',
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create new deployment."""
        data = {
            'name': name,
            'repo_url': repo_url,
            'branch': branch,
            'domain': domain,
            'env_vars': env_vars or {}
        }
        return self._request('POST', '/api/deployments/create/', json=data)

    def start_deployment(self, name: str) -> Dict[str, Any]:
        """Start deployment."""
        return self._request('POST', f'/api/deployments/{name}/start/')

    def stop_deployment(self, name: str) -> Dict[str, Any]:
        """Stop deployment."""
        return self._request('POST', f'/api/deployments/{name}/stop/')

    def restart_deployment(self, name: str) -> Dict[str, Any]:
        """Restart deployment."""
        return self._request('POST', f'/api/deployments/{name}/restart/')

    def delete_deployment(self, name: str) -> Dict[str, Any]:
        """Delete deployment."""
        return self._request('DELETE', f'/api/deployments/{name}/delete/')

    def get_deployment_logs(
        self,
        name: str,
        tail: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get deployment logs."""
        params = {}
        if tail:
            params['tail'] = tail
        return self._request('GET', f'/api/deployments/{name}/logs/', params=params)

    # Databases
    def list_databases(self) -> Dict[str, Any]:
        """List all databases."""
        return self._request('GET', '/api/databases/')

    def get_database(self, name: str) -> Dict[str, Any]:
        """Get database details."""
        return self._request('GET', f'/api/databases/{name}/')

    # Environment Variables
    def generate_env(
        self,
        deployment_name: str,
        debug: bool = False,
        domain: Optional[str] = None,
        custom_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate .env file from .env.example for a deployment.

        Args:
            deployment_name: Name of the deployment
            debug: Enable debug mode
            domain: Custom domain name
            custom_vars: Custom environment variables to set

        Returns:
            API response
        """
        data = {
            'debug': debug,
            'custom_vars': custom_vars or {}
        }
        if domain:
            data['domain'] = domain

        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/generate/',
            json=data
        )

    def validate_env(self, deployment_name: str) -> Dict[str, Any]:
        """
        Validate .env file for a deployment.

        Args:
            deployment_name: Name of the deployment

        Returns:
            Validation result with 'valid' (bool) and 'missing' (list)
        """
        return self._request(
            'GET',
            f'/api/deployments/{deployment_name}/env/validate/'
        )

    def get_env_vars(self, deployment_name: str) -> Dict[str, Any]:
        """
        Get all environment variables for a deployment.

        Args:
            deployment_name: Name of the deployment

        Returns:
            Dictionary with 'env_vars' containing key-value pairs
        """
        return self._request(
            'GET',
            f'/api/deployments/{deployment_name}/env/'
        )

    def set_env_var(
        self,
        deployment_name: str,
        key: str,
        value: str
    ) -> Dict[str, Any]:
        """
        Set an environment variable for a deployment.

        Args:
            deployment_name: Name of the deployment
            key: Variable name
            value: Variable value

        Returns:
            API response
        """
        data = {'key': key, 'value': value}
        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/set/',
            json=data
        )

    def unset_env_var(
        self,
        deployment_name: str,
        key: str
    ) -> Dict[str, Any]:
        """
        Remove an environment variable from a deployment.

        Args:
            deployment_name: Name of the deployment
            key: Variable name to remove

        Returns:
            API response
        """
        data = {'key': key}
        return self._request(
            'DELETE',
            f'/api/deployments/{deployment_name}/env/unset/',
            json=data
        )
