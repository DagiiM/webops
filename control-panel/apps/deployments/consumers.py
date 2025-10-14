"""
WebSocket consumers for real-time deployment updates.
"""

import json
from typing import Any, Dict
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Deployment


class DeploymentConsumer(AsyncWebsocketConsumer):
    """Consumer for general deployment updates."""
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        self.room_group_name = 'deployments'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection."""
        # Leave room group
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
        """Send deployment update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'deployment_update',
            'deployment': event['deployment']
        }))
    
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
        self.room_group_name: str = ""
    
    async def connect(self) -> None:
        """Handle WebSocket connection."""
        self.deployment_id = self.scope['url_route']['kwargs']['deployment_id']
        self.room_group_name = f'deployment_{self.deployment_id}'
        
        # Check if deployment exists
        deployment_exists = await self.check_deployment_exists(self.deployment_id)
        if not deployment_exists:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
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
    
    @database_sync_to_async
    def check_deployment_exists(self, deployment_id: str) -> bool:
        """Check if deployment exists in database."""
        try:
            Deployment.objects.get(id=deployment_id)
            return True
        except Deployment.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_deployment_data(self, deployment_id: str) -> Dict[str, Any] | None:
        """Get deployment data from database."""
        try:
            deployment = Deployment.objects.get(id=deployment_id)
            return {
                'id': str(deployment.id),
                'name': deployment.name,
                'status': deployment.status,
                'url': deployment.url,
                'port': deployment.port,
                'created_at': deployment.created_at.isoformat(),
                'updated_at': deployment.updated_at.isoformat(),
            }
        except Deployment.DoesNotExist:
            return None