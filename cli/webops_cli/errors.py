"""Enhanced error handling and recovery suggestions for WebOps CLI.

This module provides improved error handling with contextual recovery suggestions
and better user feedback for common WebOps CLI issues.
"""

import sys
from typing import Any, Dict, List, Optional, Self

from rich.console import Console
from rich.panel import Panel

console = Console()


class WebOpsError(Exception):
    """Base exception class for WebOps CLI errors."""
    
    def __init__(self: Self, message: str, suggestions: Optional[List[str]] = None) -> None:
        """Initialize WebOps error.
        
        Args:
            message: The error message to display.
            suggestions: Optional list of recovery suggestions.
        """
        super().__init__(message)
        self.message = message
        self.suggestions = suggestions or []


class ConfigurationError(WebOpsError):
    """Raised when there are configuration issues."""
    pass


class ConnectionError(WebOpsError):
    """Raised when there are API connection issues."""
    pass


class PermissionError(WebOpsError):
    """Raised when there are permission issues."""
    pass


class ServiceError(WebOpsError):
    """Raised when there are service-related issues."""
    pass


class ErrorHandler:
    """Handles and displays errors with recovery suggestions."""
    
    def __init__(self: Self) -> None:
        """Initialize the error handler."""
        self.error_patterns: Dict[str, Dict[str, Any]] = {
            "connection_refused": {
                "keywords": ["connection refused", "connection error", "timeout"],
                "suggestions": [
                    "Check if the WebOps control panel is running",
                    "Verify the URL in your configuration: webops config --url <URL>",
                    "Check network connectivity to the WebOps server",
                    "Ensure the control panel service is started: sudo systemctl start webops-web"
                ]
            },
            "authentication_failed": {
                "keywords": ["401", "unauthorized", "authentication failed", "invalid token"],
                "suggestions": [
                    "Check your API token: webops config --token <TOKEN>",
                    "Generate a new API token from the WebOps control panel",
                    "Verify your user account has the necessary permissions",
                    "Try logging out and back in to the control panel"
                ]
            },
            "permission_denied": {
                "keywords": ["permission denied", "403", "forbidden", "not allowed"],
                "suggestions": [
                    "Run the command with sudo if it requires admin privileges",
                    "Check if your user account has the necessary permissions",
                    "Verify you're in the correct user context",
                    "Contact your WebOps administrator for access"
                ]
            },
            "service_not_found": {
                "keywords": ["service not found", "404", "not found", "does not exist"],
                "suggestions": [
                    "Check the spelling of the service/deployment name",
                    "List available deployments: webops list",
                    "Verify the deployment exists and is accessible",
                    "Check if you have permission to access this resource"
                ]
            },
            "database_error": {
                "keywords": ["database", "connection error", "operational error", "sqlite", "postgresql"],
                "suggestions": [
                    "Check if the database service is running",
                    "Verify database connection settings in the control panel",
                    "Run database migrations: webops admin run 'python manage.py migrate'",
                    "Check database permissions and connectivity"
                ]
            },
            "celery_error": {
                "keywords": ["celery", "worker", "broker", "redis", "rabbitmq"],
                "suggestions": [
                    "Check if Celery services are running: sudo systemctl status webops-celery",
                    "Restart Celery services: sudo systemctl restart webops-celery",
                    "Verify message broker (Redis/RabbitMQ) is accessible",
                    "Check Celery configuration in the control panel"
                ]
            },
            "disk_space": {
                "keywords": ["no space left", "disk full", "storage", "quota exceeded"],
                "suggestions": [
                    "Check disk usage: webops system disk",
                    "Clean up old deployment files and logs",
                    "Remove unused Docker images and containers",
                    "Consider expanding storage or moving files to external storage"
                ]
            },
            "python_environment": {
                "keywords": ["python", "module not found", "import error", "virtual environment"],
                "suggestions": [
                    "Ensure the virtual environment is activated",
                    "Install missing dependencies: pip install -r requirements.txt",
                    "Check Python version compatibility",
                    "Recreate the virtual environment if corrupted"
                ]
            },
            "git_error": {
                "keywords": ["git", "repository", "clone", "fetch", "authentication"],
                "suggestions": [
                    "Verify the repository URL is correct and accessible",
                    "Check Git credentials and SSH keys",
                    "Ensure the repository branch exists",
                    "Try cloning the repository manually to test access"
                ]
            },
            "port_in_use": {
                "keywords": ["port", "address already in use", "bind", "listen"],
                "suggestions": [
                    "Check what's using the port: sudo netstat -tlnp | grep <port>",
                    "Stop conflicting services or change the port configuration",
                    "Kill processes using the port: sudo kill <pid>",
                    "Configure a different port in the application settings"
                ]
            }
        }
    
    def identify_error_type(self: Self, error_message: str) -> Optional[str]:
        """Identify the type of error based on the message.
        
        Args:
            error_message: The error message to analyze.
            
        Returns:
            The error type key if identified, None otherwise.
        """
        error_lower = error_message.lower()
        
        for error_type, pattern_data in self.error_patterns.items():
            for keyword in pattern_data["keywords"]:
                if keyword in error_lower:
                    return error_type
        
        return None
    
    def get_suggestions(self: Self, error_message: str) -> List[str]:
        """Get recovery suggestions for an error.
        
        Args:
            error_message: The error message to analyze.
            
        Returns:
            List of recovery suggestions.
        """
        error_type = self.identify_error_type(error_message)
        
        if error_type and error_type in self.error_patterns:
            return self.error_patterns[error_type]["suggestions"]
        
        # Generic suggestions if no specific pattern matches
        return [
            "Check the WebOps documentation for troubleshooting guides",
            "Verify your configuration: webops config",
            "Run system health check: webops system health",
            "Check service status: webops system services",
            "Review logs for more details: webops logs <service>"
        ]
    
    def display_error(
        self: Self,
        error: Exception,
        context: Optional[str] = None,
        show_suggestions: bool = True
    ) -> None:
        """Display an error with formatting and suggestions.
        
        Args:
            error: The exception that occurred.
            context: Optional context about what was being attempted.
            show_suggestions: Whether to show recovery suggestions.
        """
        error_message = str(error)
        
        # Create error panel content
        content = []
        
        if context:
            content.append(f"[bold]Context:[/bold] {context}")
            content.append("")
        
        content.append(f"[bold red]Error:[/bold red] {error_message}")
        
        # Add suggestions if requested
        if show_suggestions:
            suggestions = []
            
            # Get suggestions from WebOpsError if available
            if isinstance(error, WebOpsError) and error.suggestions:
                suggestions = error.suggestions
            else:
                suggestions = self.get_suggestions(error_message)
            
            if suggestions:
                content.append("")
                content.append("[bold blue]Suggested solutions:[/bold blue]")
                for i, suggestion in enumerate(suggestions, 1):
                    content.append(f"  {i}. {suggestion}")
        
        # Display the error panel
        console.print(Panel(
            "\n".join(content),
            title="[bold red]WebOps CLI Error[/bold red]",
            border_style="red",
            expand=False
        ))
    
    def handle_api_error(self: Self, error: Exception, operation: str) -> None:
        """Handle API-related errors with specific context.
        
        Args:
            error: The API exception that occurred.
            operation: Description of the operation that failed.
        """
        error_message = str(error)
        
        # Determine if it's a connection or authentication issue
        if any(keyword in error_message.lower() for keyword in ["connection", "timeout", "refused"]):
            suggestions = [
                "Check if the WebOps control panel is running",
                "Verify the panel URL: webops config",
                "Test connectivity: ping <panel-host>",
                "Check firewall settings and network access"
            ]
        elif any(keyword in error_message.lower() for keyword in ["401", "unauthorized", "token"]):
            suggestions = [
                "Verify your API token: webops config",
                "Generate a new token from the control panel",
                "Check token permissions and expiration",
                "Re-authenticate with the control panel"
            ]
        else:
            suggestions = self.get_suggestions(error_message)
        
        api_error = WebOpsError(error_message, suggestions)
        self.display_error(api_error, f"Failed to {operation}")
    
    def handle_system_error(self: Self, error: Exception, component: str) -> None:
        """Handle system-related errors with specific context.
        
        Args:
            error: The system exception that occurred.
            component: The system component that failed.
        """
        error_message = str(error)
        
        # Component-specific suggestions
        component_suggestions = {
            "database": [
                "Check database service status: sudo systemctl status postgresql",
                "Verify database connection settings",
                "Run database health check: webops system health",
                "Check database logs for errors"
            ],
            "celery": [
                "Check Celery services: sudo systemctl status webops-celery",
                "Restart Celery: sudo systemctl restart webops-celery",
                "Verify message broker connectivity",
                "Check Celery worker logs"
            ],
            "web": [
                "Check web service: sudo systemctl status webops-web",
                "Verify web server configuration",
                "Check application logs for errors",
                "Test web server connectivity"
            ]
        }
        
        suggestions = component_suggestions.get(component.lower(), self.get_suggestions(error_message))
        system_error = WebOpsError(error_message, suggestions)
        self.display_error(system_error, f"{component.title()} component error")


def handle_exception(
    error: Exception,
    context: Optional[str] = None,
    exit_code: int = 1
) -> None:
    """Global exception handler for WebOps CLI.
    
    Args:
        error: The exception that occurred.
        context: Optional context about what was being attempted.
        exit_code: Exit code to use when terminating.
    """
    error_handler = ErrorHandler()
    error_handler.display_error(error, context)
    sys.exit(exit_code)


def handle_keyboard_interrupt() -> None:
    """Handle Ctrl+C gracefully."""
    console.print("\n[yellow]Operation cancelled by user[/yellow]")
    sys.exit(130)  # Standard exit code for SIGINT


def validate_configuration() -> None:
    """Validate CLI configuration and provide helpful errors.
    
    Raises:
        ConfigurationError: If configuration is invalid or missing.
    """
    from .config import Config
    
    config = Config()
    
    if not config.is_configured():
        raise ConfigurationError(
            "WebOps CLI is not configured",
            [
                "Configure the CLI: webops config --url <URL> --token <TOKEN>",
                "Get your API token from the WebOps control panel",
                "Ensure the control panel is accessible at the specified URL",
                "Check the getting started guide in the documentation"
            ]
        )
    
    # Validate URL format
    url = config.get_url()
    if url and not (url.startswith('http://') or url.startswith('https://')):
        raise ConfigurationError(
            f"Invalid URL format: {url}",
            [
                "URL must start with http:// or https://",
                "Example: https://webops.example.com",
                "Update configuration: webops config --url <CORRECT_URL>"
            ]
        )
    
    # Validate token format (basic check)
    token = config.get_token()
    if token and len(token) < 10:
        raise ConfigurationError(
            "API token appears to be invalid (too short)",
            [
                "Generate a new API token from the control panel",
                "Ensure you copied the complete token",
                "Update configuration: webops config --token <NEW_TOKEN>"
            ]
        )


def require_root_privileges(operation: str) -> None:
    """Check for root privileges and provide helpful error if missing.
    
    Args:
        operation: Description of the operation requiring root access.
        
    Raises:
        PermissionError: If not running as root.
    """
    import os
    
    if os.geteuid() != 0:
        raise PermissionError(
            f"{operation} requires root privileges",
            [
                f"Run with sudo: sudo webops {operation}",
                "Ensure your user account has sudo access",
                "Contact your system administrator if needed",
                "Check the WebOps documentation for permission requirements"
            ]
        )