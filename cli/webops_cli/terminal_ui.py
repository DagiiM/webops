"""Terminal UI components for WebOps CLI.

This module provides enhanced terminal UI components for better user experience,
including interactive menus, status displays, and visual feedback.
"""

from typing import Any, Dict, List, Optional, Self, Tuple
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.align import Align

console = Console()


class TerminalUI:
    """Enhanced terminal UI components for WebOps CLI."""
    
    def __init__(self: Self) -> None:
        """Initialize terminal UI components."""
        self.console = console
    
    def create_status_dashboard(
        self: Self, 
        system_info: Dict[str, Any],
        deployments: List[Dict[str, Any]],
        services: List[Dict[str, Any]]
    ) -> Layout:
        """Create a comprehensive status dashboard.
        
        Args:
            system_info: System information dictionary.
            deployments: List of deployment information.
            services: List of service information.
            
        Returns:
            Rich Layout object for the dashboard.
        """
        layout = Layout()
        
        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body")
        )
        
        # Header with title and timestamp
        header_text = Text("WebOps System Dashboard", style="bold cyan")
        timestamp = Text(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        layout["header"].update(
            Panel(
                Align.center(f"{header_text}\n{timestamp}"),
                border_style="cyan"
            )
        )
        
        # Body split into three columns
        layout["body"].split_row(
            Layout(name="system", ratio=1),
            Layout(name="deployments", ratio=2),
            Layout(name="services", ratio=1)
        )
        
        # System information panel
        layout["system"].update(self._create_system_panel(system_info))
        
        # Deployments panel
        layout["deployments"].update(self._create_deployments_panel(deployments))
        
        # Services panel
        layout["services"].update(self._create_services_panel(services))
        
        return layout
    
    def _create_system_panel(self: Self, system_info: Dict[str, Any]) -> Panel:
        """Create system information panel.
        
        Args:
            system_info: System information dictionary.
            
        Returns:
            Rich Panel with system information.
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        # Add system metrics
        cpu_usage = system_info.get('cpu_usage', 0)
        memory_usage = system_info.get('memory_usage', 0)
        disk_usage = system_info.get('disk_usage', 0)
        
        table.add_row("CPU Usage", f"{cpu_usage:.1f}%")
        table.add_row("Memory Usage", f"{memory_usage:.1f}%")
        table.add_row("Disk Usage", f"{disk_usage:.1f}%")
        table.add_row("Uptime", system_info.get('uptime', 'N/A'))
        table.add_row("Load Average", system_info.get('load_avg', 'N/A'))
        
        return Panel(
            table,
            title="System Status",
            border_style="green" if cpu_usage < 80 and memory_usage < 80 else "yellow"
        )
    
    def _create_deployments_panel(self: Self, deployments: List[Dict[str, Any]]) -> Panel:
        """Create deployments status panel.
        
        Args:
            deployments: List of deployment information.
            
        Returns:
            Rich Panel with deployments information.
        """
        if not deployments:
            return Panel(
                Align.center("[dim]No deployments found[/dim]"),
                title="Deployments",
                border_style="blue"
            )
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Domain", style="blue")
        table.add_column("Health", justify="center")
        
        for deployment in deployments[:10]:  # Limit to 10 for display
            status = deployment.get('status', 'unknown')
            health = deployment.get('health', 'unknown')
            
            status_style = self._get_status_color(status)
            health_style = self._get_health_color(health)
            
            table.add_row(
                deployment.get('name', 'N/A'),
                f"[{status_style}]{status}[/{status_style}]",
                deployment.get('domain', 'N/A'),
                f"[{health_style}]{health}[/{health_style}]"
            )
        
        return Panel(
            table,
            title=f"Deployments ({len(deployments)})",
            border_style="blue"
        )
    
    def _create_services_panel(self: Self, services: List[Dict[str, Any]]) -> Panel:
        """Create services status panel.
        
        Args:
            services: List of service information.
            
        Returns:
            Rich Panel with services information.
        """
        tree = Tree("Services")
        
        for service in services:
            name = service.get('name', 'Unknown')
            status = service.get('status', 'unknown')
            style = self._get_status_color(status)
            
            service_node = tree.add(f"[{style}]{name}[/{style}]")
            service_node.add(f"Status: [{style}]{status}[/{style}]")
            
            if 'pid' in service:
                service_node.add(f"PID: {service['pid']}")
            if 'memory' in service:
                service_node.add(f"Memory: {service['memory']}")
        
        return Panel(
            tree,
            title="Services",
            border_style="green"
        )
    
    def _get_status_color(self: Self, status: str) -> str:
        """Get color for status display.
        
        Args:
            status: Status string.
            
        Returns:
            Rich color string.
        """
        status_colors = {
            'running': 'green',
            'active': 'green',
            'stopped': 'red',
            'inactive': 'red',
            'failed': 'bold red',
            'building': 'yellow',
            'pending': 'blue',
            'unknown': 'dim'
        }
        return status_colors.get(status.lower(), 'white')
    
    def _get_health_color(self: Self, health: str) -> str:
        """Get color for health display.
        
        Args:
            health: Health status string.
            
        Returns:
            Rich color string.
        """
        health_colors = {
            'healthy': 'green',
            'unhealthy': 'red',
            'degraded': 'yellow',
            'unknown': 'dim'
        }
        return health_colors.get(health.lower(), 'white')
    
    def create_interactive_menu(
        self: Self,
        title: str,
        options: List[Tuple[str, str]],
        description: Optional[str] = None
    ) -> Panel:
        """Create an interactive menu display.
        
        Args:
            title: Menu title.
            options: List of (key, description) tuples.
            description: Optional menu description.
            
        Returns:
            Rich Panel with menu options.
        """
        content = []
        
        if description:
            content.append(Text(description, style="dim"))
            content.append("")
        
        for key, desc in options:
            content.append(f"[cyan]{key}[/cyan] - {desc}")
        
        content.append("")
        content.append("[dim]Press the corresponding key to select an option[/dim]")
        
        return Panel(
            "\n".join(str(item) for item in content),
            title=title,
            border_style="cyan"
        )
    
    def display_progress_with_steps(
        self: Self,
        steps: List[str],
        current_step: int = 0
    ) -> Panel:
        """Display progress with step indicators.
        
        Args:
            steps: List of step descriptions.
            current_step: Current step index (0-based).
            
        Returns:
            Rich Panel with progress steps.
        """
        content = []
        
        for i, step in enumerate(steps):
            if i < current_step:
                # Completed step
                content.append(f"[green]✓[/green] {step}")
            elif i == current_step:
                # Current step
                content.append(f"[yellow]▶[/yellow] {step}")
            else:
                # Future step
                content.append(f"[dim]○[/dim] {step}")
        
        return Panel(
            "\n".join(content),
            title=f"Progress ({current_step + 1}/{len(steps)})",
            border_style="blue"
        )
    
    def create_log_viewer(
        self: Self,
        logs: List[str],
        title: str = "Logs",
        max_lines: int = 20
    ) -> Panel:
        """Create a log viewer panel.
        
        Args:
            logs: List of log lines.
            title: Panel title.
            max_lines: Maximum number of lines to display.
            
        Returns:
            Rich Panel with formatted logs.
        """
        if not logs:
            return Panel(
                Align.center("[dim]No logs available[/dim]"),
                title=title,
                border_style="blue"
            )
        
        # Take the last max_lines
        display_logs = logs[-max_lines:] if len(logs) > max_lines else logs
        
        formatted_logs = []
        for log_line in display_logs:
            # Basic log level formatting
            if 'ERROR' in log_line or 'CRITICAL' in log_line:
                formatted_logs.append(f"[red]{log_line}[/red]")
            elif 'WARNING' in log_line or 'WARN' in log_line:
                formatted_logs.append(f"[yellow]{log_line}[/yellow]")
            elif 'INFO' in log_line:
                formatted_logs.append(f"[blue]{log_line}[/blue]")
            elif 'DEBUG' in log_line:
                formatted_logs.append(f"[dim]{log_line}[/dim]")
            else:
                formatted_logs.append(log_line)
        
        return Panel(
            "\n".join(formatted_logs),
            title=f"{title} (showing last {len(display_logs)} lines)",
            border_style="blue"
        )