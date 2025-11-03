"""
WebOps AI Agent System - Core Module

This module provides the core framework for creating AI agents with
human-like characteristics for WebOps automation.
"""

from .agent import WebOpsAgent
from .lifecycle import AgentLifecycle, AgentState
from .resources import ResourceManager, ResourceLimits, ResourceUsage

__all__ = [
    'WebOpsAgent',
    'AgentLifecycle',
    'AgentState',
    'ResourceManager',
    'ResourceLimits',
    'ResourceUsage'
]

__version__ = '1.0.0'