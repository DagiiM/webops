"""Progress management and display utilities for WebOps CLI."""

import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, Self

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.status import Status
from rich.table import Table

console = Console()


class ProgressManager:
    """Manages different types of progress indicators for WebOps operations."""
    
    def __init__(self: Self) -> None:
        """Initialize the progress manager."""
        self.console = console
    
    @contextmanager
    def spinner(
        self: Self,
        message: str,
        spinner_style: str = "dots"
    ) -> Iterator[Status]:
        """Create a spinner for indeterminate progress.
        
        Args:
            message: The message to display with the spinner.
            spinner_style: The spinner style to use.
            
        Yields:
            Status object that can be updated.
        """
        with self.console.status(message, spinner=spinner_style) as status:
            yield status
    
    @contextmanager
    def progress_bar(
        self: Self,
        description: str = "Processing...",
        show_percentage: bool = True,
        show_time: bool = True
    ) -> Iterator[Progress]:
        """Create a progress bar for determinate progress.
        
        Args:
            description: Description of the operation.
            show_percentage: Whether to show percentage completion.
            show_time: Whether to show elapsed/remaining time.
            
        Yields:
            Progress object for tracking tasks.
        """
        columns = [
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
        ]
        
        if show_percentage:
            columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
        
        # Add completion column
        columns.append(MofNCompleteColumn())  # type: ignore
        
        if show_time:
            # Add time columns
            columns.extend([  # type: ignore
                TimeElapsedColumn(),
                TimeRemainingColumn()
            ])
        
        with Progress(*columns, console=self.console) as progress:
            yield progress
    
    @contextmanager
    def multi_progress(
        self: Self,
        title: str = "WebOps Operations"
    ) -> Iterator[Progress]:
        """Create a multi-task progress display.
        
        Args:
            title: Title for the progress display.
            
        Yields:
            Progress object for managing multiple tasks.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=True
        ) as progress:
            yield progress
    
    def show_deployment_progress(
        self: Self,
        deployment_name: str,
        steps: list[str]
    ) -> None:
        """Show progress for a deployment operation.
        
        Args:
            deployment_name: Name of the deployment being processed.
            steps: List of deployment steps to execute.
        """
        with self.progress_bar(f"Deploying {deployment_name}") as progress:
            task = progress.add_task("Deployment", total=len(steps))
            
            for _, step in enumerate(steps):
                progress.update(task, description=f"[cyan]{step}[/cyan]")
                # Simulate step execution time
                time.sleep(0.5)
                progress.advance(task)
    
    def show_health_check_progress(
        self: Self,
        checks: dict[str, Callable[[], bool]]
    ) -> dict[str, bool]:
        """Show progress for system health checks.
        
        Args:
            checks: Dictionary of check names to check functions.
            
        Returns:
            Dictionary of check results.
        """
        results = {}
        
        with self.progress_bar("Running health checks") as progress:
            task = progress.add_task("Health Check", total=len(checks))
            
            for check_name, check_func in checks.items():
                progress.update(task, description=f"[cyan]Checking {check_name}[/cyan]")
                
                try:
                    result = check_func()
                    results[check_name] = result
                    status = "[green]✓[/green]" if result else "[red]✗[/red]"
                    progress.update(task, description=f"{status} {check_name}")
                except Exception:
                    results[check_name] = False
                    progress.update(task, description=f"[red]✗[/red] {check_name} (error)")
                
                time.sleep(0.2)  # Brief pause for visual feedback
                progress.advance(task)
        
        return results
    
    def show_backup_progress(
        self: Self,
        backup_type: str,
        files: list[str]
    ) -> None:
        """Show progress for backup operations.
        
        Args:
            backup_type: Type of backup being performed.
            files: List of files/directories being backed up.
        """
        with self.progress_bar(f"Creating {backup_type} backup") as progress:
            task = progress.add_task("Backup", total=len(files))
            
            for file_path in files:
                filename = file_path.split('/')[-1]
                progress.update(task, description=f"[cyan]Backing up {filename}[/cyan]")
                # Simulate backup time based on file type
                time.sleep(0.3)
                progress.advance(task)


class StatusDisplay:
    """Displays real-time status information."""
    
    def __init__(self: Self) -> None:
        """Initialize the status display."""
        self.console = console
    
    def show_service_status(
        self: Self,
        services: dict[str, dict[str, Any]]
    ) -> None:
        """Display service status in a formatted table.
        
        Args:
            services: Dictionary of service names to status information.
        """
        table = Table(title="WebOps Service Status")
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Uptime", justify="right")
        table.add_column("Memory", justify="right")
        table.add_column("CPU", justify="right")
        
        for service_name, status_info in services.items():
            status = status_info.get('status', 'unknown')
            uptime = status_info.get('uptime', 'N/A')
            memory = status_info.get('memory', 'N/A')
            cpu = status_info.get('cpu', 'N/A')
            
            # Color code the status
            if status == 'active':
                status_text = "[green]●[/green] Active"
            elif status == 'inactive':
                status_text = "[red]●[/red] Inactive"
            elif status == 'failed':
                status_text = "[red]✗[/red] Failed"
            else:
                status_text = "[yellow]?[/yellow] Unknown"
            
            table.add_row(service_name, status_text, uptime, memory, cpu)
        
        self.console.print(table)
    
    def show_deployment_status(
        self: Self,
        deployments: dict[str, dict[str, Any]]
    ) -> None:
        """Display deployment status in a formatted table.
        
        Args:
            deployments: Dictionary of deployment names to status information.
        """
        table = Table(title="WebOps Deployments")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Version", justify="center")
        table.add_column("URL", style="blue")
        table.add_column("Last Updated", justify="right")
        
        for deployment_name, info in deployments.items():
            status = info.get('status', 'unknown')
            version = info.get('version', 'N/A')
            url = info.get('url', 'N/A')
            updated = info.get('last_updated', 'N/A')
            
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
                status_text = "[yellow]?[/yellow] Unknown"
            
            table.add_row(deployment_name, status_text, version, url, updated)
        
        self.console.print(table)
    
    def show_system_metrics(
        self: Self,
        metrics: dict[str, Any]
    ) -> None:
        """Display system metrics in a formatted layout.
        
        Args:
            metrics: Dictionary of system metrics.
        """
        table = Table(title="System Metrics", show_header=False)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")
        
        # CPU Usage
        cpu_usage = metrics.get('cpu_percent', 0)
        cpu_status = self._get_usage_status(cpu_usage)
        table.add_row("CPU Usage", f"{cpu_usage:.1f}%", cpu_status)
        
        # Memory Usage
        memory_usage = metrics.get('memory_percent', 0)
        memory_status = self._get_usage_status(memory_usage)
        table.add_row("Memory Usage", f"{memory_usage:.1f}%", memory_status)
        
        # Disk Usage
        disk_usage = metrics.get('disk_percent', 0)
        disk_status = self._get_usage_status(disk_usage)
        table.add_row("Disk Usage", f"{disk_usage:.1f}%", disk_status)
        
        # Load Average
        load_avg = metrics.get('load_average', [0, 0, 0])
        load_status = self._get_load_status(load_avg[0])
        table.add_row("Load Average", f"{load_avg[0]:.2f}", load_status)
        
        # Active Connections
        connections = metrics.get('connections', 0)
        table.add_row("Active Connections", str(connections), "[blue]ℹ[/blue]")
        
        self.console.print(table)
    
    def _get_usage_status(self: Self, percentage: float) -> str:
        """Get status indicator for usage percentage.
        
        Args:
            percentage: Usage percentage (0-100).
            
        Returns:
            Colored status indicator.
        """
        if percentage < 70:
            return "[green]●[/green]"
        elif percentage < 85:
            return "[yellow]●[/yellow]"
        else:
            return "[red]●[/red]"
    
    def _get_load_status(self: Self, load: float) -> str:
        """Get status indicator for system load.
        
        Args:
            load: System load average.
            
        Returns:
            Colored status indicator.
        """
        if load < 1.0:
            return "[green]●[/green]"
        elif load < 2.0:
            return "[yellow]●[/yellow]"
        else:
            return "[red]●[/red]"


@contextmanager
def show_progress(
    message: str,
    spinner_style: str = "dots"
) -> Iterator[Status]:
    """Convenience function for showing progress with a spinner.
    
    Args:
        message: The message to display.
        spinner_style: The spinner style to use.
        
    Yields:
        Status object that can be updated.
    """
    progress_manager = ProgressManager()
    with progress_manager.spinner(message, spinner_style) as status:
        yield status


def show_step_progress(
    steps: list[str],
    step_function: Callable[[str], Any],
    description: str = "Processing"
) -> list[Any]:
    """Execute steps with progress indication.
    
    Args:
        steps: List of step descriptions.
        step_function: Function to execute for each step.
        description: Overall operation description.
        
    Returns:
        List of results from step execution.
    """
    results = []
    progress_manager = ProgressManager()
    
    with progress_manager.progress_bar(description) as progress:
        task = progress.add_task("Steps", total=len(steps))
        
        for step in steps:
            progress.update(task, description=f"[cyan]{step}[/cyan]")
            result = step_function(step)
            results.append(result)
            progress.advance(task)
    
    return results


def simulate_long_operation(
    operation_name: str,
    duration: float = 3.0,
    steps: Optional[list[str]] = None
) -> None:
    """Simulate a long-running operation for testing progress indicators.
    
    Args:
        operation_name: Name of the operation being simulated.
        duration: Total duration in seconds.
        steps: Optional list of step names to show.
    """
    if steps:
        step_duration = duration / len(steps)
        progress_manager = ProgressManager()
        
        with progress_manager.progress_bar(operation_name) as progress:
            task = progress.add_task("Operation", total=len(steps))
            
            for step in steps:
                progress.update(task, description=f"[cyan]{step}[/cyan]")
                time.sleep(step_duration)
                progress.advance(task)
    else:
        with show_progress(f"{operation_name}...") as status:
            time.sleep(duration)
            status.update(f"[green]✓[/green] {operation_name} completed")