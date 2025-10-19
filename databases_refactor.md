# Database Abstraction Layer Refactor

## Overview

Refactor WebOps database management to support **multiple database engines** (PostgreSQL, MongoDB, MySQL, SQLite, Pinecone, Redis, etc.) through a clean, extensible abstraction layer. Users should be able to select their preferred database through the web UI without modifying code.

---

## 1. Architecture Goals

### Core Principles

1. **Adapter Pattern**: Encapsulate database-specific logic in dedicated adapter classes
2. **Factory Pattern with Registry**: Dynamically instantiate the correct adapter based on user selection
3. **Strict Common Interface**: All adapters implement a consistent `DatabaseAdapter` interface
4. **Unified Error Handling**: Translate database-specific exceptions into common WebOps exceptions
5. **UI-Driven Configuration**: Users select databases through the web interface, not config files
6. **Dependency Management**: Display required dependencies with installation instructions in the UI

### Design Alignment

- **SOLID Principles**: Single Responsibility, Open/Closed, Dependency Inversion
- **WebOps Philosophy**: Minimal dependencies, security-first, zero-npm frontend
- **Design System**: Use `variables.css` and `main.css` for consistent UI styling

---

## 2. Implementation Blueprint

### 2.1 Core Interface & Exceptions

**File**: `control-panel/apps/databases/adapters/base.py`

```python
"""
Base adapter interface and exceptions for database abstraction.

Reference: CLAUDE.md "Database Models" section
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Exception Hierarchy
# ═══════════════════════════════════════════════════════════════

class DatabaseException(Exception):
    """Base exception for all database errors."""
    pass


class ConnectionException(DatabaseException):
    """Raised when database connection fails."""
    pass


class QueryExecutionException(DatabaseException):
    """Raised when query execution fails."""
    pass


class TransactionException(DatabaseException):
    """Raised when transaction operations fail."""
    pass


class ConfigurationException(DatabaseException):
    """Raised when database configuration is invalid."""
    pass


# ═══════════════════════════════════════════════════════════════
# Configuration Models
# ═══════════════════════════════════════════════════════════════

class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"
    REDIS = "redis"
    PINECONE = "pinecone"


@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    db_type: DatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None  # Will be encrypted

    # Cloud database configs
    api_key: Optional[str] = None  # For Pinecone, etc.
    environment: Optional[str] = None
    uri: Optional[str] = None  # For MongoDB connection strings

    # Advanced options
    ssl_enabled: bool = False
    connection_timeout: int = 30
    pool_size: int = 5

    def validate(self) -> None:
        """Validate configuration based on database type."""
        if self.db_type == DatabaseType.POSTGRESQL:
            required = ['host', 'port', 'database', 'username', 'password']
        elif self.db_type == DatabaseType.MONGODB:
            required = ['uri'] if self.uri else ['host', 'port', 'database']
        elif self.db_type == DatabaseType.SQLITE:
            required = ['database']  # Database is the file path
        elif self.db_type == DatabaseType.PINECONE:
            required = ['api_key', 'environment']
        elif self.db_type == DatabaseType.REDIS:
            required = ['host', 'port']
        else:
            raise ConfigurationException(f"Unknown database type: {self.db_type}")

        for field in required:
            if getattr(self, field, None) is None:
                raise ConfigurationException(
                    f"Missing required field '{field}' for {self.db_type}"
                )


@dataclass
class QueryResult:
    """Unified query result container."""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    rows_affected: int = 0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════
# Database Adapter Interface
# ═══════════════════════════════════════════════════════════════

class DatabaseAdapter(ABC):
    """
    Abstract base class for all database adapters.

    All concrete adapters MUST implement this interface.
    """

    def __init__(self, config: ConnectionConfig):
        """
        Initialize adapter with configuration.

        Args:
            config: Connection configuration
        """
        config.validate()
        self.config = config
        self.connection = None
        self._in_transaction = False

    @abstractmethod
    def connect(self) -> None:
        """
        Establish database connection.

        Raises:
            ConnectionException: If connection fails
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close database connection.

        Raises:
            ConnectionException: If disconnect fails
        """
        pass

    @abstractmethod
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute a database query.

        Args:
            query: SQL/query string
            parameters: Query parameters (for parameterized queries)

        Returns:
            QueryResult with data and metadata

        Raises:
            QueryExecutionException: If query fails
        """
        pass

    @abstractmethod
    def start_transaction(self) -> None:
        """
        Begin a database transaction.

        Raises:
            TransactionException: If transaction cannot be started
        """
        pass

    @abstractmethod
    def commit_transaction(self) -> None:
        """
        Commit current transaction.

        Raises:
            TransactionException: If commit fails
        """
        pass

    @abstractmethod
    def rollback_transaction(self) -> None:
        """
        Rollback current transaction.

        Raises:
            TransactionException: If rollback fails
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if database connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get database metadata (version, capabilities, etc.).

        Returns:
            Dictionary with database metadata
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None and self._in_transaction:
            self.rollback_transaction()
        self.disconnect()
```

### 2.2 Concrete Adapter: PostgreSQL

**File**: `control-panel/apps/databases/adapters/postgresql.py`

```python
"""
PostgreSQL database adapter.

Reference: CLAUDE.md "Database Models" section
"""

import logging
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

from .base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    ConnectionException,
    QueryExecutionException,
    TransactionException,
)

logger = logging.getLogger(__name__)


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter with connection pooling."""

    # Class-level dependency information
    DEPENDENCIES = ["psycopg2-binary>=2.9.0"]
    INSTALL_COMMAND = "pip install psycopg2-binary"
    DESCRIPTION = "High-performance relational database (recommended for production)"

    def __init__(self, config: ConnectionConfig):
        """Initialize PostgreSQL adapter."""
        if psycopg2 is None:
            raise ConnectionException(
                "psycopg2 is not installed. "
                f"Install with: {self.INSTALL_COMMAND}"
            )
        super().__init__(config)
        self.pool: Optional[pool.SimpleConnectionPool] = None

    def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            self.pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=self.config.pool_size,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.username,
                password=self.config.password,
                connect_timeout=self.config.connection_timeout,
                sslmode='require' if self.config.ssl_enabled else 'prefer'
            )

            # Test connection
            conn = self.pool.getconn()
            self.pool.putconn(conn)

            logger.info(f"Connected to PostgreSQL: {self.config.database}")
        except psycopg2.Error as e:
            raise ConnectionException(f"PostgreSQL connection failed: {e}")

    def disconnect(self) -> None:
        """Close all connections in pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("Disconnected from PostgreSQL")

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute SQL query with parameters."""
        if not self.pool:
            raise ConnectionException("Not connected to database")

        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Use parameterized queries to prevent SQL injection
                cursor.execute(query, parameters or {})

                # Handle SELECT queries
                if cursor.description:
                    data = [dict(row) for row in cursor.fetchall()]
                    return QueryResult(
                        success=True,
                        data=data,
                        rows_affected=cursor.rowcount
                    )

                # Handle INSERT/UPDATE/DELETE
                if not self._in_transaction:
                    conn.commit()

                return QueryResult(
                    success=True,
                    rows_affected=cursor.rowcount
                )

        except psycopg2.Error as e:
            if conn and not self._in_transaction:
                conn.rollback()
            logger.error(f"Query execution failed: {e}")
            raise QueryExecutionException(f"PostgreSQL query failed: {e}")

        finally:
            if conn:
                self.pool.putconn(conn)

    def start_transaction(self) -> None:
        """Begin transaction."""
        if self._in_transaction:
            raise TransactionException("Transaction already in progress")

        self._in_transaction = True
        self.connection = self.pool.getconn()
        logger.debug("Transaction started")

    def commit_transaction(self) -> None:
        """Commit transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.commit()
            logger.debug("Transaction committed")
        except psycopg2.Error as e:
            raise TransactionException(f"Commit failed: {e}")
        finally:
            self.pool.putconn(self.connection)
            self.connection = None
            self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.rollback()
            logger.debug("Transaction rolled back")
        except psycopg2.Error as e:
            logger.error(f"Rollback failed: {e}")
        finally:
            self.pool.putconn(self.connection)
            self.connection = None
            self._in_transaction = False

    def health_check(self) -> bool:
        """Check PostgreSQL connection health."""
        try:
            result = self.execute_query("SELECT 1")
            return result.success
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """Get PostgreSQL version and metadata."""
        try:
            result = self.execute_query("SELECT version()")
            version = result.data[0]['version'] if result.data else 'Unknown'

            return {
                'type': 'PostgreSQL',
                'version': version,
                'host': self.config.host,
                'port': self.config.port,
                'database': self.config.database,
                'ssl_enabled': self.config.ssl_enabled,
                'pool_size': self.config.pool_size
            }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {'type': 'PostgreSQL', 'error': str(e)}
```

### 2.3 Concrete Adapter: MongoDB

**File**: `control-panel/apps/databases/adapters/mongodb.py`

```python
"""
MongoDB database adapter.

Reference: CLAUDE.md "Database Models" section
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:
    MongoClient = None

from .base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    ConnectionException,
    QueryExecutionException,
    TransactionException,
)

logger = logging.getLogger(__name__)


class MongoDBAdapter(DatabaseAdapter):
    """MongoDB NoSQL database adapter."""

    DEPENDENCIES = ["pymongo>=4.0.0"]
    INSTALL_COMMAND = "pip install pymongo"
    DESCRIPTION = "Flexible NoSQL document database for unstructured data"

    def __init__(self, config: ConnectionConfig):
        """Initialize MongoDB adapter."""
        if MongoClient is None:
            raise ConnectionException(
                "pymongo is not installed. "
                f"Install with: {self.INSTALL_COMMAND}"
            )
        super().__init__(config)
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self) -> None:
        """Connect to MongoDB."""
        try:
            # Use URI if provided, otherwise construct from parts
            if self.config.uri:
                self.client = MongoClient(
                    self.config.uri,
                    serverSelectionTimeoutMS=self.config.connection_timeout * 1000
                )
            else:
                self.client = MongoClient(
                    host=self.config.host,
                    port=self.config.port,
                    username=self.config.username,
                    password=self.config.password,
                    serverSelectionTimeoutMS=self.config.connection_timeout * 1000,
                    tls=self.config.ssl_enabled
                )

            # Get database reference
            self.db = self.client[self.config.database]

            # Test connection
            self.client.server_info()

            logger.info(f"Connected to MongoDB: {self.config.database}")

        except PyMongoError as e:
            raise ConnectionException(f"MongoDB connection failed: {e}")

    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute MongoDB query.

        Note: For MongoDB, 'query' should be a JSON string representing
        the operation (e.g., '{"operation": "find", "collection": "users", "filter": {...}}')
        """
        if not self.db:
            raise ConnectionException("Not connected to database")

        try:
            import json
            query_dict = json.loads(query)

            operation = query_dict.get('operation')
            collection_name = query_dict.get('collection')

            if not collection_name:
                raise QueryExecutionException("Collection name required")

            collection = self.db[collection_name]

            # Handle different operations
            if operation == 'find':
                filter_query = query_dict.get('filter', {})
                cursor = collection.find(filter_query)
                data = [dict(doc) for doc in cursor]
                return QueryResult(success=True, data=data, rows_affected=len(data))

            elif operation == 'insert_one':
                document = query_dict.get('document', {})
                result = collection.insert_one(document)
                return QueryResult(success=True, rows_affected=1)

            elif operation == 'update_many':
                filter_query = query_dict.get('filter', {})
                update = query_dict.get('update', {})
                result = collection.update_many(filter_query, update)
                return QueryResult(success=True, rows_affected=result.modified_count)

            elif operation == 'delete_many':
                filter_query = query_dict.get('filter', {})
                result = collection.delete_many(filter_query)
                return QueryResult(success=True, rows_affected=result.deleted_count)

            else:
                raise QueryExecutionException(f"Unknown operation: {operation}")

        except PyMongoError as e:
            logger.error(f"MongoDB query failed: {e}")
            raise QueryExecutionException(f"MongoDB query failed: {e}")

    def start_transaction(self) -> None:
        """Start MongoDB transaction (requires replica set)."""
        if self._in_transaction:
            raise TransactionException("Transaction already in progress")

        try:
            self.connection = self.client.start_session()
            self.connection.start_transaction()
            self._in_transaction = True
            logger.debug("Transaction started")
        except PyMongoError as e:
            raise TransactionException(f"Failed to start transaction: {e}")

    def commit_transaction(self) -> None:
        """Commit MongoDB transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.commit_transaction()
            logger.debug("Transaction committed")
        except PyMongoError as e:
            raise TransactionException(f"Commit failed: {e}")
        finally:
            self.connection.end_session()
            self.connection = None
            self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback MongoDB transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.abort_transaction()
            logger.debug("Transaction rolled back")
        except PyMongoError as e:
            logger.error(f"Rollback failed: {e}")
        finally:
            self.connection.end_session()
            self.connection = None
            self._in_transaction = False

    def health_check(self) -> bool:
        """Check MongoDB connection health."""
        try:
            self.client.server_info()
            return True
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """Get MongoDB version and metadata."""
        try:
            server_info = self.client.server_info()
            return {
                'type': 'MongoDB',
                'version': server_info.get('version'),
                'database': self.config.database,
                'host': self.config.host or 'URI',
                'port': self.config.port
            }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {'type': 'MongoDB', 'error': str(e)}
```

### 2.4 Adapter Registry & Factory

**File**: `control-panel/apps/databases/adapters/factory.py`

```python
"""
Database adapter factory and registry.

Reference: CLAUDE.md "Database Models" section
"""

import logging
from typing import Dict, Type, Optional

from .base import DatabaseAdapter, ConnectionConfig, DatabaseType, ConfigurationException
from .postgresql import PostgreSQLAdapter
from .mongodb import MongoDBAdapter

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
```

---

## 3. Database Model Updates

**File**: `control-panel/apps/databases/models.py`

```python
"""
Database models for WebOps.

Reference: CLAUDE.md "Database Models" section
"""

from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from apps.deployments.models import Deployment
from .adapters.base import DatabaseType


class Database(BaseModel):
    """
    Multi-database credentials and configuration.

    Supports PostgreSQL, MongoDB, MySQL, SQLite, Redis, Pinecone, etc.
    """

    # Basic Info
    name = models.CharField(max_length=100, unique=True)
    db_type = models.CharField(
        max_length=50,
        choices=[(t.value, t.value.title()) for t in DatabaseType],
        default=DatabaseType.POSTGRESQL.value
    )

    # Connection Details
    host = models.CharField(max_length=255, default='localhost', blank=True)
    port = models.IntegerField(null=True, blank=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=500, blank=True)  # Encrypted

    # Database/Collection Name
    database_name = models.CharField(max_length=100, blank=True)

    # Cloud Database Fields
    api_key = models.CharField(max_length=500, blank=True)  # Encrypted
    environment = models.CharField(max_length=100, blank=True)
    connection_uri = models.TextField(blank=True)

    # Advanced Options
    ssl_enabled = models.BooleanField(default=False)
    connection_timeout = models.IntegerField(default=30)
    pool_size = models.IntegerField(default=5)

    # Metadata
    is_active = models.BooleanField(default=True)
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='databases',
        null=True,
        blank=True
    )

    # Dependency Info (JSON field for storing install commands, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.db_type})"

    def clean(self):
        """Validate database configuration."""
        super().clean()

        # Validate required fields based on database type
        db_type = DatabaseType(self.db_type)

        if db_type == DatabaseType.POSTGRESQL:
            required = ['host', 'port', 'database_name', 'username', 'password']
            for field in required:
                if not getattr(self, field.replace('database_name', 'database_name'), None):
                    raise ValidationError(f"{field} is required for PostgreSQL")

        elif db_type == DatabaseType.MONGODB:
            if not self.connection_uri and not (self.host and self.port):
                raise ValidationError(
                    "Either connection_uri or host+port is required for MongoDB"
                )

        elif db_type == DatabaseType.SQLITE:
            if not self.database_name:
                raise ValidationError("database_name (file path) is required for SQLite")

        elif db_type == DatabaseType.PINECONE:
            if not self.api_key or not self.environment:
                raise ValidationError("api_key and environment are required for Pinecone")

    def get_connection_string(self, decrypted_password: str = None) -> str:
        """
        Generate connection string for the database.

        Args:
            decrypted_password: Decrypted password (if None, uses masked password)

        Returns:
            Database connection string
        """
        password = decrypted_password or '****'
        db_type = DatabaseType(self.db_type)

        if db_type == DatabaseType.POSTGRESQL:
            return f"postgresql://{self.username}:{password}@{self.host}:{self.port}/{self.database_name}"

        elif db_type == DatabaseType.MONGODB:
            if self.connection_uri:
                return self.connection_uri.replace(self.password, password)
            return f"mongodb://{self.username}:{password}@{self.host}:{self.port}/{self.database_name}"

        elif db_type == DatabaseType.MYSQL:
            return f"mysql://{self.username}:{password}@{self.host}:{self.port}/{self.database_name}"

        elif db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.database_name}"

        elif db_type == DatabaseType.REDIS:
            return f"redis://{self.host}:{self.port}"

        return "Connection string not available"

    class Meta:
        db_table = 'databases'
        verbose_name = 'Database'
        verbose_name_plural = 'Databases'
        ordering = ['-created_at']
```

---

## 4. Web UI for Database Selection

### 4.1 View for Database Creation

**File**: `control-panel/apps/databases/views.py`

Add view for creating databases with type selection:

```python
from django.views.generic import CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Database
from .adapters.factory import DatabaseFactory
from .forms import DatabaseForm


class DatabaseCreateView(LoginRequiredMixin, CreateView):
    """View for creating a new database."""
    model = Database
    form_class = DatabaseForm
    template_name = 'databases/database_create.html'
    success_url = '/databases/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get available database types with metadata
        factory = DatabaseFactory()
        context['available_databases'] = factory.get_available_databases()

        return context
```

### 4.2 Template for Database Selection

**File**: `control-panel/templates/databases/database_create.html`

```html
{% extends "base.html" %}
{% load static %}

{% block title %}Create Database - WebOps{% endblock %}

{% block content %}
<div class="webops-container">
    <div class="webops-card">
        <div class="webops-card-header">
            <h1 class="webops-h1">Create New Database</h1>
            <p class="webops-text-secondary">Select your preferred database engine and configure connection details</p>
        </div>

        <div class="webops-card-body">
            <form method="post" id="database-form">
                {% csrf_token %}

                <!-- Database Type Selection -->
                <div class="webops-form-group">
                    <label for="db_type" class="webops-label">Database Type</label>
                    <select name="db_type" id="db_type" class="webops-select" required>
                        <option value="">Select Database Engine...</option>
                        {% for db_type, info in available_databases.items %}
                        <option value="{{ db_type.value }}"
                                data-dependencies="{{ info.dependencies|join:', ' }}"
                                data-install="{{ info.install_command }}"
                                data-description="{{ info.description }}">
                            {{ db_type.value|title }}
                        </option>
                        {% endfor %}
                    </select>
                    <small class="webops-text-tertiary" id="db-description"></small>
                </div>

                <!-- Dependency Warning (Hidden by default) -->
                <div id="dependency-warning" class="webops-alert webops-alert-info" style="display: none;">
                    <div class="webops-alert-icon">
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
                        </svg>
                    </div>
                    <div class="webops-alert-content">
                        <h4 class="webops-alert-title">Dependencies Required</h4>
                        <p id="dependency-list"></p>
                        <div class="webops-code-block" style="margin-top: 12px;">
                            <code id="install-command"></code>
                        </div>
                    </div>
                </div>

                <!-- Connection Configuration (Dynamic based on DB type) -->
                <div id="connection-config">
                    <!-- Common Fields -->
                    <div class="webops-form-group">
                        <label for="name" class="webops-label">Database Name</label>
                        <input type="text" name="name" id="name" class="webops-input" required>
                    </div>

                    <!-- PostgreSQL/MySQL Fields -->
                    <div class="db-config db-config-relational" style="display: none;">
                        <div class="webops-form-row">
                            <div class="webops-form-group">
                                <label for="host" class="webops-label">Host</label>
                                <input type="text" name="host" id="host" class="webops-input" value="localhost">
                            </div>
                            <div class="webops-form-group">
                                <label for="port" class="webops-label">Port</label>
                                <input type="number" name="port" id="port" class="webops-input">
                            </div>
                        </div>

                        <div class="webops-form-group">
                            <label for="database_name" class="webops-label">Database Name</label>
                            <input type="text" name="database_name" id="database_name" class="webops-input">
                        </div>

                        <div class="webops-form-row">
                            <div class="webops-form-group">
                                <label for="username" class="webops-label">Username</label>
                                <input type="text" name="username" id="username" class="webops-input">
                            </div>
                            <div class="webops-form-group">
                                <label for="password" class="webops-label">Password</label>
                                <input type="password" name="password" id="password" class="webops-input">
                            </div>
                        </div>
                    </div>

                    <!-- MongoDB Fields -->
                    <div class="db-config db-config-mongodb" style="display: none;">
                        <div class="webops-form-group">
                            <label for="connection_uri" class="webops-label">Connection URI (Optional)</label>
                            <input type="text" name="connection_uri" id="connection_uri" class="webops-input"
                                   placeholder="mongodb://username:password@host:port/database">
                            <small class="webops-text-tertiary">Leave blank to use individual fields</small>
                        </div>
                    </div>

                    <!-- Cloud Database Fields (Pinecone, etc.) -->
                    <div class="db-config db-config-cloud" style="display: none;">
                        <div class="webops-form-group">
                            <label for="api_key" class="webops-label">API Key</label>
                            <input type="password" name="api_key" id="api_key" class="webops-input">
                        </div>
                        <div class="webops-form-group">
                            <label for="environment" class="webops-label">Environment</label>
                            <input type="text" name="environment" id="environment" class="webops-input"
                                   placeholder="us-west1-gcp">
                        </div>
                    </div>

                    <!-- Advanced Options -->
                    <details class="webops-details">
                        <summary class="webops-details-summary">Advanced Options</summary>
                        <div class="webops-details-content">
                            <div class="webops-form-group">
                                <label class="webops-checkbox">
                                    <input type="checkbox" name="ssl_enabled" id="ssl_enabled">
                                    <span>Enable SSL/TLS</span>
                                </label>
                            </div>

                            <div class="webops-form-row">
                                <div class="webops-form-group">
                                    <label for="connection_timeout" class="webops-label">Connection Timeout (seconds)</label>
                                    <input type="number" name="connection_timeout" id="connection_timeout"
                                           class="webops-input" value="30">
                                </div>
                                <div class="webops-form-group">
                                    <label for="pool_size" class="webops-label">Connection Pool Size</label>
                                    <input type="number" name="pool_size" id="pool_size"
                                           class="webops-input" value="5">
                                </div>
                            </div>
                        </div>
                    </details>
                </div>

                <!-- Actions -->
                <div class="webops-form-actions">
                    <button type="submit" class="webops-btn webops-btn-primary">
                        Create Database
                    </button>
                    <a href="{% url 'databases:list' %}" class="webops-btn webops-btn-secondary">
                        Cancel
                    </a>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// Dynamic form configuration based on selected database type
document.getElementById('db_type').addEventListener('change', function(e) {
    const selectedOption = e.target.options[e.target.selectedIndex];
    const dbType = e.target.value;
    const dependencies = selectedOption.dataset.dependencies;
    const installCmd = selectedOption.dataset.install;
    const description = selectedOption.dataset.description;

    // Update description
    document.getElementById('db-description').textContent = description;

    // Show dependency warning if needed
    if (dependencies) {
        document.getElementById('dependency-warning').style.display = 'flex';
        document.getElementById('dependency-list').textContent = `Dependencies: ${dependencies}`;
        document.getElementById('install-command').textContent = installCmd;
    } else {
        document.getElementById('dependency-warning').style.display = 'none';
    }

    // Hide all config sections
    document.querySelectorAll('.db-config').forEach(el => el.style.display = 'none');

    // Show relevant config sections
    if (dbType === 'postgresql' || dbType === 'mysql') {
        document.querySelector('.db-config-relational').style.display = 'block';
        document.getElementById('port').value = dbType === 'postgresql' ? '5432' : '3306';
    } else if (dbType === 'mongodb') {
        document.querySelector('.db-config-relational').style.display = 'block';
        document.querySelector('.db-config-mongodb').style.display = 'block';
        document.getElementById('port').value = '27017';
    } else if (dbType === 'pinecone') {
        document.querySelector('.db-config-cloud').style.display = 'block';
    }
});
</script>

<style>
/* Use WebOps design system variables from variables.css */
.webops-alert {
    display: flex;
    gap: var(--webops-space-3);
    padding: var(--webops-space-4);
    border-radius: var(--webops-radius-lg);
    margin-bottom: var(--webops-space-4);
}

.webops-alert-info {
    background: var(--webops-color-info-alpha-10);
    border: 1px solid var(--webops-color-info-alpha-30);
    color: var(--webops-color-info);
}

.webops-alert-icon {
    flex-shrink: 0;
}

.webops-alert-content {
    flex: 1;
}

.webops-alert-title {
    font-size: var(--webops-font-size-base);
    font-weight: var(--webops-font-weight-semibold);
    margin-bottom: var(--webops-space-2);
}

.webops-code-block {
    background: var(--webops-gray-900);
    padding: var(--webops-space-3);
    border-radius: var(--webops-radius-md);
    font-family: var(--webops-font-family-mono);
    font-size: var(--webops-font-size-sm);
    color: var(--webops-color-primary);
}

.webops-form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--webops-space-4);
}

.webops-details {
    margin-top: var(--webops-space-6);
    padding: var(--webops-space-4);
    background: var(--webops-color-bg-tertiary);
    border-radius: var(--webops-radius-lg);
}

.webops-details-summary {
    font-weight: var(--webops-font-weight-semibold);
    cursor: pointer;
    user-select: none;
}

.webops-details-content {
    margin-top: var(--webops-space-4);
}
</style>
{% endblock %}
```

---

## 5. Usage Example

Once implemented, developers can use the abstraction layer like this:

```python
from apps.databases.adapters.factory import DatabaseFactory
from apps.databases.adapters.base import ConnectionConfig, DatabaseType

# Get database configuration from Database model
db = Database.objects.get(name='my_production_db')

# Create configuration
config = ConnectionConfig(
    db_type=DatabaseType(db.db_type),
    host=db.host,
    port=db.port,
    database=db.database_name,
    username=db.username,
    password=decrypt_password(db.password),  # Decrypt from storage
    ssl_enabled=db.ssl_enabled,
    pool_size=db.pool_size
)

# Create adapter using factory
factory = DatabaseFactory()
adapter = factory.create_adapter(config)

# Use with context manager
with adapter:
    # Execute queries
    result = adapter.execute_query(
        "SELECT * FROM users WHERE active = %(active)s",
        {"active": True}
    )

    for row in result.data:
        print(row)

    # Check health
    is_healthy = adapter.health_check()

    # Get metadata
    metadata = adapter.get_metadata()
```

---

## 6. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `apps/databases/adapters/` directory
- [ ] Implement `base.py` with interfaces and exceptions
- [ ] Implement `postgresql.py` adapter (existing database)
- [ ] Implement `factory.py` with registry
- [ ] Update `Database` model with new fields
- [ ] Create and run migrations

### Phase 2: Additional Adapters
- [ ] Implement `mongodb.py` adapter
- [ ] Implement `sqlite.py` adapter
- [ ] Implement `mysql.py` adapter
- [ ] Implement `redis.py` adapter (optional)
- [ ] Implement `pinecone.py` adapter (optional)

### Phase 3: Web UI
- [ ] Create `DatabaseForm` with dynamic field validation
- [ ] Create database creation template
- [ ] Add JavaScript for dynamic form fields
- [ ] Style with WebOps design system (variables.css)
- [ ] Add dependency detection and install instructions

### Phase 4: Integration & Testing
- [ ] Update deployment service to use adapter pattern
- [ ] Add health checks for all database types
- [ ] Write unit tests for each adapter
- [ ] Write integration tests
- [ ] Update documentation (CLAUDE.md)

---

## 7. Design System Alignment

All UI components must use WebOps design system variables:

- **Colors**: Use `--webops-color-primary`, `--webops-color-info`, etc.
- **Spacing**: Use `--webops-space-*` variables
- **Typography**: Use `--webops-font-size-*` and `--webops-font-weight-*`
- **Border Radius**: Use `--webops-radius-*` variables
- **Shadows**: Use `--webops-shadow-*` for elevation
- **Transitions**: Use `--webops-transition-*` for smooth animations

Reference `control-panel/static/css/variables.css` for all available design tokens.

---

## 8. Security Considerations

1. **Encryption**: All passwords and API keys must be encrypted using WebOps encryption utilities
2. **Validation**: Validate all connection parameters before creating adapters
3. **SQL Injection**: Use parameterized queries (already handled by adapters)
4. **Rate Limiting**: Apply rate limits to database creation API endpoints
5. **Audit Logging**: Log all database creation/deletion to `SecurityAuditLog`

---

## 9. Next Steps

1. Review this refactor document with the team
2. Create GitHub issues for each phase
3. Start with Phase 1 (core infrastructure)
4. Test thoroughly in development before production deployment
5. Update user documentation and API docs

---

**End of Database Refactor Specification**
