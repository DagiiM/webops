"""
Configuration Management System

Handles configuration loading, validation, and management for the AI Agent System.
"""

import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
from configparser import ConfigParser
import asyncio
from datetime import datetime


class ConfigFormat(Enum):
    """Configuration file formats."""
    
    JSON = "json"
    YAML = "yaml"
    YAMLML = "yml"
    INI = "ini"
    ENV = "env"
    TOML = "toml"


class ConfigScope(Enum):
    """Configuration scope levels."""
    
    SYSTEM = "system"
    AGENT = "agent"
    MODULE = "module"
    USER = "user"
    ENVIRONMENT = "environment"


@dataclass
class ConfigSource:
    """Configuration source information."""
    
    path: str
    format: ConfigFormat
    scope: ConfigScope
    priority: int = 0
    required: bool = False
    reload_on_change: bool = True
    encrypted: bool = False
    watch_handlers: List[Callable] = field(default_factory=list)
    last_loaded: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigValue:
    """Configuration value with metadata."""
    
    value: Any
    source: ConfigSource
    type_hint: type = str
    description: str = ""
    validator: Optional[Callable] = None
    default: Any = None
    encrypted: bool = False
    secret: bool = False
    environment_variable: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ConfigSchema:
    """Configuration schema definition."""
    
    key_path: str
    type_hint: type
    required: bool = False
    default: Any = None
    description: str = ""
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    environment_mapping: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    sensitive: bool = False


class ConfigurationManager:
    """Central configuration management system."""
    
    def __init__(self, config_dir: str = None):
        """Initialize configuration manager."""
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".webops" / "agents" / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration storage
        self._config_values: Dict[str, ConfigValue] = {}
        self._config_sources: List[ConfigSource] = []
        self._schema: Dict[str, ConfigSchema] = {}
        
        # Load order and precedence
        self._load_order = [
            ConfigScope.SYSTEM,
            ConfigScope.AGENT,
            ConfigScope.MODULE,
            ConfigScope.ENVIRONMENT,
            ConfigScope.USER,
        ]
        
        # File watchers and reloading
        self._watchers: Dict[str, asyncio.Task] = {}
        self._watch_callbacks: Dict[str, List[Callable]] = {}
        
        # Validation and validation functions
        self._validators: Dict[str, Callable] = {}
        self._custom_types: Dict[type, Callable] = {}
        
        # Configuration caching
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True
        self._cache_ttl = 300  # 5 minutes
        
        # Logging
        self.logger = logging.getLogger("config_manager")
        
        # Configuration events
        self._event_handlers: Dict[str, List[Callable]] = {
            'config_changed': [],
            'config_reloaded': [],
            'validation_failed': [],
            'source_added': [],
            'source_removed': [],
        }
    
    def add_config_source(
        self,
        path: str,
        format: ConfigFormat = None,
        scope: ConfigScope = ConfigScope.SYSTEM,
        priority: int = 0,
        required: bool = False,
        reload_on_change: bool = True,
        encrypted: bool = False
    ) -> ConfigSource:
        """Add a configuration source."""
        if format is None:
            format = self._detect_format(path)
        
        source = ConfigSource(
            path=path,
            format=format,
            scope=scope,
            priority=priority,
            required=required,
            reload_on_change=reload_on_change,
            encrypted=encrypted
        )
        
        self._config_sources.append(source)
        
        # Sort by priority
        self._config_sources.sort(key=lambda x: (x.priority, x.scope.value), reverse=True)
        
        # Trigger event
        self._trigger_event('source_added', source)
        
        self.logger.info(f"Added config source: {path} ({format.value}, {scope.value})")
        return source
    
    def register_schema(
        self,
        key_path: str,
        type_hint: type = str,
        required: bool = False,
        default: Any = None,
        description: str = "",
        validation_rules: Dict[str, Any] = None,
        environment_mapping: str = None,
        depends_on: List[str] = None,
        sensitive: bool = False
    ) -> ConfigSchema:
        """Register a configuration schema."""
        schema = ConfigSchema(
            key_path=key_path,
            type_hint=type_hint,
            required=required,
            default=default,
            description=description,
            validation_rules=validation_rules or {},
            environment_mapping=environment_mapping,
            depends_on=depends_on or [],
            sensitive=sensitive
        )
        
        self._schema[key_path] = schema
        
        # Register validator if provided
        if 'type' in schema.validation_rules:
            type_name = schema.validation_rules['type']
            if type_name in self._custom_types:
                schema.validator = self._custom_types[type_name]
        
        self.logger.debug(f"Registered schema for: {key_path}")
        return schema
    
    async def load_all(self, force_reload: bool = False) -> Dict[str, ConfigValue]:
        """Load all configuration sources."""
        self.logger.info("Loading all configuration sources")
        
        # Load sources in priority order
        for source in self._config_sources:
            try:
                await self._load_source(source, force_reload)
            except Exception as e:
                self.logger.error(f"Error loading config source {source.path}: {e}")
                if source.required:
                    raise
        
        # Validate configuration
        await self._validate_configuration()
        
        # Trigger reload event
        self._trigger_event('config_reloaded', self._config_values)
        
        self.logger.info(f"Loaded {len(self._config_values)} configuration values")
        return self._config_values
    
    async def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value."""
        # Check cache first
        if self._cache_enabled and key_path in self._cache:
            cache_value, timestamp = self._cache[key_path]
            if (datetime.now() - timestamp).seconds < self._cache_ttl:
                return cache_value
        
        # Get from configuration values
        config_value = self._config_values.get(key_path)
        
        if config_value:
            value = config_value.value
            
            # Apply type conversion if needed
            schema = self._schema.get(key_path)
            if schema and schema.type_hint != type(value):
                value = await self._convert_type(value, schema.type_hint)
            
            # Cache the value
            if self._cache_enabled:
                self._cache[key_path] = (value, datetime.now())
            
            return value
        
        # Check for environment variable
        schema = self._schema.get(key_path)
        if schema and schema.environment_mapping:
            env_value = os.getenv(schema.environment_mapping)
            if env_value is not None:
                return await self._convert_type(env_value, schema.type_hint or str)
        
        # Return default
        if default is not None:
            return default
        
        if schema:
            return schema.default
        
        return None
    
    async def set(self, key_path: str, value: Any, persist: bool = True) -> bool:
        """Set configuration value."""
        try:
            # Validate the value
            if not await self._validate_value(key_path, value):
                return False
            
            # Get or create config value
            config_value = self._config_values.get(key_path)
            if not config_value:
                # Create default source
                source = ConfigSource(
                    path="runtime",
                    format=ConfigFormat.JSON,
                    scope=ConfigScope.USER,
                    priority=0,
                    required=False
                )
                config_value = ConfigValue(value, source)
            
            # Update value
            config_value.value = value
            config_value.last_updated = datetime.now()
            
            self._config_values[key_path] = config_value
            
            # Clear cache
            if self._cache_enabled and key_path in self._cache:
                del self._cache[key_path]
            
            # Persist if requested
            if persist:
                await self._persist_value(key_path, config_value)
            
            # Trigger change event
            self._trigger_event('config_changed', {
                'key': key_path,
                'value': value,
                'config_value': config_value
            })
            
            self.logger.debug(f"Set config value: {key_path} = {value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting config value {key_path}: {e}")
            return False
    
    async def delete(self, key_path: str) -> bool:
        """Delete configuration value."""
        if key_path in self._config_values:
            del self._config_values[key_path]
            
            # Clear cache
            if self._cache_enabled and key_path in self._cache:
                del self._cache[key_path]
            
            # Trigger change event
            self._trigger_event('config_changed', {
                'key': key_path,
                'action': 'deleted'
            })
            
            self.logger.debug(f"Deleted config value: {key_path}")
            return True
        
        return False
    
    async def exists(self, key_path: str) -> bool:
        """Check if configuration key exists."""
        return key_path in self._config_values
    
    async def get_all(self, scope: ConfigScope = None) -> Dict[str, Any]:
        """Get all configuration values."""
        if scope:
            return {
                key: config_value.value
                for key, config_value in self._config_values.items()
                if config_value.source.scope == scope
            }
        
        return {key: config_value.value for key, config_value in self._config_values.items()}
    
    async def get_schema(self, key_path: str) -> Optional[ConfigSchema]:
        """Get configuration schema."""
        return self._schema.get(key_path)
    
    async def validate_all(self) -> Dict[str, List[str]]:
        """Validate all configuration values."""
        results = {}
        
        for key_path in self._config_values.keys():
            errors = await self._validate_configuration_key(key_path)
            if errors:
                results[key_path] = errors
        
        return results
    
    def register_validator(self, name: str, validator_func: Callable) -> None:
        """Register a custom validator."""
        self._validators[name] = validator_func
        self.logger.debug(f"Registered validator: {name}")
    
    def register_custom_type(self, type_class: type, converter_func: Callable) -> None:
        """Register a custom type converter."""
        self._custom_types[type_class] = converter_func
        self.logger.debug(f"Registered custom type: {type_class.__name__}")
    
    def on_config_changed(self, callback: Callable) -> None:
        """Register config change event handler."""
        self._event_handlers['config_changed'].append(callback)
    
    def on_config_reloaded(self, callback: Callable) -> None:
        """Register config reload event handler."""
        self._event_handlers['config_reloaded'].append(callback)
    
    async def _load_source(self, source: ConfigSource, force_reload: bool = False) -> None:
        """Load configuration from a source."""
        try:
            if source.path.startswith("http"):
                content = await self._load_from_http(source.path)
            elif source.path == "environment":
                content = self._load_from_environment()
            elif source.path == "runtime":
                content = {}  # Runtime config (not persisted)
            else:
                content = await self._load_from_file(source.path)
            
            # Parse content based on format
            parsed_content = await self._parse_content(content, source.format)
            
            # Update source metadata
            source.last_loaded = datetime.now()
            
            # Process configuration entries
            await self._process_parsed_content(parsed_content, source)
            
            # Start file watching if enabled
            if source.reload_on_change and not source.path.startswith("http") and source.path != "environment":
                await self._start_file_watcher(source)
            
            self.logger.debug(f"Loaded config source: {source.path}")
            
        except Exception as e:
            self.logger.error(f"Error loading config source {source.path}: {e}")
            if source.required:
                raise
    
    async def _load_from_file(self, path: str) -> str:
        """Load configuration from file."""
        file_path = Path(path)
        
        if not file_path.is_absolute():
            file_path = self.config_dir / file_path
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    async def _load_from_http(self, url: str) -> str:
        """Load configuration from HTTP endpoint."""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    raise Exception(f"HTTP error: {response.status}")
    
    def _load_from_environment(self) -> str:
        """Load configuration from environment variables."""
        config_dict = {}
        for key, value in os.environ.items():
            if key.startswith("WEBOPS_"):
                config_key = key[7:].lower().replace("_", ".")
                config_dict[config_key] = value
        
        return json.dumps(config_dict, indent=2)
    
    async def _parse_content(self, content: str, format: ConfigFormat) -> Dict[str, Any]:
        """Parse configuration content based on format."""
        try:
            if format == ConfigFormat.JSON:
                return json.loads(content)
            elif format in [ConfigFormat.YAML, ConfigFormat.YAMLML]:
                return yaml.safe_load(content) or {}
            elif format == ConfigFormat.INI:
                parser = ConfigParser()
                parser.read_string(content)
                return {section: dict(parser[section]) for section in parser.sections()}
            elif format == ConfigFormat.TOML:
                import toml
                return toml.loads(content)
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            self.logger.error(f"Error parsing configuration content: {e}")
            raise
    
    async def _process_parsed_content(
        self,
        content: Dict[str, Any],
        source: ConfigSource
    ) -> None:
        """Process parsed configuration content."""
        flat_content = self._flatten_dict(content)
        
        for key_path, value in flat_content.items():
            # Check if key has schema
            schema = self._schema.get(key_path)
            
            # Create config value
            config_value = ConfigValue(
                value=value,
                source=source,
                type_hint=schema.type_hint if schema else type(value),
                description=schema.description if schema else "",
                validator=schema.validator if schema else None,
                default=schema.default if schema else None,
                encrypted=source.encrypted or (schema.sensitive if schema else False)
            )
            
            self._config_values[key_path] = config_value
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    async def _validate_configuration(self) -> None:
        """Validate entire configuration."""
        validation_errors = await self.validate_all()
        
        if validation_errors:
            self._trigger_event('validation_failed', validation_errors)
            
            for key_path, errors in validation_errors.items():
                for error in errors:
                    self.logger.error(f"Configuration validation error for {key_path}: {error}")
            
            raise ValueError("Configuration validation failed")
    
    async def _validate_configuration_key(self, key_path: str) -> List[str]:
        """Validate a specific configuration key."""
        errors = []
        config_value = self._config_values.get(key_path)
        schema = self._schema.get(key_path)
        
        if not config_value:
            if schema and schema.required:
                errors.append(f"Required configuration key missing: {key_path}")
            return errors
        
        # Check if value is set when required
        if schema and schema.required and config_value.value is None:
            errors.append(f"Required configuration key is None: {key_path}")
        
        # Validate against schema
        if schema:
            try:
                # Check dependencies
                for dep_key in schema.depends_on:
                    if dep_key not in self._config_values:
                        errors.append(f"Missing dependency: {dep_key} required for {key_path}")
                
                # Apply validation rules
                if 'min' in schema.validation_rules and config_value.value < schema.validation_rules['min']:
                    errors.append(f"Value below minimum: {schema.validation_rules['min']}")
                
                if 'max' in schema.validation_rules and config_value.value > schema.validation_rules['max']:
                    errors.append(f"Value above maximum: {schema.validation_rules['max']}")
                
                if 'pattern' in schema.validation_rules:
                    import re
                    pattern = schema.validation_rules['pattern']
                    if not re.match(pattern, str(config_value.value)):
                        errors.append(f"Value doesn't match pattern: {pattern}")
                
                # Custom validation
                if schema.validator:
                    schema.validator(config_value.value)
            
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")
        
        return errors
    
    async def _validate_value(self, key_path: str, value: Any) -> bool:
        """Validate a value for a configuration key."""
        validation_errors = await self._validate_configuration_key(key_path)
        
        if validation_errors:
            self.logger.error(f"Validation failed for {key_path}: {validation_errors}")
            return False
        
        return True
    
    async def _convert_type(self, value: Any, target_type: type) -> Any:
        """Convert value to target type."""
        if value is None:
            return None
        
        if isinstance(value, target_type):
            return value
        
        # Handle special types
        if target_type == bool:
            if isinstance(value, str):
                return value.lower() in ['true', '1', 'yes', 'on']
            return bool(value)
        elif target_type == list:
            if isinstance(value, str):
                return [item.strip() for item in value.split(',')]
            return list(value)
        elif target_type == dict:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return {}
            return dict(value)
        
        # Try direct conversion
        try:
            return target_type(value)
        except (ValueError, TypeError):
            self.logger.warning(f"Failed to convert {value} to {target_type}")
            return value
    
    async def _persist_value(self, key_path: str, config_value: ConfigValue) -> None:
        """Persist configuration value to appropriate source."""
        # This is a simplified implementation
        # In practice, you'd want to write back to the original source
        
        runtime_config = {
            key: cv.value
            for key, cv in self._config_values.items()
            if cv.source.path == "runtime"
        }
        
        runtime_file = self.config_dir / "runtime.json"
        with open(runtime_file, 'w', encoding='utf-8') as f:
            json.dump(runtime_config, f, indent=2, default=str)
    
    async def _start_file_watcher(self, source: ConfigSource) -> None:
        """Start watching a file for changes."""
        import asyncio
        
        async def watch_file():
            file_path = Path(source.path)
            if not file_path.is_absolute():
                file_path = self.config_dir / file_path
            
            if not file_path.exists():
                return
            
            last_modified = file_path.stat().st_mtime
            
            while True:
                try:
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                    if file_path.exists():
                        current_modified = file_path.stat().st_mtime
                        if current_modified != last_modified:
                            self.logger.info(f"Configuration file changed: {source.path}")
                            await self._load_source(source, force_reload=True)
                            last_modified = current_modified
                
                except Exception as e:
                    self.logger.error(f"Error watching file {source.path}: {e}")
                    break
        
        if source.path not in self._watchers:
            task = asyncio.create_task(watch_file())
            self._watchers[source.path] = task
    
    def _trigger_event(self, event_type: str, data: Any) -> None:
        """Trigger configuration event."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                self.logger.error(f"Error in event handler for {event_type}: {e}")
    
    def _detect_format(self, path: str) -> ConfigFormat:
        """Detect configuration format from file path."""
        ext = Path(path).suffix.lower()
        
        format_mapping = {
            '.json': ConfigFormat.JSON,
            '.yaml': ConfigFormat.YAML,
            '.yml': ConfigFormat.YAMLML,
            '.ini': ConfigFormat.INI,
            '.env': ConfigFormat.ENV,
            '.toml': ConfigFormat.TOML,
        }
        
        return format_mapping.get(ext, ConfigFormat.JSON)
    
    async def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary."""
        summary = {
            'total_sources': len(self._config_sources),
            'total_values': len(self._config_values),
            'sources_by_scope': {},
            'sources_by_format': {},
            'schema_count': len(self._schema),
            'cache_enabled': self._cache_enabled,
            'cache_size': len(self._cache),
        }
        
        # Count by scope
        for source in self._config_sources:
            scope = source.scope.value
            summary['sources_by_scope'][scope] = summary['sources_by_scope'].get(scope, 0) + 1
        
        # Count by format
        for source in self._config_sources:
            format_name = source.format.value
            summary['sources_by_format'][format_name] = summary['sources_by_format'].get(format_name, 0) + 1
        
        return summary


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


async def load_default_config() -> ConfigurationManager:
    """Load default configuration sources."""
    config_manager = get_config_manager()
    
    # Add default configuration sources
    config_manager.add_config_source(
        "config.yaml",
        format=ConfigFormat.YAML,
        scope=ConfigScope.SYSTEM,
        priority=10
    )
    
    config_manager.add_config_source(
        "agents.yaml",
        format=ConfigFormat.YAML,
        scope=ConfigScope.AGENT,
        priority=9
    )
    
    config_manager.add_config_source(
        "environment",
        scope=ConfigScope.ENVIRONMENT,
        priority=8
    )
    
    config_manager.add_config_source(
        "user.yaml",
        format=ConfigFormat.YAML,
        scope=ConfigScope.USER,
        priority=7,
        required=False
    )
    
    # Register common configuration schemas
    await _register_default_schemas(config_manager)
    
    return config_manager


async def _register_default_schemas(config_manager: ConfigurationManager) -> None:
    """Register default configuration schemas."""
    # Agent configuration
    config_manager.register_schema(
        "agent.name",
        str,
        required=True,
        description="Name of the agent"
    )
    
    config_manager.register_schema(
        "agent.version",
        str,
        default="1.0.0",
        description="Agent version"
    )
    
    config_manager.register_schema(
        "agent.debug",
        bool,
        default=False,
        description="Enable debug mode"
    )
    
    config_manager.register_schema(
        "agent.log_level",
        str,
        default="INFO",
        validation_rules={'pattern': r'^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$'},
        description="Logging level"
    )
    
    # Memory configuration
    config_manager.register_schema(
        "memory.max_episodic",
        int,
        default=10000,
        validation_rules={'min': 100, 'max': 1000000},
        description="Maximum episodic memories"
    )
    
    config_manager.register_schema(
        "memory.max_semantic",
        int,
        default=50000,
        validation_rules={'min': 1000, 'max': 10000000},
        description="Maximum semantic memories"
    )
    
    # Skills configuration
    config_manager.register_schema(
        "skills.enabled",
        list,
        default=["communication", "problem_solving", "monitoring"],
        description="List of enabled skills"
    )
    
    # Communication configuration
    config_manager.register_schema(
        "communication.host",
        str,
        default="localhost",
        description="Communication host"
    )
    
    config_manager.register_schema(
        "communication.port",
        int,
        default=8000,
        validation_rules={'min': 1024, 'max': 65535},
        description="Communication port"
    )
    
    # Security configuration
    config_manager.register_schema(
        "security.encryption_key",
        str,
        sensitive=True,
        description="Encryption key for sensitive data"
    )


if __name__ == "__main__":
    async def main():
        """Example usage of configuration manager."""
        config_manager = await load_default_config()
        
        # Load configuration
        await config_manager.load_all()
        
        # Get configuration values
        agent_name = await config_manager.get("agent.name", "default_agent")
        debug_mode = await config_manager.get("agent.debug", False)
        
        print(f"Agent Name: {agent_name}")
        print(f"Debug Mode: {debug_mode}")
        
        # Set a configuration value
        await config_manager.set("agent.custom_setting", "test_value")
        
        # Get configuration summary
        summary = await config_manager.get_config_summary()
        print(f"Config Summary: {summary}")
    
    asyncio.run(main())