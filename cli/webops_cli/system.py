"""System monitoring and information utilities for WebOps CLI."""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Self

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from .errors import ErrorHandler, handle_exception
from .progress import ProgressManager, StatusDisplay

console = Console()
error_handler = ErrorHandler()
progress_manager = ProgressManager()
status_display = StatusDisplay()


class SystemMonitor:
    """Monitors system health and performance for WebOps."""
    
    def __init__(self: Self) -> None:
        """Initialize the system monitor."""
        self.webops_dir: Path = Path("/opt/webops")
        self.control_panel_dir: Path = self.webops_dir / "control-panel"
        self.services: List[str] = [
            "webops-web",
            "webops-celery", 
            "webops-celerybeat"
        ]
    
    def check_service_status(self: Self, service_name: str) -> Dict[str, Any]:
        """Check the status of a systemd service.
        
        Args:
            service_name: Name of the systemd service to check.
            
        Returns:
            Dictionary containing service status information.
        """
        try:
            # Check if service is active
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                check=False
            )
            is_active = result.returncode == 0
            
            # Check if service is enabled
            result = subprocess.run(
                ["systemctl", "is-enabled", service_name],
                capture_output=True,
                text=True,
                check=False
            )
            is_enabled = result.returncode == 0
            
            # Get detailed status
            result = subprocess.run(
                ["systemctl", "status", service_name, "--no-pager", "-l"],
                capture_output=True,
                text=True,
                check=False
            )
            status_output = result.stdout
            
            return {
                "name": service_name,
                "active": is_active,
                "enabled": is_enabled,
                "status": "active" if is_active else "inactive",
                "details": status_output
            }
            
        except Exception as e:
            return {
                "name": service_name,
                "active": False,
                "enabled": False,
                "status": "error",
                "error": str(e)
            }
    
    def check_disk_usage(self: Self) -> Dict[str, Any]:
        """Check disk usage for WebOps directories.
        
        Returns:
            Dictionary containing disk usage information.
        """
        disk_info: Dict[str, Any] = {}
        
        try:
            # Overall system disk usage
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                disk_info["system"] = {
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_percent": parts[4]
                }
            
            # WebOps directory usage
            if self.webops_dir.exists():
                result = subprocess.run(
                    ["du", "-sh", str(self.webops_dir)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                disk_info["webops_total"] = result.stdout.split()[0]
                
                # Individual directory usage
                subdirs = ["control-panel", "deployments", "backups", "logs"]
                disk_info["subdirectories"] = {}
                
                for subdir in subdirs:
                    subdir_path = self.webops_dir / subdir
                    if subdir_path.exists():
                        try:
                            result = subprocess.run(
                                ["du", "-sh", str(subdir_path)],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            disk_info["subdirectories"][subdir] = result.stdout.split()[0]
                        except subprocess.CalledProcessError:
                            disk_info["subdirectories"][subdir] = "unknown"
            
        except subprocess.CalledProcessError as e:
            disk_info["error"] = str(e)
        
        return disk_info
    
    def check_database_connection(self: Self) -> Dict[str, Any]:
        """Check database connectivity and basic health.
        
        Returns:
            Dictionary containing database health information.
        """
        db_info: Dict[str, Any] = {}
        
        try:
            # Check if control panel directory exists (handle permission issues)
            if not self.control_panel_dir.exists():
                return {"error": "Control panel directory not found"}
        except PermissionError:
            # If we can't access the directory due to permissions, try the database check anyway
            # The subprocess will run as the webops user which should have access
            pass
        except Exception as e:
            return {"error": f"Error accessing control panel directory: {str(e)}"}
        
        try:
            # Run Django database check
            result = subprocess.run([
                "sudo", "-u", "webops", "bash", "-c",
                f"cd {self.control_panel_dir} && "
                "source venv/bin/activate && "
                "python manage.py check --database default"
            ], capture_output=True, text=True, check=False)
            
            db_info["django_check"] = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
            
            # Try to get database info
            if result.returncode == 0:
                result = subprocess.run([
                    "sudo", "-u", "webops", "bash", "-c",
                    f"cd {self.control_panel_dir} && "
                    "source venv/bin/activate && "
                    "python manage.py shell -c \"from django.db import connection; "
                    "print(f'Database: {connection.vendor}'); "
                    "print(f'Version: {connection.get_server_version()}'); "
                    "cursor = connection.cursor(); "
                    "cursor.execute('SELECT COUNT(*) FROM django_migrations'); "
                    "print(f'Migrations: {cursor.fetchone()[0]}');\""
                ], capture_output=True, text=True, check=False)
                
                if result.returncode == 0:
                    db_info["details"] = result.stdout.strip()
        
        except Exception as e:
            db_info["error"] = str(e)
        
        return db_info
    
    def check_celery_health(self: Self) -> Dict[str, Any]:
        """Check Celery worker and beat health.
        
        Returns:
            Dictionary containing Celery health information.
        """
        celery_info: Dict[str, Any] = {}
        
        try:
            # Check Celery worker status
            result = subprocess.run([
                "sudo", "-u", "webops", "bash", "-c",
                f"cd {self.control_panel_dir} && "
                "source venv/bin/activate && "
                "celery -A config inspect active"
            ], capture_output=True, text=True, check=False, timeout=10)
            
            celery_info["worker"] = {
                "responsive": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr
            }
            
            # Check Celery beat status (if running)
            result = subprocess.run([
                "sudo", "-u", "webops", "bash", "-c",
                f"cd {self.control_panel_dir} && "
                "source venv/bin/activate && "
                "celery -A config inspect scheduled"
            ], capture_output=True, text=True, check=False, timeout=10)
            
            celery_info["beat"] = {
                "responsive": result.returncode == 0,
                "output": result.stdout if result.returncode == 0 else result.stderr
            }
            
        except subprocess.TimeoutExpired:
            celery_info["error"] = "Celery commands timed out"
        except Exception as e:
            celery_info["error"] = str(e)
        
        return celery_info
    
    def get_system_load(self: Self) -> Dict[str, Any]:
        """Get system load and resource usage.
        
        Returns:
            Dictionary containing system load information.
        """
        load_info: Dict[str, Any] = {}
        
        try:
            # Load average
            with open("/proc/loadavg", "r") as f:
                load_data = f.read().strip().split()
                load_info["load_average"] = {
                    "1min": float(load_data[0]),
                    "5min": float(load_data[1]),
                    "15min": float(load_data[2])
                }
            
            # Memory usage
            result = subprocess.run(
                ["free", "-h"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                mem_line = lines[1].split()
                load_info["memory"] = {
                    "total": mem_line[1],
                    "used": mem_line[2],
                    "free": mem_line[3],
                    "available": mem_line[6] if len(mem_line) > 6 else mem_line[3]
                }
            
            # CPU usage (simple check)
            result = subprocess.run(
                ["top", "-bn1"],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split('\n'):
                if '%Cpu(s):' in line:
                    load_info["cpu"] = line.strip()
                    break
        
        except Exception as e:
            load_info["error"] = str(e)
        
        return load_info
    
    def _evaluate_database_health(self: Self) -> bool:
        """Evaluate database health and return boolean result.
        
        Returns:
            True if database is healthy, False otherwise.
        """
        try:
            db_result = self.check_database_connection()
            
            # Check if there's an error
            if "error" in db_result:
                return False
            
            # Check Django database check result
            django_check = db_result.get("django_check", {})
            if not django_check.get("success", False):
                return False
            
            return True
        except Exception:
            return False
    
    def _evaluate_services_health(self: Self) -> bool:
        """Evaluate all WebOps services health and return boolean result.
        
        Returns:
            True if all services are healthy, False otherwise.
        """
        try:
            for service_name in self.services:
                service_result = self.check_service_status(service_name)
                if not service_result.get("active", False):
                    return False
            return True
        except Exception:
            return False
    
    def _evaluate_celery_health(self: Self) -> bool:
        """Evaluate Celery health and return boolean result.
        
        Returns:
            True if Celery is healthy, False otherwise.
        """
        try:
            celery_result = self.check_celery_health()
            
            # Check if there's an error
            if "error" in celery_result:
                return False
            
            # Check worker responsiveness
            worker_status = celery_result.get("worker", {})
            if not worker_status.get("responsive", False):
                return False
            
            return True
        except Exception:
            return False
    
    def _evaluate_disk_health(self: Self) -> bool:
        """Evaluate disk usage health and return boolean result.
        
        Returns:
            True if disk usage is healthy, False otherwise.
        """
        try:
            disk_result = self.check_disk_usage()
            
            # Check system disk usage (primary concern)
            system_disk = disk_result.get("system", {})
            if not system_disk:
                return False
                
            usage_str = system_disk.get("usage_percent", "0%")
            usage_percent = float(usage_str.rstrip('%'))
            
            # Consider disk unhealthy if usage > 90%
            if usage_percent > 90:
                return False
            
            # System disk usage is healthy - don't fail due to WebOps directory permission issues
            return True
        except Exception:
            return False
    
    def _evaluate_system_load_health(self: Self) -> bool:
        """Evaluate system load health and return boolean result.
        
        Returns:
            True if system load is healthy, False otherwise.
        """
        try:
            load_result = self.get_system_load()
            
            # Check if there's an error
            if "error" in load_result:
                return False
            
            # Check load average (consider unhealthy if 1-min load > 4.0)
            load_avg = load_result.get("load_average", {})
            one_min_load = load_avg.get("1min", 0.0)
            
            if one_min_load > 4.0:
                return False
            
            return True
        except Exception:
            return False

    def run_comprehensive_health_check(self: Self) -> Dict[str, Any]:
        """Run a comprehensive health check of all system components.
        
        Returns:
            Dictionary containing health check results with detailed information.
        """
        checks = {
            "Database": self._evaluate_database_health,
            "Celery": self._evaluate_celery_health,
            "Services": self._evaluate_services_health,
            "Disk Space": self._evaluate_disk_health,
            "System Load": self._evaluate_system_load_health
        }
        
        try:
            results = progress_manager.show_health_check_progress(checks)
            
            # Get detailed information for each check
            detailed_results = {}
            for check_name, passed in results.items():
                detailed_results[check_name] = {
                    "passed": passed,
                    "details": self._get_check_details(check_name)
                }
            
            # Calculate overall health score
            passed_checks = sum(1 for result in results.values() if result)
            total_checks = len(results)
            health_score = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
            
            return {
                "checks": detailed_results,
                "health_score": health_score,
                "status": "healthy" if health_score >= 80 else "warning" if health_score >= 60 else "critical",
                "timestamp": time.time()
            }
        except Exception as e:
            error_handler.display_error(e, "Failed to run comprehensive health check")
            return {
                "checks": {},
                "health_score": 0,
                "status": "error",
                "timestamp": time.time()
            }
    
    def _get_check_details(self: Self, check_name: str) -> str:
        """Get detailed information for a specific health check.
        
        Args:
            check_name: Name of the health check.
            
        Returns:
            Detailed information string for the check.
        """
        try:
            if check_name == "Database":
                db_result = self.check_database_connection()
                if db_result.get("connection_successful"):
                    return f"Connected to {db_result.get('database_name', 'database')}"
                else:
                    return f"Connection failed: {db_result.get('error', 'Unknown error')}"
                    
            elif check_name == "Celery":
                celery_result = self.check_celery_health()
                worker_status = celery_result.get("worker", {})
                if worker_status.get("responsive"):
                    return "Worker responsive"
                else:
                    return f"Worker issues: {celery_result.get('error', 'Not responsive')}"
                    
            elif check_name == "Services":
                failed_services = []
                for service_name in self.services:
                    service_result = self.check_service_status(service_name)
                    if not service_result.get("active", False):
                        failed_services.append(service_name)
                
                if not failed_services:
                    return f"All {len(self.services)} services running"
                else:
                    return f"Failed: {', '.join(failed_services)}"
                    
            elif check_name == "Disk Space":
                disk_result = self.check_disk_usage()
                system_disk = disk_result.get("system", {})
                usage_percent = system_disk.get("usage_percent", "0%")
                available = system_disk.get("available", "Unknown")
                return f"{usage_percent} used, {available} available"
                
            elif check_name == "System Load":
                load_result = self.get_system_load()
                load_avg = load_result.get("load_average", {})
                one_min = load_avg.get("1min", 0.0)
                return f"Load: {one_min:.2f}"
                
            return "No details available"
            
        except Exception as e:
            return f"Error getting details: {str(e)}"


@click.group()
def system() -> None:
    """System monitoring and health check commands."""
    pass


@system.command()
def health() -> None:
    """Run comprehensive health check of WebOps components."""
    try:
        monitor = SystemMonitor()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running health checks...", total=None)
            health_results = monitor.run_comprehensive_health_check()
            progress.update(task, completed=True)
        
        # Display results
        console.print(Panel.fit(
            f"[bold blue]WebOps Health Check - {datetime.fromtimestamp(health_results['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}[/bold blue]",
            border_style="blue"
        ))
        
        # Overall status
        status_color = {
            "healthy": "green",
            "warning": "yellow", 
            "critical": "red",
            "error": "red"
        }.get(health_results["status"], "yellow")
        
        console.print(f"\n[bold]Overall Status:[/bold] [{status_color}]{health_results['status'].upper()}[/{status_color}]")
        console.print(f"[bold]Health Score:[/bold] {health_results['health_score']:.1f}%")
        
        # Display individual check results
        table = Table(title="Health Check Results")
        table.add_column("Check", style="cyan", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Details")
        
        for check_name, check_data in health_results["checks"].items():
            passed = check_data.get("passed", False)
            details = check_data.get("details", "")
            
            status_icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
            status_text = "Pass" if passed else "Fail"
            table.add_row(check_name, f"{status_icon} {status_text}", details)
        
        console.print(table)
        
        # Show recommendations if there are issues
        if health_results["health_score"] < 100:
            console.print("\n[bold yellow]Recommendations:[/bold yellow]")
            failed_checks = [name for name, check_data in health_results["checks"].items() 
                           if not check_data.get("passed", False)]
            for check in failed_checks:
                console.print(f"• Investigate {check} issues")
                console.print(f"  Run: [cyan]webops system {check.lower().replace(' ', '-')}[/cyan]")
        
    except Exception as e:
        handle_exception(e, "Failed to run health check")


@system.command()
def monitor() -> None:
    """Real-time system monitoring dashboard."""
    monitor = SystemMonitor()
    
    def generate_monitor_display() -> Panel:
        """Generate the monitoring display panel."""
        # Get current system load
        load_info = monitor.get_system_load()
        
        # Create content
        content = []
        
        # System load
        if "load_average" in load_info:
            load = load_info["load_average"]
            content.append(f"[bold]Load Average:[/bold] {load['1min']:.2f}, {load['5min']:.2f}, {load['15min']:.2f}")
        
        # Memory usage
        if "memory" in load_info:
            mem = load_info["memory"]
            content.append(f"[bold]Memory:[/bold] {mem['used']}/{mem['total']} (Available: {mem['available']})")
        
        # CPU usage
        if "cpu" in load_info:
            content.append(f"[bold]CPU:[/bold] {load_info['cpu']}")
        
        # Service status
        content.append("\n[bold]Services:[/bold]")
        for service in monitor.services:
            service_status = monitor.check_service_status(service)
            status_text = "[green]Active[/green]" if service_status.get("active") else "[red]Inactive[/red]"
            content.append(f"  {service}: {status_text}")
        
        # Timestamp
        content.append(f"\n[dim]Last updated: {datetime.now().strftime('%H:%M:%S')}[/dim]")
        content.append("[dim]Press Ctrl+C to exit[/dim]")
        
        return Panel(
            "\n".join(content),
            title="[bold blue]WebOps System Monitor[/bold blue]",
            border_style="blue"
        )
    
    try:
        with Live(generate_monitor_display(), refresh_per_second=1, console=console) as live:
            while True:
                time.sleep(2)  # Update every 2 seconds
                live.update(generate_monitor_display())
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")


@system.command()
def services() -> None:
    """Check status of all WebOps services."""
    monitor = SystemMonitor()
    
    console.print(Panel.fit(
        "[bold blue]WebOps Services Status[/bold blue]",
        border_style="blue"
    ))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Enabled", style="white")
    table.add_column("Details", style="dim")
    
    for service in monitor.services:
        service_data = monitor.check_service_status(service)
        
        # Status column
        if service_data.get("active"):
            status_text = Text("Active", style="green")
        else:
            status_text = Text("Inactive", style="red")
        
        # Enabled column
        enabled_text = Text("Yes", style="green") if service_data.get("enabled") else Text("No", style="yellow")
        
        # Details column
        details = "Running normally" if service_data.get("active") else "Not running"
        if "error" in service_data:
            details = f"Error: {service_data['error']}"
        
        table.add_row(
            service,
            status_text,
            enabled_text,
            details
        )
    
    console.print(table)


@system.command()
def disk() -> None:
    """Show disk usage information for WebOps directories."""
    monitor = SystemMonitor()
    
    console.print(Panel.fit(
        "[bold blue]WebOps Disk Usage[/bold blue]",
        border_style="blue"
    ))
    
    disk_info = monitor.check_disk_usage()
    
    # System disk usage
    if "system" in disk_info:
        console.print("\n[bold]System Disk Usage:[/bold]")
        sys_disk = disk_info["system"]
        
        # Parse usage percentage for color coding
        usage_str = sys_disk["usage_percent"]
        usage_pct = int(usage_str.rstrip('%'))
        
        if usage_pct > 90:
            usage_color = "red"
        elif usage_pct > 75:
            usage_color = "yellow"
        else:
            usage_color = "green"
        
        console.print(f"  Total: {sys_disk['total']}")
        console.print(f"  Used: {sys_disk['used']} ([{usage_color}]{usage_str}[/{usage_color}])")
        console.print(f"  Available: {sys_disk['available']}")
    
    # WebOps directory usage
    if "webops_total" in disk_info:
        console.print(f"\n[bold]WebOps Total:[/bold] {disk_info['webops_total']}")
    
    # Subdirectory usage
    if "subdirectories" in disk_info:
        console.print("\n[bold]WebOps Subdirectories:[/bold]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Directory", style="cyan")
        table.add_column("Size", style="green")
        
        for subdir, size in disk_info["subdirectories"].items():
            table.add_row(subdir, size)
        
        console.print(table)


@system.command()
@click.option('--output', '-o', type=click.Path(), help='Save health check results to JSON file')
def doctor(output: Optional[str] = None) -> None:
    """Run automated diagnostics and provide recommendations.
    
    Args:
        output: Optional file path to save detailed results as JSON.
    """
    monitor = SystemMonitor()
    
    console.print(Panel.fit(
        "[bold blue]WebOps Doctor - Automated Diagnostics[/bold blue]",
        border_style="blue"
    ))
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running diagnostics...", total=None)
        health_data = monitor.run_comprehensive_health_check()
        progress.update(task, completed=True)
    
    # Analyze results and provide recommendations
    recommendations: List[str] = []
    
    # Check individual components for recommendations
    checks = health_data.get("checks", {})
    
    # Database recommendations
    if "Database" in checks and not checks["Database"].get("passed", False):
        recommendations.append("Database connection failed. Check database service and configuration.")
        recommendations.append("Try: sudo webops admin run 'cd /opt/webops/control-panel && python manage.py check --database default'")
    
    # Celery recommendations
    if "Celery" in checks and not checks["Celery"].get("passed", False):
        recommendations.append("Celery worker is not responsive. Restart the celery service.")
        recommendations.append("Try: sudo systemctl restart webops-celery")
    
    # Services recommendations
    if "Services" in checks and not checks["Services"].get("passed", False):
        recommendations.append("One or more WebOps services are not running.")
        recommendations.append("Check service status: sudo systemctl status webops-web webops-celery webops-celerybeat")
        recommendations.append("Start services: sudo systemctl start webops-web webops-celery webops-celerybeat")
    
    # Disk space recommendations
    if "Disk Space" in checks and not checks["Disk Space"].get("passed", False):
        recommendations.append("Disk space is running low.")
        recommendations.append("Check disk usage: df -h")
        recommendations.append("Clean up old files or expand storage.")
    
    # System load recommendations
    if "System Load" in checks and not checks["System Load"].get("passed", False):
        recommendations.append("System load is high. This may affect performance.")
        recommendations.append("Check running processes: top or htop")
        recommendations.append("Consider reducing system load or upgrading hardware.")
    
    # Display results
    status = health_data.get("status", "unknown")
    health_score = health_data.get("health_score", 0)
    
    if status == "healthy":
        console.print(f"\n[bold green]✓ System is healthy! (Score: {health_score}%)[/bold green]")
        if health_score == 100:
            console.print("Perfect! All components are functioning optimally.")
        else:
            console.print("System is operational with minor issues.")
    else:
        console.print(f"\n[bold yellow]⚠ Issues detected (Score: {health_score}%)[/bold yellow]")
        
        # Show failed checks
        failed_checks = [name for name, data in checks.items() if not data.get("passed", False)]
        if failed_checks:
            console.print(f"\n[bold red]Failed checks:[/bold red] {', '.join(failed_checks)}")
        
        if recommendations:
            console.print("\n[bold blue]Recommended actions:[/bold blue]")
            for i, rec in enumerate(recommendations, 1):
                console.print(f"  {i}. {rec}")
    
    # Show detailed check results
    console.print(f"\n[bold]Detailed Check Results:[/bold]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Details", style="dim")
    
    for check_name, check_data in checks.items():
        status_text = Text("Pass", style="green") if check_data.get("passed", False) else Text("Fail", style="red")
        details = check_data.get("details", "No details available")
        
        table.add_row(check_name, status_text, details)
    
    console.print(table)
    
    # Save detailed results if requested
    if output:
        output_path = Path(output)
        try:
            with open(output_path, 'w') as f:
                json.dump(health_data, f, indent=2)
            console.print(f"\n[green]Detailed results saved to: {output_path}[/green]")
        except Exception as e:
            console.print(f"\n[red]Failed to save results: {e}[/red]")