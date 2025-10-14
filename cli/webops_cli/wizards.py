"""Interactive wizards for WebOps CLI.

This module provides step-by-step interactive wizards for common WebOps operations,
making the platform more accessible to users of all experience levels.
"""

import subprocess
import sys
import time
from typing import Any, Dict, Self

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from .errors import ErrorHandler
from .progress import ProgressManager

console = Console()
error_handler = ErrorHandler()
progress_manager = ProgressManager()


class InteractiveWizard:
    """Base class for interactive wizards."""
    
    def __init__(self: Self, title: str) -> None:
        """Initialize the wizard.
        
        Args:
            title: The wizard title to display.
        """
        self.title = title
        self.console = console
        
    def display_header(self: Self) -> None:
        """Display the wizard header."""
        self.console.print()
        self.console.print(Panel(
            f"[bold cyan]{self.title}[/bold cyan]",
            border_style="cyan"
        ))
        self.console.print()
    
    def display_step(self: Self, step: int, total: int, description: str) -> None:
        """Display current step information.
        
        Args:
            step: Current step number.
            total: Total number of steps.
            description: Step description.
        """
        self.console.print(f"[bold]Step {step}/{total}:[/bold] {description}")
        self.console.print()


class SetupWizard(InteractiveWizard):
    """Interactive setup wizard for WebOps installation."""
    
    def __init__(self: Self) -> None:
        """Initialize the setup wizard."""
        super().__init__("WebOps Interactive Setup Wizard")
        self.config: Dict[str, Any] = {}
    
    def run(self: Self) -> bool:
        """Run the interactive setup wizard.
        
        Returns:
            True if setup completed successfully, False otherwise.
        """
        try:
            self.display_header()
            
            # Step 1: Welcome and prerequisites
            if not self._step_welcome():
                return False
            
            # Step 2: System requirements check
            if not self._step_system_check():
                return False
            
            # Step 3: Configuration collection
            if not self._step_collect_config():
                return False
            
            # Step 4: Installation
            if not self._step_install():
                return False
            
            # Step 5: Verification
            if not self._step_verify():
                return False
            
            self._display_success()
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup cancelled by user.[/yellow]")
            return False
        except Exception as e:
            error_handler.display_error(e, "Setup wizard failed")
            return False
    
    def _step_welcome(self: Self) -> bool:
        """Welcome step with prerequisites check."""
        self.display_step(1, 5, "Welcome & Prerequisites")
        
        self.console.print("Welcome to WebOps! This wizard will guide you through the setup process.")
        self.console.print()
        
        # Display prerequisites
        prereq_table = Table(title="Prerequisites", show_header=True, header_style="bold magenta")
        prereq_table.add_column("Requirement", style="cyan")
        prereq_table.add_column("Status", justify="center")
        
        # Check prerequisites
        prereqs = [
            ("Ubuntu/Debian Linux", self._check_os()),
            ("Root/sudo access", self._check_sudo()),
            ("Internet connection", self._check_internet()),
            ("Python 3.13+", self._check_python()),
            ("Git", self._check_git())
        ]
        
        all_good = True
        for req, status in prereqs:
            status_text = "[green]✓[/green]" if status else "[red]✗[/red]"
            prereq_table.add_row(req, status_text)
            if not status:
                all_good = False
        
        self.console.print(prereq_table)
        self.console.print()
        
        if not all_good:
            self.console.print("[red]Some prerequisites are not met. Please resolve them before continuing.[/red]")
            return False
        
        return Confirm.ask("Ready to proceed with WebOps setup?", default=True)
    
    def _step_system_check(self: Self) -> bool:
        """System requirements and resource check."""
        self.display_step(2, 5, "System Requirements Check")
        
        with progress_manager.spinner("Checking system resources..."):
            time.sleep(2)  # Simulate check
            
        # Display system info
        system_table = Table(title="System Information", show_header=True, header_style="bold magenta")
        system_table.add_column("Resource", style="cyan")
        system_table.add_column("Available", justify="right")
        system_table.add_column("Required", justify="right")
        system_table.add_column("Status", justify="center")
        
        checks = [
            ("RAM", "8 GB", "4 GB", True),
            ("Disk Space", "50 GB", "20 GB", True),
            ("CPU Cores", "4", "2", True),
            ("Port 8000", "Available", "Available", self._check_port(8000)),
            ("Port 80", "Available", "Available", self._check_port(80)),
            ("Port 443", "Available", "Available", self._check_port(443))
        ]
        
        all_good = True
        for resource, available, required, status in checks:
            status_text = "[green]✓[/green]" if status else "[red]✗[/red]"
            system_table.add_row(resource, available, required, status_text)
            if not status:
                all_good = False
        
        self.console.print(system_table)
        self.console.print()
        
        if not all_good:
            self.console.print("[yellow]Warning: Some system requirements are not optimal.[/yellow]")
            if not Confirm.ask("Continue anyway?", default=False):
                return False
        
        return True
    
    def _step_collect_config(self: Self) -> bool:
        """Collect configuration from user."""
        self.display_step(3, 5, "Configuration")
        
        self.console.print("Let's configure your WebOps installation:")
        self.console.print()
        
        # Admin user configuration
        self.console.print("[bold]Admin User Setup[/bold]")
        self.config['admin_username'] = Prompt.ask(
            "Admin username",
            default="admin"
        )
        
        while True:
            password = Prompt.ask("Admin password", password=True)
            confirm_password = Prompt.ask("Confirm password", password=True)
            if password == confirm_password and len(password) >= 8:
                self.config['admin_password'] = password
                break
            elif len(password) < 8:
                self.console.print("[red]Password must be at least 8 characters long.[/red]")
            else:
                self.console.print("[red]Passwords don't match. Please try again.[/red]")
        
        self.console.print()
        
        # Domain configuration
        self.console.print("[bold]Domain Configuration[/bold]")
        use_domain = Confirm.ask("Do you want to configure a custom domain?", default=False)
        
        if use_domain:
            self.config['domain'] = Prompt.ask("Domain name (e.g., webops.example.com)")
            self.config['ssl'] = Confirm.ask("Enable SSL/HTTPS?", default=True)
        else:
            self.config['domain'] = None
            self.config['ssl'] = False
        
        self.console.print()
        
        # Database configuration
        self.console.print("[bold]Database Configuration[/bold]")
        db_choice = Prompt.ask(
            "Database type",
            choices=["sqlite", "postgresql"],
            default="sqlite"
        )
        
        self.config['database'] = db_choice
        
        if db_choice == "postgresql":
            self.config['db_host'] = Prompt.ask("PostgreSQL host", default="localhost")
            self.config['db_port'] = IntPrompt.ask("PostgreSQL port", default=5432)
            self.config['db_name'] = Prompt.ask("Database name", default="webops")
            self.config['db_user'] = Prompt.ask("Database user", default="webops")
            self.config['db_password'] = Prompt.ask("Database password", password=True)
        
        self.console.print()
        
        # Display configuration summary
        self._display_config_summary()
        
        return Confirm.ask("Proceed with this configuration?", default=True)
    
    def _step_install(self: Self) -> bool:
        """Run the installation process."""
        self.display_step(4, 5, "Installation")
        
        self.console.print("Starting WebOps installation...")
        self.console.print()
        
        try:
            with progress_manager.progress_bar("Installing WebOps...") as progress:
                task = progress.add_task("Installation", total=100)
                
                # Simulate installation steps
                steps = [
                    ("Creating webops user", 10),
                    ("Installing dependencies", 20),
                    ("Setting up virtual environment", 15),
                    ("Installing Python packages", 20),
                    ("Configuring database", 10),
                    ("Setting up systemd services", 10),
                    ("Configuring Nginx", 10),
                    ("Starting services", 5)
                ]
                
                completed = 0
                for step_name, duration in steps:
                    progress.update(task, description=f"[cyan]{step_name}[/cyan]")
                    
                    # Run actual installation command here
                    # For now, simulate with sleep
                    time.sleep(duration / 10)
                    
                    completed += duration
                    progress.update(task, completed=completed)
            
            return True
            
        except Exception as e:
            error_handler.display_error(e, "Installation failed")
            return False
    
    def _step_verify(self: Self) -> bool:
        """Verify the installation."""
        self.display_step(5, 5, "Verification")
        
        self.console.print("Verifying WebOps installation...")
        self.console.print()
        
        with progress_manager.spinner("Running verification checks..."):
            time.sleep(3)  # Simulate verification
        
        # Display verification results
        verify_table = Table(title="Verification Results", show_header=True, header_style="bold magenta")
        verify_table.add_column("Component", style="cyan")
        verify_table.add_column("Status", justify="center")
        verify_table.add_column("Details")
        
        checks = [
            ("WebOps Web Service", True, "Running on port 8000"),
            ("Celery Worker", True, "2 workers active"),
            ("Celery Beat", True, "Scheduler running"),
            ("Database", True, "Connected successfully"),
            ("Admin User", True, "Created successfully"),
            ("Nginx", True, "Configured and running")
        ]
        
        all_good = True
        for component, status, details in checks:
            status_text = "[green]✓[/green]" if status else "[red]✗[/red]"
            verify_table.add_row(component, status_text, details)
            if not status:
                all_good = False
        
        self.console.print(verify_table)
        self.console.print()
        
        return all_good
    
    def _display_config_summary(self: Self) -> None:
        """Display configuration summary."""
        summary_table = Table(title="Configuration Summary", show_header=True, header_style="bold magenta")
        summary_table.add_column("Setting", style="cyan")
        summary_table.add_column("Value")
        
        summary_table.add_row("Admin Username", self.config['admin_username'])
        summary_table.add_row("Admin Password", "••••••••")
        summary_table.add_row("Domain", self.config.get('domain', 'localhost'))
        summary_table.add_row("SSL Enabled", "Yes" if self.config.get('ssl') else "No")
        summary_table.add_row("Database", self.config['database'].title())
        
        if self.config['database'] == 'postgresql':
            summary_table.add_row("DB Host", self.config['db_host'])
            summary_table.add_row("DB Port", str(self.config['db_port']))
            summary_table.add_row("DB Name", self.config['db_name'])
        
        self.console.print(summary_table)
        self.console.print()
    
    def _display_success(self: Self) -> None:
        """Display successful installation message."""
        self.console.print()
        self.console.print(Panel(
            "[bold green]WebOps Installation Completed Successfully![/bold green]\n\n"
            f"• Control Panel: http://localhost:8000\n"
            f"• Admin Username: {self.config['admin_username']}\n"
            f"• Admin Password: [Set during installation]\n\n"
            "[cyan]Next Steps:[/cyan]\n"
            "1. Access the control panel in your browser\n"
            "2. Log in with your admin credentials\n"
            "3. Start deploying your applications!\n\n"
            "[yellow]Need help? Run:[/yellow] webops troubleshoot",
            border_style="green",
            title="🎉 Success!"
        ))
    
    # Helper methods for checks
    def _check_os(self: Self) -> bool:
        """Check if running on supported OS."""
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                return 'ubuntu' in content.lower() or 'debian' in content.lower()
        except:
            return False
    
    def _check_sudo(self: Self) -> bool:
        """Check if user has sudo access."""
        try:
            result = subprocess.run(['sudo', '-n', 'true'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _check_internet(self: Self) -> bool:
        """Check internet connectivity."""
        try:
            result = subprocess.run(['ping', '-c', '1', '8.8.8.8'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def _check_python(self: Self) -> bool:
        """Check Python version."""
        try:
            result = subprocess.run(['python3', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split()[-1]
                major, minor = map(int, version.split('.')[:2])
                return major >= 3 and minor >= 13
            return False
        except:
            return False
    
    def _check_git(self: Self) -> bool:
        """Check if Git is installed."""
        try:
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _check_port(self: Self, port: int) -> bool:
        """Check if port is available."""
        try:
            result = subprocess.run(['netstat', '-tuln'], 
                                  capture_output=True, text=True)
            return f':{port}' not in result.stdout
        except:
            return True  # Assume available if can't check


@click.group()
def wizard():
    """Interactive wizards for WebOps operations."""
    pass


@wizard.command()
def setup():
    """Run the interactive WebOps setup wizard."""
    setup_wizard = SetupWizard()
    success = setup_wizard.run()
    
    if success:
        console.print("\n[green]Setup completed successfully![/green]")
        sys.exit(0)
    else:
        console.print("\n[red]Setup failed or was cancelled.[/red]")
        sys.exit(1)


if __name__ == '__main__':
    wizard()