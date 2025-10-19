"""
Webhook services for automated deployments.

Reference: CLAUDE.md "Security Best Practices" section
Architecture: Webhook validation, secret generation, GitHub integration
"""

import logging
import secrets
import hmac
import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

from apps.core.models import Webhook, WebhookDelivery
from apps.deployments.models import Deployment
from apps.services.background import get_background_processor

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for managing webhooks and automated deployments."""

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a secure random secret for webhook validation.

        Returns:
            64-character hexadecimal secret
        """
        return secrets.token_hex(32)

    def create_webhook(
        self,
        user: User,
        deployment: Deployment,
        name: str,
        trigger_event: str = Webhook.TriggerEvent.PUSH,
        branch_filter: str = "",
    ) -> Webhook:
        """
        Create a new webhook for automated deployment.

        Args:
            user: Webhook owner
            deployment: Associated deployment
            name: Webhook name
            trigger_event: Event that triggers the webhook
            branch_filter: Optional branch filter

        Returns:
            Created webhook instance
        """
        secret = self.generate_secret()

        webhook = Webhook.objects.create(
            user=user,
            deployment=deployment,
            name=name,
            trigger_event=trigger_event,
            branch_filter=branch_filter,
            secret=secret,
            is_active=True,
        )

        logger.info(
            f"Webhook created: {webhook.name} for {deployment.name} by {user.username}"
        )

        return webhook

    def validate_github_signature(
        self, payload_body: bytes, signature_header: str, secret: str
    ) -> bool:
        """
        Validate GitHub webhook signature.

        Args:
            payload_body: Raw request body
            signature_header: X-Hub-Signature-256 header value
            secret: Webhook secret

        Returns:
            True if signature is valid
        """
        if not signature_header:
            return False

        try:
            # GitHub signature format: sha256=<hex>
            hash_algorithm, signature = signature_header.split("=")
            if hash_algorithm != "sha256":
                return False

            # Compute expected signature
            mac = hmac.new(
                secret.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
            )
            expected_signature = mac.hexdigest()

            # Constant-time comparison
            return hmac.compare_digest(expected_signature, signature)

        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return False

    def process_github_webhook(
        self, webhook: Webhook, payload: Dict[str, Any], signature: str
    ) -> Tuple[bool, str]:
        """
        Process GitHub webhook payload.

        Args:
            webhook: Webhook configuration
            payload: GitHub payload
            signature: Request signature

        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate signature
            payload_json = json.dumps(payload, separators=(",", ":"))
            if not self.validate_github_signature(
                payload_json.encode("utf-8"), signature, webhook.secret
            ):
                logger.warning(f"Invalid signature for webhook {webhook.id}")
                return False, "Invalid signature"

            # Check if webhook is active
            if not webhook.is_active:
                return False, "Webhook is paused"

            # Extract event information
            ref = payload.get("ref", "")
            branch = ref.split("/")[-1] if ref.startswith("refs/heads/") else ""

            # Apply branch filter
            if webhook.branch_filter and branch != webhook.branch_filter:
                logger.info(
                    f"Webhook {webhook.id}: Branch {branch} doesn't match filter {webhook.branch_filter}"
                )
                return False, f"Branch {branch} doesn't match filter"

            # Create delivery record
            delivery = WebhookDelivery.objects.create(
                webhook=webhook,
                status=WebhookDelivery.Status.PENDING,
                payload=payload,
                triggered_by=f"GitHub push to {branch}",
            )

            # Trigger deployment
            from apps.deployments.tasks import deploy_django_app

            webhook.last_triggered = timezone.now()
            webhook.trigger_count += 1
            webhook.save()

            # Ensure Celery worker is running (non-interactive)
            from apps.deployments.service_manager import ServiceManager
            ServiceManager().ensure_celery_running()

            # Queue deployment task via background processor
            handle = get_background_processor().submit(
                'apps.deployments.tasks.deploy_application',
                webhook.deployment.id
            )

            # Update delivery record
            delivery.status = WebhookDelivery.Status.SUCCESS
            delivery.response = {"task_id": handle.id, "branch": branch}
            delivery.save()

            logger.info(
                f"Webhook {webhook.id} triggered deployment {webhook.deployment.id}"
            )

            return True, f"Deployment triggered for branch {branch}"

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")

            # Record error in delivery
            if "delivery" in locals():
                delivery.status = WebhookDelivery.Status.FAILED
                delivery.error_message = str(e)
                delivery.save()

            webhook.status = Webhook.Status.FAILED
            webhook.last_error = str(e)
            webhook.save()

            return False, f"Error: {str(e)}"

    def get_webhook_url(self, webhook: Webhook) -> str:
        """
        Generate the webhook URL for GitHub configuration.

        Args:
            webhook: Webhook instance

        Returns:
            Full webhook URL
        """
        # In production, this should use the actual domain
        base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
        return f"{base_url}/webhooks/{webhook.secret}/"

    def list_user_webhooks(self, user: User) -> list:
        """
        List all webhooks for a user.

        Args:
            user: User instance

        Returns:
            List of webhooks with metadata
        """
        webhooks = Webhook.objects.filter(user=user).select_related("deployment")

        return [
            {
                "id": webhook.id,
                "name": webhook.name,
                "deployment": webhook.deployment.name,
                "trigger_event": webhook.trigger_event,
                "branch_filter": webhook.branch_filter,
                "is_active": webhook.is_active,
                "status": webhook.status,
                "trigger_count": webhook.trigger_count,
                "last_triggered": webhook.last_triggered,
                "url": self.get_webhook_url(webhook),
                "created_at": webhook.created_at,
            }
            for webhook in webhooks
        ]

    def toggle_webhook(self, webhook: Webhook) -> bool:
        """
        Toggle webhook active status.

        Args:
            webhook: Webhook instance

        Returns:
            New active status
        """
        webhook.is_active = not webhook.is_active
        if webhook.is_active:
            webhook.status = Webhook.Status.ACTIVE
        else:
            webhook.status = Webhook.Status.PAUSED
        webhook.save()

        logger.info(
            f"Webhook {webhook.id} {'activated' if webhook.is_active else 'paused'}"
        )

        return webhook.is_active

    def delete_webhook(self, webhook: Webhook) -> bool:
        """
        Delete a webhook.

        Args:
            webhook: Webhook instance

        Returns:
            True if deleted successfully
        """
        webhook_id = webhook.id
        webhook.delete()
        logger.info(f"Webhook {webhook_id} deleted")
        return True

    def get_recent_deliveries(self, webhook: Webhook, limit: int = 10) -> list:
        """
        Get recent webhook deliveries.

        Args:
            webhook: Webhook instance
            limit: Maximum number of deliveries to return

        Returns:
            List of delivery records
        """
        deliveries = webhook.deliveries.all()[:limit]

        return [
            {
                "id": delivery.id,
                "status": delivery.status,
                "triggered_by": delivery.triggered_by,
                "created_at": delivery.created_at,
                "error_message": delivery.error_message,
                "payload_summary": {
                    "ref": delivery.payload.get("ref", ""),
                    "commits": len(delivery.payload.get("commits", [])),
                },
            }
            for delivery in deliveries
        ]
