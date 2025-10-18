"""
URL configuration for core app (authentication and integrations).

Reference: CLAUDE.md "URL Routing" section
"""

from django.urls import path
from . import auth_views, views, integration_views

urlpatterns = [
    # Authentication
    path('login/', auth_views.login_view, name='login'),
    path('register/', auth_views.register_view, name='register'),
    path('logout/', auth_views.logout_view, name='logout'),

    # Password Reset
    path('password-reset/', auth_views.password_reset_request, name='password_reset'),
    path('password-reset/<uidb64>/<token>/', auth_views.password_reset_confirm, name='password_reset_confirm'),

    # Two-Factor Authentication
    path('2fa/setup/', auth_views.two_factor_setup, name='two_factor_setup'),
    path('2fa/verify/', auth_views.two_factor_verify, name='two_factor_verify'),
    path('2fa/disable/', auth_views.two_factor_disable, name='two_factor_disable'),

    # Branding Settings
    path('settings/branding/', views.branding_settings, name='branding_settings'),
    path('settings/branding/reset/', views.reset_branding, name='reset_branding'),
    
    # Google OAuth Configuration
    path('settings/google-oauth/', views.google_oauth_config, name='google_oauth_config'),

    # Platform Integrations
    path('integrations/', integration_views.integrations_dashboard, name='integrations_dashboard'),

    # GitHub Integration
    path('integrations/github/connect/', integration_views.github_connect, name='github_connect'),
    path('integrations/github/oauth/', integration_views.github_connect_oauth, name='github_connect_oauth'),
    path('integrations/github/callback/', integration_views.github_callback, name='github_callback'),
    path('integrations/github/disconnect/', integration_views.github_disconnect, name='github_disconnect'),
    path('integrations/github/test/', integration_views.github_test, name='github_test'),

    # Hugging Face Integration
    path('integrations/huggingface/connect/', integration_views.huggingface_connect, name='huggingface_connect'),
    path('integrations/huggingface/disconnect/', integration_views.huggingface_disconnect, name='huggingface_disconnect'),
    path('integrations/huggingface/test/', integration_views.huggingface_test, name='huggingface_test'),
    path('integrations/huggingface/models/', integration_views.huggingface_models, name='huggingface_models'),

    # Webhooks (placeholder views to be implemented)
    path('integrations/webhooks/', integration_views.webhook_list, name='webhook_list'),

    # Notifications (placeholder views to be implemented)
    path('integrations/notifications/', integration_views.notification_list, name='notification_list'),
    path('login/google/', auth_views.google_login_start, name='google_login'),
    path('login/google/callback/', auth_views.google_login_callback, name='google_login_callback'),
    path('integrations/google/connect/', integration_views.google_connect, name='google_connect'),
    path('integrations/google/oauth/', integration_views.google_connect_oauth, name='google_connect_oauth'),
    path('integrations/google/callback/', integration_views.google_callback, name='google_callback'),
    path('integrations/google/disconnect/', integration_views.google_disconnect, name='google_disconnect'),
    path('integrations/google/test/', integration_views.google_test, name='google_test'),
    
    # Toast Test Pages
    path('test/toast/', views.toast_test, name='toast_test'),
    path('test/toast-messages/', views.test_toast_messages, name='test-toast-messages'),
]
