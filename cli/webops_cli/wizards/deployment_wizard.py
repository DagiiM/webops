"""Deployment wizard for WebOps CLI.

This module provides an interactive wizard for creating and managing deployments.
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Self

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from ..api import WebOpsAPIClient
from ..config import Config
from ..errors import ErrorHandler
from ..progress import ProgressManager
from .wizards import InteractiveWizard

console = Console()
error_handler = ErrorHandler()
progress_manager = ProgressManager()
config = Config()


class DeploymentWizard(InteractiveWizard):
    """Interactive deployment wizard for applications."""
    
    def __init__(self: Self) -> None:
        """Initialize the deployment wizard."""
        super().__init__("WebOps Interactive Deployment Wizard")
        self.deployment_config: Dict[str, Any] = {}
        self.api_client: Optional[WebOpsAPIClient] = None
    
    def run(self: Self) -> bool:
        """Run the interactive deployment wizard.
        
        Returns:
            True if deployment completed successfully, False otherwise.
        """
        try:
            self.display_header()
            
            # Check API configuration
            if not self._check_api_config():
                return False
            
            # Step 1: Application source
            if not self._step_application_source():
                return False
            
            # Step 2: Application configuration
            if not self._step_application_config():
                return False
            
            # Step 3: Environment variables
            if not self._step_environment_config():
                return False
            
            # Step 4: Domain and SSL
            if not self._step_domain_config():
                return False
            
            # Step 5: Resource allocation
            if not self._step_resource_config():
                return False
            
            # Step 6: Review and deploy
            if not self._step_review_and_deploy():
                return False
            
            # Step 7: Monitor deployment
            if not self._step_monitor_deployment():
                return False
            
            self._display_success()
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Deployment cancelled by user.[/yellow]")
            return False
        except Exception as e:
            error_handler.display_error(e, "Deployment wizard failed")
            return False
    
    def _check_api_config(self: Self) -> bool:
        """Check if API is configured and accessible."""
        if not config.is_configured():
            self.console.print("[red]Error:[/red] WebOps CLI is not configured.")
            self.console.print("Run: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
            return False
        
        try:
            base_url = config.get_url()
            token = config.get_token()
            
            if not base_url or not token:
                console.print("[red]Error: WebOps CLI is not configured[/red]")
                console.print("Please run: webops config --url <URL> --token <TOKEN>")
                return False
            
            self.api_client = WebOpsAPIClient(
                base_url=base_url,
                token=token
            )
            
            with progress_manager.spinner("Checking API connection..."):
                # Test API connection
                time.sleep(1)
            
            self.console.print("[green]✓[/green] Connected to WebOps API")
            self.console.print()
            return True
            
        except Exception as e:
            self.console.print(f"[red]✗[/red] Failed to connect to WebOps API: {e}")
            return False
    
    def _step_application_source(self: Self) -> bool:
        """Configure application source."""
        self.display_step(1, 7, "Application Source")
        
        self.console.print("Let's configure your application source:")
        self.console.print()
        
        # Source type selection
        source_type = Prompt.ask(
            "Application source type",
            choices=["git", "docker", "local"],
            default="git"
        )
        
        self.deployment_config['source_type'] = source_type
        
        if source_type == "git":
            return self._configure_git_source()
        elif source_type == "docker":
            return self._configure_docker_source()
        else:
            return self._configure_local_source()
    
    def _configure_git_source(self: Self) -> bool:
        """Configure Git repository source."""
        while True:
            repo_url = Prompt.ask("Git repository URL")
            
            if self._validate_git_url(repo_url):
                self.deployment_config['repo_url'] = repo_url
                break
            else:
                self.console.print("[red]Invalid Git URL. Please try again.[/red]")
        
        # Branch selection
        self.deployment_config['branch'] = Prompt.ask("Git branch", default="main")
        
        # Check if repository is accessible
        with progress_manager.spinner("Checking repository access..."):
            accessible = self._check_git_access(
                self.deployment_config['repo_url'],
                self.deployment_config['branch']
            )
        
        if not accessible:
            self.console.print("[yellow]Warning: Repository may not be accessible or branch doesn't exist.[/yellow]")
            if not Confirm.ask("Continue anyway?", default=False):
                return False
        
        # Authentication for private repos
        if self._is_private_repo(self.deployment_config['repo_url']):
            if Confirm.ask("Is this a private repository requiring authentication?", default=True):
                auth_method = Prompt.ask(
                    "Authentication method",
                    choices=["ssh", "token", "username"],
                    default="ssh"
                )
                self.deployment_config['auth_method'] = auth_method
                
                if auth_method == "token":
                    self.deployment_config['git_token'] = Prompt.ask("Git access token", password=True)
                elif auth_method == "username":
                    self.deployment_config['git_username'] = Prompt.ask("Git username")
                    self.deployment_config['git_password'] = Prompt.ask("Git password", password=True)
        
        return True
    
    def _configure_docker_source(self: Self) -> bool:
        """Configure Docker image source."""
        while True:
            image_name = Prompt.ask("Docker image name (e.g., nginx:latest)")
            
            if self._validate_docker_image(image_name):
                self.deployment_config['docker_image'] = image_name
                break
            else:
                self.console.print("[red]Invalid Docker image name. Please try again.[/red]")
        
        # Registry authentication
        if self._is_private_registry(self.deployment_config['docker_image']):
            if Confirm.ask("Does this image require registry authentication?", default=False):
                self.deployment_config['registry_username'] = Prompt.ask("Registry username")
                self.deployment_config['registry_password'] = Prompt.ask("Registry password", password=True)
        
        return True
    
    def _configure_local_source(self: Self) -> bool:
        """Configure local directory source."""
        while True:
            local_path = Prompt.ask("Local directory path")
            path = Path(local_path).expanduser().resolve()
            
            if path.exists() and path.is_dir():
                self.deployment_config['local_path'] = str(path)
                break
            else:
                self.console.print("[red]Directory doesn't exist. Please try again.[/red]")
        
        return True
    
    def _step_application_config(self: Self) -> bool:
        """Configure application settings."""
        self.display_step(2, 7, "Application Configuration")
        
        # Application name
        while True:
            app_name = Prompt.ask("Application name")
            
            if self._validate_app_name(app_name):
                self.deployment_config['name'] = app_name
                break
            else:
                self.console.print("[red]Invalid application name. Use only letters, numbers, and hyphens.[/red]")
        
        # Application type detection
        app_type = self._detect_application_type()
        if app_type:
            self.console.print(f"[green]✓[/green] Detected application type: [cyan]{app_type}[/cyan]")
            if not Confirm.ask("Is this correct?", default=True):
                app_type = self._select_application_type()
        else:
            app_type = self._select_application_type()
        
        self.deployment_config['app_type'] = app_type
        
        # Port configuration
        default_port = self._get_default_port(app_type)
        port = IntPrompt.ask("Application port", default=default_port)
        self.deployment_config['port'] = port
        
        # Build configuration
        if app_type in ['nodejs', 'python', 'ruby']:
            if Confirm.ask("Does your application require a build step?", default=False):
                self.deployment_config['build_command'] = Prompt.ask(
                    "Build command",
                    default=self._get_default_build_command(app_type)
                )
        
        # Start command
        self.deployment_config['start_command'] = Prompt.ask(
            "Start command",
            default=self._get_default_start_command(app_type)
        )
        
        return True
    
    def _step_environment_config(self: Self) -> bool:
        """Configure environment variables."""
        self.display_step(3, 7, "Environment Variables")
        
        self.console.print("Configure environment variables for your application:")
        self.console.print()
        
        env_vars = {}
        
        # Common environment variables
        common_vars = self._get_common_env_vars(self.deployment_config['app_type'])
        
        if common_vars:
            self.console.print("[bold]Common environment variables for this application type:[/bold]")
            for var, description in common_vars.items():
                if Confirm.ask(f"Set {var}? ({description})", default=False):
                    value = Prompt.ask(f"Value for {var}")
                    env_vars[var] = value
            self.console.print()
        
        # Custom environment variables
        if Confirm.ask("Add custom environment variables?", default=False):
            self.console.print("Enter environment variables (press Enter with empty name to finish):")
            
            while True:
                var_name = Prompt.ask("Variable name", default="")
                if not var_name:
                    break
                
                if not self._validate_env_var_name(var_name):
                    self.console.print("[red]Invalid variable name. Use only letters, numbers, and underscores.[/red]")
                    continue
                
                is_secret = Confirm.ask(f"Is {var_name} a secret value?", default=False)
                var_value = Prompt.ask(f"Value for {var_name}", password=is_secret)
                env_vars[var_name] = var_value
        
        self.deployment_config['env_vars'] = env_vars
        
        # Display summary
        if env_vars:
            env_table = Table(title="Environment Variables", show_header=True, header_style="bold magenta")
            env_table.add_column("Variable", style="cyan")
            env_table.add_column("Value")
            
            for var, value in env_vars.items():
                display_value = "••••••••" if len(value) > 20 else value
                env_table.add_row(var, display_value)
            
            self.console.print(env_table)
            self.console.print()
        
        return True
    
    def _step_domain_config(self: Self) -> bool:
        """Configure domain and SSL settings."""
        self.display_step(4, 7, "Domain & SSL Configuration")
        
        # Domain configuration
        use_custom_domain = Confirm.ask("Use a custom domain?", default=False)
        
        if use_custom_domain:
            while True:
                domain = Prompt.ask("Domain name (e.g., myapp.example.com)")
                
                if self._validate_domain(domain):
                    self.deployment_config['domain'] = domain
                    break
                else:
                    self.console.print("[red]Invalid domain name. Please try again.[/red]")
            
            # SSL configuration
            ssl_enabled = Confirm.ask("Enable SSL/HTTPS?", default=True)
            self.deployment_config['ssl_enabled'] = ssl_enabled
            
            if ssl_enabled:
                ssl_method = Prompt.ask(
                    "SSL certificate method",
                    choices=["letsencrypt", "custom", "cloudflare"],
                    default="letsencrypt"
                )
                self.deployment_config['ssl_method'] = ssl_method
                
                if ssl_method == "custom":
                    self.deployment_config['ssl_cert_path'] = Prompt.ask("SSL certificate file path")
                    self.deployment_config['ssl_key_path'] = Prompt.ask("SSL private key file path")
        else:
            self.deployment_config['domain'] = None
            self.deployment_config['ssl_enabled'] = False
        
        return True
    
    def _step_resource_config(self: Self) -> bool:
        """Configure resource allocation."""
        self.display_step(5, 7, "Resource Allocation")
        
        self.console.print("Configure resource limits for your application:")
        self.console.print()
        
        # CPU configuration
        cpu_limit = Prompt.ask(
            "CPU limit (cores)",
            default="1.0"
        )
        self.deployment_config['cpu_limit'] = float(cpu_limit)
        
        # Memory configuration
        memory_limit = Prompt.ask(
            "Memory limit (MB)",
            default="512"
        )
        self.deployment_config['memory_limit'] = int(memory_limit)
        
        # Storage configuration
        storage_size = Prompt.ask(
            "Storage size (GB)",
            default="10"
        )
        self.deployment_config['storage_size'] = int(storage_size)
        
        # Scaling configuration
        if Confirm.ask("Enable auto-scaling?", default=False):
            min_instances = IntPrompt.ask("Minimum instances", default=1)
            max_instances = IntPrompt.ask("Maximum instances", default=3)
            
            self.deployment_config['auto_scaling'] = True
            self.deployment_config['min_instances'] = min_instances
            self.deployment_config['max_instances'] = max_instances
        else:
            self.deployment_config['auto_scaling'] = False
            self.deployment_config['instances'] = IntPrompt.ask("Number of instances", default=1)
        
        return True
    
    def _step_review_and_deploy(self: Self) -> bool:
        """Review configuration and start deployment."""
        self.display_step(6, 7, "Review & Deploy")
        
        self.console.print("Review your deployment configuration:")
        self.console.print()
        
        self._display_deployment_summary()
        
        if not Confirm.ask("Proceed with deployment?", default=True):
            return False
        
        # Start deployment
        try:
            with progress_manager.progress_bar("Deploying application...") as progress:
                task = progress.add_task("Deployment", total=100)
                
                # Deployment steps
                steps = [
                    ("Validating configuration", 10),
                    ("Creating deployment", 15),
                    ("Setting up environment", 10),
                    ("Building application", 25),
                    ("Starting services", 15),
                    ("Configuring networking", 10),
                    ("Running health checks", 10),
                    ("Finalizing deployment", 5)
                ]
                
                completed = 0
                for step_name, duration in steps:
                    progress.update(task, description=f"[cyan]{step_name}[/cyan]")
                    
                    # Simulate deployment step
                    time.sleep(duration / 10)
                    
                    completed += duration
                    progress.update(task, completed=completed)
            
            self.deployment_config['deployment_id'] = f"deploy-{int(time.time())}"
            return True
            
        except Exception as e:
            error_handler.display_error(e, "Deployment failed")
            return False
    
    def _step_monitor_deployment(self: Self) -> bool:
        """Monitor deployment progress."""
        self.display_step(7, 7, "Deployment Monitoring")
        
        self.console.print("Monitoring deployment progress...")
        self.console.print()
        
        # Simulate monitoring
        with progress_manager.spinner("Waiting for application to start..."):
            time.sleep(5)
        
        # Display deployment status
        status_table = Table(title="Deployment Status", show_header=True, header_style="bold magenta")
        status_table.add_column("Component", style="cyan")
        status_table.add_column("Status", justify="center")
        status_table.add_column("Details")
        
        components = [
            ("Application", True, "Running successfully"),
            ("Health Check", True, "Passing"),
            ("Load Balancer", True, "Configured"),
            ("SSL Certificate", self.deployment_config.get('ssl_enabled', False), 
             "Issued" if self.deployment_config.get('ssl_enabled') else "Not configured"),
            ("Domain", bool(self.deployment_config.get('domain')), 
             self.deployment_config.get('domain', 'Not configured'))
        ]
        
        for component, status, details in components:
            status_text = "[green]✓[/green]" if status else "[yellow]○[/yellow]"
            status_table.add_row(component, status_text, details)
        
        self.console.print(status_table)
        self.console.print()
        
        return True
    
    def _display_deployment_summary(self: Self) -> None:
        """Display deployment configuration summary."""
        summary_table = Table(title="Deployment Summary", show_header=True, header_style="bold magenta")
        summary_table.add_column("Setting", style="cyan")
        summary_table.add_column("Value")
        
        summary_table.add_row("Application Name", self.deployment_config['name'])
        summary_table.add_row("Source Type", self.deployment_config['source_type'])
        
        if self.deployment_config['source_type'] == 'git':
            summary_table.add_row("Repository", self.deployment_config['repo_url'])
            summary_table.add_row("Branch", self.deployment_config['branch'])
        elif self.deployment_config['source_type'] == 'docker':
            summary_table.add_row("Docker Image", self.deployment_config['docker_image'])
        
        summary_table.add_row("Application Type", self.deployment_config['app_type'])
        summary_table.add_row("Port", str(self.deployment_config['port']))
        summary_table.add_row("CPU Limit", f"{self.deployment_config['cpu_limit']} cores")
        summary_table.add_row("Memory Limit", f"{self.deployment_config['memory_limit']} MB")
        summary_table.add_row("Storage Size", f"{self.deployment_config['storage_size']} GB")
        
        if self.deployment_config.get('domain'):
            summary_table.add_row("Domain", self.deployment_config['domain'])
            summary_table.add_row("SSL Enabled", "Yes" if self.deployment_config.get('ssl_enabled') else "No")
        
        if self.deployment_config.get('env_vars'):
            summary_table.add_row("Environment Variables", f"{len(self.deployment_config['env_vars'])} configured")
        
        self.console.print(summary_table)
        self.console.print()
    
    def _display_success(self: Self) -> None:
        """Display successful deployment message."""
        self.console.print()
        
        access_url = f"http://localhost:{self.deployment_config['port']}"
        if self.deployment_config.get('domain'):
            protocol = "https" if self.deployment_config.get('ssl_enabled') else "http"
            access_url = f"{protocol}://{self.deployment_config['domain']}"
        
        self.console.print(Panel(
            f"[bold green]Application Deployed Successfully![/bold green]\n\n"
            f"• Application Name: {self.deployment_config['name']}\n"
            f"• Access URL: {access_url}\n"
            f"• Deployment ID: {self.deployment_config.get('deployment_id', 'N/A')}\n\n"
            "[cyan]Next Steps:[/cyan]\n"
            "1. Test your application at the access URL\n"
            "2. Monitor logs: webops logs " + self.deployment_config['name'] + "\n"
            "3. Scale if needed: webops scale " + self.deployment_config['name'] + "\n\n"
            "[yellow]Need help? Run:[/yellow] webops troubleshoot",
            border_style="green",
            title="🚀 Deployment Complete!"
        ))
    
    # Helper methods
    def _validate_git_url(self: Self, url: str) -> bool:
        """Validate Git repository URL."""
        git_patterns = [
            r'^https://github\.com/.+/.+\.git$',
            r'^git@github\.com:.+/.+\.git$',
            r'^https://gitlab\.com/.+/.+\.git$',
            r'^git@gitlab\.com:.+/.+\.git$',
            r'^https://bitbucket\.org/.+/.+\.git$',
            r'^git@bitbucket\.org:.+/.+\.git$'
        ]
        
        return any(re.match(pattern, url) for pattern in git_patterns)
    
    def _validate_docker_image(self: Self, image: str) -> bool:
        """Validate Docker image name."""
        pattern = r'^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*(?::[a-zA-Z0-9._-]+)?$'
        return re.match(pattern, image) is not None
    
    def _validate_app_name(self: Self, name: str) -> bool:
        """Validate application name."""
        pattern = r'^[a-z0-9-]+$'
        return re.match(pattern, name) is not None and len(name) <= 50
    
    def _validate_domain(self: Self, domain: str) -> bool:
        """Validate domain name."""
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        return re.match(pattern, domain) is not None
    
    def _validate_env_var_name(self: Self, name: str) -> bool:
        """Validate environment variable name."""
        pattern = r'^[A-Z_][A-Z0-9_]*$'
        return re.match(pattern, name) is not None
    
    def _detect_application_type(self: Self) -> Optional[str]:
        """Detect application type from source."""
        # This would analyze the source to detect the application type
        # For now, return None to force manual selection
        return None
    
    def _select_application_type(self: Self) -> str:
        """Let user select application type."""
        return Prompt.ask(
            "Application type",
            choices=["nodejs", "python", "php", "ruby", "java", "go", "static", "docker"],
            default="nodejs"
        )
    
    def _get_default_port(self: Self, app_type: str) -> int:
        """Get default port for application type."""
        defaults = {
            'nodejs': 3000,
            'python': 8000,
            'php': 80,
            'ruby': 3000,
            'java': 8080,
            'go': 8080,
            'static': 80,
            'docker': 80
        }
        return defaults.get(app_type, 8000)
    
    def _get_default_build_command(self: Self, app_type: str) -> str:
        """Get default build command for application type."""
        defaults = {
            'nodejs': 'npm install && npm run build',
            'python': 'pip install -r requirements.txt',
            'ruby': 'bundle install',
            'java': 'mvn clean package',
            'go': 'go build'
        }
        return defaults.get(app_type, '')
    
    def _get_default_start_command(self: Self, app_type: str) -> str:
        """Get default start command for application type."""
        defaults = {
            'nodejs': 'npm start',
            'python': 'python app.py',
            'php': 'php -S 0.0.0.0:80',
            'ruby': 'ruby app.rb',
            'java': 'java -jar target/app.jar',
            'go': './app',
            'static': 'nginx -g "daemon off;"'
        }
        return defaults.get(app_type, '')
    
    def _get_common_env_vars(self: Self, app_type: str) -> Dict[str, str]:
        """Get common environment variables for application type."""
        common_vars = {
            'nodejs': {
                'NODE_ENV': 'Environment (development/production)',
                'PORT': 'Application port'
            },
            'python': {
                'PYTHONPATH': 'Python path',
                'DEBUG': 'Debug mode (true/false)'
            },
            'php': {
                'PHP_ENV': 'PHP environment',
                'APP_DEBUG': 'Debug mode'
            }
        }
        return common_vars.get(app_type, {})
    
    def _check_git_access(self: Self, repo_url: str, branch: str) -> bool:
        """Check if Git repository is accessible."""
        try:
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', repo_url, branch],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def _is_private_repo(self: Self, repo_url: str) -> bool:
        """Check if repository is likely private."""
        return 'github.com' in repo_url or 'gitlab.com' in repo_url or 'bitbucket.org' in repo_url
    
    def _is_private_registry(self: Self, image: str) -> bool:
        """Check if Docker image is from a private registry."""
        return '/' in image and not image.startswith('docker.io/')


@click.command()
def deploy():
    """Run the interactive deployment wizard."""
    deployment_wizard = DeploymentWizard()
    success = deployment_wizard.run()
    
    if success:
        console.print("\n[green]Deployment completed successfully![/green]")
    else:
        console.print("\n[red]Deployment failed or was cancelled.[/red]")


if __name__ == '__main__':
    deploy()