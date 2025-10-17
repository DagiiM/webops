"""API client for WebOps."""

from typing import Dict, Any, Optional, List, Self
import requests
from requests.exceptions import RequestException


class WebOpsAPIError(Exception):
    """Base exception for API errors."""
    pass


class WebOpsAPIClient:
    """Client for WebOps REST API."""

    def __init__(self: Self, base_url: str, token: str) -> None:
        """Initialize API client.

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
        self: Self,
        method: str,
        endpoint: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make HTTP request to API.

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
    def get_status(self: Self) -> Dict[str, Any]:
        """Get API status.
        
        Returns:
            Dictionary containing API status information.
        """
        return self._request('GET', '/api/status/')

    # Deployments
    def list_deployments(
        self: Self,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all deployments.
        
        Args:
            page: Page number for pagination.
            per_page: Number of results per page.
            status: Filter by deployment status.
            
        Returns:
            Dictionary containing deployment list and pagination info.
        """
        params = {'page': page, 'per_page': per_page}
        if status:
            params['status'] = status
        return self._request('GET', '/api/deployments/', params=params)

    def get_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Get deployment details by name.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing deployment details.
        """
        return self._request('GET', f'/api/deployments/{name}/')

    def create_deployment(
        self: Self,
        name: str,
        repo_url: str,
        branch: str = 'main',
        domain: str = '',
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create new deployment.
        
        Args:
            name: Deployment name.
            repo_url: Git repository URL.
            branch: Git branch to deploy.
            domain: Custom domain name.
            env_vars: Environment variables dictionary.
            
        Returns:
            Dictionary containing created deployment details.
        """
        data = {
            'name': name,
            'repo_url': repo_url,
            'branch': branch,
            'domain': domain,
            'env_vars': env_vars or {}
        }
        return self._request('POST', '/api/deployments/create/', json=data)

    def start_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Start a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        return self._request('POST', f'/api/deployments/{name}/start/')

    def stop_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Stop a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        return self._request('POST', f'/api/deployments/{name}/stop/')

    def restart_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Restart a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        return self._request('POST', f'/api/deployments/{name}/restart/')

    def delete_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Delete a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        return self._request('DELETE', f'/api/deployments/{name}/')

    def get_deployment_logs(
        self: Self,
        name: str,
        tail: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get deployment logs.
        
        Args:
            name: Deployment name.
            tail: Number of lines to retrieve from end of log.
            
        Returns:
            Dictionary containing log data.
        """
        params = {}
        if tail:
            params['tail'] = tail
        return self._request('GET', f'/api/deployments/{name}/logs/', params=params)

    # Databases
    def list_databases(self: Self) -> Dict[str, Any]:
        """List all databases.
        
        Returns:
            Dictionary containing database list.
        """
        return self._request('GET', '/api/databases/')

    def get_database(self: Self, name: str) -> Dict[str, Any]:
        """Get database details by name.
        
        Args:
            name: Database name.
            
        Returns:
            Dictionary containing database details.
        """
        return self._request('GET', f'/api/databases/{name}/')

    # Environment Variables
    def generate_env(
        self: Self,
        deployment_name: str,
        debug: bool = False,
        domain: Optional[str] = None,
        custom_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Generate environment file for deployment.
        
        Args:
            deployment_name: Name of the deployment.
            debug: Enable debug mode.
            domain: Custom domain name.
            custom_vars: Additional environment variables.
            
        Returns:
            Dictionary containing generated environment configuration.
        """
        data = {
            'debug': debug,
        }
        if domain:
            data['domain'] = domain
        if custom_vars:
            data['custom_vars'] = custom_vars

        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/generate/',
            json=data
        )

    def validate_env(self: Self, deployment_name: str) -> Dict[str, Any]:
        """Validate environment configuration for deployment.
        
        Args:
            deployment_name: Name of the deployment.
            
        Returns:
            Dictionary containing validation results.
        """
        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/validate/'
        )

    def validate_project(self: Self, deployment_name: str) -> Dict[str, Any]:
        """Validate project structure and requirements.
        
        Args:
            deployment_name: Name of the deployment.
            
        Returns:
            Dictionary containing validation results.
        """
        return self._request(
            'GET',
            f'/api/deployments/{deployment_name}/project/validate/'
        )

    def get_env_vars(self: Self, deployment_name: str) -> Dict[str, Any]:
        """Get environment variables for deployment.
        
        Args:
            deployment_name: Name of the deployment.
            
        Returns:
            Dictionary containing environment variables.
        """
        return self._request(
            'GET',
            f'/api/deployments/{deployment_name}/env/'
        )

    def set_env_var(
        self: Self,
        deployment_name: str,
        key: str,
        value: str
    ) -> Dict[str, Any]:
        """Set environment variable for deployment.
        
        Args:
            deployment_name: Name of the deployment.
            key: Environment variable key.
            value: Environment variable value.
            
        Returns:
            Dictionary containing operation result.
        """
        data = {
            'key': key,
            'value': value
        }
        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/set/',
            json=data
        )

    def unset_env_var(
        self: Self,
        deployment_name: str,
        key: str
    ) -> Dict[str, Any]:
        """Remove environment variable from deployment.
        
        Args:
            deployment_name: Name of the deployment.
            key: Environment variable key to remove.
            
        Returns:
            Dictionary containing operation result.
        """
        data = {
            'key': key
        }
        return self._request(
            'POST',
            f'/api/deployments/{deployment_name}/env/unset/',
            json=data
        )
