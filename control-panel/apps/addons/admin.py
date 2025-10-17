from django.contrib import admin
from .models import Addon

@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'version', 'enabled', 'author',
        'success_count', 'failure_count', 'last_success_at', 'last_run_at', 'last_duration_ms'
    )
    search_fields = ('name', 'author')
    list_filter = ('enabled',)