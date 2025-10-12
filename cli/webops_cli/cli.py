"""Main CLI interface for WebOps."""

import sys
import time
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.spinner import Spinner

from .config import Config
from .api import WebOpsAPIClient, WebOpsAPIError

console = Console()
config = Config()


def get_api_client() -> WebOpsAPIClient:
    """Get configured API client or exit with error."""
    if not config.is_configured():
        console.print("[red]Error:[/red] WebOps CLI is not configured.")
        console.print("Run: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
        sys.exit(1)

    return WebOpsAPIClient(
        base_url=config.get_url(),
        token=config.get_token()
    )


@click.group()
@click.version_option(version="0.1.0")
def main():
    """WebOps CLI - Manage your deployments from the command line."""
    pass


@main.command()
@click.option('--url', help='WebOps panel URL (e.g., https://panel.example.com)')
@click.option('--token', help='API authentication token')
def config_cmd(url: Optional[str], token: Optional[str]):
    """Configure WebOps CLI."""
    if not url and not token:
        # Show current configuration
        current_url = config.get_url()
        current_token = config.get_token()

        if current_url:
            console.print(f"[green]URL:[/green] {current_url}")
        if current_token:
            masked_token = current_token[:8] + "..." + current_token[-4:]
            console.print(f"[green]Token:[/green] {masked_token}")

        if not (current_url and current_token):
            console.print("\n[yellow]Not fully configured.[/yellow]")
            console.print("Usage: [cyan]webops config --url <URL> --token <TOKEN>[/cyan]")
        return

    if url:
        config.set('url', url.rstrip('/'))
        console.print(f"[green]✓[/green] URL set to: {url}")

    if token:
        config.set('token', token)
        console.print("[green]✓[/green] Token saved")

    if url and token:
        console.print("\n[green]Configuration complete![/green]")


@main.command(name='list')
@click.option('--status', help='Filter by status (pending, building, running, stopped, failed)')
@click.option('--page', default=1, help='Page number')
@click.option('--per-page', default=20, help='Results per page')
def list_deployments(status: Optional[str], page: int, per_page: int):
    """List all deployments."""
    client = get_api_client()

    try:
        with console.status("[cyan]Fetching deployments...", spinner="dots"):
            result = client.list_deployments(page=page, per_page=per_page, status=status)

        deployments = result.get('deployments', [])

        if not deployments:
            console.print("[yellow]No deployments found.[/yellow]")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Type")
        table.add_column("Domain")
        table.add_column("Branch")

        for d in deployments:
            status_color = {
                'pending': 'yellow',
                'building': 'blue',
                'running': 'green',
                'stopped': 'white',
                'failed': 'red'
            }.get(d['status'], 'white')

            table.add_row(
                d['name'],
                f"[{status_color}]{d['status']}[/{status_color}]",
                d['project_type'],
                d.get('domain', '-'),
                d['branch']
            )

        console.print(table)

        pagination = result.get('pagination', {})
        console.print(f"\nPage {pagination.get('page', 1)} of {pagination.get('pages', 1)}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def info(name: str):
    """Show deployment details."""
    client = get_api_client()

    try:
        with console.status(f"[cyan]Fetching info for {name}...", spinner="dots"):
            deployment = client.get_deployment(name)

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
def deploy(repo: str, name: str, branch: str, domain: str):
    """Deploy a new application."""
    client = get_api_client()

    try:
        console.print(f"[cyan]Creating deployment:[/cyan] {name}")
        result = client.create_deployment(
            name=name,
            repo_url=repo,
            branch=branch,
            domain=domain
        )

        console.print(f"[green]✓[/green] Deployment created: {result.get('message')}")
        console.print(f"[cyan]ID:[/cyan] {result.get('id')}")
        console.print("\nUse [cyan]webops logs {name}[/cyan] to monitor deployment progress")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
@click.option('--tail', type=int, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(name: str, tail: Optional[int], follow: bool):
    """View deployment logs."""
    client = get_api_client()

    try:
        if follow:
            console.print(f"[cyan]Following logs for {name}...[/cyan] (Ctrl+C to stop)\n")
            last_log_count = 0

            while True:
                result = client.get_deployment_logs(name, tail=tail)
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
            with console.status(f"[cyan]Fetching logs for {name}...", spinner="dots"):
                result = client.get_deployment_logs(name, tail=tail)

            logs_list = result.get('logs', [])

            if not logs_list:
                console.print("[yellow]No logs found.[/yellow]")
                return

            for log in logs_list:
                level_color = {
                    'info': 'cyan',
                    'warning': 'yellow',
                    'error': 'red',
                    'success': 'green'
                }.get(log['level'], 'white')

                console.print(f"[{level_color}]{log['created_at']}[/{level_color}] {log['message']}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs.[/yellow]")
    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def start(name: str):
    """Start a deployment."""
    client = get_api_client()

    try:
        with console.status(f"[cyan]Starting {name}...", spinner="dots"):
            result = client.start_deployment(name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment started')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def stop(name: str):
    """Stop a deployment."""
    client = get_api_client()

    try:
        with console.status(f"[cyan]Stopping {name}...", spinner="dots"):
            result = client.stop_deployment(name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment stopped')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
def restart(name: str):
    """Restart a deployment."""
    client = get_api_client()

    try:
        with console.status(f"[cyan]Restarting {name}...", spinner="dots"):
            result = client.restart_deployment(name)

        console.print(f"[green]✓[/green] {result.get('message', 'Deployment restarted')}")

    except WebOpsAPIError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
@click.argument('name')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def delete(name: str, yes: bool):
    """Delete a deployment."""
    if not yes:
        confirm = click.confirm(f"Are you sure you want to delete '{name}'? This cannot be undone.")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            return

    client = get_api_client()

    try:
        with console.status(f"[cyan]Deleting {name}...", spinner="dots"):
            result = client.delete_deployment(name)

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
def env_generate(name: str, debug: bool, domain: Optional[str], set: tuple):
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
def env_validate(name: str):
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
def env_show(name: str, show_secrets: bool):
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
def env_set(name: str, key: str, value: str, restart: bool):
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
            console.print(f"\n[cyan]Restarting {name}...[/cyan]")
            restart_result = client.restart_deployment(name)
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
def env_unset(name: str, key: str, restart: bool):
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


# Register config command with proper name
main.add_command(config_cmd, name='config')


if __name__ == '__main__':
    main()
