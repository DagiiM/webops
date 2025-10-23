"""
Webhook views for WebOps.

"API Design" section
Handles webhook configuration and management.
"""

import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from apps.core.webhooks.models import Webhook
from apps.core.webhooks.services import WebhookService
from apps.core.webhooks.forms import WebhookForm

logger = logging.getLogger(__name__)


@login_required
def webhook_list(request):
    """List and manage webhooks for automated deployments."""
    webhook_service = WebhookService()
    webhooks = webhook_service.list_user_webhooks(request.user)

    context = {
        'webhooks': webhooks,
        'page_title': 'Webhooks',
    }

    return render(request, 'webhooks/webhook_list.html', context)


@login_required
def webhook_create(request):
    """Create a new webhook."""
    if request.method == 'POST':
        form = WebhookForm(request.POST, user=request.user)
        if form.is_valid():
            webhook_service = WebhookService()
            webhook = webhook_service.create_webhook(
                user=request.user,
                deployment=form.cleaned_data['deployment'],
                name=form.cleaned_data['name'],
                trigger_event=form.cleaned_data['trigger_event'],
                branch_filter=form.cleaned_data.get('branch_filter', ''),
            )
            messages.success(request, f'Webhook "{webhook.name}" created successfully!')
            return redirect('webhook_detail', webhook_id=webhook.id)
    else:
        form = WebhookForm(user=request.user)

    context = {
        'form': form,
        'page_title': 'Create Webhook',
    }

    return render(request, 'webhooks/webhook_create.html', context)


@login_required
def webhook_detail(request, webhook_id):
    """View webhook details and recent deliveries."""
    try:
        webhook = Webhook.objects.get(id=webhook_id, user=request.user)
    except Webhook.DoesNotExist:
        messages.error(request, 'Webhook not found.')
        return redirect('webhook_list')

    webhook_service = WebhookService()
    webhook_url = webhook_service.get_webhook_url(webhook)
    recent_deliveries = webhook_service.get_recent_deliveries(webhook, limit=20)

    context = {
        'webhook': webhook,
        'webhook_url': webhook_url,
        'recent_deliveries': recent_deliveries,
        'page_title': f'Webhook: {webhook.name}',
    }

    return render(request, 'webhooks/webhook_detail.html', context)


@login_required
@require_http_methods(["POST"])
def webhook_toggle(request, webhook_id):
    """Toggle webhook active status."""
    try:
        webhook = Webhook.objects.get(id=webhook_id, user=request.user)
    except Webhook.DoesNotExist:
        messages.error(request, 'Webhook not found.')
        return redirect('webhook_list')

    webhook_service = WebhookService()
    is_active = webhook_service.toggle_webhook(webhook)

    status = 'activated' if is_active else 'paused'
    messages.success(request, f'Webhook "{webhook.name}" {status}.')

    return redirect('webhook_detail', webhook_id=webhook.id)


@login_required
@require_http_methods(["POST"])
def webhook_delete(request, webhook_id):
    """Delete a webhook."""
    try:
        webhook = Webhook.objects.get(id=webhook_id, user=request.user)
    except Webhook.DoesNotExist:
        messages.error(request, 'Webhook not found.')
        return redirect('webhook_list')

    webhook_name = webhook.name
    webhook_service = WebhookService()
    webhook_service.delete_webhook(webhook)

    messages.success(request, f'Webhook "{webhook_name}" deleted successfully.')
    return redirect('webhook_list')


@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request, secret: str):
    """
    Handle incoming webhook from GitHub.

    This endpoint is called by GitHub when events occur.
    URL format: /webhooks/<secret>/

    Args:
        request: HTTP request from GitHub
        secret: Webhook secret for validation

    Returns:
        JSON response with status
    """
    try:
        # Get webhook by secret
        try:
            webhook = Webhook.objects.get(secret=secret)
        except Webhook.DoesNotExist:
            logger.warning(f"Webhook not found for secret: {secret[:8]}...")
            return JsonResponse({"error": "Webhook not found"}, status=404)

        # Get GitHub signature header
        signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")

        # Get event type
        event_type = request.META.get("HTTP_X_GITHUB_EVENT", "unknown")

        # Parse JSON payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Process webhook based on event type
        webhook_service = WebhookService()

        if event_type == "push":
            success, message = webhook_service.process_github_webhook(
                webhook, payload, signature
            )

            if success:
                return JsonResponse(
                    {"status": "success", "message": message}, status=200
                )
            else:
                return JsonResponse(
                    {"status": "error", "message": message}, status=400
                )

        elif event_type == "ping":
            # GitHub sends ping event when webhook is first set up
            logger.info(f"Ping event received for webhook {webhook.id}")
            return JsonResponse(
                {"status": "success", "message": "Pong! Webhook is configured correctly."},
                status=200,
            )

        else:
            logger.info(f"Unsupported event type: {event_type}")
            return JsonResponse(
                {"status": "ignored", "message": f"Event type '{event_type}' not supported"},
                status=200,
            )

    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def webhook_test(request, secret: str):
    """
    Test endpoint to verify webhook configuration.

    This is useful for testing webhook URLs without GitHub.
    """
    try:
        webhook = Webhook.objects.get(secret=secret)
        return JsonResponse(
            {
                "status": "success",
                "webhook": webhook.name,
                "deployment": webhook.deployment.name,
                "is_active": webhook.is_active,
                "message": "Webhook is configured correctly. Send POST requests with GitHub signature to trigger deployments.",
            }
        )
    except Webhook.DoesNotExist:
        return JsonResponse({"error": "Webhook not found"}, status=404)