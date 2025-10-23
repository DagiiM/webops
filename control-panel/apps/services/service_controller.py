"""
Service Controller for centralized service management.

"Services Control System"
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
from apps.deployments.models import BaseDeployment, ApplicationDeployment
from apps.deployments.shared import ServiceManager

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

    def start_service(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Start a deployment service.

        Args:
            deployment: BaseDeployment instance to start

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
                deployment.status = BaseDeployment.Status.RUNNING
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

    def stop_service(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Stop a deployment service.

        Args:
            deployment: BaseDeployment instance to stop

        Returns:
            Result dict with success status
        """
        try:
            logger.info(f"Stopping service for deployment: {deployment.name}")

            self.service_manager.stop_service(deployment)

            # Update deployment status
            deployment.status = BaseDeployment.Status.STOPPED
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

    def restart_service(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Restart a deployment service.

        Args:
            deployment: BaseDeployment instance to restart

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
                deployment.status = BaseDeployment.Status.RUNNING
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

    def get_service_status(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Get detailed service status.

        Args:
            deployment: BaseDeployment instance

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
        deployments = ApplicationDeployment.objects.filter(
            status__in=[BaseDeployment.Status.STOPPED, BaseDeployment.Status.FAILED]
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
        deployments = ApplicationDeployment.objects.filter(status=ApplicationDeployment.Status.RUNNING)

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
        deployments = ApplicationDeployment.objects.filter(status=ApplicationDeployment.Status.RUNNING)

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
        deployments = ApplicationDeployment.objects.filter(status=ApplicationDeployment.Status.RUNNING)

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

    # =========================================================================
    # BACKGROUND PROCESSOR MANAGEMENT
    # =========================================================================

    def check_celery_workers(self) -> Dict[str, Any]:
        """
        Check Celery worker status.

        Returns:
            Celery worker status summary
        """
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # Get active workers
            active_workers = inspect.active()
            if not active_workers:
                return {
                    'healthy': False,
                    'worker_count': 0,
                    'workers': []
                }
            
            workers = []
            for worker_name, tasks in active_workers.items():
                workers.append({
                    'name': worker_name,
                    'active_tasks': len(tasks),
                    'status': 'online'
                })
            
            return {
                'healthy': len(workers) > 0,
                'worker_count': len(workers),
                'workers': workers
            }
            
        except Exception as e:
            logger.error(f"Failed to check Celery workers: {e}")
            return {
                'healthy': False,
                'worker_count': 0,
                'workers': [],
                'error': str(e)
            }

    def restart_celery_workers(self) -> Dict[str, Any]:
        """
        Restart Celery workers.

        Returns:
            Restart result
        """
        try:
            # Use systemctl to restart Celery workers
            result = subprocess.run(
                ['systemctl', 'restart', 'celery'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Celery workers restarted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr,
                    'message': f'Failed to restart Celery workers: {result.stderr}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Timeout restarting Celery workers',
                'message': 'Timeout restarting Celery workers'
            }
        except Exception as e:
            logger.error(f"Failed to restart Celery workers: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to restart Celery workers: {e}'
            }

    def restart_background_workers(self, processor) -> Dict[str, Any]:
        """
        Restart background processor workers (generic adapter).

        Args:
            processor: BackgroundProcessor instance

        Returns:
            Restart result
        """
        # Determine backend type from processor class name
        backend_name = processor.__class__.__name__.lower().replace('backgroundprocessor', '')
        
        try:
            if backend_name == 'celery':
                # Delegate to Celery-specific restart
                return self.restart_celery_workers()
            elif backend_name == 'inmemory':
                # In-memory processor doesn't need restart
                return {
                    'success': True,
                    'message': 'In-memory processor does not require restart'
                }
            else:
                return {
                    'success': False,
                    'error': f'Unknown backend: {backend_name}',
                    'message': f'Restart not implemented for backend: {backend_name}'
                }
                
        except Exception as e:
            logger.error(f"Failed to restart background workers ({backend_name}): {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to restart {backend_name} workers: {e}'
            }


    # =========================================================================
    # SSL MANAGEMENT
    # =========================================================================

    def get_ssl_status(self, deployment_id: int) -> Dict[str, Any]:
        """
        Get SSL configuration and status for a deployment.

        Args:
            deployment_id: ID of the deployment

        Returns:
            SSL configuration and status
        """
        try:
            from .models import SSLConfiguration
            
            ssl_config = SSLConfiguration.objects.filter(deployment_id=deployment_id).first()
            
            if not ssl_config:
                return {
                    'enabled': False,
                    'configured': False,
                    'message': 'SSL not configured for this deployment'
                }
            
            # Check certificate validity
            is_valid = ssl_config.is_certificate_valid()
            needs_renewal = ssl_config.needs_renewal()
            
            return {
                'enabled': ssl_config.enabled,
                'configured': True,
                'domain': ssl_config.domain,
                'certificate_type': ssl_config.certificate_type,
                'valid_until': ssl_config.valid_until.isoformat() if ssl_config.valid_until else None,
                'is_valid': is_valid,
                'needs_renewal': needs_renewal,
                'encryption_protocol': ssl_config.encryption_protocol,
                'hsts_enabled': ssl_config.hsts_enabled,
                'message': 'SSL configured and active' if is_valid else 'Certificate invalid or expired'
            }
            
        except Exception as e:
            logger.error(f"Failed to get SSL status for deployment {deployment_id}: {e}")
            return {
                'enabled': False,
                'configured': False,
                'error': str(e),
                'message': f'Error checking SSL status: {e}'
            }

    def enable_ssl(self, deployment_id: int, domain: str, certificate_type: str = 'self_signed') -> Dict[str, Any]:
        """
        Enable SSL for a deployment.

        Args:
            deployment_id: ID of the deployment
            domain: Domain name for SSL
            certificate_type: Type of certificate ('self_signed', 'lets_encrypt', 'custom')

        Returns:
            Result of SSL enable operation
        """
        try:
            from .models import SSLConfiguration
            
            # Check if SSL configuration already exists
            ssl_config, created = SSLConfiguration.objects.get_or_create(
                deployment_id=deployment_id,
                defaults={
                    'enabled': True,
                    'domain': domain,
                    'certificate_type': certificate_type,
                    'encryption_protocol': 'TLSv1.3',
                    'hsts_enabled': True
                }
            )
            
            if not created:
                ssl_config.enabled = True
                ssl_config.domain = domain
                ssl_config.certificate_type = certificate_type
                ssl_config.save()
            
            # Create SSL certificate based on type
            if certificate_type == 'self_signed':
                result = self._generate_self_signed_certificate(ssl_config)
            elif certificate_type == 'lets_encrypt':
                result = self._generate_lets_encrypt_certificate(ssl_config)
            else:
                result = {'success': True, 'message': 'Custom certificate - upload required'}
            
            if result['success']:
                # Update service configuration to use SSL
                self._update_service_ssl_config(deployment_id, ssl_config)
                
                # Log the SSL enablement
                self._log_service_action(
                    'ssl_enabled',
                    f'SSL enabled for deployment {deployment_id}',
                    {'domain': domain, 'certificate_type': certificate_type}
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to enable SSL for deployment {deployment_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to enable SSL: {e}'
            }

    def disable_ssl(self, deployment_id: int) -> Dict[str, Any]:
        """
        Disable SSL for a deployment.

        Args:
            deployment_id: ID of the deployment

        Returns:
            Result of SSL disable operation
        """
        try:
            from .models import SSLConfiguration
            
            ssl_config = SSLConfiguration.objects.filter(deployment_id=deployment_id).first()
            
            if not ssl_config:
                return {
                    'success': False,
                    'message': 'SSL not configured for this deployment'
                }
            
            ssl_config.enabled = False
            ssl_config.save()
            
            # Update service configuration to disable SSL
            self._update_service_ssl_config(deployment_id, ssl_config)
            
            # Log the SSL disablement
            self._log_service_action(
                'ssl_disabled',
                f'SSL disabled for deployment {deployment_id}',
                {'domain': ssl_config.domain}
            )
            
            return {
                'success': True,
                'message': 'SSL disabled successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to disable SSL for deployment {deployment_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to disable SSL: {e}'
            }

    def upload_ssl_certificate(self, deployment_id: int, certificate_file, private_key_file) -> Dict[str, Any]:
        """
        Upload custom SSL certificate and private key.

        Args:
            deployment_id: ID of the deployment
            certificate_file: Certificate file
            private_key_file: Private key file

        Returns:
            Result of certificate upload
        """
        try:
            from .models import SSLConfiguration
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            import ssl
            
            ssl_config = SSLConfiguration.objects.filter(deployment_id=deployment_id).first()
            
            if not ssl_config:
                return {
                    'success': False,
                    'message': 'SSL configuration not found for this deployment'
                }
            
            # Validate certificate
            try:
                cert_data = certificate_file.read()
                certificate = x509.load_pem_x509_certificate(cert_data, default_backend())
                
                # Extract certificate information
                ssl_config.valid_until = certificate.not_valid_after
                ssl_config.domain = certificate.subject.rfc4514_string()
                
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Invalid certificate file: {e}'
                }
            
            # Validate private key
            try:
                key_data = private_key_file.read()
                # Basic validation - check if it's a valid private key format
                if not (b'BEGIN PRIVATE KEY' in key_data or b'BEGIN RSA PRIVATE KEY' in key_data):
                    return {
                        'success': False,
                        'message': 'Invalid private key format'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Invalid private key file: {e}'
                }
            
            # Save files
            ssl_config.certificate_file.save(f'cert_{deployment_id}.pem', certificate_file)
            ssl_config.private_key_file.save(f'key_{deployment_id}.pem', private_key_file)
            ssl_config.certificate_type = 'custom'
            ssl_config.save()
            
            # Update service configuration
            self._update_service_ssl_config(deployment_id, ssl_config)
            
            return {
                'success': True,
                'message': 'Certificate uploaded successfully',
                'valid_until': ssl_config.valid_until.isoformat() if ssl_config.valid_until else None,
                'domain': ssl_config.domain
            }
            
        except Exception as e:
            logger.error(f"Failed to upload SSL certificate for deployment {deployment_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to upload certificate: {e}'
            }

    def _generate_self_signed_certificate(self, ssl_config) -> Dict[str, Any]:
        """
        Generate a self-signed SSL certificate.

        Args:
            ssl_config: SSLConfiguration instance

        Returns:
            Result of certificate generation
        """
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.backends import default_backend
            import datetime
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            # Generate certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"State"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, u"City"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"WebOps"),
                x509.NameAttribute(NameOID.COMMON_NAME, ssl_config.domain),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.datetime.utcnow()
            ).not_valid_after(
                datetime.datetime.utcnow() + datetime.timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([x509.DNSName(ssl_config.domain)]),
                critical=False,
            ).sign(private_key, hashes.SHA256(), default_backend())
            
            # Save certificate and key
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            )
            
            from django.core.files.base import ContentFile
            ssl_config.certificate_file.save(f'self_signed_cert_{ssl_config.id}.pem', ContentFile(cert_pem))
            ssl_config.private_key_file.save(f'self_signed_key_{ssl_config.id}.pem', ContentFile(key_pem))
            ssl_config.valid_until = cert.not_valid_after
            ssl_config.save()
            
            return {
                'success': True,
                'message': 'Self-signed certificate generated successfully',
                'valid_until': ssl_config.valid_until.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate self-signed certificate: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to generate self-signed certificate: {e}'
            }

    def _generate_lets_encrypt_certificate(self, ssl_config) -> Dict[str, Any]:
        """
        Generate Let's Encrypt certificate (placeholder for now).

        Args:
            ssl_config: SSLConfiguration instance

        Returns:
            Result of certificate generation
        """
        # This is a placeholder - in a real implementation, you would integrate
        # with Let's Encrypt ACME protocol
        return {
            'success': False,
            'message': 'Let\'s Encrypt integration not yet implemented. Please use self-signed or custom certificates.'
        }

    def validate_ssl_certificate(self, ssl_config) -> Dict[str, Any]:
        """
        Validate SSL certificate configuration.

        Args:
            ssl_config: SSLConfiguration instance

        Returns:
            Validation result
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            from datetime import datetime
            
            # Check if certificate file exists
            if not ssl_config.certificate_file:
                return {
                    'valid': False,
                    'error': 'No certificate file found'
                }
            
            # Check if private key file exists
            if not ssl_config.private_key_file:
                return {
                    'valid': False,
                    'error': 'No private key file found'
                }
            
            # Validate certificate
            try:
                cert_data = ssl_config.certificate_file.read()
                certificate = x509.load_pem_x509_certificate(cert_data, default_backend())
                
                # Check if certificate is expired
                now = datetime.now()
                if certificate.not_valid_after < now:
                    return {
                        'valid': False,
                        'error': 'Certificate has expired'
                    }
                
                # Check if certificate is not yet valid
                if certificate.not_valid_before > now:
                    return {
                        'valid': False,
                        'error': 'Certificate is not yet valid'
                    }
                
                # Extract certificate information
                cert_info = {
                    'subject': str(certificate.subject),
                    'issuer': str(certificate.issuer),
                    'expires_at': certificate.not_valid_after.isoformat(),
                    'domain': str(certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value) if certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME) else ''
                }
                
                # Validate private key format
                key_data = ssl_config.private_key_file.read()
                if not (b'BEGIN PRIVATE KEY' in key_data or b'BEGIN RSA PRIVATE KEY' in key_data):
                    return {
                        'valid': False,
                        'error': 'Invalid private key format'
                    }
                
                return {
                    'valid': True,
                    'message': 'Certificate is valid',
                    'certificate_info': cert_info
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Invalid certificate: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"Failed to validate SSL certificate: {e}")
            return {
                'valid': False,
                'error': f'Validation failed: {str(e)}'
            }

    def _update_service_ssl_config(self, deployment_id: int, ssl_config) -> None:
        """
        Update service configuration to use SSL settings.

        Args:
            deployment_id: ID of the deployment
            ssl_config: SSLConfiguration instance
        """
        # This would integrate with your deployment configuration system
        # For now, it's a placeholder that would update nginx/apache configs
        logger.info(f"Updating SSL configuration for deployment {deployment_id}")

    def _log_service_action(self, action: str, message: str, details: Dict[str, Any] = None) -> None:
        """
        Log service actions for audit purposes.

        Args:
            action: Action type
            message: Action message
            details: Additional details
        """
        logger.info(f"Service Action: {action} - {message}")
        if details:
            logger.info(f"Details: {details}")


# Singleton instance
service_controller = ServiceController()
