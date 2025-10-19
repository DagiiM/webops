"""
Views for Services monitoring app.

Reference: CLAUDE.md "Django App Structure" section
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg
from datetime import timedelta

from .models import ServiceStatus, ResourceUsage, Alert, HealthCheck
from .monitoring import SystemMonitor
from apps.deployments.models import Deployment


@login_required
def monitoring_dashboard(request):
    """Main monitoring dashboard with system overview."""
    monitor = SystemMonitor()

    # Get latest metrics or collect new ones
    latest_metrics = monitor.get_latest_metrics()
    if not latest_metrics:
        latest_metrics = monitor.collect_metrics()

    # Get system summary
    summary = monitor.get_system_summary()

    # Get recent alerts
    recent_alerts = Alert.objects.filter(is_acknowledged=False)[:5]

    # Get historical data for charts (last 24 hours)
    history = monitor.get_metrics_history(hours=24)

    # Service statuses
    deployments = Deployment.objects.all()
    service_statuses = []
    for deployment in deployments:
        status = ServiceStatus.objects.filter(deployment=deployment).first()
        if not status:
            # Create initial status by checking
            status = monitor.check_service_status(deployment)
        service_statuses.append({
            'deployment': deployment,
            'status': status
        })

    # Recent health checks
    recent_health_checks = HealthCheck.objects.select_related('deployment')[:10]

    context = {
        'latest_metrics': latest_metrics,
        'summary': summary,
        'recent_alerts': recent_alerts,
        'history': history,
        'service_statuses': service_statuses,
        'recent_health_checks': recent_health_checks,
    }

    return render(request, 'services/monitoring_dashboard.html', context)


@login_required
def alerts_list(request):
    """List all alerts with filtering."""
    # Filters
    severity = request.GET.get('severity')
    alert_type = request.GET.get('type')
    acknowledged = request.GET.get('acknowledged')

    alerts = Alert.objects.all()

    if severity:
        alerts = alerts.filter(severity=severity)
    if alert_type:
        alerts = alerts.filter(alert_type=alert_type)
    if acknowledged == 'true':
        alerts = alerts.filter(is_acknowledged=True)
    elif acknowledged == 'false':
        alerts = alerts.filter(is_acknowledged=False)

    # Stats
    stats = {
        'total': Alert.objects.count(),
        'unacknowledged': Alert.objects.filter(is_acknowledged=False).count(),
        'critical': Alert.objects.filter(severity=Alert.Severity.CRITICAL, is_acknowledged=False).count(),
        'by_type': Alert.objects.filter(is_acknowledged=False).values('alert_type').annotate(count=Count('id'))
    }

    context = {
        'alerts': alerts[:50],  # Limit to 50
        'stats': stats,
        'severity_choices': Alert.Severity.choices,
        'type_choices': Alert.AlertType.choices,
    }

    return render(request, 'services/alerts_list.html', context)


@login_required
def alert_acknowledge(request, pk):
    """Acknowledge an alert."""
    if request.method == 'POST':
        alert = get_object_or_404(Alert, pk=pk)
        alert.acknowledge()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Alert acknowledged'})

        return redirect('monitoring:alerts_list')

    return redirect('monitoring:alerts_list')


@login_required
def alert_acknowledge_all(request):
    """Acknowledge all unacknowledged alerts."""
    if request.method == 'POST':
        count = Alert.objects.filter(is_acknowledged=False).update(
            is_acknowledged=True,
            acknowledged_at=timezone.now()
        )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'count': count})

        return redirect('monitoring:alerts_list')

    return redirect('monitoring:alerts_list')


@login_required
def metrics_history(request):
    """Get metrics history as JSON for charts."""
    hours = int(request.GET.get('hours', 24))

    monitor = SystemMonitor()
    history = monitor.get_metrics_history(hours=hours)

    # Format for charts
    data = {
        'timestamps': [m.created_at.isoformat() for m in history],
        'cpu': [m.cpu_percent for m in history],
        'memory': [m.memory_percent for m in history],
        'disk': [m.disk_percent for m in history],
        'load_avg_1m': [m.load_average_1m for m in history],
        'network_sent': [m.network_sent_mb for m in history],
        'network_recv': [m.network_recv_mb for m in history],
    }

    return JsonResponse(data)


@login_required
def service_status_detail(request, deployment_id):
    """Get detailed service status."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    monitor = SystemMonitor()
    status = monitor.check_service_status(deployment)

    # Get health check history (base queryset without slicing)
    health_checks_qs = HealthCheck.objects.filter(deployment=deployment)

    # Calculate uptime percentage
    total_checks = health_checks_qs.count()
    healthy_checks = health_checks_qs.filter(is_healthy=True).count()
    uptime_percent = (healthy_checks / total_checks * 100) if total_checks > 0 else 0

    # Average response time
    avg_response_time = health_checks_qs.filter(is_healthy=True).aggregate(
        avg_time=Avg('response_time_ms')
    )['avg_time'] or 0

    # Get last 20 checks for display
    health_checks = health_checks_qs[:20]

    context = {
        'deployment': deployment,
        'status': status,
        'health_checks': health_checks,
        'uptime_percent': uptime_percent,
        'avg_response_time': avg_response_time,
    }

    return render(request, 'services/service_status_detail.html', context)


@login_required
def refresh_service_status(request, deployment_id):
    """Manually refresh service status."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    monitor = SystemMonitor()
    status = monitor.check_service_status(deployment)

    # Also perform health check if deployment has URL
    health_check = monitor.perform_health_check(deployment)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'status': status.status,
            'pid': status.pid,
            'memory_mb': status.memory_mb,
            'cpu_percent': status.cpu_percent,
            'uptime_seconds': status.uptime_seconds,
            'health_check': {
                'is_healthy': health_check.is_healthy if health_check else None,
                'response_time_ms': health_check.response_time_ms if health_check else None,
            } if health_check else None
        })

    return redirect('monitoring:service_status_detail', deployment_id=deployment_id)


@login_required
def current_metrics_api(request):
    """Get current system metrics as JSON (for real-time updates)."""
    monitor = SystemMonitor()
    latest = monitor.get_latest_metrics()

    if not latest:
        latest = monitor.collect_metrics()

    data = {
        'timestamp': latest.created_at.isoformat(),
        'cpu_percent': latest.cpu_percent,
        'memory_percent': latest.memory_percent,
        'memory_used_mb': latest.memory_used_mb,
        'memory_total_mb': latest.memory_total_mb,
        'disk_percent': latest.disk_percent,
        'disk_used_gb': round(latest.disk_used_gb, 2),
        'disk_total_gb': round(latest.disk_total_gb, 2),
        'load_average': {
            '1m': latest.load_average_1m,
            '5m': latest.load_average_5m,
            '15m': latest.load_average_15m,
        },
        'network': {
            'sent_mb': round(latest.network_sent_mb, 2),
            'recv_mb': round(latest.network_recv_mb, 2),
        }
    }

    return JsonResponse(data)


@login_required
def system_summary_api(request):
    """Get complete system summary as JSON."""
    monitor = SystemMonitor()
    summary = monitor.get_system_summary()

    # Convert alert objects to dict
    summary['alerts']['recent'] = [
        {
            'id': alert.id,
            'title': alert.title,
            'severity': alert.severity,
            'alert_type': alert.alert_type,
            'created_at': alert.created_at.isoformat(),
        }
        for alert in summary['alerts']['recent']
    ]

    return JsonResponse(summary)


@login_required
def health_check_history(request, deployment_id):
    """Get health check history for a deployment."""
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    hours = int(request.GET.get('hours', 24))
    cutoff = timezone.now() - timedelta(hours=hours)

    checks = HealthCheck.objects.filter(
        deployment=deployment,
        created_at__gte=cutoff
    ).order_by('created_at')

    data = {
        'deployment': deployment.name,
        'checks': [
            {
                'timestamp': check.created_at.isoformat(),
                'status_code': check.status_code,
                'response_time_ms': check.response_time_ms,
                'is_healthy': check.is_healthy,
                'error_message': check.error_message,
            }
            for check in checks
        ]
    }

    return JsonResponse(data)
