"""
Django Admin for KVM Addon

Admin interface for managing VMs, compute nodes, plans, and templates.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ComputeNode,
    VMPlan,
    OSTemplate,
    VMDeployment,
    VMSnapshot,
    VMUsageRecord,
    VMQuota,
)


@admin.register(ComputeNode)
class ComputeNodeAdmin(admin.ModelAdmin):
    list_display = [
        'hostname',
        'is_active',
        'total_vcpus',
        'total_memory_mb',
        'total_disk_gb',
        'available_resources',
        'vm_count',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['hostname']
    readonly_fields = ['created_at', 'updated_at', 'resource_usage']

    fieldsets = (
        ('Basic Information', {
            'fields': ('hostname', 'is_active', 'libvirt_uri')
        }),
        ('Resources', {
            'fields': (
                'total_vcpus',
                'total_memory_mb',
                'total_disk_gb',
                'cpu_overcommit_ratio',
                'memory_overcommit_ratio',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('resource_usage',),
        }),
    )

    def available_resources(self, obj):
        """Display available resources."""
        return format_html(
            'CPU: {}<br>RAM: {} MB<br>Disk: {} GB',
            obj.available_vcpus(),
            obj.available_memory_mb(),
            obj.available_disk_gb(),
        )
    available_resources.short_description = 'Available Resources'

    def vm_count(self, obj):
        """Display count of VMs on this node."""
        count = obj.vm_deployments.count()
        return count
    vm_count.short_description = 'VMs'

    def resource_usage(self, obj):
        """Display detailed resource usage."""
        total_vcpus = obj.total_vcpus
        available_vcpus = obj.available_vcpus()
        allocated_vcpus = total_vcpus - available_vcpus
        cpu_pct = (allocated_vcpus / total_vcpus * 100) if total_vcpus > 0 else 0

        total_memory = obj.total_memory_mb
        available_memory = obj.available_memory_mb()
        allocated_memory = total_memory - available_memory
        memory_pct = (allocated_memory / total_memory * 100) if total_memory > 0 else 0

        total_disk = obj.total_disk_gb
        available_disk = obj.available_disk_gb()
        allocated_disk = total_disk - available_disk
        disk_pct = (allocated_disk / total_disk * 100) if total_disk > 0 else 0

        return format_html(
            '<strong>CPU:</strong> {}/{} vCPUs ({:.1f}% allocated)<br>'
            '<strong>Memory:</strong> {}/{} MB ({:.1f}% allocated)<br>'
            '<strong>Disk:</strong> {}/{} GB ({:.1f}% allocated)',
            allocated_vcpus, total_vcpus, cpu_pct,
            allocated_memory, total_memory, memory_pct,
            allocated_disk, total_disk, disk_pct,
        )
    resource_usage.short_description = 'Resource Usage'


@admin.register(VMPlan)
class VMPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'display_name',
        'vcpus',
        'memory_display',
        'disk_gb',
        'hourly_price',
        'is_active',
        'deployment_count',
        'sort_order',
    ]
    list_filter = ['is_active']
    search_fields = ['name', 'display_name']
    ordering = ['sort_order', 'name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active', 'sort_order')
        }),
        ('Resources', {
            'fields': ('vcpus', 'memory_mb', 'disk_gb')
        }),
        ('Pricing', {
            'fields': ('hourly_price',)
        }),
    )

    def memory_display(self, obj):
        """Display memory in GB."""
        return f"{obj.memory_gb:.1f} GB"
    memory_display.short_description = 'Memory'

    def deployment_count(self, obj):
        """Display count of deployments using this plan."""
        count = obj.deployments.count()
        return count
    deployment_count.short_description = 'Deployments'


@admin.register(OSTemplate)
class OSTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'display_name',
        'os_family',
        'os_version',
        'image_size_gb',
        'supports_cloud_init',
        'is_active',
        'deployment_count',
    ]
    list_filter = ['os_family', 'is_active', 'supports_cloud_init']
    search_fields = ['name', 'display_name']
    ordering = ['sort_order', 'display_name']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active', 'sort_order')
        }),
        ('Operating System', {
            'fields': ('os_family', 'os_version')
        }),
        ('Storage', {
            'fields': ('image_path', 'image_size_gb')
        }),
        ('Features', {
            'fields': ('supports_cloud_init',)
        }),
    )

    def deployment_count(self, obj):
        """Display count of deployments using this template."""
        count = obj.deployments.count()
        return count
    deployment_count.short_description = 'Deployments'


@admin.register(VMDeployment)
class VMDeploymentAdmin(admin.ModelAdmin):
    list_display = [
        'vm_name',
        'deployment_link',
        'compute_node',
        'vm_plan',
        'os_template',
        'libvirt_state',
        'ip_address',
        'ssh_port',
        'created_at',
    ]
    list_filter = ['libvirt_state', 'compute_node', 'os_template', 'created_at']
    search_fields = ['vm_name', 'vm_uuid', 'ip_address']
    readonly_fields = [
        'vm_uuid',
        'mac_address',
        'created_at',
        'updated_at',
        'ssh_command_display',
    ]

    fieldsets = (
        ('VM Information', {
            'fields': (
                'deployment',
                'vm_name',
                'vm_uuid',
                'libvirt_state',
            )
        }),
        ('Infrastructure', {
            'fields': (
                'compute_node',
                'vm_plan',
                'os_template',
            )
        }),
        ('Resources', {
            'fields': ('vcpus', 'memory_mb', 'disk_gb', 'disk_path')
        }),
        ('Networking', {
            'fields': (
                'ip_address',
                'mac_address',
                'ssh_port',
                'vnc_port',
                'ssh_command_display',
            )
        }),
        ('Access', {
            'fields': ('root_password', 'ssh_public_keys'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def deployment_link(self, obj):
        """Link to deployment."""
        url = reverse('admin:deployments_deployment_change', args=[obj.deployment.id])
        return format_html('<a href="{}">{}</a>', url, obj.deployment.name)
    deployment_link.short_description = 'Deployment'

    def ssh_command_display(self, obj):
        """Display SSH command."""
        return obj.get_ssh_command()
    ssh_command_display.short_description = 'SSH Command'


@admin.register(VMSnapshot)
class VMSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'vm_deployment',
        'disk_size_mb',
        'is_active',
        'created_at',
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description', 'vm_deployment__vm_name']
    readonly_fields = ['snapshot_xml', 'created_at', 'updated_at']

    fieldsets = (
        ('Snapshot Information', {
            'fields': ('vm_deployment', 'name', 'description', 'is_active')
        }),
        ('Technical Details', {
            'fields': ('disk_size_mb', 'snapshot_xml'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VMUsageRecord)
class VMUsageRecordAdmin(admin.ModelAdmin):
    list_display = [
        'vm_deployment',
        'timestamp',
        'state',
        'vcpus',
        'memory_mb',
        'disk_gb',
        'hourly_rate',
        'cost',
    ]
    list_filter = ['state', 'timestamp']
    search_fields = ['vm_deployment__vm_name']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp', 'created_at', 'updated_at']

    fieldsets = (
        ('Usage Information', {
            'fields': (
                'vm_deployment',
                'timestamp',
                'state',
                'uptime_seconds',
            )
        }),
        ('Resources', {
            'fields': ('vcpus', 'memory_mb', 'disk_gb')
        }),
        ('Billing', {
            'fields': ('hourly_rate', 'cost')
        }),
    )

    def has_add_permission(self, request):
        """Disable manual creation of usage records."""
        return False


@admin.register(VMQuota)
class VMQuotaAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'max_vms',
        'max_vcpus',
        'max_memory_display',
        'max_disk_gb',
        'current_usage',
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'current_usage']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('VM Limits', {
            'fields': ('max_vms',)
        }),
        ('Resource Limits', {
            'fields': (
                'max_vcpus',
                'max_memory_mb',
                'max_disk_gb',
            )
        }),
        ('Current Usage', {
            'fields': ('current_usage',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def max_memory_display(self, obj):
        """Display memory in GB."""
        return f"{obj.max_memory_mb / 1024:.1f} GB"
    max_memory_display.short_description = 'Max Memory'

    def current_usage(self, obj):
        """Display current resource usage."""
        from django.db.models import Sum, Count

        vms = VMDeployment.objects.filter(
            deployment__user=obj.user,
            deployment__status__in=['running', 'deploying', 'stopped']
        )

        vm_count = vms.count()
        total_vcpus = vms.aggregate(Sum('vcpus'))['vcpus__sum'] or 0
        total_memory = vms.aggregate(Sum('memory_mb'))['memory_mb__sum'] or 0
        total_disk = vms.aggregate(Sum('disk_gb'))['disk_gb__sum'] or 0

        return format_html(
            '<strong>VMs:</strong> {}/{}<br>'
            '<strong>vCPUs:</strong> {}/{}<br>'
            '<strong>Memory:</strong> {} MB / {} MB<br>'
            '<strong>Disk:</strong> {} GB / {} GB',
            vm_count, obj.max_vms,
            total_vcpus, obj.max_vcpus,
            total_memory, obj.max_memory_mb,
            total_disk, obj.max_disk_gb,
        )
    current_usage.short_description = 'Current Usage'
