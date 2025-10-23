"""
SQLite database adapter.

"Database Models" section
"""

import logging
import os
from typing import Any, Dict, List, Optional

try:
    import sqlite3
except ImportError:
    sqlite3 = None

from .base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    ConnectionException,
    QueryExecutionException,
    TransactionException,
)

logger = logging.getLogger(__name__)


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter for local file-based databases."""

    DEPENDENCIES = []  # SQLite is built into Python
    INSTALL_COMMAND = ""
    DESCRIPTION = "Lightweight file-based database (ideal for development and small applications)"

    def __init__(self, config: ConnectionConfig):
        """Initialize SQLite adapter."""
        if sqlite3 is None:
            raise ConnectionException("sqlite3 is not available")
        super().__init__(config)
        self.connection = None

    def connect(self) -> None:
        """Connect to SQLite database."""
        try:
            # Ensure the directory for the database file exists
            db_path = self.config.database
            if db_path:
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

            self.connection = sqlite3.connect(
                db_path,
                timeout=self.config.connection_timeout
            )
            
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # Set row factory to return dictionaries
            self.connection.row_factory = sqlite3.Row

            logger.info(f"Connected to SQLite: {db_path}")
        except sqlite3.Error as e:
            raise ConnectionException(f"SQLite connection failed: {e}")

    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from SQLite")

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
            
            # Convert parameters dict to tuple if needed
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)

            # Handle SELECT queries
            if cursor.description:
                data = [dict(row) for row in cursor.fetchall()]
                return QueryResult(
                    success=True,
                    data=data,
                    rows_affected=len(data)
                )

            # Handle INSERT/UPDATE/DELETE
            if not self._in_transaction:
                self.connection.commit()

            return QueryResult(
                success=True,
                rows_affected=cursor.rowcount
            )

        except sqlite3.Error as e:
            if self.connection and not self._in_transaction:
                self.connection.rollback()
            logger.error(f"Query execution failed: {e}")
            raise QueryExecutionException(f"SQLite query failed: {e}")

    def start_transaction(self) -> None:
        """Begin transaction."""
        if self._in_transaction:
            raise TransactionException("Transaction already in progress")

        self._in_transaction = True
        logger.debug("Transaction started")

    def commit_transaction(self) -> None:
        """Commit transaction."""
        if not self._in_transaction:
            raise TransactionException("No active transaction")

        try:
            self.connection.commit()
            logger.debug("Transaction committed")
        except sqlite3.Error as e:
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
        except sqlite3.Error as e:
            logger.error(f"Rollback failed: {e}")
        finally:
            self._in_transaction = False

    def health_check(self) -> bool:
        """Check SQLite connection health."""
        try:
            result = self.execute_query("SELECT 1")
            return result.success
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """Get SQLite version and metadata."""
        try:
            result = self.execute_query("SELECT sqlite_version()")
            version = result.data[0]['sqlite_version()'] if result.data else 'Unknown'

            return {
                'type': 'SQLite',
                'version': version,
                'database': self.config.database,
                'file_exists': os.path.exists(self.config.database) if self.config.database else False,
                'file_size': os.path.getsize(self.config.database) if (
                    self.config.database and os.path.exists(self.config.database)
                ) else 0
            }
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return {'type': 'SQLite', 'error': str(e)}