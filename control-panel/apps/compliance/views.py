from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q, Avg
from django.core.paginator import Paginator
import json
from datetime import datetime, timedelta

from .models import (
    ComplianceFramework, ComplianceControl, ComplianceEvidence,
    SecurityScan, ComplianceReport, DataRetentionPolicy, ComplianceAlert
)

@login_required
def dashboard(request):
    """Main compliance dashboard"""
    
    # Get overview statistics
    frameworks = ComplianceFramework.objects.filter(is_active=True)
    total_controls = ComplianceControl.objects.count()
    automated_controls = ComplianceControl.objects.filter(is_automated=True).count()
    
    # Recent security scans
    recent_scans = SecurityScan.objects.order_by('-started_at')[:10]
    
    # Active alerts
    active_alerts = ComplianceAlert.objects.filter(is_resolved=False).order_by('-created_at')[:10]
    
    # Compliance by framework
    framework_stats = []
    for framework in frameworks:
        controls = ComplianceControl.objects.filter(framework=framework)
        total = controls.count()
        automated = controls.filter(is_automated=True).count()
        implemented = controls.filter(
            implementation_status__in=['implemented', 'automated']
        ).count()
        
        framework_stats.append({
            'framework': framework,
            'total_controls': total,
            'automated_controls': automated,
            'implemented_controls': implemented,
            'compliance_percentage': (implemented / total * 100) if total > 0 else 0
        })
    
    # Security score trend (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    security_scores = SecurityScan.objects.filter(
        completed_at__gte=thirty_days_ago,
        security_score__isnull=False
    ).order_by('completed_at')
    
    score_trend = []
    for scan in security_scores:
        score_trend.append({
            'date': scan.completed_at.strftime('%Y-%m-%d'),
            'score': float(scan.security_score)
        })
    
    context = {
        'framework_stats': framework_stats,
        'total_controls': total_controls,
        'automated_controls': automated_controls,
        'automation_percentage': (automated_controls / total_controls * 100) if total_controls > 0 else 0,
        'recent_scans': recent_scans,
        'active_alerts': active_alerts,
        'alert_count': active_alerts.count(),
        'score_trend_json': json.dumps(score_trend),
    }
    
    return render(request, 'compliance/dashboard.html', context)

@login_required
def frameworks_list(request):
    """List all compliance frameworks"""
    frameworks = ComplianceFramework.objects.all().order_by('name')
    
    context = {
        'frameworks': frameworks,
    }
    
    return render(request, 'compliance/frameworks.html', context)

@login_required
def framework_detail(request, framework_id):
    """Detail view for a specific framework"""
    framework = get_object_or_404(ComplianceFramework, id=framework_id)
    
    # Get controls with statistics
    controls = ComplianceControl.objects.filter(framework=framework).order_by('control_id')
    
    # Statistics
    total_controls = controls.count()
    automated_controls = controls.filter(is_automated=True).count()
    implemented_controls = controls.filter(
        implementation_status__in=['implemented', 'automated']
    ).count()
    
    # Category breakdown
    category_stats = controls.values('category').annotate(
        total=Count('id'),
        automated=Count('id', filter=Q(is_automated=True)),
        implemented=Count('id', filter=Q(
            implementation_status__in=['implemented', 'automated']
        ))
    ).order_by('category')
    
    context = {
        'framework': framework,
        'controls': controls,
        'total_controls': total_controls,
        'automated_controls': automated_controls,
        'implemented_controls': implemented_controls,
        'compliance_percentage': (implemented_controls / total_controls * 100) if total_controls > 0 else 0,
        'category_stats': category_stats,
    }
    
    return render(request, 'compliance/framework_detail.html', context)

@login_required
def controls_list(request):
    """List all compliance controls"""
    
    # Filtering
    framework_filter = request.GET.get('framework')
    category_filter = request.GET.get('category')
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    
    controls = ComplianceControl.objects.all()
    
    if framework_filter:
        controls = controls.filter(framework_id=framework_filter)
    if category_filter:
        controls = controls.filter(category=category_filter)
    if status_filter:
        controls = controls.filter(implementation_status=status_filter)
    if priority_filter:
        controls = controls.filter(priority=priority_filter)
    
    controls = controls.order_by('framework', 'control_id')
    
    # Pagination
    paginator = Paginator(controls, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique values for filters
    frameworks = ComplianceFramework.objects.filter(is_active=True)
    categories = ComplianceControl.objects.values_list('category', flat=True).distinct().order_by('category')
    
    context = {
        'controls': page_obj,
        'frameworks': frameworks,
        'categories': categories,
        'status_choices': ComplianceControl.IMPLEMENTATION_STATUS,
        'priority_choices': ComplianceControl.priority.field.choices,
        'current_filters': {
            'framework': framework_filter,
            'category': category_filter,
            'status': status_filter,
            'priority': priority_filter,
        }
    }
    
    return render(request, 'compliance/controls.html', context)

@login_required
def control_detail(request, control_id):
    """Detail view for a specific control"""
    control = get_object_or_404(ComplianceControl, id=control_id)
    
    # Get evidence
    evidence = ComplianceEvidence.objects.filter(control=control).order_by('-collected_at')
    
    # Get related security scans
    related_scans = SecurityScan.objects.filter(related_controls=control).order_by('-started_at')
    
    # Get related alerts
    related_alerts = ComplianceAlert.objects.filter(related_controls=control).order_by('-created_at')
    
    context = {
        'control': control,
        'evidence': evidence,
        'related_scans': related_scans,
        'related_alerts': related_alerts,
    }
    
    return render(request, 'compliance/control_detail.html', context)

@login_required
def security_scans(request):
    """Security scans list"""
    
    # Filtering
    scan_type_filter = request.GET.get('scan_type')
    tool_filter = request.GET.get('tool')
    status_filter = request.GET.get('status')
    
    scans = SecurityScan.objects.all()
    
    if scan_type_filter:
        scans = scans.filter(scan_type=scan_type_filter)
    if tool_filter:
        scans = scans.filter(tool=tool_filter)
    if status_filter:
        scans = scans.filter(status=status_filter)
    
    scans = scans.order_by('-started_at')
    
    # Pagination
    paginator = Paginator(scans, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'scans': page_obj,
        'scan_type_choices': SecurityScan.scan_type.field.choices,
        'tool_choices': SecurityScan.tool.field.choices,
        'status_choices': SecurityScan.status.field.choices,
        'current_filters': {
            'scan_type': scan_type_filter,
            'tool': tool_filter,
            'status': status_filter,
        }
    }
    
    return render(request, 'compliance/security_scans.html', context)

@login_required
def scan_detail(request, scan_id):
    """Detail view for a security scan"""
    scan = get_object_or_404(SecurityScan, scan_id=scan_id)
    
    # Parse results data
    results_data = scan.results_data or {}
    
    context = {
        'scan': scan,
        'results_data': results_data,
    }
    
    return render(request, 'compliance/scan_detail.html', context)

@login_required
def compliance_reports(request):
    """Compliance reports list"""
    
    # Filtering
    framework_filter = request.GET.get('framework')
    report_type_filter = request.GET.get('report_type')
    status_filter = request.GET.get('status')
    
    reports = ComplianceReport.objects.all()
    
    if framework_filter:
        reports = reports.filter(framework_id=framework_filter)
    if report_type_filter:
        reports = reports.filter(report_type=report_type_filter)
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    reports = reports.order_by('-generated_at')
    
    # Pagination
    paginator = Paginator(reports, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'reports': page_obj,
        'frameworks': ComplianceFramework.objects.filter(is_active=True),
        'report_type_choices': ComplianceReport.REPORT_TYPES,
        'status_choices': ComplianceReport.STATUS_CHOICES,
        'current_filters': {
            'framework': framework_filter,
            'report_type': report_type_filter,
            'status': status_filter,
        }
    }
    
    return render(request, 'compliance/reports.html', context)

@login_required
def report_detail(request, report_id):
    """Detail view for a compliance report"""
    report = get_object_or_404(ComplianceReport, report_id=report_id)
    
    # Parse report data
    report_data = report.report_data or {}
    
    context = {
        'report': report,
        'report_data': report_data,
    }
    
    return render(request, 'compliance/report_detail.html', context)

@login_required
def compliance_alerts(request):
    """Compliance alerts list"""
    
    # Filtering
    alert_type_filter = request.GET.get('alert_type')
    severity_filter = request.GET.get('severity')
    resolved_filter = request.GET.get('resolved')
    
    alerts = ComplianceAlert.objects.all()
    
    if alert_type_filter:
        alerts = alerts.filter(alert_type=alert_type_filter)
    if severity_filter:
        alerts = alerts.filter(severity=severity_filter)
    if resolved_filter:
        if resolved_filter == 'resolved':
            alerts = alerts.filter(is_resolved=True)
        elif resolved_filter == 'active':
            alerts = alerts.filter(is_resolved=False)
    
    alerts = alerts.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(alerts, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'alerts': page_obj,
        'alert_type_choices': ComplianceAlert.ALERT_TYPES,
        'severity_choices': ComplianceAlert.SEVERITY_CHOICES,
        'current_filters': {
            'alert_type': alert_type_filter,
            'severity': severity_filter,
            'resolved': resolved_filter,
        }
    }
    
    return render(request, 'compliance/alerts.html', context)

@login_required
def alert_detail(request, alert_id):
    """Detail view for a compliance alert"""
    alert = get_object_or_404(ComplianceAlert, alert_id=alert_id)
    
    context = {
        'alert': alert,
    }
    
    return render(request, 'compliance/alert_detail.html', context)

@login_required
@require_http_methods(["POST"])
def resolve_alert(request, alert_id):
    """Resolve a compliance alert"""
    alert = get_object_or_404(ComplianceAlert, alert_id=alert_id)
    
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save()
    
    messages.success(request, f'Alert "{alert.title}" has been resolved.')
    
    return redirect('compliance:alert_detail', alert_id=alert_id)

# API endpoints for AJAX requests
@login_required
def api_dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    
    frameworks = ComplianceFramework.objects.filter(is_active=True)
    total_controls = ComplianceControl.objects.count()
    automated_controls = ComplianceControl.objects.filter(is_automated=True).count()
    
    # Recent alerts
    recent_alerts = ComplianceAlert.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Recent scans
    recent_scans = SecurityScan.objects.filter(
        completed_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    stats = {
        'total_frameworks': frameworks.count(),
        'total_controls': total_controls,
        'automated_controls': automated_controls,
        'automation_percentage': (automated_controls / total_controls * 100) if total_controls > 0 else 0,
        'recent_alerts': recent_alerts,
        'recent_scans': recent_scans,
        'active_alerts': ComplianceAlert.objects.filter(is_resolved=False).count(),
    }
    
    return JsonResponse(stats)

@login_required
def api_scan_now(request):
    """API endpoint to trigger a security scan"""
    if request.method == 'POST':
        scan_type = request.POST.get('scan_type')
        target = request.POST.get('target', 'system')
        
        # Create scan record
        scan = SecurityScan.objects.create(
            scan_type=scan_type,
            target=target,
            tool='custom',
            status='running',
            is_automated=False
        )
        
        # TODO #17: Implement security scan execution
        # See: docs/TODO_TRACKING.md for details and acceptance criteria
        # For now, just mark as completed with sample data
        scan.status = 'completed'
        scan.completed_at = timezone.now()
        scan.security_score = 85.5
        scan.results_data = {
            'summary': 'Sample scan results',
            'details': 'This is a placeholder for actual scan results'
        }
        scan.save()
        
        return JsonResponse({
            'success': True,
            'scan_id': scan.scan_id,
            'message': 'Scan initiated successfully'
        })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def api_generate_report(request):
    """API endpoint to generate a compliance report"""
    if request.method == 'POST':
        framework_id = request.POST.get('framework_id')
        report_type = request.POST.get('report_type')
        period_start = request.POST.get('period_start')
        period_end = request.POST.get('period_end')
        
        try:
            framework = ComplianceFramework.objects.get(id=framework_id)
            
            # Create report record
            report = ComplianceReport.objects.create(
                title=f"{framework.name} {report_type.replace('_', ' ').title()}",
                framework=framework,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                generated_by=request.user,
                total_controls=ComplianceControl.objects.filter(framework=framework).count(),
                implemented_controls=ComplianceControl.objects.filter(
                    framework=framework,
                    implementation_status__in=['implemented', 'automated']
                ).count(),
                automated_controls=ComplianceControl.objects.filter(
                    framework=framework,
                    is_automated=True
                ).count(),
                compliant_controls=ComplianceControl.objects.filter(
                    framework=framework,
                    implementation_status__in=['implemented', 'automated']
                ).count()
            )
            
            return JsonResponse({
                'success': True,
                'report_id': report.report_id,
                'message': 'Report generated successfully'
            })
            
        except ComplianceFramework.DoesNotExist:
            return JsonResponse({'error': 'Framework not found'}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)
