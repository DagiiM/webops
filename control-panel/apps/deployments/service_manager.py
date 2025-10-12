"""
Service management for WebOps deployments.

Reference: CLAUDE.md "Service Management" section

This module implements systemd service management:
- Service start/stop/restart
- Service status checking
- Nginx configuration reload
- Service installation and enablement
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from django.conf import settings

from .models import Deployment, DeploymentLog

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manager for systemd service operations."""

    def __init__(self):
        """Initialize service manager."""
        pass
    CORE_UNITS = {
        'nginx': ['nginx.service', 'nginx'],
        'postgresql': ['postgresql.service', 'postgresql'],
        'redis': ['redis-server.service', 'redis.service', 'redis-server', 'redis'],
        'celery': ['webops-celery.service'],
        'celerybeat': ['webops-celerybeat.service'],
        'web': ['webops-web.service'],
    }

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
        deployment: Deployment,
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
        deployment: Deployment,
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

    def enable_service(self, deployment: Deployment) -> Tuple[bool, str]:
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

    def start_service(self, deployment: Deployment) -> Tuple[bool, str]:
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
            deployment.status = Deployment.Status.RUNNING
            deployment.save(update_fields=['status'])

            self._log(
                deployment,
                f"Service {deployment.name} started successfully",
                DeploymentLog.Level.SUCCESS
            )
            return True, f"Service {deployment.name} started"
        else:
            deployment.status = Deployment.Status.FAILED
            deployment.save(update_fields=['status'])

            error_msg = f"Failed to start service: {output}"
            self._log(deployment, error_msg, DeploymentLog.Level.ERROR)
            return False, error_msg

    def stop_service(self, deployment: Deployment) -> Tuple[bool, str]:
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
            deployment.status = Deployment.Status.STOPPED
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

    def restart_service(self, deployment: Deployment) -> Tuple[bool, str]:
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
            deployment.status = Deployment.Status.RUNNING
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

    def get_service_status(self, deployment: Deployment) -> Dict[str, Any]:
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
        deployment: Deployment,
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

    def reload_nginx(self, deployment: Deployment) -> Tuple[bool, str]:
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

    def remove_service(self, deployment: Deployment) -> Tuple[bool, str]:
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

    def remove_nginx_config(self, deployment: Deployment) -> Tuple[bool, str]:
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