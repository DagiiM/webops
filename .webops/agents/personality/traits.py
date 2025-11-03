"""
Personality Traits Module

Implements the Big Five personality model for AI agents,
providing human-like personality characteristics.
"""

import json
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class PersonalityType(Enum):
    """Predefined personality types based on Big Five combinations."""
    
    GUARDIAN = "guardian"          # High C, Low O, Low N
    INNOVATOR = "innovator"        # High O, High E, Low N
    ANALYST = "analyst"            # High O, High C, Low E
    DIPLOMAT = "diplomat"         # High A, High E, Low N
    PERFECTIONIST = "perfectionist" # High C, Low O, High N
    EXPLORER = "explorer"          # High O, High E, High N
    STABILIZER = "stabilizer"      # Low O, High C, Low N
    VISIONARY = "visionary"        # High O, High E, High A


@dataclass
class PersonalityProfile:
    """
    Agent personality based on Big Five model.
    
    The Big Five personality traits:
    - Openness: Creative vs. Conventional (0.0 to 1.0)
    - Conscientiousness: Organized vs. Spontaneous (0.0 to 1.0)
    - Extraversion: Social vs. Reserved (0.0 to 1.0)
    - Agreeableness: Cooperative vs. Competitive (0.0 to 1.0)
    - Neuroticism: Sensitive vs. Resilient (0.0 to 1.0)
    """
    
    openness: float = 0.5          # Creative vs. Conventional
    conscientiousness: float = 0.5  # Organized vs. Spontaneous
    extraversion: float = 0.5       # Social vs. Reserved
    agreeableness: float = 0.5      # Cooperative vs. Competitive
    neuroticism: float = 0.5        # Sensitive vs. Resilient
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: str = "1.0.0"
    
    def __post_init__(self):
        """Validate personality trait values."""
        for trait_name, value in asdict(self).items():
            if trait_name in ['openness', 'conscientiousness', 'extraversion', 
                           'agreeableness', 'neuroticism']:
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"Personality trait {trait_name} must be between 0.0 and 1.0")
    
    @classmethod
    def from_type(cls, personality_type: PersonalityType) -> 'PersonalityProfile':
        """Create personality profile from predefined type."""
        
        profiles = {
            PersonalityType.GUARDIAN: cls(
                openness=0.2,
                conscientiousness=0.9,
                extraversion=0.3,
                agreeableness=0.7,
                neuroticism=0.2
            ),
            PersonalityType.INNOVATOR: cls(
                openness=0.9,
                conscientiousness=0.6,
                extraversion=0.8,
                agreeableness=0.6,
                neuroticism=0.3
            ),
            PersonalityType.ANALYST: cls(
                openness=0.8,
                conscientiousness=0.9,
                extraversion=0.2,
                agreeableness=0.4,
                neuroticism=0.3
            ),
            PersonalityType.DIPLOMAT: cls(
                openness=0.6,
                conscientiousness=0.7,
                extraversion=0.8,
                agreeableness=0.9,
                neuroticism=0.2
            ),
            PersonalityType.PERFECTIONIST: cls(
                openness=0.3,
                conscientiousness=0.95,
                extraversion=0.4,
                agreeableness=0.5,
                neuroticism=0.7
            ),
            PersonalityType.EXPLORER: cls(
                openness=0.9,
                conscientiousness=0.5,
                extraversion=0.9,
                agreeableness=0.6,
                neuroticism=0.6
            ),
            PersonalityType.STABILIZER: cls(
                openness=0.2,
                conscientiousness=0.9,
                extraversion=0.3,
                agreeableness=0.8,
                neuroticism=0.1
            ),
            PersonalityType.VISIONARY: cls(
                openness=0.9,
                conscientiousness=0.7,
                extraversion=0.8,
                agreeableness=0.8,
                neuroticism=0.4
            )
        }
        
        return profiles.get(personality_type, cls())
    
    @classmethod
    def random(cls) -> 'PersonalityProfile':
        """Generate a random personality profile."""
        import random
        return cls(
            openness=random.random(),
            conscientiousness=random.random(),
            extraversion=random.random(),
            agreeableness=random.random(),
            neuroticism=random.random()
        )
    
    @classmethod
    def balanced(cls) -> 'PersonalityProfile':
        """Create a balanced personality profile."""
        return cls(
            openness=0.5,
            conscientiousness=0.5,
            extraversion=0.5,
            agreeableness=0.5,
            neuroticism=0.5
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert personality profile to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonalityProfile':
        """Create personality profile from dictionary."""
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert personality profile to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PersonalityProfile':
        """Create personality profile from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def similarity(self, other: 'PersonalityProfile') -> float:
        """
        Calculate similarity with another personality profile.
        
        Uses Euclidean distance normalized to 0-1 range.
        
        Args:
            other: Another personality profile
            
        Returns:
            Similarity score (0.0 to 1.0, where 1.0 is identical)
        """
        traits = ['openness', 'conscientiousness', 'extraversion', 
                 'agreeableness', 'neuroticism']
        
        distance = math.sqrt(sum(
            (getattr(self, trait) - getattr(other, trait)) ** 2 
            for trait in traits
        ))
        
        # Normalize to 0-1 range (max distance is sqrt(5))
        return 1.0 - (distance / math.sqrt(5))
    
    def distance(self, other: 'PersonalityProfile') -> float:
        """
        Calculate Euclidean distance to another personality profile.
        
        Args:
            other: Another personality profile
            
        Returns:
            Distance (0.0 to sqrt(5))
        """
        traits = ['openness', 'conscientiousness', 'extraversion', 
                 'agreeableness', 'neuroticism']
        
        return math.sqrt(sum(
            (getattr(self, trait) - getattr(other, trait)) ** 2 
            for trait in traits
        ))
    
    def blend(self, other: 'PersonalityProfile', weight: float = 0.5) -> 'PersonalityProfile':
        """
        Blend with another personality profile.
        
        Args:
            other: Another personality profile
            weight: Weight for blending (0.0 = self, 1.0 = other)
            
        Returns:
            Blended personality profile
        """
        weight = max(0.0, min(1.0, weight))
        
        return PersonalityProfile(
            openness=self.openness * (1 - weight) + other.openness * weight,
            conscientiousness=self.conscientiousness * (1 - weight) + other.conscientiousness * weight,
            extraversion=self.extraversion * (1 - weight) + other.extraversion * weight,
            agreeableness=self.agreeableness * (1 - weight) + other.agreeableness * weight,
            neuroticism=self.neuroticism * (1 - weight) + other.neuroticism * weight
        )
    
    def mutate(self, mutation_rate: float = 0.1) -> 'PersonalityProfile':
        """
        Apply random mutation to personality traits.
        
        Args:
            mutation_rate: Maximum mutation amount (0.0 to 1.0)
            
        Returns:
            Mutated personality profile
        """
        import random
        
        def mutate_trait(value: float) -> float:
            mutation = (random.random() - 0.5) * 2 * mutation_rate
            return max(0.0, min(1.0, value + mutation))
        
        return PersonalityProfile(
            openness=mutate_trait(self.openness),
            conscientiousness=mutate_trait(self.conscientiousness),
            extraversion=mutate_trait(self.extraversion),
            agreeableness=mutate_trait(self.agreeableness),
            neuroticism=mutate_trait(self.neuroticism)
        )
    
    def get_dominant_traits(self, threshold: float = 0.7) -> List[str]:
        """
        Get dominant personality traits above threshold.
        
        Args:
            threshold: Threshold for dominance (0.0 to 1.0)
            
        Returns:
            List of dominant trait names
        """
        traits = []
        
        if self.openness >= threshold:
            traits.append("open")
        if self.conscientiousness >= threshold:
            traits.append("conscientious")
        if self.extraversion >= threshold:
            traits.append("extraverted")
        if self.agreeableness >= threshold:
            traits.append("agreeable")
        if self.neuroticism >= threshold:
            traits.append("neurotic")
        
        return traits
    
    def get_personality_description(self) -> str:
        """Get human-readable personality description."""
        descriptions = []
        
        # Openness
        if self.openness > 0.7:
            descriptions.append("creative and curious")
        elif self.openness < 0.3:
            descriptions.append("conventional and practical")
        
        # Conscientiousness
        if self.conscientiousness > 0.7:
            descriptions.append("organized and reliable")
        elif self.conscientiousness < 0.3:
            descriptions.append("flexible and spontaneous")
        
        # Extraversion
        if self.extraversion > 0.7:
            descriptions.append("outgoing and energetic")
        elif self.extraversion < 0.3:
            descriptions.append("reserved and thoughtful")
        
        # Agreeableness
        if self.agreeableness > 0.7:
            descriptions.append("cooperative and trusting")
        elif self.agreeableness < 0.3:
            descriptions.append("competitive and critical")
        
        # Neuroticism
        if self.neuroticism > 0.7:
            descriptions.append("sensitive and reactive")
        elif self.neuroticism < 0.3:
            descriptions.append("calm and resilient")
        
        if not descriptions:
            return "balanced and moderate"
        
        return ", ".join(descriptions[:-1]) + " and " + descriptions[-1]
    
    def influence_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply personality influence to decision making.
        
        Args:
            decision: Decision to influence
            
        Returns:
            Personality-influenced decision
        """
        influenced = decision.copy()
        
        # Openness influences creativity and risk-taking
        if self.openness > 0.7:
            influenced['creativity_boost'] = 0.3
            influenced['risk_tolerance'] *= 1.2
        elif self.openness < 0.3:
            influenced['creativity_boost'] = -0.2
            influenced['risk_tolerance'] *= 0.8
        
        # Conscientiousness influences planning and thoroughness
        if self.conscientiousness > 0.7:
            influenced['planning_detail'] = 1.3
            influenced['thoroughness'] = 1.2
        elif self.conscientiousness < 0.3:
            influenced['planning_detail'] = 0.8
            influenced['thoroughness'] = 0.9
        
        # Extraversion influences social interaction and confidence
        if self.extraversion > 0.7:
            influenced['social_confidence'] = 1.3
            influenced['communication_style'] = 'assertive'
        elif self.extraversion < 0.3:
            influenced['social_confidence'] = 0.8
            influenced['communication_style'] = 'reserved'
        
        # Agreeableness influences cooperation and conflict resolution
        if self.agreeableness > 0.7:
            influenced['cooperation_tendency'] = 1.3
            influenced['conflict_avoidance'] = 1.2
        elif self.agreeableness < 0.3:
            influenced['cooperation_tendency'] = 0.8
            influenced['conflict_approach'] = 'direct'
        
        # Neuroticism influences emotional responses
        if self.neuroticism > 0.7:
            influenced['emotional_sensitivity'] = 1.3
            influenced['stress_response'] = 'high'
        elif self.neuroticism < 0.3:
            influenced['emotional_sensitivity'] = 0.8
            influenced['stress_response'] = 'low'
        
        return influenced
    
    def affect_communication(self, message: str) -> str:
        """
        Apply personality to communication style.
        
        Args:
            message: Original message
            
        Returns:
            Personality-styled message
        """
        styled_message = message
        
        # Openness affects language creativity
        if self.openness > 0.7:
            styled_message = self._add_creative_language(styled_message)
        elif self.openness < 0.3:
            styled_message = self._simplify_language(styled_message)
        
        # Conscientiousness affects structure and detail
        if self.conscientiousness > 0.7:
            styled_message = self._add_structure(styled_message)
        elif self.conscientiousness < 0.3:
            styled_message = self._make_casual(styled_message)
        
        # Extraversion affects enthusiasm and expressiveness
        if self.extraversion > 0.7:
            styled_message = self._add_enthusiasm(styled_message)
        elif self.extraversion < 0.3:
            styled_message = self._make_reserved(styled_message)
        
        # Agreeableness affects politeness and tone
        if self.agreeableness > 0.7:
            styled_message = self._add_politeness(styled_message)
        elif self.agreeableness < 0.3:
            styled_message = self._make_direct(styled_message)
        
        return styled_message
    
    def _add_creative_language(self, message: str) -> str:
        """Add creative and expressive language."""
        creative_words = ["innovative", "fascinating", "exciting", "imaginative"]
        # Simple implementation - in practice would use NLP
        return message.replace("good", "innovative")
    
    def _simplify_language(self, message: str) -> str:
        """Simplify language to be more direct."""
        return message.replace("consequently", "so").replace("therefore", "so")
    
    def _add_structure(self, message: str) -> str:
        """Add structure and organization to message."""
        if not message.startswith(("1.", "•", "-")):
            return f"1. {message}"
        return message
    
    def _make_casual(self, message: str) -> str:
        """Make message more casual."""
        return message.replace("therefore", "so").replace("consequently", "so")
    
    def _add_enthusiasm(self, message: str) -> str:
        """Add enthusiasm and energy to message."""
        return message + "!" if not message.endswith("!") else message
    
    def _make_reserved(self, message: str) -> str:
        """Make message more reserved."""
        return message.rstrip("!") + "."
    
    def _add_politeness(self, message: str) -> str:
        """Add politeness to message."""
        if not any(word in message.lower() for word in ["please", "thank", "kindly"]):
            return f"Please note that {message.lower()}"
        return message
    
    def _make_direct(self, message: str) -> str:
        """Make message more direct."""
        return message.replace("Could you please", "Please").replace("Would you mind", "Please")
    
    def calculate_adjustments(self, experiences: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate personality adjustments based on experiences.
        
        Args:
            experiences: List of recent experiences
            
        Returns:
            Dictionary of trait adjustments
        """
        if not experiences:
            return {}
        
        adjustments = {
            'openness': 0.0,
            'conscientiousness': 0.0,
            'extraversion': 0.0,
            'agreeableness': 0.0,
            'neuroticism': 0.0
        }
        
        # Analyze experiences for patterns
        for exp in experiences:
            success = exp.get('success', False)
            social = exp.get('social_interaction', False)
            creative = exp.get('creative_task', False)
            stressful = exp.get('stressful', False)
            
            # Adjust based on outcomes
            if success and creative:
                adjustments['openness'] += 0.01
            if success and not stressful:
                adjustments['neuroticism'] -= 0.01
            if social and success:
                adjustments['extraversion'] += 0.01
            if not social and success:
                adjustments['extraversion'] -= 0.005
        
        # Normalize adjustments
        for trait in adjustments:
            adjustments[trait] = max(-0.1, min(0.1, adjustments[trait]))
        
        return adjustments
    
    def apply_adjustments(self, adjustments: Dict[str, float]) -> None:
        """
        Apply personality adjustments.
        
        Args:
            adjustments: Dictionary of trait adjustments
        """
        for trait, adjustment in adjustments.items():
            if hasattr(self, trait):
                current_value = getattr(self, trait)
                new_value = max(0.0, min(1.0, current_value + adjustment))
                setattr(self, trait, new_value)