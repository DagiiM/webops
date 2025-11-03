"""
WebOps AI Agent System - Personality Module

This module provides personality traits, emotional state management,
and behavioral patterns for AI agents with human-like characteristics.
"""

from .traits import PersonalityProfile, PersonalityType
from .emotions import EmotionalState, Emotion, Mood
from .behavior import BehaviorPattern, BehaviorManager

__all__ = [
    'PersonalityProfile',
    'PersonalityType',
    'EmotionalState',
    'Emotion',
    'Mood',
    'BehaviorPattern',
    'BehaviorManager'
]

__version__ = '1.0.0'