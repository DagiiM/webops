"""
Episodic Memory Module

Stores and retrieves personal experiences and events for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid


class EventType(Enum):
    """Types of events stored in episodic memory."""
    
    INTERACTION = "interaction"
    TASK = "task"
    DECISION = "decision"
    OBSERVATION = "observation"
    ERROR = "error"
    SUCCESS = "success"
    CONVERSATION = "conversation"
    INTERNAL_EVENT = "internal_event"
    EXTERNAL_EVENT = "external_event"


class EmotionType(Enum):
    """Emotional states associated with events."""
    
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CONFUSED = "confused"
    SATISFIED = "satisfied"
    DISAPPOINTED = "disappointed"
    SURPRISED = "surprised"
    ANXIOUS = "anxious"


class ImportanceLevel(Enum):
    """Importance levels for events."""
    
    TRIVIAL = 1
    MINOR = 2
    MODERATE = 3
    SIGNIFICANT = 4
    CRITICAL = 5


@dataclass
class Actor:
    """An actor involved in an event."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    role: str = ""  # user, system, agent, etc.
    relationship: str = ""
    characteristics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert actor to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Actor':
        """Create actor from dictionary."""
        return cls(**data)


@dataclass
class Context:
    """Context information for an event."""
    
    location: str = ""
    environment: str = ""
    time_of_day: str = ""
    weather: str = ""
    social_situation: str = ""
    technical_context: Dict[str, Any] = field(default_factory=dict)
    environmental_factors: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Context':
        """Create context from dictionary."""
        return cls(**data)


@dataclass
class Event:
    """An episodic memory event."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    event_type: EventType = EventType.INTERNAL_EVENT
    title: str = ""
    description: str = ""
    actors: List[Actor] = field(default_factory=list)
    context: Context = field(default_factory=Context)
    emotions: List[EmotionType] = field(default_factory=list)
    importance: ImportanceLevel = ImportanceLevel.MODERATE
    duration_seconds: float = 0.0
    outcomes: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retrieval_count: int = 0
    last_retrieved: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['emotions'] = [emotion.value for emotion in self.emotions]
        data['importance'] = self.importance.value
        data['context'] = self.context.to_dict()
        data['actors'] = [actor.to_dict() for actor in self.actors]
        data['last_retrieved'] = self.last_retrieved.isoformat() if self.last_retrieved else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'event_type' in data and isinstance(data['event_type'], str):
            data['event_type'] = EventType(data['event_type'])
        if 'emotions' in data:
            data['emotions'] = [EmotionType(emotion) for emotion in data['emotions']]
        if 'importance' in data and isinstance(data['importance'], int):
            data['importance'] = ImportanceLevel(data['importance'])
        if 'context' in data:
            data['context'] = Context.from_dict(data['context'])
        if 'actors' in data:
            data['actors'] = [Actor.from_dict(actor) for actor in data['actors']]
        if 'last_retrieved' in data and isinstance(data['last_retrieved'], str):
            data['last_retrieved'] = datetime.fromisoformat(data['last_retrieved'])
        return cls(**data)
    
    def calculate_salience(self) -> float:
        """Calculate event salience score for memory consolidation."""
        salience = 0.0
        
        # Importance contribution
        salience += self.importance.value * 0.2
        
        # Emotional intensity
        if self.emotions:
            emotion_intensity = len(self.emotions) * 0.1
            # Negative emotions have higher salience
            negative_emotions = {
                EmotionType.FRUSTRATED, EmotionType.SAD, EmotionType.DISAPPOINTED,
                EmotionType.ANXIOUS, EmotionType.CONFUSED
            }
            negative_count = sum(1 for emotion in self.emotions if emotion in negative_emotions)
            emotion_intensity += negative_count * 0.05
            salience += min(emotion_intensity, 0.3)
        
        # Duration (longer events are more salient)
        if self.duration_seconds > 0:
            duration_score = min(self.duration_seconds / 3600.0, 0.2)  # Max 0.2 for 1+ hour
            salience += duration_score
        
        # Number of actors
        if self.actors:
            actor_score = min(len(self.actors) * 0.05, 0.15)
            salience += actor_score
        
        # Outcomes and lessons
        outcome_score = min((len(self.outcomes) + len(self.lessons_learned)) * 0.05, 0.15)
        salience += outcome_score
        
        # Retrieval frequency (recency effect)
        if self.last_retrieved:
            days_since_retrieval = (datetime.now() - self.last_retrieved).days
            recency_score = max(0, 0.1 - (days_since_retrieval * 0.01))
            salience += recency_score
        
        return min(1.0, salience)
    
    def is_recent(self, days: int = 7) -> bool:
        """Check if event is recent."""
        return (datetime.now() - self.timestamp).days <= days


class EpisodicMemory:
    """Stores and retrieves personal experiences and events."""
    
    def __init__(self, config):
        """Initialize episodic memory."""
        self.config = config
        self.logger = logging.getLogger("episodic_memory")
        
        # Storage
        self._events: Dict[str, Event] = {}
        self._consolidated_events: Dict[str, Event] = {}
        
        # Indices
        self._type_index: Dict[EventType, List[str]] = {
            event_type: [] for event_type in EventType
        }
        self._emotion_index: Dict[EmotionType, List[str]] = {
            emotion: [] for emotion in EmotionType
        }
        self._importance_index: Dict[ImportanceLevel, List[str]] = {
            importance: [] for importance in ImportanceLevel
        }
        self._actor_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._temporal_index: List[Tuple[datetime, str]] = []
        
        # Memory consolidation
        self._consolidation_threshold = 0.7
        self._max_events = 10000
        self._max_consolidated = 1000
        
        # Statistics
        self._total_events = 0
        self._total_consolidated = 0
        self._last_consolidation = datetime.now()
    
    async def store_event(self, event: Event) -> str:
        """Store a new episodic event."""
        try:
            # Store event
            self._events[event.id] = event
            
            # Update indices
            await self._index_event(event)
            
            # Update statistics
            self._total_events += 1
            
            # Check if consolidation is needed
            await self._check_consolidation()
            
            self.logger.debug(f"Stored event: {event.id}")
            return event.id
            
        except Exception as e:
            self.logger.error(f"Error storing event: {e}")
            raise
    
    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        event = self._events.get(event_id) or self._consolidated_events.get(event_id)
        
        if event:
            # Update retrieval statistics
            event.retrieval_count += 1
            event.last_retrieved = datetime.now()
        
        return event
    
    async def search_events(
        self,
        query: str,
        event_type: Optional[EventType] = None,
        emotion: Optional[EmotionType] = None,
        importance: Optional[ImportanceLevel] = None,
        actor_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for events."""
        try:
            results = []
            query_lower = query.lower()
            
            # Search in both active and consolidated events
            all_events = {**self._events, **self._consolidated_events}
            
            for event in all_events.values():
                # Filter by event type
                if event_type and event.event_type != event_type:
                    continue
                
                # Filter by emotion
                if emotion and emotion not in event.emotions:
                    continue
                
                # Filter by importance
                if importance and event.importance != importance:
                    continue
                
                # Filter by actor
                if actor_name:
                    actor_match = any(
                        actor_name.lower() in actor.name.lower()
                        for actor in event.actors
                    )
                    if not actor_match:
                        continue
                
                # Filter by date range
                if start_date and event.timestamp < start_date:
                    continue
                if end_date and event.timestamp > end_date:
                    continue
                
                # Filter by tags
                if tags:
                    if not any(tag in event.tags for tag in tags):
                        continue
                
                # Calculate relevance
                relevance = 0.0
                
                # Title match
                if query_lower in event.title.lower():
                    relevance += 0.4
                
                # Description match
                if query_lower in event.description.lower():
                    relevance += 0.3
                
                # Actor match
                for actor in event.actors:
                    if query_lower in actor.name.lower():
                        relevance += 0.2
                    if query_lower in actor.role.lower():
                        relevance += 0.1
                
                # Context match
                if query_lower in event.context.location.lower():
                    relevance += 0.1
                if query_lower in event.context.environment.lower():
                    relevance += 0.1
                
                # Outcome/lessons match
                for outcome in event.outcomes:
                    if query_lower in outcome.lower():
                        relevance += 0.2
                for lesson in event.lessons_learned:
                    if query_lower in lesson.lower():
                        relevance += 0.2
                
                # Tag matches
                tag_matches = sum(1 for tag in event.tags if query_lower in tag.lower())
                if tag_matches > 0:
                    relevance += 0.1 * (tag_matches / len(event.tags)) if event.tags else 0.1
                
                if relevance > 0:
                    results.append({
                        'event_id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'event_type': event.event_type.value,
                        'title': event.title,
                        'description': event.description[:200] + "..." if len(event.description) > 200 else event.description,
                        'importance': event.importance.value,
                        'emotions': [emotion.value for emotion in event.emotions],
                        'actors': [actor.name for actor in event.actors],
                        'tags': event.tags,
                        'salience': event.calculate_salience(),
                        'retrieval_count': event.retrieval_count,
                        'relevance': relevance
                    })
            
            # Sort by relevance and salience
            results.sort(key=lambda x: (x['relevance'], x['salience']), reverse=True)
            return results[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching events: {e}")
            return []
    
    async def get_recent_events(
        self,
        days: int = 7,
        event_type: Optional[EventType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent events."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            recent_events = []
            for event in self._events.values():
                if event.timestamp >= cutoff_date:
                    if event_type is None or event.event_type == event_type:
                        recent_events.append({
                            'event_id': event.id,
                            'timestamp': event.timestamp.isoformat(),
                            'event_type': event.event_type.value,
                            'title': event.title,
                            'description': event.description[:100] + "..." if len(event.description) > 100 else event.description,
                            'importance': event.importance.value,
                            'emotions': [emotion.value for emotion in event.emotions],
                            'actors': [actor.name for actor in event.actors],
                            'salience': event.calculate_salience()
                        })
            
            # Sort by timestamp (most recent first)
            recent_events.sort(key=lambda x: x['timestamp'], reverse=True)
            return recent_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting recent events: {e}")
            return []
    
    async def get_events_by_actor(self, actor_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get events involving a specific actor."""
        try:
            actor_name_lower = actor_name.lower()
            actor_events = []
            
            all_events = {**self._events, **self._consolidated_events}
            
            for event in all_events.values():
                actor_match = any(
                    actor_name_lower in actor.name.lower()
                    for actor in event.actors
                )
                if actor_match:
                    actor_events.append({
                        'event_id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'event_type': event.event_type.value,
                        'title': event.title,
                        'description': event.description[:200] + "..." if len(event.description) > 200 else event.description,
                        'importance': event.importance.value,
                        'emotions': [emotion.value for emotion in event.emotions],
                        'actors': [actor.name for actor in event.actors],
                        'salience': event.calculate_salience()
                    })
            
            # Sort by timestamp (most recent first)
            actor_events.sort(key=lambda x: x['timestamp'], reverse=True)
            return actor_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting events by actor: {e}")
            return []
    
    async def get_emotional_timeline(
        self,
        days: int = 30,
        emotion: Optional[EmotionType] = None
    ) -> List[Dict[str, Any]]:
        """Get emotional timeline."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            timeline = []
            
            all_events = {**self._events, **self._consolidated_events}
            
            for event in all_events.values():
                if event.timestamp >= cutoff_date:
                    event_emotions = event.emotions if emotion is None else [
                        e for e in event.emotions if e == emotion
                    ]
                    
                    if event_emotions:
                        timeline.append({
                            'timestamp': event.timestamp.isoformat(),
                            'event_id': event.id,
                            'title': event.title,
                            'emotions': [emotion.value for emotion in event_emotions],
                            'importance': event.importance.value,
                            'salience': event.calculate_salience()
                        })
            
            # Sort by timestamp
            timeline.sort(key=lambda x: x['timestamp'])
            return timeline
            
        except Exception as e:
            self.logger.error(f"Error getting emotional timeline: {e}")
            return []
    
    async def find_similar_events(
        self,
        event_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find events similar to a given event."""
        try:
            target_event = self._events.get(event_id) or self._consolidated_events.get(event_id)
            if not target_event:
                return []
            
            similar_events = []
            all_events = {**self._events, **self._consolidated_events}
            
            for event in all_events.values():
                if event.id == event_id:
                    continue
                
                similarity = await self._calculate_event_similarity(target_event, event)
                
                if similarity > 0.3:  # Similarity threshold
                    similar_events.append({
                        'event_id': event.id,
                        'timestamp': event.timestamp.isoformat(),
                        'event_type': event.event_type.value,
                        'title': event.title,
                        'description': event.description[:200] + "..." if len(event.description) > 200 else event.description,
                        'similarity': similarity,
                        'salience': event.calculate_salience()
                    })
            
            # Sort by similarity
            similar_events.sort(key=lambda x: x['similarity'], reverse=True)
            return similar_events[:limit]
            
        except Exception as e:
            self.logger.error(f"Error finding similar events: {e}")
            return []
    
    async def extract_patterns(
        self,
        days: int = 30,
        min_frequency: int = 3
    ) -> List[Dict[str, Any]]:
        """Extract patterns from recent events."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Collect recent events
            recent_events = [
                event for event in self._events.values()
                if event.timestamp >= cutoff_date
            ]
            
            patterns = []
            
            # Analyze event type patterns
            type_counts = {}
            for event in recent_events:
                event_type = event.event_type.value
                type_counts[event_type] = type_counts.get(event_type, 0) + 1
            
            for event_type, count in type_counts.items():
                if count >= min_frequency:
                    patterns.append({
                        'pattern_type': 'event_type',
                        'pattern': event_type,
                        'frequency': count,
                        'description': f"Event type '{event_type}' occurs {count} times in {days} days"
                    })
            
            # Analyze emotion patterns
            emotion_counts = {}
            for event in recent_events:
                for emotion in event.emotions:
                    emotion_name = emotion.value
                    emotion_counts[emotion_name] = emotion_counts.get(emotion_name, 0) + 1
            
            for emotion, count in emotion_counts.items():
                if count >= min_frequency:
                    patterns.append({
                        'pattern_type': 'emotion',
                        'pattern': emotion,
                        'frequency': count,
                        'description': f"Emotion '{emotion}' occurs {count} times in {days} days"
                    })
            
            # Analyze actor patterns
            actor_counts = {}
            for event in recent_events:
                for actor in event.actors:
                    actor_name = actor.name
                    actor_counts[actor_name] = actor_counts.get(actor_name, 0) + 1
            
            for actor, count in actor_counts.items():
                if count >= min_frequency:
                    patterns.append({
                        'pattern_type': 'actor',
                        'pattern': actor,
                        'frequency': count,
                        'description': f"Actor '{actor}' appears {count} times in {days} days"
                    })
            
            # Analyze tag patterns
            tag_counts = {}
            for event in recent_events:
                for tag in event.tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            for tag, count in tag_counts.items():
                if count >= min_frequency:
                    patterns.append({
                        'pattern_type': 'tag',
                        'pattern': tag,
                        'frequency': count,
                        'description': f"Tag '{tag}' appears {count} times in {days} days"
                    })
            
            # Sort by frequency
            patterns.sort(key=lambda x: x['frequency'], reverse=True)
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error extracting patterns: {e}")
            return []
    
    async def consolidate_memory(self) -> int:
        """Consolidate important events into long-term memory."""
        try:
            consolidated_count = 0
            
            # Find events to consolidate
            events_to_consolidate = []
            for event in self._events.values():
                salience = event.calculate_salience()
                if salience >= self._consolidation_threshold:
                    events_to_consolidate.append((event, salience))
            
            # Sort by salience
            events_to_consolidate.sort(key=lambda x: x[1], reverse=True)
            
            # Consolidate top events
            for event, salience in events_to_consolidate:
                if len(self._consolidated_events) >= self._max_consolidated:
                    break
                
                # Move to consolidated memory
                self._consolidated_events[event.id] = event
                
                # Remove from active memory
                if event.id in self._events:
                    del self._events[event.id]
                    self._total_events -= 1
                
                consolidated_count += 1
                self._total_consolidated += 1
            
            self._last_consolidation = datetime.now()
            self.logger.info(f"Consolidated {consolidated_count} events")
            return consolidated_count
            
        except Exception as e:
            self.logger.error(f"Error consolidating memory: {e}")
            return 0
    
    async def cleanup_old_events(self, cutoff_date: datetime) -> int:
        """Clean up old events based on retention policy."""
        try:
            removed_count = 0
            
            # Find old, low-importance events
            old_event_ids = [
                eid for eid, event in self._events.items()
                if (event.timestamp < cutoff_date and
                    event.importance.value <= ImportanceLevel.MINOR.value and
                    event.calculate_salience() < 0.3)
            ]
            
            # Remove old events
            for event_id in old_event_ids:
                if await self._remove_event(event_id):
                    removed_count += 1
            
            self.logger.info(f"Cleaned up {removed_count} old events")
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old events: {e}")
            return 0
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get episodic memory statistics."""
        try:
            stats = {
                'total_events': len(self._events),
                'total_consolidated': len(self._consolidated_events),
                'events_by_type': {
                    event_type.value: len(ids)
                    for event_type, ids in self._type_index.items()
                },
                'events_by_emotion': {
                    emotion.value: len(ids)
                    for emotion, ids in self._emotion_index.items()
                },
                'events_by_importance': {
                    importance.value: len(ids)
                    for importance, ids in self._importance_index.items()
                },
                'total_actors': len(self._actor_index),
                'total_tags': len(self._tag_index),
                'average_salience': 0.0,
                'last_consolidation': self._last_consolidation.isoformat()
            }
            
            # Calculate average salience
            all_events = {**self._events, **self._consolidated_events}
            if all_events:
                stats['average_salience'] = sum(
                    event.calculate_salience() for event in all_events.values()
                ) / len(all_events)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _index_event(self, event: Event) -> None:
        """Index an event for efficient retrieval."""
        # Type index
        if event.id not in self._type_index[event.event_type]:
            self._type_index[event.event_type].append(event.id)
        
        # Emotion index
        for emotion in event.emotions:
            if event.id not in self._emotion_index[emotion]:
                self._emotion_index[emotion].append(event.id)
        
        # Importance index
        if event.id not in self._importance_index[event.importance]:
            self._importance_index[event.importance].append(event.id)
        
        # Actor index
        for actor in event.actors:
            if actor.name not in self._actor_index:
                self._actor_index[actor.name] = []
            if event.id not in self._actor_index[actor.name]:
                self._actor_index[actor.name].append(event.id)
        
        # Tag index
        for tag in event.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if event.id not in self._tag_index[tag]:
                self._tag_index[tag].append(event.id)
        
        # Temporal index
        self._temporal_index.append((event.timestamp, event.id))
        self._temporal_index.sort(key=lambda x: x[0])
    
    async def _unindex_event(self, event: Event) -> None:
        """Remove an event from indices."""
        # Type index
        if event.id in self._type_index[event.event_type]:
            self._type_index[event.event_type].remove(event.id)
        
        # Emotion index
        for emotion in event.emotions:
            if event.id in self._emotion_index[emotion]:
                self._emotion_index[emotion].remove(event.id)
        
        # Importance index
        if event.id in self._importance_index[event.importance]:
            self._importance_index[event.importance].remove(event.id)
        
        # Actor index
        for actor in event.actors:
            if actor.name in self._actor_index and event.id in self._actor_index[actor.name]:
                self._actor_index[actor.name].remove(event.id)
                if not self._actor_index[actor.name]:
                    del self._actor_index[actor.name]
        
        # Tag index
        for tag in event.tags:
            if tag in self._tag_index and event.id in self._tag_index[tag]:
                self._tag_index[tag].remove(event.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
        
        # Temporal index
        self._temporal_index = [
            (timestamp, eid) for timestamp, eid in self._temporal_index
            if eid != event.id
        ]
    
    async def _check_consolidation(self) -> None:
        """Check if memory consolidation is needed."""
        # Consolidate if we have too many events or if enough time has passed
        if (len(self._events) > self._max_events or
            datetime.now() - self._last_consolidation > timedelta(hours=24)):
            await self.consolidate_memory()
    
    async def _calculate_event_similarity(self, event1: Event, event2: Event) -> float:
        """Calculate similarity between two events."""
        similarity = 0.0
        
        # Event type similarity
        if event1.event_type == event2.event_type:
            similarity += 0.2
        
        # Emotion similarity
        common_emotions = set(event1.emotions) & set(event2.emotions)
        if event1.emotions and event2.emotions:
            emotion_similarity = len(common_emotions) / len(set(event1.emotions) | set(event2.emotions))
            similarity += emotion_similarity * 0.2
        
        # Actor similarity
        actor1_names = {actor.name for actor in event1.actors}
        actor2_names = {actor.name for actor in event2.actors}
        common_actors = actor1_names & actor2_names
        if actor1_names and actor2_names:
            actor_similarity = len(common_actors) / len(actor1_names | actor2_names)
            similarity += actor_similarity * 0.2
        
        # Tag similarity
        common_tags = set(event1.tags) & set(event2.tags)
        if event1.tags and event2.tags:
            tag_similarity = len(common_tags) / len(set(event1.tags) | set(event2.tags))
            similarity += tag_similarity * 0.1
        
        # Text similarity (simple keyword matching)
        words1 = set(event1.title.lower().split() + event1.description.lower().split())
        words2 = set(event2.title.lower().split() + event2.description.lower().split())
        common_words = words1 & words2
        if words1 and words2:
            text_similarity = len(common_words) / len(words1 | words2)
            similarity += text_similarity * 0.3
        
        return similarity
    
    async def _remove_event(self, event_id: str) -> bool:
        """Remove an event from memory."""
        if event_id not in self._events:
            return False
        
        event = self._events[event_id]
        
        # Remove from indices
        await self._unindex_event(event)
        
        # Remove from storage
        del self._events[event_id]
        self._total_events -= 1
        
        return True