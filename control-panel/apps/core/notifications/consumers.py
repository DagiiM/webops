"""
WebSocket consumers for real-time notifications.

Provides WebSocket endpoint for live notification updates.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from typing import Dict, Any


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time user notifications.

    Each user connects to their own notification channel.
    When a notification is created, it's broadcast to the user's channel.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        # Get the user from the scope
        self.user = self.scope['user']

        # Only allow authenticated users
        if not self.user.is_authenticated:
            await self.close()
            return

        # Create a unique channel group for this user
        self.group_name = f'notifications_user_{self.user.id}'

        # Join the user's notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

        # Send initial unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name'):
            # Leave the notification group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Handle messages from WebSocket client.

        Supports commands like:
        - {"command": "get_notifications", "limit": 50}
        - {"command": "mark_read", "notification_id": 123}
        - {"command": "mark_all_read"}
        """
        try:
            data = json.loads(text_data)
            command = data.get('command')

            if command == 'get_notifications':
                await self.handle_get_notifications(data)
            elif command == 'mark_read':
                await self.handle_mark_read(data)
            elif command == 'mark_all_read':
                await self.handle_mark_all_read()
            elif command == 'get_unread_count':
                await self.handle_get_unread_count()
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown command: {command}'
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))

    async def handle_get_notifications(self, data):
        """Handle get_notifications command."""
        limit = data.get('limit', 50)
        offset = data.get('offset', 0)
        unread_only = data.get('unread_only', False)
        notification_type = data.get('type')

        notifications = await self.get_notifications(
            limit=limit,
            offset=offset,
            unread_only=unread_only,
            notification_type=notification_type
        )

        await self.send(text_data=json.dumps({
            'type': 'notifications_list',
            'notifications': notifications
        }))

    async def handle_mark_read(self, data):
        """Handle mark_read command."""
        notification_id = data.get('notification_id')
        if not notification_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'notification_id required'
            }))
            return

        success = await self.mark_notification_read(notification_id)
        if success:
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'marked_read',
                'notification_id': notification_id,
                'unread_count': unread_count
            }))
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Notification not found'
            }))

    async def handle_mark_all_read(self):
        """Handle mark_all_read command."""
        count = await self.mark_all_notifications_read()
        await self.send(text_data=json.dumps({
            'type': 'all_marked_read',
            'count': count,
            'unread_count': 0
        }))

    async def handle_get_unread_count(self):
        """Handle get_unread_count command."""
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count
        }))

    # Handler for notification events sent from channel layer
    async def notification_new(self, event):
        """
        Handle new notification event from channel layer.

        This is called when a notification is created for this user.
        """
        notification = event['notification']

        # Send notification to WebSocket client
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': notification
        }))

    async def notification_update(self, event):
        """Handle notification update event."""
        notification_id = event['notification_id']
        updates = event['updates']

        await self.send(text_data=json.dumps({
            'type': 'notification_updated',
            'notification_id': notification_id,
            'updates': updates
        }))

    async def notification_deleted(self, event):
        """Handle notification deletion event."""
        notification_id = event['notification_id']

        await self.send(text_data=json.dumps({
            'type': 'notification_deleted',
            'notification_id': notification_id
        }))

    # Database query methods (async wrappers)

    @database_sync_to_async
    def get_unread_count(self) -> int:
        """Get count of unread notifications for the user."""
        from .models import UserNotification
        return UserNotification.objects.filter(
            user=self.user,
            is_read=False,
            is_deleted=False
        ).count()

    @database_sync_to_async
    def get_notifications(
        self,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: str = None
    ) -> list:
        """Get notifications for the user."""
        from .models import UserNotification

        queryset = UserNotification.objects.filter(
            user=self.user,
            is_deleted=False
        )

        if unread_only:
            queryset = queryset.filter(is_read=False)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        queryset = queryset.order_by('-created_at')[offset:offset + limit]

        notifications = []
        for notification in queryset:
            notifications.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'read': notification.is_read,
                'timestamp': notification.created_at.isoformat(),
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'is_important': notification.is_important,
                'metadata': notification.metadata,
            })

        return notifications

    @database_sync_to_async
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark a notification as read."""
        from .models import UserNotification

        try:
            notification = UserNotification.objects.get(
                id=notification_id,
                user=self.user,
                is_deleted=False
            )
            notification.mark_as_read()
            return True
        except UserNotification.DoesNotExist:
            return False

    @database_sync_to_async
    def mark_all_notifications_read(self) -> int:
        """Mark all user notifications as read."""
        from .models import UserNotification
        from django.utils import timezone

        return UserNotification.objects.filter(
            user=self.user,
            is_read=False,
            is_deleted=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
