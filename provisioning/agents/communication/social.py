"""
Social Communication Module

Handles social interactions, relationship management, and social context for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid


class SocialRole(Enum):
    """Social roles in interactions."""
    
    FRIEND = "friend"
    COLLEAGUE = "colleague"
    SUPERIOR = "superior"
    SUBORDINATE = "subordinate"
    CUSTOMER = "customer"
    PROVIDER = "provider"
    MENTOR = "mentor"
    MENTEE = "mentee"
    ACQUAINTANCE = "acquaintance"
    STRANGER = "stranger"
    FAMILY = "family"
    TEAM_MEMBER = "team_member"
    LEADER = "leader"
    FOLLOWER = "follower"


class InteractionType(Enum):
    """Types of social interactions."""
    
    CONVERSATION = "conversation"
    COLLABORATION = "collaboration"
    NEGOTIATION = "negotiation"
    CONFERENCE = "conference"
    MEETING = "meeting"
    CHAT = "chat"
    EMAIL = "email"
    CALL = "call"
    PRESENTATION = "presentation"
    FEEDBACK = "feedback"
    SOCIAL_MEDIA = "social_media"


class RelationshipStatus(Enum):
    """Status of social relationships."""
    
    NEW = "new"
    DEVELOPING = "developing"
    ESTABLISHED = "established"
    STRONG = "strong"
    DETERIORATING = "deteriorating"
    TERMINATED = "terminated"


class CommunicationStyle(Enum):
    """Communication styles."""
    
    FORMAL = "formal"
    INFORMAL = "informal"
    DIRECT = "direct"
    INDIRECT = "indirect"
    ASSERTIVE = "assertive"
    PASSIVE = "passive"
    AGGRESSIVE = "aggressive"
    PASSIVE_AGGRESSIVE = "passive_aggressive"
    COLLABORATIVE = "collaborative"
    COMPETITIVE = "competitive"


class EmotionalState(Enum):
    """Emotional states in social interactions."""
    
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    FEARFUL = "fearful"
    DISGUSTED = "disgusted"
    CONFUSED = "confused"
    EXCITED = "excited"
    ANXIOUS = "anxious"
    CONTENT = "content"
    FRUSTRATED = "frustrated"
    HOPEFUL = "hopeful"


@dataclass
class SocialContext:
    """Context for social interactions."""
    
    interaction_type: InteractionType
    participants: List[str] # participant IDs
    setting: str = ""  # formal meeting, casual chat, etc.
    topic: str = ""
    duration_minutes: int = 0
    formality_level: float = 0.5  # 0.0 to 1.0
    emotional_tone: EmotionalState = EmotionalState.NEUTRAL
    cultural_context: str = ""
    power_dynamics: Dict[str, str] = field(default_factory=dict)  # participant_id: role
    shared_history: List[str] = field(default_factory=list)
    current_agenda: List[str] = field(default_factory=list)
    communication_channel: str = "text"  # text, voice, video, etc.
    privacy_level: str = "public"  # public, private, confidential
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        data = asdict(self)
        data['interaction_type'] = self.interaction_type.value
        data['emotional_tone'] = self.emotional_tone.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialContext':
        """Create context from dictionary."""
        if 'interaction_type' in data and isinstance(data['interaction_type'], str):
            data['interaction_type'] = InteractionType(data['interaction_type'])
        if 'emotional_tone' in data and isinstance(data['emotional_tone'], str):
            data['emotional_tone'] = EmotionalState(data['emotional_tone'])
        return cls(**data)


@dataclass
class SocialRelationship:
    """A social relationship between the agent and another entity."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    participant_id: str = ""
    participant_name: str = ""
    role: SocialRole = SocialRole.ACQUAINTANCE
    status: RelationshipStatus = RelationshipStatus.NEW
    communication_style: CommunicationStyle = CommunicationStyle.FORMAL
    trust_level: float = 0.0  # 0.0 to 1.0
    rapport_level: float = 0.0  # 0.0 to 1.0
    interaction_frequency: str = "rarely"  # daily, weekly, monthly, rarely
    last_interaction: Optional[datetime] = None
    next_interaction: Optional[datetime] = None
    shared_interests: List[str] = field(default_factory=list)
    communication_preferences: Dict[str, Any] = field(default_factory=dict)
    cultural_background: str = ""
    personal_facts: Dict[str, str] = field(default_factory=dict)
    interaction_history: List[str] = field(default_factory=list)
    relationship_goals: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary."""
        data = asdict(self)
        data['role'] = self.role.value
        data['status'] = self.status.value
        data['communication_style'] = self.communication_style.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_interaction'] = self.last_interaction.isoformat() if self.last_interaction else None
        data['next_interaction'] = self.next_interaction.isoformat() if self.next_interaction else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialRelationship':
        """Create relationship from dictionary."""
        if 'role' in data and isinstance(data['role'], str):
            data['role'] = SocialRole(data['role'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = RelationshipStatus(data['status'])
        if 'communication_style' in data and isinstance(data['communication_style'], str):
            data['communication_style'] = CommunicationStyle(data['communication_style'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_interaction' in data and isinstance(data['last_interaction'], str):
            data['last_interaction'] = datetime.fromisoformat(data['last_interaction'])
        if 'next_interaction' in data and isinstance(data['next_interaction'], str):
            data['next_interaction'] = datetime.fromisoformat(data['next_interaction'])
        return cls(**data)
    
    def calculate_relationship_strength(self) -> float:
        """Calculate overall relationship strength."""
        factors = [
            self.trust_level * 0.4,  # Trust is most important
            self.rapport_level * 0.3,  # Rapport is important
            self._time_factor() * 0.2,  # Duration of relationship
            self._interaction_factor() * 0.1  # Recent interactions
        ]
        
        return min(1.0, sum(factors))
    
    def _time_factor(self) -> float:
        """Calculate factor based on relationship duration."""
        if not self.created_at:
            return 0.0
        
        days_since_creation = (datetime.now() - self.created_at).days
        # Max 1.0 after 365 days
        return min(1.0, days_since_creation / 365.0)
    
    def _interaction_factor(self) -> float:
        """Calculate factor based on recent interactions."""
        if not self.last_interaction:
            return 0.0
        
        days_since_interaction = (datetime.now() - self.last_interaction).days
        # Recent interactions get higher score
        if days_since_interaction <= 1:
            return 1.0
        elif days_since_interaction <= 7:
            return 0.8
        elif days_since_interaction <= 30:
            return 0.5
        elif days_since_interaction <= 90:
            return 0.2
        else:
            return 0.0


@dataclass
class SocialInteraction:
    """A social interaction record."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: SocialContext = field(default_factory=SocialContext)
    participants: List[str] = field(default_factory=list)  # participant IDs
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    outcomes: List[str] = field(default_factory=list)
    sentiment_analysis: Dict[str, float] = field(default_factory=dict)  # participant_id: sentiment_score
    engagement_levels: Dict[str, float] = field(default_factory=dict)  # participant_id: engagement_score
    communication_quality: float = 0.0  # 0.0 to 1.0
    relationship_impact: Dict[str, float] = field(default_factory=dict)  # participant_id: impact_score
    challenges_faced: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    follow_up_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert interaction to dictionary."""
        data = asdict(self)
        data['context'] = self.context.to_dict()
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SocialInteraction':
        """Create interaction from dictionary."""
        if 'context' in data:
            data['context'] = SocialContext.from_dict(data['context'])
        if 'start_time' in data and isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


class SocialCommunication:
    """Handles social interactions and relationship management."""
    
    def __init__(self, config):
        """Initialize social communication module."""
        self.config = config
        self.logger = logging.getLogger("social_communication")
        
        # Storage
        self._relationships: Dict[str, SocialRelationship] = {}
        self._interactions: Dict[str, SocialInteraction] = {}
        self._context_stack: List[SocialContext] = []
        
        # Social parameters
        self._default_communication_style = CommunicationStyle.COLLABORATIVE
        self._max_relationships = 1000
        self._max_interactions = 10000
        
        # Statistics
        self._total_interactions = 0
        self._total_relationships = 0
        self._average_relationship_strength = 0.0
        self._interaction_types_count = {}
        self._last_relationship_update = datetime.now()
    
    async def initialize(self) -> None:
        """Initialize the social communication module."""
        try:
            # Load saved relationships and interactions
            await self._load_saved_data()
            
            self.logger.info("Social communication module initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing social communication: {e}")
            raise
    
    async def create_relationship(self, relationship: SocialRelationship) -> str:
        """Create a new social relationship."""
        try:
            # Validate relationship
            await self._validate_relationship(relationship)
            
            # Check if relationship already exists
            if relationship.participant_id in self._relationships:
                existing_rel = self._relationships[relationship.participant_id]
                self.logger.warning(f"Relationship with {relationship.participant_id} already exists, updating")
                return await self.update_relationship(relationship)
            
            # Store relationship
            self._relationships[relationship.participant_id] = relationship
            self._total_relationships += 1
            
            # Update statistics
            self._update_relationship_stats(relationship)
            
            self.logger.info(f"Created relationship with {relationship.participant_name}")
            return relationship.participant_id
            
        except Exception as e:
            self.logger.error(f"Error creating relationship: {e}")
            raise
    
    async def get_relationship(self, participant_id: str) -> Optional[SocialRelationship]:
        """Get a social relationship."""
        return self._relationships.get(participant_id)
    
    async def update_relationship(self, relationship: SocialRelationship) -> str:
        """Update an existing social relationship."""
        try:
            # Validate relationship
            await self._validate_relationship(relationship)
            
            # Update timestamp
            relationship.updated_at = datetime.now()
            
            # Store relationship
            self._relationships[relationship.participant_id] = relationship
            
            # Update statistics
            self._update_relationship_stats(relationship)
            
            self.logger.debug(f"Updated relationship with {relationship.participant_name}")
            return relationship.participant_id
            
        except Exception as e:
            self.logger.error(f"Error updating relationship: {e}")
            raise
    
    async def start_interaction(self, context: SocialContext) -> str:
        """Start a new social interaction."""
        try:
            # Create interaction
            interaction = SocialInteraction(context=context, participants=context.participants.copy())
            
            # Store interaction
            self._interactions[interaction.id] = interaction
            self._total_interactions += 1
            
            # Add to context stack
            self._context_stack.append(context)
            
            # Update interaction types count
            interaction_type = context.interaction_type.value
            self._interaction_types_count[interaction_type] = self._interaction_types_count.get(interaction_type, 0) + 1
            
            self.logger.info(f"Started interaction: {context.interaction_type.value}")
            return interaction.id
            
        except Exception as e:
            self.logger.error(f"Error starting interaction: {e}")
            raise
    
    async def end_interaction(self, interaction_id: str, outcomes: List[str]) -> Dict[str, Any]:
        """End a social interaction."""
        try:
            if interaction_id not in self._interactions:
                raise ValueError(f"Interaction {interaction_id} not found")
            
            interaction = self._interactions[interaction_id]
            interaction.end_time = datetime.now()
            interaction.duration_seconds = (interaction.end_time - interaction.start_time).total_seconds()
            interaction.outcomes = outcomes
            
            # Calculate communication quality
            interaction.communication_quality = await self._calculate_communication_quality(interaction)
            
            # Update relationship impacts
            interaction.relationship_impact = await self._calculate_relationship_impacts(interaction)
            
            # Update relationships
            await self._update_relationships_from_interaction(interaction)
            
            # Remove from context stack
            if self._context_stack and self._context_stack[-1] == interaction.context:
                self._context_stack.pop()
            
            # Clean up old interactions if needed
            await self._cleanup_old_interactions()
            
            result = {
                'success': True,
                'interaction_id': interaction_id,
                'duration_seconds': interaction.duration_seconds,
                'communication_quality': interaction.communication_quality,
                'relationship_impacts': interaction.relationship_impact,
                'outcomes': outcomes
            }
            
            self.logger.info(f"Ended interaction: {interaction_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error ending interaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def adapt_communication_style(
        self,
        participant_id: str,
        context: SocialContext
    ) -> CommunicationStyle:
        """Adapt communication style based on participant and context."""
        try:
            # Get existing relationship
            relationship = self._relationships.get(participant_id)
            
            if relationship:
                # Use relationship's preferred style if available
                if relationship.communication_style != CommunicationStyle.FORMAL:
                    return relationship.communication_style
                
                # Adapt based on role and context
                role = relationship.role
                interaction_type = context.interaction_type
                
                # Adjust style based on role and interaction type
                if role in [SocialRole.SUPERIOR, SocialRole.MENTOR] and interaction_type in [InteractionType.MEETING, InteractionType.PRESENTATION]:
                    return CommunicationStyle.FORMAL
                elif role in [SocialRole.FRIEND, SocialRole.FAMILY] and interaction_type == InteractionType.CHAT:
                    return CommunicationStyle.INFORMAL
                elif interaction_type == InteractionType.NEGOTIATION:
                    return CommunicationStyle.ASSERTIVE
                else:
                    return CommunicationStyle.COLLABORATIVE
            else:
                # Default to context formality level
                if context.formality_level > 0.7:
                    return CommunicationStyle.FORMAL
                elif context.formality_level < 0.3:
                    return CommunicationStyle.INFORMAL
                else:
                    return self._default_communication_style
            
        except Exception as e:
            self.logger.error(f"Error adapting communication style: {e}")
            return self._default_communication_style
    
    async def suggest_relationship_improvement(self, participant_id: str) -> List[str]:
        """Suggest ways to improve a relationship."""
        try:
            relationship = self._relationships.get(participant_id)
            if not relationship:
                return ["No existing relationship found"]
            
            suggestions = []
            
            # Suggest based on relationship status
            if relationship.status == RelationshipStatus.NEW:
                suggestions.append("Introduce yourself and learn about their interests")
                suggestions.append("Find common ground and shared interests")
            elif relationship.status == RelationshipStatus.DETERIORATING:
                suggestions.append("Address any issues or concerns directly")
                suggestions.append("Schedule a one-on-one conversation to reconnect")
            elif relationship.status == RelationshipStatus.ESTABLISHED:
                suggestions.append("Look for opportunities to collaborate on projects")
                suggestions.append("Share relevant resources or information")
            
            # Suggest based on trust level
            if relationship.trust_level < 0.3:
                suggestions.append("Be consistent and reliable in your interactions")
                suggestions.append("Follow through on commitments and promises")
            elif relationship.trust_level < 0.6:
                suggestions.append("Share more personal insights appropriately")
                suggestions.append("Show genuine interest in their work and goals")
            
            # Suggest based on interaction frequency
            if relationship.interaction_frequency == "rarely":
                suggestions.append("Schedule regular check-ins or conversations")
                suggestions.append("Initiate contact more frequently")
            
            # Suggest based on rapport level
            if relationship.rapport_level < 0.4:
                suggestions.append("Find opportunities for informal conversations")
                suggestions.append("Show appreciation for their contributions")
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error suggesting relationship improvement: {e}")
            return []
    
    async def get_social_insights(self, participant_id: str) -> Dict[str, Any]:
        """Get social insights about a participant."""
        try:
            relationship = self._relationships.get(participant_id)
            if not relationship:
                return {'error': 'No relationship found'}
            
            # Get recent interactions
            recent_interactions = await self._get_recent_interactions(participant_id)
            
            insights = {
                'relationship_strength': relationship.calculate_relationship_strength(),
                'trust_level': relationship.trust_level,
                'rapport_level': relationship.rapport_level,
                'last_interaction': relationship.last_interaction.isoformat() if relationship.last_interaction else None,
                'interaction_frequency': relationship.interaction_frequency,
                'communication_style': relationship.communication_style.value,
                'role': relationship.role.value,
                'status': relationship.status.value,
                'shared_interests': relationship.shared_interests,
                'recent_interactions_count': len(recent_interactions),
                'average_communication_quality': 0.0,
                'relationship_trend': 'stable'  # calculated based on recent interactions
            }
            
            # Calculate average communication quality from recent interactions
            if recent_interactions:
                quality_scores = [interaction.communication_quality for interaction in recent_interactions if interaction.communication_quality > 0]
                if quality_scores:
                    insights['average_communication_quality'] = sum(quality_scores) / len(quality_scores)
                
                # Determine trend
                if len(quality_scores) >= 2:
                    recent_quality = quality_scores[-1]
                    previous_quality = quality_scores[-2]
                    if recent_quality > previous_quality:
                        insights['relationship_trend'] = 'improving'
                    elif recent_quality < previous_quality:
                        insights['relationship_trend'] = 'declining'
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting social insights: {e}")
            return {'error': str(e)}
    
    async def manage_relationships(self) -> Dict[str, Any]:
        """Manage all relationships and provide recommendations."""
        try:
            recommendations = []
            
            for participant_id, relationship in self._relationships.items():
                # Check if relationship needs attention
                if relationship.status == RelationshipStatus.DETERIORATING:
                    recommendations.append({
                        'participant_id': participant_id,
                        'participant_name': relationship.participant_name,
                        'action': 'reconnect',
                        'priority': 'high',
                        'reason': 'Relationship is deteriorating'
                    })
                elif relationship.status == RelationshipStatus.NEW:
                    recommendations.append({
                        'participant_id': participant_id,
                        'participant_name': relationship.participant_name,
                        'action': 'engage',
                        'priority': 'medium',
                        'reason': 'New relationship needs development'
                    })
                elif relationship.trust_level < 0.3:
                    recommendations.append({
                        'participant_id': participant_id,
                        'participant_name': relationship.participant_name,
                        'action': 'build_trust',
                        'priority': 'high',
                        'reason': 'Low trust level detected'
                    })
                elif relationship.interaction_frequency == 'rarely' and relationship.status != RelationshipStatus.TERMINATED:
                    recommendations.append({
                        'participant_id': participant_id,
                        'participant_name': relationship.participant_name,
                        'action': 'increase_frequency',
                        'priority': 'medium',
                        'reason': 'Low interaction frequency'
                    })
            
            # Update statistics
            await self._update_social_stats()
            
            return {
                'total_relationships': len(self._relationships),
                'recommendations': recommendations,
                'average_relationship_strength': self._average_relationship_strength,
                'last_update': self._last_relationship_update.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error managing relationships: {e}")
            return {'error': str(e)}
    
    async def get_social_network_map(self) -> Dict[str, Any]:
        """Get a map of the social network."""
        try:
            network = {
                'participants': [],
                'relationships': [],
                'clusters': [],  # Groups of closely connected participants
                'influencers': [],  # Highly connected participants
                'isolated': []  # Participants with few connections
            }
            
            # Add participants
            for participant_id, relationship in self._relationships.items():
                network['participants'].append({
                    'id': participant_id,
                    'name': relationship.participant_name,
                    'role': relationship.role.value,
                    'trust_level': relationship.trust_level,
                    'rapport_level': relationship.rapport_level,
                    'relationship_strength': relationship.calculate_relationship_strength()
                })
            
            # For now, just return basic network info
            # In a real implementation, we would analyze connections between participants
            
            return network
            
        except Exception as e:
            self.logger.error(f"Error getting social network map: {e}")
            return {'error': str(e)}
    
    async def get_social_stats(self) -> Dict[str, Any]:
        """Get social communication statistics."""
        try:
            stats = {
                'total_relationships': len(self._relationships),
                'total_interactions': len(self._interactions),
                'average_relationship_strength': self._average_relationship_strength,
                'relationships_by_status': {
                    status.value: sum(1 for rel in self._relationships.values() if rel.status == status)
                    for status in RelationshipStatus
                },
                'relationships_by_role': {
                    role.value: sum(1 for rel in self._relationships.values() if rel.role == role)
                    for role in SocialRole
                },
                'interaction_types': self._interaction_types_count.copy(),
                'most_active_participants': [],
                'relationship_growth_rate': 0.0,
                'last_update': self._last_relationship_update.isoformat()
            }
            
            # Find most active participants
            interaction_counts = {}
            for interaction in self._interactions.values():
                for participant in interaction.participants:
                    interaction_counts[participant] = interaction_counts.get(participant, 0) + 1
            
            sorted_participants = sorted(interaction_counts.items(), key=lambda x: x[1], reverse=True)
            stats['most_active_participants'] = [
                {'participant_id': pid, 'interaction_count': count}
                for pid, count in sorted_participants[:10]  # Top 10
            ]
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting social stats: {e}")
            return {}
    
    async def _validate_relationship(self, relationship: SocialRelationship) -> None:
        """Validate relationship data."""
        if not relationship.participant_id:
            raise ValueError("Participant ID is required")
        
        if not relationship.participant_name:
            raise ValueError("Participant name is required")
        
        if relationship.trust_level < 0.0 or relationship.trust_level > 1.0:
            raise ValueError("Trust level must be between 0.0 and 1.0")
        
        if relationship.rapport_level < 0.0 or relationship.rapport_level > 1.0:
            raise ValueError("Rapport level must be between 0.0 and 1.0")
    
    async def _update_relationship_stats(self, relationship: SocialRelationship) -> None:
        """Update relationship statistics."""
        # Calculate average relationship strength
        strengths = [rel.calculate_relationship_strength() for rel in self._relationships.values()]
        if strengths:
            self._average_relationship_strength = sum(strengths) / len(strengths)
        
        self._last_relationship_update = datetime.now()
    
    async def _calculate_communication_quality(self, interaction: SocialInteraction) -> float:
        """Calculate communication quality for an interaction."""
        # Base quality from engagement levels
        engagement_scores = list(interaction.engagement_levels.values())
        base_quality = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0.5
        
        # Adjust based on sentiment
        sentiment_scores = list(interaction.sentiment_analysis.values())
        sentiment_adjustment = 0.0
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            sentiment_adjustment = avg_sentiment * 0.2  # Sentiment affects quality by 20%
        
        # Adjust based on outcomes
        outcome_score = len(interaction.outcomes) * 0.1 if interaction.outcomes else 0.0
        outcome_score = min(0.3, outcome_score)  # Cap at 30%
        
        # Combine scores
        quality = base_quality * 0.5 + sentiment_adjustment * 0.3 + outcome_score * 0.2
        return max(0.0, min(1.0, quality))
    
    async def _calculate_relationship_impacts(self, interaction: SocialInteraction) -> Dict[str, float]:
        """Calculate impact of interaction on relationships."""
        impacts = {}
        
        for participant_id in interaction.participants:
            # Base impact on communication quality
            base_impact = interaction.communication_quality * 0.3
            
            # Impact based on engagement
            engagement = interaction.engagement_levels.get(participant_id, 0.5)
            engagement_impact = engagement * 0.3
            
            # Impact based on sentiment
            sentiment = interaction.sentiment_analysis.get(participant_id, 0.0)
            sentiment_impact = sentiment * 0.4
            
            # Combine impacts
            total_impact = base_impact + engagement_impact + sentiment_impact
            impacts[participant_id] = max(-1.0, min(1.0, total_impact))  # Clamp between -1 and 1
        
        return impacts
    
    async def _update_relationships_from_interaction(self, interaction: SocialInteraction) -> None:
        """Update relationships based on interaction outcomes."""
        for participant_id, impact in interaction.relationship_impact.items():
            if participant_id in self._relationships:
                relationship = self._relationships[participant_id]
                
                # Update trust level based on impact
                relationship.trust_level = max(0.0, min(1.0, relationship.trust_level + impact * 0.1))
                
                # Update rapport level based on positive impact
                if impact > 0:
                    relationship.rapport_level = max(0.0, min(1.0, relationship.rapport_level + impact * 0.05))
                
                # Update last interaction time
                relationship.last_interaction = datetime.now()
                
                # Add to interaction history
                relationship.interaction_history.append(interaction.id)
                
                # Update status based on trust and rapport
                relationship.status = await self._determine_relationship_status(relationship)
                
                # Update relationship
                await self.update_relationship(relationship)
    
    async def _determine_relationship_status(self, relationship: SocialRelationship) -> RelationshipStatus:
        """Determine relationship status based on metrics."""
        strength = relationship.calculate_relationship_strength()
        
        if strength >= 0.8:
            return RelationshipStatus.STRONG
        elif strength >= 0.6:
            return RelationshipStatus.ESTABLISHED
        elif strength >= 0.4:
            return RelationshipStatus.DEVELOPING
        elif strength >= 0.2:
            return RelationshipStatus.NEW
        else:
            # Check if deteriorating
            if relationship.last_interaction:
                days_since_interaction = (datetime.now() - relationship.last_interaction).days
                if days_since_interaction > 180:  # 6 months
                    return RelationshipStatus.DETERIORATING
            
            return RelationshipStatus.NEW
    
    async def _get_recent_interactions(self, participant_id: str, days: int = 30) -> List[SocialInteraction]:
        """Get recent interactions with a participant."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_interactions = []
        for interaction in self._interactions.values():
            if (participant_id in interaction.participants and 
                interaction.start_time >= cutoff_date):
                recent_interactions.append(interaction)
        
        return recent_interactions
    
    async def _cleanup_old_interactions(self) -> None:
        """Clean up old interactions to manage memory."""
        if len(self._interactions) > self._max_interactions:
            # Sort interactions by start time (oldest first)
            sorted_interactions = sorted(
                self._interactions.items(),
                key=lambda x: x[1].start_time
            )
            
            # Remove oldest interactions (keep last 5000)
            to_remove = len(self._interactions) - 500
            for i in range(min(to_remove, len(sorted_interactions))):
                interaction_id, _ = sorted_interactions[i]
                del self._interactions[interaction_id]
    
    async def _load_saved_data(self) -> None:
        """Load saved relationships and interactions."""
        # In a real implementation, this would load from persistent storage
        # For now, just initialize empty collections
        pass
    
    async def _update_social_stats(self) -> None:
        """Update social statistics."""
        # Calculate average relationship strength
        strengths = [rel.calculate_relationship_strength() for rel in self._relationships.values()]
        if strengths:
            self._average_relationship_strength = sum(strengths) / len(strengths)
        
        self._last_relationship_update = datetime.now()