"""
WebSocket consumers for real-time deployment updates.
"""

import json
import re
from typing import Any, Dict
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import BaseDeployment


class DeploymentConsumer(AsyncWebsocketConsumer):
    """Consumer for general deployment updates."""
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        import logging
        logger = logging.getLogger('webops.websocket.consumer')
        
        # Require authenticated user (TokenAuthMiddleware sets scope['user'])
        user = self.scope.get('user')
        client_ip = self.scope.get('client', ['unknown', 0])[0]
        
        logger.info(f"DeploymentConsumer connection attempt from {client_ip}, user: {user}")
        
        if not user or not getattr(user, 'is_authenticated', False):
            logger.warning(f"DeploymentConsumer rejected unauthenticated connection from {client_ip}")
            # Use custom close code for authentication failure
            await self.close(code=4001)
            return

        self.room_group_name = 'deployments'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        logger.info(f"DeploymentConsumer accepted connection for user {user.username} from {client_ip}")
        await self.accept()
    
    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection."""
        # Leave room group
        if hasattr(self, 'room_group_name') and self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data: str) -> None:
        """Handle messages from WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'ping')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def deployment_update(self, event: Dict[str, Any]) -> None:
        """Normalize broadcast payloads to client format used by CLI/UI."""
        payload = event.get('message', {})
        deployment = payload.get('deployment', {})
        normalized = {
            'type': 'deployment_update',
            'deployment': deployment,
        }
        # Preserve timestamp if present
        if 'timestamp' in payload:
            normalized['timestamp'] = payload['timestamp']
        await self.send(text_data=json.dumps(normalized))
    
    async def deployment_status(self, event: Dict[str, Any]) -> None:
        """Send deployment status update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'deployment_status',
            'deployment_id': event['deployment_id'],
            'status': event['status'],
            'message': event.get('message', '')
        }))


class DeploymentStatusConsumer(AsyncWebsocketConsumer):
    """Consumer for specific deployment status updates."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.deployment_id: str = ""
        self.deployment_name: str = ""
        self.room_group_name: str = ""
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        import logging
        logger = logging.getLogger('webops.websocket.consumer')
        
        # Require authenticated user
        user = self.scope.get('user')
        client_ip = self.scope.get('client', ['unknown', 0])[0]
        
        logger.info(f"DeploymentStatusConsumer connection attempt from {client_ip}, user: {user}")
        
        if not user or not getattr(user, 'is_authenticated', False):
            logger.warning(f"DeploymentStatusConsumer rejected unauthenticated connection from {client_ip}")
            # Use custom close code for authentication failure
            await self.close(code=4001)
            return

        self.deployment_id = self.scope['url_route']['kwargs']['deployment_id']
        logger.info(f"DeploymentStatusConsumer checking access to deployment {self.deployment_id} for user {user.username}")

        # Check if deployment exists and user has permission
        deployment_exists = await self.check_deployment_exists(self.deployment_id)
        if not deployment_exists:
            logger.warning(f"DeploymentStatusConsumer rejected connection - deployment {self.deployment_id} does not exist")
            await self.close(code=4004)  # Not found
            return

        has_access = await self.user_can_access_deployment(self.deployment_id, user)
        if not has_access:
            logger.warning(f"DeploymentStatusConsumer rejected connection - user {user.username} lacks access to deployment {self.deployment_id}")
            await self.close(code=4003)  # Forbidden
            return

        # Resolve deployment name for group subscription; signals use name-based groups
        self.deployment_name = await self.get_deployment_name(self.deployment_id)

        # Set a default deployment name if none exists
        if not self.deployment_name:
            self.deployment_name = f"deployment_{self.deployment_id}"

        # Create a valid room group name
        base_name = self.deployment_name or f"deployment_{self.deployment_id}"
        self.room_group_name = f"deployment_{base_name}"

        # Ensure room_group_name meets Django Channels requirements
        if len(self.room_group_name) >= 100:
            # Truncate if too long
            self.room_group_name = f"dep_{self.deployment_id}"

        # Validate group name contains only allowed characters
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.room_group_name):
            self.room_group_name = f"deployment_{self.deployment_id}"

        # Ensure it's a non-empty string
        if not self.room_group_name or not isinstance(self.room_group_name, str):
            self.room_group_name = f"deployment_{self.deployment_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"DeploymentStatusConsumer accepted connection for user {user.username} to deployment {self.deployment_id} (group: {self.room_group_name})")
        await self.accept()
        
        # Send current deployment status
        deployment_data = await self.get_deployment_data(self.deployment_id)
        if deployment_data:
            await self.send(text_data=json.dumps({
                'type': 'deployment_status',
                'deployment': deployment_data
            }))
    
    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection."""
        # Leave room group
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data: str) -> None:
        """Handle messages from WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'ping')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
            elif message_type == 'get_status':
                deployment_data = await self.get_deployment_data(self.deployment_id)
                if deployment_data:
                    await self.send(text_data=json.dumps({
                        'type': 'deployment_status',
                        'deployment': deployment_data
                    }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def deployment_status_update(self, event: Dict[str, Any]) -> None:
        """Send deployment status update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'deployment_status_update',
            'deployment_id': event['deployment_id'],
            'status': event['status'],
            'message': event.get('message', ''),
            'timestamp': event.get('timestamp')
        }))
    
    async def deployment_logs(self, event: Dict[str, Any]) -> None:
        """Send deployment logs to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'deployment_logs',
            'deployment_id': event['deployment_id'],
            'logs': event['logs'],
            'timestamp': event.get('timestamp')
        }))

    async def deployment_update(self, event: Dict[str, Any]) -> None:
        """Normalize broadcast payloads to client format used by CLI/UI."""
        payload = event.get('message', {})
        event_type = payload.get('type')
        # Map specific payload types to expected client event names
        if event_type == 'log_entry':
            logs = payload.get('log')
            await self.send(text_data=json.dumps({
                'type': 'deployment_logs',
                'deployment_id': self.deployment_id,
                'logs': [logs] if logs else [],
                'timestamp': payload.get('timestamp'),
            }))
            return

        if event_type in ('deployment_created', 'deployment_updated'):
            dep = payload.get('deployment', {})
            await self.send(text_data=json.dumps({
                'type': 'deployment_status_update',
                'deployment_id': self.deployment_id,
                'status': dep.get('status'),
                'message': '',
                'timestamp': payload.get('timestamp'),
            }))
            return

        # Fallback: forward as generic deployment_update with deployment object
        deployment = payload.get('deployment', {})
        normalized = {
            'type': 'deployment_update',
            'deployment': deployment,
        }
        if 'timestamp' in payload:
            normalized['timestamp'] = payload['timestamp']
        await self.send(text_data=json.dumps(normalized))
    
    @database_sync_to_async
    def check_deployment_exists(self, deployment_id: str) -> bool:
        """Check if deployment exists in database."""
        try:
            BaseDeployment.objects.get(id=deployment_id)
            return True
        except BaseDeployment.DoesNotExist:
            return False

    @database_sync_to_async
    def get_deployment_data(self, deployment_id: str) -> Dict[str, Any] | None:
        """Get deployment data from database."""
        try:
            deployment = BaseDeployment.objects.get(id=deployment_id)
            return {
                'id': str(deployment.id),
                'name': deployment.name,
                'status': deployment.status,
                'domain': deployment.domain,
                'port': deployment.port,
                'created_at': deployment.created_at.isoformat(),
                'updated_at': deployment.updated_at.isoformat(),
            }
        except BaseDeployment.DoesNotExist:
            return None

    @database_sync_to_async
    def user_can_access_deployment(self, deployment_id: str, user: User) -> bool:
        """Check if user can access specific deployment."""
        try:
            deployment = BaseDeployment.objects.get(id=deployment_id)
            if getattr(user, 'is_superuser', False):
                return True
            return deployment.deployed_by_id == user.id
        except BaseDeployment.DoesNotExist:
            return False

    @database_sync_to_async
    def get_deployment_name(self, deployment_id: str) -> str | None:
        """Resolve deployment name by id."""
        try:
            return BaseDeployment.objects.get(id=deployment_id).name
        except BaseDeployment.DoesNotExist:
            return None
