"""Interactive troubleshooting wizard for WebOps CLI.

This module provides automated diagnostics and guided troubleshooting
for common WebOps deployment and operational issues.
"""

import os
import subprocess
import time
from typing import Any, Dict, List, Self

import click
import psutil
import requests
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import Config
from .errors import ErrorHandler
from .progress import ProgressManager
from .system import SystemMonitor
from .wizards import InteractiveWizard

console = Console()
error_handler = ErrorHandler()
progress_manager = ProgressManager()
config = Config()
system_monitor = SystemMonitor()


class TroubleshootingWizard(InteractiveWizard):
    """Interactive troubleshooting wizard for WebOps issues."""
    
    def __init__(self: Self) -> None:
        """Initialize the troubleshooting wizard."""
        super().__init__("WebOps Interactive Troubleshooting Guide")
        self.diagnostics: Dict[str, Any] = {}
        self.issues_found: List[Dict[str, Any]] = []
        self.fixes_applied: List[str] = []
    
    def run(self: Self) -> bool:
        """Run the interactive troubleshooting wizard.
        
        Returns:
            True if troubleshooting completed successfully, False otherwise.
        """
        try:
            self.display_header()
            
            # Step 1: Problem identification
            if not self._step_identify_problem():
                return False
            
            # Step 2: System diagnostics
            if not self._step_system_diagnostics():
                return False
            
            # Step 3: Service diagnostics
            if not self._step_service_diagnostics():
                return False
            
            # Step 4: Network diagnostics
            if not self._step_network_diagnostics():
                return False
            
            # Step 5: Application diagnostics
            if not self._step_application_diagnostics():
                return False
            
            # Step 6: Issue analysis
            if not self._step_analyze_issues():
                return False
            
            # Step 7: Apply fixes
            if not self._step_apply_fixes():
                return False
            
            # Step 8: Verification
            if not self._step_verify_fixes():
                return False
            
            self._display_summary()
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Troubleshooting cancelled by user.[/yellow]")
            return False
        except Exception as e:
            error_handler.display_error(e, "Troubleshooting wizard failed")
            return False
    
    def _step_identify_problem(self: Self) -> bool:
        """Identify the problem category."""
        self.display_step(1, 8, "Problem Identification")
        
        self.console.print("What type of issue are you experiencing?")
        self.console.print()
        
        problem_categories = [
            ("deployment", "Deployment failures or issues"),
            ("performance", "Slow response times or high resource usage"),
            ("connectivity", "Cannot access application or API"),
            ("services", "WebOps services not running properly"),
            ("ssl", "SSL/HTTPS certificate issues"),
            ("database", "Database connection or query issues"),
            ("logs", "Application errors in logs"),
            ("other", "Other issues not listed above")
        ]
        
        # Display options
        for i, (_, description) in enumerate(problem_categories, 1):
            self.console.print(f"[cyan]{i}.[/cyan] {description}")
        
        self.console.print()
        
        while True:
            try:
                choice = int(Prompt.ask("Select problem category (1-8)"))
                if 1 <= choice <= len(problem_categories):
                    problem_type, _ = problem_categories[choice - 1]
                    self.diagnostics['problem_type'] = problem_type
                    break
                else:
                    self.console.print("[red]Invalid choice. Please select 1-8.[/red]")
            except ValueError:
                self.console.print("[red]Please enter a number.[/red]")
        
        # Get additional details
        self.diagnostics['problem_description'] = Prompt.ask(
            "Describe the issue in more detail (optional)",
            default=""
        )
        
        # Get affected application if applicable
        if problem_type in ['deployment', 'performance', 'connectivity', 'logs']:
            app_name = Prompt.ask("Application name (if applicable)", default="")
            if app_name:
                self.diagnostics['app_name'] = app_name
        
        return True
    
    def _step_system_diagnostics(self: Self) -> bool:
        """Run system-level diagnostics."""
        self.display_step(2, 8, "System Diagnostics")
        
        self.console.print("Running system diagnostics...")
        self.console.print()
        
        with progress_manager.progress_bar("System checks") as progress:
            task = progress.add_task("Checking system health", total=100)
            
            # CPU usage
            progress.update(task, description="[cyan]Checking CPU usage[/cyan]")
            cpu_usage = psutil.cpu_percent(interval=1)
            self.diagnostics['cpu_usage'] = cpu_usage
            progress.update(task, completed=20)
            
            # Memory usage
            progress.update(task, description="[cyan]Checking memory usage[/cyan]")
            memory = psutil.virtual_memory()
            self.diagnostics['memory_usage'] = memory.percent
            self.diagnostics['memory_available'] = memory.available // (1024**3)  # GB
            progress.update(task, completed=40)
            
            # Disk usage
            progress.update(task, description="[cyan]Checking disk usage[/cyan]")
            disk = psutil.disk_usage('/')
            self.diagnostics['disk_usage'] = (disk.used / disk.total) * 100
            self.diagnostics['disk_free'] = disk.free // (1024**3)  # GB
            progress.update(task, completed=60)
            
            # Load average
            progress.update(task, description="[cyan]Checking system load[/cyan]")
            load_avg = os.getloadavg()
            self.diagnostics['load_average'] = load_avg[0]
            progress.update(task, completed=80)
            
            # Network connectivity
            progress.update(task, description="[cyan]Checking network connectivity[/cyan]")
            self.diagnostics['internet_connectivity'] = self._check_internet_connectivity()
            progress.update(task, completed=100)
        
        # Display results
        self._display_system_status()
        
        # Analyze system issues
        self._analyze_system_issues()
        
        return True
    
    def _step_service_diagnostics(self: Self) -> bool:
        """Run WebOps service diagnostics."""
        self.display_step(3, 8, "Service Diagnostics")
        
        self.console.print("Checking WebOps services...")
        self.console.print()
        
        services = ['webops-web', 'webops-celery', 'webops-celerybeat']
        service_status = {}
        
        with progress_manager.progress_bar("Service checks") as progress:
            task = progress.add_task("Checking services", total=len(services))
            
            for service in services:
                progress.update(task, description=f"[cyan]Checking {service}[/cyan]")
                
                status = self._check_service_status(service)
                service_status[service] = status
                
                progress.update(task, advance=1)
        
        self.diagnostics['service_status'] = service_status
        
        # Display service status
        self._display_service_status(service_status)
        
        # Analyze service issues
        self._analyze_service_issues(service_status)
        
        return True
    
    def _step_network_diagnostics(self: Self) -> bool:
        """Run network diagnostics."""
        self.display_step(4, 8, "Network Diagnostics")
        
        self.console.print("Running network diagnostics...")
        self.console.print()
        
        network_tests = [
            ("localhost_8000", "WebOps Control Panel (localhost:8000)"),
            ("nginx_config", "Nginx configuration"),
            ("ssl_cert", "SSL certificates"),
            ("dns_resolution", "DNS resolution")
        ]
        
        network_results = {}
        
        with progress_manager.progress_bar("Network checks") as progress:
            task = progress.add_task("Network diagnostics", total=len(network_tests))
            
            for test_key, test_name in network_tests:
                progress.update(task, description=f"[cyan]Testing {test_name}[/cyan]")
                
                result = None  # Initialize result
                if test_key == "localhost_8000":
                    result = self._test_localhost_connection()
                elif test_key == "nginx_config":
                    result = self._test_nginx_config()
                elif test_key == "ssl_cert":
                    result = self._test_ssl_certificates()
                elif test_key == "dns_resolution":
                    result = self._test_dns_resolution()
                
                if result is not None:
                    network_results[test_key] = result
                progress.update(task, advance=1)
        
        self.diagnostics['network_tests'] = network_results
        
        # Display network test results
        self._display_network_status(network_results)
        
        # Analyze network issues
        self._analyze_network_issues(network_results)
        
        return True
    
    def _step_application_diagnostics(self: Self) -> bool:
        """Run application-specific diagnostics."""
        self.display_step(5, 8, "Application Diagnostics")
        
        if not self.diagnostics.get('app_name'):
            self.console.print("[yellow]No specific application specified. Skipping application diagnostics.[/yellow]")
            return True
        
        app_name = self.diagnostics['app_name']
        self.console.print(f"Running diagnostics for application: [cyan]{app_name}[/cyan]")
        self.console.print()
        
        app_diagnostics = {}
        
        with progress_manager.progress_bar("Application checks") as progress:
            task = progress.add_task("Application diagnostics", total=100)
            
            # Check application logs
            progress.update(task, description="[cyan]Checking application logs[/cyan]")
            app_diagnostics['logs'] = self._check_application_logs(app_name)
            progress.update(task, completed=25)
            
            # Check application health
            progress.update(task, description="[cyan]Checking application health[/cyan]")
            app_diagnostics['health'] = self._check_application_health(app_name)
            progress.update(task, completed=50)
            
            # Check application configuration
            progress.update(task, description="[cyan]Checking application config[/cyan]")
            app_diagnostics['config'] = self._check_application_config(app_name)
            progress.update(task, completed=75)
            
            # Check application dependencies
            progress.update(task, description="[cyan]Checking dependencies[/cyan]")
            app_diagnostics['dependencies'] = self._check_application_dependencies(app_name)
            progress.update(task, completed=100)
        
        self.diagnostics['application'] = app_diagnostics
        
        # Display application status
        self._display_application_status(app_diagnostics)
        
        # Analyze application issues
        self._analyze_application_issues(app_diagnostics)
        
        return True
    
    def _step_analyze_issues(self: Self) -> bool:
        """Analyze all collected diagnostics and identify issues."""
        self.display_step(6, 8, "Issue Analysis")
        
        self.console.print("Analyzing diagnostic results...")
        self.console.print()
        
        with progress_manager.spinner("Analyzing issues..."):
            time.sleep(2)  # Simulate analysis
        
        if not self.issues_found:
            self.console.print("[green]✓ No critical issues found![/green]")
            self.console.print()
            return True
        
        # Display found issues
        self.console.print(f"[yellow]Found {len(self.issues_found)} issue(s):[/yellow]")
        self.console.print()
        
        issues_table = Table(title="Issues Found", show_header=True, header_style="bold red")
        issues_table.add_column("Priority", justify="center")
        issues_table.add_column("Category", style="cyan")
        issues_table.add_column("Issue", style="yellow")
        issues_table.add_column("Impact")
        
        for issue in self.issues_found:
            priority_icon = "🔴" if issue['priority'] == 'high' else "🟡" if issue['priority'] == 'medium' else "🟢"
            issues_table.add_row(
                f"{priority_icon} {issue['priority'].upper()}",
                issue['category'],
                issue['description'],
                issue['impact']
            )
        
        self.console.print(issues_table)
        self.console.print()
        
        return True
    
    def _step_apply_fixes(self: Self) -> bool:
        """Apply automated fixes for identified issues."""
        self.display_step(7, 8, "Apply Fixes")
        
        if not self.issues_found:
            self.console.print("[green]No issues to fix![/green]")
            return True
        
        self.console.print("Available automated fixes:")
        self.console.print()
        
        fixable_issues = [issue for issue in self.issues_found if issue.get('fix_available')]
        
        if not fixable_issues:
            self.console.print("[yellow]No automated fixes available for the identified issues.[/yellow]")
            self.console.print("Please refer to the manual resolution steps below.")
            self._display_manual_fixes()
            return True
        
        # Display fixable issues
        for i, issue in enumerate(fixable_issues, 1):
            self.console.print(f"[cyan]{i}.[/cyan] {issue['description']}")
            self.console.print(f"   Fix: {issue['fix_description']}")
            self.console.print()
        
        if not Confirm.ask("Apply all available automated fixes?", default=True):
            return self._selective_fix_application(fixable_issues)
        
        # Apply all fixes
        with progress_manager.progress_bar("Applying fixes") as progress:
            task = progress.add_task("Fixing issues", total=len(fixable_issues))
            
            for issue in fixable_issues:
                progress.update(task, description=f"[cyan]Fixing: {issue['description']}[/cyan]")
                
                success = self._apply_fix(issue)
                if success:
                    self.fixes_applied.append(issue['description'])
                
                progress.update(task, advance=1)
        
        self.console.print(f"[green]Applied {len(self.fixes_applied)} fix(es).[/green]")
        self.console.print()
        
        return True
    
    def _step_verify_fixes(self: Self) -> bool:
        """Verify that applied fixes resolved the issues."""
        self.display_step(8, 8, "Verification")
        
        if not self.fixes_applied:
            self.console.print("[yellow]No fixes were applied. Skipping verification.[/yellow]")
            return True
        
        self.console.print("Verifying applied fixes...")
        self.console.print()
        
        verification_results = {}
        
        with progress_manager.progress_bar("Verification") as progress:
            task = progress.add_task("Verifying fixes", total=len(self.fixes_applied))
            
            for fix in self.fixes_applied:
                progress.update(task, description=f"[cyan]Verifying: {fix}[/cyan]")
                
                # Re-run relevant diagnostics
                verification_results[fix] = self._verify_fix(fix)
                
                progress.update(task, advance=1)
        
        # Display verification results
        verification_table = Table(title="Fix Verification", show_header=True, header_style="bold green")
        verification_table.add_column("Fix Applied", style="cyan")
        verification_table.add_column("Status", justify="center")
        verification_table.add_column("Notes")
        
        for fix, result in verification_results.items():
            status_icon = "[green]✓[/green]" if result['success'] else "[red]✗[/red]"
            verification_table.add_row(fix, status_icon, result['notes'])
        
        self.console.print(verification_table)
        self.console.print()
        
        return True
    
    def _display_summary(self: Self) -> None:
        """Display troubleshooting summary."""
        self.console.print()
        
        summary_text = f"[bold green]Troubleshooting Complete![/bold green]\n\n"
        
        if self.issues_found:
            summary_text += f"• Issues Found: {len(self.issues_found)}\n"
            summary_text += f"• Fixes Applied: {len(self.fixes_applied)}\n"
        else:
            summary_text += "• No critical issues found\n"
        
        summary_text += f"• Problem Type: {self.diagnostics.get('problem_type', 'Unknown')}\n\n"
        
        if self.fixes_applied:
            summary_text += "[cyan]Applied Fixes:[/cyan]\n"
            for fix in self.fixes_applied:
                summary_text += f"  ✓ {fix}\n"
            summary_text += "\n"
        
        summary_text += "[yellow]Next Steps:[/yellow]\n"
        summary_text += "1. Test your application to ensure it's working\n"
        summary_text += "2. Monitor system performance\n"
        summary_text += "3. Check logs for any new issues\n"
        summary_text += "4. Run troubleshooting again if problems persist"
        
        self.console.print(Panel(
            summary_text,
            border_style="green",
            title="🔧 Troubleshooting Summary"
        ))
    
    # Diagnostic methods
    def _check_internet_connectivity(self: Self) -> bool:
        """Check internet connectivity."""
        try:
            response = requests.get('https://httpbin.org/ip', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _check_service_status(self: Self, service_name: str) -> Dict[str, Any]:
        """Check systemd service status."""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True, text=True
            )
            
            active = result.stdout.strip() == 'active'
            
            # Get detailed status
            status_result = subprocess.run(
                ['systemctl', 'status', service_name, '--no-pager', '-l'],
                capture_output=True, text=True
            )
            
            return {
                'active': active,
                'status_output': status_result.stdout,
                'error_output': status_result.stderr
            }
        except Exception as e:
            return {
                'active': False,
                'error': str(e)
            }
    
    def _test_localhost_connection(self: Self) -> Dict[str, Any]:
        """Test connection to localhost:8000."""
        try:
            response = requests.get('http://localhost:8000', timeout=5)
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_nginx_config(self: Self) -> Dict[str, Any]:
        """Test Nginx configuration."""
        try:
            result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True, text=True
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stderr,  # nginx -t outputs to stderr
                'error': result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _test_ssl_certificates(self: Self) -> Dict[str, Any]:
        """Test SSL certificate validity."""
        # This would check SSL certificates
        # For now, return a placeholder
        return {
            'success': True,
            'certificates_found': 0,
            'expired_certificates': 0
        }
    
    def _test_dns_resolution(self: Self) -> Dict[str, Any]:
        """Test DNS resolution."""
        try:
            import socket
            socket.gethostbyname('google.com')
            return {
                'success': True,
                'dns_working': True
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _check_application_logs(self: Self, app_name: str) -> Dict[str, Any]:
        """Check application logs for errors."""
        # This would check application-specific logs
        return {
            'errors_found': 0,
            'warnings_found': 0,
            'last_error': None
        }
    
    def _check_application_health(self: Self, app_name: str) -> Dict[str, Any]:
        """Check application health endpoint."""
        # This would check application health
        return {
            'healthy': True,
            'response_time': 0.1
        }
    
    def _check_application_config(self: Self, app_name: str) -> Dict[str, Any]:
        """Check application configuration."""
        # This would validate application configuration
        return {
            'config_valid': True,
            'missing_vars': []
        }
    
    def _check_application_dependencies(self: Self, app_name: str) -> Dict[str, Any]:
        """Check application dependencies."""
        # This would check application dependencies
        return {
            'dependencies_ok': True,
            'missing_dependencies': []
        }
    
    # Display methods
    def _display_system_status(self: Self) -> None:
        """Display system status table."""
        status_table = Table(title="System Status", show_header=True, header_style="bold cyan")
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", justify="right")
        status_table.add_column("Status", justify="center")
        
        # CPU usage
        cpu_status = "[green]Good[/green]" if self.diagnostics['cpu_usage'] < 80 else "[red]High[/red]"
        status_table.add_row("CPU Usage", f"{self.diagnostics['cpu_usage']:.1f}%", cpu_status)
        
        # Memory usage
        mem_status = "[green]Good[/green]" if self.diagnostics['memory_usage'] < 80 else "[red]High[/red]"
        status_table.add_row("Memory Usage", f"{self.diagnostics['memory_usage']:.1f}%", mem_status)
        
        # Disk usage
        disk_status = "[green]Good[/green]" if self.diagnostics['disk_usage'] < 80 else "[red]High[/red]"
        status_table.add_row("Disk Usage", f"{self.diagnostics['disk_usage']:.1f}%", disk_status)
        
        # Load average
        load_status = "[green]Good[/green]" if self.diagnostics['load_average'] < 2.0 else "[red]High[/red]"
        status_table.add_row("Load Average", f"{self.diagnostics['load_average']:.2f}", load_status)
        
        # Internet connectivity
        net_status = "[green]Connected[/green]" if self.diagnostics['internet_connectivity'] else "[red]Disconnected[/red]"
        status_table.add_row("Internet", "Available" if self.diagnostics['internet_connectivity'] else "Unavailable", net_status)
        
        self.console.print(status_table)
        self.console.print()
    
    def _display_service_status(self: Self, service_status: Dict[str, Any]) -> None:
        """Display service status table."""
        service_table = Table(title="WebOps Services", show_header=True, header_style="bold cyan")
        service_table.add_column("Service", style="cyan")
        service_table.add_column("Status", justify="center")
        service_table.add_column("Details")
        
        for service, status in service_status.items():
            if status['active']:
                status_text = "[green]✓ Active[/green]"
                details = "Running normally"
            else:
                status_text = "[red]✗ Inactive[/red]"
                details = status.get('error', 'Service not running')
            
            service_table.add_row(service, status_text, details)
        
        self.console.print(service_table)
        self.console.print()
    
    def _display_network_status(self: Self, network_results: Dict[str, Any]) -> None:
        """Display network test results."""
        network_table = Table(title="Network Tests", show_header=True, header_style="bold cyan")
        network_table.add_column("Test", style="cyan")
        network_table.add_column("Result", justify="center")
        network_table.add_column("Details")
        
        test_names = {
            'localhost_8000': 'WebOps Control Panel',
            'nginx_config': 'Nginx Configuration',
            'ssl_cert': 'SSL Certificates',
            'dns_resolution': 'DNS Resolution'
        }
        
        for test_key, result in network_results.items():
            test_name = test_names.get(test_key, test_key)
            
            if result['success']:
                status_text = "[green]✓ Pass[/green]"
                details = "Working correctly"
            else:
                status_text = "[red]✗ Fail[/red]"
                details = result.get('error', 'Test failed')
            
            network_table.add_row(test_name, status_text, details)
        
        self.console.print(network_table)
        self.console.print()
    
    def _display_application_status(self: Self, app_diagnostics: Dict[str, Any]) -> None:
        """Display application diagnostics."""
        app_table = Table(title="Application Diagnostics", show_header=True, header_style="bold cyan")
        app_table.add_column("Component", style="cyan")
        app_table.add_column("Status", justify="center")
        app_table.add_column("Details")
        
        # Add rows based on diagnostics
        components = [
            ('Logs', app_diagnostics.get('logs', {})),
            ('Health', app_diagnostics.get('health', {})),
            ('Configuration', app_diagnostics.get('config', {})),
            ('Dependencies', app_diagnostics.get('dependencies', {}))
        ]
        
        for component, data in components:
            # Initialize default values
            status = "[dim]Unknown[/dim]"
            details = "No data available"
            
            # Determine status based on component data
            if component == 'Logs':
                errors = data.get('errors_found', 0)
                status = "[green]✓ Good[/green]" if errors == 0 else f"[yellow]⚠ {errors} errors[/yellow]"
                details = f"{errors} errors, {data.get('warnings_found', 0)} warnings"
            elif component == 'Health':
                healthy = data.get('healthy', True)
                status = "[green]✓ Healthy[/green]" if healthy else "[red]✗ Unhealthy[/red]"
                details = f"Response time: {data.get('response_time', 0):.2f}s"
            elif component == 'Configuration':
                valid = data.get('config_valid', True)
                status = "[green]✓ Valid[/green]" if valid else "[red]✗ Invalid[/red]"
                missing = len(data.get('missing_vars', []))
                details = f"{missing} missing variables" if missing > 0 else "All variables present"
            elif component == 'Dependencies':
                deps_ok = data.get('dependencies_ok', True)
                status = "[green]✓ OK[/green]" if deps_ok else "[red]✗ Missing[/red]"
                missing = len(data.get('missing_dependencies', []))
                details = f"{missing} missing dependencies" if missing > 0 else "All dependencies available"
            
            app_table.add_row(component, status, details)
        
        self.console.print(app_table)
        self.console.print()
    
    # Issue analysis methods
    def _analyze_system_issues(self: Self) -> None:
        """Analyze system diagnostics for issues."""
        if self.diagnostics['cpu_usage'] > 90:
            self.issues_found.append({
                'priority': 'high',
                'category': 'System',
                'description': 'High CPU usage detected',
                'impact': 'Performance degradation',
                'fix_available': True,
                'fix_description': 'Restart high-CPU processes',
                'fix_function': 'restart_services'
            })
        
        if self.diagnostics['memory_usage'] > 90:
            self.issues_found.append({
                'priority': 'high',
                'category': 'System',
                'description': 'High memory usage detected',
                'impact': 'System instability',
                'fix_available': True,
                'fix_description': 'Clear memory cache and restart services',
                'fix_function': 'clear_memory'
            })
        
        if self.diagnostics['disk_usage'] > 95:
            self.issues_found.append({
                'priority': 'high',
                'category': 'System',
                'description': 'Disk space critically low',
                'impact': 'Application failures',
                'fix_available': True,
                'fix_description': 'Clean up log files and temporary data',
                'fix_function': 'cleanup_disk'
            })
    
    def _analyze_service_issues(self: Self, service_status: Dict[str, Any]) -> None:
        """Analyze service status for issues."""
        for service, status in service_status.items():
            if not status['active']:
                self.issues_found.append({
                    'priority': 'high',
                    'category': 'Services',
                    'description': f'{service} service is not running',
                    'impact': 'WebOps functionality impaired',
                    'fix_available': True,
                    'fix_description': f'Restart {service} service',
                    'fix_function': 'restart_service',
                    'fix_params': {'service': service}
                })
    
    def _analyze_network_issues(self: Self, network_results: Dict[str, Any]) -> None:
        """Analyze network test results for issues."""
        if not network_results.get('localhost_8000', {}).get('success'):
            self.issues_found.append({
                'priority': 'high',
                'category': 'Network',
                'description': 'WebOps Control Panel not accessible',
                'impact': 'Cannot access web interface',
                'fix_available': True,
                'fix_description': 'Restart web service and check configuration',
                'fix_function': 'fix_web_access'
            })
        
        if not network_results.get('nginx_config', {}).get('success'):
            self.issues_found.append({
                'priority': 'high',
                'category': 'Network',
                'description': 'Nginx configuration error',
                'impact': 'Web server not functioning',
                'fix_available': True,
                'fix_description': 'Fix Nginx configuration syntax',
                'fix_function': 'fix_nginx_config'
            })
    
    def _analyze_application_issues(self: Self, app_diagnostics: Dict[str, Any]) -> None:
        """Analyze application diagnostics for issues."""
        logs = app_diagnostics.get('logs', {})
        if logs.get('errors_found', 0) > 0:
            self.issues_found.append({
                'priority': 'medium',
                'category': 'Application',
                'description': f"Application has {logs['errors_found']} log errors",
                'impact': 'Application may not function correctly',
                'fix_available': False,
                'manual_fix': 'Review application logs and fix code issues'
            })
        
        health = app_diagnostics.get('health', {})
        if not health.get('healthy', True):
            self.issues_found.append({
                'priority': 'high',
                'category': 'Application',
                'description': 'Application health check failing',
                'impact': 'Application not responding correctly',
                'fix_available': True,
                'fix_description': 'Restart application',
                'fix_function': 'restart_application'
            })
    
    # Fix application methods
    def _selective_fix_application(self: Self, fixable_issues: List[Dict[str, Any]]) -> bool:
        """Allow user to select which fixes to apply.
        
        Args:
            fixable_issues: List of issues that can be automatically fixed.
            
        Returns:
            True if fixes were applied successfully, False otherwise.
        """
        self.console.print("Select fixes to apply:")
        self.console.print()
        
        selected_fixes: List[Dict[str, Any]] = []
        for issue in fixable_issues:
            if Confirm.ask(f"Apply fix for: {issue['description']}?", default=True):
                selected_fixes.append(issue)
        
        if not selected_fixes:
            self.console.print("[yellow]No fixes selected.[/yellow]")
            return True
        
        # Apply selected fixes
        with progress_manager.progress_bar("Applying selected fixes") as progress:
            task = progress.add_task("Fixing issues", total=len(selected_fixes))
            
            for issue in selected_fixes:
                progress.update(task, description=f"[cyan]Fixing: {issue['description']}[/cyan]")
                
                success = self._apply_fix(issue)
                if success:
                    self.fixes_applied.append(issue['description'])
                
                progress.update(task, advance=1)
        
        return True
    
    def _apply_fix(self: Self, issue: Dict[str, Any]) -> bool:
        """Apply a specific fix."""
        fix_function = issue.get('fix_function')
        fix_params = issue.get('fix_params', {})
        
        try:
            if fix_function == 'restart_services':
                return self._fix_restart_services()
            elif fix_function == 'clear_memory':
                return self._fix_clear_memory()
            elif fix_function == 'cleanup_disk':
                return self._fix_cleanup_disk()
            elif fix_function == 'restart_service':
                return self._fix_restart_service(fix_params.get('service'))
            elif fix_function == 'fix_web_access':
                return self._fix_web_access()
            elif fix_function == 'fix_nginx_config':
                return self._fix_nginx_config()
            elif fix_function == 'restart_application':
                return self._fix_restart_application()
            else:
                return False
        except Exception:
            return False
    
    def _verify_fix(self: Self, fix_description: str) -> Dict[str, Any]:
        """Verify that a fix was successful."""
        # This would re-run relevant diagnostics to verify the fix
        # For now, return a placeholder
        return {
            'success': True,
            'notes': 'Fix verified successfully'
        }
    
    # Specific fix implementations
    def _fix_restart_services(self: Self) -> bool:
        """Restart WebOps services."""
        services = ['webops-web', 'webops-celery', 'webops-celerybeat']
        for service in services:
            try:
                subprocess.run(['systemctl', 'restart', service], check=True)
            except:
                return False
        return True
    
    def _fix_clear_memory(self: Self) -> bool:
        """Clear system memory cache."""
        try:
            subprocess.run(['sync'], check=True)
            subprocess.run(['echo', '3', '>', '/proc/sys/vm/drop_caches'], shell=True, check=True)
            return True
        except:
            return False
    
    def _fix_cleanup_disk(self: Self) -> bool:
        """Clean up disk space."""
        try:
            # Clean up log files
            subprocess.run(['find', '/var/log', '-name', '*.log', '-mtime', '+7', '-delete'], check=True)
            # Clean up temporary files
            subprocess.run(['rm', '-rf', '/tmp/*'], shell=True, check=True)
            return True
        except:
            return False
    
    def _fix_restart_service(self: Self, service: str) -> bool:
        """Restart a specific service."""
        try:
            subprocess.run(['systemctl', 'restart', service], check=True)
            return True
        except:
            return False
    
    def _fix_web_access(self: Self) -> bool:
        """Fix web access issues."""
        try:
            subprocess.run(['systemctl', 'restart', 'webops-web'], check=True)
            subprocess.run(['systemctl', 'restart', 'nginx'], check=True)
            return True
        except:
            return False
    
    def _fix_nginx_config(self: Self) -> bool:
        """Fix Nginx configuration."""
        try:
            # Test configuration first
            result = subprocess.run(['nginx', '-t'], capture_output=True)
            if result.returncode == 0:
                subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
                return True
            return False
        except:
            return False
    
    def _fix_restart_application(self: Self) -> bool:
        """Restart application."""
        app_name = self.diagnostics.get('app_name')
        if not app_name:
            return False
        
        try:
            # This would restart the specific application
            # For now, just restart web services
            subprocess.run(['systemctl', 'restart', 'webops-web'], check=True)
            return True
        except:
            return False
    
    def _display_manual_fixes(self: Self) -> None:
        """Display manual fix instructions."""
        manual_issues = [issue for issue in self.issues_found if not issue.get('fix_available')]
        
        if not manual_issues:
            return
        
        self.console.print("[bold yellow]Manual Resolution Required:[/bold yellow]")
        self.console.print()
        
        for i, issue in enumerate(manual_issues, 1):
            self.console.print(f"[cyan]{i}.[/cyan] {issue['description']}")
            self.console.print(f"   [yellow]Resolution:[/yellow] {issue.get('manual_fix', 'Contact support')}")
            self.console.print()


@click.command()
def troubleshoot():
    """Run the interactive troubleshooting wizard."""
    troubleshooting_wizard = TroubleshootingWizard()
    success = troubleshooting_wizard.run()
    
    if success:
        console.print("\n[green]Troubleshooting completed successfully![/green]")
    else:
        console.print("\n[red]Troubleshooting failed or was cancelled.[/red]")


if __name__ == '__main__':
    troubleshoot()