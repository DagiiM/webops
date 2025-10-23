"""
Base adapter interface and exceptions for database abstraction.

"Database Models" section
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
        elif self.db_type == DatabaseType.MYSQL:
            required = ['host', 'port', 'database', 'username', 'password']
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