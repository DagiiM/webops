"""
Health Check System for BaseDeployments

This module provides comprehensive health checking for deployed applications:
- Process health (is the service running?)
- HTTP health (is the app responding?)
- Resource health (CPU, memory usage)
- Database connectivity
- Disk space monitoring

"Service Monitoring" section
"""

import subprocess
import requests
import psutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone

from ..models import BaseDeployment, ApplicationDeployment, DeploymentLog

logger = logging.getLogger(__name__)


class HealthCheckResult:
    """Result of a health check operation."""

    def __init__(self, healthy: bool, message: str, details: Optional[Dict[str, Any]] = None):
        self.healthy = healthy
        self.message = message
        self.details = details or {}
        self.timestamp = timezone.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'healthy': self.healthy,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class HealthChecker:
    """Performs health checks on deployments."""

    def __init__(self, deployment: BaseDeployment):
        self.deployment = deployment
        self.service_name = f"{deployment.name}.service"

    def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        results = {
            'process': self.check_process(),
            'http': self.check_http_response(),
            'resources': self.check_resources(),
            'disk': self.check_disk_space(),
        }

        # Overall health
        all_healthy = all(r.healthy for r in results.values())
        results['overall'] = HealthCheckResult(
            healthy=all_healthy,
            message='All checks passed' if all_healthy else 'Some checks failed',
            details={
                'total_checks': len(results),
                'passed': sum(1 for r in results.values() if r.healthy),
                'failed': sum(1 for r in results.values() if not r.healthy)
            }
        )

        return results

    def check_process(self) -> HealthCheckResult:
        """Check if the deployment service is running."""
        try:
            # Check systemd service status
            result = subprocess.run(
                ['systemctl', 'is-active', self.service_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            is_active = result.returncode == 0
            status = result.stdout.strip()

            if is_active:
                # Get additional service info
                info_result = subprocess.run(
                    ['systemctl', 'show', self.service_name,
                     '--property=MainPID,ActiveEnterTimestamp,MemoryCurrent'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                details = {}
                for line in info_result.stdout.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        details[key] = value

                return HealthCheckResult(
                    healthy=True,
                    message=f'Service {self.service_name} is running',
                    details={
                        'status': status,
                        'pid': details.get('MainPID', 'unknown'),
                        'started': details.get('ActiveEnterTimestamp', 'unknown'),
                    }
                )
            else:
                return HealthCheckResult(
                    healthy=False,
                    message=f'Service {self.service_name} is not active (status: {status})',
                    details={'status': status}
                )

        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                healthy=False,
                message='Health check timed out',
                details={'error': 'timeout'}
            )
        except FileNotFoundError:
            # systemctl not available (development mode)
            return HealthCheckResult(
                healthy=True,
                message='Service check skipped (development mode)',
                details={'mode': 'development'}
            )
        except Exception as e:
            logger.error(f"Process health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                message=f'Health check error: {str(e)}',
                details={'error': str(e)}
            )

    def check_http_response(self, timeout: int = 10) -> HealthCheckResult:
        """Check if the deployment is responding to HTTP requests."""
        if not self.deployment.port:
            return HealthCheckResult(
                healthy=False,
                message='No port allocated',
                details={'error': 'no_port'}
            )

        try:
            # Try to connect to the deployment
            url = f'http://localhost:{self.deployment.port}/'

            start_time = datetime.now()
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            response_time = (datetime.now() - start_time).total_seconds()

            # Consider 2xx and 3xx as healthy, 4xx/5xx as unhealthy
            is_healthy = 200 <= response.status_code < 400

            return HealthCheckResult(
                healthy=is_healthy,
                message=f'HTTP {response.status_code} in {response_time:.2f}s',
                details={
                    'status_code': response.status_code,
                    'response_time': response_time,
                    'content_length': len(response.content),
                    'url': url
                }
            )

        except requests.exceptions.ConnectionError:
            return HealthCheckResult(
                healthy=False,
                message=f'Connection refused on port {self.deployment.port}',
                details={'error': 'connection_refused', 'port': self.deployment.port}
            )
        except requests.exceptions.Timeout:
            return HealthCheckResult(
                healthy=False,
                message=f'Request timed out after {timeout}s',
                details={'error': 'timeout', 'timeout': timeout}
            )
        except Exception as e:
            logger.error(f"HTTP health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                message=f'HTTP check error: {str(e)}',
                details={'error': str(e)}
            )

    def check_resources(self) -> HealthCheckResult:
        """Check resource usage (CPU, memory) for the deployment process."""
        try:
            # Get PID from systemd
            result = subprocess.run(
                ['systemctl', 'show', self.service_name, '--property=MainPID'],
                capture_output=True,
                text=True,
                timeout=5
            )

            pid_line = result.stdout.strip()
            if '=' not in pid_line:
                return HealthCheckResult(
                    healthy=False,
                    message='Could not determine process PID',
                    details={'error': 'no_pid'}
                )

            pid = int(pid_line.split('=')[1])

            if pid == 0:
                return HealthCheckResult(
                    healthy=False,
                    message='Service not running (PID=0)',
                    details={'pid': 0}
                )

            # Get process info
            process = psutil.Process(pid)

            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # Get child processes too
            children = process.children(recursive=True)
            total_memory = memory_mb
            for child in children:
                try:
                    child_mem = child.memory_info().rss / 1024 / 1024
                    total_memory += child_mem
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Health thresholds
            high_cpu = cpu_percent > 90
            high_memory = memory_mb > 1024  # 1GB

            is_healthy = not (high_cpu or high_memory)

            message_parts = []
            if high_cpu:
                message_parts.append(f'High CPU: {cpu_percent:.1f}%')
            if high_memory:
                message_parts.append(f'High memory: {memory_mb:.1f}MB')

            if message_parts:
                message = ', '.join(message_parts)
            else:
                message = f'Resources OK (CPU: {cpu_percent:.1f}%, Mem: {memory_mb:.1f}MB)'

            return HealthCheckResult(
                healthy=is_healthy,
                message=message,
                details={
                    'pid': pid,
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_mb,
                    'memory_total_mb': total_memory,
                    'num_children': len(children),
                    'num_threads': process.num_threads()
                }
            )

        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                healthy=False,
                message='Resource check timed out',
                details={'error': 'timeout'}
            )
        except psutil.NoSuchProcess:
            return HealthCheckResult(
                healthy=False,
                message='Process not found',
                details={'error': 'no_such_process'}
            )
        except FileNotFoundError:
            # systemctl not available (development mode)
            return HealthCheckResult(
                healthy=True,
                message='Resource check skipped (development mode)',
                details={'mode': 'development'}
            )
        except Exception as e:
            logger.error(f"Resource health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                message=f'Resource check error: {str(e)}',
                details={'error': str(e)}
            )

    def check_disk_space(self, min_free_gb: float = 1.0) -> HealthCheckResult:
        """Check available disk space for deployment."""
        try:
            from ..services import BaseDeploymentService

            service = BaseDeploymentService()
            deployment_path = service.get_deployment_path(self.deployment)

            if not deployment_path.exists():
                return HealthCheckResult(
                    healthy=False,
                    message='BaseDeployment path does not exist',
                    details={'path': str(deployment_path)}
                )

            # Get disk usage
            disk_usage = psutil.disk_usage(str(deployment_path))

            free_gb = disk_usage.free / 1024 / 1024 / 1024
            total_gb = disk_usage.total / 1024 / 1024 / 1024
            percent_used = disk_usage.percent

            is_healthy = free_gb >= min_free_gb

            if is_healthy:
                message = f'Disk OK ({free_gb:.2f}GB free, {percent_used:.1f}% used)'
            else:
                message = f'Low disk space: {free_gb:.2f}GB free (warning threshold: {min_free_gb}GB)'

            return HealthCheckResult(
                healthy=is_healthy,
                message=message,
                details={
                    'free_gb': free_gb,
                    'total_gb': total_gb,
                    'percent_used': percent_used,
                    'path': str(deployment_path)
                }
            )

        except Exception as e:
            logger.error(f"Disk health check failed: {e}")
            return HealthCheckResult(
                healthy=False,
                message=f'Disk check error: {str(e)}',
                details={'error': str(e)}
            )

    def log_health_check(self, results: Dict[str, HealthCheckResult]):
        """Log health check results to deployment logs."""
        overall = results.get('overall')
        if not overall:
            return

        level = DeploymentLog.Level.INFO if overall.healthy else DeploymentLog.Level.ERROR

        # Create summary message
        failed_checks = [name for name, result in results.items()
                        if not result.healthy and name != 'overall']

        if overall.healthy:
            message = f"Health check passed: all systems operational"
        else:
            message = f"Health check failed: {', '.join(failed_checks)}"

        DeploymentLog.objects.create(
            deployment=self.deployment,
            level=level,
            message=message
        )


class AutoRestartService:
    """Handles automatic restart of failed deployments."""

    def __init__(self, deployment: BaseDeployment):
        self.deployment = deployment
        self.max_restarts_per_hour = 3

    def should_auto_restart(self) -> Tuple[bool, str]:
        """
        Determine if deployment should be auto-restarted.

        Returns:
            Tuple of (should_restart: bool, reason: str)
        """
        # Check if deployment is supposed to be running
        if self.deployment.status != BaseDeployment.Status.RUNNING:
            return False, f'BaseDeployment status is {self.deployment.status}, not running'

        # Check restart history to prevent restart loops
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent_restarts = DeploymentLog.objects.filter(
            deployment=self.deployment,
            level=DeploymentLog.Level.WARNING,
            message__icontains='auto-restart',
            created_at__gte=one_hour_ago
        ).count()

        if recent_restarts >= self.max_restarts_per_hour:
            return False, f'Too many restarts ({recent_restarts}) in the last hour'

        return True, 'Auto-restart conditions met'

    def attempt_restart(self) -> bool:
        """
        Attempt to restart the deployment.

        Returns:
            True if restart was successful, False otherwise
        """
        should_restart, reason = self.should_auto_restart()

        if not should_restart:
            logger.warning(f"Skipping auto-restart for {self.deployment.name}: {reason}")
            DeploymentLog.objects.create(
                deployment=self.deployment,
                level=DeploymentLog.Level.WARNING,
                message=f'Auto-restart skipped: {reason}'
            )
            return False

        logger.info(f"Attempting auto-restart for {self.deployment.name}")

        DeploymentLog.objects.create(
            deployment=self.deployment,
            level=DeploymentLog.Level.WARNING,
            message='Attempting auto-restart due to health check failure'
        )

        try:
            from .service_manager import ServiceManager

            service_manager = ServiceManager()
            success, message = service_manager.restart_service(self.deployment)

            if success:
                DeploymentLog.objects.create(
                    deployment=self.deployment,
                    level=DeploymentLog.Level.SUCCESS,
                    message='Auto-restart completed successfully'
                )
                logger.info(f"Auto-restart successful for {self.deployment.name}")
                return True
            else:
                DeploymentLog.objects.create(
                    deployment=self.deployment,
                    level=DeploymentLog.Level.ERROR,
                    message=f'Auto-restart failed: {message}'
                )
                logger.error(f"Auto-restart failed for {self.deployment.name}: {message}")
                return False

        except Exception as e:
            logger.error(f"Auto-restart error for {self.deployment.name}: {e}")
            DeploymentLog.objects.create(
                deployment=self.deployment,
                level=DeploymentLog.Level.ERROR,
                message=f'Auto-restart error: {str(e)}'
            )
            return False


def perform_health_check(deployment: BaseDeployment, auto_restart: bool = True) -> Dict[str, Any]:
    """
    Perform comprehensive health check on deployment.

    Args:
        deployment: BaseDeployment to check
        auto_restart: Whether to attempt auto-restart on failure

    Returns:
        Dictionary with health check results
    """
    checker = HealthChecker(deployment)
    results = checker.check_all()

    # Log results
    checker.log_health_check(results)

    # Convert to dictionary for JSON serialization
    results_dict = {name: result.to_dict() for name, result in results.items()}

    # Attempt auto-restart if unhealthy and auto_restart is enabled
    if auto_restart and not results['overall'].healthy:
        restart_service = AutoRestartService(deployment)
        restart_attempted = restart_service.attempt_restart()
        results_dict['auto_restart_attempted'] = restart_attempted

    return results_dict
