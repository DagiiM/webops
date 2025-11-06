"""
Chat Interface Module

Provides natural language chat interface for interacting with AI agents.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..core.agent import WebOpsAgent


class MessageType(Enum):
    """Types of chat messages."""
    
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    ERROR = "error"


class MessageStatus(Enum):
    """Status of message processing."""
    
    SENDING = "sending"
    SENT = "sent"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class Message:
    """A chat message."""
    
    id: str
    type: MessageType
    content: str
    timestamp: datetime
    status: MessageStatus = MessageStatus.SENT
    metadata: Dict[str, Any] = field(default_factory=dict)
    response_to: Optional[str] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            'id': self.id,
            'type': self.type.value,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'metadata': self.metadata,
            'response_to': self.response_to,
            'processing_time': self.processing_time
        }


@dataclass
class ChatSession:
    """A chat session with an agent."""
    
    id: str
    agent: WebOpsAgent
    messages: List[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: Message) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_recent_messages(self, limit: int = 10) -> List[Message]:
        """Get recent messages from session."""
        return self.messages[-limit:]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            'id': self.id,
            'agent_name': self.agent.name,
            'message_count': len(self.messages),
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'context': self.context,
            'metadata': self.metadata,
            'messages': [msg.to_dict() for msg in self.messages]
        }


class ChatInterface:
    """
    Chat interface for interacting with AI agents.
    
    Provides natural language conversation capabilities
    with session management and message history.
    """
    
    def __init__(self, agent: WebOpsAgent):
        """Initialize chat interface."""
        self.agent = agent
        self.logger = logging.getLogger("chat_interface")
        
        # Session management
        self.sessions: Dict[str, ChatSession] = {}
        self.active_sessions: Dict[str, ChatSession] = {}
        
        # Message handlers
        self.message_handlers: Dict[str, List[Callable]] = {}
        
        # Configuration
        self.max_session_duration_hours = 24
        self.max_messages_per_session = 1000
        self.max_sessions_per_agent = 100
    
    async def create_session(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new chat session.
        
        Args:
            context: Initial context for session
            
        Returns:
            Session ID
        """
        try:
            # Generate session ID
            session_id = f"session_{datetime.now().timestamp()}"
            
            # Check session limit
            if len(self.sessions) >= self.max_sessions_per_agent:
                # Remove oldest session
                oldest_session_id = min(
                    self.sessions.keys(),
                    key=lambda x: self.sessions[x].created_at
                )
                await self.close_session(oldest_session_id)
            
            # Create session
            session = ChatSession(
                id=session_id,
                agent=self.agent,
                context=context or {}
            )
            
            # Store session
            self.sessions[session_id] = session
            self.active_sessions[session_id] = session
            
            self.logger.info(f"Created chat session: {session_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            raise
    
    async def close_session(self, session_id: str) -> bool:
        """
        Close a chat session.
        
        Args:
            session_id: ID of session to close
            
        Returns:
            Success status
        """
        try:
            if session_id not in self.sessions:
                return False
            
            # Remove from active sessions
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # Store session summary
            session = self.sessions[session_id]
            await self._store_session_summary(session)
            
            # Remove session
            del self.sessions[session_id]
            
            self.logger.info(f"Closed chat session: {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")
            return False
    
    async def send_message(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the agent.
        
        Args:
            session_id: Session ID
            content: Message content
            metadata: Additional metadata
            
        Returns:
            Response data
        """
        try:
            # Validate session
            if session_id not in self.sessions:
                return {
                    'success': False,
                    'error': 'Session not found',
                    'session_id': session_id
                }
            
            session = self.sessions[session_id]
            
            # Check message limit
            if len(session.messages) >= self.max_messages_per_session:
                return {
                    'success': False,
                    'error': 'Session message limit reached',
                    'session_id': session_id
                }
            
            # Create user message
            user_message = Message(
                id=f"msg_{datetime.now().timestamp()}",
                type=MessageType.USER,
                content=content,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )
            
            # Add to session
            session.add_message(user_message)
            
            # Process message through agent
            start_time = datetime.now()
            response = await self.agent.chat(content, session.context)
            end_time = datetime.now()
            
            # Create agent message
            agent_message = Message(
                id=f"msg_{datetime.now().timestamp()}",
                type=MessageType.AGENT,
                content=response,
                timestamp=end_time,
                processing_time=(end_time - start_time).total_seconds(),
                response_to=user_message.id
            )
            
            # Add to session
            session.add_message(agent_message)
            
            # Update session context
            await self._update_session_context(session, user_message, agent_message)
            
            # Emit message event
            await self._emit_message_event(session_id, user_message, agent_message)
            
            return {
                'success': True,
                'session_id': session_id,
                'user_message': user_message.to_dict(),
                'agent_message': agent_message.to_dict(),
                'response_time': agent_message.processing_time
            }
            
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return {
                'success': False,
                'error': str(e),
                'session_id': session_id
            }
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data or None
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                return None
            
            # Check session age
            session_age = datetime.now() - session.created_at
            if session_age.total_seconds() > self.max_session_duration_hours * 3600:
                await self.close_session(session_id)
                return None
            
            return session.to_dict()
            
        except Exception as e:
            self.logger.error(f"Error getting session: {e}")
            return None
    
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get session message history.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages
            
        Returns:
            List of messages
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                return []
            
            recent_messages = session.get_recent_messages(limit)
            return [msg.to_dict() for msg in recent_messages]
            
        except Exception as e:
            self.logger.error(f"Error getting session history: {e}")
            return []
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all active sessions.
        
        Returns:
            List of active sessions
        """
        try:
            # Clean up old sessions
            await self._cleanup_old_sessions()
            
            return [
                session.to_dict()
                for session in self.active_sessions.values()
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting active sessions: {e}")
            return []
    
    async def search_sessions(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search sessions by content.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching sessions
        """
        try:
            matching_sessions = []
            
            for session in self.sessions.values():
                # Search in messages
                for message in session.messages:
                    if query.lower() in message.content.lower():
                        matching_sessions.append(session.to_dict())
                        break
            
            # Sort by last activity and limit
            matching_sessions.sort(
                key=lambda x: x['last_activity'],
                reverse=True
            )
            
            return matching_sessions[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching sessions: {e}")
            return []
    
    async def register_message_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Register a message event handler.
        
        Args:
            event_type: Type of event
            handler: Handler function
        """
        if event_type not in self.message_handlers:
            self.message_handlers[event_type] = []
        
        self.message_handlers[event_type].append(handler)
        self.logger.info(f"Registered message handler for: {event_type}")
    
    async def unregister_message_handler(
        self,
        event_type: str,
        handler: Callable
    ) -> None:
        """
        Unregister a message event handler.
        
        Args:
            event_type: Type of event
            handler: Handler function
        """
        if event_type in self.message_handlers:
            try:
                self.message_handlers[event_type].remove(handler)
                self.logger.info(f"Unregistered message handler for: {event_type}")
            except ValueError:
                pass  # Handler not found
    
    async def get_chat_stats(self) -> Dict[str, Any]:
        """Get chat interface statistics."""
        try:
            total_sessions = len(self.sessions)
            active_sessions = len(self.active_sessions)
            total_messages = sum(
                len(session.messages)
                for session in self.sessions.values()
            )
            
            # Calculate average messages per session
            avg_messages = (
                total_messages / total_sessions
                if total_sessions > 0 else 0
            )
            
            # Calculate session duration stats
            session_durations = [
                (datetime.now() - session.created_at).total_seconds()
                for session in self.sessions.values()
            ]
            
            avg_duration = (
                sum(session_durations) / len(session_durations)
                if session_durations else 0
            )
            
            return {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'avg_messages_per_session': avg_messages,
                'avg_session_duration_seconds': avg_duration,
                'max_sessions_per_agent': self.max_sessions_per_agent,
                'max_messages_per_session': self.max_messages_per_session,
                'max_session_duration_hours': self.max_session_duration_hours
            }
            
        except Exception as e:
            self.logger.error(f"Error getting chat stats: {e}")
            return {}
    
    async def _update_session_context(
        self,
        session: ChatSession,
        user_message: Message,
        agent_message: Message
    ) -> None:
        """Update session context based on conversation."""
        try:
            # Extract entities from messages
            entities = await self._extract_entities(user_message.content)
            
            # Update context
            if 'entities' not in session.context:
                session.context['entities'] = {}
            
            session.context['entities'].update(entities)
            
            # Update conversation state
            if 'conversation_state' not in session.context:
                session.context['conversation_state'] = {}
            
            session.context['conversation_state']['last_topic'] = await self._detect_topic(user_message.content)
            session.context['conversation_state']['message_count'] = len(session.messages)
            
        except Exception as e:
            self.logger.error(f"Error updating session context: {e}")
    
    async def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from text."""
        # Simple entity extraction - in practice would use NLP
        entities = {}
        
        # Extract common patterns
        import re
        
        # Numbers
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            entities['numbers'] = [int(n) for n in numbers]
        
        # URLs
        urls = re.findall(r'https?://[^\s]+', text)
        if urls:
            entities['urls'] = urls
        
        # Email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if emails:
            entities['emails'] = emails
        
        return entities
    
    async def _detect_topic(self, text: str) -> str:
        """Detect topic of text."""
        # Simple topic detection - in practice would use NLP
        text_lower = text.lower()
        
        topic_keywords = {
            'deployment': ['deploy', 'deployment', 'release', 'publish'],
            'monitoring': ['monitor', 'check', 'status', 'health'],
            'troubleshooting': ['error', 'issue', 'problem', 'fix', 'debug'],
            'security': ['security', 'auth', 'permission', 'access'],
            'performance': ['performance', 'speed', 'slow', 'optimize'],
            'backup': ['backup', 'restore', 'recover'],
            'configuration': ['config', 'setting', 'parameter', 'option']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return topic
        
        return 'general'
    
    async def _store_session_summary(self, session: ChatSession) -> None:
        """Store session summary for analytics."""
        try:
            summary = {
                'session_id': session.id,
                'agent_name': session.agent.name,
                'message_count': len(session.messages),
                'duration_seconds': (session.last_activity - session.created_at).total_seconds(),
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'context': session.context
            }
            
            # Store to file or database
            # For now, just log
            self.logger.info(f"Session summary: {summary}")
            
        except Exception as e:
            self.logger.error(f"Error storing session summary: {e}")
    
    async def _cleanup_old_sessions(self) -> None:
        """Clean up old inactive sessions."""
        try:
            current_time = datetime.now()
            sessions_to_close = []
            
            for session_id, session in self.sessions.items():
                # Check session age
                session_age = current_time - session.last_activity
                if session_age.total_seconds() > self.max_session_duration_hours * 3600:
                    sessions_to_close.append(session_id)
            
            # Close old sessions
            for session_id in sessions_to_close:
                await self.close_session(session_id)
            
            if sessions_to_close:
                self.logger.info(f"Cleaned up {len(sessions_to_close)} old sessions")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old sessions: {e}")
    
    async def _emit_message_event(
        self,
        session_id: str,
        user_message: Message,
        agent_message: Message
    ) -> None:
        """Emit message event to handlers."""
        try:
            event_data = {
                'session_id': session_id,
                'user_message': user_message.to_dict(),
                'agent_message': agent_message.to_dict(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Call all handlers
            if 'message_received' in self.message_handlers:
                for handler in self.message_handlers['message_received']:
                    try:
                        await handler(event_data)
                    except Exception as e:
                        self.logger.error(f"Error in message handler: {e}")
            
        except Exception as e:
            self.logger.error(f"Error emitting message event: {e}")