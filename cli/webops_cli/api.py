"""API client for WebOps with enhanced security features."""

import json
import time
from typing import Dict, Any, Optional, List, Self, Union
from datetime import datetime, timezone, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException

from .validators import InputValidator, ValidationError
from .encryption import EncryptionError
from .security_logging import SecurityLogger, SecurityEventType, get_security_logger


class WebOpsAPIError(Exception):
    """Base exception for API errors."""
    pass


class RBACError(Exception):
    """Raised when RBAC authorization fails."""
    pass


class TokenExpiredError(Exception):
    """Raised when authentication token has expired."""
    pass


class Role:
    """User roles for RBAC."""
    
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    
    @classmethod
    def all_roles(cls) -> List[str]:
        """Get all available roles."""
        return [cls.ADMIN, cls.DEVELOPER, cls.VIEWER]
    
    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        """Check if a role is valid."""
        return role in cls.all_roles()


class Permission:
    """Permissions for RBAC."""
    
    # Deployment permissions
    DEPLOYMENT_CREATE = "deployment:create"
    DEPLOYMENT_READ = "deployment:read"
    DEPLOYMENT_UPDATE = "deployment:update"
    DEPLOYMENT_DELETE = "deployment:delete"
    DEPLOYMENT_START = "deployment:start"
    DEPLOYMENT_STOP = "deployment:stop"
    DEPLOYMENT_RESTART = "deployment:restart"
    DEPLOYMENT_LOGS = "deployment:logs"
    
    # Database permissions
    DATABASE_CREATE = "database:create"
    DATABASE_READ = "database:read"
    DATABASE_UPDATE = "database:update"
    DATABASE_DELETE = "database:delete"
    DATABASE_CREDENTIALS = "database:credentials"
    
    # Configuration permissions
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"
    
    # System permissions
    SYSTEM_STATUS = "system:status"
    SYSTEM_ADMIN = "system:admin"
    
    @classmethod
    def all_permissions(cls) -> List[str]:
        """Get all available permissions."""
        return [
            cls.DEPLOYMENT_CREATE, cls.DEPLOYMENT_READ, cls.DEPLOYMENT_UPDATE,
            cls.DEPLOYMENT_DELETE, cls.DEPLOYMENT_START, cls.DEPLOYMENT_STOP,
            cls.DEPLOYMENT_RESTART, cls.DEPLOYMENT_LOGS,
            cls.DATABASE_CREATE, cls.DATABASE_READ, cls.DATABASE_UPDATE,
            cls.DATABASE_DELETE, cls.DATABASE_CREDENTIALS,
            cls.CONFIG_READ, cls.CONFIG_UPDATE,
            cls.SYSTEM_STATUS, cls.SYSTEM_ADMIN
        ]


class RBACManager:
    """Role-based access control manager."""
    
    # Role permissions mapping
    ROLE_PERMISSIONS = {
        Role.ADMIN: Permission.all_permissions(),
        Role.DEVELOPER: [
            Permission.DEPLOYMENT_CREATE, Permission.DEPLOYMENT_READ,
            Permission.DEPLOYMENT_UPDATE, Permission.DEPLOYMENT_START,
            Permission.DEPLOYMENT_STOP, Permission.DEPLOYMENT_RESTART,
            Permission.DEPLOYMENT_LOGS,
            Permission.DATABASE_CREATE, Permission.DATABASE_READ,
            Permission.DATABASE_UPDATE, Permission.DATABASE_DELETE,
            Permission.CONFIG_READ, Permission.CONFIG_UPDATE,
            Permission.SYSTEM_STATUS
        ],
        Role.VIEWER: [
            Permission.DEPLOYMENT_READ, Permission.DEPLOYMENT_LOGS,
            Permission.DATABASE_READ,
            Permission.CONFIG_READ,
            Permission.SYSTEM_STATUS
        ]
    }
    
    def __init__(self, user_role: str) -> None:
        """Initialize RBAC manager.
        
        Args:
            user_role: User role
            
        Raises:
            RBACError: If role is invalid
        """
        if not Role.is_valid_role(user_role):
            raise RBACError(f"Invalid role: {user_role}")
        
        self.user_role = user_role
        self.permissions = set(self.ROLE_PERMISSIONS.get(user_role, []))
    
    def check_permission(self, permission: str) -> bool:
        """Check if user has a specific permission.
        
        Args:
            permission: Permission to check
            
        Returns:
            True if user has permission, False otherwise
        """
        return permission in self.permissions
    
    def require_permission(self, permission: str) -> None:
        """Require a specific permission.
        
        Args:
            permission: Required permission
            
        Raises:
            RBACError: If user doesn't have permission
        """
        if not self.check_permission(permission):
            raise RBACError(f"Access denied: {permission} required for role {self.user_role}")
    
    def get_permissions(self) -> List[str]:
        """Get all permissions for the user.
        
        Returns:
            List of permissions
        """
        return list(self.permissions)


class WebOpsAPIClient:
    """Enhanced client for WebOps REST API with security features."""

    def __init__(
        self: Self,
        base_url: str,
        token: str,
        user_role: str = Role.DEVELOPER,
        timeout: int = 30,
        max_retries: int = 3,
        enable_security: bool = False
    ) -> None:
        """Initialize API client.

        Args:
            base_url: Base URL of WebOps panel (e.g., https://panel.example.com)
            token: API authentication token
            user_role: User role for RBAC (when security is enabled)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            enable_security: Enable security features (RBAC, logging, etc.)
        """
        # Validate inputs
        self.base_url = InputValidator.validate_url(base_url) if enable_security else base_url.rstrip('/')
        self.token = InputValidator.validate_api_token(token) if enable_security else token
        self.enable_security = enable_security
        
        # Initialize security features if enabled
        if self.enable_security:
            # Initialize RBAC
            self.rbac = RBACManager(user_role)
            
            # Security logging
            self.security_logger = get_security_logger()
            self.user = self.security_logger.get_user()
            
            # Log authentication
            self.security_logger.log_authentication(
                user=self.user,
                success=True,
                method="token"
            )
        
        # Session configuration
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Setup session with connection pooling
        self._setup_session()
    
    def _setup_session(self) -> None:
        """Setup session with connection pooling and retry strategy."""
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Create adapter with connection pooling
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=retry_strategy
        )
        
        # Mount adapters for both http and https
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'User-Agent': 'webops-cli/0.1.0'
        })
    
    def _validate_token(self) -> None:
        """Validate token and refresh if needed."""
        # Check if token is expired
        if hasattr(self, 'token_expiry') and self.token_expiry:
            if datetime.now(timezone.utc) >= self.token_expiry:
                self._refresh_token()
    
    def _refresh_token(self) -> None:
        """Refresh authentication token."""
        try:
            # This would be implemented based on the API's token refresh endpoint
            # For now, we'll just log the attempt
            if self.enable_security:
                self.security_logger.log_authentication(
                    user=self.user,
                    success=False,
                    method="token_refresh",
                    details={"reason": "Token expired"}
                )
            
            # In a real implementation, this would call the refresh endpoint
            # and update self.token and self.token_expiry
            raise TokenExpiredError("Token refresh not implemented")
            
        except Exception as e:
            if self.enable_security:
                self.security_logger.log_error(
                    user=self.user,
                    error_type="token_refresh_failed",
                    error_message=str(e)
                )
            raise TokenExpiredError(f"Failed to refresh token: {e}")
    
    def _request(
        self: Self,
        method: str,
        endpoint: str,
        permission: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make HTTP request with optional security checks.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            permission: Required permission for RBAC
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response as dictionary
            
        Raises:
            RBACError: If user doesn't have required permission (when security enabled)
            WebOpsAPIError: If request fails
        """
        # Check RBAC permission if security is enabled
        if self.enable_security and permission:
            self.rbac.require_permission(permission)
        
        # Validate token if security is enabled
        if self.enable_security:
            self._validate_token()
        
        # Log data access if security is enabled
        if self.enable_security:
            self.security_logger.log_data_access(
                user=self.user,
                resource_type="api",
                resource_name=endpoint,
                action=method.lower()
            )
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            # Parse response
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.Timeout as e:
            if self.enable_security:
                self.security_logger.log_error(
                    user=self.user,
                    error_type="request_timeout",
                    error_message=str(e),
                    details={"url": url, "method": method}
                )
            raise WebOpsAPIError(f"Request timeout: {e}")
            
        except requests.exceptions.ConnectionError as e:
            if self.enable_security:
                self.security_logger.log_error(
                    user=self.user,
                    error_type="connection_error",
                    error_message=str(e),
                    details={"url": url, "method": method}
                )
            raise WebOpsAPIError(f"Connection error: {e}")
            
        except requests.exceptions.HTTPError as e:
            error_details = {"url": url, "method": method, "status_code": e.response.status_code}
            
            # Try to parse error response
            try:
                error_data = e.response.json()
                error_details["error_response"] = error_data
                error_msg = error_data.get('error', str(e))
            except (ValueError, json.JSONDecodeError):
                error_msg = e.response.text or str(e)
            
            if self.enable_security:
                self.security_logger.log_error(
                    user=self.user,
                    error_type="http_error",
                    error_message=error_msg,
                    details=error_details
                )
                
                # Check for authentication errors
                if e.response.status_code == 401:
                    self.security_logger.log_authentication(
                        user=self.user,
                        success=False,
                        method="token",
                        details={"reason": "HTTP 401 Unauthorized"}
                    )
            
            raise WebOpsAPIError(error_msg)
            
        except Exception as e:
            if self.enable_security:
                self.security_logger.log_error(
                    user=self.user,
                    error_type="unexpected_error",
                    error_message=str(e),
                    details={"url": url, "method": method}
                )
            raise WebOpsAPIError(f"Unexpected error: {e}")

    def close(self) -> None:
        """Close the session and cleanup resources."""
        if self.session:
            self.session.close()
    
    def __enter__(self: Self) -> Self:
        """Context manager entry."""
        return self
    
    def __exit__(self: Self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    # Status
    def get_status(self: Self) -> Dict[str, Any]:
        """Get API status.
        
        Returns:
            Dictionary containing API status information.
        """
        permission = Permission.SYSTEM_STATUS if self.enable_security else None
        return self._request('GET', '/api/status/', permission)

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
        
        permission = Permission.DEPLOYMENT_READ if self.enable_security else None
        return self._request('GET', '/api/deployments/', permission, params=params)

    def get_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Get deployment details by name.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing deployment details.
        """
        # Validate input if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
        else:
            validated_name = name
        
        permission = Permission.DEPLOYMENT_READ if self.enable_security else None
        return self._request('GET', f'/api/deployments/{validated_name}/', permission)

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
        # Validate inputs if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
            validated_repo = InputValidator.validate_git_url(repo_url)
            validated_branch = InputValidator.validate_git_branch(branch)
            validated_domain = InputValidator.validate_domain_name(domain)
        else:
            validated_name = name
            validated_repo = repo_url
            validated_branch = branch
            validated_domain = domain
        
        data = {
            'name': validated_name,
            'repo_url': validated_repo,
            'branch': validated_branch,
            'domain': validated_domain,
            'env_vars': env_vars or {}
        }
        
        permission = Permission.DEPLOYMENT_CREATE if self.enable_security else None
        result = self._request('POST', '/api/deployments/create/', permission, json=data)
        
        # Log deployment operation if security is enabled
        if self.enable_security:
            self.security_logger.log_deployment_operation(
                user=self.user,
                operation="create",
                deployment=validated_name,
                success=True
            )
        
        return result

    def start_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Start a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        # Validate input if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
        else:
            validated_name = name
        
        permission = Permission.DEPLOYMENT_START if self.enable_security else None
        result = self._request('POST', f'/api/deployments/{validated_name}/start/', permission)
        
        # Log deployment operation if security is enabled
        if self.enable_security:
            self.security_logger.log_deployment_operation(
                user=self.user,
                operation="start",
                deployment=validated_name,
                success=True
            )
        
        return result

    def stop_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Stop a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        # Validate input if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
        else:
            validated_name = name
        
        permission = Permission.DEPLOYMENT_STOP if self.enable_security else None
        result = self._request('POST', f'/api/deployments/{validated_name}/stop/', permission)
        
        # Log deployment operation if security is enabled
        if self.enable_security:
            self.security_logger.log_deployment_operation(
                user=self.user,
                operation="stop",
                deployment=validated_name,
                success=True
            )
        
        return result

    def restart_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Restart a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        # Validate input if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
        else:
            validated_name = name
        
        permission = Permission.DEPLOYMENT_RESTART if self.enable_security else None
        result = self._request('POST', f'/api/deployments/{validated_name}/restart/', permission)
        
        # Log deployment operation if security is enabled
        if self.enable_security:
            self.security_logger.log_deployment_operation(
                user=self.user,
                operation="restart",
                deployment=validated_name,
                success=True
            )
        
        return result

    def delete_deployment(self: Self, name: str) -> Dict[str, Any]:
        """Delete a deployment.
        
        Args:
            name: Deployment name.
            
        Returns:
            Dictionary containing operation result.
        """
        # Validate input if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
        else:
            validated_name = name
        
        permission = Permission.DEPLOYMENT_DELETE if self.enable_security else None
        result = self._request('DELETE', f'/api/deployments/{validated_name}/', permission)
        
        # Log deployment operation if security is enabled
        if self.enable_security:
            self.security_logger.log_deployment_operation(
                user=self.user,
                operation="delete",
                deployment=validated_name,
                success=True
            )
        
        return result

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
        # Validate inputs if security is enabled
        if self.enable_security:
            validated_name = InputValidator.validate_deployment_name(name)
            validated_tail = InputValidator.validate_tail_count(tail)
        else:
            validated_name = name
            validated_tail = tail
        
        params = {}
        if validated_tail:
            params['tail'] = validated_tail
        
        permission = Permission.DEPLOYMENT_LOGS if self.enable_security else None
        return self._request('GET', f'/api/deployments/{validated_name}/logs/', permission, params=params)

    # Databases
    def list_databases(self: Self) -> Dict[str, Any]:
        """List all databases.
        
        Returns:
            Dictionary containing database list.
        """
        permission = Permission.DATABASE_READ if self.enable_security else None
        return self._request('GET', '/api/databases/', permission)

    def get_database(self: Self, name: str) -> Dict[str, Any]:
        """Get database details by name.
        
        Args:
            name: Database name.
            
        Returns:
            Dictionary containing database details.
        """
        permission = Permission.DATABASE_READ if self.enable_security else None
        return self._request('GET', f'/api/databases/{name}/', permission)

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
