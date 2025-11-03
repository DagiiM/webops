"""
Emotional State Management Module

Implements emotional state tracking and management for AI agents,
providing human-like emotional responses and mood variations.
"""

import math
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta

from .traits import PersonalityProfile


class Emotion(Enum):
    """Basic emotions based on Plutchik's model."""
    
    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class Mood(Enum):
    """Mood states derived from emotion combinations."""
    
    HAPPY = "happy"           # Joy + Trust
    LOVING = "loving"         # Joy + Trust + Anticipation
    OPTIMISTIC = "optimistic"   # Joy + Anticipation
    DISAPPOINTED = "disappointed"  # Sadness + Surprise
    FEARFUL = "fearful"       # Fear + Surprise
    ANXIOUS = "anxious"        # Fear + Anticipation
    FRUSTRATED = "frustrated"  # Anger + Surprise
    HOSTILE = "hostile"        # Anger + Disgust
    GUILTY = "guilty"          # Sadness + Disgust
    BORED = "bored"            # Sadness + Disgust + Surprise
    DEPRESSED = "depressed"     # Sadness + Disgust + Fear
    EXCITED = "excited"        # Joy + Surprise + Anticipation
    CONFIDENT = "confident"     # Joy + Trust + Anticipation
    CONTENT = "content"         # Joy + Trust
    LONELY = "lonely"         # Sadness + Fear
    HURT = "hurt"             # Sadness + Anger
    JEALOUS = "jealous"       # Anger + Fear + Disgust
    PROUD = "proud"           # Joy + Anger + Trust


@dataclass
class EmotionalState:
    """
    Manages agent emotional state and responses.
    
    Tracks eight basic emotions and derives mood states
    from emotion combinations.
    """
    
    # Basic emotion intensities (0.0 to 1.0)
    joy: float = 0.5
    trust: float = 0.5
    fear: float = 0.2
    surprise: float = 0.3
    sadness: float = 0.2
    disgust: float = 0.1
    anger: float = 0.1
    anticipation: float = 0.5
    
    # Emotional state metadata
    last_updated: Optional[datetime] = None
    emotion_history: List[Dict[str, Any]] = field(default_factory=list)
    mood_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Personality influence
    personality: Optional[PersonalityProfile] = None
    
    # Emotional regulation
    emotional_stability: float = 0.7  # How quickly emotions change
    emotional_intensity: float = 0.8    # How strong emotions feel
    
    def __post_init__(self):
        """Initialize emotional state."""
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    def set_personality(self, personality: PersonalityProfile) -> None:
        """Set personality profile for emotional influence."""
        self.personality = personality
        
        # Adjust emotional stability based on neuroticism
        self.emotional_stability = 1.0 - (personality.neuroticism * 0.5)
        
        # Adjust emotional intensity based on extraversion
        self.emotional_intensity = 0.5 + (personality.extraversion * 0.5)
    
    def get_current_state(self) -> Dict[str, float]:
        """Get current emotional state as dictionary."""
        return {
            'joy': self.joy,
            'trust': self.trust,
            'fear': self.fear,
            'surprise': self.surprise,
            'sadness': self.sadness,
            'disgust': self.disgust,
            'anger': self.anger,
            'anticipation': self.anticipation
        }
    
    def get_mood(self) -> Mood:
        """Determine current mood based on emotion combination."""
        emotions = self.get_current_state()
        
        # Calculate mood scores based on emotion combinations
        mood_scores = {
            Mood.HAPPY: emotions['joy'] * emotions['trust'],
            Mood.LOVING: emotions['joy'] * emotions['trust'] * emotions['anticipation'],
            Mood.OPTIMISTIC: emotions['joy'] * emotions['anticipation'],
            Mood.DISAPPOINTED: emotions['sadness'] * emotions['surprise'],
            Mood.FEARFUL: emotions['fear'] * emotions['surprise'],
            Mood.ANXIOUS: emotions['fear'] * emotions['anticipation'],
            Mood.FRUSTRATED: emotions['anger'] * emotions['surprise'],
            Mood.HOSTILE: emotions['anger'] * emotions['disgust'],
            Mood.GUILTY: emotions['sadness'] * emotions['disgust'],
            Mood.BORED: emotions['sadness'] * emotions['disgust'] * emotions['surprise'],
            Mood.DEPRESSED: emotions['sadness'] * emotions['disgust'] * emotions['fear'],
            Mood.EXCITED: emotions['joy'] * emotions['surprise'] * emotions['anticipation'],
            Mood.CONFIDENT: emotions['joy'] * emotions['trust'] * emotions['anticipation'],
            Mood.CONTENT: emotions['joy'] * emotions['trust'],
            Mood.LONELY: emotions['sadness'] * emotions['fear'],
            Mood.HURT: emotions['sadness'] * emotions['anger'],
            Mood.JEALOUS: emotions['anger'] * emotions['fear'] * emotions['disgust'],
            Mood.PROUD: emotions['joy'] * emotions['anger'] * emotions['trust']
        }
        
        # Return mood with highest score
        return max(mood_scores, key=mood_scores.get)
    
    def get_mood_score(self) -> float:
        """
        Get overall mood score (-1.0 to 1.0).
        
        Positive emotions (joy, trust, anticipation) contribute positively
        Negative emotions (fear, sadness, disgust, anger) contribute negatively
        """
        positive = (self.joy + self.trust + self.anticipation) / 3
        negative = (self.fear + self.sadness + self.disgust + self.anger) / 4
        
        return (positive - negative) * self.emotional_intensity
    
    def get_emotional_balance(self) -> Dict[str, float]:
        """Get emotional balance metrics."""
        emotions = self.get_current_state()
        
        return {
            'positive_ratio': (emotions['joy'] + emotions['trust'] + emotions['anticipation']) / 3,
            'negative_ratio': (emotions['fear'] + emotions['sadness'] + emotions['disgust'] + emotions['anger']) / 4,
            'arousal': (emotions['surprise'] + emotions['anticipation'] + emotions['fear'] + emotions['anger']) / 4,
            'valence': self.get_mood_score(),
            'dominance': (emotions['anger'] + emotions['trust'] - emotions['fear'] - emotions['sadness']) / 2
        }
    
    async def update_from_stimulus(self, stimulus: Dict[str, Any]) -> None:
        """
        Update emotional state based on external stimulus.
        
        Args:
            stimulus: External stimulus information
        """
        stimulus_type = stimulus.get('type', 'neutral')
        intensity = stimulus.get('intensity', 0.5)
        
        # Map stimulus types to emotion changes
        emotion_changes = {
            'success': {'joy': 0.3, 'trust': 0.2, 'anticipation': 0.1},
            'failure': {'sadness': 0.3, 'anger': 0.2, 'disgust': 0.1},
            'threat': {'fear': 0.4, 'anger': 0.2, 'surprise': 0.2},
            'surprise': {'surprise': 0.5, 'anticipation': 0.2},
            'praise': {'joy': 0.4, 'trust': 0.3, 'pride': 0.2},
            'criticism': {'sadness': 0.3, 'anger': 0.2, 'disgust': 0.1},
            'uncertainty': {'fear': 0.3, 'anticipation': 0.3, 'surprise': 0.2},
            'achievement': {'joy': 0.4, 'pride': 0.3, 'trust': 0.2},
            'loss': {'sadness': 0.4, 'anger': 0.2, 'disgust': 0.1},
            'social_rejection': {'sadness': 0.3, 'anger': 0.2, 'fear': 0.2},
            'social_acceptance': {'joy': 0.3, 'trust': 0.3, 'anticipation': 0.2}
        }
        
        # Get emotion changes for stimulus type
        changes = emotion_changes.get(stimulus_type, {})
        
        # Apply intensity and personality influence
        for emotion, change in changes.items():
            if emotion in ['joy', 'trust', 'fear', 'surprise', 'sadness', 'disgust', 'anger', 'anticipation']:
                # Apply intensity
                adjusted_change = change * intensity * self.emotional_intensity
                
                # Apply personality influence
                if self.personality:
                    adjusted_change = self._apply_personality_influence(emotion, adjusted_change)
                
                # Apply emotional stability (dampening)
                adjusted_change *= self.emotional_stability
                
                # Update emotion
                current_value = getattr(self, emotion)
                new_value = max(0.0, min(1.0, current_value + adjusted_change))
                setattr(self, emotion, new_value)
        
        # Update timestamp
        self.last_updated = datetime.now()
        
        # Store in history
        self.emotion_history.append({
            'timestamp': self.last_updated,
            'stimulus': stimulus,
            'state': self.get_current_state(),
            'mood': self.get_mood().value,
            'mood_score': self.get_mood_score()
        })
        
        # Limit history size
        if len(self.emotion_history) > 1000:
            self.emotion_history = self.emotion_history[-500:]
    
    async def update_from_interaction(self, message: str, response: str) -> None:
        """
        Update emotional state based on social interaction.
        
        Args:
            message: Incoming message
            response: Agent's response
        """
        # Analyze sentiment of interaction
        sentiment = self._analyze_sentiment(message)
        response_sentiment = self._analyze_sentiment(response)
        
        # Update emotions based on interaction
        if sentiment > 0.5:  # Positive message
            await self.update_from_stimulus({
                'type': 'social_acceptance',
                'intensity': sentiment
            })
        elif sentiment < -0.5:  # Negative message
            await self.update_from_stimulus({
                'type': 'social_rejection',
                'intensity': abs(sentiment)
            })
        
        # Update based on response confidence
        if response_sentiment > 0.3:
            self.trust = min(1.0, self.trust + 0.05)
    
    async def update_from_results(self, success_rate: float) -> None:
        """
        Update emotional state based on task results.
        
        Args:
            success_rate: Success rate (0.0 to 1.0)
        """
        if success_rate > 0.8:
            await self.update_from_stimulus({
                'type': 'success',
                'intensity': success_rate
            })
        elif success_rate < 0.3:
            await self.update_from_stimulus({
                'type': 'failure',
                'intensity': 1.0 - success_rate
            })
    
    def get_recent_changes(self, minutes: int = 10) -> Dict[str, float]:
        """
        Get recent emotional changes.
        
        Args:
            minutes: Time window to look back
            
        Returns:
            Dictionary of emotion changes
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        # Find first state in time window
        old_state = None
        for entry in reversed(self.emotion_history):
            if entry['timestamp'] < cutoff_time:
                old_state = entry['state']
                break
        
        if old_state is None:
            return {}
        
        current_state = self.get_current_state()
        changes = {}
        
        for emotion in current_state:
            changes[emotion] = current_state[emotion] - old_state.get(emotion, 0.5)
        
        return changes
    
    def _apply_personality_influence(self, emotion: str, change: float) -> float:
        """Apply personality influence to emotion change."""
        if not self.personality:
            return change
        
        # Neuroticism amplifies negative emotions
        if emotion in ['fear', 'sadness', 'disgust', 'anger']:
            change *= (1.0 + self.personality.neuroticism * 0.5)
        
        # Extraversion amplifies positive emotions
        if emotion in ['joy', 'trust', 'anticipation']:
            change *= (1.0 + self.personality.extraversion * 0.3)
        
        # Agreeableness reduces anger
        if emotion == 'anger':
            change *= (1.0 - self.personality.agreeableness * 0.3)
        
        # Openness affects surprise response
        if emotion == 'surprise':
            change *= (1.0 + self.personality.openness * 0.2)
        
        return change
    
    def _analyze_sentiment(self, text: str) -> float:
        """
        Simple sentiment analysis.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment score (-1.0 to 1.0)
        """
        # Simple keyword-based sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'awesome', 'fantastic', 'love', 'happy', 'wonderful']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'angry', 'sad', 'disappointed', 'wrong']
        
        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        total_words = len(words)
        if total_words == 0:
            return 0.0
        
        sentiment = (positive_count - negative_count) / total_words
        return max(-1.0, min(1.0, sentiment))
    
    def decay_emotions(self, decay_rate: float = 0.01) -> None:
        """
        Apply emotional decay over time.
        
        Args:
            decay_rate: Rate of emotional decay
        """
        # Decay all emotions toward neutral (0.5)
        emotions = ['joy', 'trust', 'fear', 'surprise', 'sadness', 'disgust', 'anger', 'anticipation']
        
        for emotion in emotions:
            current_value = getattr(self, emotion)
            neutral_value = 0.5
            
            # Apply decay
            new_value = current_value + (neutral_value - current_value) * decay_rate
            setattr(self, emotion, new_value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert emotional state to dictionary."""
        return {
            'current_state': self.get_current_state(),
            'mood': self.get_mood().value,
            'mood_score': self.get_mood_score(),
            'emotional_balance': self.get_emotional_balance(),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'emotional_stability': self.emotional_stability,
            'emotional_intensity': self.emotional_intensity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmotionalState':
        """Create emotional state from dictionary."""
        state = cls()
        
        if 'current_state' in data:
            for emotion, value in data['current_state'].items():
                if hasattr(state, emotion):
                    setattr(state, emotion, value)
        
        if 'emotional_stability' in data:
            state.emotional_stability = data['emotional_stability']
        
        if 'emotional_intensity' in data:
            state.emotional_intensity = data['emotional_intensity']
        
        if 'last_updated' in data and data['last_updated']:
            state.last_updated = datetime.fromisoformat(data['last_updated'])
        
        return state
    
    def to_json(self) -> str:
        """Convert emotional state to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EmotionalState':
        """Create emotional state from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)