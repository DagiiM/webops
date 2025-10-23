"""
Branding views for WebOps.

"API Design" section
Handles branding settings and theme management.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from apps.core.branding.models import BrandingSettings
from apps.core.branding.forms import BrandingSettingsForm


def is_superuser(user):
    """Check if user is a superuser."""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def branding_settings(request):
    """View for managing branding settings (admin only)."""
    settings = BrandingSettings.get_settings()

    if request.method == 'POST':
        form = BrandingSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            # Update all settings including HSL fields
            settings.site_name = form.cleaned_data['site_name']
            
            # HSL color generation fields
            settings.primary_hue = form.cleaned_data['primary_hue']
            settings.primary_saturation = form.cleaned_data['primary_saturation']
            settings.primary_lightness = form.cleaned_data['primary_lightness']
            settings.color_harmony = form.cleaned_data['color_harmony']
            
            # Accessibility options
            settings.enforce_wcag_aa = form.cleaned_data['enforce_wcag_aa']
            settings.enforce_wcag_aaa = form.cleaned_data['enforce_wcag_aaa']
            settings.supports_dark_mode = form.cleaned_data['supports_dark_mode']

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
            'primary_hue': settings.primary_hue,
            'primary_saturation': settings.primary_saturation,
            'primary_lightness': settings.primary_lightness,
            'color_harmony': settings.color_harmony,
            'enforce_wcag_aa': settings.enforce_wcag_aa,
            'enforce_wcag_aaa': settings.enforce_wcag_aaa,
            'supports_dark_mode': settings.supports_dark_mode,
            # Legacy hex colors (auto-generated, read-only)
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
    
    # Reset to default HSL values
    settings.site_name = 'WebOps'
    settings.primary_hue = 210  # Blue hue
    settings.primary_saturation = 80
    settings.primary_lightness = 50
    settings.color_harmony = 'complementary'
    settings.enforce_wcag_aa = True
    settings.enforce_wcag_aaa = False
    settings.supports_dark_mode = True
    
    # Clear file uploads
    settings.logo = None
    settings.favicon = None
    
    settings.save()

    return JsonResponse({'status': 'success', 'message': 'Branding reset to defaults'})