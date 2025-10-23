"""
Integration views for GitHub, Hugging Face, and Google.

"API Design" section
Handles OAuth flows and API token management.
"""

import secrets
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.urls import reverse

from apps.core.integrations.services import (
    GitHubIntegrationService,
    HuggingFaceIntegrationService,
    GoogleIntegrationService
)
from apps.core.integrations.models import GitHubConnection, HuggingFaceConnection, GoogleConnection


@login_required
def integrations_dashboard(request):
    """
    Main integrations dashboard showing connection status.
    """
    from apps.core.webhooks.models import Webhook
    from apps.core.notifications.models import NotificationChannel, NotificationLog
    from django.db.models import Count, Sum

    # Check GitHub connection
    github_connected = False
    github_username = None
    try:
        github_conn = GitHubConnection.objects.get(user=request.user)
        github_connected = True
        github_username = github_conn.username
    except GitHubConnection.DoesNotExist:
        pass

    # Check Hugging Face connection
    hf_connected = False
    hf_username = None
    try:
        hf_conn = HuggingFaceConnection.objects.get(user=request.user)
        hf_connected = hf_conn.is_valid
        hf_username = hf_conn.username
    except HuggingFaceConnection.DoesNotExist:
        pass

    # Check Google connection
    google_connected = False
    google_email = None
    try:
        g_conn = GoogleConnection.objects.get(user=request.user)
        google_connected = g_conn.is_valid
        google_email = g_conn.email
    except GoogleConnection.DoesNotExist:
        pass

    # Webhook stats
    webhook_count = Webhook.objects.filter(user=request.user, is_active=True).count()
    webhook_triggers = (
        Webhook.objects.filter(user=request.user).aggregate(total=Sum("trigger_count"))[
            "total"
        ]
        or 0
    )

    # Notification stats
    notification_count = NotificationChannel.objects.filter(
        user=request.user, is_active=True
    ).count()
    notifications_sent = (
        NotificationChannel.objects.filter(user=request.user).aggregate(
            total=Sum("notification_count")
        )["total"]
        or 0
    )

    # Auto-deployment stats
    from apps.core.webhooks.models import WebhookDelivery
    auto_deployments = WebhookDelivery.objects.filter(
        webhook__user=request.user, status=WebhookDelivery.Status.SUCCESS
    ).count()

    # Connected platforms
    connected_platforms = sum(
        [1 for connected in [github_connected, hf_connected, google_connected] if connected]
    )

    context = {
        "github_connected": github_connected,
        "github_username": github_username,
        "hf_connected": hf_connected,
        "hf_username": hf_username,
        "google_connected": google_connected,
        "google_email": google_email,
        "webhook_count": webhook_count,
        "notification_count": notification_count,
        "webhook_triggers": webhook_triggers,
        "notifications_sent": notifications_sent,
        "auto_deployments": auto_deployments,
        "connected_platforms": connected_platforms,
    }

    return render(request, "integrations/dashboard.html", context)


@login_required
def github_connect(request):
    """
    Connect GitHub account with Personal Access Token.

    This provides a simpler alternative to OAuth for self-hosted setups.
    Users can generate a PAT at https://github.com/settings/tokens
    """
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()

        if not token:
            messages.error(request, 'Please provide a GitHub Personal Access Token.')
            return render(request, 'integrations/github_connect.html')

        # Validate and save connection
        github_service = GitHubIntegrationService()
        connection = github_service.save_connection_with_pat(request.user, token)

        if connection:
            messages.success(
                request,
                f'Successfully connected to GitHub as @{connection.username}!'
            )
            return redirect('integrations_dashboard')
        else:
            messages.error(
                request,
                'Invalid GitHub token. Please check your token and try again.'
            )

    return render(request, 'integrations/github_connect.html')


@login_required
def github_connect_oauth(request):
    """
    Initiate GitHub OAuth flow (alternative to PAT).

    This requires OAuth app configuration in settings.
    """
    # Check if OAuth is configured
    if not settings.GITHUB_OAUTH_CLIENT_ID or not settings.GITHUB_OAUTH_CLIENT_SECRET:
        messages.error(
            request,
            'GitHub OAuth is not configured. Please use Personal Access Token instead.'
        )
        return redirect('github_connect')

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session['github_oauth_state'] = state

    # Get redirect URI
    redirect_uri = request.build_absolute_uri(reverse('github_callback'))

    # Generate authorization URL
    github_service = GitHubIntegrationService()
    auth_url = github_service.get_authorization_url(redirect_uri, state)

    return redirect(auth_url)


@login_required
def github_callback(request):
    """
    Handle GitHub OAuth callback.
    """
    # Verify state token
    state = request.GET.get('state')
    session_state = request.session.get('github_oauth_state')

    if not state or state != session_state:
        messages.error(request, 'Invalid OAuth state. Please try again.')
        return redirect('integrations_dashboard')

    # Clean up session
    del request.session['github_oauth_state']

    # Get authorization code
    code = request.GET.get('code')
    if not code:
        error = request.GET.get('error', 'Unknown error')
        messages.error(request, f'GitHub authorization failed: {error}')
        return redirect('integrations_dashboard')

    # Exchange code for token
    github_service = GitHubIntegrationService()
    redirect_uri = request.build_absolute_uri(reverse('github_callback'))
    token_data = github_service.exchange_code_for_token(code, redirect_uri)

    if not token_data:
        messages.error(request, 'Failed to exchange authorization code for access token.')
        return redirect('integrations_dashboard')

    # Get user info
    access_token = token_data.get('access_token')
    user_data = github_service.get_user_info(access_token)

    if not user_data:
        messages.error(request, 'Failed to retrieve GitHub user information.')
        return redirect('integrations_dashboard')

    # Save connection
    try:
        connection = github_service.save_connection(
            request.user,
            access_token,
            user_data
        )
        messages.success(
            request,
            f'Successfully connected to GitHub as @{user_data["login"]}!'
        )
    except Exception as e:
        messages.error(request, f'Failed to save GitHub connection: {str(e)}')

    return redirect('integrations_dashboard')


@login_required
@require_http_methods(["POST"])
def github_disconnect(request):
    """
    Disconnect GitHub account.
    """
    github_service = GitHubIntegrationService()
    success = github_service.disconnect(request.user)

    if success:
        messages.success(request, 'GitHub account disconnected successfully.')
    else:
        messages.warning(request, 'No GitHub connection found.')

    return redirect('integrations_dashboard')


@login_required
@require_http_methods(["POST"])
def github_test(request):
    """
    Test GitHub connection (AJAX endpoint).
    """
    github_service = GitHubIntegrationService()
    is_valid, message = github_service.test_connection(request.user)

    return JsonResponse({
        'valid': is_valid,
        'message': message
    })


@login_required
def huggingface_connect(request):
    """
    Connect Hugging Face account with API token.
    """
    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        token_type = request.POST.get('token_type', 'read')

        if not token:
            messages.error(request, 'Please provide a Hugging Face API token.')
            return render(request, 'integrations/hf_connect.html')

        # Validate and save connection
        hf_service = HuggingFaceIntegrationService()
        connection = hf_service.save_connection(
            request.user,
            token,
            token_type
        )

        if connection:
            messages.success(
                request,
                f'Successfully connected to Hugging Face as @{connection.username}!'
            )
            return redirect('integrations_dashboard')
        else:
            messages.error(
                request,
                'Invalid Hugging Face token. Please check your token and try again.'
            )

    return render(request, 'integrations/hf_connect.html')


@login_required
@require_http_methods(["POST"])
def huggingface_disconnect(request):
    """
    Disconnect Hugging Face account.
    """
    hf_service = HuggingFaceIntegrationService()
    success = hf_service.disconnect(request.user)

    if success:
        messages.success(request, 'Hugging Face account disconnected successfully.')
    else:
        messages.warning(request, 'No Hugging Face connection found.')

    return redirect('integrations_dashboard')


@login_required
@require_http_methods(["POST"])
def huggingface_test(request):
    """
    Test Hugging Face connection (AJAX endpoint).
    """
    hf_service = HuggingFaceIntegrationService()
    is_valid, message = hf_service.test_connection(request.user)

    return JsonResponse({
        'valid': is_valid,
        'message': message
    })


@login_required
def huggingface_models(request):
    """
    Browse Hugging Face models (AJAX endpoint).
    """
    query = request.GET.get('q', '')
    limit = int(request.GET.get('limit', 20))

    hf_service = HuggingFaceIntegrationService()

    # If user has HF connection, list their models
    if query:
        # For now, return a basic response
        # In production, you'd query the HF API
        return JsonResponse({
            'models': [],
            'query': query
        })

    models = hf_service.list_user_models(request.user, limit=limit)

    if models:
        return JsonResponse({'models': models})
    else:
        return JsonResponse({'models': [], 'error': 'No connection or failed to fetch'})


@login_required
def google_connect(request):
    """
    Entry page for Google integration. Provides OAuth connect button.
    """
    from config.dynamic_settings import dynamic_settings
    if not dynamic_settings.GOOGLE_OAUTH_CLIENT_ID or not dynamic_settings.GOOGLE_OAUTH_CLIENT_SECRET:
        messages.error(request, 'Google OAuth is not configured.')
    return render(request, 'integrations/google_connect.html')


@login_required
def google_connect_oauth(request):
    """
    Initiate Google OAuth flow for integration.
    """
    from config.dynamic_settings import dynamic_settings
    if not dynamic_settings.GOOGLE_OAUTH_CLIENT_ID or not dynamic_settings.GOOGLE_OAUTH_CLIENT_SECRET:
        messages.error(request, 'Google OAuth is not configured.')
        return redirect('google_connect')

    state = secrets.token_urlsafe(32)
    request.session['google_oauth_state'] = state

    redirect_uri = request.build_absolute_uri(reverse('google_callback'))

    google_service = GoogleIntegrationService()
    auth_url = google_service.get_authorization_url(redirect_uri, state)
    return redirect(auth_url)


@login_required
def google_callback(request):
    """
    Handle Google OAuth callback for integration.
    """
    state = request.GET.get('state')
    session_state = request.session.get('google_oauth_state')
    if not state or state != session_state:
        messages.error(request, 'Invalid OAuth state. Please try again.')
        return redirect('integrations_dashboard')

    if 'google_oauth_state' in request.session:
        del request.session['google_oauth_state']

    code = request.GET.get('code')
    if not code:
        error = request.GET.get('error', 'Unknown error')
        messages.error(request, f'Google authorization failed: {error}')
        return redirect('integrations_dashboard')

    google_service = GoogleIntegrationService()
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    token_data = google_service.exchange_code_for_token(code, redirect_uri)

    if not token_data:
        messages.error(request, 'Failed to exchange authorization code for tokens.')
        return redirect('integrations_dashboard')

    access_token = token_data.get('access_token')
    user_info = google_service.get_user_info(access_token) if access_token else None
    if not user_info:
        messages.error(request, 'Failed to retrieve Google user information.')
        return redirect('integrations_dashboard')

    connection = google_service.save_connection(request.user, token_data, user_info)
    if connection:
        messages.success(request, f'Successfully connected to Google as {connection.email}!')
    else:
        messages.error(request, 'Failed to save Google connection.')

    return redirect('integrations_dashboard')


@login_required
@require_http_methods(["POST"])
def google_disconnect(request):
    """
    Disconnect Google integration.
    """
    google_service = GoogleIntegrationService()
    success = google_service.disconnect(request.user)
    if success:
        messages.success(request, 'Google account disconnected successfully.')
    else:
        messages.warning(request, 'No Google connection found.')
    return redirect('integrations_dashboard')


@login_required
@require_http_methods(["POST"])
def google_test(request):
    """
    Test Google integration connection.
    """
    google_service = GoogleIntegrationService()
    is_valid, message = google_service.test_connection(request.user)
    return JsonResponse({
        'valid': is_valid,
        'message': message
    })