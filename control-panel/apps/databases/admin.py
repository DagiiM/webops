"""Django admin configuration for Databases app."""

from django.contrib import admin
from .models import Database


@admin.register(Database)
class DatabaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'username', 'host', 'port', 'deployment', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'username']
    readonly_fields = ['created_at', 'updated_at']