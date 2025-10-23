"""Main CLI interface for WebOps with enhanced features."""

import sys
import time
import asyncio
from typing import Optional, Tuple, Dict, Any, List, Self

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner
from rich.prompt import Confirm

from .config import Config
from .api import WebOpsAPIClient, WebOpsAPIError, RBACError, TokenExpiredError, Role, Permission
from .validators import InputValidator, ValidationError
from .security_logging import get_security_logger, SecurityEventType
from .encryption import EncryptionError
from .errors import ErrorHandler
from .admin import admin
from .system import system
from .ui.interactive import InteractiveCommands
from .ui.display import display_deployment_table, _get_status_style
from .command_shortcuts import create_shortcut_commands
from .websocket_client import DeploymentStatusMonitor, DeploymentListMonitor

console = Console()
error_handler = ErrorHandler()
config = Config()


def confirm_destructive_action(
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
        
    console.print(
        Panel(
            f"[bold red]Warning:[/bold red] You are about to {action} '{resource}'.\n"
            f"This action cannot be undone.",
            title="Confirmation Required",
            border_style="red"
        )
    )
    
    return Confirm.ask(f"Are you sure you want to {action} '{resource}'?")


def display_logs_with_formatting(
    logs: List[str],
    deployment_name: str
) -> None:
    """Display logs with syntax highlighting and formatting.
    
    Args:
        logs: List of log lines.
        deployment_name: Name of the deployment.
    """
    if not logs:
        console.print("[yellow]No logs available.[/yellow]")
        return
        
    console.print(
        Panel(
            f"Logs for [cyan]{deployment_name}[/cyan]",
            border_style="blue"
        )
    )
    
    for line in logs:
        # Basic log level highlighting
        if 'ERROR' in line or 'CRITICAL' in line:
            console.print(f"[red]{line}[/red]")
        elif 'WARNING' in line or 'WARN' in line:
            console.print(f"[yellow]{line}[/yellow]")
        elif 'INFO' in line:
            console.print(f"[blue]{line}[/blue]")
        elif 'DEBUG' in line:
            console.print(f"[dim]{line}[/dim]")
        else:
            console.print(line)


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


def get_api_client() -> WebOpsAPIClient:
    """Get configured API client or exit with error."""
    if not config.is_configured():
        console.print("[red]Error:[/red] WebOps CLI is not configured.")
        console.print("Run: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
        sys.exit(1)

    try:
        # Get user role from config or default to developer
        user_role = config.get('role', Role.DEVELOPER)
        
        # Create enhanced API client with security features enabled
        return WebOpsAPIClient(
            base_url=config.get_url(),
            token=config.get_token(),
            user_role=user_role,
            enable_security=True
        )
    except (ValidationError, EncryptionError) as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        sys.exit(1)
    except RBACError as e:
        console.print(f"[red]Authorization Error:[/red] {e}")
        sys.exit(1)


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """WebOps CLI - Manage your deployments from the command line."""
    pass


@main.command()
@click.option('--url', help='WebOps panel URL (e.g., https://panel.example.com)')
@click.option('--token', help='API authentication token')
@click.option('--role', type=click.Choice(['admin', 'developer', 'viewer']), help='User role for RBAC')
def config_cmd(url: Optional[str], token: Optional[str], role: Optional[str]) -> None:
    """Configure WebOps CLI."""
    security_logger = get_security_logger()
    
    if not url and not token and not role:
        # Show current configuration
        current_url = config.get_url()
        current_token = config.get_token()
        current_role = config.get('role', 'developer')

        if current_url:
            console.print(f"[green]URL:[/green] {current_url}")
        if current_token:
            masked_token = current_token[:8] + "..." + current_token[-4:]
            console.print(f"[green]Token:[/green] {masked_token}")
        console.print(f"[green]Role:[/green] {current_role}")

        if not (current_url and current_token):
            console.print("\n[yellow]Not fully configured.[/yellow]")
            console.print("Usage: [cyan]webops config --url <URL> --token <TOKEN> --role <ROLE>[/cyan]")
        return

    try:
        changes = []
        
        if url:
            validated_url = InputValidator.validate_url(url)
            old_url = config.get_url()
            config.set('url', validated_url)
            console.print(f"[green]✓[/green] URL set to: {validated_url}")
            changes.append(('url', old_url, validated_url))

        if token:
            validated_token = InputValidator.validate_api_token(token)
            old_token = config.get_token()
            config.set('token', validated_token)
            console.print("[green]✓[/green] Token saved")
            changes.append(('token', old_token, '***MASKED***'))

        if role:
            old_role = config.get('role', 'developer')
            config.set('role', role)
            console.print(f"[green]✓[/green] Role set to: {role}")
            changes.append(('role', old_role, role))

        # Log configuration changes
        for setting, old_value, new_value in changes:
            security_logger.log_configuration_change(
                user=security_logger.get_user(),
                setting=setting,
                old_value=old_value,
                new_value=new_value
            )

        if url and token:
            console.print("\n[green]Configuration complete![/green]")
            
    except ValidationError as e:
        security_logger.log_security_violation(
            user=security_logger.get_user(),
            violation_type="invalid_input",
            description=f"Configuration validation failed: {e}",
            severity="MEDIUM"
        )
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    except EncryptionError as e:
        security_logger.log_error(
            user=security_logger.get_user(),
            error_type="encryption_error",
            error_message=str(e)
        )
        console.print(f"[red]Encryption Error:[/red] {e}")
        sys.exit(1)


@main.command(name='list')
@click.option('--status', help='Filter by status (pending, building, running, stopped, failed)')
@click.option('--page', default=1, help='Page number')
@click.option('--per-page', default=20, help='Results per page')
def list_deployments(status: Optional[str], page: int, per_page: int) -> None:
    """List all deployments."""
    try:
        # Validate pagination parameters
        validated_page = InputValidator.validate_page_number(page)
        validated_per_page = InputValidator.validate_per_page(per_page)
        
        # Validate status if provided
        if status:
            valid_statuses = ['pending', 'building', 'running', 'stopped', 'failed']
            if status not in valid_statuses:
                raise ValidationError(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        with console.status("[cyan]Fetching deployments...", spinner="dots"):
            result = client.list_deployments(page=validated_page, per_page=validated_per_page, status=status)

        deployments = result.get('deployments', [])
        display_deployment_table(deployments)

        pagination = result.get('pagination', {})
        console.print(f"\nPage {pagination.get('page', 1)} of {pagination.get('pages', 1)}")

    except (WebOpsAPIError, RBACError, TokenExpiredError) as e:
        if isinstance(e, RBACError):
            console.print(f"[red]Authorization Error:[/red] {e}")
            console.print("[yellow]Hint:[/yellow] Check your user role or contact an administrator")
        elif isinstance(e, TokenExpiredError):
            console.print(f"[red]Authentication Error:[/red] {e}")
            console.print("[yellow]Hint:[/yellow] Please re-authenticate with a new token")
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def info(name: str) -> None:
    """Show deployment details."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        with console.status(f"[cyan]Fetching info for {validated_name}...", spinner="dots"):
            deployment = client.get_deployment(validated_name)

        status_color = {
            'pending': 'yellow',
            'building': 'blue',
            'running': 'green',
            'stopped': 'white',
            'failed': 'red'
        }.get(deployment['status'], 'white')

        info_text = f"""
[cyan]Name:[/cyan] {deployment['name']}
[cyan]Status:[/cyan] [{status_color}]{deployment['status']}[/{status_color}]
[cyan]Type:[/cyan] {deployment['project_type']}
[cyan]Repository:[/cyan] {deployment['repo_url']}
[cyan]Branch:[/cyan] {deployment['branch']}
[cyan]Domain:[/cyan] {deployment.get('domain') or 'Not set'}
[cyan]Port:[/cyan] {deployment.get('port') or 'Not assigned'}
[cyan]Created:[/cyan] {deployment['created_at']}
[cyan]Updated:[/cyan] {deployment['updated_at']}
        """

        console.print(Panel(info_text.strip(), title=f"Deployment: {name}", border_style="cyan"))

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.option('--repo', required=True, help='Repository URL')
@click.option('--name', required=True, help='Deployment name')
@click.option('--branch', default='main', help='Git branch')
@click.option('--domain', default='', help='Domain name')
def deploy(repo: str, name: str, branch: str, domain: str) -> None:
    """Deploy a new application."""
    try:
        # Validate all inputs
        validated_name = InputValidator.validate_deployment_name(name)
        validated_repo = InputValidator.validate_git_url(repo)
        validated_branch = InputValidator.validate_git_branch(branch)
        validated_domain = InputValidator.validate_domain_name(domain)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        console.print(f"[cyan]Creating deployment:[/cyan] {validated_name}")
        result = client.create_deployment(
            name=validated_name,
            repo_url=validated_repo,
            branch=validated_branch,
            domain=validated_domain
        )

        sanitized_name = result.get('name', validated_name)
        console.print(f"[green]✓[/green] Deployment created: {result.get('message')}")
        console.print(f"[cyan]ID:[/cyan] {result.get('id')}")
        console.print(f"[cyan]Name:[/cyan] {sanitized_name}")
        console.print(f"\nUse [cyan]webops logs {sanitized_name}[/cyan] to monitor deployment progress")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
@click.option('--tail', type=int, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(name: str, tail: Optional[int], follow: bool) -> None:
    """View deployment logs."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
        validated_tail = InputValidator.validate_tail_count(tail)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        if follow:
            console.print(f"[cyan]Following logs for {validated_name}...[/cyan] (Ctrl+C to stop)\n")
            last_log_count = 0

            while True:
                result = client.get_deployment_logs(validated_name, tail=validated_tail)
                logs_list = result.get('logs', [])

                # Only show new logs
                if len(logs_list) > last_log_count:
                    for log in logs_list[last_log_count:]:
                        level_color = {
                            'info': 'cyan',
                            'warning': 'yellow',
                            'error': 'red',
                            'success': 'green'
                        }.get(log['level'], 'white')

                        console.print(f"[{level_color}]{log['created_at']}[/{level_color}] {log['message']}")

                    last_log_count = len(logs_list)

                time.sleep(2)
        else:
            with console.status(f"[cyan]Fetching logs for {validated_name}...", spinner="dots"):
                result = client.get_deployment_logs(validated_name, tail=validated_tail)

            logs_list = result.get('logs', [])

            if not logs_list:
                console.print("[yellow]No logs found.[/yellow]")
                return

            # Convert log objects to strings for formatting
            log_strings = [f"{log['created_at']} {log['level']} {log['message']}" for log in logs_list]
            display_logs_with_formatting(log_strings, validated_name)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs.[/yellow]")
    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def start(name: str) -> None:
    """Start a deployment."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        with console.status(f"[cyan]Starting {validated_name}...", spinner="dots"):
            result = client.start_deployment(validated_name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment started')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def stop(name: str) -> None:
    """Stop a deployment."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        with console.status(f"[cyan]Stopping {validated_name}...", spinner="dots"):
            result = client.stop_deployment(validated_name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment stopped')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def restart(name: str) -> None:
    """Restart a deployment."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    client = get_api_client()

    try:
        with console.status(f"[cyan]Restarting {validated_name}...", spinner="dots"):
            result = client.restart_deployment(validated_name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment restarted')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def delete(name: str, yes: bool) -> None:
    """Delete a deployment."""
    try:
        validated_name = InputValidator.validate_deployment_name(name)
    except ValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        sys.exit(1)
    
    if not yes:
        if not confirm_destructive_action("delete", validated_name):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    client = get_api_client()

    try:
        with console.status(f"[cyan]Deleting {validated_name}...", spinner="dots"):
            result = client.delete_deployment(validated_name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment deleted')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='db:list')
def database_list():
    """List all databases."""
    client = get_api_client()

    try:
        with console.status("[cyan]Fetching databases...", spinner="dots"):
            result = client.list_databases()

        databases = result.get('databases', [])

        if not databases:
            console.print("[yellow]No databases found.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name")
        table.add_column("Deployment")
        table.add_column("Host")
        table.add_column("Port")

        for db in databases:
            table.add_row(
                db['name'],
                db['deployment'],
                db['host'],
                str(db['port'])
            )

        console.print(table)

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='db:credentials')
@click.argument('name')
def database_credentials(name: str):
    """Show database credentials."""
    client = get_api_client()

    try:
        with console.status(f"[cyan]Fetching credentials for {name}...", spinner="dots"):
            db = client.get_database(name)

        info_text = f"""
[cyan]Database:[/cyan] {db['name']}
[cyan]Username:[/cyan] {db['username']}
[cyan]Password:[/cyan] {db['password']}
[cyan]Host:[/cyan] {db['host']}
[cyan]Port:[/cyan] {db['port']}

[cyan]Connection String:[/cyan]
postgresql://{db['username']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}
        """

        console.print(Panel(info_text.strip(), title=f"Database: {name}", border_style="cyan"))

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def status():
    """Check WebOps API status."""
    client = get_api_client()

    try:
        with console.status("[cyan]Checking API status...", spinner="dots"):
            result = client.get_status()

        status_text = f"""
[cyan]Status:[/cyan] [green]{result.get('status', 'unknown')}[/green]
[cyan]Version:[/cyan] {result.get('version', 'unknown')}
[cyan]Timestamp:[/cyan] {result.get('timestamp', 'unknown')}
        """

        console.print(Panel(status_text.strip(), title="WebOps API Status", border_style="green"))

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='env:generate')
@click.argument('name')
@click.option('--debug', is_flag=True, help='Enable debug mode in generated .env')
@click.option('--domain', help='Custom domain name')
@click.option('--set', multiple=True, help='Set custom env variable (KEY=VALUE)')
def env_generate(name: str, debug: bool, domain: Optional[str], set: Tuple[str, ...]) -> None:
    """
    Generate .env file from .env.example for a deployment.

    This command processes the .env.example file in the deployment repository
    and intelligently generates appropriate values for all variables.

    Examples:
        webops env:generate myapp
        webops env:generate myapp --debug
        webops env:generate myapp --domain example.com
        webops env:generate myapp --set API_KEY=secret123 --set SMTP_HOST=smtp.gmail.com
    """
    client = get_api_client()

    try:
        # Parse custom env vars
        custom_vars = {}
        for item in set:
            if '=' not in item:
                console.print(f"[red]Error:[/red] Invalid --set format: {item}")
                console.print("Use: [cyan]--set KEY=VALUE[/cyan]")
                sys.exit(1)
            key, value = item.split('=', 1)
            custom_vars[key.strip()] = value.strip()

        with console.status(f"[cyan]Generating .env file for {name}...", spinner="dots"):
            result = client.generate_env(
                deployment_name=name,
                debug=debug,
                domain=domain,
                custom_vars=custom_vars
            )

        console.print(f"[green]✓[/green] {result.get('message', 'Environment file generated')}")

        if custom_vars:
            console.print("\n[cyan]Custom variables applied:[/cyan]")
            for key in custom_vars.keys():
                console.print(f"  • {key}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='env:validate')
@click.argument('name')
def env_validate(name: str) -> None:
    """
    Validate .env file for a deployment.

    Checks that all required environment variables from .env.example
    are present and set in the .env file.

    Example:
        webops env:validate myapp
    """
    client = get_api_client()

    try:
        with console.status(f"[cyan]Validating .env file for {name}...", spinner="dots"):
            result = client.validate_env(deployment_name=name)

        is_valid = result.get('valid', False)
        missing = result.get('missing', [])

        if is_valid:
            console.print(f"[green]✓[/green] .env file is valid - all required variables are set")
        else:
            console.print(f"[red]✗[/red] .env file validation failed\n")
            console.print("[yellow]Missing or empty variables:[/yellow]")
            for var in missing:
                console.print(f"  • {var}")
            console.print(f"\nRun: [cyan]webops env:generate {name}[/cyan] to regenerate")
            sys.exit(1)
    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='env:show')
@click.argument('name')
@click.option('--show-secrets', is_flag=True, help='Show full values of secret variables')
def env_show(name: str, show_secrets: bool) -> None:
    """
    Show environment variables for a deployment.

    By default, secret values (passwords, keys, tokens) are masked.
    Use --show-secrets to display full values (be careful in shared terminals!).

    Examples:
        webops env:show myapp
        webops env:show myapp --show-secrets
    """
    client = get_api_client()

    try:
        with console.status(f"[cyan]Fetching environment variables for {name}...", spinner="dots"):
            result = client.get_env_vars(deployment_name=name)

        env_vars = result.get('env_vars', {})

        if not env_vars:
            console.print("[yellow]No environment variables found.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Variable", style="cyan")
        table.add_column("Value")

        secret_keywords = ['SECRET', 'PASSWORD', 'KEY', 'TOKEN', 'API', 'AUTH']

        for key, value in sorted(env_vars.items()):
            # Mask sensitive values
            is_secret = any(keyword in key.upper() for keyword in secret_keywords)

            if is_secret and not show_secrets and value:
                if len(value) > 8:
                    masked_value = value[:4] + '*' * 8 + value[-4:]
                else:
                    masked_value = '*' * len(value)
                table.add_row(key, f"[dim]{masked_value}[/dim]")
            else:
                table.add_row(key, value or "[dim](empty)[/dim]")

        console.print(table)

        if not show_secrets:
            console.print("\n[dim]Tip: Use --show-secrets to display full values[/dim]")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='env:set')
@click.argument('name')
@click.argument('key')
@click.argument('value')
@click.option('--restart', is_flag=True, help='Restart deployment after updating')
def env_set(name: str, key: str, value: str, restart: bool) -> None:
    """
    Set an environment variable for a deployment.

    Updates the .env file and optionally restarts the deployment
    to apply the change.

    Examples:
        webops env:set myapp DEBUG True
        webops env:set myapp API_KEY sk_live_123 --restart
    """
    client = get_api_client()

    try:
        with console.status(f"[cyan]Setting {key}...", spinner="dots"):
            result = client.set_env_var(
                deployment_name=name,
                key=key,
                value=value
            )

        console.print(f"[green]✓[/green] {key} = {value}")

        if restart:
            console.print(f"\n[cyan]Restarting {validated_name}...[/cyan]")
            restart_result = client.restart_deployment(validated_name)
            console.print(f"[green]✓[/green] Deployment restarted")
        else:
            console.print(f"\n[dim]Tip: Use --restart to apply changes immediately[/dim]")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='env:unset')
@click.argument('name')
@click.argument('key')
@click.option('--restart', is_flag=True, help='Restart deployment after updating')
def env_unset(name: str, key: str, restart: bool) -> None:
    """
    Remove an environment variable from a deployment.

    Examples:
        webops env:unset myapp TEMP_KEY
        webops env:unset myapp DEBUG --restart
    """
    client = get_api_client()

    try:
        with console.status(f"[cyan]Removing {key}...", spinner="dots"):
            result = client.unset_env_var(
                deployment_name=name,
                key=key
            )

        console.print(f"[green]✓[/green] {key} removed")

        if restart:
            console.print(f"\n[cyan]Restarting {name}...[/cyan]")
            restart_result = client.restart_deployment(name)
            console.print(f"[green]✓[/green] Deployment restarted")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='project:validate')
@click.argument('name')
def project_validate(name: str) -> None:
    """
    Validate project structure and requirements for a deployment.

    Example:
        webops project:validate myapp
    """
    client = get_api_client()

    try:
        with console.status(f"[cyan]Validating project for {name}...", spinner="dots"):
            result = client.validate_project(deployment_name=name)

        all_passed = result.get('all_passed', False)
        checks = result.get('results', [])

        if all_passed:
            console.print("[green]✓[/green] Project validation passed — ready to deploy")
            return

        errors = sum(1 for r in checks if r.get('level') == 'error')
        warnings = sum(1 for r in checks if r.get('level') == 'warning')
        infos = sum(1 for r in checks if r.get('level') == 'info')

        console.print("[red]✗[/red] Project validation found issues")
        console.print(f"[cyan]Summary:[/cyan] {errors} error(s), {warnings} warning(s), {infos} info")
        console.print("\n[cyan]Checks:[/cyan]")

        for r in checks:
            level = r.get('level', 'info')
            color = {'error': 'red', 'warning': 'yellow', 'info': 'cyan'}.get(level, 'white')
            icon = '✓' if r.get('passed') else '✗'
            message = r.get('message', '')
            console.print(f"  • [{color}]{icon}[/{color}] {message}")
            details = r.get('details') or {}
            if details and not r.get('passed'):
                count = 0
                for k, v in details.items():
                    kv = f"{k}: {v}"
                    if len(kv) > 120:
                        kv = kv[:120] + "…"
                    console.print(f"      [dim]{kv}[/dim]")
                    count += 1
                    if count >= 5:
                        break

        sys.exit(1)

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name='setup')
def setup_wizard():
    """Run the interactive WebOps setup wizard."""
    from .wizards import SetupWizard
    wizard = SetupWizard()
    success = wizard.run()

    if success:
        console.print("\n[green]Setup completed successfully![/green]")
    else:
        console.print("\n[red]Setup failed or was cancelled.[/red]")


@main.command(name='deploy-wizard')
def deploy_wizard():
    """Run the interactive deployment wizard."""
    from .wizards import DeploymentWizard
    wizard = DeploymentWizard()
    success = wizard.run()

    if success:
        console.print("\n[green]Deployment wizard completed successfully![/green]")
    else:
        console.print("\n[red]Deployment wizard failed or was cancelled.[/red]")


@main.command(name='troubleshoot')
def troubleshoot_wizard():
    """Run the interactive troubleshooting wizard."""
    from .wizards import TroubleshootingWizard
    wizard = TroubleshootingWizard()
    success = wizard.run()

    if success:
        console.print("\n[green]Troubleshooting completed successfully![/green]")
    else:
        console.print("\n[red]Troubleshooting failed or was cancelled.[/red]")


@main.command()
@click.option('--refresh-rate', default=2, help='Refresh rate in seconds')
def interactive_status(refresh_rate: int) -> None:
    """Display interactive system status dashboard."""
    api_client = get_api_client()
    config = Config()
    interactive_cmd = InteractiveCommands(api_client, config)
    interactive_cmd.interactive_status()


@main.command()
def manage() -> None:
    """Interactive deployment management interface."""
    api_client = get_api_client()
    config = Config()
    interactive_cmd = InteractiveCommands(api_client, config)
    interactive_cmd.interactive_deployment_manager()


@main.command(name='interactive-logs')
@click.argument('deployment_name', required=False)
def interactive_logs(deployment_name: str) -> None:
    """Interactive logs viewer with real-time updates."""
    api_client = get_api_client()
    config = Config()
    interactive_cmd = InteractiveCommands(api_client, config)
    interactive_cmd.interactive_logs_viewer(deployment_name)


@main.command(name='watch')
@click.argument('deployment_name', required=False)
@click.option('--all', '-a', is_flag=True, help='Watch all deployments')
def watch_deployments(deployment_name: Optional[str], all: bool) -> None:
    """Watch deployment status in real-time via WebSocket."""
    if not config.is_configured():
        console.print("[red]Error:[/red] WebOps CLI is not configured.")
        console.print("Run: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
        sys.exit(1)

    if all or not deployment_name:
        console.print("[cyan]Watching all deployments...[/cyan]")
        console.print("Press Ctrl+C to stop")
        
        async def run_monitor():
            monitor = DeploymentListMonitor(config)
            await monitor.monitor_deployments()
        
        try:
            asyncio.run(run_monitor())
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped watching deployments[/yellow]")
    else:
        console.print(f"[cyan]Watching deployment: {deployment_name}[/cyan]")
        console.print("Press Ctrl+C to stop")
        
        async def run_monitor():
            monitor = DeploymentStatusMonitor(config)
            await monitor.monitor_deployment(deployment_name)
        
        try:
            asyncio.run(run_monitor())
        except KeyboardInterrupt:
            console.print(f"\n[yellow]Stopped watching {deployment_name}[/yellow]")


from typing import Any, Dict, List, Optional, Self
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

console = Console()


class EnhancedCLI:
    """Enhanced CLI components for WebOps."""
    
    def __init__(self: Self, api_client: Optional[Any] = None, config: Optional[Any] = None) -> None:
        """Initialize enhanced CLI components.
        
        Args:
            api_client: Optional WebOps API client instance.
            config: Optional configuration instance.
        """
        self.api_client = api_client
        self.config = config
        self.console = console
    
    def display_deployment_table(self: Self, deployments: List[Dict[str, Any]]) -> None:
        """Display deployments in a formatted table.
        
        Args:
            deployments: List of deployment dictionaries.
        """
        if not deployments:
            self.console.print("[yellow]No deployments found[/yellow]")
            return
        
        table = Table(title="WebOps Deployments")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Health", justify="center")
        table.add_column("Domain", style="blue")
        table.add_column("Repository", style="dim")
        
        for deployment in deployments:
            if not isinstance(deployment, dict):
                continue
                
            name = deployment.get('name', 'N/A')
            status = deployment.get('status', 'unknown')
            health = deployment.get('health', 'unknown')
            domain = deployment.get('domain', 'N/A')
            repo_url = deployment.get('repo_url', 'N/A')
            
            # Color code the status
            if status == 'running':
                status_text = "[green]●[/green] Running"
            elif status == 'stopped':
                status_text = "[red]●[/red] Stopped"
            elif status == 'deploying':
                status_text = "[yellow]◐[/yellow] Deploying"
            elif status == 'error':
                status_text = "[red]✗[/red] Error"
            else:
                status_text = f"[yellow]?[/yellow] {status}"
            
            # Color code the health
            if health == 'healthy':
                health_text = "[green]●[/green] Healthy"
            elif health == 'unhealthy':
                health_text = "[red]●[/red] Unhealthy"
            elif health == 'degraded':
                health_text = "[yellow]●[/yellow] Degraded"
            else:
                health_text = f"[yellow]?[/yellow] {health}"
            
            # Truncate long URLs
            if len(repo_url) > 40:
                repo_url = repo_url[:37] + "..."
            
            table.add_row(name, status_text, health_text, domain, repo_url)
        
        self.console.print(table)
    
    def confirm_destructive_action(self: Self, action: str, target: str) -> bool:
        """Confirm a destructive action.
        
        Args:
            action: The action being performed (e.g., "stop", "restart", "delete").
            target: The target of the action (e.g., deployment name).
            
        Returns:
            True if the user confirms the action, False otherwise.
        """
        self.console.print(f"\n[yellow]You are about to {action} '{target}'.[/yellow]")
        self.console.print("[red]This action may have consequences.[/red]")
        
        return Confirm.ask(f"Are you sure you want to {action} '{target}'?", default=False)
        
# Register config command with proper name
main.add_command(config_cmd, name='config')

# Register shortcut commands
create_shortcut_commands(main)

# Add command groups
main.add_command(admin)
main.add_command(system)


if __name__ == '__main__':
    main()
