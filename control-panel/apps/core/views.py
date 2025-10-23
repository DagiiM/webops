"""
Core views for WebOps.

This module provides backward compatibility by importing views from their
new domain-specific locations. For new code, please import directly from
the domain modules instead of this compatibility layer.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .branding.views import branding_settings, reset_branding
from .integrations.views import (
    integrations_dashboard,
    github_connect_oauth,
    github_callback,
    github_disconnect,
    github_test,
    huggingface_connect,
    huggingface_disconnect,
    huggingface_test,
    huggingface_models,
    google_connect,
    google_connect_oauth,
    google_callback,
    google_disconnect,
    google_test,
)
from .webhooks.views import (
    webhook_list,
    webhook_create,
    webhook_detail,
    webhook_toggle,
    webhook_delete,
    webhook_handler,
    webhook_test,
)
from .notifications.views import (
    notification_list,
    notification_create,
    notification_detail,
    notification_toggle,
    notification_test,
    notification_delete,
)

def is_superuser(user):
    """Check if user is a superuser."""
    return user.is_superuser

@login_required
def user_settings(request):
    """View for general user settings with persistent preferences."""
    from .auth.models import UserPreferences
    
    # Get or create user preferences
    preferences = UserPreferences.get_preferences(request.user)
    
    if request.method == 'POST':
        # Handle form submission
        try:
            # Update user information
            user = request.user
            
            # Update email
            email = request.POST.get('email')
            if email:
                user.email = email
            
            # Update names
            first_name = request.POST.get('first_name')
            if first_name:
                user.first_name = first_name
                
            last_name = request.POST.get('last_name')
            if last_name:
                user.last_name = last_name
            
            # Save user changes
            user.save()
            
            # Handle appearance preferences
            theme = request.POST.get('theme')
            if theme:
                preferences.theme = theme
            
            animations = request.POST.get('animations') == 'on'
            preferences.animations_enabled = animations
            
            compact_view = request.POST.get('compact_view') == 'on'
            preferences.compact_view = compact_view
            
            font_size = request.POST.get('font_size')
            if font_size:
                preferences.font_size = font_size
            
            # Handle language and regional preferences
            interface_language = request.POST.get('interface_language')
            if interface_language:
                preferences.interface_language = interface_language
            
            timezone = request.POST.get('timezone')
            if timezone:
                preferences.timezone = timezone
            
            date_format = request.POST.get('date_format')
            if date_format:
                preferences.date_format = date_format
            
            time_format = request.POST.get('time_format')
            if time_format:
                preferences.time_format = time_format
            
            # Handle notification preferences
            email_notifications = request.POST.get('email_notifications_enabled') == 'on'
            preferences.email_notifications_enabled = email_notifications
            
            browser_notifications = request.POST.get('browser_notifications_enabled') == 'on'
            preferences.browser_notifications_enabled = browser_notifications
            
            deployment_notifications = request.POST.get('deployment_notifications') == 'on'
            preferences.deployment_notifications = deployment_notifications
            
            security_notifications = request.POST.get('security_notifications') == 'on'
            preferences.security_notifications = security_notifications
            
            system_notifications = request.POST.get('system_notifications') == 'on'
            preferences.system_notifications = system_notifications
            
            notification_frequency = request.POST.get('notification_frequency')
            if notification_frequency:
                preferences.notification_frequency = notification_frequency
            
            # Handle privacy preferences
            activity_tracking = request.POST.get('activity_tracking') == 'on'
            preferences.activity_tracking = activity_tracking
            
            personalized_recommendations = request.POST.get('personalized_recommendations') == 'on'
            preferences.personalized_recommendations = personalized_recommendations
            
            third_party_integrations = request.POST.get('third_party_integrations') == 'on'
            preferences.third_party_integrations = third_party_integrations
            
            analytics_sharing = request.POST.get('analytics_sharing') == 'on'
            preferences.analytics_sharing = analytics_sharing
            
            # Handle dashboard preferences
            dashboard_layout = request.POST.get('dashboard_layout')
            if dashboard_layout:
                preferences.dashboard_layout = dashboard_layout
            
            default_dashboard_tab = request.POST.get('default_dashboard_tab')
            if default_dashboard_tab:
                preferences.default_dashboard_tab = default_dashboard_tab
            
            items_per_page = request.POST.get('items_per_page')
            if items_per_page:
                preferences.items_per_page = int(items_per_page)
            
            # Handle security preferences
            session_timeout = request.POST.get('session_timeout')
            if session_timeout:
                preferences.session_timeout = int(session_timeout)
            
            require_2fa_for_sensitive = request.POST.get('require_2fa_for_sensitive') == 'on'
            preferences.require_2fa_for_sensitive = require_2fa_for_sensitive
            
            login_notifications = request.POST.get('login_notifications') == 'on'
            preferences.login_notifications = login_notifications
            
            # Handle developer preferences
            show_advanced_options = request.POST.get('show_advanced_options') == 'on'
            preferences.show_advanced_options = show_advanced_options
            
            debug_mode = request.POST.get('debug_mode') == 'on'
            preferences.debug_mode = debug_mode
            
            beta_features = request.POST.get('beta_features') == 'on'
            preferences.beta_features = beta_features
            
            # Save preferences
            preferences.save()
            
            # Apply theme to session for immediate effect
            request.session['theme'] = preferences.theme
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Settings saved successfully!',
                    'preferences': preferences.to_dict()
                })
            
            # For non-AJAX requests, redirect back with success message
            from django.contrib import messages
            messages.success(request, 'Settings saved successfully!')
            return redirect(request.path)
            
        except Exception as e:
            # Handle errors
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': str(e),
                    'errors': {'__all__': [str(e)]}
                }, status=400)
            
            # For non-AJAX requests, show error message
            from django.contrib import messages
            messages.error(request, f'Error saving settings: {str(e)}')
    
    # For GET requests, render the page with current preferences
    return render(request, 'core/user_settings.html', {
        'page_title': 'User Settings',
        'preferences': preferences.to_dict(),
        'user': request.user,
    })

# Re-export for backward compatibility
__all__ = [
    # Branding views
    'branding_settings',
    'reset_branding',
    
    # General settings view
    'user_settings',
    
    # Integration views
    'integrations_dashboard',
    'github_connect',
    'github_connect_oauth',
    'github_callback',
    'github_disconnect',
    'github_test',
    'huggingface_connect',
    'huggingface_disconnect',
    'huggingface_test',
    'huggingface_models',
    'google_connect',
    'google_connect_oauth',
    'google_callback',
    'google_disconnect',
    'google_test',
    
    # Webhook views
    'webhook_list',
    'webhook_create',
    'webhook_detail',
    'webhook_toggle',
    'webhook_delete',
    'webhook_handler',
    'webhook_test',
    
    # Notification views
    'notification_list',
    'notification_create',
    'notification_detail',
    'notification_toggle',
    'notification_test',
    'notification_delete',
]
