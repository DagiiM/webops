"""
MongoDB database adapter.

"Database Models" section
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