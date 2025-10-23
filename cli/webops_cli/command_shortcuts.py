"""Command shortcuts and aliases for WebOps CLI.

This module provides convenient shortcuts and aliases for common operations,
improving CLI efficiency and user experience.
"""

from typing import Any, Dict, List, Optional, Self
import click
from rich.console import Console

from .api import WebOpsAPIClient
from .config import Config
from .ui.display import display_deployment_table
from .errors import WebOpsError

console = Console()


class CommandShortcuts:
    """Convenient shortcuts for common WebOps operations."""
    
    def __init__(self: Self, api_client: Optional[WebOpsAPIClient], config: Config) -> None:
        """Initialize command shortcuts.
        
        Args:
            api_client: WebOps API client instance (can be None for some operations).
            config: Configuration instance.
        """
        self.api_client = api_client
        self.config = config
    
    def quick_deploy(
        self: Self,
        name: str,
        repo_url: str,
        branch: str = "main",
        domain: Optional[str] = None,
        auto_start: bool = True
    ) -> None:
        """Quick deployment creation and start.
        
        Args:
            name: Deployment name.
            repo_url: Repository URL.
            branch: Git branch to deploy.
            domain: Optional domain name.
            auto_start: Whether to start deployment automatically.
        """
        try:
            console.print(f"[cyan]Creating deployment '{name}'...[/cyan]")
            
            deployment_data = {
                'name': name,
                'repo_url': repo_url,
                'branch': branch
            }
            
            if domain:
                deployment_data['domain'] = domain
            
            # Create deployment
            result = self.api_client.create_deployment(deployment_data)
            console.print(f"[green]✓ Deployment '{name}' created successfully[/green]")
            
            # Auto-start if requested
            if auto_start:
                console.print(f"[cyan]Starting deployment '{name}'...[/cyan]")
                self.api_client.start_deployment(name)
                console.print(f"[green]✓ Deployment '{name}' started successfully[/green]")
                
        except WebOpsError as e:
            console.print(f"[red]✗ Quick deploy failed: {e}[/red]")
    
    def quick_restart(self: Self, deployment_name: str) -> None:
        """Quick deployment restart.
        
        Args:
            deployment_name: Name of deployment to restart.
        """
        try:
            console.print(f"[cyan]Restarting deployment '{deployment_name}'...[/cyan]")
            self.api_client.restart_deployment(deployment_name)
            console.print(f"[green]✓ Deployment '{deployment_name}' restarted successfully[/green]")
        except WebOpsError as e:
            console.print(f"[red]✗ Restart failed: {e}[/red]")
    
    def quick_stop(self: Self, deployment_name: str) -> None:
        """Quick deployment stop.
        
        Args:
            deployment_name: Name of deployment to stop.
        """
        try:
            console.print(f"[cyan]Stopping deployment '{deployment_name}'...[/cyan]")
            self.api_client.stop_deployment(deployment_name)
            console.print(f"[green]✓ Deployment '{deployment_name}' stopped successfully[/green]")
        except WebOpsError as e:
            console.print(f"[red]✗ Stop failed: {e}[/red]")
    
    def quick_status(self: Self, deployment_name: Optional[str] = None) -> None:
        """Quick status check.
        
        Args:
            deployment_name: Optional specific deployment to check.
        """
        try:
            if deployment_name:
                # Show specific deployment status
                deployment = self.api_client.get_deployment(deployment_name)
                console.print(f"[cyan]Status for '{deployment_name}':[/cyan]")
                console.print(f"  Status: {deployment.get('status', 'unknown')}")
                console.print(f"  Health: {deployment.get('health', 'unknown')}")
                console.print(f"  Domain: {deployment.get('domain', 'N/A')}")
            else:
                # Show all deployments
                deployments = self.api_client.list_deployments()
                display_deployment_table(deployments)
                
        except WebOpsError as e:
            console.print(f"[red]✗ Status check failed: {e}[/red]")
    
    def quick_logs(self: Self, deployment_name: str, lines: int = 50) -> None:
        """Quick logs display.
        
        Args:
            deployment_name: Name of deployment to show logs for.
            lines: Number of log lines to display.
        """
        if not self.api_client:
            console.print("[red]✗ API client not available[/red]")
            return
            
        try:
            console.print(f"[cyan]Fetching logs for '{deployment_name}' (last {lines} lines)...[/cyan]")
            logs_response = self.api_client.get_deployment_logs(deployment_name)
            
            if logs_response and 'logs' in logs_response:
                logs = logs_response['logs']
                log_lines = logs.split('\n')
                display_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
                
                console.print(f"\n[dim]--- Logs for {deployment_name} ---[/dim]")
                for line in display_lines:
                    if line.strip():
                        console.print(line)
                console.print(f"[dim]--- End of logs ---[/dim]")
            else:
                console.print("[yellow]No logs available[/yellow]")
                
        except WebOpsError as e:
            console.print(f"[red]✗ Failed to fetch logs: {e}[/red]")
    
    def quick_env_set(self: Self, deployment_name: str, key: str, value: str) -> None:
        """Quick environment variable setting.
        
        Args:
            deployment_name: Name of deployment.
            key: Environment variable key.
            value: Environment variable value.
        """
        if not self.api_client:
            console.print("[red]✗ API client not available[/red]")
            return
            
        try:
            console.print(f"[cyan]Setting {key} for '{deployment_name}'...[/cyan]")
            self.api_client.set_env_var(deployment_name, key, value)
            console.print(f"[green]✓ Environment variable '{key}' set successfully[/green]")
        except WebOpsError as e:
            console.print(f"[red]✗ Failed to set environment variable: {e}[/red]")
    
    def quick_env_get(self: Self, deployment_name: str, key: Optional[str] = None) -> None:
        """Quick environment variable retrieval.
        
        Args:
            deployment_name: Name of deployment.
            key: Optional specific key to retrieve.
        """
        if not self.api_client:
            console.print("[red]✗ API client not available[/red]")
            return
            
        try:
            if key:
                # Get specific environment variable
                env_vars = self.api_client.get_env_vars(deployment_name)
                if key in env_vars:
                    console.print(f"[cyan]{key}=[/cyan]{env_vars[key]}")
                else:
                    console.print(f"[yellow]Environment variable '{key}' not found[/yellow]")
            else:
                # Get all environment variables
                env_vars = self.api_client.get_env_vars(deployment_name)
                if env_vars:
                    console.print(f"[cyan]Environment variables for '{deployment_name}':[/cyan]")
                    for k, v in env_vars.items():
                        console.print(f"  {k}={v}")
                else:
                    console.print("[yellow]No environment variables found[/yellow]")
                    
        except WebOpsError as e:
            console.print(f"[red]✗ Failed to get environment variables: {e}[/red]")
    
    def quick_health_check(self: Self) -> None:
        """Quick system health check."""
        if not self.api_client:
            console.print("[red]✗ API client not available[/red]")
            return
            
        try:
            console.print("[cyan]Performing system health check...[/cyan]")
            
            # Check API connectivity
            status = self.api_client.get_status()
            console.print("[green]✓ API connection: OK[/green]")
            
            # Check deployments
            deployments_response = self.api_client.list_deployments()
            deployments = deployments_response.get('results', [])
            running_count = len([d for d in deployments if isinstance(d, dict) and d.get('status') == 'running'])
            total_count = len(deployments)
            
            console.print(f"[green]✓ Deployments: {running_count}/{total_count} running[/green]")
            
            # Check system resources
            cpu_usage = status.get('cpu_usage', 0)
            memory_usage = status.get('memory_usage', 0)
            
            cpu_status = "OK" if cpu_usage < 80 else "HIGH"
            memory_status = "OK" if memory_usage < 80 else "HIGH"
            
            cpu_color = "green" if cpu_usage < 80 else "yellow"
            memory_color = "green" if memory_usage < 80 else "yellow"
            
            console.print(f"[{cpu_color}]✓ CPU usage: {cpu_usage:.1f}% ({cpu_status})[/{cpu_color}]")
            console.print(f"[{memory_color}]✓ Memory usage: {memory_usage:.1f}% ({memory_status})[/{memory_color}]")
            
            console.print("[green]✓ System health check completed[/green]")
            
        except WebOpsError as e:
            console.print(f"[red]✗ Health check failed: {e}[/red]")
    
    def list_shortcuts(self: Self) -> None:
        """Display available shortcuts and their usage."""
        shortcuts = [
            ("quick-deploy", "webops quick-deploy <name> <repo-url> [--branch=main] [--domain=example.com]"),
            ("quick-restart", "webops quick-restart <deployment-name>"),
            ("quick-stop", "webops quick-stop <deployment-name>"),
            ("quick-status", "webops quick-status [deployment-name]"),
            ("quick-logs", "webops quick-logs <deployment-name> [--lines=50]"),
            ("quick-env-set", "webops quick-env-set <deployment-name> <key> <value>"),
            ("quick-env-get", "webops quick-env-get <deployment-name> [key]"),
            ("health-check", "webops health-check"),
        ]
        
        console.print("[cyan]Available WebOps CLI Shortcuts:[/cyan]\n")
        
        for name, usage in shortcuts:
            console.print(f"[green]{name}[/green]")
            console.print(f"  {usage}\n")
        
        console.print("[dim]Use 'webops <command> --help' for detailed information about each command.[/dim]")


# CLI command implementations for shortcuts
def create_shortcut_commands(main_group: click.Group) -> None:
    """Create shortcut commands and add them to the main CLI group.
    
    Args:
        main_group: Main Click group to add commands to.
    """
    
    @main_group.command(name='quick-deploy')
    @click.argument('name')
    @click.argument('repo_url')
    @click.option('--branch', default='main', help='Git branch to deploy')
    @click.option('--domain', help='Domain name for the deployment')
    @click.option('--no-start', is_flag=True, help='Do not start deployment automatically')
    def quick_deploy_cmd(name: str, repo_url: str, branch: str, domain: Optional[str], no_start: bool) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick deployment creation and start."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_deploy(name, repo_url, branch, domain, not no_start)
    
    @main_group.command(name='quick-restart')
    @click.argument('deployment_name')
    def quick_restart_cmd(deployment_name: str) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick deployment restart."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_restart(deployment_name)
    
    @main_group.command(name='quick-stop')
    @click.argument('deployment_name')
    def quick_stop_cmd(deployment_name: str) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick deployment stop."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_stop(deployment_name)
    
    @main_group.command(name='quick-status')
    @click.argument('deployment_name', required=False)
    def quick_status_cmd(deployment_name: Optional[str]) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick status check."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_status(deployment_name)
    
    @main_group.command(name='quick-logs')
    @click.argument('deployment_name')
    @click.option('--lines', default=50, help='Number of log lines to display')
    def quick_logs_cmd(deployment_name: str, lines: int) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick logs display."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_logs(deployment_name, lines)
    
    @main_group.command(name='quick-env-set')
    @click.argument('deployment_name')
    @click.argument('key')
    @click.argument('value')
    def quick_env_set_cmd(deployment_name: str, key: str, value: str) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick environment variable setting."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_env_set(deployment_name, key, value)
    
    @main_group.command(name='quick-env-get')
    @click.argument('deployment_name')
    @click.argument('key', required=False)
    def quick_env_get_cmd(deployment_name: str, key: Optional[str]) -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick environment variable retrieval."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_env_get(deployment_name, key)
    
    @main_group.command(name='health-check')
    def health_check_cmd() -> None:  # pyright: ignore[reportUnusedFunction]
        """Quick system health check."""
        from .cli import get_api_client
        
        api_client = get_api_client()
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.quick_health_check()
    
    @main_group.command(name='shortcuts')
    def shortcuts_cmd() -> None:  # pyright: ignore[reportUnusedFunction]
        """List available shortcuts."""
        api_client = None  # Not needed for listing shortcuts
        config = Config()
        shortcuts = CommandShortcuts(api_client, config)
        shortcuts.list_shortcuts()