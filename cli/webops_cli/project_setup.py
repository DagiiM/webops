"""
Project setup workflow for WebOps.

This module provides automated workflow for:
1. Cloning projects from GitHub
2. Detecting project entry points
3. Setting up the project (dependencies, environment, etc.)
4. Verifying web access on the specified port
"""

import os
import time
import requests
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, Prompt
from git import Repo, GitCommandError

from .api import WebOpsAPIClient, WebOpsAPIError
from .validators import InputValidator, ValidationError
from .security_logging import get_security_logger

console = Console()
security_logger = get_security_logger()


@dataclass
class ProjectSetupResult:
    """Result of project setup process."""
    success: bool
    project_name: str
    repo_url: str
    entry_point: str
    project_type: str
    port: Optional[int] = None
    web_url: Optional[str] = None
    setup_steps: List[Dict[str, Any]] = None
    error_message: Optional[str] = None
    deployment_id: Optional[int] = None

    def __post_init__(self):
        if self.setup_steps is None:
            self.setup_steps = []


class ProjectSetupWorkflow:
    """Automated project setup workflow."""

    def __init__(self, api_client: WebOpsAPIClient):
        self.api_client = api_client
        self.temp_dir = Path("/tmp/webops_project_setup")
        self.temp_dir.mkdir(exist_ok=True)

    def cleanup(self):
        """Clean up temporary files."""
        try:
            if self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not cleanup temp directory: {e}[/yellow]")

    def clone_project(self, repo_url: str, project_name: str) -> Tuple[bool, str, Path]:
        """
        Clone a project from GitHub.

        Args:
            repo_url: GitHub repository URL
            project_name: Name for the project

        Returns:
            Tuple of (success, message, repo_path)
        """
        try:
            # Validate repo URL
            validated_repo = InputValidator.validate_git_url(repo_url)
            
            # Ensure HTTPS format for GitHub
            if not validated_repo.startswith('https://'):
                if 'github.com' in validated_repo:
                    validated_repo = f"https://github.com/{validated_repo.split('github.com/')[-1]}"
                else:
                    return False, "Only HTTPS URLs are supported for cloning", Path()

            # Add .git if missing
            if validated_repo.startswith('https://github.com/') and not validated_repo.endswith('.git'):
                validated_repo += '.git'

            repo_path = self.temp_dir / project_name

            # Remove existing directory if present
            if repo_path.exists():
                import shutil
                shutil.rmtree(repo_path)

            console.print(f"[cyan]Cloning repository:[/cyan] {validated_repo}")
            
            # Clone the repository
            repo = Repo.clone_from(
                validated_repo,
                repo_path,
                depth=1,  # Shallow clone for speed
                single_branch=True
            )

            return True, f"Repository cloned successfully", repo_path

        except GitCommandError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                return False, "Repository not found or is private", Path()
            elif "permission denied" in error_msg.lower():
                return False, "Permission denied - repository may be private", Path()
            else:
                return False, f"Git error: {error_msg}", Path()
        except ValidationError as e:
            return False, f"Invalid repository URL: {e}", Path()
        except Exception as e:
            return False, f"Unexpected error: {e}", Path()

    def detect_project_type_and_entry_point(self, repo_path: Path) -> Tuple[str, str, Dict[str, Any]]:
        """
        Detect project type and entry point.

        Args:
            repo_path: Path to cloned repository

        Returns:
            Tuple of (project_type, entry_point, details)
        """
        details = {}

        # Check for Django project
        manage_py = repo_path / "manage.py"
        if manage_py.exists():
            # Find settings.py
            settings_files = list(repo_path.rglob("settings.py"))
            
            # Filter out excluded directories
            excluded_dirs = {'migrations', 'tests', 'test', 'venv', 'env', '__pycache__', '.git'}
            valid_settings = []
            for settings_file in settings_files:
                relative_path = settings_file.relative_to(repo_path)
                if not any(part in excluded_dirs for part in relative_path.parts):
                    valid_settings.append(settings_file)

            if valid_settings:
                # Use the same logic as WebOps deployment service
                best_settings = None
                best_score = -1
                
                for settings_file in valid_settings:
                    relative_path = settings_file.relative_to(repo_path)
                    path_parts = relative_path.parts[:-1]  # Exclude 'settings.py'
                    
                    score = 0
                    if 'config' in path_parts:
                        score += 10
                    elif any(word in path_parts for word in ['core', 'project']):
                        score += 6
                    elif len(path_parts) == 1:
                        score += 4
                    
                    score += max(0, 5 - len(path_parts))
                    
                    init_file = settings_file.parent / "__init__.py"
                    if init_file.exists():
                        score += 3
                    
                    if score > best_score:
                        best_score = score
                        best_settings = settings_file

                if best_settings:
                    relative_path = best_settings.relative_to(repo_path)
                    module_parts = relative_path.parts[:-1]
                    if module_parts:
                        entry_point = '.'.join(module_parts) + '.settings'
                    else:
                        entry_point = 'settings'
                    
                    details['settings_file'] = str(relative_path)
                    details['manage_py'] = True
                else:
                    entry_point = 'settings'
                    details['settings_file'] = 'settings.py'
                    details['manage_py'] = True
            else:
                entry_point = 'settings'
                details['manage_py'] = True
                details['settings_file'] = 'Not found'

            # Check for ASGI
            asgi_files = list(repo_path.rglob("asgi.py"))
            valid_asgi = [f for f in asgi_files if not any(part in f.relative_to(repo_path).parts for part in excluded_dirs)]
            if valid_asgi:
                details['asgi'] = True
                details['asgi_file'] = str(valid_asgi[0].relative_to(repo_path))
            else:
                details['asgi'] = False

            return 'django', entry_point, details

        # Check for static site
        static_files = [
            repo_path / "index.html",
            repo_path / "index.htm",
            repo_path / "public/index.html",
            repo_path / "dist/index.html",
            repo_path / "build/index.html"
        ]
        
        for static_file in static_files:
            if static_file.exists():
                return 'static', str(static_file.relative_to(repo_path)), {'static_file': str(static_file.relative_to(repo_path))}

        # Check for Node.js project
        package_json = repo_path / "package.json"
        if package_json.exists():
            try:
                import json
                package_data = json.loads(package_json.read_text())
                scripts = package_data.get('scripts', {})
                
                if 'start' in scripts:
                    return 'nodejs', 'npm start', {'package_json': True, 'start_script': scripts['start']}
                elif 'dev' in scripts:
                    return 'nodejs', 'npm run dev', {'package_json': True, 'dev_script': scripts['dev']}
                else:
                    return 'nodejs', 'npm install', {'package_json': True, 'no_start_script': True}
            except:
                return 'nodejs', 'package.json', {'package_json': True, 'parse_error': True}

        # Default to static if no clear indicators
        return 'static', 'index.html', {'default_assumption': True}

    def create_webops_deployment(self, project_name: str, repo_url: str, project_type: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a WebOps deployment for the project.

        Args:
            project_name: Name of the project
            repo_url: Repository URL
            project_type: Detected project type

        Returns:
            Tuple of (success, deployment_info)
        """
        try:
            console.print(f"[cyan]Creating WebOps deployment:[/cyan] {project_name}")
            
            result = self.api_client.create_deployment(
                name=project_name,
                repo_url=repo_url,
                branch='main',
                domain=''  # No domain for basic setup
            )

            if result.get('success', True):
                return True, {
                    'deployment_id': result.get('id'),
                    'deployment_name': result.get('name', project_name),
                    'message': result.get('message', 'Deployment created')
                }
            else:
                return False, {'error': result.get('error', 'Unknown error')}

        except WebOpsAPIError as e:
            return False, {'error': str(e)}
        except Exception as e:
            return False, {'error': f"Unexpected error: {e}"}

    def wait_for_deployment_setup(self, deployment_name: str, timeout: int = 300) -> Tuple[bool, Dict[str, Any]]:
        """
        Wait for deployment setup to complete.

        Args:
            deployment_name: Name of the deployment
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, deployment_info)
        """
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Setting up deployment...", total=100)

            while time.time() - start_time < timeout:
                try:
                    # Get deployment status
                    deployment = self.api_client.get_deployment(deployment_name)
                    status = deployment.get('status', 'unknown')
                    port = deployment.get('port')
                    
                    progress.update(task, description=f"Deployment status: {status}")
                    
                    if status == 'running':
                        progress.update(task, completed=100)
                        return True, {
                            'status': status,
                            'port': port,
                            'deployment': deployment
                        }
                    elif status == 'failed':
                        progress.update(task, completed=100)
                        return False, {
                            'status': status,
                            'error': 'Deployment failed',
                            'deployment': deployment
                        }
                    
                    # Update progress based on time elapsed
                    elapsed = time.time() - start_time
                    progress_value = min(90, int((elapsed / timeout) * 90))
                    progress.update(task, completed=progress_value)
                    
                    time.sleep(5)
                    
                except WebOpsAPIError as e:
                    progress.update(task, description=f"API Error: {e}")
                    time.sleep(5)
                except Exception as e:
                    progress.update(task, description=f"Error: {e}")
                    time.sleep(5)

            return False, {'error': 'Setup timeout', 'status': 'timeout'}

    def verify_web_access(self, port: int, deployment_name: str, timeout: int = 60) -> Tuple[bool, str]:
        """
        Verify that the project is accessible on the web.

        Args:
            port: Port number to check
            deployment_name: Name of the deployment
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, message)
        """
        console.print(f"[cyan]Verifying web access on port {port}...[/cyan]")
        
        # Try different URLs
        urls_to_try = [
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ]
        
        for url in urls_to_try:
            for attempt in range(timeout // 5):  # Try every 5 seconds
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        return True, f"✓ Project accessible at {url} (Status: {response.status_code})"
                    elif response.status_code in [301, 302, 307, 308]:
                        # Redirect is good
                        return True, f"✓ Project accessible at {url} (Redirect: {response.status_code})"
                    elif response.status_code >= 400:
                        console.print(f"[yellow]Attempt {attempt + 1}: {url} returned {response.status_code}[/yellow]")
                    
                except requests.exceptions.ConnectionError:
                    console.print(f"[yellow]Attempt {attempt + 1}: {url} - Connection refused[/yellow]")
                except requests.exceptions.Timeout:
                    console.print(f"[yellow]Attempt {attempt + 1}: {url} - Timeout[/yellow]")
                except Exception as e:
                    console.print(f"[yellow]Attempt {attempt + 1}: {url} - {e}[/yellow]")
                
                time.sleep(5)
        
        return False, f"✗ Could not access project on port {port} after {timeout} seconds"

    def run_complete_workflow(
        self,
        repo_url: str,
        project_name: Optional[str] = None,
        create_deployment: bool = True,
        verify_access: bool = True
    ) -> ProjectSetupResult:
        """
        Run the complete project setup workflow.

        Args:
            repo_url: GitHub repository URL
            project_name: Optional name for the project
            create_deployment: Whether to create WebOps deployment
            verify_access: Whether to verify web access

        Returns:
            ProjectSetupResult with all details
        """
        result = ProjectSetupResult(
            success=False,
            project_name=project_name or "unknown",
            repo_url=repo_url,
            entry_point="",
            project_type=""
        )

        try:
            # Step 1: Clone project
            console.print(Panel("Step 1: Cloning Project", border_style="blue"))
            success, message, repo_path = self.clone_project(repo_url, result.project_name)
            
            result.setup_steps.append({
                'step': 'clone',
                'success': success,
                'message': message
            })
            
            if not success:
                result.error_message = message
                return result
            
            console.print(f"[green]✓[/green] {message}")

            # Step 2: Detect project type and entry point
            console.print(Panel("Step 2: Detecting Project Type and Entry Point", border_style="blue"))
            project_type, entry_point, details = self.detect_project_type_and_entry_point(repo_path)
            
            result.project_type = project_type
            result.entry_point = entry_point
            
            result.setup_steps.append({
                'step': 'detect',
                'success': True,
                'message': f"Detected {project_type} project with entry point: {entry_point}",
                'details': details
            })
            
            console.print(f"[green]✓[/green] Project Type: {project_type}")
            console.print(f"[green]✓[/green] Entry Point: {entry_point}")

            # Display detection details
            if details:
                details_table = Table(title="Detection Details")
                details_table.add_column("Property", style="cyan")
                details_table.add_column("Value", style="white")
                
                for key, value in details.items():
                    if isinstance(value, bool):
                        value = "Yes" if value else "No"
                    details_table.add_row(key.replace('_', ' ').title(), str(value))
                
                console.print(details_table)

            # Step 3: Create WebOps deployment (if requested)
            if create_deployment:
                console.print(Panel("Step 3: Creating WebOps Deployment", border_style="blue"))
                success, deployment_info = self.create_webops_deployment(
                    result.project_name, repo_url, project_type
                )
                
                result.setup_steps.append({
                    'step': 'deploy',
                    'success': success,
                    'message': deployment_info.get('message', deployment_info.get('error', 'Unknown')),
                    'details': deployment_info
                })
                
                if not success:
                    result.error_message = deployment_info.get('error', 'Deployment creation failed')
                    return result
                
                result.deployment_id = deployment_info.get('deployment_id')
                console.print(f"[green]✓[/green] {deployment_info.get('message')}")

                # Step 4: Wait for deployment setup
                console.print(Panel("Step 4: Waiting for Setup Completion", border_style="blue"))
                success, setup_info = self.wait_for_deployment_setup(result.project_name)
                
                result.setup_steps.append({
                    'step': 'setup',
                    'success': success,
                    'message': f"Deployment status: {setup_info.get('status', 'unknown')}",
                    'details': setup_info
                })
                
                if not success:
                    result.error_message = setup_info.get('error', 'Setup failed')
                    return result
                
                result.port = setup_info.get('port')
                console.print(f"[green]✓[/green] Deployment ready on port {result.port}")

                # Step 5: Verify web access (if requested)
                if verify_access and result.port:
                    console.print(Panel("Step 5: Verifying Web Access", border_style="blue"))
                    success, access_message = self.verify_web_access(result.port, result.project_name)
                    
                    result.setup_steps.append({
                        'step': 'verify',
                        'success': success,
                        'message': access_message
                    })
                    
                    if success:
                        result.web_url = f"http://localhost:{result.port}"
                        console.print(f"[green]✓[/green] {access_message}")
                    else:
                        console.print(f"[red]✗[/red] {access_message}")
                        # Don't fail the entire workflow for access issues
                        console.print("[yellow]Note: The project may need additional configuration or time to start[/yellow]")

            # Mark as successful
            result.success = True

        except Exception as e:
            result.error_message = f"Unexpected error: {e}"
            result.setup_steps.append({
                'step': 'error',
                'success': False,
                'message': str(e)
            })

        finally:
            # Cleanup
            self.cleanup()

        return result

    def display_result_summary(self, result: ProjectSetupResult):
        """Display a summary of the setup result."""
        console.print("\n" + "="*60)
        console.print(Panel("PROJECT SETUP SUMMARY", border_style="bold blue"))
        console.print("="*60)
        
        # Basic info
        info_table = Table(title="Project Information")
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")
        
        info_table.add_row("Project Name", result.project_name)
        info_table.add_row("Repository", result.repo_url)
        info_table.add_row("Project Type", result.project_type)
        info_table.add_row("Entry Point", result.entry_point)
        
        if result.port:
            info_table.add_row("Port", str(result.port))
        if result.web_url:
            info_table.add_row("Web URL", result.web_url)
        if result.deployment_id:
            info_table.add_row("Deployment ID", str(result.deployment_id))
        
        console.print(info_table)
        
        # Steps summary
        steps_table = Table(title="Setup Steps")
        steps_table.add_column("Step", style="cyan")
        steps_table.add_column("Status", justify="center")
        steps_table.add_column("Message", style="white")
        
        for step in result.setup_steps:
            step_name = step['step'].replace('_', ' ').title()
            status = "✓" if step['success'] else "✗"
            status_style = "green" if step['success'] else "red"
            
            steps_table.add_row(
                step_name,
                f"[{status_style}]{status}[/{status_style}]",
                step['message']
            )
        
        console.print(steps_table)
        
        # Final status
        if result.success:
            console.print(f"\n[green]✓ PROJECT SETUP COMPLETED SUCCESSFULLY![/green]")
            if result.web_url:
                console.print(f"[cyan]Access your project at:[/cyan] {result.web_url}")
        else:
            console.print(f"\n[red]✗ PROJECT SETUP FAILED[/red]")
            if result.error_message:
                console.print(f"[red]Error:[/red] {result.error_message}")
        
        console.print("="*60)
