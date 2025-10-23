"""
Django management command for health checks.

Usage:
    python manage.py health_check
    python manage.py health_check --report
    python manage.py health_check --fix-deployments
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.deployments.shared.monitoring import DeploymentMonitor, DeploymentAnalytics
from apps.deployments.models import BaseDeployment, ApplicationDeployment


class Command(BaseCommand):
    help = 'Check system and deployment health'

    def add_arguments(self, parser):
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate detailed health report',
        )
        parser.add_argument(
            '--fix-deployments',
            action='store_true',
            help='Attempt to fix stuck deployments',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for analytics (default: 7)',
        )

    def handle(self, *args, **options):
        monitor = DeploymentMonitor()
        
        self.stdout.write(
            self.style.SUCCESS('=== WebOps Health Check ===')
        )
        
        if options['fix_deployments']:
            self.fix_stuck_deployments()
        
        # Basic health check
        system_health = monitor.check_system_health()
        deployment_health = monitor.check_all_deployments()
        
        # Display system health
        self.stdout.write('\n🖥️  System Health:')
        if system_health['is_healthy']:
            self.stdout.write(self.style.SUCCESS('  ✓ System is healthy'))
        else:
            self.stdout.write(self.style.ERROR('  ✗ System has issues:'))
            for issue in system_health['issues']:
                self.stdout.write(f'    - {issue}')
        
        self.stdout.write(f"  CPU: {system_health['cpu_percent']:.1f}%")
        self.stdout.write(f"  Memory: {system_health['memory_percent']:.1f}%")
        self.stdout.write(f"  Disk: {system_health['disk_percent']:.1f}%")
        
        # Display deployment health
        healthy_count = sum(1 for d in deployment_health if d['is_healthy'])
        total_count = len(deployment_health)
        
        self.stdout.write(f'\n🚀 Deployments: {healthy_count}/{total_count} healthy')
        
        for deployment in deployment_health:
            if deployment['is_healthy']:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ {deployment['name']}")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {deployment['name']}")
                )
                for issue in deployment['issues']:
                    self.stdout.write(f"    - {issue}")
        
        # Generate detailed report if requested
        if options['report']:
            self.generate_detailed_report(options['days'])

    def fix_stuck_deployments(self):
        """Attempt to fix deployments stuck in building state."""
        self.stdout.write('\n🔧 Checking for stuck deployments...')
        
        # Find deployments stuck in building state for > 1 hour
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        stuck_deployments = ApplicationDeployment.objects.filter(
            status=ApplicationDeployment.Status.BUILDING,
            updated_at__lt=one_hour_ago
        )
        
        if not stuck_deployments.exists():
            self.stdout.write('  No stuck deployments found')
            return
        
        for deployment in stuck_deployments:
            self.stdout.write(f'  Fixing stuck deployment: {deployment.name}')
            deployment.status = ApplicationDeployment.Status.FAILED
            deployment.save()
            
            self.stdout.write(
                self.style.WARNING(f'    Reset {deployment.name} to failed status')
            )

    def generate_detailed_report(self, days: int):
        """Generate detailed analytics report."""
        analytics = DeploymentAnalytics()
        stats = analytics.get_deployment_statistics(days)
        
        self.stdout.write(f'\n📊 Statistics (Last {days} days):')
        self.stdout.write(f'  Total: {stats["total_deployments"]}')
        self.stdout.write(f'  Success rate: {stats["success_rate"]:.1f}%')