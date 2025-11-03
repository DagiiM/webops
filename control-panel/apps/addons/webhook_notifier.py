"""
Webhook notification system for addon events.

Sends HTTP webhook notifications when addon operations complete,
with retry logic, signature verification, and event filtering.
"""

import json
import hmac
import hashlib
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .logging_config import get_logger
from .models import SystemAddon, AddonExecution

logger = get_logger(__name__)


# ============================================================================
# Webhook Event Types
# ============================================================================

class WebhookEvents:
    """Webhook event types."""
    ADDON_INSTALL_STARTED = 'addon.install.started'
    ADDON_INSTALL_COMPLETED = 'addon.install.completed'
    ADDON_INSTALL_FAILED = 'addon.install.failed'

    ADDON_UNINSTALL_STARTED = 'addon.uninstall.started'
    ADDON_UNINSTALL_COMPLETED = 'addon.uninstall.completed'
    ADDON_UNINSTALL_FAILED = 'addon.uninstall.failed'

    ADDON_CONFIGURE_STARTED = 'addon.configure.started'
    ADDON_CONFIGURE_COMPLETED = 'addon.configure.completed'
    ADDON_CONFIGURE_FAILED = 'addon.configure.failed'

    ADDON_HEALTH_CHANGED = 'addon.health.changed'
    ADDON_STATUS_CHANGED = 'addon.status.changed'


# ============================================================================
# Webhook Payload Builder
# ============================================================================

class WebhookPayloadBuilder:
    """Builds webhook payloads for addon events."""

    @staticmethod
    def build_operation_payload(
        event_type: str,
        addon: SystemAddon,
        execution: Optional[AddonExecution] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build payload for addon operation events.

        Args:
            event_type: Event type
            addon: SystemAddon instance
            execution: AddonExecution instance (optional)
            extra_data: Additional data to include

        Returns:
            Webhook payload dictionary
        """
        payload = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'addon': {
                'id': addon.id,
                'name': addon.name,
                'display_name': addon.display_name,
                'version': addon.version,
                'status': addon.status,
                'health': addon.health,
                'category': addon.category,
            }
        }

        if execution:
            payload['execution'] = {
                'id': str(execution.id),
                'operation': execution.operation,
                'status': execution.status,
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                'duration_ms': execution.duration_ms,
                'requested_by': execution.requested_by.username if execution.requested_by else None,
            }

            # Add error if failed
            if execution.status == 'failed' and execution.output_data:
                error = execution.output_data.get('error')
                if error:
                    payload['execution']['error'] = error

        if extra_data:
            payload.update(extra_data)

        return payload

    @staticmethod
    def build_health_change_payload(
        addon: SystemAddon,
        old_health: str,
        new_health: str
    ) -> Dict[str, Any]:
        """
        Build payload for health change events.

        Args:
            addon: SystemAddon instance
            old_health: Previous health status
            new_health: New health status

        Returns:
            Webhook payload dictionary
        """
        return {
            'event': WebhookEvents.ADDON_HEALTH_CHANGED,
            'timestamp': timezone.now().isoformat(),
            'addon': {
                'id': addon.id,
                'name': addon.name,
                'display_name': addon.display_name,
                'version': addon.version,
                'status': addon.status,
            },
            'health_change': {
                'old_health': old_health,
                'new_health': new_health,
            }
        }

    @staticmethod
    def build_status_change_payload(
        addon: SystemAddon,
        old_status: str,
        new_status: str
    ) -> Dict[str, Any]:
        """
        Build payload for status change events.

        Args:
            addon: SystemAddon instance
            old_status: Previous status
            new_status: New status

        Returns:
            Webhook payload dictionary
        """
        return {
            'event': WebhookEvents.ADDON_STATUS_CHANGED,
            'timestamp': timezone.now().isoformat(),
            'addon': {
                'id': addon.id,
                'name': addon.name,
                'display_name': addon.display_name,
                'version': addon.version,
                'health': addon.health,
            },
            'status_change': {
                'old_status': old_status,
                'new_status': new_status,
            }
        }


# ============================================================================
# Webhook Signature
# ============================================================================

class WebhookSignature:
    """Handles webhook signature generation and verification."""

    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON payload string
            secret: Webhook secret

        Returns:
            Hex signature
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return f'sha256={signature}'

    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: JSON payload string
            signature: Signature to verify
            secret: Webhook secret

        Returns:
            True if signature is valid
        """
        expected_signature = WebhookSignature.generate_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)


# ============================================================================
# Webhook Delivery
# ============================================================================

class WebhookDelivery:
    """Handles webhook delivery with retries."""

    DEFAULT_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 5, 15]  # seconds

    def __init__(
        self,
        url: str,
        secret: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize webhook delivery.

        Args:
            url: Webhook URL
            secret: Webhook secret for signatures
            timeout: Request timeout in seconds
        """
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def send(
        self,
        payload: Dict[str, Any],
        retry: bool = True
    ) -> Dict[str, Any]:
        """
        Send webhook with optional retry.

        Args:
            payload: Webhook payload
            retry: Whether to retry on failure

        Returns:
            Delivery result dictionary
        """
        # Serialize payload
        payload_json = json.dumps(payload, indent=2)

        # Generate signature
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'WebOps-Addon-Webhook/1.0',
            'X-Webhook-Event': payload.get('event', 'unknown'),
            'X-Webhook-Timestamp': payload.get('timestamp', ''),
        }

        if self.secret:
            signature = WebhookSignature.generate_signature(payload_json, self.secret)
            headers['X-Webhook-Signature'] = signature

        # Attempt delivery with retries
        attempt = 0
        last_error = None

        while attempt < (self.MAX_RETRIES if retry else 1):
            try:
                logger.debug(
                    'Sending webhook',
                    url=self.url,
                    event=payload.get('event'),
                    attempt=attempt + 1
                )

                response = requests.post(
                    self.url,
                    data=payload_json,
                    headers=headers,
                    timeout=self.timeout
                )

                # Check response
                if response.status_code in [200, 201, 202, 204]:
                    logger.info(
                        'Webhook delivered successfully',
                        url=self.url,
                        event=payload.get('event'),
                        status_code=response.status_code,
                        attempt=attempt + 1
                    )

                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'attempts': attempt + 1,
                        'response_time_ms': response.elapsed.total_seconds() * 1000
                    }
                else:
                    last_error = f'HTTP {response.status_code}: {response.text[:200]}'
                    logger.warning(
                        'Webhook delivery failed',
                        url=self.url,
                        event=payload.get('event'),
                        status_code=response.status_code,
                        attempt=attempt + 1
                    )

            except requests.exceptions.Timeout:
                last_error = 'Request timeout'
                logger.warning(
                    'Webhook delivery timeout',
                    url=self.url,
                    event=payload.get('event'),
                    attempt=attempt + 1
                )

            except requests.exceptions.ConnectionError as e:
                last_error = f'Connection error: {str(e)}'
                logger.warning(
                    'Webhook delivery connection error',
                    url=self.url,
                    event=payload.get('event'),
                    attempt=attempt + 1,
                    exc_info=e
                )

            except Exception as e:
                last_error = f'Unexpected error: {str(e)}'
                logger.error(
                    'Webhook delivery unexpected error',
                    url=self.url,
                    event=payload.get('event'),
                    attempt=attempt + 1,
                    exc_info=e
                )

            # Retry delay
            attempt += 1
            if retry and attempt < self.MAX_RETRIES:
                delay = self.RETRY_DELAYS[attempt - 1]
                logger.debug(
                    'Retrying webhook delivery',
                    url=self.url,
                    delay_seconds=delay
                )
                time.sleep(delay)

        # All retries exhausted
        logger.error(
            'Webhook delivery failed after retries',
            url=self.url,
            event=payload.get('event'),
            attempts=attempt,
            last_error=last_error
        )

        return {
            'success': False,
            'error': last_error,
            'attempts': attempt
        }


# ============================================================================
# Webhook Notifier
# ============================================================================

class WebhookNotifier:
    """
    Main webhook notifier for addon events.

    Manages webhook URLs, event filtering, and delivery.
    """

    CACHE_PREFIX = 'webhook_config'
    CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        """Initialize webhook notifier."""
        self.payload_builder = WebhookPayloadBuilder()

    def notify_operation_started(
        self,
        operation: str,
        addon: SystemAddon,
        execution: AddonExecution
    ):
        """
        Notify that an operation has started.

        Args:
            operation: Operation type (install, uninstall, configure)
            addon: SystemAddon instance
            execution: AddonExecution instance
        """
        event_map = {
            'install': WebhookEvents.ADDON_INSTALL_STARTED,
            'uninstall': WebhookEvents.ADDON_UNINSTALL_STARTED,
            'configure': WebhookEvents.ADDON_CONFIGURE_STARTED,
        }

        event_type = event_map.get(operation)
        if not event_type:
            logger.warning(
                'Unknown operation type for webhook',
                operation=operation
            )
            return

        payload = self.payload_builder.build_operation_payload(
            event_type, addon, execution
        )

        self._send_webhooks(event_type, payload)

    def notify_operation_completed(
        self,
        operation: str,
        addon: SystemAddon,
        execution: AddonExecution,
        success: bool
    ):
        """
        Notify that an operation has completed.

        Args:
            operation: Operation type
            addon: SystemAddon instance
            execution: AddonExecution instance
            success: Whether operation succeeded
        """
        event_map_success = {
            'install': WebhookEvents.ADDON_INSTALL_COMPLETED,
            'uninstall': WebhookEvents.ADDON_UNINSTALL_COMPLETED,
            'configure': WebhookEvents.ADDON_CONFIGURE_COMPLETED,
        }

        event_map_failed = {
            'install': WebhookEvents.ADDON_INSTALL_FAILED,
            'uninstall': WebhookEvents.ADDON_UNINSTALL_FAILED,
            'configure': WebhookEvents.ADDON_CONFIGURE_FAILED,
        }

        event_type = (
            event_map_success.get(operation) if success
            else event_map_failed.get(operation)
        )

        if not event_type:
            logger.warning(
                'Unknown operation type for webhook',
                operation=operation
            )
            return

        payload = self.payload_builder.build_operation_payload(
            event_type, addon, execution
        )

        self._send_webhooks(event_type, payload)

    def notify_health_changed(
        self,
        addon: SystemAddon,
        old_health: str,
        new_health: str
    ):
        """
        Notify that addon health has changed.

        Args:
            addon: SystemAddon instance
            old_health: Previous health status
            new_health: New health status
        """
        payload = self.payload_builder.build_health_change_payload(
            addon, old_health, new_health
        )

        self._send_webhooks(WebhookEvents.ADDON_HEALTH_CHANGED, payload)

    def notify_status_changed(
        self,
        addon: SystemAddon,
        old_status: str,
        new_status: str
    ):
        """
        Notify that addon status has changed.

        Args:
            addon: SystemAddon instance
            old_status: Previous status
            new_status: New status
        """
        payload = self.payload_builder.build_status_change_payload(
            addon, old_status, new_status
        )

        self._send_webhooks(WebhookEvents.ADDON_STATUS_CHANGED, payload)

    def _send_webhooks(self, event_type: str, payload: Dict[str, Any]):
        """
        Send webhooks to configured URLs.

        Args:
            event_type: Event type
            payload: Webhook payload
        """
        webhook_configs = self._get_webhook_configs()

        if not webhook_configs:
            logger.debug(
                'No webhooks configured',
                event_type=event_type
            )
            return

        for config in webhook_configs:
            # Check if this webhook is interested in this event
            if not self._should_send_event(config, event_type):
                continue

            # Send webhook
            delivery = WebhookDelivery(
                url=config['url'],
                secret=config.get('secret'),
                timeout=config.get('timeout', 30)
            )

            result = delivery.send(payload, retry=config.get('retry', True))

            # Log result
            if result['success']:
                logger.info(
                    'Webhook notification sent',
                    event_type=event_type,
                    url=config['url'],
                    attempts=result.get('attempts', 1)
                )
            else:
                logger.error(
                    'Webhook notification failed',
                    event_type=event_type,
                    url=config['url'],
                    error=result.get('error')
                )

    def _should_send_event(self, config: Dict[str, Any], event_type: str) -> bool:
        """
        Check if webhook should receive this event.

        Args:
            config: Webhook configuration
            event_type: Event type

        Returns:
            True if webhook should receive event
        """
        # If no event filter, send all events
        if 'events' not in config or not config['events']:
            return True

        # Check if event type matches any pattern
        for pattern in config['events']:
            if event_type == pattern:
                return True
            # Support wildcard patterns (e.g., "addon.install.*")
            if pattern.endswith('.*'):
                prefix = pattern[:-2]
                if event_type.startswith(prefix):
                    return True

        return False

    def _get_webhook_configs(self) -> List[Dict[str, Any]]:
        """
        Get webhook configurations.

        Returns:
            List of webhook configurations
        """
        # Try cache first
        cache_key = f'{self.CACHE_PREFIX}:all'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Get from settings or database
        # For now, use Django settings
        webhooks = getattr(settings, 'ADDON_WEBHOOKS', [])

        # Cache for future requests
        cache.set(cache_key, webhooks, self.CACHE_TTL)

        return webhooks


# ============================================================================
# Global Notifier Instance
# ============================================================================

webhook_notifier = WebhookNotifier()
