"""Enhanced CLI features for WebOps.

This module provides enhanced CLI features including improved error handling,
better user experience, and additional utility commands.
"""

from typing import Dict, Any, List, Self

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from .config import Config
from .errors import ErrorHandler

console = Console()
error_handler = ErrorHandler()
config = Config()


class EnhancedCLI:
    """Enhanced CLI functionality for WebOps."""
    
    def __init__(self: Self) -> None:
        """Initialize enhanced CLI features."""
        self.console = console
        self.error_handler = error_handler
        
    def display_deployment_table(
        self: Self, 
        deployments: List[Dict[str, Any]], 
        title: str = "Deployments"
    ) -> None:
        """Display deployments in a formatted table.
        
        Args:
            deployments: List of deployment dictionaries.
            title: Table title to display.
        """
        if not deployments:
            self.console.print("[yellow]No deployments found.[/yellow]")
            return
            
        table = Table(title=title, show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Domain", style="blue")
        table.add_column("Branch", style="green")
        table.add_column("Created", style="dim")
        
        for deployment in deployments:
            status_style = self._get_status_style(deployment.get('status', 'unknown'))
            table.add_row(
                deployment.get('name', 'N/A'),
                f"[{status_style}]{deployment.get('status', 'unknown')}[/{status_style}]",
                deployment.get('domain', 'N/A'),
                deployment.get('branch', 'N/A'),
                deployment.get('created_at', 'N/A')
            )
        
        self.console.print(table)
    
    def _get_status_style(self: Self, status: str) -> str:
        """Get Rich style for deployment status.
        
        Args:
            status: Deployment status string.
            
        Returns:
            Rich style string for the status.
        """
        status_styles = {
            'running': 'green',
            'stopped': 'red',
            'building': 'yellow',
            'failed': 'bold red',
            'pending': 'blue'
        }
        return status_styles.get(status.lower(), 'white')
    
    def confirm_destructive_action(
        self: Self, 
        action: str, 
        resource: str,
        force: bool = False
    ) -> bool:
        """Confirm destructive actions with user.
        
        Args:
            action: The action being performed (e.g., "delete", "stop").
            resource: The resource being acted upon.
            force: Whether to skip confirmation.
            
        Returns:
            True if action should proceed, False otherwise.
        """
        if force:
            return True
            
        self.console.print(
            Panel(
                f"[bold red]Warning:[/bold red] You are about to {action} '{resource}'.\n"
                f"This action cannot be undone.",
                title="Confirmation Required",
                border_style="red"
            )
        )
        
        return Confirm.ask(f"Are you sure you want to {action} '{resource}'?")
    
    def display_logs_with_formatting(
        self: Self, 
        logs: List[str], 
        deployment_name: str
    ) -> None:
        """Display logs with syntax highlighting and formatting.
        
        Args:
            logs: List of log lines.
            deployment_name: Name of the deployment.
        """
        if not logs:
            self.console.print("[yellow]No logs available.[/yellow]")
            return
            
        self.console.print(
            Panel(
                f"Logs for [cyan]{deployment_name}[/cyan]",
                border_style="blue"
            )
        )
        
        for line in logs:
            # Basic log level highlighting
            if 'ERROR' in line or 'CRITICAL' in line:
                self.console.print(f"[red]{line}[/red]")
            elif 'WARNING' in line or 'WARN' in line:
                self.console.print(f"[yellow]{line}[/yellow]")
            elif 'INFO' in line:
                self.console.print(f"[blue]{line}[/blue]")
            elif 'DEBUG' in line:
                self.console.print(f"[dim]{line}[/dim]")
            else:
                self.console.print(line)


# Enhanced command decorators
def handle_api_errors(func: Any) -> Any:
    """Decorator to handle API errors gracefully.
    
    Args:
        func: The function to wrap.
        
    Returns:
        Wrapped function with error handling.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_handler.display_error(e, f"Error in {func.__name__}")
            return None
    return wrapper


def require_config(func: Any) -> Any:
    """Decorator to ensure CLI is configured before running commands.
    
    Args:
        func: The function to wrap.
        
    Returns:
        Wrapped function with configuration check.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not config.is_configured():
            console.print("[red]Error:[/red] WebOps CLI is not configured.")
            console.print("Run: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
            return None
        return func(*args, **kwargs)
    return wrapper