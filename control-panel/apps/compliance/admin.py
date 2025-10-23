from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ComplianceFramework, ComplianceControl, ComplianceEvidence,
    SecurityScan, ComplianceReport, DataRetentionPolicy, ComplianceAlert
)

@admin.register(ComplianceFramework)
class ComplianceFrameworkAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(ComplianceControl)
class ComplianceControlAdmin(admin.ModelAdmin):
    list_display = ['control_id', 'title', 'framework', 'category', 'priority', 'implementation_status', 'is_automated']
    list_filter = ['framework', 'category', 'priority', 'implementation_status', 'is_automated']
    search_fields = ['control_id', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'last_automated_check']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('framework', 'control_id', 'title', 'description', 'category')
        }),
        ('Priority & Status', {
            'fields': ('priority', 'implementation_status', 'is_automated', 'automation_script')
        }),
        ('Evidence', {
            'fields': ('evidence_required', 'evidence_description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_automated_check'),
            'classes': ('collapse',)
        })
    )

@admin.register(ComplianceEvidence)
class ComplianceEvidenceAdmin(admin.ModelAdmin):
    list_display = ['title', 'control', 'evidence_type', 'collected_by', 'collected_at', 'is_valid']
    list_filter = ['evidence_type', 'is_valid', 'collected_at']
    search_fields = ['title', 'description', 'control__title']
    readonly_fields = ['collected_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('control', 'collected_by')

@admin.register(SecurityScan)
class SecurityScanAdmin(admin.ModelAdmin):
    list_display = ['scan_id', 'scan_type', 'tool', 'target', 'status', 'security_score', 'started_at']
    list_filter = ['scan_type', 'tool', 'status', 'started_at']
    search_fields = ['scan_id', 'target']
    readonly_fields = ['scan_id', 'started_at', 'completed_at', 'duration_seconds']
    
    fieldsets = (
        ('Scan Information', {
            'fields': ('scan_id', 'scan_type', 'tool', 'target', 'status')
        }),
        ('Results', {
            'fields': ('total_items', 'threats_found', 'warnings_found', 'clean_items', 'security_score')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration_seconds'),
            'classes': ('collapse',)
        }),
        ('Automation', {
            'fields': ('is_automated', 'automation_script', 'related_controls')
        })
    )
    
    def security_score_display(self, obj):
        if obj.security_score is not None:
            color = 'red' if obj.security_score < 50 else 'orange' if obj.security_score < 80 else 'green'
            return format_html('<span style="color: {};">{}%</span>', color, obj.security_score)
        return '-'
    security_score_display.short_description = 'Security Score'

@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ['report_id', 'title', 'framework', 'report_type', 'status', 'compliance_percentage', 'generated_at']
    list_filter = ['framework', 'report_type', 'status', 'generated_at']
    search_fields = ['report_id', 'title']
    readonly_fields = ['report_id', 'generated_at', 'compliance_percentage']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_id', 'title', 'framework', 'report_type', 'status')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Metrics', {
            'fields': ('total_controls', 'implemented_controls', 'automated_controls', 'compliant_controls', 'compliance_percentage')
        }),
        ('Files', {
            'fields': ('pdf_report',)
        })
    )
    
    def compliance_percentage_display(self, obj):
        if obj.compliance_percentage is not None:
            color = 'red' if obj.compliance_percentage < 70 else 'orange' if obj.compliance_percentage < 90 else 'green'
            return format_html('<span style="color: {};">{}%</span>', color, obj.compliance_percentage)
        return '-'
    compliance_percentage_display.short_description = 'Compliance %'

@admin.register(DataRetentionPolicy)
class DataRetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'retention_days', 'archive_before_delete', 'is_active', 'last_enforced']
    list_filter = ['is_active', 'archive_before_delete', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['last_enforced', 'created_at', 'updated_at']
    filter_horizontal = ['frameworks']

@admin.register(ComplianceAlert)
class ComplianceAlertAdmin(admin.ModelAdmin):
    list_display = ['alert_id', 'title', 'alert_type', 'severity', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'severity', 'is_resolved', 'created_at']
    search_fields = ['alert_id', 'title', 'description']
    readonly_fields = ['alert_id', 'created_at', 'resolved_at']
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_id', 'title', 'description', 'alert_type', 'severity')
        }),
        ('Related Items', {
            'fields': ('related_controls', 'related_scans')
        }),
        ('Status', {
            'fields': ('is_resolved', 'resolved_at', 'resolved_by')
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('related_controls', 'related_scans')
    
    actions = ['mark_as_resolved']
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(is_resolved=True, resolved_at=timezone.now(), resolved_by=request.user)
        self.message_user(request, f'{updated} alert(s) marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected alerts as resolved'
