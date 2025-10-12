"""
Core views for WebOps.

Reference: CLAUDE.md "API Design" section
Handles branding settings and core functionality.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.models import BrandingSettings
from apps.core.forms import BrandingSettingsForm


def is_superuser(user):
    """Check if user is a superuser."""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def branding_settings(request):
    """View for managing branding settings (admin only)."""
    settings = BrandingSettings.get_settings()

    if request.method == 'POST':
        form = BrandingSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            # Update settings
            settings.site_name = form.cleaned_data['site_name']
            settings.primary_color = form.cleaned_data['primary_color']
            settings.secondary_color = form.cleaned_data['secondary_color']
            settings.accent_color = form.cleaned_data['accent_color']
            settings.header_bg_color = form.cleaned_data['header_bg_color']

            # Handle file uploads
            if form.cleaned_data.get('logo'):
                settings.logo = form.cleaned_data['logo']
            if form.cleaned_data.get('favicon'):
                settings.favicon = form.cleaned_data['favicon']

            settings.save()
            messages.success(request, 'Branding settings updated successfully!')
            return redirect('branding_settings')
    else:
        # Populate form with current settings
        form = BrandingSettingsForm(initial={
            'site_name': settings.site_name,
            'primary_color': settings.primary_color,
            'secondary_color': settings.secondary_color,
            'accent_color': settings.accent_color,
            'header_bg_color': settings.header_bg_color,
        })

    return render(request, 'core/branding_settings.html', {
        'form': form,
        'settings': settings,
    })


@login_required
@user_passes_test(is_superuser)
@require_http_methods(["POST"])
def reset_branding(request):
    """Reset branding to default values."""
    settings = BrandingSettings.get_settings()
    settings.site_name = 'WebOps'
    settings.primary_color = '#3b82f6'
    settings.secondary_color = '#1e40af'
    settings.accent_color = '#10b981'
    settings.header_bg_color = '#1f2937'
    settings.logo = None
    settings.favicon = None
    settings.save()

    return JsonResponse({'status': 'success', 'message': 'Branding reset to defaults'})
