"""
Skill Registry Module

Manages registration, discovery, and metadata of agent skills.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod


class SkillCategory(Enum):
    """Categories of skills for organization."""
    
    TECHNICAL = "technical"
    COMMUNICATION = "communication"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    SOCIAL = "social"
    LEARNING = "learning"
    MANAGEMENT = "management"
    SECURITY = "security"


class SkillLevel(Enum):
    """Proficiency levels for skills."""
    
    NOVICE = "novice"          # 0.0 - 0.2
    BEGINNER = "beginner"        # 0.2 - 0.4
    INTERMEDIATE = "intermediate"  # 0.4 - 0.6
    ADVANCED = "advanced"          # 0.6 - 0.8
    EXPERT = "expert"            # 0.8 - 1.0
    MASTER = "master"            # 1.0


@dataclass
class SkillMetadata:
    """Metadata for a skill."""
    
    name: str
    description: str
    category: SkillCategory
    version: str = "1.0.0"
    author: str = "WebOps"
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SkillProficiency:
    """Agent's proficiency in a skill."""
    
    skill_name: str
    level: float = 0.0  # 0.0 to 1.0
    experience_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    learning_rate: float = 0.01
    improvement_rate: float = 0.001
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def skill_level(self) -> SkillLevel:
        """Get skill level based on proficiency."""
        if self.level >= 1.0:
            return SkillLevel.MASTER
        elif self.level >= 0.8:
            return SkillLevel.EXPERT
        elif self.level >= 0.6:
            return SkillLevel.ADVANCED
        elif self.level >= 0.4:
            return SkillLevel.INTERMEDIATE
        elif self.level >= 0.2:
            return SkillLevel.BEGINNER
        else:
            return SkillLevel.NOVICE
    
    def update_proficiency(self, success: bool) -> None:
        """Update proficiency based on usage outcome."""
        self.experience_count += 1
        self.last_used = datetime.now()
        
        if success:
            self.success_count += 1
            # Increase proficiency
            self.level = min(1.0, self.level + self.learning_rate)
        else:
            self.failure_count += 1
            # Decrease proficiency slightly
            self.level = max(0.0, self.level - self.learning_rate * 0.5)
        
        # Apply improvement rate over time
        self.level = min(1.0, self.level + self.improvement_rate)


class Skill(ABC):
    """
    Abstract base class for all skills.
    
    All skills must inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, metadata: SkillMetadata):
        """Initialize skill with metadata."""
        self.metadata = metadata
        self.logger = logging.getLogger(f"skill.{metadata.name}")
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill with given parameters.
        
        Args:
            parameters: Skill execution parameters
            context: Execution context
            
        Returns:
            Execution result
        """
        pass
    
    @abstractmethod
    async def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate skill parameters.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            Validation result
        """
        pass
    
    async def get_help(self) -> str:
        """Get help text for the skill."""
        help_text = f"""
# {self.metadata.name}

{self.metadata.description}

## Category
{self.metadata.category.value}

## Parameters
"""
        for param_name, param_info in self.metadata.parameters.items():
            help_text += f"- **{param_name}**: {param_info.get('description', 'No description')}\n"
        
        help_text += f"""
## Examples
"""
        for example in self.metadata.examples:
            help_text += f"- {example.get('description', 'No description')}: `{example.get('command', '')}`\n"
        
        return help_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary."""
        return {
            'metadata': asdict(self.metadata),
            'type': self.__class__.__name__
        }


class SkillRegistry:
    """
    Registry for managing agent skills.
    
    Handles skill registration, discovery, and proficiency tracking.
    """
    
    def __init__(self):
        """Initialize skill registry."""
        self.logger = logging.getLogger("skill_registry")
        
        # Skill storage
        self._skills: Dict[str, Skill] = {}
        self._proficiencies: Dict[str, SkillProficiency] = {}
        
        # Skill categories
        self._categories: Dict[SkillCategory, List[str]] = {
            category: [] for category in SkillCategory
        }
        
        # Load built-in skills
        self._load_builtin_skills()
    
    async def register_skill(self, skill: Skill) -> str:
        """
        Register a new skill.
        
        Args:
            skill: Skill instance to register
            
        Returns:
            Skill ID
        """
        try:
            skill_name = skill.metadata.name
            
            # Check if skill already exists
            if skill_name in self._skills:
                self.logger.warning(f"Skill {skill_name} already exists, updating")
            
            # Register skill
            self._skills[skill_name] = skill
            
            # Initialize proficiency if not exists
            if skill_name not in self._proficiencies:
                self._proficiencies[skill_name] = SkillProficiency(skill_name)
            
            # Add to category
            category = skill.metadata.category
            if skill_name not in self._categories[category]:
                self._categories[category].append(skill_name)
            
            self.logger.info(f"Registered skill: {skill_name}")
            return skill_name
            
        except Exception as e:
            self.logger.error(f"Error registering skill: {e}")
            raise
    
    async def unregister_skill(self, skill_name: str) -> bool:
        """
        Unregister a skill.
        
        Args:
            skill_name: Name of skill to unregister
            
        Returns:
            Success status
        """
        try:
            if skill_name not in self._skills:
                return False
            
            # Get skill category
            category = self._skills[skill_name].metadata.category
            
            # Remove from registry
            del self._skills[skill_name]
            
            # Remove from category
            if skill_name in self._categories[category]:
                self._categories[category].remove(skill_name)
            
            # Keep proficiency for potential re-registration
            
            self.logger.info(f"Unregistered skill: {skill_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unregistering skill: {e}")
            return False
    
    async def has_skill(self, skill_name: str) -> bool:
        """
        Check if skill is registered.
        
        Args:
            skill_name: Name of skill to check
            
        Returns:
            True if skill exists
        """
        return skill_name in self._skills
    
    async def get_skill(self, skill_name: str) -> Optional[Skill]:
        """
        Get skill by name.
        
        Args:
            skill_name: Name of skill to get
            
        Returns:
            Skill instance or None
        """
        return self._skills.get(skill_name)
    
    async def list_skills(self, category: Optional[SkillCategory] = None) -> List[str]:
        """
        List registered skills.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of skill names
        """
        if category:
            return self._categories.get(category, []).copy()
        
        return list(self._skills.keys())
    
    async def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        Get skill metadata.
        
        Args:
            skill_name: Name of skill
            
        Returns:
            Skill metadata or None
        """
        skill = self._skills.get(skill_name)
        return skill.metadata if skill else None
    
    async def get_proficiency(self, skill_name: str) -> Optional[SkillProficiency]:
        """
        Get skill proficiency.
        
        Args:
            skill_name: Name of skill
            
        Returns:
            Skill proficiency or None
        """
        return self._proficiencies.get(skill_name)
    
    async def update_proficiency(self, skill_name: str, level: float) -> None:
        """
        Update skill proficiency level.
        
        Args:
            skill_name: Name of skill
            level: New proficiency level (0.0 to 1.0)
        """
        if skill_name in self._proficiencies:
            self._proficiencies[skill_name].level = max(0.0, min(1.0, level))
            self.logger.info(f"Updated proficiency for {skill_name}: {level}")
    
    async def execute_skill(self, skill_name: str, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a skill.
        
        Args:
            skill_name: Name of skill to execute
            parameters: Skill parameters
            context: Execution context
            
        Returns:
            Execution result
        """
        try:
            # Get skill
            skill = self._skills.get(skill_name)
            if not skill:
                return {
                    'success': False,
                    'error': f'Skill {skill_name} not found',
                    'skill_name': skill_name
                }
            
            # Validate parameters
            validation = await skill.validate_parameters(parameters)
            if not validation.get('valid', False):
                return {
                    'success': False,
                    'error': validation.get('error', 'Invalid parameters'),
                    'skill_name': skill_name,
                    'validation': validation
                }
            
            # Get proficiency
            proficiency = self._proficiencies.get(skill_name)
            if proficiency:
                # Add proficiency to context
                context['skill_proficiency'] = proficiency.level
                context['skill_level'] = proficiency.skill_level.value
            
            # Execute skill
            start_time = datetime.now()
            result = await skill.execute(parameters, context)
            end_time = datetime.now()
            
            # Update proficiency
            if proficiency:
                success = result.get('success', False)
                proficiency.update_proficiency(success)
            
            # Add execution metadata
            result['skill_name'] = skill_name
            result['execution_time'] = (end_time - start_time).total_seconds()
            result['proficiency'] = proficiency.level if proficiency else 0.0
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing skill {skill_name}: {e}")
            
            # Update proficiency on error
            if skill_name in self._proficiencies:
                self._proficiencies[skill_name].update_proficiency(False)
            
            return {
                'success': False,
                'error': str(e),
                'skill_name': skill_name
            }
    
    async def load_skill(self, skill_name: str) -> bool:
        """
        Load a skill from built-in library.
        
        Args:
            skill_name: Name of skill to load
            
        Returns:
            Success status
        """
        try:
            # Try to load from built-in skills
            skill_class = self._get_builtin_skill_class(skill_name)
            if not skill_class:
                return False
            
            # Create skill instance
            skill = skill_class()
            
            # Register skill
            await self.register_skill(skill)
            
            self.logger.info(f"Loaded built-in skill: {skill_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading skill {skill_name}: {e}")
            return False
    
    async def update_from_pattern(self, pattern: Dict[str, Any]) -> None:
        """
        Update skills based on identified pattern.
        
        Args:
            pattern: Identified pattern
        """
        try:
            pattern_type = pattern.get('type', 'unknown')
            
            if pattern_type == 'success_pattern':
                # Improve related skills
                await self._improve_related_skills(pattern, improvement=0.05)
            elif pattern_type == 'failure_pattern':
                # Reduce confidence in related skills
                await self._improve_related_skills(pattern, improvement=-0.02)
            
        except Exception as e:
            self.logger.error(f"Error updating from pattern: {e}")
    
    async def optimize_storage(self) -> None:
        """Optimize skill storage and performance."""
        try:
            # Clean up unused skills
            cutoff_time = datetime.now() - timedelta(days=30)
            
            for skill_name, proficiency in self._proficiencies.items():
                if proficiency.last_used and proficiency.last_used < cutoff_time:
                    # Mark as less important
                    proficiency.learning_rate *= 0.9
            
            self.logger.info("Skill storage optimization completed")
            
        except Exception as e:
            self.logger.error(f"Error optimizing storage: {e}")
    
    def _load_builtin_skills(self) -> None:
        """Load built-in skills."""
        # This would load all built-in skills
        # For now, just log that we're loading
        self.logger.info("Loading built-in skills")
    
    def _get_builtin_skill_class(self, skill_name: str) -> Optional[type]:
        """Get built-in skill class by name."""
        # This would return the actual skill class
        # For now, return None
        return None
    
    async def _improve_related_skills(self, pattern: Dict[str, Any], improvement: float) -> None:
        """Improve skills related to a pattern."""
        try:
            decision_type = pattern.get('decision_type', 'unknown')
            context = pattern.get('context', {})
            
            # Find related skills
            related_skills = []
            for skill_name, skill in self._skills.items():
                # Check if skill relates to pattern
                if self._skill_relates_to_pattern(skill, pattern):
                    related_skills.append(skill_name)
            
            # Update proficiencies
            for skill_name in related_skills:
                if skill_name in self._proficiencies:
                    proficiency = self._proficiencies[skill_name]
                    proficiency.level = max(0.0, min(1.0, proficiency.level + improvement))
            
        except Exception as e:
            self.logger.error(f"Error improving related skills: {e}")
    
    def _skill_relates_to_pattern(self, skill: Skill, pattern: Dict[str, Any]) -> bool:
        """Check if skill relates to a pattern."""
        # Simple implementation - check tags and category
        pattern_tags = pattern.get('tags', [])
        skill_tags = skill.metadata.tags
        
        # Check for tag overlap
        return any(tag in skill_tags for tag in pattern_tags)