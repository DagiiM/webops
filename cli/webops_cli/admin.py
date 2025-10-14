"""Admin commands for WebOps CLI.

This module provides administrative functionality previously available
in webops-admin.sh script, integrated into the main CLI interface.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Self

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .errors import ErrorHandler, handle_exception, require_root_privileges
from .progress import ProgressManager, show_progress

console = Console()
error_handler = ErrorHandler()
progress_manager = ProgressManager()


class AdminManager:
    """Manages administrative operations for WebOps."""
    
    def __init__(self: Self) -> None:
        """Initialize the admin manager."""
        self.webops_user: str = "webops"
        self.webops_dir: Path = Path("/opt/webops")
        self.scripts_dir: Path = Path("/home/douglas/webops/scripts")
    
    def check_root_privileges(self: Self) -> bool:
        """Check if running with root privileges.
        
        Returns:
            True if running as root, False otherwise.
        """
        try:
            return os.geteuid() == 0
        except Exception as e:
            error_handler.display_error(e, "Failed to check root privileges")
            return False
    
    def run_as_webops_user(self: Self, command: str) -> subprocess.CompletedProcess[str]:
        """Run a command as the webops user.
        
        Args:
            command: The command to execute.
            
        Returns:
            The completed process result.
            
        Raises:
            subprocess.CalledProcessError: If the command fails.
        """
        try:
            with show_progress(f"Running command as webops user") as status:
                result = subprocess.run(
                    ["sudo", "-u", "webops", "bash", "-c", command],
                    capture_output=True,
                    text=True,
                    check=True
                )
                status.update("[green]✓[/green] Command completed successfully")
                return result
        except subprocess.CalledProcessError as e:
            error_handler.handle_system_error(e, "webops user command")
            raise
        except Exception as e:
            error_handler.display_error(e, f"Failed to run command: {command}")
            raise
    
    def get_system_status(self: Self) -> Dict[str, Any]:
        """Get comprehensive system status information.
        
        Returns:
            Dictionary containing system status data.
        """
        status_data: Dict[str, Any] = {}
        
        try:
            # User information
            result = subprocess.run(
                ["id", self.webops_user],
                capture_output=True,
                text=True,
                check=True
            )
            status_data["user_info"] = result.stdout.strip()
            
            # Process count
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=True
            )
            webops_processes = [
                line for line in result.stdout.split('\n')
                if line.startswith(self.webops_user) and 'grep' not in line
            ]
            status_data["process_count"] = len(webops_processes)
            status_data["processes"] = webops_processes[:10]  # Limit to first 10
            
            # Disk usage
            if self.webops_dir.exists():
                result = subprocess.run(
                    ["du", "-sh"] + [str(p) for p in self.webops_dir.iterdir()],
                    capture_output=True,
                    text=True,
                    check=False  # Don't fail if some directories are inaccessible
                )
                status_data["disk_usage"] = result.stdout.strip().split('\n')
            
            # SystemD services
            result = subprocess.run(
                ["systemctl", "status", "webops-*", "--no-pager", "-l"],
                capture_output=True,
                text=True,
                check=False  # Services might not exist
            )
            status_data["services"] = result.stdout.split('\n')[:20]
            
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Error getting system status:[/red] {e}")
            
        return status_data
    
    def get_deployment_list(self: Self) -> List[Dict[str, str]]:
        """Get list of deployed applications.
        
        Returns:
            List of deployment information dictionaries.
        """
        deployments: List[Dict[str, str]] = []
        deployments_dir = self.webops_dir / "deployments"
        
        if not deployments_dir.exists():
            return deployments
        
        for app_dir in deployments_dir.iterdir():
            if app_dir.is_dir():
                app_name = app_dir.name
                
                # Get directory size
                try:
                    result = subprocess.run(
                        ["du", "-sh", str(app_dir)],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    size = result.stdout.split()[0]
                except subprocess.CalledProcessError:
                    size = "unknown"
                
                # Check service status
                service_name = f"app-{app_name}"
                try:
                    result = subprocess.run(
                        ["systemctl", "is-active", service_name],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if result.returncode == 0:
                        status = "running"
                    else:
                        # Check if service exists
                        result = subprocess.run(
                            ["systemctl", "list-unit-files", service_name + ".service"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if service_name in result.stdout:
                            status = "stopped"
                        else:
                            status = "no service"
                except subprocess.CalledProcessError:
                    status = "unknown"
                
                deployments.append({
                    "name": app_name,
                    "path": str(app_dir),
                    "size": size,
                    "status": status
                })
        
        return deployments
    
    def fix_permissions(self: Self) -> None:
        """Fix file ownership and permissions for WebOps directory.
        
        Raises:
            subprocess.CalledProcessError: If permission fixing fails.
        """
        if not self.check_root_privileges():
            console.print("[red]Error:[/red] Permission fixing requires root privileges")
            sys.exit(1)
        
        console.print("[blue]Fixing file ownership and permissions...[/blue]")
        
        # Fix ownership
        console.print(f"Setting ownership to {self.webops_user}:{self.webops_user}...")
        subprocess.run(
            ["chown", "-R", f"{self.webops_user}:{self.webops_user}", str(self.webops_dir)],
            check=True
        )
        
        # Fix directory permissions
        console.print("Setting directory permissions...")
        directories_to_fix = [
            (self.webops_dir, "750"),
            (self.webops_dir / "control-panel", "750"),
            (self.webops_dir / "deployments", "750"),
            (self.webops_dir / "backups", "700"),
            (self.webops_dir / ".secrets", "700"),
        ]
        
        for dir_path, perms in directories_to_fix:
            if dir_path.exists():
                subprocess.run(["chmod", perms, str(dir_path)], check=True)
        
        # Fix .env file permissions
        console.print("Setting .env file permissions to 600...")
        subprocess.run([
            "find", str(self.webops_dir), "-name", ".env", "-type", "f",
            "-exec", "chmod", "600", "{}", ";"
        ], check=True)
        
        # Fix tmp directory
        tmp_dir = self.webops_dir / "control-panel" / "tmp"
        if tmp_dir.exists():
            subprocess.run(["chmod", "1777", str(tmp_dir)], check=True)
        
        console.print("[green]Permissions fixed ✓[/green]")


@click.group()
def admin() -> None:
    """Administrative commands for WebOps."""
    pass


@admin.command()
def status() -> None:
    """Show system status and information."""
    try:
        require_root_privileges("status check")
        
        admin_manager = AdminManager()
        
        with show_progress("Gathering system status") as status_indicator:
            system_status = admin_manager.get_system_status()
            status_indicator.update("[green]✓[/green] System status collected")
        
        # Display system information
        table = Table(title="WebOps System Status")
        table.add_column("Component", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Details")
        
        for component, details in system_status.items():
            if isinstance(details, dict):
                status_text = details.get('status', 'Unknown')
                info = details.get('info', '')
            else:
                status_text = str(details)
                info = ''
            
            # Color code status
            if 'active' in status_text.lower() or 'running' in status_text.lower():
                status_display = f"[green]●[/green] {status_text}"
            elif 'inactive' in status_text.lower() or 'stopped' in status_text.lower():
                status_display = f"[red]●[/red] {status_text}"
            else:
                status_display = f"[yellow]?[/yellow] {status_text}"
            
            table.add_row(component, status_display, info)
        
        console.print(table)
        
    except Exception as e:
        handle_exception(e, "Failed to get system status")


@admin.command()
def shell() -> None:
    """Start interactive shell as webops user."""
    admin_manager = AdminManager()
    
    if not admin_manager.check_root_privileges():
        console.print("[red]Error:[/red] Shell access requires root privileges")
        console.print("Run with: [cyan]sudo webops admin shell[/cyan]")
        sys.exit(1)
    
    console.print(f"[blue]Starting shell as {admin_manager.webops_user} user...[/blue]")
    
    # Use os.system for interactive shell
    os.system(f"sudo -u {admin_manager.webops_user} -i")


@admin.command()
@click.argument('command', required=True)
def run(command: str) -> None:
    """Run a command as the webops user."""
    try:
        require_root_privileges("run command")
        
        admin_manager = AdminManager()
        
        console.print(f"[cyan]Running:[/cyan] {command}")
        
        result = admin_manager.run_as_webops_user(command)
        
        if result.stdout:
            console.print("[bold]Output:[/bold]")
            console.print(result.stdout)
        
        if result.stderr:
            console.print("[bold red]Errors:[/bold red]")
            console.print(result.stderr)
        
        console.print(f"[green]✓[/green] Command completed with exit code: {result.returncode}")
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗[/red] Command failed with exit code: {e.returncode}")
        if e.stdout:
            console.print("[bold]Output:[/bold]")
            console.print(e.stdout)
        if e.stderr:
            console.print("[bold red]Errors:[/bold red]")
            console.print(e.stderr)
    except Exception as e:
        handle_exception(e, f"Failed to run command: {command}")


@admin.command(name="fix-permissions")
def fix_permissions() -> None:
    """Fix file ownership and permissions in WebOps directory."""
    admin_manager = AdminManager()
    admin_manager.fix_permissions()


@admin.command()
def deployments() -> None:
    """List all deployed applications and their status."""
    admin_manager = AdminManager()
    
    console.print(Panel.fit(
        "[bold blue]Deployed Applications[/bold blue]",
        border_style="blue"
    ))
    
    deployment_list = admin_manager.get_deployment_list()
    
    if not deployment_list:
        console.print("\n[yellow]No deployments found[/yellow]")
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="green")
    table.add_column("Status", style="white")
    table.add_column("Path", style="dim")
    
    for deployment in deployment_list:
        # Color code status
        status = deployment["status"]
        if status == "running":
            status_text = Text(status, style="green")
        elif status == "stopped":
            status_text = Text(status, style="red")
        elif status == "no service":
            status_text = Text(status, style="yellow")
        else:
            status_text = Text(status, style="dim")
        
        table.add_row(
            deployment["name"],
            deployment["size"],
            status_text,
            deployment["path"]
        )
    
    console.print(table)
    console.print(f"\n[blue]Total: {len(deployment_list)} deployment(s)[/blue]")


@admin.command()
def validate() -> None:
    """Run comprehensive validation of WebOps user setup."""
    admin_manager = AdminManager()
    validate_script = admin_manager.scripts_dir / "validate-user-setup.sh"
    
    if not validate_script.exists():
        console.print(f"[red]Error:[/red] Validation script not found: {validate_script}")
        sys.exit(1)
    
    console.print("[blue]Running validation script...[/blue]")
    
    try:
        result = subprocess.run(
            ["bash", str(validate_script)],
            check=True
        )
        console.print("[green]Validation completed successfully ✓[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Validation failed with exit code {e.returncode}[/red]")
        sys.exit(e.returncode)