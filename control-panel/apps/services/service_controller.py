"""
Service Controller for centralized service management.

Reference: CLAUDE.md "Services Control System"
Architecture: Centralized control for deployments, Celery workers, and system services

This module provides:
- Service lifecycle management (start, stop, restart)
- Health monitoring and auto-recovery
- Celery worker management
- Configuration management
- Service dependency resolution
"""

from typing import Dict, Any, List, Optional, Tuple
import subprocess
import logging
import psutil
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import ServiceStatus, Alert, ResourceUsage
from .monitoring import SystemMonitor
from apps.deployments.models import Deployment
from apps.deployments.service_manager import ServiceManager

logger = logging.getLogger(__name__)


class ServiceControlError(Exception):
    """Base exception for service control errors."""
    pass


class ServiceController:
    """
    Centralized controller for managing all WebOps services.

    Handles:
    - Deployment services (user applications)
    - Celery workers (background tasks)
    - System services (monitoring, cleanup)
    - Health checks and auto-recovery
    """

    def __init__(self):
        self.service_manager = ServiceManager()
        self.system_monitor = SystemMonitor()

    # =========================================================================
    # DEPLOYMENT SERVICE CONTROL
    # =========================================================================

    def start_service(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Start a deployment service.

        Args:
            deployment: Deployment instance to start

        Returns:
            Result dict with success status and details
        """
        try:
            logger.info(f"Starting service for deployment: {deployment.name}")

            # Use ServiceManager to start
            self.service_manager.start_service(deployment)

            # Wait a moment for service to stabilize
            import time
            time.sleep(2)

            # Check if it's actually running
            status = self.system_monitor.check_service_status(deployment)

            if status.status == ServiceStatus.Status.RUNNING:
                # Update deployment status
                deployment.status = Deployment.Status.RUNNING
                deployment.save(update_fields=['status'])

                logger.info(f"Service started successfully: {deployment.name}")
                return {
                    'success': True,
                    'message': f'Service {deployment.name} started successfully',
                    'status': status.status,
                    'pid': status.pid
                }
            else:
                raise ServiceControlError(f"Service failed to start: {status.status}")

        except Exception as e:
            logger.error(f"Failed to start service {deployment.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to start service: {e}'
            }

    def stop_service(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Stop a deployment service.

        Args:
            deployment: Deployment instance to stop

        Returns:
            Result dict with success status
        """
        try:
            logger.info(f"Stopping service for deployment: {deployment.name}")

            self.service_manager.stop_service(deployment)

            # Update deployment status
            deployment.status = Deployment.Status.STOPPED
            deployment.save(update_fields=['status'])

            # Update service status
            status = self.system_monitor.check_service_status(deployment)

            logger.info(f"Service stopped successfully: {deployment.name}")
            return {
                'success': True,
                'message': f'Service {deployment.name} stopped successfully',
                'status': status.status
            }

        except Exception as e:
            logger.error(f"Failed to stop service {deployment.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to stop service: {e}'
            }

    def restart_service(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Restart a deployment service.

        Args:
            deployment: Deployment instance to restart

        Returns:
            Result dict with success status
        """
        try:
            logger.info(f"Restarting service for deployment: {deployment.name}")

            self.service_manager.restart_service(deployment)

            # Wait for service to stabilize
            import time
            time.sleep(2)

            # Check status
            status = self.system_monitor.check_service_status(deployment)

            if status.status == ServiceStatus.Status.RUNNING:
                # Update deployment status
                deployment.status = Deployment.Status.RUNNING
                deployment.save(update_fields=['status'])

                # Increment restart count
                if hasattr(status, 'restart_count'):
                    status.restart_count += 1
                    status.save(update_fields=['restart_count'])

                logger.info(f"Service restarted successfully: {deployment.name}")
                return {
                    'success': True,
                    'message': f'Service {deployment.name} restarted successfully',
                    'status': status.status,
                    'restart_count': status.restart_count
                }
            else:
                raise ServiceControlError(f"Service failed to restart: {status.status}")

        except Exception as e:
            logger.error(f"Failed to restart service {deployment.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to restart service: {e}'
            }

    def get_service_status(self, deployment: Deployment) -> Dict[str, Any]:
        """
        Get detailed service status.

        Args:
            deployment: Deployment instance

        Returns:
            Status dict with details
        """
        status = self.system_monitor.check_service_status(deployment)

        return {
            'deployment_id': deployment.id,
            'deployment_name': deployment.name,
            'status': status.status,
            'pid': status.pid,
            'memory_mb': status.memory_mb,
            'cpu_percent': status.cpu_percent,
            'uptime_seconds': status.uptime_seconds,
            'restart_count': status.restart_count,
            'last_checked': status.last_checked.isoformat()
        }

    # =========================================================================
    # CELERY WORKER MANAGEMENT
    # =========================================================================

    def check_celery_workers(self) -> Dict[str, Any]:
        """
        Check status of Celery workers.

        Returns:
            Dict with worker status and details
        """
        try:
            # Check if Celery workers are running
            result = subprocess.run(
                ['pgrep', '-f', 'celery worker'],
                capture_output=True,
                text=True,
                timeout=5
            )

            worker_pids = result.stdout.strip().split('\n') if result.stdout.strip() else []
            worker_count = len([pid for pid in worker_pids if pid])

            # Get worker details
            workers = []
            for pid_str in worker_pids:
                if pid_str:
                    try:
                        pid = int(pid_str)
                        process = psutil.Process(pid)
                        workers.append({
                            'pid': pid,
                            'name': process.name(),
                            'status': process.status(),
                            'memory_mb': process.memory_info().rss / (1024 * 1024),
                            'cpu_percent': process.cpu_percent(interval=0.1),
                            'created': process.create_time()
                        })
                    except (psutil.NoSuchProcess, ValueError):
                        continue

            # Check Celery beat (scheduler)
            beat_result = subprocess.run(
                ['pgrep', '-f', 'celery beat'],
                capture_output=True,
                text=True,
                timeout=5
            )
            beat_running = bool(beat_result.stdout.strip())

            return {
                'success': True,
                'worker_count': worker_count,
                'workers': workers,
                'beat_running': beat_running,
                'healthy': worker_count > 0
            }

        except Exception as e:
            logger.error(f"Failed to check Celery workers: {e}")
            return {
                'success': False,
                'error': str(e),
                'worker_count': 0,
                'healthy': False
            }

    def restart_celery_workers(self) -> Dict[str, Any]:
        """
        Restart Celery workers.

        Returns:
            Result dict
        """
        try:
            logger.info("Restarting Celery workers")

            # Stop existing workers
            subprocess.run(
                ['pkill', '-f', 'celery worker'],
                timeout=10
            )

            # Wait for graceful shutdown
            import time
            time.sleep(3)

            # Start workers using the start script
            start_script = settings.BASE_DIR / 'start_celery.sh'
            if start_script.exists():
                subprocess.Popen(
                    [str(start_script)],
                    cwd=settings.BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                # Wait for startup
                time.sleep(2)

                # Verify workers started
                status = self.check_celery_workers()

                if status['healthy']:
                    logger.info("Celery workers restarted successfully")
                    return {
                        'success': True,
                        'message': 'Celery workers restarted successfully',
                        'worker_count': status['worker_count']
                    }
                else:
                    raise ServiceControlError("Workers failed to start after restart")
            else:
                raise ServiceControlError(f"Start script not found: {start_script}")

        except Exception as e:
            logger.error(f"Failed to restart Celery workers: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to restart workers: {e}'
            }

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    def start_all_services(self) -> Dict[str, Any]:
        """
        Start all stopped deployment services.

        Returns:
            Summary of operations
        """
        deployments = Deployment.objects.filter(
            status__in=[Deployment.Status.STOPPED, Deployment.Status.FAILED]
        )

        results = []
        for deployment in deployments:
            result = self.start_service(deployment)
            results.append({
                'deployment': deployment.name,
                'result': result
            })

        success_count = len([r for r in results if r['result']['success']])

        return {
            'success': True,
            'total': len(results),
            'started': success_count,
            'failed': len(results) - success_count,
            'results': results
        }

    def stop_all_services(self) -> Dict[str, Any]:
        """
        Stop all running deployment services.

        Returns:
            Summary of operations
        """
        deployments = Deployment.objects.filter(status=Deployment.Status.RUNNING)

        results = []
        for deployment in deployments:
            result = self.stop_service(deployment)
            results.append({
                'deployment': deployment.name,
                'result': result
            })

        success_count = len([r for r in results if r['result']['success']])

        return {
            'success': True,
            'total': len(results),
            'stopped': success_count,
            'failed': len(results) - success_count,
            'results': results
        }

    def restart_all_services(self) -> Dict[str, Any]:
        """
        Restart all running deployment services.

        Returns:
            Summary of operations
        """
        deployments = Deployment.objects.filter(status=Deployment.Status.RUNNING)

        results = []
        for deployment in deployments:
            result = self.restart_service(deployment)
            results.append({
                'deployment': deployment.name,
                'result': result
            })

        success_count = len([r for r in results if r['result']['success']])

        return {
            'success': True,
            'total': len(results),
            'restarted': success_count,
            'failed': len(results) - success_count,
            'results': results
        }

    # =========================================================================
    # HEALTH CHECK & AUTO-RECOVERY
    # =========================================================================

    def perform_health_checks(self, auto_restart: bool = False) -> Dict[str, Any]:
        """
        Perform health checks on all running services.

        Args:
            auto_restart: Whether to automatically restart failed services

        Returns:
            Health check results
        """
        deployments = Deployment.objects.filter(status=Deployment.Status.RUNNING)

        results = []
        unhealthy = []

        for deployment in deployments:
            # Check service status
            status = self.system_monitor.check_service_status(deployment)

            # Perform HTTP health check if applicable
            health_check = self.system_monitor.perform_health_check(deployment)

            is_healthy = (
                status.status == ServiceStatus.Status.RUNNING and
                (health_check is None or health_check.is_healthy)
            )

            result = {
                'deployment': deployment.name,
                'deployment_id': deployment.id,
                'healthy': is_healthy,
                'service_status': status.status,
                'http_check': {
                    'healthy': health_check.is_healthy if health_check else None,
                    'status_code': health_check.status_code if health_check else None,
                    'response_time_ms': health_check.response_time_ms if health_check else None
                } if health_check else None
            }

            results.append(result)

            if not is_healthy:
                unhealthy.append(deployment)

        # Auto-restart unhealthy services if enabled
        restart_results = []
        if auto_restart and unhealthy:
            logger.info(f"Auto-restarting {len(unhealthy)} unhealthy services")
            for deployment in unhealthy:
                restart_result = self.restart_service(deployment)
                restart_results.append({
                    'deployment': deployment.name,
                    'restart_result': restart_result
                })

        return {
            'success': True,
            'total_checked': len(results),
            'healthy': len(results) - len(unhealthy),
            'unhealthy': len(unhealthy),
            'results': results,
            'auto_restart_enabled': auto_restart,
            'restart_results': restart_results
        }

    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check.

        Returns:
            Complete system health status
        """
        # Get resource metrics
        metrics = self.system_monitor.get_latest_metrics()
        if not metrics:
            metrics = self.system_monitor.collect_metrics()

        # Check Celery workers
        celery_status = self.check_celery_workers()

        # Check deployment services
        deployment_health = self.perform_health_checks(auto_restart=False)

        # Count unacknowledged alerts
        alert_count = Alert.objects.filter(is_acknowledged=False).count()
        critical_alerts = Alert.objects.filter(
            is_acknowledged=False,
            severity=Alert.Severity.CRITICAL
        ).count()

        # Overall health determination
        is_healthy = (
            metrics.cpu_percent < 90 and
            metrics.memory_percent < 95 and
            metrics.disk_percent < 95 and
            celery_status['healthy'] and
            critical_alerts == 0
        )

        return {
            'healthy': is_healthy,
            'timestamp': timezone.now().isoformat(),
            'resources': {
                'cpu_percent': metrics.cpu_percent,
                'memory_percent': metrics.memory_percent,
                'disk_percent': metrics.disk_percent,
                'load_average_1m': metrics.load_average_1m,
            },
            'celery': celery_status,
            'deployments': deployment_health,
            'alerts': {
                'total': alert_count,
                'critical': critical_alerts
            }
        }

    # =========================================================================
    # SYSTEM SERVICES
    # =========================================================================

    def get_system_services_status(self) -> Dict[str, Any]:
        """
        Check status of system services (Nginx, PostgreSQL, Redis).

        Returns:
            Status of system services
        """
        services = ['nginx', 'postgresql', 'redis-server']
        statuses = {}

        for service in services:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                statuses[service] = {
                    'active': result.stdout.strip() == 'active',
                    'status': result.stdout.strip()
                }
            except Exception as e:
                statuses[service] = {
                    'active': False,
                    'status': 'error',
                    'error': str(e)
                }

        all_healthy = all(s['active'] for s in statuses.values())

        return {
            'success': True,
            'healthy': all_healthy,
            'services': statuses
        }


# Singleton instance
service_controller = ServiceController()
