"""Display utilities for WebOps CLI.

This module provides shared display functions to avoid circular imports.
"""

from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table

console = Console()


def display_deployment_table(
    deployments: List[Dict[str, Any]],
    title: str = "Deployments"
) -> None:
    """Display deployments in a formatted table.
    
    Args:
        deployments: List of deployment dictionaries.
        title: Table title to display.
    """
    if not deployments:
        console.print("[yellow]No deployments found.[/yellow]")
        return
        
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Domain", style="blue")
    table.add_column("Branch", style="green")
    table.add_column("Created", style="dim")
    
    for deployment in deployments:
        status_style = _get_status_style(deployment.get('status', 'unknown'))
        table.add_row(
            deployment.get('name', 'N/A'),
            f"[{status_style}]{deployment.get('status', 'unknown')}[/{status_style}]",
            deployment.get('domain', 'N/A'),
            deployment.get('branch', 'N/A'),
            deployment.get('created_at', 'N/A')
        )
    
    console.print(table)


def _get_status_style(status: str) -> str:
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