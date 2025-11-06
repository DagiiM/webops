"""
Communication Protocol Module

Handles communication protocols, message formatting, and transmission for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import hashlib
import hmac


class MessageType(Enum):
    """Types of messages that can be communicated."""
    
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    IMAGE = "image"
    FILE = "file"
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ALERT = "alert"
    STATUS = "status"
    HEARTBEAT = "heartbeat"
    HANDSHAKE = "handshake"
    ERROR = "error"


class Priority(Enum):
    """Message priority levels."""
    
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class DeliveryStatus(Enum):
    """Message delivery status."""
    
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"


class ProtocolType(Enum):
    """Supported communication protocols."""
    
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UDP = "udp"
    MQTT = "mqtt"
    AMQP = "amqp"
    GRPC = "grpc"
    CUSTOM = "custom"


@dataclass
class Message:
    """A communication message."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.TEXT
    protocol: ProtocolType = ProtocolType.HTTPS
    priority: Priority = Priority.NORMAL
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    content: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    delivery_attempts: List[Dict[str, Any]] = field(default_factory=list)
    signature: Optional[str] = None
    encrypted: bool = False
    compression: str = ""  # gzip, deflate, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        data = asdict(self)
        data['message_type'] = self.message_type.value
        data['protocol'] = self.protocol.value
        data['priority'] = self.priority.value
        data['delivery_status'] = self.delivery_status.value
        data['timestamp'] = self.timestamp.isoformat()
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        if 'message_type' in data and isinstance(data['message_type'], str):
            data['message_type'] = MessageType(data['message_type'])
        if 'protocol' in data and isinstance(data['protocol'], str):
            data['protocol'] = ProtocolType(data['protocol'])
        if 'priority' in data and isinstance(data['priority'], int):
            data['priority'] = Priority(data['priority'])
        if 'delivery_status' in data and isinstance(data['delivery_status'], str):
            data['delivery_status'] = DeliveryStatus(data['delivery_status'])
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'expires_at' in data and isinstance(data['expires_at'], str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries and not self.is_expired()
    
    def calculate_size(self) -> int:
        """Calculate message size in bytes."""
        size = len(self.content.encode('utf-8'))
        for attachment in self.attachments:
            size += attachment.get('size', 0)
        size += len(json.dumps(self.metadata).encode('utf-8'))
        return size


@dataclass
class Channel:
    """A communication channel."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    protocol: ProtocolType = ProtocolType.HTTPS
    endpoint: str = ""
    port: int = 0
    secure: bool = True
    authentication: Dict[str, Any] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    latency_ms: float = 0.0
    bandwidth_bps: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert channel to dictionary."""
        data = asdict(self)
        data['protocol'] = self.protocol.value
        data['created_at'] = self.created_at.isoformat()
        data['last_used'] = self.last_used.isoformat() if self.last_used else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Channel':
        """Create channel from dictionary."""
        if 'protocol' in data and isinstance(data['protocol'], str):
            data['protocol'] = ProtocolType(data['protocol'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'last_used' in data and isinstance(data['last_used'], str):
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        return cls(**data)
    
    def is_healthy(self) -> bool:
        """Check if channel is healthy."""
        if not self.active:
            return False
        
        # Check error rate
        if self.message_count > 0:
            error_rate = self.error_count / self.message_count
            if error_rate > 0.1:  # More than 10% errors
                return False
        
        # Check latency
        if self.latency_ms > 5000:  # More than 5 seconds
            return False
        
        return True


@dataclass
class ProtocolConfig:
    """Configuration for a communication protocol."""
    
    protocol: ProtocolType
    default_port: int
    secure_by_default: bool
    supports_streaming: bool
    supports_compression: bool
    supports_encryption: bool
    max_message_size: int
    timeout_seconds: int
    keep_alive: bool
    authentication_methods: List[str]
    custom_headers: Dict[str, str] = field(default_factory=dict)
    custom_options: Dict[str, Any] = field(default_factory=dict)


class CommunicationProtocol:
    """Handles communication protocols and message transmission."""
    
    def __init__(self, config):
        """Initialize communication protocol."""
        self.config = config
        self.logger = logging.getLogger("communication_protocol")
        
        # Storage
        self._channels: Dict[str, Channel] = {}
        self._messages: Dict[str, Message] = {}
        self._pending_messages: Dict[str, Message] = {}
        
        # Protocol configurations
        self._protocol_configs = self._initialize_protocol_configs()
        
        # Message handlers
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        self._protocol_handlers: Dict[ProtocolType, Callable] = {}
        
        # Statistics
        self._total_messages_sent = 0
        self._total_messages_received = 0
        self._total_bytes_transferred = 0
        self._average_latency = 0.0
        self._last_activity = datetime.now()
        
        # Background tasks
        self._retry_task = None
        self._cleanup_task = None
    
    async def initialize(self) -> None:
        """Initialize the communication protocol."""
        try:
            # Start background tasks
            self._retry_task = asyncio.create_task(self._retry_failed_messages())
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_messages())
            
            # Register default protocol handlers
            await self._register_default_handlers()
            
            self.logger.info("Communication protocol initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing communication protocol: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the communication protocol."""
        try:
            # Cancel background tasks
            if self._retry_task:
                self._retry_task.cancel()
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            # Close all channels
            for channel in self._channels.values():
                await self._close_channel(channel)
            
            self.logger.info("Communication protocol shutdown")
            
        except Exception as e:
            self.logger.error(f"Error shutting down communication protocol: {e}")
    
    async def create_channel(self, channel: Channel) -> str:
        """Create a new communication channel."""
        try:
            # Validate channel configuration
            await self._validate_channel(channel)
            
            # Store channel
            self._channels[channel.id] = channel
            
            # Initialize channel based on protocol
            await self._initialize_channel(channel)
            
            self.logger.info(f"Created channel: {channel.name} ({channel.protocol.value})")
            return channel.id
            
        except Exception as e:
            self.logger.error(f"Error creating channel: {e}")
            raise
    
    async def send_message(self, message: Message) -> Dict[str, Any]:
        """Send a message through the appropriate channel."""
        try:
            # Validate message
            await self._validate_message(message)
            
            # Get channel for recipient
            channel = await self._get_channel_for_recipient(message.recipient)
            if not channel:
                return {
                    'success': False,
                    'error': f'No channel found for recipient: {message.recipient}'
                }
            
            # Process message
            processed_message = await self._process_message(message, channel)
            
            # Send message
            result = await self._send_via_channel(processed_message, channel)
            
            if result['success']:
                # Update message status
                processed_message.delivery_status = DeliveryStatus.SENT
                processed_message.delivery_attempts.append({
                    'timestamp': datetime.now(),
                    'channel_id': channel.id,
                    'success': True,
                    'latency_ms': result.get('latency_ms', 0)
                })
                
                # Update statistics
                self._total_messages_sent += 1
                self._total_bytes_transferred += processed_message.calculate_size()
                channel.message_count += 1
                channel.last_used = datetime.now()
                channel.latency_ms = result.get('latency_ms', 0)
                
                # Store message
                self._messages[processed_message.id] = processed_message
                
                self.logger.debug(f"Message sent: {processed_message.id}")
            else:
                # Handle failure
                processed_message.delivery_status = DeliveryStatus.FAILED
                processed_message.delivery_attempts.append({
                    'timestamp': datetime.now(),
                    'channel_id': channel.id,
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                })
                
                # Add to pending for retry
                if processed_message.can_retry():
                    self._pending_messages[processed_message.id] = processed_message
                
                channel.error_count += 1
            
            self._last_activity = datetime.now()
            return result
            
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def receive_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and process an incoming message."""
        try:
            # Parse message
            message = Message.from_dict(message_data)
            
            # Validate message
            await self._validate_message(message)
            
            # Update statistics
            self._total_messages_received += 1
            self._total_bytes_transferred += message.calculate_size()
            
            # Process message
            processed_message = await self._process_incoming_message(message)
            
            # Handle message
            result = await self._handle_message(processed_message)
            
            # Store message
            self._messages[processed_message.id] = processed_message
            
            self._last_activity = datetime.now()
            return result
            
        except Exception as e:
            self.logger.error(f"Error receiving message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def register_handler(
        self,
        message_type: MessageType,
        handler: Callable
    ) -> None:
        """Register a message handler."""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        
        self._message_handlers[message_type].append(handler)
        self.logger.debug(f"Registered handler for {message_type.value}")
    
    async def register_protocol_handler(
        self,
        protocol: ProtocolType,
        handler: Callable
    ) -> None:
        """Register a protocol handler."""
        self._protocol_handlers[protocol] = handler
        self.logger.debug(f"Registered handler for {protocol.value}")
    
    async def get_channel_status(self, channel_id: str) -> Dict[str, Any]:
        """Get status of a channel."""
        if channel_id not in self._channels:
            return {'error': 'Channel not found'}
        
        channel = self._channels[channel_id]
        
        return {
            'channel_id': channel_id,
            'name': channel.name,
            'protocol': channel.protocol.value,
            'active': channel.active,
            'healthy': channel.is_healthy(),
            'message_count': channel.message_count,
            'error_count': channel.error_count,
            'error_rate': channel.error_count / channel.message_count if channel.message_count > 0 else 0,
            'latency_ms': channel.latency_ms,
            'bandwidth_bps': channel.bandwidth_bps,
            'last_used': channel.last_used.isoformat() if channel.last_used else None
        }
    
    async def get_protocol_stats(self) -> Dict[str, Any]:
        """Get communication protocol statistics."""
        try:
            stats = {
                'total_channels': len(self._channels),
                'active_channels': sum(1 for ch in self._channels.values() if ch.active),
                'healthy_channels': sum(1 for ch in self._channels.values() if ch.is_healthy()),
                'total_messages_sent': self._total_messages_sent,
                'total_messages_received': self._total_messages_received,
                'total_bytes_transferred': self._total_bytes_transferred,
                'pending_messages': len(self._pending_messages),
                'average_latency': self._average_latency,
                'last_activity': self._last_activity.isoformat(),
                'channels_by_protocol': {
                    protocol.value: sum(1 for ch in self._channels.values() if ch.protocol == protocol)
                    for protocol in ProtocolType
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting protocol stats: {e}")
            return {}
    
    async def _initialize_protocol_configs(self) -> Dict[ProtocolType, ProtocolConfig]:
        """Initialize protocol configurations."""
        configs = {
            ProtocolType.HTTP: ProtocolConfig(
                protocol=ProtocolType.HTTP,
                default_port=80,
                secure_by_default=False,
                supports_streaming=True,
                supports_compression=True,
                supports_encryption=False,
                max_message_size=10 * 1024 * 1024,  # 10MB
                timeout_seconds=30,
                keep_alive=True,
                authentication_methods=['basic', 'token', 'oauth2']
            ),
            ProtocolType.HTTPS: ProtocolConfig(
                protocol=ProtocolType.HTTPS,
                default_port=443,
                secure_by_default=True,
                supports_streaming=True,
                supports_compression=True,
                supports_encryption=True,
                max_message_size=10 * 1024 * 1024,  # 10MB
                timeout_seconds=30,
                keep_alive=True,
                authentication_methods=['basic', 'token', 'oauth2', 'certificate']
            ),
            ProtocolType.WEBSOCKET: ProtocolConfig(
                protocol=ProtocolType.WEBSOCKET,
                default_port=8080,
                secure_by_default=False,
                supports_streaming=True,
                supports_compression=True,
                supports_encryption=False,
                max_message_size=1 * 1024 * 1024,  # 1MB
                timeout_seconds=300,
                keep_alive=True,
                authentication_methods=['token', 'cookie']
            ),
            ProtocolType.TCP: ProtocolConfig(
                protocol=ProtocolType.TCP,
                default_port=0,  # Dynamic
                secure_by_default=False,
                supports_streaming=True,
                supports_compression=False,
                supports_encryption=False,
                max_message_size=64 * 1024,  # 64KB
                timeout_seconds=60,
                keep_alive=True,
                authentication_methods=['custom']
            ),
            ProtocolType.UDP: ProtocolConfig(
                protocol=ProtocolType.UDP,
                default_port=0,  # Dynamic
                secure_by_default=False,
                supports_streaming=False,
                supports_compression=False,
                supports_encryption=False,
                max_message_size=64 * 1024,  # 64KB
                timeout_seconds=5,
                keep_alive=False,
                authentication_methods=['custom']
            ),
            ProtocolType.MQTT: ProtocolConfig(
                protocol=ProtocolType.MQTT,
                default_port=1883,
                secure_by_default=False,
                supports_streaming=False,
                supports_compression=False,
                supports_encryption=False,
                max_message_size=256 * 1024,  # 256KB
                timeout_seconds=60,
                keep_alive=True,
                authentication_methods=['username_password', 'certificate']
            ),
            ProtocolType.AMQP: ProtocolConfig(
                protocol=ProtocolType.AMQP,
                default_port=5672,
                secure_by_default=False,
                supports_streaming=False,
                supports_compression=True,
                supports_encryption=False,
                max_message_size=2 * 1024 * 1024,  # 2MB
                timeout_seconds=30,
                keep_alive=True,
                authentication_methods=['plain', 'external']
            ),
            ProtocolType.GRPC: ProtocolConfig(
                protocol=ProtocolType.GRPC,
                default_port=50051,
                secure_by_default=True,
                supports_streaming=True,
                supports_compression=True,
                supports_encryption=True,
                max_message_size=4 * 1024 * 1024,  # 4MB
                timeout_seconds=30,
                keep_alive=True,
                authentication_methods=['token', 'certificate']
            ),
            ProtocolType.CUSTOM: ProtocolConfig(
                protocol=ProtocolType.CUSTOM,
                default_port=0,  # Dynamic
                secure_by_default=False,
                supports_streaming=False,
                supports_compression=False,
                supports_encryption=False,
                max_message_size=1 * 1024 * 1024,  # 1MB
                timeout_seconds=30,
                keep_alive=False,
                authentication_methods=['custom']
            )
        }
        
        return configs
    
    async def _validate_channel(self, channel: Channel) -> None:
        """Validate channel configuration."""
        if not channel.name:
            raise ValueError("Channel name is required")
        
        if not channel.endpoint:
            raise ValueError("Channel endpoint is required")
        
        # Check protocol configuration
        if channel.protocol not in self._protocol_configs:
            raise ValueError(f"Unsupported protocol: {channel.protocol.value}")
        
        # Validate port
        protocol_config = self._protocol_configs[channel.protocol]
        if channel.port == 0:
            channel.port = protocol_config.default_port
        elif channel.port < 0 or channel.port > 65535:
            raise ValueError(f"Invalid port: {channel.port}")
        
        # Set secure default
        if protocol_config.secure_by_default:
            channel.secure = True
    
    async def _validate_message(self, message: Message) -> None:
        """Validate message."""
        if not message.sender:
            raise ValueError("Message sender is required")
        
        if not message.recipient:
            raise ValueError("Message recipient is required")
        
        if not message.content and not message.attachments:
            raise ValueError("Message must have content or attachments")
        
        # Check message size
        message_size = message.calculate_size()
        protocol_config = self._protocol_configs.get(message.protocol)
        if protocol_config and message_size > protocol_config.max_message_size:
            raise ValueError(f"Message size ({message_size}) exceeds maximum ({protocol_config.max_message_size})")
        
        # Check expiration
        if message.is_expired():
            raise ValueError("Message has expired")
    
    async def _initialize_channel(self, channel: Channel) -> None:
        """Initialize a channel based on its protocol."""
        protocol_config = self._protocol_configs[channel.protocol]
        
        # Apply protocol-specific initialization
        if channel.protocol in self._protocol_handlers:
            handler = self._protocol_handlers[channel.protocol]
            await handler(channel, 'initialize')
        
        # Set default configuration
        if not channel.configuration:
            channel.configuration = {}
        
        # Apply protocol defaults
        channel.configuration.update({
            'timeout': protocol_config.timeout_seconds,
            'keep_alive': protocol_config.keep_alive,
            'supports_compression': protocol_config.supports_compression,
            'supports_encryption': protocol_config.supports_encryption
        })
    
    async def _close_channel(self, channel: Channel) -> None:
        """Close a channel."""
        if channel.protocol in self._protocol_handlers:
            handler = self._protocol_handlers[channel.protocol]
            await handler(channel, 'close')
    
    async def _get_channel_for_recipient(self, recipient: str) -> Optional[Channel]:
        """Get the best channel for a recipient."""
        # Find active channels for recipient
        candidate_channels = [
            channel for channel in self._channels.values()
            if channel.active and channel.is_healthy()
        ]
        
        if not candidate_channels:
            return None
        
        # Sort by priority (latency, error rate, etc.)
        candidate_channels.sort(key=lambda ch: (
            ch.latency_ms,
            ch.error_count / max(1, ch.message_count)
        ))
        
        return candidate_channels[0]
    
    async def _process_message(self, message: Message, channel: Channel) -> Message:
        """Process message before sending."""
        processed_message = Message(
            id=message.id,
            message_type=message.message_type,
            protocol=channel.protocol,
            priority=message.priority,
            sender=message.sender,
            recipient=message.recipient,
            subject=message.subject,
            content=message.content,
            attachments=message.attachments.copy(),
            metadata=message.metadata.copy(),
            timestamp=message.timestamp,
            expires_at=message.expires_at,
            retry_count=message.retry_count,
            max_retries=message.max_retries,
            delivery_status=message.delivery_status,
            delivery_attempts=message.delivery_attempts.copy()
        )
        
        # Apply compression if supported
        protocol_config = self._protocol_configs[channel.protocol]
        if protocol_config.supports_compression and channel.configuration.get('compression', False):
            processed_message.compression = "gzip"
            # In a real implementation, compress the content here
        
        # Apply encryption if supported and required
        if protocol_config.supports_encryption and (channel.secure or message.encrypted):
            processed_message.encrypted = True
            # In a real implementation, encrypt the content here
        
        # Add signature if required
        if channel.authentication.get('sign_messages', False):
            processed_message.signature = self._sign_message(processed_message)
        
        return processed_message
    
    async def _process_incoming_message(self, message: Message) -> Message:
        """Process incoming message."""
        # Verify signature if present
        if message.signature:
            if not self._verify_signature(message):
                raise ValueError("Invalid message signature")
        
        # Decrypt if encrypted
        if message.encrypted:
            # In a real implementation, decrypt the content here
            pass
        
        # Decompress if compressed
        if message.compression:
            # In a real implementation, decompress the content here
            pass
        
        return message
    
    async def _send_via_channel(self, message: Message, channel: Channel) -> Dict[str, Any]:
        """Send message through a specific channel."""
        start_time = datetime.now()
        
        try:
            # Use protocol handler if available
            if channel.protocol in self._protocol_handlers:
                handler = self._protocol_handlers[channel.protocol]
                result = await handler(channel, 'send', message)
                
                # Calculate latency
                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                result['latency_ms'] = latency_ms
                
                return result
            else:
                # Default HTTP/HTTPS handler
                return await self._default_http_handler(channel, 'send', message)
        
        except Exception as e:
            end_time = datetime.now()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'error': str(e),
                'latency_ms': latency_ms
            }
    
    async def _handle_message(self, message: Message) -> Dict[str, Any]:
        """Handle received message."""
        try:
            # Get handlers for message type
            handlers = self._message_handlers.get(message.message_type, [])
            
            if not handlers:
                return {
                    'success': True,
                    'message': 'Message received but no handlers registered'
                }
            
            # Call all handlers
            results = []
            for handler in handlers:
                try:
                    result = await handler(message)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")
                    results.append({'error': str(e)})
            
            return {
                'success': True,
                'handled_by': len(handlers),
                'results': results
            }
        
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _retry_failed_messages(self) -> None:
        """Retry failed messages."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                messages_to_retry = []
                for message_id, message in list(self._pending_messages.items()):
                    if message.can_retry():
                        messages_to_retry.append(message)
                
                for message in messages_to_retry:
                    message.retry_count += 1
                    
                    # Try to send again
                    result = await self.send_message(message)
                    
                    if result['success']:
                        # Remove from pending
                        if message.id in self._pending_messages:
                            del self._pending_messages[message.id]
                    else:
                        # Check if max retries reached
                        if not message.can_retry():
                            message.delivery_status = DeliveryStatus.FAILED
                            if message.id in self._pending_messages:
                                del self._pending_messages[message.id]
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in retry task: {e}")
    
    async def _cleanup_expired_messages(self) -> None:
        """Clean up expired messages."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour
                
                expired_messages = []
                for message_id, message in list(self._pending_messages.items()):
                    if message.is_expired():
                        expired_messages.append(message)
                
                for message in expired_messages:
                    message.delivery_status = DeliveryStatus.EXPIRED
                    if message.id in self._pending_messages:
                        del self._pending_messages[message.id]
                
                # Clean up old messages from storage
                cutoff_date = datetime.now() - timedelta(days=7)
                old_message_ids = [
                    msg_id for msg_id, msg in self._messages.items()
                    if msg.timestamp < cutoff_date
                ]
                
                for msg_id in old_message_ids:
                    del self._messages[msg_id]
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
    
    async def _register_default_handlers(self) -> None:
        """Register default protocol handlers."""
        # Register HTTP/HTTPS handler
        await self.register_protocol_handler(ProtocolType.HTTP, self._default_http_handler)
        await self.register_protocol_handler(ProtocolType.HTTPS, self._default_http_handler)
        
        # Register WebSocket handler
        await self.register_protocol_handler(ProtocolType.WEBSOCKET, self._websocket_handler)
    
    async def _default_http_handler(
        self,
        channel: Channel,
        action: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """Default HTTP/HTTPS handler."""
        if action == 'initialize':
            return {'success': True}
        elif action == 'close':
            return {'success': True}
        elif action == 'send':
            # In a real implementation, send HTTP request here
            return {
                'success': True,
                'message': 'HTTP message sent (simulated)'
            }
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}'
            }
    
    async def _websocket_handler(
        self,
        channel: Channel,
        action: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """WebSocket handler."""
        if action == 'initialize':
            return {'success': True}
        elif action == 'close':
            return {'success': True}
        elif action == 'send':
            # In a real implementation, send WebSocket message here
            return {
                'success': True,
                'message': 'WebSocket message sent (simulated)'
            }
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}'
            }
    
    def _sign_message(self, message: Message) -> str:
        """Sign a message."""
        # In a real implementation, use proper cryptographic signing
        message_data = json.dumps(message.to_dict(), sort_keys=True)
        signature = hmac.new(
            b'secret_key',  # In real implementation, use proper secret
            message_data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _verify_signature(self, message: Message) -> bool:
        """Verify a message signature."""
        # In a real implementation, use proper cryptographic verification
        return True  # Simplified for example