"""
WebOps AI Agent System - Memory Module

This module provides memory storage and learning capabilities for AI agents,
including episodic, semantic, and procedural memory systems.
"""

from .memory_manager import MemoryManager, MemoryConfig
from .episodic import EpisodicMemory, Experience
from .semantic import SemanticMemory, Fact, Knowledge
from .procedural import ProceduralMemory, Procedure, Skill
from .learning import LearningSystem, LearningResult

__all__ = [
    'MemoryManager',
    'MemoryConfig',
    'EpisodicMemory',
    'Experience',
    'SemanticMemory',
    'Fact',
    'Knowledge',
    'ProceduralMemory',
    'Procedure',
    'Skill',
    'LearningSystem',
    'LearningResult'
]

__version__ = '1.0.0'