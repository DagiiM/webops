"""
Database adapter factory and registry.

"Database Models" section
"""

import logging
from typing import Dict, Type, Optional

from .base import DatabaseAdapter, ConnectionConfig, DatabaseType, ConfigurationException
from .postgresql import PostgreSQLAdapter
from .mongodb import MongoDBAdapter
from .sqlite import SQLiteAdapter
from .mysql import MySQLAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Registry for database adapters.

    Allows dynamic registration and retrieval of adapter classes.
    """

    def __init__(self):
        """Initialize registry with built-in adapters."""
        self._adapters: Dict[DatabaseType, Type[DatabaseAdapter]] = {}

        # Register built-in adapters
        self.register(DatabaseType.POSTGRESQL, PostgreSQLAdapter)
        self.register(DatabaseType.MONGODB, MongoDBAdapter)
        self.register(DatabaseType.SQLITE, SQLiteAdapter)
        self.register(DatabaseType.MYSQL, MySQLAdapter)

    def register(
        self,
        db_type: DatabaseType,
        adapter_class: Type[DatabaseAdapter]
    ) -> None:
        """
        Register a new adapter.

        Args:
            db_type: Database type identifier
            adapter_class: Adapter class (must inherit from DatabaseAdapter)
        """
        if not issubclass(adapter_class, DatabaseAdapter):
            raise ValueError(
                f"{adapter_class.__name__} must inherit from DatabaseAdapter"
            )

        self._adapters[db_type] = adapter_class
        logger.info(f"Registered adapter: {db_type.value} -> {adapter_class.__name__}")

    def get_adapter_class(self, db_type: DatabaseType) -> Type[DatabaseAdapter]:
        """
        Get adapter class for database type.

        Args:
            db_type: Database type

        Returns:
            Adapter class

        Raises:
            ConfigurationException: If adapter not found
        """
        adapter_class = self._adapters.get(db_type)
        if not adapter_class:
            available = ", ".join(t.value for t in self._adapters.keys())
            raise ConfigurationException(
                f"No adapter registered for '{db_type.value}'. "
                f"Available: {available}"
            )
        return adapter_class

    def list_adapters(self) -> Dict[DatabaseType, Dict[str, str]]:
        """
        List all registered adapters with metadata.

        Returns:
            Dictionary mapping database types to adapter info
        """
        return {
            db_type: {
                'class': adapter_class.__name__,
                'dependencies': getattr(adapter_class, 'DEPENDENCIES', []),
                'install_command': getattr(adapter_class, 'INSTALL_COMMAND', ''),
                'description': getattr(adapter_class, 'DESCRIPTION', '')
            }
            for db_type, adapter_class in self._adapters.items()
        }


# Global registry instance
adapter_registry = AdapterRegistry()


class DatabaseFactory:
    """
    Factory for creating database adapter instances.

    Uses the adapter registry to instantiate the correct adapter
    based on configuration.
    """

    def __init__(self, registry: Optional[AdapterRegistry] = None):
        """
        Initialize factory.

        Args:
            registry: Adapter registry (uses global if not provided)
        """
        self.registry = registry or adapter_registry

    def create_adapter(self, config: ConnectionConfig) -> DatabaseAdapter:
        """
        Create and initialize a database adapter.

        Args:
            config: Connection configuration

        Returns:
            Initialized adapter instance

        Raises:
            ConfigurationException: If adapter cannot be created
        """
        adapter_class = self.registry.get_adapter_class(config.db_type)

        try:
            adapter = adapter_class(config)
            logger.info(f"Created adapter: {config.db_type.value}")
            return adapter
        except Exception as e:
            raise ConfigurationException(
                f"Failed to create {config.db_type.value} adapter: {e}"
            )

    def get_available_databases(self) -> Dict[DatabaseType, Dict[str, str]]:
        """
        Get list of available database types.

        Returns:
            Dictionary with database metadata
        """
        return self.registry.list_adapters()