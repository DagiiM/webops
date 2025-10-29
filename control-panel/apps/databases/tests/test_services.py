"""
Tests for database services.
"""

import os
from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.databases.services import DatabaseService
from apps.databases.models import Database
from apps.core.utils import encrypt_password, decrypt_password


class DatabaseServiceTest(TestCase):
    """Test cases for database services."""

    def setUp(self):
        """Set up test fixtures."""
        self.db_service = DatabaseService()
        
        # Mock database connection parameters
        self.db_service.connection_params = {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': None,
            'database': 'postgres'
        }

    def test_validate_identifier_valid(self):
        """Test identifier validation with valid inputs."""
        # Test valid identifiers
        self.assertTrue(self.db_service._validate_identifier("valid_name"))
        self.assertTrue(self.db_service._validate_identifier("valid_name_123"))
        self.assertTrue(self.db_service._validate_identifier("ValidName"))
        
    def test_validate_identifier_invalid(self):
        """Test identifier validation with invalid inputs."""
        # Test invalid identifiers
        self.assertFalse(self.db_service._validate_identifier(""))
        self.assertFalse(self.db_service._validate_identifier("123invalid"))
        self.assertFalse(self.db_service._validate_identifier("invalid-name"))
        self.assertFalse(self.db_service._validate_identifier("invalid@name"))
        self.assertFalse(self.db_service._validate_identifier("invalid name"))
        
        # Test length validation
        long_name = "a" * 64  # 64 characters, exceeds limit
        self.assertFalse(self.db_service._validate_identifier(long_name))

    def test_validate_sql_query_safe(self):
        """Test SQL query validation with safe queries."""
        # Test safe queries
        self.assertTrue(self.db_service._validate_sql_query("SELECT * FROM users"))
        self.assertTrue(self.db_service._validate_sql_query("SELECT * FROM users WHERE id = %s"))
        self.assertTrue(self.db_service._validate_sql_query("INSERT INTO users (name) VALUES (%s)"))
        
    def test_validate_sql_query_unsafe(self):
        """Test SQL query validation with unsafe queries."""
        # Test unsafe queries
        self.assertFalse(self.db_service._validate_sql_query("SELECT * FROM users; DROP TABLE users;"))
        self.assertFalse(self.db_service._validate_sql_query("SELECT * FROM users --"))
        self.assertFalse(self.db_service._validate_sql_query("SELECT * FROM users /* comment */"))
        self.assertFalse(self.db_service._validate_sql_query("SELECT * FROM users UNION SELECT * FROM admin"))
        self.assertFalse(self.db_service._validate_sql_query("xp_cmdshell 'whoami'"))
        self.assertFalse(self.db_service._validate_sql_query("SELECT * FROM users; SELECT * FROM users"))

    @patch('apps.databases.services.psycopg2.connect')
    def test_execute_sql_success(self, mock_connect):
        """Test successful SQL execution."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = None  # Not a SELECT query
        mock_cursor.rowcount = 1
        
        # Test SQL execution
        success, output = self.db_service.execute_sql("CREATE TABLE test (id INTEGER)")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with("CREATE TABLE test (id INTEGER)")
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("executed successfully", output)

    @patch('apps.databases.services.psycopg2.connect')
    def test_execute_sql_select_query(self, mock_connect):
        """Test SQL execution with SELECT query."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = [('id',), ('name',)]  # SELECT query
        mock_cursor.fetchall.return_value = [(1, 'test'), (2, 'user')]
        
        # Test SELECT SQL execution
        success, output = self.db_service.execute_sql("SELECT * FROM users")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with("SELECT * FROM users")
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify success and output
        self.assertTrue(success)
        self.assertIn("[(1, 'test'), (2, 'user')]", output)

    @patch('apps.databases.services.psycopg2.connect')
    def test_execute_sql_with_parameters(self, mock_connect):
        """Test SQL execution with parameters."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.description = None  # Not a SELECT query
        mock_cursor.rowcount = 1
        
        # Test SQL execution with parameters
        success, output = self.db_service.execute_sql(
            "INSERT INTO users (name) VALUES (%s)",
            params=('test_user',)
        )
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations with parameters
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO users (name) VALUES (%s)",
            ('test_user',)
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify success
        self.assertTrue(success)

    @patch('apps.databases.services.psycopg2.connect')
    def test_execute_sql_error(self, mock_connect):
        """Test SQL execution with error."""
        # Mock: database connection to raise an exception
        from psycopg2 import Error
        mock_connect.side_effect = Error("Connection failed")
        
        # Test SQL execution with error
        success, output = self.db_service.execute_sql("SELECT * FROM users")
        
        # Verify failure
        self.assertFalse(success)
        self.assertEqual(output, "Database operation failed")

    @patch('apps.databases.services.psycopg2.connect')
    def test_database_exists_true(self, mock_connect):
        """Test database exists check when database exists."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        
        # Test database exists
        exists = self.db_service.database_exists("test_db")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            ("test_db",)
        )
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify result
        self.assertTrue(exists)

    @patch('apps.databases.services.psycopg2.connect')
    def test_database_exists_false(self, mock_connect):
        """Test database exists check when database doesn't exist."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        
        # Test database exists
        exists = self.db_service.database_exists("nonexistent_db")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            ("nonexistent_db",)
        )
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify result
        self.assertFalse(exists)

    def test_database_exists_invalid_name(self):
        """Test database exists check with invalid name."""
        # Test database exists with invalid name
        exists = self.db_service.database_exists("invalid@name")
        
        # Verify result
        self.assertFalse(exists)

    @patch('apps.databases.services.psycopg2.connect')
    def test_user_exists_true(self, mock_connect):
        """Test user exists check when user exists."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        
        # Test user exists
        exists = self.db_service.user_exists("test_user")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            ("test_user",)
        )
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify result
        self.assertTrue(exists)

    @patch('apps.databases.services.psycopg2.connect')
    def test_user_exists_false(self, mock_connect):
        """Test user exists check when user doesn't exist."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        
        # Test user exists
        exists = self.db_service.user_exists("nonexistent_user")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify cursor operations
        mock_cursor.execute.assert_called_once_with(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            ("nonexistent_user",)
        )
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
        
        # Verify result
        self.assertFalse(exists)

    def test_user_exists_invalid_name(self):
        """Test user exists check with invalid name."""
        # Test user exists with invalid name
        exists = self.db_service.user_exists("invalid@name")
        
        # Verify result
        self.assertFalse(exists)

    @patch('apps.databases.services.psycopg2.connect')
    @patch('apps.databases.services.psycopg2.sql')
    def test_create_database_success(self, mock_connect, mock_sql):
        """Test successful database creation."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        
        # Mock database_exists to return False (database doesn't exist)
        with patch.object(self.db_service, 'database_exists', return_value=False):
            # Test database creation
            success, message = self.db_service.create_database("test_db")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify SQL was composed correctly
        mock_sql.SQL.assert_called_once_with("CREATE DATABASE %s")
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("created successfully", message)

    def test_create_database_already_exists(self):
        """Test database creation when database already exists."""
        # Mock database_exists to return True (database already exists)
        with patch.object(self.db_service, 'database_exists', return_value=True):
            # Test database creation
            success, message = self.db_service.create_database("existing_db")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("already exists", message)

    def test_create_database_invalid_name(self):
        """Test database creation with invalid name."""
        # Test database creation with invalid name
        success, message = self.db_service.create_database("invalid@name")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid database name", message)

    @patch('apps.databases.services.psycopg2.connect')
    @patch('apps.databases.services.psycopg2.sql')
    def test_create_user_success(self, mock_connect, mock_sql):
        """Test successful user creation."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        
        # Mock user_exists to return False (user doesn't exist)
        with patch.object(self.db_service, 'user_exists', return_value=False):
            # Test user creation
            success, message = self.db_service.create_user("test_user", "secure_password")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify SQL was composed correctly
        mock_sql.SQL.assert_called_once()
        mock_sql.Identifier.assert_called_once_with("test_user")
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("created successfully", message)

    def test_create_user_already_exists(self):
        """Test user creation when user already exists."""
        # Mock user_exists to return True (user already exists)
        with patch.object(self.db_service, 'user_exists', return_value=True):
            # Test user creation
            success, message = self.db_service.create_user("existing_user", "password")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("already exists", message)

    def test_create_user_invalid_name(self):
        """Test user creation with invalid name."""
        # Test user creation with invalid name
        success, message = self.db_service.create_user("invalid@name", "password")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid username", message)

    @patch('apps.databases.services.psycopg2.connect')
    @patch('apps.databases.services.psycopg2.sql')
    def test_grant_privileges_success(self, mock_connect, mock_sql):
        """Test successful privilege granting."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        
        # Test privilege granting
        success, message = self.db_service.grant_privileges("test_db", "test_user")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called_once_with(**self.db_service.connection_params)
        
        # Verify SQL was composed correctly
        mock_sql.SQL.assert_called_once()
        mock_sql.Identifier.assert_any_call()  # Called with database name
        mock_sql.Identifier.assert_any_call()  # Called with username
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("granted successfully", message)

    def test_grant_privileges_invalid_db_name(self):
        """Test privilege granting with invalid database name."""
        # Test privilege granting with invalid database name
        success, message = self.db_service.grant_privileges("invalid@name", "test_user")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid database name", message)

    def test_grant_privileges_invalid_username(self):
        """Test privilege granting with invalid username."""
        # Test privilege granting with invalid username
        success, message = self.db_service.grant_privileges("test_db", "invalid@name")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid username", message)

    @patch('apps.databases.services.psycopg2.connect')
    @patch('apps.databases.services.psycopg2.sql')
    def test_delete_database_success(self, mock_connect, mock_sql):
        """Test successful database deletion."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        
        # Mock database_exists to return True (database exists)
        with patch.object(self.db_service, 'database_exists', return_value=True):
            # Test database deletion
            success, message = self.db_service.delete_database("test_db")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called()
        
        # Verify SQL was composed correctly
        mock_sql.SQL.assert_called_once_with("DROP DATABASE %s")
        mock_sql.Identifier.assert_called_once_with("test_db")
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("deleted successfully", message)

    def test_delete_database_not_exists(self):
        """Test database deletion when database doesn't exist."""
        # Mock database_exists to return False (database doesn't exist)
        with patch.object(self.db_service, 'database_exists', return_value=False):
            # Test database deletion
            success, message = self.db_service.delete_database("nonexistent_db")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("does not exist", message)

    def test_delete_database_invalid_name(self):
        """Test database deletion with invalid name."""
        # Test database deletion with invalid name
        success, message = self.db_service.delete_database("invalid@name")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid database name", message)

    @patch('apps.databases.services.psycopg2.connect')
    @patch('apps.databases.services.psycopg2.sql')
    def test_delete_user_success(self, mock_connect, mock_sql):
        """Test successful user deletion."""
        # Mock: database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.rowcount = 1
        
        # Mock user_exists to return True (user exists)
        with patch.object(self.db_service, 'user_exists', return_value=True):
            # Test user deletion
            success, message = self.db_service.delete_user("test_user")
        
        # Verify: connection was made with correct parameters
        mock_connect.assert_called()
        
        # Verify SQL was composed correctly
        mock_sql.SQL.assert_called_once_with("DROP USER %s")
        mock_sql.Identifier.assert_called_once_with("test_user")
        
        # Verify success
        self.assertTrue(success)
        self.assertIn("deleted successfully", message)

    def test_delete_user_not_exists(self):
        """Test user deletion when user doesn't exist."""
        # Mock user_exists to return False (user doesn't exist)
        with patch.object(self.db_service, 'user_exists', return_value=False):
            # Test user deletion
            success, message = self.db_service.delete_user("nonexistent_user")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("does not exist", message)

    def test_delete_user_invalid_name(self):
        """Test user deletion with invalid name."""
        # Test user deletion with invalid name
        success, message = self.db_service.delete_user("invalid@name")
        
        # Verify failure
        self.assertFalse(success)
        self.assertIn("Invalid username", message)

    def test_get_connection_string(self):
        """Test getting connection string."""
        # Create a test database
        database = Database.objects.create(
            name="test_db",
            db_type="postgresql",
            host="localhost",
            port=5432,
            username="test_user",
            password=encrypt_password("test_password"),
            database_name="test_db"
        )
        
        # Test getting connection string
        connection_string = self.db_service.get_connection_string(database, decrypted=True)
        
        # Verify connection string format
        expected = "postgresql://test_user:test_password@localhost:5432/test_db"
        self.assertEqual(connection_string, expected)

    def test_get_connection_string_masked(self):
        """Test getting connection string with masked password."""
        # Create a test database
        database = Database.objects.create(
            name="test_db",
            db_type="postgresql",
            host="localhost",
            port=5432,
            username="test_user",
            password=encrypt_password("test_password"),
            database_name="test_db"
        )
        
        # Test getting connection string with masked password
        connection_string = self.db_service.get_connection_string(database, decrypted=False)
        
        # Verify connection string format with masked password
        expected = "postgresql://test_user:****@localhost:5432/test_db"
        self.assertEqual(connection_string, expected)