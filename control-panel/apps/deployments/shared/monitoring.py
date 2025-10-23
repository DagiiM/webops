"""
BaseDeployment monitoring and alerting system.

"Monitoring & Logs" section
"""

import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail

from ..models import BaseDeployment, ApplicationDeployment, DeploymentLog
from apps.core.security.models import SecurityAuditLog
from apps.core.common.models import SystemHealthCheck

logger = logging.getLogger(__name__)


class DeploymentMonitor:
    """Monitor deployment health and performance."""
    
    def __init__(self):
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'failed_deployments': 3,
            'build_time_minutes': 30,
        }
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Check overall system health.
        
        Returns:
            Dictionary with system health metrics
        """
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Count deployments
        active_deployments = BaseDeployment.objects.filter(
            status=BaseDeployment.Status.RUNNING
        ).count()
        
        failed_deployments = BaseDeployment.objects.filter(
            status=BaseDeployment.Status.FAILED,
            updated_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Determine health status
        issues = []
        is_healthy = True
        
        if cpu_percent > self.alert_thresholds['cpu_percent']:
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")
            is_healthy = False
        
        if memory.percent > self.alert_thresholds['memory_percent']:
            issues.append(f"High memory usage: {memory.percent:.1f}%")
            is_healthy = False
        
        if disk.percent > self.alert_thresholds['disk_percent']:
            issues.append(f"High disk usage: {disk.percent:.1f}%")
            is_healthy = False
        
        if failed_deployments > self.alert_thresholds['failed_deployments']:
            issues.append(f"Too many failed deployments: {failed_deployments}")
            is_healthy = False
        
        health_data = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_used_mb': memory.used // (1024 * 1024),
            'memory_total_mb': memory.total // (1024 * 1024),
            'disk_percent': disk.percent,
            'disk_used_gb': disk.used / (1024 ** 3),
            'disk_total_gb': disk.total / (1024 ** 3),
            'active_deployments': active_deployments,
            'failed_deployments': failed_deployments,
            'is_healthy': is_healthy,
            'issues': issues
        }
        
        # Save to database
        SystemHealthCheck.objects.create(**health_data)
        
        # Clean up old health checks (keep last 100)
        old_checks = SystemHealthCheck.objects.all()[100:]
        if old_checks:
            SystemHealthCheck.objects.filter(
                id__in=[check.id for check in old_checks]
            ).delete()
        
        return health_data
    
    def check_deployment_health(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Check health of a specific deployment.
        
        Args:
            deployment: BaseDeployment instance
            
        Returns:
            Dictionary with deployment health status
        """
        health_status = {
            'deployment_id': deployment.id,
            'name': deployment.name,
            'status': deployment.status,
            'is_healthy': True,
            'issues': [],
            'metrics': {}
        }
        
        # Check if deployment is running
        if deployment.status != BaseDeployment.Status.RUNNING:
            if deployment.status == BaseDeployment.Status.FAILED:
                health_status['is_healthy'] = False
                health_status['issues'].append('BaseDeployment failed')
            elif deployment.status == BaseDeployment.Status.BUILDING:
                # Check build time
                build_time = timezone.now() - deployment.updated_at
                if build_time.total_seconds() > (self.alert_thresholds['build_time_minutes'] * 60):
                    health_status['is_healthy'] = False
                    health_status['issues'].append(f'Build taking too long: {build_time}')
        
        # Check recent error logs
        error_logs = DeploymentLog.objects.filter(
            deployment=deployment,
            level=DeploymentLog.Level.ERROR,
            created_at__gte=timezone.now() - timedelta(hours=1)
        )
        
        if error_logs.exists():
            health_status['is_healthy'] = False
            health_status['issues'].append(f'{error_logs.count()} errors in last hour')
        
        # Check service status (if running)
        if deployment.status == BaseDeployment.Status.RUNNING and deployment.port:
            try:
                from .service_manager import ServiceManager
                service_manager = ServiceManager()
                service_status = service_manager.get_service_status(deployment)
                health_status['metrics']['service_status'] = service_status
                
                if not service_status.get('is_active', False):
                    health_status['is_healthy'] = False
                    health_status['issues'].append('Service not running')
                    
            except Exception as e:
                logger.warning(f"Could not check service status for {deployment.name}: {e}")
        
        return health_status
    
    def get_deployment_metrics(self, deployment: BaseDeployment) -> Dict[str, Any]:
        """
        Get performance metrics for deployment.
        
        Args:
            deployment: BaseDeployment instance
            
        Returns:
            Dictionary with metrics
        """
        metrics = {
            'deployment_count': 1,
            'error_count': 0,
            'warning_count': 0,
            'uptime_seconds': 0,
            'last_deployment': deployment.updated_at,
        }
        
        # Count recent logs
        recent_logs = DeploymentLog.objects.filter(
            deployment=deployment,
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        metrics['error_count'] = recent_logs.filter(level=DeploymentLog.Level.ERROR).count()
        metrics['warning_count'] = recent_logs.filter(level=DeploymentLog.Level.WARNING).count()
        
        # Calculate uptime
        if deployment.status == BaseDeployment.Status.RUNNING:
            # Find last successful deployment log
            success_log = DeploymentLog.objects.filter(
                deployment=deployment,
                level=DeploymentLog.Level.SUCCESS,
                message__icontains='deployment completed'
            ).first()
            
            if success_log:
                uptime = timezone.now() - success_log.created_at
                metrics['uptime_seconds'] = int(uptime.total_seconds())
        
        return metrics
    
    def send_alert(self, subject: str, message: str, level: str = 'warning'):
        """
        Send alert notification.
        
        Args:
            subject: Alert subject
            message: Alert message
            level: Alert level (info, warning, error, critical)
        """
        logger.warning(f"ALERT [{level.upper()}]: {subject} - {message}")
        
        # TODO: Implement email/Slack notifications
        # For now, just log the alert
        try:
            # Create security audit log
            SecurityAuditLog.objects.create(
                event_type=SecurityAuditLog.EventType.SUSPICIOUS_ACTIVITY,
                severity=SecurityAuditLog.Severity.WARNING if level == 'warning' else SecurityAuditLog.Severity.ERROR,
                ip_address='127.0.0.1',
                description=f"System Alert: {subject}",
                metadata={'message': message, 'level': level}
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
    
    def check_all_deployments(self) -> List[Dict[str, Any]]:
        """
        Check health of all deployments.
        
        Returns:
            List of health status dictionaries
        """
        results = []
        deployments = BaseDeployment.objects.all()
        
        for deployment in deployments:
            try:
                health_status = self.check_deployment_health(deployment)
                results.append(health_status)
                
                # Send alerts for unhealthy deployments
                if not health_status['is_healthy']:
                    self.send_alert(
                        subject=f"BaseDeployment Issue: {deployment.name}",
                        message=f"Issues: {', '.join(health_status['issues'])}",
                        level='warning'
                    )
                    
            except Exception as e:
                logger.error(f"Error checking deployment {deployment.name}: {e}")
                results.append({
                    'deployment_id': deployment.id,
                    'name': deployment.name,
                    'is_healthy': False,
                    'issues': [f'Monitoring error: {str(e)}']
                })
        
        return results
    
    def generate_health_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive health report.
        
        Returns:
            Dictionary with complete system and deployment health
        """
        system_health = self.check_system_health()
        deployment_health = self.check_all_deployments()
        
        # Summary statistics
        total_deployments = len(deployment_health)
        healthy_deployments = sum(1 for d in deployment_health if d['is_healthy'])
        unhealthy_deployments = total_deployments - healthy_deployments
        
        report = {
            'timestamp': timezone.now(),
            'system_health': system_health,
            'deployment_health': deployment_health,
            'summary': {
                'total_deployments': total_deployments,
                'healthy_deployments': healthy_deployments,
                'unhealthy_deployments': unhealthy_deployments,
                'system_healthy': system_health['is_healthy'],
                'overall_healthy': system_health['is_healthy'] and unhealthy_deployments == 0
            }
        }
        
        # Send critical alerts
        if not report['summary']['overall_healthy']:
            issues = system_health['issues'] + [
                f"{unhealthy_deployments} unhealthy deployments" 
                if unhealthy_deployments > 0 else ""
            ]
            issues = [issue for issue in issues if issue]  # Remove empty strings
            
            self.send_alert(
                subject="WebOps System Health Alert",
                message=f"System issues detected: {', '.join(issues)}",
                level='error'
            )
        
        return report


class DeploymentAnalytics:
    """Analytics and insights for deployments."""
    
    def get_deployment_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get deployment statistics for the last N days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with deployment statistics
        """
        since = timezone.now() - timedelta(days=days)
        
        # Get deployments in time period
        deployments = BaseDeployment.objects.filter(created_at__gte=since)
        
        stats = {
            'period_days': days,
            'total_deployments': deployments.count(),
            'successful_deployments': deployments.filter(status=BaseDeployment.Status.RUNNING).count(),
            'failed_deployments': deployments.filter(status=BaseDeployment.Status.FAILED).count(),
            'pending_deployments': deployments.filter(status=BaseDeployment.Status.PENDING).count(),
            'building_deployments': deployments.filter(status=BaseDeployment.Status.BUILDING).count(),
            'by_project_type': {},
            'by_user': {},
            'success_rate': 0.0,
            'avg_build_time': 0.0,
        }
        
        if stats['total_deployments'] > 0:
            stats['success_rate'] = (stats['successful_deployments'] / stats['total_deployments']) * 100
        
        # Group by project type
        for project_type in BaseDeployment.ProjectType:
            count = deployments.filter(project_type=project_type).count()
            stats['by_project_type'][project_type.label] = count
        
        # Group by user
        from django.contrib.auth.models import User
        for user in User.objects.all():
            count = deployments.filter(deployed_by=user).count()
            if count > 0:
                stats['by_user'][user.username] = count
        
        # Calculate average build time for successful deployments
        successful = deployments.filter(
            status=BaseDeployment.Status.RUNNING,
            updated_at__isnull=False
        )
        
        if successful.exists():
            build_times = []
            for deployment in successful:
                build_time = deployment.updated_at - deployment.created_at
                build_times.append(build_time.total_seconds())
            
            if build_times:
                stats['avg_build_time'] = sum(build_times) / len(build_times)
        
        return stats
    
    def get_error_analysis(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze deployment errors for insights.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with error analysis
        """
        since = timezone.now() - timedelta(days=days)
        
        error_logs = DeploymentLog.objects.filter(
            level=DeploymentLog.Level.ERROR,
            created_at__gte=since
        )
        
        # Group errors by common patterns
        error_patterns = {}
        common_errors = [
            ('git clone', 'Repository access issues'),
            ('psycopg2', 'PostgreSQL dependency issues'),
            ('pip install', 'Python dependency issues'),
            ('migrate', 'Database migration issues'),
            ('ModuleNotFoundError', 'Missing Python modules'),
            ('Permission denied', 'File system permission issues'),
            ('timeout', 'Process timeout issues'),
        ]
        
        for pattern, description in common_errors:
            count = error_logs.filter(message__icontains=pattern).count()
            if count > 0:
                error_patterns[description] = count
        
        return {
            'period_days': days,
            'total_errors': error_logs.count(),
            'error_patterns': error_patterns,
            'recommendations': self._get_error_recommendations(error_patterns)
        }
    
    def _get_error_recommendations(self, error_patterns: Dict[str, int]) -> List[str]:
        """Generate recommendations based on error patterns."""
        recommendations = []
        
        if error_patterns.get('Repository access issues', 0) > 0:
            recommendations.append(
                "Consider adding GitHub token for private repository access"
            )
        
        if error_patterns.get('PostgreSQL dependency issues', 0) > 0:
            recommendations.append(
                "Install PostgreSQL development headers: sudo apt-get install libpq-dev"
            )
        
        if error_patterns.get('Python dependency issues', 0) > 0:
            recommendations.append(
                "Review requirements.txt files and ensure compatible versions"
            )
        
        if error_patterns.get('Missing Python modules', 0) > 0:
            recommendations.append(
                "Check Django settings modules and project structure"
            )
        
        return recommendations
