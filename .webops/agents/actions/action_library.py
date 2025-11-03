"""
Action Library for AI Agent

Provides a comprehensive library of authenticated actions that agents can use
to interact with systems and services.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid
import aiohttp
from datetime import datetime
import hashlib
import hmac


class ActionType(Enum):
    """Types of actions in the action library."""
    
    SYSTEM = "system"
    DEPLOYMENT = "deployment"
    DATABASE = "database"
    NETWORK = "network"
    FILE = "file"
    MONITORING = "monitoring"
    SECURITY = "security"
    COMMUNICATION = "communication"
    INTEGRATION = "integration"


class AuthenticationMethod(Enum):
    """Authentication methods for actions."""
    
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    OAUTH = "oauth"
    JWT = "jwt"
    HMAC = "hmac"
    CUSTOM = "custom"


@dataclass
class ActionParameter:
    """Parameter for an action."""
    
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    validation: Optional[Dict[str, Any]] = None
    
    def validate(self, value: Any) -> bool:
        """Validate parameter value."""
        if value is None and self.required:
            return False
        
        if value is not None:
            # Type validation
            if self.type == "string" and not isinstance(value, str):
                return False
            elif self.type == "integer" and not isinstance(value, int):
                return False
            elif self.type == "float" and not isinstance(value, (int, float)):
                return False
            elif self.type == "boolean" and not isinstance(value, bool):
                return False
            elif self.type == "list" and not isinstance(value, list):
                return False
            elif self.type == "dict" and not isinstance(value, dict):
                return False
        
        # Custom validation
        if self.validation and value is not None:
            for rule, rule_value in self.validation.items():
                if rule == "min_length" and isinstance(value, str) and len(value) < rule_value:
                    return False
                elif rule == "max_length" and isinstance(value, str) and len(value) > rule_value:
                    return False
                elif rule == "min_value" and isinstance(value, (int, float)) and value < rule_value:
                    return False
                elif rule == "max_value" and isinstance(value, (int, float)) and value > rule_value:
                    return False
                elif rule == "pattern" and isinstance(value, str) and not rule_value.match(value):
                    return False
        
        return True


@dataclass
class ActionDefinition:
    """Definition of an action."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    action_type: ActionType = ActionType.SYSTEM
    category: str = "general"
    parameters: List[ActionParameter] = field(default_factory=list)
    authentication_method: AuthenticationMethod = AuthenticationMethod.NONE
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    retry_count: int = 3
    rate_limit: Optional[Dict[str, Any]] = None
    cost: float = 0.0
    tags: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    is_active: bool = True
    
    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate action parameters."""
        errors = []
        validated_params = {}
        
        # Check required parameters
        for param in self.parameters:
            value = params.get(param.name, param.default)
            
            if value is None and param.required:
                errors.append(f"Required parameter '{param.name}' is missing")
                continue
            
            if not param.validate(value):
                errors.append(f"Parameter '{param.name}' validation failed")
                continue
            
            validated_params[param.name] = value
        
        if errors:
            raise ValueError(f"Parameter validation failed: {'; '.join(errors)}")
        
        return validated_params
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'action_type': self.action_type.value,
            'category': self.category,
            'parameters': [param.__dict__ for param in self.parameters],
            'authentication_method': self.authentication_method.value,
            'required_permissions': self.required_permissions,
            'timeout_seconds': self.timeout_seconds,
            'retry_count': self.retry_count,
            'rate_limit': self.rate_limit,
            'cost': self.cost,
            'tags': self.tags,
            'examples': self.examples,
            'version': self.version,
            'is_active': self.is_active
        }


class BaseAction(ABC):
    """Base class for all actions."""
    
    def __init__(self, definition: ActionDefinition):
        self.definition = definition
        self.logger = logging.getLogger(f"action.{self.definition.name}")
        self._rate_limiter = None
        self._cost_tracker = {}
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action."""
        pass
    
    async def authenticate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform authentication."""
        auth_info = {
            'method': self.definition.authentication_method,
            'authenticated': True,
            'token': None,
            'expires_at': None
        }
        
        # Authentication logic based on method
        if self.definition.authentication_method == AuthenticationMethod.API_KEY:
            auth_info['token'] = context.get('api_key')
        elif self.definition.authentication_method == AuthenticationMethod.BEARER_TOKEN:
            auth_info['token'] = context.get('bearer_token')
        elif self.definition.authentication_method == AuthenticationMethod.BASIC_AUTH:
            auth_info['username'] = context.get('username')
            auth_info['password'] = context.get('password')
        elif self.definition.authentication_method == AuthenticationMethod.JWT:
            auth_info['token'] = context.get('jwt_token')
        elif self.definition.authentication_method == AuthenticationMethod.HMAC:
            # HMAC authentication
            message = context.get('message', '')
            secret_key = context.get('secret_key', '')
            if secret_key:
                signature = hmac.new(
                    secret_key.encode(),
                    message.encode(),
                    hashlib.sha256
                ).hexdigest()
                auth_info['signature'] = signature
        
        return auth_info
    
    async def rate_limit_check(self, context: Dict[str, Any]) -> bool:
        """Check rate limits."""
        if not self.definition.rate_limit:
            return True
        
        # Simple rate limiting implementation
        user_id = context.get('user_id', 'anonymous')
        now = datetime.now()
        
        if user_id not in self._rate_limiter:
            self._rate_limiter[user_id] = []
        
        # Clean old entries
        cutoff = now.timestamp() - self.definition.rate_limit.get('window_seconds', 3600)
        self._rate_limiter[user_id] = [
            timestamp for timestamp in self._rate_limiter[user_id]
            if timestamp > cutoff
        ]
        
        # Check limit
        max_requests = self.definition.rate_limit.get('max_requests', 100)
        if len(self._rate_limiter[user_id]) >= max_requests:
            return False
        
        # Add current request
        self._rate_limiter[user_id].append(now.timestamp())
        return True
    
    async def log_execution(self, params: Dict[str, Any], result: Dict[str, Any], 
                          context: Dict[str, Any]) -> None:
        """Log action execution."""
        log_entry = {
            'action_id': self.definition.id,
            'action_name': self.definition.name,
            'timestamp': datetime.now().isoformat(),
            'user_id': context.get('user_id'),
            'success': result.get('success', False),
            'duration': result.get('duration'),
            'cost': result.get('cost', 0.0),
            'error': result.get('error')
        }
        
        self.logger.info(f"Action executed: {json.dumps(log_entry)}")


class WebOpsActionLibrary:
    """Library of actions available to AI agents."""
    
    def __init__(self):
        self.logger = logging.getLogger("action_library")
        self._actions: Dict[str, BaseAction] = {}
        self._action_definitions: Dict[str, ActionDefinition] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._type_index: Dict[ActionType, List[str]] = {}
        self._enabled = True
    
    def register_action(self, action: BaseAction) -> None:
        """Register an action in the library."""
        definition = action.definition
        self._actions[definition.id] = action
        self._action_definitions[definition.id] = definition
        
        # Update indices
        if definition.category not in self._category_index:
            self._category_index[definition.category] = []
        self._category_index[definition.category].append(definition.id)
        
        if definition.action_type not in self._type_index:
            self._type_index[definition.action_type] = []
        self._type_index[definition.action_type].append(definition.id)
        
        self.logger.info(f"Registered action: {definition.name} ({definition.id})")
    
    async def execute_action(self, action_id: str, params: Dict[str, Any], 
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action."""
        if not self._enabled:
            raise ValueError("Action library is disabled")
        
        if action_id not in self._actions:
            raise ValueError(f"Action not found: {action_id}")
        
        action = self._actions[action_id]
        definition = action.definition
        
        if not definition.is_active:
            raise ValueError(f"Action is not active: {action_id}")
        
        try:
            # Validate parameters
            validated_params = definition.validate_parameters(params)
            
            # Rate limiting check
            if not await action.rate_limit_check(context):
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'action_id': action_id
                }
            
            # Authentication
            auth_info = await action.authenticate(context)
            
            # Execute action
            start_time = datetime.now()
            result = await action.execute(validated_params, context)
            end_time = datetime.now()
            
            # Add execution metadata
            result.update({
                'action_id': action_id,
                'action_name': definition.name,
                'success': result.get('success', True),
                'duration': (end_time - start_time).total_seconds(),
                'cost': result.get('cost', definition.cost),
                'timestamp': end_time.isoformat()
            })
            
            # Log execution
            await action.log_execution