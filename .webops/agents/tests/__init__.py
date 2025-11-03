"""
WebOps AI Agent System - Testing Framework

This module provides comprehensive testing capabilities for AI agents,
including unit tests, integration tests, and performance tests.
"""

from .test_agent import TestAgent, AgentTestCase
from .test_personality import TestPersonality, PersonalityTestCase
from .test_memory import TestMemory, MemoryTestCase
from .test_skills import TestSkills, SkillTestCase
from .test_decision import TestDecision, DecisionTestCase
from .test_interface import TestInterface, InterfaceTestCase

__all__ = [
    'TestAgent',
    'AgentTestCase',
    'TestPersonality',
    'PersonalityTestCase',
    'TestMemory',
    'MemoryTestCase',
    'TestSkills',
    'SkillTestCase',
    'TestDecision',
    'DecisionTestCase',
    'TestInterface',
    'InterfaceTestCase'
]

__version__ = '1.0.0'