"""
WebOps AI Agent System - Skills Module

This module provides skill management, acquisition, and execution
capabilities for AI agents.
"""

from .skill_registry import SkillRegistry, Skill, SkillCategory
from .acquisition import SkillAcquisition, LearningMethod
from .execution import SkillExecutor, ExecutionContext, SkillResult

__all__ = [
    'SkillRegistry',
    'Skill',
    'SkillCategory',
    'SkillAcquisition',
    'LearningMethod',
    'SkillExecutor',
    'ExecutionContext',
    'SkillResult'
]

__version__ = '1.0.0'