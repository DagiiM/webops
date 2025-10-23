"""
Service management for WebOps deployments.

"Service Management" section

This module implements systemd service management:
- Service start/stop/restart
- Service status checking
- Nginx configuration reload
- Service installation and enablement
"""

import subprocess
import logging
import time
import threading
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from django.conf import settings
from django.core.cache import cache

from ..models import BaseDeployment, ApplicationDeployment, DeploymentLog

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manager for systemd service operations."""

    def __init__(self):
        """Initialize service manager."""
        self._health_check_thread = None
        self._stop_health_check = threading.Event()
        self._fallback_configs = {
            'redis': self._redis_fallback,
            'postgresql': self._postgresql_fallback,
            'nginx': self._nginx_fallback,
            'celery': self._celery_fallback,
        }
        
    CORE_UNITS = {
        'nginx': ['nginx.service', 'nginx'],
        'postgresql': ['postgresql.service', 'postgresql'],
        'redis': ['redis-server.service', 'redis.service', 'redis-server', 'redis'],
        'celery': ['webops-celery.service'],
        'celerybeat': ['webops-celerybeat.service'],
        'web': ['webops-web.service'],
    }
    
    # Health check configuration
    HEALTH_CHECK_INTERVAL = 30  # seconds
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5  # seconds
    SERVICE_TIMEOUT = 10  # seconds

    @staticmethod
    def _is_unit_active(unit_names: list[str]) -> bool:
        for name in unit_names:
            try:
                p = subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True)
                if p.returncode == 0 and p.stdout.strip() == 'active':
                    return True
            except Exception:
                continue
        return False

    def get_core_services_status(self) -> Dict[str, Any]:
        """Read-only check of core services required for deployment."""
        # systemctl availability
        try:
            sc = subprocess.run(['systemctl', '--version'], capture_output=True, text=True)
            systemctl_ok = sc.returncode == 0
        except Exception:
            systemctl_ok = False

        statuses = {}
        for key, units in self.CORE_UNITS.items():
            statuses[key] = self._is_unit_active(units)

        all_ok = systemctl_ok and statuses.get('redis') and statuses.get('postgresql') and statuses.get('celery')
        return {
            'systemctl': systemctl_ok,
            'services': statuses,
            'all_ok': bool(all_ok),
        }


    def _log(
        self,
        deployment: BaseDeployment,
        message: str,
        level: str = DeploymentLog.Level.INFO
    ) -> None:
        """
        Log a service management message.

        Args:
            deployment: Deployment instance
            message: Log message
            level: Log level
        """
        DeploymentLog.objects.create(
            deployment=deployment,
            level=level,
            message=message
        )
        logger.info(f"[{deployment.name}] {message}")

    def _run_systemctl(
        self,
        command: str,
        service_name: str,
        check: bool = True
    ) -> Tuple[bool, str]:
        """
        Run systemctl command.

        Args:
            command: systemctl command (start, stop, restart, status, etc.)
            service_name: Name of the service
            check: Whether to check return code

        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['sudo', '-n', 'systemctl', command, f'{service_name}.service'],
                capture_output=True,
                text=True,
                check=check
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"systemctl {command} failed for {service_name}: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            logger.error(f"Unexpected error running systemctl: {e}")
            return False, str(e)

    def install_service(
        self,
        deployment: BaseDeployment,
        service_config: str
    ) -> Tuple[bool, str]:
        """
        Install systemd service file.

        Args:
            deployment: Deployment instance
            service_config: Rendered service configuration

        Returns:
            Tuple of (success, message)
        """
        service_path = Path(f"/etc/systemd/system/{deployment.name}.service")

        try:
            # Write service file (requires sudo in production)
            service_path.write_text(service_config)

            # Reload systemd daemon
            subprocess.run(
                ['sudo', 'systemctl', 'daemon-reload'],
                check=True,
                capture_output=True
            )

            self._log(
                deployment,
                f"Systemd service installed: {service_path}",
                DeploymentLog.Level.SUCCESS
            )
            return True, str(service_path)

        except PermissionError:
            error_msg = "Permission denied: requires sudo for systemd service"
            self._log(deployment, error_msg, DeploymentLog.Level.WARNING)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to install systemd service: {e}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def enable_service(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Enable service to start on boot.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        self._log(deployment, f"Enabling service {deployment.name}")

        success, output = self._run_systemctl('enable', deployment.name)

        if success:
            self._log(
                deployment,
                f"Service {deployment.name} enabled",
                DeploymentLog.Level.SUCCESS
            )
            return True, f"Service {deployment.name} enabled"
        else:
            error_msg = f"Failed to enable service: {output}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def start_service(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Start systemd service.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        self._log(deployment, f"Starting service {deployment.name}")

        success, output = self._run_systemctl('start', deployment.name)

        if success:
            deployment.status = BaseDeployment.Status.RUNNING
            deployment.save(update_fields=['status'])

            self._log(
                deployment,
                f"Service {deployment.name} started successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, f"Service {deployment.name} started"
        else:
            deployment.status = BaseDeployment.Status.FAILED
            deployment.save(update_fields=['status'])

            error_msg = f"Failed to start service: {output}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def stop_service(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Stop systemd service.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        self._log(deployment, f"Stopping service {deployment.name}")

        success, output = self._run_systemctl('stop', deployment.name)

        if success:
            deployment.status = STOPPED
            deployment.save(update_fields=['status'])

            self._log(
                deployment,
                f"Service {deployment.name} stopped successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, f"Service {deployment.name} stopped"
        else:
            error_msg = f"Failed to stop service: {output}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def restart_service(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Restart systemd service.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        self._log(deployment, f"Restarting service {deployment.name}")

        success, output = self._run_systemctl('restart', deployment.name)

        if success:
            deployment.status = BaseDeployment.Status.RUNNING
            deployment.save(update_fields=['status'])

            self._log(
                deployment,
                f"Service {deployment.name} restarted successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, f"Service {deployment.name} restarted"
        else:
            error_msg = f"Failed to restart service: {output}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def get_service_status(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Get current service status using read-only systemctl queries (no sudo).
        """
        service_unit = f"{deployment.name}.service"

        # is-active (read-only)
        try:
            active_proc = subprocess.run(
                ['systemctl', 'is-active', service_unit],
                capture_output=True,
                text=True
            )
            is_active = active_proc.returncode == 0
        except Exception:
            is_active = False

        # is-enabled (read-only)
        try:
            enabled_proc = subprocess.run(
                ['systemctl', 'is-enabled', service_unit],
                capture_output=True,
                text=True
            )
            is_enabled = enabled_proc.returncode == 0
        except Exception:
            is_enabled = False

        # Best-effort status output (no sudo, no pager)
        try:
            status_proc = subprocess.run(
                ['systemctl', 'status', '--no-pager', service_unit],
                capture_output=True,
                text=True
            )
            output = status_proc.stdout or status_proc.stderr
        except Exception as e:
            output = str(e)

    def restart_core_service(self, service_name: str) -> Tuple[bool, str]:
        """
        Restart a core prerequisite service.
        
        Args:
            service_name: Name of the service to restart
            
        Returns:
            Tuple of (success, message)
        """
        if service_name not in self.CORE_UNITS:
            return False, f"Unknown service: {service_name}"
        
        # First check if systemd is available in this environment
        try:
            systemd_check = subprocess.run(
                ['systemctl', '--version'],
                capture_output=True,
                text=True,
                check=False
            )
            if systemd_check.returncode != 0:
                logger.warning(f"Systemd not available in this environment. Service restart functionality is limited.")
                return False, "Service restart is not available in this environment. Systemd is not available (possibly running in a container). This is expected in development environments."
        except Exception as e:
            logger.warning(f"Unable to check systemd availability: {e}")
            return False, f"Unable to verify systemd availability: {e}"
        
        units = self.CORE_UNITS[service_name]
        
        # Try to restart each possible unit name for this service
        for unit in units:
            try:
                # First try to stop the service (ignore errors if not running)
                stop_result = subprocess.run(
                    ['sudo', '-n', 'systemctl', 'stop', unit],
                    capture_output=True,
                    text=True,
                    check=False  # Don't fail if service isn't running
                )
                
                # Check if sudo password is required
                if stop_result.returncode != 0 and 'sudo: a password is required' in stop_result.stderr:
                    logger.warning(f"Sudo password required for stopping {unit}")
                    # Try without sudo first (for services that don't require it)
                    stop_result = subprocess.run(
                        ['systemctl', 'stop', unit],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                
                # Then start the service
                start_result = subprocess.run(
                    ['sudo', '-n', 'systemctl', 'start', unit],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Check if sudo password is required for start
                if start_result.returncode != 0 and 'sudo: a password is required' in start_result.stderr:
                    logger.warning(f"Sudo password required for starting {unit}")
                    # Try without sudo first
                    start_result = subprocess.run(
                        ['systemctl', 'start', unit],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                
                # Check if either attempt was successful
                if start_result.returncode == 0:
                    return True, f"Service {service_name} restarted successfully"
                else:
                    # If both sudo and non-sudo failed, log the error
                    error_msg = f"Failed to restart {unit}: {start_result.stderr}"
                    logger.warning(f"Service restart failed for {unit}: {error_msg}")
                    continue
                    
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to restart {unit}: {e.stderr}"
                logger.warning(f"Service restart failed for {unit}: {error_msg}")
                continue
            except Exception as e:
                error_msg = f"Unexpected error restarting {unit}: {e}"
                logger.error(error_msg)
                continue
        
        return False, f"Failed to restart {service_name} - all unit attempts failed. This may be due to insufficient sudo privileges. Please ensure the web server user has passwordless sudo access for systemctl commands or that services can be managed without sudo."

    def get_core_services_status_detailed(self) -> Dict[str, Any]:
        """
        Get detailed status of all core services with restart capabilities.
        
        Returns:
            Dictionary with detailed service information
        """
        services = {}
        
        for service_key, units in self.CORE_UNITS.items():
            service_info = {
                'name': service_key,
                'units': units,
                'status': 'unknown',
                'active': False,
                'enabled': False,
                'restartable': True,
                'last_check': None,
                'fallback_available': service_key in self._fallback_configs,
                'health_check_enabled': True,
                'auto_restart_enabled': cache.get(f'service_auto_restart_{service_key}', True),
                'consecutive_failures': cache.get(f'service_failures_{service_key}', 0),
                'last_failure_time': cache.get(f'service_last_failure_{service_key}'),
            }
            
            # Check if any unit is active
            for unit in units:
                try:
                    # Check if active
                    active_proc = subprocess.run(
                        ['systemctl', 'is-active', unit],
                        capture_output=True,
                        text=True,
                        timeout=self.SERVICE_TIMEOUT
                    )
                    is_active = active_proc.returncode == 0
                    
                    # Check if enabled
                    enabled_proc = subprocess.run(
                        ['systemctl', 'is-enabled', unit],
                        capture_output=True,
                        text=True,
                        timeout=self.SERVICE_TIMEOUT
                    )
                    is_enabled = enabled_proc.returncode == 0
                    
                    # Get status output
                    status_proc = subprocess.run(
                        ['systemctl', 'status', '--no-pager', unit],
                        capture_output=True,
                        text=True,
                        timeout=self.SERVICE_TIMEOUT
                    )
                    status_output = status_proc.stdout or status_proc.stderr
                    
                    service_info.update({
                        'status': 'running' if is_active else 'stopped',
                        'active': is_active,
                        'enabled': is_enabled,
                        'current_unit': unit,
                        'status_output': status_output,
                        'last_check': time.time()
                    })
                    
                    # Update failure tracking
                    if is_active:
                        cache.set(f'service_failures_{service_key}', 0)
                    else:
                        failures = cache.get(f'service_failures_{service_key}', 0) + 1
                        cache.set(f'service_failures_{service_key}', failures)
                        cache.set(f'service_last_failure_{service_key}', time.time())
                    
                    # If we found an active unit, use it as the primary status
                    if is_active:
                        break
                        
                except subprocess.TimeoutExpired:
                    service_info['error'] = f'Timeout checking {unit}'
                    continue
                except Exception as e:
                    service_info['error'] = str(e)
                    continue
            
            services[service_key] = service_info
        
        return services

    def check_service_health_with_retry(self, service_name: str, max_retries: int = None) -> Tuple[bool, str]:
        """
        Check service health with retry logic and fallback options.
        
        Args:
            service_name: Name of the service to check
            max_retries: Maximum number of retry attempts (default: MAX_RETRY_ATTEMPTS)
            
        Returns:
            Tuple of (is_healthy, message)
        """
        if max_retries is None:
            max_retries = self.MAX_RETRY_ATTEMPTS
            
        for attempt in range(max_retries + 1):
            try:
                # Check if service is healthy
                if service_name in self.CORE_UNITS:
                    units = self.CORE_UNITS[service_name]
                    is_healthy = self._is_unit_active(units)
                    
                    if is_healthy:
                        # Reset failure counter on success
                        cache.set(f'service_failures_{service_name}', 0)
                        return True, f"{service_name} is healthy"
                    
                    # If not healthy and we have retries left, wait and try again
                    if attempt < max_retries:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    
                    # No more retries, try fallback if available
                    if service_name in self._fallback_configs:
                        fallback_success, fallback_msg = self._try_fallback(service_name)
                        if fallback_success:
                            return True, f"Service unhealthy but fallback activated: {fallback_msg}"
                        else:
                            return False, f"Service unhealthy and fallback failed: {fallback_msg}"
                    
                    return False, f"{service_name} is not healthy after {max_retries} retries"
                
                else:
                    return False, f"Unknown service: {service_name}"
                    
            except Exception as e:
                error_msg = f"Health check failed for {service_name} (attempt {attempt + 1}): {e}"
                logger.warning(error_msg)
                
                if attempt < max_retries:
                    time.sleep(self.RETRY_DELAY)
                    continue
                
                return False, error_msg
        
        return False, f"Health check failed for {service_name} after {max_retries} retries"

    def _try_fallback(self, service_name: str) -> Tuple[bool, str]:
        """
        Try fallback mechanism for a failed service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Tuple of (success, message)
        """
        if service_name not in self._fallback_configs:
            return False, f"No fallback available for {service_name}"
        
        try:
            fallback_func = self._fallback_configs[service_name]
            return fallback_func()
        except Exception as e:
            error_msg = f"Fallback failed for {service_name}: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _redis_fallback(self) -> Tuple[bool, str]:
        """Fallback mechanism for Redis service failure."""
        try:
            # Try to start Redis with different configurations
            fallback_configs = [
                ['redis-server', '--daemonize', 'yes', '--port', '6379'],
                ['redis-server', '/etc/redis/redis.conf'],
                ['redis-server', '/usr/local/etc/redis.conf'],
            ]
            
            for config in fallback_configs:
                try:
                    result = subprocess.run(
                        config,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        return True, f"Redis started with fallback configuration: {' '.join(config)}"
                except Exception:
                    continue
            
            return False, "All Redis fallback configurations failed"
        except Exception as e:
            return False, f"Redis fallback error: {e}"

    def _postgresql_fallback(self) -> Tuple[bool, str]:
        """Fallback mechanism for PostgreSQL service failure."""
        try:
            # Try different PostgreSQL start methods
            fallback_commands = [
                ['pg_ctlcluster', '$(pg_lsclusters -h | tail -1 | cut -d" " -f1)', '$(pg_lsclusters -h | tail -1 | cut -d" " -f2)', 'start'],
                ['pg_ctl', '-D', '/var/lib/postgresql/*/main', 'start'],
                ['service', 'postgresql', 'start'],
            ]
            
            for cmd in fallback_commands:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        shell=True
                    )
                    if result.returncode == 0:
                        return True, f"PostgreSQL started with fallback command: {cmd[0]}"
                except Exception:
                    continue
            
            return False, "All PostgreSQL fallback commands failed"
        except Exception as e:
            return False, f"PostgreSQL fallback error: {e}"

    def _nginx_fallback(self) -> Tuple[bool, str]:
        """Fallback mechanism for Nginx service failure."""
        try:
            # Try to start Nginx directly
            nginx_paths = ['/usr/sbin/nginx', '/usr/local/sbin/nginx', 'nginx']
            
            for nginx_path in nginx_paths:
                try:
                    result = subprocess.run(
                        [nginx_path, '-g', 'daemon off;'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        return True, f"Nginx started directly with {nginx_path}"
                except Exception:
                    continue
            
            return False, "All Nginx fallback attempts failed"
        except Exception as e:
            return False, f"Nginx fallback error: {e}"

    def _celery_fallback(self) -> Tuple[bool, str]:
        """Fallback mechanism for Celery service failure."""
        try:
            # Try to start Celery worker directly
            celery_cmd = [
                'celery', '-A', 'webops', 'worker',
                '--loglevel=info', '--concurrency=2',
                '--without-gossip', '--without-mingle', '--without-heartbeat'
            ]
            
            result = subprocess.run(
                celery_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, "Celery started with direct command"
            else:
                return False, f"Celery fallback failed: {result.stderr}"
                
        except Exception as e:
            return False, f"Celery fallback error: {e}"

    def start_health_monitoring(self) -> None:
        """Start background health monitoring thread."""
        if self._health_check_thread and self._health_check_thread.is_alive():
            logger.info("Health monitoring already running")
            return
        
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True
        )
        self._health_check_thread.start()
        logger.info("Service health monitoring started")

    def stop_health_monitoring(self) -> None:
        """Stop background health monitoring thread."""
        if self._health_check_thread:
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=10)
            logger.info("Service health monitoring stopped")

    def _health_monitor_loop(self) -> None:
        """Main health monitoring loop."""
        while not self._stop_health_check.is_set():
            try:
                # Check all core services
                for service_name in self.CORE_UNITS.keys():
                    if self._stop_health_check.is_set():
                        break
                    
                    # Skip if auto-restart is disabled for this service
                    if not cache.get(f'service_auto_restart_{service_name}', True):
                        continue
                    
                    # Check service health with minimal retries
                    is_healthy, message = self.check_service_health_with_retry(
                        service_name, 
                        max_retries=1  # Minimal retries for monitoring
                    )
                    
                    if not is_healthy:
                        logger.warning(f"Health monitor detected unhealthy service {service_name}: {message}")
                        
                        # Try to restart the service
                        restart_success, restart_msg = self.restart_core_service(service_name)
                        if restart_success:
                            logger.info(f"Health monitor successfully restarted {service_name}: {restart_msg}")
                        else:
                            logger.error(f"Health monitor failed to restart {service_name}: {restart_msg}")
                
                # Wait for next check cycle
                self._stop_health_check.wait(self.HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
                # Wait a bit before retrying
                self._stop_health_check.wait(5)

    def ensure_celery_running(self) -> Tuple[bool, str]:
        """Ensure the Celery worker service is running; start it if not.
        Uses sudo -n to avoid interactive prompts.
        """
        unit = 'webops-celery.service'
        try:
            proc = subprocess.run(
                ['systemctl', 'is-active', unit],
                capture_output=True,
                text=True
            )
            if proc.returncode == 0:
                return True, 'Celery already running'
        except Exception:
            pass

        # Try to start without prompting for password
        try:
            subprocess.run(
                ['sudo', '-n', 'systemctl', 'start', unit],
                check=True,
                capture_output=True,
                text=True
            )
            return True, 'Celery started'
        except subprocess.CalledProcessError as e:
            return False, f"Failed to start Celery: {e.stderr.strip()}"
        except Exception as e:
            return False, f"Failed to start Celery: {e}"

        return {
            'active': is_active,
            'enabled': is_enabled,
            'status': deployment.status,
            'output': output,
        }

    def install_nginx_config(
        self,
        deployment: BaseDeployment,
        nginx_config: str
    ) -> Tuple[bool, str]:
        """
        Install Nginx configuration file.

        Args:
            deployment: Deployment instance
            nginx_config: Rendered Nginx configuration

        Returns:
            Tuple of (success, message)
        """
        config_path = Path(f"/etc/nginx/sites-available/{deployment.name}")
        enabled_path = Path(f"/etc/nginx/sites-enabled/{deployment.name}")

        try:
            # Write config file (requires sudo in production)
            config_path.write_text(nginx_config)

            # Create symlink to sites-enabled
            if not enabled_path.exists():
                enabled_path.symlink_to(config_path)

            self._log(
                deployment,
                f"Nginx configuration installed: {config_path}",
                DeploymentLog.Level.SUCCESS
            )
            return True, str(config_path)

        except PermissionError:
            error_msg = "Permission denied: requires sudo for Nginx config"
            self._log(deployment, error_msg, DeploymentLog.Level.WARNING)
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to install Nginx config: {e}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def reload_nginx(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Reload Nginx configuration.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        self._log(deployment, "Reloading Nginx configuration")

        try:
            # Test Nginx configuration first
            subprocess.run(
                ['sudo', 'nginx', '-t'],
                check=True,
                capture_output=True,
                text=True
            )

            # Reload Nginx
            subprocess.run(
                ['sudo', 'systemctl', 'reload', 'nginx'],
                check=True,
                capture_output=True
            )

            self._log(
                deployment,
                "Nginx configuration reloaded successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, "Nginx reloaded successfully"

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to reload Nginx: {e.stderr}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error reloading Nginx: {e}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def remove_service(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Remove systemd service and cleanup.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        service_path = Path(f"/etc/systemd/system/{deployment.name}.service")

        # Stop service first
        self._log(deployment, "Stopping service before removal")
        self.stop_service(deployment)

        # Disable service
        self._log(deployment, "Disabling service")
        self._run_systemctl('disable', deployment.name, check=False)

        # Remove service file
        try:
            if service_path.exists():
                service_path.unlink()

            # Reload systemd daemon
            subprocess.run(
                ['sudo', 'systemctl', 'daemon-reload'],
                check=True,
                capture_output=True
            )

            self._log(
                deployment,
                "Service removed successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, "Service removed"

        except Exception as e:
            error_msg = f"Failed to remove service: {e}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def remove_nginx_config(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Remove Nginx configuration.

        Args:
            deployment: Deployment instance

        Returns:
            Tuple of (success, message)
        """
        config_path = Path(f"/etc/nginx/sites-available/{deployment.name}")
        enabled_path = Path(f"/etc/nginx/sites-enabled/{deployment.name}")

        try:
            # Remove symlink
            if enabled_path.exists():
                enabled_path.unlink()

            # Remove config file
            if config_path.exists():
                config_path.unlink()

            # Reload Nginx
            self.reload_nginx(deployment)

            self._log(
                deployment,
                "Nginx configuration removed successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, "Nginx config removed"

        except Exception as e:
            error_msg = f"Failed to remove Nginx config: {e}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg