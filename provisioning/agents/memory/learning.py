"""
Learning Memory Module

Manages learning processes, adaptation, and knowledge acquisition for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import math


class LearningType(Enum):
    """Types of learning processes."""
    
    SUPERVISED = "supervised"
    UNSUPERVISED = "unsupervised"
    REINFORCEMENT = "reinforcement"
    TRANSFER = "transfer"
    LIFELONG = "lifelong"
    ACTIVE = "active"
    META_LEARNING = "meta_learning"


class LearningStrategy(Enum):
    """Learning strategies."""
    
    REPETITION = "repetition"
    SPACED_REPETITION = "spaced_repetition"
    INTERLEAVING = "interleaving"
    ELABORATION = "elaboration"
    MIRRORING = "mirroring"
    ANALOGY = "analogy"
    EXPERIMENTATION = "experimentation"
    FEEDBACK_DRIVEN = "feedback_driven"


class KnowledgeStatus(Enum):
    """Status of knowledge items."""
    
    UNKNOWN = "unknown"
    LEARNING = "learning"
    PRACTICING = "practicing"
    MASTERED = "mastered"
    REFRESHING = "refreshing"
    DECAYING = "decaying"
    FORGOTTEN = "forgotten"


@dataclass
class LearningObjective:
    """A learning objective for the agent."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    learning_type: LearningType = LearningType.SUPERVISED
    target_knowledge: List[str] = field(default_factory=list)
    target_skills: List[str] = field(default_factory=list)
    success_criteria: List[Dict[str, Any]] = field(default_factory=list)
    priority: float = 0.5  # 0.0 to 1.0
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    status: str = "active"  # active, completed, paused, cancelled
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert objective to dictionary."""
        data = asdict(self)
        data['learning_type'] = self.learning_type.value
        data['created_at'] = self.created_at.isoformat()
        data['deadline'] = self.deadline.isoformat() if self.deadline else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningObjective':
        """Create objective from dictionary."""
        if 'learning_type' in data and isinstance(data['learning_type'], str):
            data['learning_type'] = LearningType(data['learning_type'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'deadline' in data and isinstance(data['deadline'], str):
            data['deadline'] = datetime.fromisoformat(data['deadline'])
        if 'completed_at' in data and isinstance(data['completed_at'], str):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


@dataclass
class KnowledgeItem:
    """A piece of knowledge being learned."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    knowledge_type: str = "fact"  # fact, concept, procedure, principle
    domain: str = ""
    difficulty: float = 0.5  # 0.0 to 1.0
    importance: float = 0.5  # 0.0 to 1.0
    status: KnowledgeStatus = KnowledgeStatus.UNKNOWN
    confidence: float = 0.0  # 0.0 to 1.0
    mastery_level: float = 0.0  # 0.0 to 1.0
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    review_count: int = 0
    correct_reviews: int = 0
    incorrect_reviews: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    related_items: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert knowledge item to dictionary."""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_reviewed'] = self.last_reviewed.isoformat() if self.last_reviewed else None
        data['next_review'] = self.next_review.isoformat() if self.next_review else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeItem':
        """Create knowledge item from dictionary."""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = KnowledgeStatus(data['status'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_reviewed' in data and isinstance(data['last_reviewed'], str):
            data['last_reviewed'] = datetime.fromisoformat(data['last_reviewed'])
        if 'next_review' in data and isinstance(data['next_review'], str):
            data['next_review'] = datetime.fromisoformat(data['next_review'])
        return cls(**data)
    
    def calculate_recall_probability(self) -> float:
        """Calculate probability of recall using forgetting curve."""
        if self.mastery_level == 0:
            return 0.0
        
        if not self.last_reviewed:
            return 0.1
        
        # Time since last review (in days)
        days_since_review = (datetime.now() - self.last_reviewed).days
        
        # Forgetting curve parameters
        initial_strength = self.mastery_level
        decay_rate = 0.1 * (1.0 - self.mastery_level)  # Better mastery = slower decay
        
        # Exponential decay
        recall_probability = initial_strength * math.exp(-decay_rate * days_since_review)
        
        return max(0.0, min(1.0, recall_probability))
    
    def should_review(self) -> bool:
        """Check if knowledge item should be reviewed."""
        if not self.next_review:
            return True
        
        return datetime.now() >= self.next_review
    
    def update_from_review(self, correct: bool) -> None:
        """Update knowledge item based on review outcome."""
        self.review_count += 1
        self.last_reviewed = datetime.now()
        self.updated_at = datetime.now()
        
        if correct:
            self.correct_reviews += 1
            # Increase mastery and confidence
            self.mastery_level = min(1.0, self.mastery_level + 0.1)
            self.confidence = min(1.0, self.confidence + 0.05)
            
            # Update status
            if self.mastery_level >= 0.8:
                self.status = KnowledgeStatus.MASTERED
            elif self.mastery_level >= 0.5:
                self.status = KnowledgeStatus.PRACTICING
            else:
                self.status = KnowledgeStatus.LEARNING
            
            # Schedule next review (spaced repetition)
            interval_multiplier = 2.5 ** (self.mastery_level * 3)  # Exponential spacing
            next_interval_days = min(365, max(1, interval_multiplier))
            self.next_review = datetime.now() + timedelta(days=next_interval_days)
        else:
            self.incorrect_reviews += 1
            # Decrease mastery and confidence
            self.mastery_level = max(0.0, self.mastery_level - 0.2)
            self.confidence = max(0.0, self.confidence - 0.1)
            
            # Update status
            if self.mastery_level < 0.2:
                self.status = KnowledgeStatus.FORGOTTEN
            elif self.mastery_level < 0.4:
                self.status = KnowledgeStatus.DECAYING
            else:
                self.status = KnowledgeStatus.REFRESHING
            
            # Schedule sooner review
            self.next_review = datetime.now() + timedelta(days=1)


@dataclass
class LearningSession:
    """A learning session."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    objective_id: str = ""
    strategy: LearningStrategy = LearningStrategy.REPETITION
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    items_reviewed: List[str] = field(default_factory=list)
    correct_responses: int = 0
    incorrect_responses: int = 0
    focus_score: float = 0.0  # 0.0 to 1.0
    engagement_score: float = 0.0  # 0.0 to 1.0
    learning_gains: Dict[str, float] = field(default_factory=dict)
    challenges_faced: List[str] = field(default_factory=list)
    insights_gained: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        data = asdict(self)
        data['strategy'] = self.strategy.value
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningSession':
        """Create session from dictionary."""
        if 'strategy' in data and isinstance(data['strategy'], str):
            data['strategy'] = LearningStrategy(data['strategy'])
        if 'start_time' in data and isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)
    
    def calculate_effectiveness(self) -> float:
        """Calculate session effectiveness score."""
        if self.duration_seconds == 0:
            return 0.0
        
        # Base effectiveness from accuracy
        total_responses = self.correct_responses + self.incorrect_responses
        accuracy = self.correct_responses / total_responses if total_responses > 0 else 0.0
        
        # Adjust for focus and engagement
        adjusted_accuracy = accuracy * (0.7 * self.focus_score + 0.3 * self.engagement_score)
        
        # Consider learning gains
        if self.learning_gains:
            avg_gain = sum(self.learning_gains.values()) / len(self.learning_gains)
            adjusted_accuracy = 0.7 * adjusted_accuracy + 0.3 * avg_gain
        
        return min(1.0, adjusted_accuracy)


class LearningMemory:
    """Manages learning processes and knowledge acquisition."""
    
    def __init__(self, config):
        """Initialize learning memory."""
        self.config = config
        self.logger = logging.getLogger("learning_memory")
        
        # Storage
        self._objectives: Dict[str, LearningObjective] = {}
        self._knowledge_items: Dict[str, KnowledgeItem] = {}
        self._sessions: Dict[str, LearningSession] = {}
        
        # Indices
        self._domain_index: Dict[str, List[str]] = {}
        self._status_index: Dict[KnowledgeStatus, List[str]] = {
            status: [] for status in KnowledgeStatus
        }
        self._tag_index: Dict[str, List[str]] = {}
        self._objective_index: Dict[str, List[str]] = {}  # objective_id -> knowledge_item_ids
        
        # Learning parameters
        self._max_daily_sessions = 10
        self._session_duration_minutes = 30
        self._review_batch_size = 20
        self._mastery_threshold = 0.8
        self._forgetting_threshold = 0.3
        
        # Statistics
        self._total_objectives = 0
        self._total_knowledge = 0
        self._total_sessions = 0
        self._last_optimization = datetime.now()
    
    async def create_objective(self, objective: LearningObjective) -> str:
        """Create a new learning objective."""
        try:
            # Store objective
            self._objectives[objective.id] = objective
            
            # Update statistics
            self._total_objectives += 1
            
            # Initialize objective index
            self._objective_index[objective.id] = []
            
            self.logger.info(f"Created learning objective: {objective.name}")
            return objective.id
            
        except Exception as e:
            self.logger.error(f"Error creating objective: {e}")
            raise
    
    async def add_knowledge_item(
        self,
        objective_id: str,
        knowledge_item: KnowledgeItem
    ) -> str:
        """Add a knowledge item to an objective."""
        try:
            # Validate objective exists
            if objective_id not in self._objectives:
                raise ValueError(f"Objective {objective_id} not found")
            
            # Store knowledge item
            self._knowledge_items[knowledge_item.id] = knowledge_item
            
            # Update indices
            await self._index_knowledge_item(knowledge_item)
            
            # Link to objective
            if objective_id not in self._objective_index:
                self._objective_index[objective_id] = []
            self._objective_index[objective_id].append(knowledge_item.id)
            
            # Update statistics
            self._total_knowledge += 1
            
            self.logger.debug(f"Added knowledge item: {knowledge_item.id}")
            return knowledge_item.id
            
        except Exception as e:
            self.logger.error(f"Error adding knowledge item: {e}")
            raise
    
    async def start_learning_session(
        self,
        objective_id: str,
        strategy: LearningStrategy = LearningStrategy.SPACED_REPETITION
    ) -> str:
        """Start a new learning session."""
        try:
            # Validate objective exists
            if objective_id not in self._objectives:
                raise ValueError(f"Objective {objective_id} not found")
            
            # Create session
            session = LearningSession(
                objective_id=objective_id,
                strategy=strategy
            )
            
            # Store session
            self._sessions[session.id] = session
            
            # Update statistics
            self._total_sessions += 1
            
            self.logger.info(f"Started learning session: {session.id}")
            return session.id
            
        except Exception as e:
            self.logger.error(f"Error starting learning session: {e}")
            raise
    
    async def get_items_for_review(
        self,
        objective_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get knowledge items that need review."""
        try:
            items_to_review = []
            
            # Filter by objective if specified
            if objective_id:
                if objective_id not in self._objective_index:
                    return []
                item_ids = self._objective_index[objective_id]
            else:
                item_ids = list(self._knowledge_items.keys())
            
            # Get items that need review
            for item_id in item_ids:
                if item_id not in self._knowledge_items:
                    continue
                
                item = self._knowledge_items[item_id]
                
                if item.should_review():
                    # Calculate priority
                    priority = await self._calculate_review_priority(item)
                    
                    items_to_review.append({
                        'item_id': item.id,
                        'content': item.content,
                        'knowledge_type': item.knowledge_type,
                        'domain': item.domain,
                        'difficulty': item.difficulty,
                        'importance': item.importance,
                        'mastery_level': item.mastery_level,
                        'recall_probability': item.calculate_recall_probability(),
                        'days_since_review': (datetime.now() - item.last_reviewed).days if item.last_reviewed else 999,
                        'priority': priority,
                        'status': item.status.value
                    })
            
            # Sort by priority
            items_to_review.sort(key=lambda x: x['priority'], reverse=True)
            return items_to_review[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting items for review: {e}")
            return []
    
    async def submit_review(
        self,
        session_id: str,
        item_id: str,
        correct: bool,
        response_time_ms: int,
        confidence: float
    ) -> Dict[str, Any]:
        """Submit a review response."""
        try:
            # Validate session and item exist
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")
            if item_id not in self._knowledge_items:
                raise ValueError(f"Knowledge item {item_id} not found")
            
            session = self._sessions[session_id]
            item = self._knowledge_items[item_id]
            
            # Update knowledge item
            item.update_from_review(correct)
            
            # Update session
            if item_id not in session.items_reviewed:
                session.items_reviewed.append(item_id)
            
            if correct:
                session.correct_responses += 1
            else:
                session.incorrect_responses += 1
            
            # Calculate learning gain
            previous_mastery = item.mastery_level - (0.1 if correct else -0.2)
            learning_gain = max(0.0, item.mastery_level - previous_mastery)
            session.learning_gains[item_id] = learning_gain
            
            # Update objective progress
            await self._update_objective_progress(session.objective_id)
            
            return {
                'success': True,
                'item_id': item_id,
                'new_mastery': item.mastery_level,
                'new_status': item.status.value,
                'next_review': item.next_review.isoformat() if item.next_review else None,
                'learning_gain': learning_gain
            }
            
        except Exception as e:
            self.logger.error(f"Error submitting review: {e}")
            return {'success': False, 'error': str(e)}
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """End a learning session."""
        try:
            if session_id not in self._sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session = self._sessions[session_id]
            session.end_time = datetime.now()
            session.duration_seconds = (session.end_time - session.start_time).total_seconds()
            
            # Calculate session metrics
            effectiveness = session.calculate_effectiveness()
            
            # Generate insights
            insights = await self._generate_session_insights(session)
            session.insights_gained = insights
            
            # Update objective progress
            await self._update_objective_progress(session.objective_id)
            
            # Check if optimization is needed
            await self._check_optimization()
            
            return {
                'success': True,
                'session_id': session_id,
                'duration_seconds': session.duration_seconds,
                'items_reviewed': len(session.items_reviewed),
                'accuracy': session.correct_responses / (session.correct_responses + session.incorrect_responses) if (session.correct_responses + session.incorrect_responses) > 0 else 0.0,
                'effectiveness': effectiveness,
                'insights': insights
            }
            
        except Exception as e:
            self.logger.error(f"Error ending session: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_learning_progress(self, objective_id: str) -> Dict[str, Any]:
        """Get learning progress for an objective."""
        try:
            if objective_id not in self._objectives:
                raise ValueError(f"Objective {objective_id} not found")
            
            objective = self._objectives[objective_id]
            
            # Get knowledge items for this objective
            item_ids = self._objective_index.get(objective_id, [])
            items = [self._knowledge_items[item_id] for item_id in item_ids if item_id in self._knowledge_items]
            
            if not items:
                return {
                    'objective_id': objective_id,
                    'objective_name': objective.name,
                    'progress': 0.0,
                    'total_items': 0,
                    'mastered_items': 0,
                    'learning_items': 0,
                    'practicing_items': 0,
                    'forgotten_items': 0,
                    'average_mastery': 0.0,
                    'average_confidence': 0.0
                }
            
            # Calculate statistics
            total_items = len(items)
            mastered_items = sum(1 for item in items if item.status == KnowledgeStatus.MASTERED)
            learning_items = sum(1 for item in items if item.status == KnowledgeStatus.LEARNING)
            practicing_items = sum(1 for item in items if item.status == KnowledgeStatus.PRACTICING)
            forgotten_items = sum(1 for item in items if item.status in [KnowledgeStatus.FORGOTTEN, KnowledgeStatus.DECAYING])
            
            average_mastery = sum(item.mastery_level for item in items) / total_items
            average_confidence = sum(item.confidence for item in items) / total_items
            
            # Calculate overall progress
            progress = (mastered_items + 0.5 * practicing_items + 0.25 * learning_items) / total_items
            
            return {
                'objective_id': objective_id,
                'objective_name': objective.name,
                'progress': progress,
                'total_items': total_items,
                'mastered_items': mastered_items,
                'learning_items': learning_items,
                'practicing_items': practicing_items,
                'forgotten_items': forgotten_items,
                'average_mastery': average_mastery,
                'average_confidence': average_confidence,
                'deadline': objective.deadline.isoformat() if objective.deadline else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting learning progress: {e}")
            return {}
    
    async def recommend_learning_strategy(
        self,
        objective_id: str,
        recent_performance: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Recommend optimal learning strategy."""
        try:
            if objective_id not in self._objectives:
                raise ValueError(f"Objective {objective_id} not found")
            
            objective = self._objectives[objective_id]
            
            # Get current progress
            progress_data = await self.get_learning_progress(objective_id)
            
            # Analyze recent performance
            performance_analysis = await self._analyze_recent_performance(
                objective_id, recent_performance
            )
            
            # Recommend strategy based on analysis
            recommendations = []
            
            if progress_data['average_mastery'] < 0.3:
                # Beginner - need repetition and basic practice
                recommendations.append({
                    'strategy': LearningStrategy.REPETITION,
                    'reason': 'Low mastery level requires basic repetition',
                    'confidence': 0.8
                })
                recommendations.append({
                    'strategy': LearningStrategy.FEEDBACK_DRIVEN,
                    'reason': 'Beginners benefit from immediate feedback',
                    'confidence': 0.7
                })
            
            elif progress_data['forgotten_items'] > progress_data['total_items'] * 0.3:
                # Forgetting issues - need spaced repetition
                recommendations.append({
                    'strategy': LearningStrategy.SPACED_REPETITION,
                    'reason': 'High forgetting rate requires spaced repetition',
                    'confidence': 0.9
                })
                recommendations.append({
                    'strategy': LearningStrategy.REFRESHING,
                    'reason': 'Need to refresh forgotten knowledge',
                    'confidence': 0.8
                })
            
            elif progress_data['average_mastery'] > 0.7:
                # Advanced - need interleaving and elaboration
                recommendations.append({
                    'strategy': LearningStrategy.INTERLEAVING,
                    'reason': 'High mastery level benefits from interleaving',
                    'confidence': 0.8
                })
                recommendations.append({
                    'strategy': LearningStrategy.ELABORATION,
                    'reason': 'Advanced learners benefit from deeper processing',
                    'confidence': 0.7
                })
            
            else:
                # Intermediate - mixed approach
                recommendations.append({
                    'strategy': LearningStrategy.SPACED_REPETITION,
                    'reason': 'Balanced approach for intermediate learners',
                    'confidence': 0.7
                })
                recommendations.append({
                    'strategy': LearningStrategy.INTERLEAVING,
                    'reason': 'Mix different topics to improve retention',
                    'confidence': 0.6
                })
            
            # Sort by confidence
            recommendations.sort(key=lambda x: x['confidence'], reverse=True)
            
            return {
                'objective_id': objective_id,
                'current_progress': progress_data,
                'performance_analysis': performance_analysis,
                'recommended_strategy': recommendations[0] if recommendations else None,
                'alternative_strategies': recommendations[1:3] if len(recommendations) > 1 else []
            }
            
        except Exception as e:
            self.logger.error(f"Error recommending learning strategy: {e}")
            return {}
    
    async def optimize_learning_schedule(self) -> Dict[str, Any]:
        """Optimize the overall learning schedule."""
        try:
            optimizations = []
            
            # Find overdue items
            overdue_items = []
            for item in self._knowledge_items.values():
                if item.should_review():
                    days_overdue = (datetime.now() - item.next_review).days if item.next_review else 999
                    if days_overdue > 0:
                        overdue_items.append((item.id, days_overdue, item.importance))
            
            # Sort by importance and overdue days
            overdue_items.sort(key=lambda x: (x[2], x[1]), reverse=True)
            
            # Prioritize overdue items
            if overdue_items:
                optimizations.append({
                    'type': 'prioritize_overdue',
                    'description': f'Prioritize {len(overdue_items)} overdue items',
                    'items': overdue_items[:10]  # Top 10
                })
            
            # Find items at risk of forgetting
            at_risk_items = []
            for item in self._knowledge_items.values():
                recall_prob = item.calculate_recall_probability()
                if recall_prob < self._forgetting_threshold and item.mastery_level > 0.3:
                    at_risk_items.append((item.id, recall_prob, item.importance))
            
            if at_risk_items:
                optimizations.append({
                    'type': 'prevent_forgetting',
                    'description': f'Review {len(at_risk_items)} items at risk of forgetting',
                    'items': at_risk_items[:10]
                })
            
            # Schedule optimization
            for item_id, _, _ in overdue_items[:5]:  # Top 5 overdue
                if item_id in self._knowledge_items:
                    item = self._knowledge_items[item_id]
                    item.next_review = datetime.now() + timedelta(hours=1)
            
            self._last_optimization = datetime.now()
            
            return {
                'success': True,
                'optimizations': optimizations,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing learning schedule: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get learning memory statistics."""
        try:
            stats = {
                'total_objectives': len(self._objectives),
                'total_knowledge_items': len(self._knowledge_items),
                'total_sessions': len(self._sessions),
                'knowledge_by_status': {
                    status.value: len(ids)
                    for status, ids in self._status_index.items()
                },
                'knowledge_by_domain': {
                    domain: len(ids)
                    for domain, ids in self._domain_index.items()
                },
                'average_mastery': 0.0,
                'average_confidence': 0.0,
                'items_needing_review': 0,
                'overdue_items': 0,
                'last_optimization': self._last_optimization.isoformat()
            }
            
            # Calculate averages
            if self._knowledge_items:
                stats['average_mastery'] = sum(
                    item.mastery_level for item in self._knowledge_items.values()
                ) / len(self._knowledge_items)
                stats['average_confidence'] = sum(
                    item.confidence for item in self._knowledge_items.values()
                ) / len(self._knowledge_items)
                
                # Count items needing review
                stats['items_needing_review'] = sum(
                    1 for item in self._knowledge_items.values()
                    if item.should_review()
                )
                
                # Count overdue items
                now = datetime.now()
                stats['overdue_items'] = sum(
                    1 for item in self._knowledge_items.values()
                    if item.next_review and now > item.next_review
                )
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _index_knowledge_item(self, item: KnowledgeItem) -> None:
        """Index a knowledge item for efficient retrieval."""
        # Status index
        if item.id not in self._status_index[item.status]:
            self._status_index[item.status].append(item.id)
        
        # Domain index
        if item.domain:
            if item.domain not in self._domain_index:
                self._domain_index[item.domain] = []
            if item.id not in self._domain_index[item.domain]:
                self._domain_index[item.domain].append(item.id)
        
        # Tag index
        for tag in item.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if item.id not in self._tag_index[tag]:
                self._tag_index[tag].append(item.id)
    
    async def _unindex_knowledge_item(self, item: KnowledgeItem) -> None:
        """Remove a knowledge item from indices."""
        # Status index
        if item.id in self._status_index[item.status]:
            self._status_index[item.status].remove(item.id)
        
        # Domain index
        if item.domain and item.domain in self._domain_index:
            if item.id in self._domain_index[item.domain]:
                self._domain_index[item.domain].remove(item.id)
                if not self._domain_index[item.domain]:
                    del self._domain_index[item.domain]
        
        # Tag index
        for tag in item.tags:
            if tag in self._tag_index and item.id in self._tag_index[tag]:
                self._tag_index[tag].remove(item.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
    
    async def _calculate_review_priority(self, item: KnowledgeItem) -> float:
        """Calculate review priority for a knowledge item."""
        priority = 0.0
        
        # Importance factor
        priority += item.importance * 0.3
        
        # Urgency (how overdue)
        if item.next_review:
            days_overdue = (datetime.now() - item.next_review).days
            urgency = min(1.0, days_overdue / 30.0)  # Max urgency at 30 days overdue
            priority += urgency * 0.4
        
        # Forgetting risk
        recall_prob = item.calculate_recall_probability()
        forgetting_risk = 1.0 - recall_prob
        priority += forgetting_risk * 0.2
        
        # Mastery level (lower mastery = higher priority)
        mastery_priority = 1.0 - item.mastery_level
        priority += mastery_priority * 0.1
        
        return min(1.0, priority)
    
    async def _update_objective_progress(self, objective_id: str) -> None:
        """Update objective progress based on knowledge items."""
        if objective_id not in self._objectives:
            return
        
        objective = self._objectives[objective_id]
        progress_data = await self.get_learning_progress(objective_id)
        
        objective.progress = progress_data['progress']
        
        # Check if objective is completed
        if objective.progress >= 0.9:  # 90% mastery threshold
            objective.completed_at = datetime.now()
            objective.status = "completed"
    
    async def _generate_session_insights(self, session: LearningSession) -> List[str]:
        """Generate insights from a learning session."""
        insights = []
        
        # Accuracy insight
        total_responses = session.correct_responses + session.incorrect_responses
        if total_responses > 0:
            accuracy = session.correct_responses / total_responses
            if accuracy >= 0.9:
                insights.append("Excellent performance! Consider moving to more challenging material.")
            elif accuracy >= 0.7:
                insights.append("Good performance. Continue with current difficulty level.")
            elif accuracy >= 0.5:
                insights.append("Moderate performance. Consider reviewing fundamentals.")
            else:
                insights.append("Low performance. Recommend returning to basics.")
        
        # Learning gains insight
        if session.learning_gains:
            avg_gain = sum(session.learning_gains.values()) / len(session.learning_gains)
            if avg_gain > 0.1:
                insights.append("Strong learning gains detected in this session.")
            elif avg_gain > 0.05:
                insights.append("Moderate learning progress achieved.")
            else:
                insights.append("Limited learning gains. Consider changing approach.")
        
        # Duration insight
        if session.duration_seconds > 0:
            items_per_minute = len(session.items_reviewed) / (session.duration_seconds / 60)
            if items_per_minute > 2:
                insights.append("Fast pace - ensure comprehension is maintained.")
            elif items_per_minute < 0.5:
                insights.append("Slow pace - consider increasing review speed.")
        
        return insights
    
    async def _analyze_recent_performance(
        self,
        objective_id: str,
        recent_performance: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Analyze recent performance data."""
        if not recent_performance:
            return {'trend': 'insufficient_data'}
        
        # Calculate trends
        recent_accuracy = sum(p.get('accuracy', 0) for p in recent_performance[-5:]) / min(5, len(recent_performance))
        older_accuracy = sum(p.get('accuracy', 0) for p in recent_performance[-10:-5]) / max(1, min(5, len(recent_performance) - 5))
        
        trend = 'stable'
        if recent_accuracy > older_accuracy + 0.1:
            trend = 'improving'
        elif recent_accuracy < older_accuracy - 0.1:
            trend = 'declining'
        
        return {
            'trend': trend,
            'recent_accuracy': recent_accuracy,
            'older_accuracy': older_accuracy,
            'performance_variance': self._calculate_variance([p.get('accuracy', 0) for p in recent_performance])
        }
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if not values:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance
    
    async def _check_optimization(self) -> None:
        """Check if learning optimization is needed."""
        # Optimize every hour or after many sessions
        if (datetime.now() - self._last_optimization > timedelta(hours=1) or
            len(self._sessions) % 50 == 0):
            await self.optimize_learning_schedule()