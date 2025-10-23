"""
VNC Proxy for Web Console

WebSocket proxy that bridges browser (noVNC client) to QEMU VNC server.
Provides authentication and access control for VM console access.
"""

import asyncio
import logging
import struct
from typing import Optional
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

User = get_user_model()


class VNCProxyConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that proxies VNC traffic between browser and QEMU.

    URL pattern: /ws/vnc/<deployment_id>/
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vnc_reader = None
        self.vnc_writer = None
        self.proxy_task = None
        self.vm_deployment = None

    async def connect(self):
        """Handle WebSocket connection."""
        # Get deployment ID from URL
        deployment_id = self.scope['url_route']['kwargs']['deployment_id']

        # Authenticate user
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            logger.warning(f"Unauthenticated VNC access attempt for deployment {deployment_id}")
            await self.close(code=4001)
            return

        # Get VM deployment
        try:
            self.vm_deployment = await self._get_vm_deployment(deployment_id)
        except Exception as e:
            logger.error(f"Failed to get VM deployment {deployment_id}: {e}")
            await self.close(code=4004)
            return

        # Check authorization
        if not await self._check_authorization(user, self.vm_deployment):
            logger.warning(f"Unauthorized VNC access attempt by {user.username} for {deployment_id}")
            await self.close(code=4003)
            return

        # Accept WebSocket connection
        await self.accept()

        # Connect to QEMU VNC server
        try:
            await self._connect_to_vnc()
        except Exception as e:
            logger.error(f"Failed to connect to VNC server: {e}")
            await self.send_text(f"Error: {str(e)}")
            await self.close()
            return

        # Log access
        await self._log_console_access(user, self.vm_deployment, 'connect')

        # Start bidirectional proxy
        self.proxy_task = asyncio.create_task(self._proxy_vnc_to_websocket())

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Cancel proxy task
        if self.proxy_task:
            self.proxy_task.cancel()

        # Close VNC connection
        if self.vnc_writer:
            self.vnc_writer.close()
            await self.vnc_writer.wait_closed()

        # Log disconnection
        if self.vm_deployment:
            user = self.scope.get('user')
            await self._log_console_access(user, self.vm_deployment, 'disconnect')

        logger.info(f"VNC proxy disconnected: {close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Receive data from WebSocket (browser) and forward to VNC server.
        """
        if bytes_data and self.vnc_writer:
            try:
                self.vnc_writer.write(bytes_data)
                await self.vnc_writer.drain()
            except Exception as e:
                logger.error(f"Error forwarding to VNC server: {e}")
                await self.close()

    async def _connect_to_vnc(self):
        """Connect to QEMU VNC server via Unix socket or TCP."""
        # Get VNC connection details
        vnc_host = self.vm_deployment.compute_node.hostname
        vnc_port = self.vm_deployment.vnc_port

        if not vnc_port:
            raise Exception("VM does not have VNC port configured")

        # For local VMs, connect directly to localhost
        # For remote VMs, would need SSH tunnel or different setup
        if vnc_host in ['localhost', '127.0.0.1']:
            connect_host = '127.0.0.1'
        else:
            # TODO: Implement SSH tunnel for remote VMs
            connect_host = vnc_host

        logger.info(f"Connecting to VNC at {connect_host}:{vnc_port}")

        try:
            self.vnc_reader, self.vnc_writer = await asyncio.open_connection(
                connect_host, vnc_port
            )
            logger.info(f"Connected to VNC server")
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
            raise

    async def _proxy_vnc_to_websocket(self):
        """
        Read from VNC server and forward to WebSocket (browser).
        Runs continuously until connection closes.
        """
        try:
            while True:
                data = await self.vnc_reader.read(4096)
                if not data:
                    break

                await self.send(bytes_data=data)
        except asyncio.CancelledError:
            logger.debug("VNC proxy task cancelled")
        except Exception as e:
            logger.error(f"Error in VNC proxy: {e}")
        finally:
            await self.close()

    @sync_to_async
    def _get_vm_deployment(self, deployment_id):
        """Get VM deployment from database."""
        from .models import VMDeployment

        return VMDeployment.objects.select_related(
            'deployment',
            'compute_node'
        ).get(deployment_id=deployment_id)

    @sync_to_async
    def _check_authorization(self, user, vm_deployment):
        """Check if user is authorized to access this VM console."""
        # Owner can always access
        if vm_deployment.deployment.user == user:
            return True

        # Staff can access
        if user.is_staff or user.is_superuser:
            return True

        # TODO: Add shared access / team permissions

        return False

    @sync_to_async
    def _log_console_access(self, user, vm_deployment, action):
        """Log console access for security audit."""
        from apps.core.security.models import SecurityAuditLog

        SecurityAuditLog.objects.create(
            user=user,
            action=f'vm_console_{action}',
            details={
                'vm_name': vm_deployment.vm_name,
                'deployment_id': vm_deployment.deployment.id,
                'action': action,
            },
            ip_address=self.scope.get('client', ['unknown', 0])[0],
        )


class VNCTokenAuth:
    """
    Token-based authentication for VNC console access.
    Generates short-lived tokens for secure console access.
    """

    @staticmethod
    def generate_token(vm_deployment, user, expiry_minutes=15):
        """
        Generate a short-lived token for VNC access.

        Args:
            vm_deployment: VMDeployment instance
            user: User requesting access
            expiry_minutes: Token validity in minutes

        Returns:
            Token string
        """
        from django.core.signing import TimestampSigner
        from django.utils import timezone

        signer = TimestampSigner()
        data = f"{vm_deployment.id}:{user.id}"
        token = signer.sign(data)

        return token

    @staticmethod
    def validate_token(token, vm_deployment, user, max_age=900):
        """
        Validate VNC access token.

        Args:
            token: Token to validate
            vm_deployment: VMDeployment instance
            user: User making the request
            max_age: Maximum age in seconds (default 15 minutes)

        Returns:
            True if valid, False otherwise
        """
        from django.core.signing import TimestampSigner, SignatureExpired, BadSignature

        signer = TimestampSigner()

        try:
            data = signer.unsign(token, max_age=max_age)
            expected_data = f"{vm_deployment.id}:{user.id}"
            return data == expected_data
        except (SignatureExpired, BadSignature):
            return False
