"""
MySQL database adapter.

"Database Models" section
"""

import logging
from typing import Any, Dict, List, Optional

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None

from .base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    ConnectionException,
    QueryExecutionException,
    TransactionException,
)

logger = logging.getLogger(__name__)


class MySQLAdapter(DatabaseAdapter):
    """MySQL database adapter with connection pooling."""

    # Class-level dependency information
    DEPENDENCIES = ["pymysql>=1.0.0"]
    INSTALL_COMMAND = "pip install pymysql"
    DESCRIPTION = "Popular open-source relational database"

    def __init__(self, config: ConnectionConfig):
        """Initialize MySQL adapter."""
        if pymysql is None:
            raise ConnectionException(
                "pymysql is not installed. "
                f"Install with: {self.INSTALL_COMMAND}"
            )
        super().__init__(config)
        self.connection = None

    def connect(self) -> None:
        """Establish connection to MySQL."""
        try:
            self.connection = pymysql.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.username,
                password=self.config.password,
                database=self.config.database,
                connect_timeout=self.config.connection_timeout,
                ssl_disabled=not self.config.ssl_enabled,
                charset='utf8mb4',
                cursorclass=DictCursor
            )

            logger.info(f"Connected to MySQL: {self.config.database}")
        except pymysql.Error as e:
            raise ConnectionException(f"MySQL connection failed: {e}")

    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from MySQL")

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        """Execute SQL query with parameters."""
        if not self.connection:
            raise ConnectionException("Not connected to database")

        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Use parameterized queries to prevent SQL injection
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)

            # Handle SELECT queries
            if cursor.description:
                data = cursor.fetchall()
                return QueryResult(
                    success=True,
                    data=data,
                    rows_affected=cursor.rowcount
                )

            # Handle INSERT/UPDATE/DELETE
            if not self._in_transaction:
                self.connection.commit()

            return QueryResult(
                success=True,
                rows_affected=cursor.rowcount
            )

        except pymysql.Error as e:
            if self.connection and not self._in_transaction:
                self.connection.rollback()
            logger.error(f"Query execution failed: {e}")
            raise QueryExecutionException(f"MySQL query failed: {e}")

        finally:
            if cursor:
                cursor.close()

    def start_transaction(self) -> None:
        """Begin transaction."""
        if self._in_transaction:
            raise TransactionException("Transaction already in progress")

        try:
            self.connection.begin()
            self._in_transaction = True
            logger.debug("Transaction started")
        except pymysql.Error as e:
            raise TransactionException(f"Failed to start transaction: {e}")

    def commit_transaction(self) -> None:
        """Commit transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.commit()
            logger.debug("Transaction committed")
        except pymysql.Error as e:
            raise TransactionException(f"Commit failed: {e}")
        finally:
            self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.rollback()
            logger.debug("Transaction rolled back")
        except pymysql.Error as e:
            logger.error(f"Rollback failed: {e}")
        finally:
            self._in_transaction = False

    def health_check(self) -> bool:
        """Check MySQL connection health."""
        try:
            result = self.execute_query("SELECT 1")
            return result.success
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """Get MySQL version and metadata."""
        try:
            result = self.execute_query("SELECT VERSION() as version")
            version = result.data[0]['version'] if result.data else 'Unknown'

            return {
                'type': 'MySQL',
                'version': version,
                'host': self.config.host,
                'port': self.config.port,
                'database': self.config.database,
                'ssl_enabled': self.config.ssl_enabled
            }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {'type': 'MySQL', 'error': str(e)}