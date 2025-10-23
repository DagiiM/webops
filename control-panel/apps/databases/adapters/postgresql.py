"""
PostgreSQL database adapter.

"Database Models" section
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