"""
System monitoring service for WebOps.

Reference: CLAUDE.md "Services" section
Architecture: Real-time system monitoring using psutil
"""

from typing import Dict, Any, List, Optional
import psutil
import subprocess
from django.utils import timezone
from .models import ResourceUsage, ServiceStatus, Alert, HealthCheck
from apps.deployments.models import Deployment
import requests
import logging

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Monitor system resources and health."""

    def __init__(self):
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
        }

    def collect_metrics(self) -> ResourceUsage:
        """Collect current system metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used // (1024 * 1024)
        memory_total_mb = memory.total // (1024 * 1024)

        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_total_gb = disk.total / (1024 * 1024 * 1024)

        # Network
        network = psutil.net_io_counters()
        network_sent_mb = network.bytes_sent / (1024 * 1024)
        network_recv_mb = network.bytes_recv / (1024 * 1024)

        # Connections
        try:
            active_connections = len(psutil.net_connections())
        except (PermissionError, psutil.AccessDenied):
            active_connections = 0

        # Load average (Unix only)
        try:
            load_avg = psutil.getloadavg()
            load_average_1m, load_average_5m, load_average_15m = load_avg
        except (AttributeError, OSError):
            load_average_1m = load_average_5m = load_average_15m = 0.0

        # Create usage record
        usage = ResourceUsage.objects.create(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            active_connections=active_connections,
            load_average_1m=load_average_1m,
            load_average_5m=load_average_5m,
            load_average_15m=load_average_15m,
        )

        # Check thresholds and create alerts
        self._check_thresholds(usage)

        return usage

    def _check_thresholds(self, usage: ResourceUsage) -> None:
        """Check resource thresholds and create alerts."""
        # CPU alert
        if usage.cpu_percent > self.alert_thresholds['cpu_percent']:
            self._create_alert(
                alert_type=Alert.AlertType.CPU_HIGH,
                severity=Alert.Severity.WARNING if usage.cpu_percent < 90 else Alert.Severity.ERROR,
                title=f'High CPU Usage: {usage.cpu_percent:.1f}%',
                message=f'System CPU usage is at {usage.cpu_percent:.1f}%, above threshold of {self.alert_thresholds["cpu_percent"]}%',
                metadata={'cpu_percent': usage.cpu_percent}
            )

        # Memory alert
        if usage.memory_percent > self.alert_thresholds['memory_percent']:
            self._create_alert(
                alert_type=Alert.AlertType.MEMORY_HIGH,
                severity=Alert.Severity.WARNING if usage.memory_percent < 95 else Alert.Severity.CRITICAL,
                title=f'High Memory Usage: {usage.memory_percent:.1f}%',
                message=f'System memory usage is at {usage.memory_percent:.1f}%, above threshold of {self.alert_thresholds["memory_percent"]}%',
                metadata={
                    'memory_percent': usage.memory_percent,
                    'memory_used_mb': usage.memory_used_mb,
                    'memory_total_mb': usage.memory_total_mb
                }
            )

        # Disk alert
        if usage.disk_percent > self.alert_thresholds['disk_percent']:
            self._create_alert(
                alert_type=Alert.AlertType.DISK_HIGH,
                severity=Alert.Severity.CRITICAL,
                title=f'High Disk Usage: {usage.disk_percent:.1f}%',
                message=f'System disk usage is at {usage.disk_percent:.1f}%, above threshold of {self.alert_thresholds["disk_percent"]}%',
                metadata={
                    'disk_percent': usage.disk_percent,
                    'disk_used_gb': usage.disk_used_gb,
                    'disk_total_gb': usage.disk_total_gb
                }
            )

    def _create_alert(self, alert_type: str, severity: str, title: str, message: str, metadata: Dict[str, Any], deployment: Optional[Deployment] = None) -> Alert:
        """Create an alert if one doesn't already exist for this issue."""
        # Check if similar unacknowledged alert exists (within last hour)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        existing = Alert.objects.filter(
            alert_type=alert_type,
            is_acknowledged=False,
            created_at__gte=one_hour_ago
        ).first()

        if not existing:
            return Alert.objects.create(
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                metadata=metadata,
                deployment=deployment
            )
        return existing

    def get_latest_metrics(self) -> Optional[ResourceUsage]:
        """Get the most recent resource usage snapshot."""
        return ResourceUsage.objects.first()

    def get_metrics_history(self, hours: int = 24) -> List[ResourceUsage]:
        """Get resource usage history for specified hours."""
        cutoff = timezone.now() - timezone.timedelta(hours=hours)
        return list(ResourceUsage.objects.filter(created_at__gte=cutoff))

    def check_service_status(self, deployment: Deployment) -> ServiceStatus:
        """Check status of a deployed service."""
        service_name = f"webops-{deployment.name}"

        try:
            # Check systemd service status
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            is_active = result.stdout.strip() == 'active'

            # Get service details if running
            pid = None
            memory_mb = 0.0
            cpu_percent = 0.0
            uptime_seconds = 0

            if is_active:
                # Get PID
                pid_result = subprocess.run(
                    ['systemctl', 'show', service_name, '--property=MainPID'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                pid_line = pid_result.stdout.strip()
                if pid_line.startswith('MainPID='):
                    pid = int(pid_line.split('=')[1])

                # Get process stats if we have PID
                if pid and pid > 0:
                    try:
                        process = psutil.Process(pid)
                        memory_mb = process.memory_info().rss / (1024 * 1024)
                        cpu_percent = process.cpu_percent(interval=0.1)
                        uptime_seconds = int(timezone.now().timestamp() - process.create_time())
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            # Determine status
            if is_active:
                status = ServiceStatus.Status.RUNNING
            else:
                # Check if it's failed
                result = subprocess.run(
                    ['systemctl', 'is-failed', service_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                status = ServiceStatus.Status.FAILED if result.stdout.strip() == 'failed' else ServiceStatus.Status.STOPPED

            # Get or create status record
            service_status, created = ServiceStatus.objects.get_or_create(
                deployment=deployment,
                defaults={
                    'status': status,
                    'pid': pid,
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent,
                    'uptime_seconds': uptime_seconds,
                }
            )

            if not created:
                # Update existing
                service_status.status = status
                service_status.pid = pid
                service_status.memory_mb = memory_mb
                service_status.cpu_percent = cpu_percent
                service_status.uptime_seconds = uptime_seconds
                service_status.save()

            return service_status

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout checking service status for {service_name}")
            return self._get_or_create_failed_status(deployment, "Timeout checking service")
        except Exception as e:
            logger.error(f"Error checking service status for {service_name}: {e}")
            return self._get_or_create_failed_status(deployment, str(e))

    def _get_or_create_failed_status(self, deployment: Deployment, error: str) -> ServiceStatus:
        """Get or create a failed status record."""
        service_status, _ = ServiceStatus.objects.get_or_create(
            deployment=deployment,
            defaults={'status': ServiceStatus.Status.FAILED}
        )
        service_status.status = ServiceStatus.Status.FAILED
        service_status.save()
        return service_status

    def perform_health_check(self, deployment: Deployment) -> Optional[HealthCheck]:
        """Perform HTTP health check on deployment."""
        if not deployment.domain and not deployment.port:
            return None

        # Construct URL
        if deployment.domain:
            url = f"http://{deployment.domain}/"
        else:
            url = f"http://localhost:{deployment.port}/"

        try:
            start_time = timezone.now()
            response = requests.get(url, timeout=10)
            end_time = timezone.now()

            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            is_healthy = 200 <= response.status_code < 500

            health_check = HealthCheck.objects.create(
                deployment=deployment,
                url=url,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                is_healthy=is_healthy,
                error_message='' if is_healthy else f'HTTP {response.status_code}'
            )

            # Create alert if service is down
            if not is_healthy:
                self._create_alert(
                    alert_type=Alert.AlertType.SERVICE_DOWN,
                    severity=Alert.Severity.ERROR,
                    title=f'Service Health Check Failed: {deployment.name}',
                    message=f'Health check failed for {deployment.name} with status {response.status_code}',
                    metadata={'url': url, 'status_code': response.status_code},
                    deployment=deployment
                )

            return health_check

        except requests.Timeout:
            health_check = HealthCheck.objects.create(
                deployment=deployment,
                url=url,
                status_code=0,
                response_time_ms=10000,
                is_healthy=False,
                error_message='Request timeout'
            )
            self._create_alert(
                alert_type=Alert.AlertType.SERVICE_DOWN,
                severity=Alert.Severity.ERROR,
                title=f'Service Timeout: {deployment.name}',
                message=f'Health check timeout for {deployment.name}',
                metadata={'url': url},
                deployment=deployment
            )
            return health_check

        except requests.RequestException as e:
            health_check = HealthCheck.objects.create(
                deployment=deployment,
                url=url,
                status_code=0,
                response_time_ms=0,
                is_healthy=False,
                error_message=str(e)
            )
            return health_check

    def get_system_summary(self) -> Dict[str, Any]:
        """Get comprehensive system summary."""
        latest = self.get_latest_metrics()
        if not latest:
            latest = self.collect_metrics()

        # Get recent alerts (don't slice yet to allow filtering)
        all_unacked_alerts = Alert.objects.filter(is_acknowledged=False)

        # Get service statuses
        deployments = Deployment.objects.all()
        service_statuses = []
        for deployment in deployments:
            status = ServiceStatus.objects.filter(deployment=deployment).first()
            if status:
                service_statuses.append(status)

        return {
            'resources': {
                'cpu_percent': latest.cpu_percent,
                'memory_percent': latest.memory_percent,
                'memory_used_mb': latest.memory_used_mb,
                'memory_total_mb': latest.memory_total_mb,
                'disk_percent': latest.disk_percent,
                'disk_used_gb': latest.disk_used_gb,
                'disk_total_gb': latest.disk_total_gb,
                'load_average': {
                    '1m': latest.load_average_1m,
                    '5m': latest.load_average_5m,
                    '15m': latest.load_average_15m,
                }
            },
            'alerts': {
                'total': all_unacked_alerts.count(),
                'critical': all_unacked_alerts.filter(severity=Alert.Severity.CRITICAL).count(),
                'error': all_unacked_alerts.filter(severity=Alert.Severity.ERROR).count(),
                'warning': all_unacked_alerts.filter(severity=Alert.Severity.WARNING).count(),
                'recent': list(all_unacked_alerts[:10])
            },
            'services': {
                'total': len(service_statuses),
                'running': len([s for s in service_statuses if s.status == ServiceStatus.Status.RUNNING]),
                'stopped': len([s for s in service_statuses if s.status == ServiceStatus.Status.STOPPED]),
                'failed': len([s for s in service_statuses if s.status == ServiceStatus.Status.FAILED]),
            }
        }

    def cleanup_old_data(self, days: int = 7) -> None:
        """Clean up old monitoring data."""
        cutoff = timezone.now() - timezone.timedelta(days=days)

        # Delete old resource usage
        deleted_usage = ResourceUsage.objects.filter(created_at__lt=cutoff).delete()

        # Delete old acknowledged alerts
        deleted_alerts = Alert.objects.filter(
            is_acknowledged=True,
            acknowledged_at__lt=cutoff
        ).delete()

        # Delete old health checks
        deleted_health = HealthCheck.objects.filter(created_at__lt=cutoff).delete()

        logger.info(f"Cleaned up old data: {deleted_usage[0]} usage records, {deleted_alerts[0]} alerts, {deleted_health[0]} health checks")
