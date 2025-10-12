"""
Webhook endpoint views for handling GitHub webhook deliveries.

Reference: CLAUDE.md "API Design" section
Architecture: Webhook validation, payload processing, deployment triggering
"""

import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.models import Webhook
from apps.core.webhook_services import WebhookService

logger = logging.getLogger(__name__)


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
