"""
Core views for WebOps.

Reference: CLAUDE.md "API Design" section
Handles branding settings and core functionality.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.models import BrandingSettings
from apps.core.forms import BrandingSettingsForm, GoogleOAuthConfigForm


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
def google_oauth_config(request):
    """View for managing Google OAuth configuration (admin only)."""
    from django.conf import settings
    from apps.core.integration_services import GoogleIntegrationService
    from apps.core.config_service import config_service
    
    # Check current OAuth configuration status using the config service
    oauth_config = config_service.get_oauth_config('google')
    oauth_configured = config_service.is_oauth_configured('google')
    
    # Get connection status if OAuth is configured
    connection_status = None
    user_connections = []
    if oauth_configured:
        google_service = GoogleIntegrationService()
        try:
            # Test the OAuth configuration (not user connection)
            is_valid, status_message = google_service.test_oauth_config()
            connection_status = {
                'is_valid': is_valid,
                'message': status_message,
                'client_id_partial': oauth_config['client_id'][:20] + '...' if oauth_config['client_id'] else None
            }
        except Exception as e:
            connection_status = {
                'is_valid': False,
                'message': f'Error testing configuration: {str(e)}',
                'client_id_partial': oauth_config['client_id'][:20] + '...' if oauth_config['client_id'] else None
            }
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        
        if action == 'test_connection':
            # Handle AJAX test connection request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                try:
                    google_service = GoogleIntegrationService()
                    is_valid, message = google_service.test_oauth_config()
                    return JsonResponse({
                        'success': is_valid,
                        'error': message if not is_valid else None,
                        'message': message
                    })
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'error': str(e)
                    })
            else:
                # Non-AJAX fallback
                if oauth_configured:
                    google_service = GoogleIntegrationService()
                    is_valid, message = google_service.test_oauth_config()
                    if is_valid:
                        messages.success(request, f'✅ Configuration test successful: {message}')
                    else:
                        messages.error(request, f'❌ Configuration test failed: {message}')
                else:
                    messages.error(request, 'OAuth is not configured. Please save your credentials first.')
                return redirect('google_oauth_config')
        
        elif action == 'save':
            form = GoogleOAuthConfigForm(request.POST)
            if form.is_valid():
                client_id = form.cleaned_data.get('google_oauth_client_id')
                client_secret = form.cleaned_data.get('google_oauth_client_secret')
                redirect_uri = form.cleaned_data.get('google_oauth_redirect_uri')
                
                try:
                    if client_id and client_secret:
                        # Validate the OAuth configuration
                        is_valid, error_message = config_service.validate_oauth_config('google', client_id, client_secret)
                        
                        if is_valid:
                            # Save the OAuth configuration to the database
                            config_service.set_oauth_config('google', client_id, client_secret, redirect_uri or '')
                            
                            messages.success(
                                request, 
                                '✅ Google OAuth credentials have been saved successfully and are now active! '
                                'The configuration has been applied dynamically without requiring a restart.'
                            )
                        else:
                            messages.error(request, f'❌ Invalid OAuth configuration: {error_message}')
                    else:
                        # Clear OAuth configuration if credentials are empty
                        config_service.delete_config(config_service.GOOGLE_OAUTH_CLIENT_ID)
                        config_service.delete_config(config_service.GOOGLE_OAUTH_CLIENT_SECRET)
                        config_service.delete_config(config_service.GOOGLE_OAUTH_REDIRECT_URI)
                        
                        messages.success(request, '⚠️ Google OAuth has been disabled and credentials removed.')
                    
                except Exception as e:
                    messages.error(request, f'❌ Error saving OAuth configuration: {str(e)}')
                
                return redirect('google_oauth_config')
    else:
        # Pre-populate form with current configuration from database
        form = GoogleOAuthConfigForm(initial={
            'google_oauth_client_id': oauth_config['client_id'],
            'google_oauth_client_secret': oauth_config['client_secret'],
            'google_oauth_redirect_uri': oauth_config['redirect_uri'],
        })
        
        # Set the redirect URI dynamically if not already set
        if not oauth_config['redirect_uri']:
            from django.urls import reverse
            redirect_uri = request.build_absolute_uri(reverse('google_login_callback'))
            form.fields['google_oauth_redirect_uri'].initial = redirect_uri
    
    return render(request, 'core/google_oauth_config.html', {
        'form': form,
        'oauth_configured': oauth_configured,
        'connection_status': connection_status,
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


@login_required
def toast_test(request):
    """View for testing toast notifications."""
    return render(request, 'toast-test.html')


@login_required
@require_http_methods(["POST"])
def test_toast_messages(request):
    """Test view for Django messages to toast conversion."""
    message_type = request.POST.get('message_type', 'info')
    message = request.POST.get('message', 'Test message')
    
    # Add Django message based on type
    if message_type == 'success':
        messages.success(request, message)
    elif message_type == 'error':
        messages.error(request, message)
    elif message_type == 'warning':
        messages.warning(request, message)
    else:
        messages.info(request, message)
    
    return render(request, 'toast-test.html')
