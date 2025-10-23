from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
import json

class ComplianceFramework(models.Model):
    """Compliance framework model (SOC2, ISO27001, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    version = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} {self.version}"

class ComplianceControl(models.Model):
    """Individual compliance controls/requirements"""
    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE, related_name='controls')
    control_id = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)
    priority = models.CharField(max_length=20, choices=[
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], default='medium')
    
    # Implementation status
    IMPLEMENTATION_STATUS = [
        ('not_implemented', 'Not Implemented'),
        ('partially_implemented', 'Partially Implemented'),
        ('implemented', 'Implemented'),
        ('automated', 'Automated')
    ]
    implementation_status = models.CharField(max_length=25, choices=IMPLEMENTATION_STATUS, default='not_implemented')
    
    # Evidence and documentation
    evidence_required = models.BooleanField(default=True)
    evidence_description = models.TextField(blank=True)
    
    # Automation
    is_automated = models.BooleanField(default=False)
    automation_script = models.CharField(max_length=255, blank=True)
    last_automated_check = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['framework', 'control_id']
        ordering = ['framework', 'control_id']
    
    def __str__(self):
        return f"{self.framework.name} - {self.control_id}: {self.title}"

class ComplianceEvidence(models.Model):
    """Evidence for compliance controls"""
    control = models.ForeignKey(ComplianceControl, on_delete=models.CASCADE, related_name='evidence')
    evidence_type = models.CharField(max_length=50, choices=[
        ('document', 'Document'),
        ('screenshot', 'Screenshot'),
        ('log', 'Log File'),
        ('script', 'Script'),
        ('report', 'Report'),
        ('certificate', 'Certificate'),
        ('other', 'Other')
    ])
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_data = models.BinaryField(null=True, blank=True)
    
    # Evidence metadata
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Evidence validation
    is_valid = models.BooleanField(default=True)
    validation_notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.control.control_id} - {self.title}"

class SecurityScan(models.Model):
    """Security scan results"""
    scan_id = models.CharField(max_length=100, unique=True)
    scan_type = models.CharField(max_length=50, choices=[
        ('malware', 'Malware Scan'),
        ('vulnerability', 'Vulnerability Scan'),
        ('compliance', 'Compliance Scan'),
        ('configuration', 'Configuration Scan'),
        ('access_control', 'Access Control Scan'),
        ('backup_verification', 'Backup Verification'),
        ('comprehensive', 'Comprehensive Security Scan')
    ])
    
    target = models.CharField(max_length=255)
    tool = models.CharField(max_length=50, choices=[
        ('clamav', 'ClamAV'),
        ('lynis', 'Lynis'),
        ('rkhunter', 'RKHunter'),
        ('openvas', 'OpenVAS'),
        ('custom', 'Custom Script')
    ])
    
    # Scan results
    status = models.CharField(max_length=20, choices=[
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], default='running')
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Results summary
    total_items = models.IntegerField(default=0)
    threats_found = models.IntegerField(default=0)
    warnings_found = models.IntegerField(default=0)
    clean_items = models.IntegerField(default=0)
    
    # Security score (0-100)
    security_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Detailed results (stored as JSON)
    results_data = models.JSONField(default=dict)
    
    # Compliance mapping
    related_controls = models.ManyToManyField(ComplianceControl, blank=True, related_name='security_scans')
    
    # Automation metadata
    is_automated = models.BooleanField(default=True)
    automation_script = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return f"{self.scan_type} - {self.scan_id}"
    
    def save(self, *args, **kwargs):
        if not self.scan_id:
            self.scan_id = f"scan-{uuid.uuid4().hex[:8]}"
        if self.completed_at and self.started_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())
        super().save(*args, **kwargs)

class ComplianceReport(models.Model):
    """Compliance reports and assessments"""
    report_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    framework = models.ForeignKey(ComplianceFramework, on_delete=models.CASCADE, related_name='reports')
    
    REPORT_TYPES = [
        ('assessment', 'Compliance Assessment'),
        ('audit', 'Audit Report'),
        ('gap_analysis', 'Gap Analysis'),
        ('remediation', 'Remediation Report'),
        ('status', 'Status Report'),
        ('summary', 'Executive Summary')
    ]
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    
    # Report period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Report status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Report data
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Compliance metrics
    total_controls = models.IntegerField(default=0)
    implemented_controls = models.IntegerField(default=0)
    automated_controls = models.IntegerField(default=0)
    compliant_controls = models.IntegerField(default=0)
    
    # Compliance percentage
    compliance_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Report content (stored as JSON)
    report_data = models.JSONField(default=dict)
    
    # File attachments
    pdf_report = models.FileField(upload_to='compliance_reports/', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.report_id:
            self.report_id = f"report-{uuid.uuid4().hex[:8]}"
        if self.total_controls > 0:
            self.compliance_percentage = (self.compliant_controls / self.total_controls) * 100
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.framework.name} - {self.title} ({self.period_start} to {self.period_end})"

class DataRetentionPolicy(models.Model):
    """Data retention policies for compliance"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    
    # Data types
    data_types = models.JSONField(default=list, help_text="List of data types this policy applies to")
    
    # Retention settings
    retention_days = models.IntegerField(help_text="Number of days to retain data")
    archive_before_delete = models.BooleanField(default=True, help_text="Archive data before deletion")
    
    # Compliance frameworks
    frameworks = models.ManyToManyField(ComplianceFramework, related_name='retention_policies')
    
    # Policy status
    is_active = models.BooleanField(default=True)
    last_enforced = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.retention_days} days)"

class ComplianceAlert(models.Model):
    """Compliance alerts and notifications"""
    alert_id = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    ALERT_TYPES = [
        ('control_failure', 'Control Implementation Failure'),
        ('evidence_expiry', 'Evidence Expiry Warning'),
        ('scan_failure', 'Security Scan Failure'),
        ('compliance_gap', 'Compliance Gap Detected'),
        ('policy_violation', 'Policy Violation'),
        ('audit_due', 'Audit Due Soon'),
        ('evidence_missing', 'Evidence Missing'),
        ('retention_policy', 'Data Retention Policy')
    ]
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    
    # Severity
    SEVERITY_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical')
    ]
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    
    # Related items
    related_controls = models.ManyToManyField(ComplianceControl, blank=True, related_name='alerts')
    related_scans = models.ManyToManyField(SecurityScan, blank=True, related_name='alerts')
    
    # Alert status
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_severity_display()}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.alert_id:
            self.alert_id = f"alert-{uuid.uuid4().hex[:8]}"
        if self.is_resolved and not self.resolved_at:
            self.resolved_at = timezone.now()
        super().save(*args, **kwargs)
