"""
WebOps AI Agent System - Interface Module

This module provides user interfaces for interacting with AI agents,
including chat, REST API, and CLI interfaces.
"""

from .chat import ChatInterface, ChatSession, Message
from .api import AgentAPI, APIResponse, APIRequest
from .cli import AgentCLI, CLICommand

__all__ = [
    'ChatInterface',
    'ChatSession',
    'Message',
    'AgentAPI',
    'APIResponse',
    'APIRequest',
    'AgentCLI',
    'CLICommand'
]

__version__ = '1.0.0'