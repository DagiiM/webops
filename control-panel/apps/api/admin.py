"""Admin configuration for API app."""

from django.contrib import admin
from .models import APIToken


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    """Admin interface for API tokens."""

    list_display = ('name', 'user', 'is_active', 'last_used', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__username')
    readonly_fields = ('token', 'created_at', 'updated_at', 'last_used')

    fieldsets = (
        ('Token Information', {
            'fields': ('name', 'user', 'is_active', 'expires_at')
        }),
        ('Token Value', {
            'fields': ('token',),
            'description': 'This token will be generated automatically.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
