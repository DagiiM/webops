"""Interactive commands for WebOps CLI.

This module provides interactive command implementations with enhanced UX,
including real-time status updates, interactive wizards, and improved feedback.
"""

from typing import Dict, Any, List, Optional, Self
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm

from ..api import WebOpsAPIClient
from ..config import Config
from ..errors import WebOpsError, ConnectionError as WebOpsConnectionError
from .display import display_deployment_table
from .terminal import TerminalUI

console = Console()


class InteractiveCommands:
    """Interactive command implementations with enhanced UX."""
    
    def __init__(self: Self, api_client: WebOpsAPIClient, config: Config) -> None:
        """Initialize interactive commands.
        
        Args:
            api_client: WebOps API client instance.
            config: Configuration instance.
        """
        self.api_client = api_client
        self.config = config
        self.ui = TerminalUI()
    
    def interactive_status(self: Self) -> None:
        """Display interactive system status with real-time updates."""
        console.print("[cyan]Starting interactive status monitor...[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        
        try:
            with Live(console=console, refresh_per_second=2) as live:
                while True:
                    try:
                        # Gather system information
                        system_info = self._get_system_info()
                        deployments = self._get_deployments_info()
                        services = self._get_services_info()
                        
                        # Create dashboard
                        dashboard = self.ui.create_status_dashboard(
                            system_info, deployments, services
                        )
                        
                        live.update(dashboard)
                        time.sleep(1)
                        
                    except WebOpsConnectionError:
                        error_panel = Panel(
                            "[red]Connection to WebOps API failed[/red]\n"
                            "[dim]Retrying in 5 seconds...[/dim]",
                            title="Connection Error",
                            border_style="red"
                        )
                        live.update(error_panel)
                        time.sleep(5)
                        
        except KeyboardInterrupt:
            console.print("\n[yellow]Status monitor stopped[/yellow]")
    
    def interactive_deployment_manager(self: Self) -> None:
        """Interactive deployment management interface."""
        while True:
            try:
                deployments_response = self.api_client.list_deployments()
                deployments = deployments_response.get('deployments', [])
                
                # Display current deployments
                display_deployment_table(deployments)
                
                # Show menu
                menu_options = [
                    ("1", "Create new deployment"),
                    ("2", "Start deployment"),
                    ("3", "Stop deployment"),
                    ("4", "Restart deployment"),
                    ("5", "View deployment logs"),
                    ("6", "Delete deployment"),
                    ("r", "Refresh list"),
                    ("q", "Quit")
                ]
                
                menu_panel = self.ui.create_interactive_menu(
                    "Deployment Manager",
                    menu_options,
                    "Manage your WebOps deployments"
                )
                
                console.print(menu_panel)
                
                choice = Prompt.ask(
                    "Select an option",
                    choices=["1", "2", "3", "4", "5", "6", "r", "q"],
                    default="q"
                )
                
                if choice == "q":
                    break
                elif choice == "r":
                    continue
                elif choice == "1":
                    self._interactive_create_deployment()
                elif choice == "2":
                    self._interactive_start_deployment(deployments)
                elif choice == "3":
                    self._interactive_stop_deployment(deployments)
                elif choice == "4":
                    self._interactive_restart_deployment(deployments)
                elif choice == "5":
                    self._interactive_view_logs(deployments)
                elif choice == "6":
                    self._interactive_delete_deployment(deployments)
                    
            except WebOpsError as e:
                console.print(f"[red]Error: {e}[/red]")
                if not Confirm.ask("Continue?", default=True):
                    break
    
    def interactive_logs_viewer(self: Self, deployment_name: Optional[str] = None) -> None:
        """Interactive logs viewer with real-time updates.
        
        Args:
            deployment_name: Optional deployment name to view logs for.
        """
        if not deployment_name:
            deployments_response = self.api_client.list_deployments()
            deployments = deployments_response.get('deployments', [])
            if not deployments:
                console.print("[yellow]No deployments found[/yellow]")
                return
            
            deployment_name = self._select_deployment(deployments, "Select deployment to view logs")
            if not deployment_name:
                return
        
        console.print(f"[cyan]Viewing logs for: {deployment_name}[/cyan]")
        console.print("[dim]Press Ctrl+C to exit[/dim]\n")
        
        try:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    try:
                        logs_response = self.api_client.get_deployment_logs(deployment_name)
                        logs = logs_response.get('logs', '')
                        log_lines = logs.split('\n') if logs else []
                        
                        log_panel = self.ui.create_log_viewer(
                            log_lines,
                            f"Logs: {deployment_name}",
                            max_lines=30
                        )
                        
                        live.update(log_panel)
                        time.sleep(2)
                        
                    except WebOpsError as e:
                        error_panel = Panel(
                            f"[red]Error fetching logs: {e}[/red]",
                            title="Error",
                            border_style="red"
                        )
                        live.update(error_panel)
                        time.sleep(5)
                        
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Stopped viewing logs for {deployment_name}[/yellow]")
    
    def _interactive_create_deployment(self: Self) -> None:
        """Interactive deployment creation wizard."""
        console.print("\n[cyan]Create New Deployment[/cyan]")
        
        # Gather deployment information
        name = Prompt.ask("Deployment name")
        if not name:
            console.print("[red]Deployment name is required[/red]")
            return
        
        domain = Prompt.ask("Domain (optional)", default="")
        repo_url = Prompt.ask("Repository URL")
        if not repo_url:
            console.print("[red]Repository URL is required[/red]")
            return
        
        branch = Prompt.ask("Branch", default="main")
        
        # Confirm creation
        console.print("\n[yellow]Deployment Configuration:[/yellow]")
        console.print(f"Name: {name}")
        console.print(f"Domain: {domain or 'Not set'}")
        console.print(f"Repository: {repo_url}")
        console.print(f"Branch: {branch}")
        
        if not Confirm.ask("\nCreate this deployment?", default=True):
            console.print("[yellow]Deployment creation cancelled[/yellow]")
            return
        
        # Create deployment with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Creating deployment...", total=100)
            
            try:
                deployment_data = {
                    'name': name,
                    'domain': domain,
                    'repo_url': repo_url,
                    'branch': branch
                }
                
                progress.update(task, advance=30, description="Validating configuration...")
                time.sleep(1)
                
                progress.update(task, advance=40, description="Creating deployment...")
                _ = self.api_client.create_deployment(
                    name=deployment_data['name'],
                    repo_url=deployment_data['repo_url'],
                    branch=deployment_data['branch'],
                    domain=deployment_data['domain']
                )
                
                progress.update(task, advance=30, description="Deployment created successfully!")
                progress.update(task, completed=100)
                
                console.print(f"\n[green]✓ Deployment '{name}' created successfully![/green]")
                
                if Confirm.ask("Start the deployment now?", default=True):
                    self._start_deployment_with_progress(name)
                    
            except WebOpsError as e:
                progress.stop()
                console.print(f"\n[red]✗ Failed to create deployment: {e}[/red]")
    
    def _interactive_start_deployment(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Interactive deployment start."""
        deployment_name = self._select_deployment(deployments, "Select deployment to start")
        if deployment_name:
            self._start_deployment_with_progress(deployment_name)
    
    def _interactive_stop_deployment(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Interactive deployment stop."""
        try:
            running_deployments = [d for d in deployments if d.get('status') == 'running']
            if not running_deployments:
                console.print("[yellow]No running deployments found[/yellow]")
                return
            
            deployment_name = self._select_deployment(running_deployments, "Select deployment to stop")
            if deployment_name:
                if Confirm.ask(f"Are you sure you want to stop '{deployment_name}'?"):
                    self._stop_deployment_with_progress(deployment_name)
        except Exception as e:
            console.print(f"[red]Error stopping deployment: {e}[/red]")
    
    def _interactive_restart_deployment(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Interactive deployment restart."""
        try:
            deployment_name = self._select_deployment(deployments, "Select deployment to restart")
            if deployment_name:
                if Confirm.ask(f"Are you sure you want to restart '{deployment_name}'?"):
                    self._restart_deployment_with_progress(deployment_name)
        except Exception as e:
            console.print(f"[red]Error restarting deployment: {e}[/red]")
    
    def _interactive_view_logs(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Interactive logs viewing."""
        try:
            deployment_name = self._select_deployment(deployments, "Select deployment to view logs")
            if deployment_name:
                self.interactive_logs_viewer(deployment_name)
        except Exception as e:
            console.print(f"[red]Error viewing logs: {e}[/red]")
    
    def _interactive_delete_deployment(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Interactive deployment deletion."""
        try:
            deployment_name = self._select_deployment(deployments, "Select deployment to delete")
            if deployment_name:
                if Confirm.ask(f"Are you sure you want to delete '{deployment_name}'? This cannot be undone."):
                    self._delete_deployment_with_progress(deployment_name)
        except Exception as e:
            console.print(f"[red]Error deleting deployment: {e}[/red]")
    def _start_deployment_with_progress(self: Self, deployment_name: str) -> None:
        """Start deployment with progress indication.
        
        Args:
            deployment_name: Name of the deployment to start.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Starting deployment '{deployment_name}'...", total=None)
            
            try:
                self.api_client.start_deployment(deployment_name)
                progress.update(task, description=f"✓ Deployment '{deployment_name}' started successfully!")
                time.sleep(1)
                console.print(f"[green]✓ Deployment '{deployment_name}' started successfully![/green]")
            except WebOpsError as e:
                progress.stop()
                console.print(f"[red]✗ Failed to start deployment: {e}[/red]")
    
    def _stop_deployment_with_progress(self: Self, deployment_name: str) -> None:
        """Stop deployment with progress indication.
        
        Args:
            deployment_name: Name of the deployment to stop.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Stopping deployment '{deployment_name}'...", total=None)
            
            try:
                self.api_client.stop_deployment(deployment_name)
                progress.update(task, description=f"✓ Deployment '{deployment_name}' stopped successfully!")
                time.sleep(1)
                console.print(f"[green]✓ Deployment '{deployment_name}' stopped successfully![/green]")
            except WebOpsError as e:
                progress.stop()
                console.print(f"[red]✗ Failed to stop deployment: {e}[/red]")
    
    def _restart_deployment_with_progress(self: Self, deployment_name: str) -> None:
        """Restart deployment with progress indication.
        
        Args:
            deployment_name: Name of the deployment to restart.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Restarting deployment '{deployment_name}'...", total=None)
            
            try:
                self.api_client.restart_deployment(deployment_name)
                progress.update(task, description=f"✓ Deployment '{deployment_name}' restarted successfully!")
                time.sleep(1)
                console.print(f"[green]✓ Deployment '{deployment_name}' restarted successfully![/green]")
            except WebOpsError as e:
                progress.stop()
                console.print(f"[red]✗ Failed to restart deployment: {e}[/red]")
    
    def _delete_deployment_with_progress(self: Self, deployment_name: str) -> None:
        """Delete deployment with progress indication.
        
        Args:
            deployment_name: Name of the deployment to delete.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Deleting deployment '{deployment_name}'...", total=None)
            
            try:
                self.api_client.delete_deployment(deployment_name)
                progress.update(task, description=f"✓ Deployment '{deployment_name}' deleted successfully!")
                time.sleep(1)
                console.print(f"[green]✓ Deployment '{deployment_name}' deleted successfully![/green]")
            except WebOpsError as e:
                progress.stop()
                console.print(f"[red]✗ Failed to delete deployment: {e}[/red]")
    
    def _get_system_info(self: Self) -> Dict[str, Any]:
        """Get system information for dashboard.
        
        Returns:
            Dictionary containing system information.
        """
        try:
            status = self.api_client.get_status()
            return {
                'cpu_usage': status.get('cpu_usage', 0),
                'memory_usage': status.get('memory_usage', 0),
                'disk_usage': status.get('disk_usage', 0),
                'uptime': status.get('uptime', 'N/A'),
                'load_avg': status.get('load_avg', 'N/A')
            }
        except WebOpsError:
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'uptime': 'N/A',
                'load_avg': 'N/A'
            }
    
    def _get_deployments_info(self: Self) -> List[Dict[str, Any]]:
        """Get deployments information for dashboard.
        
        Returns:
            List of deployment information dictionaries.
        """
        try:
            deployments_response = self.api_client.list_deployments()
            return deployments_response.get('deployments', [])
        except WebOpsError:
            return []
    
    def _get_services_info(self: Self) -> List[Dict[str, Any]]:
        """Get services information for dashboard.
        
        Returns:
            List of service information dictionaries.
        """
        # This would typically come from the API
        # For now, return mock data
        return [
            {'name': 'nginx', 'status': 'running', 'pid': '1234', 'memory': '45MB'},
            {'name': 'postgresql', 'status': 'running', 'pid': '5678', 'memory': '128MB'},
            {'name': 'redis', 'status': 'running', 'pid': '9012', 'memory': '32MB'}
        ]
    
    def _select_deployment(self: Self, deployments: List[Dict[str, Any]], prompt_text: str) -> Optional[str]:
        """Select a deployment from the list.
        
        Args:
            deployments: List of deployment dictionaries.
            prompt_text: Text to display when prompting for selection.
            
        Returns:
            Selected deployment name or None if cancelled.
        """
        if not deployments:
            console.print("[yellow]No deployments available[/yellow]")
            return None
        
        # Create choices list
        choices = []
        for i, deployment in enumerate(deployments, 1):
            name = deployment.get('name', f'deployment-{i}')
            status = deployment.get('status', 'unknown')
            choices.append(f"{i}. {name} ({status})")
        
        choices.append("c. Cancel")
        
        console.print("\nAvailable deployments:")
        for choice in choices:
            console.print(f"  {choice}")
        
        while True:
            selection = Prompt.ask(
                prompt_text,
                choices=[str(i) for i in range(1, len(deployments) + 1)] + ["c"],
                default="c"
            )
            
            if selection == "c":
                return None
            
            try:
                index = int(selection) - 1
                if 0 <= index < len(deployments):
                    return deployments[index].get('name')
            except ValueError:
                pass
            
            console.print("[red]Invalid selection. Please try again.[/red]")