"""
Input validation for addon API requests.

Provides JSON schema validation for:
- Addon configuration
- Installation requests
- API request bodies
- Parameter sanitization
"""

import re
from functools import wraps
from typing import Dict, Any, Optional, Callable, List

from django.http import JsonResponse, HttpRequest
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# JSON Schemas for Validation
# ============================================================================

class AddonSchemas:
    """JSON schemas for addon validation."""

    # Schema for addon configuration
    CONFIG_SCHEMA = {
        "type": "object",
        "additionalProperties": True,  # Allow arbitrary config keys
        "properties": {
            "port": {
                "type": "integer",
                "minimum": 1,
                "maximum": 65535
            },
            "max_connections": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000
            },
            "memory_limit": {
                "type": "string",
                "pattern": r"^\d+[KMG]B$"
            },
            "enabled": {
                "type": "boolean"
            }
        }
    }

    # Schema for install request
    INSTALL_REQUEST_SCHEMA = {
        "type": "object",
        "properties": {
            "config": CONFIG_SCHEMA
        },
        "additionalProperties": False
    }

    # Schema for uninstall request
    UNINSTALL_REQUEST_SCHEMA = {
        "type": "object",
        "properties": {
            "keep_data": {
                "type": "boolean"
            }
        },
        "additionalProperties": False
    }

    # Schema for configure request
    CONFIGURE_REQUEST_SCHEMA = {
        "type": "object",
        "required": ["config"],
        "properties": {
            "config": CONFIG_SCHEMA
        },
        "additionalProperties": False
    }

    # Schema for toggle request
    TOGGLE_REQUEST_SCHEMA = {
        "type": "object",
        "required": ["enabled"],
        "properties": {
            "enabled": {
                "type": "boolean"
            }
        },
        "additionalProperties": False
    }


class ValidationError(Exception):
    """Custom validation error."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


def validate_json_schema(data: Any, schema: Dict) -> List[str]:
    """
    Validate data against JSON schema.

    Simple validation without external dependencies.
    For production, consider using jsonschema library.

    Args:
        data: Data to validate
        schema: JSON schema

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    schema_type = schema.get('type')

    # Type validation
    if schema_type == 'object' and not isinstance(data, dict):
        errors.append(f"Expected object, got {type(data).__name__}")
        return errors

    if schema_type == 'array' and not isinstance(data, list):
        errors.append(f"Expected array, got {type(data).__name__}")
        return errors

    if schema_type == 'string' and not isinstance(data, str):
        errors.append(f"Expected string, got {type(data).__name__}")
        return errors

    if schema_type == 'integer' and not isinstance(data, int):
        errors.append(f"Expected integer, got {type(data).__name__}")
        return errors

    if schema_type == 'boolean' and not isinstance(data, bool):
        errors.append(f"Expected boolean, got {type(data).__name__}")
        return errors

    # Object validation
    if schema_type == 'object' and isinstance(data, dict):
        # Required properties
        required = schema.get('required', [])
        for prop in required:
            if prop not in data:
                errors.append(f"Missing required property: {prop}")

        # Additional properties
        if not schema.get('additionalProperties', True):
            allowed_props = set(schema.get('properties', {}).keys())
            extra_props = set(data.keys()) - allowed_props
            if extra_props:
                errors.append(f"Additional properties not allowed: {', '.join(extra_props)}")

        # Validate properties
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                prop_errors = validate_json_schema(data[prop_name], prop_schema)
                errors.extend([f"{prop_name}: {err}" for err in prop_errors])

    # Integer validation
    if schema_type == 'integer' and isinstance(data, int):
        minimum = schema.get('minimum')
        maximum = schema.get('maximum')

        if minimum is not None and data < minimum:
            errors.append(f"Value {data} is less than minimum {minimum}")

        if maximum is not None and data > maximum:
            errors.append(f"Value {data} is greater than maximum {maximum}")

    # String validation
    if schema_type == 'string' and isinstance(data, str):
        pattern = schema.get('pattern')
        if pattern:
            if not re.match(pattern, data):
                errors.append(f"String does not match pattern: {pattern}")

        min_length = schema.get('minLength')
        max_length = schema.get('maxLength')

        if min_length is not None and len(data) < min_length:
            errors.append(f"String length {len(data)} is less than minimum {min_length}")

        if max_length is not None and len(data) > max_length:
            errors.append(f"String length {len(data)} is greater than maximum {max_length}")

    return errors


def validate_addon_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate addon configuration.

    Args:
        config: Configuration dictionary

    Returns:
        List of validation errors
    """
    errors = []

    if not isinstance(config, dict):
        return ["Configuration must be a JSON object"]

    # Validate using schema
    schema_errors = validate_json_schema(config, AddonSchemas.CONFIG_SCHEMA)
    errors.extend(schema_errors)

    # Additional validation rules
    if 'port' in config:
        port = config['port']
        if port in [22, 80, 443]:
            errors.append(f"Port {port} is reserved and cannot be used")

    return errors


def sanitize_string(value: str, max_length: int = 255) -> str:
    """
    Sanitize string input.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value)

    # Trim whitespace
    value = value.strip()

    # Limit length
    value = value[:max_length]

    # Remove control characters
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\n\r\t')

    return value


def sanitize_addon_name(name: str) -> str:
    """
    Sanitize addon name.

    Args:
        name: Addon name

    Returns:
        Sanitized name

    Raises:
        ValidationError: If name is invalid
    """
    name = sanitize_string(name, max_length=100)

    # Allow only alphanumeric, dash, underscore
    if not re.match(r'^[a-z0-9_-]+$', name):
        raise ValidationError(
            "Addon name must contain only lowercase letters, numbers, hyphens, and underscores"
        )

    return name


def validate_request_json(schema: Dict):
    """
    Decorator to validate request JSON against schema.

    Args:
        schema: JSON schema to validate against

    Usage:
        @validate_request_json(AddonSchemas.INSTALL_REQUEST_SCHEMA)
        def install_addon(request, name):
            data = json.loads(request.body)
            # data is now validated
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Skip validation for GET requests
            if request.method == 'GET':
                return view_func(request, *args, **kwargs)

            # Parse JSON
            try:
                if request.body:
                    data = json.loads(request.body)
                else:
                    data = {}
            except json.JSONDecodeError as e:
                return JsonResponse({
                    'error': 'Invalid JSON',
                    'message': str(e)
                }, status=400)

            # Validate against schema
            errors = validate_json_schema(data, schema)

            if errors:
                return JsonResponse({
                    'error': 'Validation failed',
                    'errors': errors
                }, status=400)

            # Validation passed
            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def validate_addon_name_param(view_func: Callable) -> Callable:
    """
    Decorator to validate addon name URL parameter.

    Usage:
        @validate_addon_name_param
        def get_addon(request, name):
            # name is now validated and sanitized
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        name = kwargs.get('name')

        if not name:
            return JsonResponse({
                'error': 'Addon name required'
            }, status=400)

        try:
            sanitized_name = sanitize_addon_name(name)
            kwargs['name'] = sanitized_name
        except ValidationError as e:
            return JsonResponse({
                'error': 'Invalid addon name',
                'message': str(e)
            }, status=400)

        return view_func(request, *args, **kwargs)

    return wrapper


def validate_pagination_params(request: HttpRequest) -> Dict[str, int]:
    """
    Validate and sanitize pagination parameters.

    Args:
        request: Django request

    Returns:
        Dictionary with validated page and per_page

    Raises:
        ValidationError: If parameters are invalid
    """
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
    except ValueError:
        raise ValidationError("Page and per_page must be integers")

    if page < 1:
        raise ValidationError("Page must be >= 1")

    if per_page < 1 or per_page > 100:
        raise ValidationError("Per page must be between 1 and 100")

    return {'page': page, 'per_page': per_page}


class ConfigValidator:
    """
    Validator for addon-specific configuration.

    Allows defining custom validation rules per addon type.
    """

    def __init__(self):
        """Initialize validator with default rules."""
        self.validators = {}

    def register_validator(self, addon_type: str, validator: Callable):
        """
        Register a custom validator for an addon type.

        Args:
            addon_type: Type of addon (e.g., 'database', 'cache')
            validator: Callable that validates config and returns errors
        """
        self.validators[addon_type] = validator

    def validate(self, addon_type: str, config: Dict) -> List[str]:
        """
        Validate configuration for specific addon type.

        Args:
            addon_type: Type of addon
            config: Configuration dictionary

        Returns:
            List of validation errors
        """
        # Basic validation
        errors = validate_addon_config(config)

        # Type-specific validation
        if addon_type in self.validators:
            type_errors = self.validators[addon_type](config)
            errors.extend(type_errors)

        return errors


# Global validator instance
config_validator = ConfigValidator()


# Example type-specific validators
def validate_database_config(config: Dict) -> List[str]:
    """Validate database addon configuration."""
    errors = []

    if 'max_connections' in config:
        if config['max_connections'] < 10:
            errors.append("Database max_connections must be at least 10")

    return errors


def validate_cache_config(config: Dict) -> List[str]:
    """Validate cache addon configuration."""
    errors = []

    if 'memory_limit' in config:
        memory = config['memory_limit']
        if not re.match(r'^\d+[MG]B$', memory):
            errors.append("Memory limit must be in format: 256MB or 1GB")

    return errors


# Register default validators
config_validator.register_validator('database', validate_database_config)
config_validator.register_validator('cache', validate_cache_config)
