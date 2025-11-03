"""
Personality Influence Module

Manages how the AI agent's personality affects decision making and behavior.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import math


class PersonalityTrait(Enum):
    """Big Five personality traits."""
    
    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"


class DecisionMakingStyle(Enum):
    """Different decision-making styles influenced by personality."""
    
    ANALYTICAL = "analytical"
    INTUITIVE = "intuitive"
    DEPENDENT = "dependent"
    SPONTANEOUS = "spontaneous"
    AVOIDANT = "avoidant"
    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"
    EMOTIONAL = "emotional"


class SocialOrientation(Enum):
    """Social orientation influenced by personality."""
    
    INDIVIDUALISTIC = "individualistic"
    COLLECTIVISTIC = "collectivistic"
    COMPETITIVE = "competitive"
    COOPERATIVE = "cooperative"
    HIERARCHICAL = "hierarchical"
    Egalitarian = "egalitarian"


@dataclass
class PersonalityProfile:
    """The agent's personality profile."""
    
    openness: float = 0.5  # 0.0 to 1.0
    conscientiousness: float = 0.5  # 0.0 to 1.0
    extraversion: float = 0.5  # 0.0 to 1.0
    agreeableness: float = 0.5  # 0.0 to 1.0
    neuroticism: float = 0.5  # 0.0 to 1.0
    decision_making_style: DecisionMakingStyle = DecisionMakingStyle.ANALYTICAL
    social_orientation: SocialOrientation = SocialOrientation.COLLECTIVISTIC
    risk_tolerance: float = 0.5  # 0.0 to 1.0
    creativity_level: float = 0.5  # 0.0 to 1.0
    assertiveness: float = 0.5  # 0.0 to 1.0
    empathy_level: float = 0.5  # 0.0 to 1.0
    adaptability: float = 0.5  # 0.0 to 1.0
    patience: float = 0.5  # 0.0 to 1.0
    perfectionism: float = 0.5  # 0.0 to 1.0
    optimism: float = 0.5  # 0.0 to 1.0
    need_for_cognition: float = 0.5  # 0.0 to 1.0 (desire for complex thinking)
    need_for_closure: float = 0.5  # 0.0 to 1.0 (need for definite answers)
    core_values: List[str] = field(default_factory=list)
    behavioral_patterns: List[Dict[str, Any]] = field(default_factory=list)
    situation_preferences: Dict[str, float] = field(default_factory=dict)  # situation_type: preference_score
    interaction_preferences: Dict[str, float] = field(default_factory=dict)  # interaction_type: preference_score
    stress_responses: List[Dict[str, Any]] = field(default_factory=list)
    growth_areas: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        data = asdict(self)
        data['decision_making_style'] = self.decision_making_style.value
        data['social_orientation'] = self.social_orientation.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonalityProfile':
        """Create profile from dictionary."""
        if 'decision_making_style' in data and isinstance(data['decision_making_style'], str):
            data['decision_making_style'] = DecisionMakingStyle(data['decision_making_style'])
        if 'social_orientation' in data and isinstance(data['social_orientation'], str):
            data['social_orientation'] = SocialOrientation(data['social_orientation'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)
    
    def calculate_composite_scores(self) -> Dict[str, float]:
        """Calculate composite personality scores."""
        return {
            'openness': self.openness,
            'conscientiousness': self.conscientiousness,
            'extraversion': self.extraversion,
            'agreeableness': self.agreeableness,
            'neuroticism': self.neuroticism,
            'emotional_stability': 1.0 - self.neuroticism,  # Inverse of neuroticism
            'planning_orientation': self.conscientiousness,
            'social_energy': self.extraversion,
            'cooperation_tendency': self.agreeableness,
            'risk_appetite': self.risk_tolerance,
            'innovation_tendency': self.openness,
            'empathy_score': self.empathy_level,
            'assertiveness_score': self.assertiveness
        }


@dataclass
class DecisionContext:
    """Context for a decision influenced by personality."""
    
    decision_type: str = ""
    options: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    timeline: Optional[Dict[str, datetime]] = None  # start: end
    stakeholders: List[str] = field(default_factory=list)
    priority: float = 0.5  # 0.0 to 1.0
    risk_level: float = 0.5  # 0.0 to 1.0
    uncertainty_level: float = 0.5  # 0.0 to 1.0
    social_impact: float = 0.5  # 0.0 to 1.0
    personal_impact: float = 0.5 # 0.0 to 1.0
    cultural_context: str = ""
    previous_decisions: List[str] = field(default_factory=list)
    learning_from_past: List[Dict[str, Any]] = field(default_factory=list)
    current_emotional_state: str = "neutral"
    stress_level: float = 0.0  # 0.0 to 1.0
    cognitive_load: float = 0.0  # 0.0 to 1.0
    time_pressure: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        data = asdict(self)
        if self.timeline:
            timeline_dict = {}
            for key, value in self.timeline.items():
                if isinstance(value, datetime):
                    timeline_dict[key] = value.isoformat()
                else:
                    timeline_dict[key] = value
            data['timeline'] = timeline_dict
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DecisionContext':
        """Create context from dictionary."""
        timeline = data.get('timeline')
        if timeline:
            parsed_timeline = {}
            for key, value in timeline.items():
                if isinstance(value, str):
                    parsed_timeline[key] = datetime.fromisoformat(value)
                else:
                    parsed_timeline[key] = value
            data['timeline'] = parsed_timeline
        return cls(**data)


@dataclass
class PersonalityInfluence:
    """Result of personality influence on a decision."""
    
    personality_trait: PersonalityTrait
    influence_strength: float  # -1.0 to 1.0 (negative = reduces likelihood, positive = increases)
    influence_type: str = "direct"  # direct, indirect, contextual
    affected_aspect: str = ""  # decision_factor, option_preference, etc.
    modifier_value: float = 0.0
    reasoning: str = ""
    confidence: float = 0.5  # 0.0 to 1.0
    temporal_factor: float = 1.0  # How influence changes over time
    context_sensitivity: float = 0.5  # How sensitive to context
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert influence to dictionary."""
        data = asdict(self)
        data['personality_trait'] = self.personality_trait.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersonalityInfluence':
        """Create influence from dictionary."""
        if 'personality_trait' in data and isinstance(data['personality_trait'], str):
            data['personality_trait'] = PersonalityTrait(data['personality_trait'])
        return cls(**data)


class PersonalityInfluenceEngine:
    """Engine that calculates how personality influences decisions."""
    
    def __init__(self, config):
        """Initialize the personality influence engine."""
        self.config = config
        self.logger = logging.getLogger("personality_influence")
        
        # Storage
        self._personality_profile: Optional[PersonalityProfile] = None
        self._decision_history: List[Dict[str, Any]] = []
        self._influence_cache: Dict[str, List[PersonalityInfluence]] = {}
        
        # Influence parameters
        self._trait_influence_weights = self._initialize_trait_weights()
        self._situation_modifiers = self._initialize_situation_modifiers()
        self._cultural_modifiers = self._initialize_cultural_modifiers()
        
        # Statistics
        self._total_decisions_influenced = 0
        self._average_influence_strength = 0.0
        self._influence_by_trait: Dict[PersonalityTrait, List[float]] = {
            trait: [] for trait in PersonalityTrait
        }
        self._last_profile_update = datetime.now()
    
    async def set_personality_profile(self, profile: PersonalityProfile) -> None:
        """Set the agent's personality profile."""
        self._personality_profile = profile
        self._last_profile_update = datetime.now()
        
        self.logger.info(f"Personality profile set with traits: {profile.calculate_composite_scores()}")
    
    async def get_personality_profile(self) -> Optional[PersonalityProfile]:
        """Get the agent's personality profile."""
        return self._personality_profile
    
    async def calculate_personality_influences(
        self,
        decision_context: DecisionContext
    ) -> List[PersonalityInfluence]:
        """Calculate personality influences on a decision."""
        try:
            if not self._personality_profile:
                raise ValueError("Personality profile not set")
            
            # Check cache
            cache_key = f"{decision_context.decision_type}:{decision_context.priority}:{decision_context.risk_level}"
            if cache_key in self._influence_cache:
                cached_influences = self._influence_cache[cache_key]
                # Update temporal factors
                for influence in cached_influences:
                    influence.temporal_factor *= 0.99  # Slight decay over time
                return cached_influences
            
            influences = []
            
            # Calculate influence of each trait
            for trait in PersonalityTrait:
                influence = await self._calculate_trait_influence(
                    trait, decision_context
                )
                if influence:
                    influences.append(influence)
            
            # Apply situation modifiers
            influences = await self._apply_situation_modifiers(
                influences, decision_context
            )
            
            # Apply cultural context
            influences = await self._apply_cultural_modifiers(
                influences, decision_context
            )
            
            # Apply current state modifiers
            influences = await self._apply_current_state_modifiers(
                influences, decision_context
            )
            
            # Cache influences
            self._influence_cache[cache_key] = influences
            
            # Update statistics
            self._update_influence_stats(influences)
            
            self.logger.debug(f"Calculated {len(influences)} personality influences for decision: {decision_context.decision_type}")
            return influences
            
        except Exception as e:
            self.logger.error(f"Error calculating personality influences: {e}")
            return []
    
    async def modify_decision_options(
        self,
        options: List[Dict[str, Any]],
        decision_context: DecisionContext
    ) -> List[Dict[str, Any]]:
        """Modify decision options based on personality influences."""
        try:
            influences = await self.calculate_personality_influences(decision_context)
            
            modified_options = []
            for option in options:
                modified_option = option.copy()
                
                # Apply personality-based modifications
                for influence in influences:
                    modification = await self._apply_influence_to_option(
                        modified_option, influence, decision_context
                    )
                    modified_option = modification
                
                modified_options.append(modified_option)
            
            return modified_options
            
        except Exception as e:
            self.logger.error(f"Error modifying decision options: {e}")
            return options
    
    async def predict_decision_style(
        self,
        decision_context: DecisionContext
    ) -> DecisionMakingStyle:
        """Predict the agent's likely decision-making style for a context."""
        try:
            if not self._personality_profile:
                return DecisionMakingStyle.ANALYTICAL
            
            # Calculate style probabilities based on traits and context
            style_scores = {}
            
            for style in DecisionMakingStyle:
                score = await self._calculate_style_probability(
                    style, decision_context
                )
                style_scores[style] = score
            
            # Return style with highest probability
            predicted_style = max(style_scores, key=style_scores.get)
            
            return predicted_style
            
        except Exception as e:
            self.logger.error(f"Error predicting decision style: {e}")
            return DecisionMakingStyle.ANALYTICAL
    
    async def adapt_personality_to_context(
        self,
        decision_context: DecisionContext
    ) -> Dict[str, float]:
        """Adapt personality traits based on the current context."""
        try:
            if not self._personality_profile:
                return {}
            
            adaptations = {}
            profile = self._personality_profile
            
            # Adapt based on stress level
            stress_factor = decision_context.stress_level
            adaptations['neuroticism'] = profile.neuroticism + (stress_factor * 0.2)
            
            # Adapt based on time pressure
            time_pressure_factor = decision_context.time_pressure
            adaptations['conscientiousness'] = max(0.0, min(1.0, profile.conscientiousness - (time_pressure_factor * 0.1)))
            
            # Adapt based on social impact
            social_factor = decision_context.social_impact
            adaptations['agreeableness'] = min(1.0, profile.agreeableness + (social_factor * 0.1))
            
            # Ensure values stay within bounds
            for trait, value in adaptations.items():
                adaptations[trait] = max(0.0, min(1.0, value))
            
            return adaptations
            
        except Exception as e:
            self.logger.error(f"Error adapting personality to context: {e}")
            return {}
    
    async def get_personality_insights(
        self,
        decision_context: DecisionContext
    ) -> Dict[str, Any]:
        """Get insights about how personality affects decision making."""
        try:
            if not self._personality_profile:
                return {'error': 'Personality profile not set'}
            
            influences = await self.calculate_personality_influences(decision_context)
            
            insights = {
                'personality_profile': self._personality_profile.to_dict(),
                'calculated_influences': [inf.to_dict() for inf in influences],
                'predicted_decision_style': (await self.predict_decision_style(decision_context)).value,
                'context_adaptations': await self.adapt_personality_to_context(decision_context),
                'trait_influence_summary': await self._summarize_trait_influences(influences),
                'decision_confidence_factors': await self._calculate_confidence_factors(decision_context),
                'recommendations': await self._generate_recommendations(influences, decision_context)
            }
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting personality insights: {e}")
            return {'error': str(e)}
    
    async def update_personality_from_experience(
        self,
        decision_outcome: Dict[str, Any]
    ) -> None:
        """Update personality based on decision outcomes."""
        try:
            if not self._personality_profile:
                return
            
            # Update based on success/failure
            success = decision_outcome.get('success', False)
            outcome_value = decision_outcome.get('outcome_value', 0.0)
            
            # Adjust traits based on outcomes
            if success:
                # Increase traits that contributed to success
                self._personality_profile.openness = min(1.0, self._personality_profile.openness + 0.01)
                self._personality_profile.conscientiousness = min(1.0, self._personality_profile.conscientiousness + 0.02)
            else:
                # Adjust for failure
                self._personality_profile.neuroticism = min(1.0, self._personality_profile.neuroticism + 0.01)
            
            # Update based on feedback
            feedback = decision_outcome.get('feedback', {})
            if 'positive' in feedback:
                self._personality_profile.agreeableness = min(1.0, self._personality_profile.agreeableness + 0.01)
            elif 'negative' in feedback:
                self._personality_profile.extraversion = max(0.0, self._personality_profile.extraversion - 0.01)
            
            # Update last modified
            self._personality_profile.updated_at = datetime.now()
            
            self.logger.info(f"Updated personality from experience: {decision_outcome.get('decision_id', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error updating personality from experience: {e}")
    
    async def get_influence_statistics(self) -> Dict[str, Any]:
        """Get statistics about personality influences."""
        try:
            stats = {
                'total_decisions_influenced': self._total_decisions_influenced,
                'average_influence_strength': self._average_influence_strength,
                'influence_by_trait': {
                    trait.value: sum(values) / len(values) if values else 0.0
                    for trait, values in self._influence_by_trait.items()
                },
                'trait_distribution': {
                    trait.value: len(values)
                    for trait, values in self._influence_by_trait.items()
                },
                'last_profile_update': self._last_profile_update.isoformat(),
                'cache_size': len(self._influence_cache),
                'decision_history_count': len(self._decision_history)
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting influence statistics: {e}")
            return {}
    
    async def _calculate_trait_influence(
        self,
        trait: PersonalityTrait,
        context: DecisionContext
    ) -> Optional[PersonalityInfluence]:
        """Calculate influence of a specific trait on the decision."""
        if not self._personality_profile:
            return None
        
        # Get trait value
        trait_value = getattr(self._personality_profile, trait.value)
        
        # Calculate base influence strength
        base_strength = 0.0
        
        # Trait-specific calculations
        if trait == PersonalityTrait.OPENNESS:
            # Higher openness increases exploration of options
            base_strength = trait_value * 0.8
            affected_aspect = "option_exploration"
            reasoning = "High openness promotes exploration of novel options"
            
        elif trait == PersonalityTrait.CONSIENTIOUSNESS:
            # Higher conscientiousness increases planning and analysis
            base_strength = trait_value * 0.7
            affected_aspect = "decision_thoroughness"
            reasoning = "High conscientiousness promotes thorough analysis"
            
        elif trait == PersonalityTrait.EXTRAVERSION:
            # Higher extraversion increases social considerations
            base_strength = trait_value * context.social_impact * 0.6
            affected_aspect = "social_consideration"
            reasoning = "High extraversion increases attention to social impact"
            
        elif trait == PersonalityTrait.AGREEABLENESS:
            # Higher agreeableness increases cooperation
            base_strength = trait_value * 0.7
            affected_aspect = "cooperative_tendency"
            reasoning = "High agreeableness promotes cooperative decisions"
            
        elif trait == PersonalityTrait.NEUROTICISM:
            # Higher neuroticism increases risk aversion
            base_strength = -trait_value * 0.6  # Negative because it reduces risk-taking
            affected_aspect = "risk_tolerance"
            reasoning = "High neuroticism reduces risk tolerance"
        
        # Adjust for context
        base_strength *= self._calculate_context_adjustment(context)
        
        # Create influence object
        influence = PersonalityInfluence(
            personality_trait=trait,
            influence_strength=base_strength,
            affected_aspect=affected_aspect,
            modifier_value=base_strength,
            reasoning=reasoning,
            confidence=0.8,  # High confidence in trait-based influences
            temporal_factor=1.0,
            context_sensitivity=0.5
        )
        
        return influence
    
    async def _apply_situation_modifiers(
        self,
        influences: List[PersonalityInfluence],
        context: DecisionContext
    ) -> List[PersonalityInfluence]:
        """Apply situation-specific modifiers to influences."""
        modified_influences = []
        
        for influence in influences:
            modifier = 1.0
            
            # Apply risk level modifier
            if influence.affected_aspect in ["risk_tolerance", "decision_thoroughness"]:
                risk_modifier = 1.0 + (context.risk_level * 0.2)
                modifier *= risk_modifier
            
            # Apply time pressure modifier
            if influence.affected_aspect in ["decision_thoroughness", "option_exploration"]:
                time_modifier = 1.0 - (context.time_pressure * 0.3)
                modifier *= time_modifier
            
            # Apply stress level modifier
            if influence.affected_aspect in ["risk_tolerance", "social_consideration"]:
                stress_modifier = 1.0 - (context.stress_level * 0.15)
                modifier *= stress_modifier
            
            # Apply social impact modifier
            if influence.affected_aspect in ["cooperative_tendency", "social_consideration"]:
                social_modifier = 1.0 + (context.social_impact * 0.25)
                modifier *= social_modifier
            
            # Apply cognitive load modifier
            if influence.affected_aspect in ["decision_thoroughness", "option_exploration"]:
                load_modifier = 1.0 - (context.cognitive_load * 0.2)
                modifier *= load_modifier
            
            # Apply modifier
            modified_influence = influence
            modified_influence.influence_strength *= modifier
            modified_influence.modifier_value *= modifier
            modified_influence.temporal_factor *= modifier
            
            modified_influences.append(modified_influence)
        
        return modified_influences
    
    async def _apply_cultural_modifiers(
        self,
        influences: List[PersonalityInfluence],
        context: DecisionContext
    ) -> List[PersonalityInfluence]:
        """Apply cultural context modifiers to influences."""
        # In a real implementation, this would use cultural context
        # For now, just return the influences as-is
        return influences
    
    async def _apply_current_state_modifiers(
        self,
        influences: List[PersonalityInfluence],
        context: DecisionContext
    ) -> List[PersonalityInfluence]:
        """Apply current state modifiers to influences."""
        modified_influences = []
        
        for influence in influences:
            modifier = 1.0
            
            # Apply emotional state modifier
            if context.current_emotional_state == "anxious":
                modifier *= 0.8  # Reduce influence when anxious
            elif context.current_emotional_state == "excited":
                modifier *= 1.2  # Increase influence when excited
            elif context.current_emotional_state == "calm":
                modifier *= 1.1  # Slight increase when calm
            
            # Apply modifier
            modified_influence = influence
            modified_influence.influence_strength *= modifier
            modified_influence.modifier_value *= modifier
            
            modified_influences.append(modified_influence)
        
        return modified_influences
    
    async def _apply_influence_to_option(
        self,
        option: Dict[str, Any],
        influence: PersonalityInfluence,
        context: DecisionContext
    ) -> Dict[str, Any]:
        """Apply a personality influence to a decision option."""
        modified_option = option.copy()
        
        # Apply influence based on affected aspect
        if influence.affected_aspect == "risk_tolerance":
            # Adjust risk-related factors
            if 'risk_factor' in modified_option:
                original_risk = modified_option['risk_factor']
                adjusted_risk = original_risk * (1.0 - influence.influence_strength)
                modified_option['risk_factor'] = max(0.0, min(1.0, adjusted_risk))
            
            if 'expected_return' in modified_option:
                # Risk-tolerant personalities might increase expected return perception
                original_return = modified_option['expected_return']
                return_adjustment = influence.influence_strength * 0.1
                modified_option['expected_return'] = original_return * (1.0 + return_adjustment)
        
        elif influence.affected_aspect == "decision_thoroughness":
            # Adjust thoroughness-related factors
            if 'complexity' in modified_option:
                original_complexity = modified_option['complexity']
                adjusted_complexity = original_complexity * (1.0 + influence.influence_strength * 0.2)
                modified_option['complexity'] = max(0.0, min(1.0, adjusted_complexity))
        
        elif influence.affected_aspect == "social_consideration":
            # Adjust social impact factors
            if 'social_impact' in modified_option:
                original_impact = modified_option['social_impact']
                adjusted_impact = original_impact * (1.0 + influence.influence_strength * 0.3)
                modified_option['social_impact'] = max(0.0, min(1.0, adjusted_impact))
        
        elif influence.affected_aspect == "option_exploration":
            # Adjust exploration factors
            if 'novelty' in modified_option:
                original_novelty = modified_option['novelty']
                adjusted_novelty = original_novelty * (1.0 + influence.influence_strength * 0.4)
                modified_option['novelty'] = max(0.0, min(1.0, adjusted_novelty))
        
        elif influence.affected_aspect == "cooperative_tendency":
            # Adjust cooperation factors
            if 'collaboration_potential' in modified_option:
                original_collab = modified_option['collaboration_potential']
                adjusted_collab = original_collab * (1.0 + influence.influence_strength * 0.3)
                modified_option['collaboration_potential'] = max(0.0, min(1.0, adjusted_collab))
        
        return modified_option
    
    async def _calculate_style_probability(
        self,
        style: DecisionMakingStyle,
        context: DecisionContext
    ) -> float:
        """Calculate probability of using a specific decision-making style."""
        if not self._personality_profile:
            return 0.0
        
        # Base probability
        base_prob = 0.2  # Equal base probability
        
        # Adjust based on personality traits
        if style == DecisionMakingStyle.ANALYTICAL:
            # Favors conscientiousness and need for cognition
            base_prob += (self._personality_profile.conscientiousness * 0.3)
            base_prob += (self._personality_profile.need_for_cognition * 0.2)
            
        elif style == DecisionMakingStyle.INTUITIVE:
            # Favors openness and low need for closure
            base_prob += (self._personality_profile.openness * 0.25)
            base_prob += ((1.0 - self._personality_profile.need_for_closure) * 0.25)
            
        elif style == DecisionMakingStyle.DEPENDENT:
            # Favors low assertiveness and high agreeableness
            base_prob += ((1.0 - self._personality_profile.assertiveness) * 0.3)
            base_prob += (self._personality_profile.agreeableness * 0.2)
            
        elif style == DecisionMakingStyle.SPONTANEOUS:
            # Favors low conscientiousness and high extraversion
            base_prob += ((1.0 - self._personality_profile.conscientiousness) * 0.3)
            base_prob += (self._personality_profile.extraversion * 0.2)
            
        elif style == DecisionMakingStyle.AVOIDANT:
            # Favors high neuroticism and low openness
            base_prob += (self._personality_profile.neuroticism * 0.3)
            base_prob += ((1.0 - self._personality_profile.openness) * 0.2)
            
        elif style == DecisionMakingStyle.COOPERATIVE:
            # Favors high agreeableness and collectivistic orientation
            base_prob += (self._personality_profile.agreeableness * 0.3)
            if self._personality_profile.social_orientation == SocialOrientation.COLLECTIVISTIC:
                base_prob += 0.2
                
        elif style == DecisionMakingStyle.COMPETITIVE:
            # Favors low agreeableness and individualistic orientation
            base_prob += ((1.0 - self._personality_profile.agreeableness) * 0.3)
            if self._personality_profile.social_orientation == SocialOrientation.INDIVIDUALISTIC:
                base_prob += 0.2
                
        elif style == DecisionMakingStyle.EMOTIONAL:
            # Favors high neuroticism and low need for cognition
            base_prob += (self._personality_profile.neuroticism * 0.3)
            base_prob += ((1.0 - self._personality_profile.need_for_cognition) * 0.2)
        
        # Adjust for context
        base_prob *= self._calculate_context_adjustment(context)
        
        # Ensure probability is between 0 and 1
        return max(0.0, min(1.0, base_prob))
    
    async def _summarize_trait_influences(
        self,
        influences: List[PersonalityInfluence]
    ) -> Dict[str, float]:
        """Summarize influences by trait."""
        summary = {}
        for influence in influences:
            trait_name = influence.personality_trait.value
            if trait_name not in summary:
                summary[trait_name] = 0.0
            summary[trait_name] += abs(influence.influence_strength)
        
        return summary
    
    async def _calculate_confidence_factors(
        self,
        context: DecisionContext
    ) -> Dict[str, float]:
        """Calculate factors affecting decision confidence."""
        if not self._personality_profile:
            return {}
        
        factors = {
            'personality_alignment': (
                self._personality_profile.conscientiousness * 0.3 +
                self._personality_profile.need_for_cognition * 0.2 +
                self._personality_profile.need_for_closure * 0.1
            ),
            'context_familiarity': 0.5,  # Placeholder
            'stress_impact': 1.0 - context.stress_level,
            'time_pressure_impact': 1.0 - context.time_pressure,
            'cognitive_load_impact': 1.0 - context.cognitive_load
        }
        
        return factors
    
    async def _generate_recommendations(
        self,
        influences: List[PersonalityInfluence],
        context: DecisionContext
    ) -> List[str]:
        """Generate recommendations based on personality influences."""
        recommendations = []
        
        # Check for strong risk aversion
        risk_influences = [inf for inf in influences if inf.affected_aspect == "risk_tolerance"]
        if risk_influences:
            avg_risk_influence = sum(inf.influence_strength for inf in risk_influences) / len(risk_influences)
            if avg_risk_influence < -0.5:  # Strong risk aversion
                recommendations.append(
                    "Consider taking more calculated risks to achieve better outcomes"
                )
        
        # Check for excessive thoroughness
        thoroughness_influences = [inf for inf in influences if inf.affected_aspect == "decision_thoroughness"]
        if thoroughness_influences:
            avg_thoroughness = sum(inf.influence_strength for inf in thoroughness_influences) / len(thoroughness_influences)
            if avg_thoroughness > 0.7 and context.time_pressure > 0.5:  # Too thorough under time pressure
                recommendations.append(
                    "Consider making a quicker decision to meet time constraints"
                )
        
        # Check for low social consideration
        social_influences = [inf for inf in influences if inf.affected_aspect == "social_consideration"]
        if social_influences and context.social_impact > 0.7:
            avg_social = sum(inf.influence_strength for inf in social_influences) / len(social_influences)
            if avg_social < 0.3:  # Low social consideration in high-impact situation
                recommendations.append(
                    "Consider the social implications more carefully"
                )
        
        return recommendations
    
    def _calculate_context_adjustment(self, context: DecisionContext) -> float:
        """Calculate context-based adjustment factor."""
        adjustment = 1.0
        
        # Adjust for stress
        adjustment *= (1.0 - context.stress_level * 0.3)
        
        # Adjust for time pressure
        adjustment *= (1.0 - context.time_pressure * 0.2)
        
        # Adjust for cognitive load
        adjustment *= (1.0 - context.cognitive_load * 0.1)
        
        # Adjust for uncertainty
        adjustment *= (1.0 - context.uncertainty_level * 0.1)
        
        return max(0.5, min(1.5, adjustment))  # Keep between 0.5 and 1.5
    
    def _initialize_trait_weights(self) -> Dict[PersonalityTrait, float]:
        """Initialize default trait influence weights."""
        return {
            PersonalityTrait.OPENNESS: 1.0,
            PersonalityTrait.CONSIENTIOUSNESS: 1.0,
            PersonalityTrait.EXTRAVERSION: 1.0,
            PersonalityTrait.AGREEABLENESS: 1.0,
            PersonalityTrait.NEUROTICISM: 1.0
        }
    
    def _initialize_situation_modifiers(self) -> Dict[str, float]:
        """Initialize situation-based modifiers."""
        return {
            'high_risk': 1.2,
            'low_risk': 0.8,
            'time_critical': 0.7,
            'non_critical': 1.0,
            'social_impact_high': 1.3,
            'social_impact_low': 0.9
        }
    
    def _initialize_cultural_modifiers(self) -> Dict[str, float]:
        """Initialize cultural context modifiers."""
        return {
            'individualistic': 1.0,
            'collectivistic': 1.0,
            'high_context': 1.0,
            'low_context': 1.0
        }
    
    def _update_influence_stats(self, influences: List[PersonalityInfluence]) -> None:
        """Update influence statistics."""
        self._total_decisions_influenced += 1
        
        # Calculate average influence strength
        if influences:
            total_strength = sum(abs(inf.influence_strength) for inf in influences)
            avg_strength = total_strength / len(influences)
            
            if self._total_decisions_influenced == 1:
                self._average_influence_strength = avg_strength
            else:
                # Running average
                self._average_influence_strength = (
                    self._average_influence_strength * (self._total_decisions_influenced - 1) +
                    avg_strength
                ) / self._total_decisions_influenced
        
        # Update influence by trait
        for influence in influences:
            trait = influence.personality_trait
            self._influence_by_trait[trait].append(abs(influence.influence_strength))
        
        # Keep lists manageable
        for trait_list in self._influence_by_trait.values():
            if len(trait_list) > 1000:  # Keep last 1000 entries
                trait_list[:] = trait_list[-500:]