from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import TrashItem, TrashSettings, TrashOperation


@admin.register(TrashItem)
class TrashItemAdmin(admin.ModelAdmin):
    list_display = [
        'item_name', 'item_type', 'deleted_by', 'deleted_at',
        'size_display', 'expiry_status', 'is_restored', 'is_permanently_deleted'
    ]
    list_filter = [
        'item_type', 'is_restored', 'is_permanently_deleted',
        'deleted_at', 'auto_delete_at'
    ]
    search_fields = ['item_name', 'original_path', 'deleted_by__username']
    readonly_fields = [
        'deleted_at', 'restored_at', 'permanently_deleted_at',
        'size_display', 'expiry_info'
    ]
    raw_id_fields = ['deleted_by', 'restored_by', 'permanently_deleted_by']
    list_per_page = 50

    fieldsets = (
        ('Item Information', {
            'fields': ('item_name', 'item_type', 'original_path', 'size', 'size_display')
        }),
        ('Ownership & Tracking', {
            'fields': ('deleted_by', 'deleted_at', 'restored_by', 'restored_at')
        }),
        ('Permanent Deletion', {
            'fields': ('is_permanently_deleted', 'permanently_deleted_by', 'permanently_deleted_at')
        }),
        ('Retention', {
            'fields': ('retention_days', 'auto_delete_at', 'expiry_info')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )

    def size_display(self, obj):
        return obj.get_size_display()
    size_display.short_description = "Size"
    size_display.admin_order_field = 'size'

    def expiry_status(self, obj):
        if obj.is_restored:
            return format_html('<span style="color: #00ff88;">✓ Restored</span>')
        if obj.is_permanently_deleted:
            return format_html('<span style="color: #ff4444;">✗ Permanently Deleted</span>')

        if obj.is_expired():
            return format_html('<span style="color: #ffaa00;">⏰ Expired</span>')
        else:
            days = obj.days_until_expiry()
            return format_html(f'<span style="color: #00aaff;">{days} days left</span>')
    expiry_status.short_description = "Status"

    def expiry_info(self, obj):
        info = []
        if obj.auto_delete_at:
            info.append(f"Auto-delete: {obj.auto_delete_at.strftime('%Y-%m-%d %H:%M')}")
        if obj.retention_days:
            info.append(f"Retention: {obj.retention_days} days")

        return "\n".join(info) if info else "No retention info"
    expiry_info.short_description = "Retention Info"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'deleted_by', 'restored_by', 'permanently_deleted_by'
        )

    def has_delete_permission(self, request, obj=None):
        # Prevent direct deletion from admin (use permanent delete instead)
        return False

    actions = ['mark_as_restored', 'mark_as_permanently_deleted', 'extend_retention']

    def mark_as_restored(self, request, queryset):
        updated = 0
        for item in queryset.filter(is_restored=False, is_permanently_deleted=False):
            item.restore(user=request.user)
            updated += 1

        self.message_user(
            request,
            f'{updated} items marked as restored.'
        )
    mark_as_restored.short_description = "Mark selected items as restored"

    def mark_as_permanently_deleted(self, request, queryset):
        updated = 0
        for item in queryset.filter(is_permanently_deleted=False):
            item.permanent_delete(user=request.user)
            updated += 1

        self.message_user(
            request,
            f'{updated} items permanently deleted.'
        )
    mark_as_permanently_deleted.short_description = "Permanently delete selected items"

    def extend_retention(self, request, queryset):
        days = 30  # Default extension
        updated = 0

        for item in queryset.filter(is_restored=False, is_permanently_deleted=False):
            item.retention_days += days
            item.save()
            updated += 1

        self.message_user(
            request,
            f'Extended retention by {days} days for {updated} items.'
        )
    extend_retention.short_description = "Extend retention by 30 days"


@admin.register(TrashSettings)
class TrashSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'default_retention_days', 'max_retention_days',
        'max_trash_size_gb', 'enable_auto_cleanup'
    ]
    readonly_fields = ['__str__']

    fieldsets = (
        ('Retention Settings', {
            'fields': ('default_retention_days', 'max_retention_days')
        }),
        ('Size Limits', {
            'fields': ('max_trash_size_gb',)
        }),
        ('Auto-Cleanup', {
            'fields': ('enable_auto_cleanup', 'cleanup_schedule_hours')
        }),
        ('Notifications', {
            'fields': ('notify_before_deletion_days',)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one settings instance
        return not TrashSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False


@admin.register(TrashOperation)
class TrashOperationAdmin(admin.ModelAdmin):
    list_display = [
        'operation', 'performed_by', 'performed_at',
        'items_count', 'ip_address'
    ]
    list_filter = ['operation', 'performed_at', 'performed_by']
    search_fields = ['performed_by__username', 'details']
    readonly_fields = ['operation', 'performed_by', 'performed_at', 'items_count', 'ip_address', 'details']
    raw_id_fields = ['performed_by', 'items_affected']
    list_per_page = 100

    def has_add_permission(self, request):
        return False  # Operations are created automatically

    def has_change_permission(self, request, obj=None):
        return False  # Operations should not be modified

    def has_delete_permission(self, request, obj=None):
        return False  # Operations should not be deleted
