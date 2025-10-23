"""
Notification views for WebOps.

"API Design" section
Handles notification channel configuration and management.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.notifications.models import NotificationChannel
from apps.core.notifications.services import NotificationService
from apps.core.notifications.forms import NotificationChannelForm


@login_required
def notification_list(request):
    """List and manage notification channels."""
    notification_service = NotificationService()
    channels = notification_service.list_user_channels(request.user)

    context = {
        'channels': channels,
        'page_title': 'Notifications',
    }

    return render(request, 'notifications/notification_list.html', context)


@login_required
def notification_create(request):
    """Create a new notification channel."""
    if request.method == 'POST':
        form = NotificationChannelForm(request.POST)
        if form.is_valid():
            notification_service = NotificationService()

            # Extract event filters from form
            event_filters = {
                'notify_on_deploy_success': form.cleaned_data.get('notify_on_deploy_success', True),
                'notify_on_deploy_failure': form.cleaned_data.get('notify_on_deploy_failure', True),
                'notify_on_deploy_start': form.cleaned_data.get('notify_on_deploy_start', False),
                'notify_on_health_check_fail': form.cleaned_data.get('notify_on_health_check_fail', True),
                'notify_on_resource_warning': form.cleaned_data.get('notify_on_resource_warning', False),
            }

            # Build config based on channel type
            channel_type = form.cleaned_data['channel_type']
            config = {}
            if channel_type == 'email':
                config['email'] = form.cleaned_data.get('email_address')
            elif channel_type == 'webhook':
                config['webhook_url'] = form.cleaned_data.get('webhook_url')

            channel = notification_service.create_channel(
                user=request.user,
                name=form.cleaned_data['name'],
                channel_type=channel_type,
                config=config,
                **event_filters
            )

            messages.success(request, f'Notification channel "{channel.name}" created successfully!')
            return redirect('notification_detail', channel_id=channel.id)
    else:
        form = NotificationChannelForm()

    context = {
        'form': form,
        'page_title': 'Create Notification Channel',
    }

    return render(request, 'notifications/notification_create.html', context)


@login_required
def notification_detail(request, channel_id):
    """View notification channel details."""
    try:
        channel = NotificationChannel.objects.get(id=channel_id, user=request.user)
    except NotificationChannel.DoesNotExist:
        messages.error(request, 'Notification channel not found.')
        return redirect('notification_list')

    # Get recent notification logs
    recent_logs = channel.logs.all()[:20]

    context = {
        'channel': channel,
        'recent_logs': recent_logs,
        'page_title': f'Channel: {channel.name}',
    }

    return render(request, 'notifications/notification_detail.html', context)


@login_required
@require_http_methods(["POST"])
def notification_toggle(request, channel_id):
    """Toggle notification channel active status."""
    try:
        channel = NotificationChannel.objects.get(id=channel_id, user=request.user)
    except NotificationChannel.DoesNotExist:
        messages.error(request, 'Notification channel not found.')
        return redirect('notification_list')

    notification_service = NotificationService()
    is_active = notification_service.toggle_channel(channel)

    status = 'activated' if is_active else 'paused'
    messages.success(request, f'Notification channel "{channel.name}" {status}.')

    return redirect('notification_detail', channel_id=channel.id)


@login_required
@require_http_methods(["POST"])
def notification_test(request, channel_id):
    """Send a test notification."""
    try:
        channel = NotificationChannel.objects.get(id=channel_id, user=request.user)
    except NotificationChannel.DoesNotExist:
        messages.error(request, 'Notification channel not found.')
        return redirect('notification_list')

    notification_service = NotificationService()
    success, message = notification_service.test_channel(channel)

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect('notification_detail', channel_id=channel.id)


@login_required
@require_http_methods(["POST"])
def notification_delete(request, channel_id):
    """Delete a notification channel."""
    try:
        channel = NotificationChannel.objects.get(id=channel_id, user=request.user)
    except NotificationChannel.DoesNotExist:
        messages.error(request, 'Notification channel not found.')
        return redirect('notification_list')

    channel_name = channel.name
    notification_service = NotificationService()
    notification_service.delete_channel(channel)

    messages.success(request, f'Notification channel "{channel_name}" deleted successfully.')
    return redirect('notification_list')