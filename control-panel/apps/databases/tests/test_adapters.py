"""
Tests for database adapters.
"""

import os
import tempfile
from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.databases.adapters.base import (
    ConnectionConfig, DatabaseType, QueryResult, 
    ConfigurationException, ConnectionException
)
from apps.databases.adapters.factory import DatabaseFactory, adapter_registry
from apps.databases.adapters.postgresql import PostgreSQLAdapter
from apps.databases.adapters.mongodb import MongoDBAdapter
from apps.databases.adapters.sqlite import SQLiteAdapter
from apps.databases.adapters.mysql import MySQLAdapter


class DatabaseAdapterTest(TestCase):
    """Test cases for database adapters."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = DatabaseFactory()
        
        # PostgreSQL config
        self.pg_config = ConnectionConfig(
            db_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user",
            password="test_pass"
        )
        
        # MySQL config
        self.mysql_config = ConnectionConfig(
            db_type=DatabaseType.MYSQL,
            host="localhost",
            port=3306,
            database="test_mysql",
            username="mysql_user",
            password="mysql_pass"
        )
        
        # MongoDB config
        self.mongo_config = ConnectionConfig(
            db_type=DatabaseType.MONGODB,
            host="localhost",
            port=27017,
            database="test_mongo",
            username="mongo_user",
            password="mongo_pass"
        )
        
        # SQLite config
        self.sqlite_config = ConnectionConfig(
            db_type=DatabaseType.SQLITE,
            database="/tmp/test_sqlite.db"
        )

    def test_adapter_registry(self):
        """Test that all adapters are registered."""
        adapters = adapter_registry.list_adapters()
        
        self.assertIn(DatabaseType.POSTGRESQL, adapters)
        self.assertIn(DatabaseType.MYSQL, adapters)
        self.assertIn(DatabaseType.MONGODB, adapters)
        self.assertIn(DatabaseType.SQLITE, adapters)
        
        # Check adapter metadata
        self.assertEqual(adapters[DatabaseType.POSTGRESQL]['class'], 'PostgreSQLAdapter')
        self.assertEqual(adapters[DatabaseType.MYSQL]['class'], 'MySQLAdapter')
        self.assertEqual(adapters[DatabaseType.MONGODB]['class'], 'MongoDBAdapter')
        self.assertEqual(adapters[DatabaseType.SQLITE]['class'], 'SQLiteAdapter')

    def test_factory_creates_adapters(self):
        """Test that factory creates correct adapter instances."""
        pg_adapter = self.factory.create_adapter(self.pg_config)
        self.assertIsInstance(pg_adapter, PostgreSQLAdapter)
        
        mysql_adapter = self.factory.create_adapter(self.mysql_config)
        self.assertIsInstance(mysql_adapter, MySQLAdapter)
        
        mongo_adapter = self.factory.create_adapter(self.mongo_config)
        self.assertIsInstance(mongo_adapter, MongoDBAdapter)
        
        sqlite_adapter = self.factory.create_adapter(self.sqlite_config)
        self.assertIsInstance(sqlite_adapter, SQLiteAdapter)

    def test_configuration_validation(self):
        """Test configuration validation."""
        # Valid PostgreSQL config
        try:
            self.pg_config.validate()
        except ConfigurationException:
            self.fail("Valid PostgreSQL config raised ConfigurationException")
        
        # Invalid PostgreSQL config (missing password)
        invalid_pg_config = ConnectionConfig(
            db_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="test_db",
            username="test_user"
            # Missing password
        )
        with self.assertRaises(ConfigurationException):
            invalid_pg_config.validate()
        
        # Valid SQLite config
        try:
            self.sqlite_config.validate()
        except ConfigurationException:
            self.fail("Valid SQLite config raised ConfigurationException")
        
        # Invalid SQLite config (missing database)
        invalid_sqlite_config = ConnectionConfig(
            db_type=DatabaseType.SQLITE
            # Missing database path
        )
        with self.assertRaises(ConfigurationException):
            invalid_sqlite_config.validate()

    @patch('sqlite3.connect')
    def test_sqlite_adapter(self, mock_connect):
        """Test SQLite adapter functionality."""
        # Mock the SQLite connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.row_factory = {'id': 1, 'name': 'test'}
        
        # Create and connect adapter
        adapter = SQLiteAdapter(self.sqlite_config)
        adapter.connect()
        
        # Verify connection was made
        mock_connect.assert_called_once()
        
        # Test query execution
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.description = ['id', 'name']
        mock_cursor.fetchall.return_value = [{'id': 1, 'name': 'test'}]
        
        result = adapter.execute_query("SELECT * FROM test")
        
        self.assertIsInstance(result, QueryResult)
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), 1)
        
        # Test disconnect
        adapter.disconnect()
        mock_conn.close.assert_called_once()

    def test_adapter_metadata(self):
        """Test adapter metadata retrieval."""
        # Test SQLite adapter metadata
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_db = tmp.name
        
        try:
            sqlite_config = ConnectionConfig(
                db_type=DatabaseType.SQLITE,
                database=tmp_db
            )
            adapter = SQLiteAdapter(sqlite_config)
            adapter.connect()
            
            metadata = adapter.get_metadata()
            self.assertEqual(metadata['type'], 'SQLite')
            self.assertIn('version', metadata)
            
            adapter.disconnect()
        finally:
            if os.path.exists(tmp_db):
                os.unlink(tmp_db)

    def test_adapter_health_check(self):
        """Test adapter health check."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_db = tmp.name
        
        try:
            sqlite_config = ConnectionConfig(
                db_type=DatabaseType.SQLITE,
                database=tmp_db
            )
            adapter = SQLiteAdapter(sqlite_config)
            adapter.connect()
            
            # Test health check
            is_healthy = adapter.health_check()
            self.assertTrue(is_healthy)
            
            adapter.disconnect()
        finally:
            if os.path.exists(tmp_db):
                os.unlink(tmp_db)