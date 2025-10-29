"""
Tests for database forms.
"""

import re
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.databases.forms import (
    DatabaseForm, identifier_validator, database_name_validator,
    username_validator, connection_uri_validator
)
from apps.databases.models import Database
from apps.core.utils import encrypt_password


class DatabaseFormTest(TestCase):
    """Test cases for database forms."""

    def test_identifier_validator_valid(self):
        """Test identifier validator with valid inputs."""
        # Test valid identifiers
        self.assertTrue(identifier_validator("valid_name"))
        self.assertTrue(identifier_validator("valid_name_123"))
        self.assertTrue(identifier_validator("ValidName"))
        
    def test_identifier_validator_invalid(self):
        """Test identifier validator with invalid inputs."""
        # Test invalid identifiers
        self.assertFalse(identifier_validator(""))
        self.assertFalse(identifier_validator("123invalid"))
        self.assertFalse(identifier_validator("invalid-name"))
        self.assertFalse(identifier_validator("invalid@name"))
        self.assertFalse(identifier_validator("invalid name"))
        
        # Test length validation
        long_name = "a" * 64  # 64 characters, exceeds limit
        self.assertFalse(identifier_validator(long_name))

    def test_database_name_validator_valid(self):
        """Test database name validator with valid inputs."""
        # Test valid database names
        self.assertTrue(database_name_validator("valid_db"))
        self.assertTrue(database_name_validator("valid_db_123"))
        self.assertTrue(database_name_validator("ValidDB"))
        
    def test_database_name_validator_invalid(self):
        """Test database name validator with invalid inputs."""
        # Test invalid database names
        self.assertFalse(database_name_validator(""))
        self.assertFalse(database_name_validator("123invalid"))
        self.assertFalse(database_name_validator("invalid-db"))
        self.assertFalse(database_name_validator("invalid@db"))
        self.assertFalse(database_name_validator("invalid db"))
        
        # Test length validation
        long_name = "a" * 64  # 64 characters, exceeds limit
        self.assertFalse(database_name_validator(long_name))

    def test_username_validator_valid(self):
        """Test username validator with valid inputs."""
        # Test valid usernames
        self.assertTrue(username_validator("valid_user"))
        self.assertTrue(username_validator("valid_user_123"))
        self.assertTrue(username_validator("ValidUser"))
        
    def test_username_validator_invalid(self):
        """Test username validator with invalid inputs."""
        # Test invalid usernames
        self.assertFalse(username_validator(""))
        self.assertFalse(username_validator("123invalid"))
        self.assertFalse(username_validator("invalid-user"))
        self.assertFalse(username_validator("invalid@user"))
        self.assertFalse(username_validator("invalid user"))
        
        # Test length validation
        long_name = "a" * 64  # 64 characters, exceeds limit
        self.assertFalse(username_validator(long_name))

    def test_connection_uri_validator_valid(self):
        """Test connection URI validator with valid inputs."""
        # Test valid connection URIs
        self.assertTrue(connection_uri_validator("mongodb://localhost:27017"))
        self.assertTrue(connection_uri_validator("mysql://localhost:3306"))
        self.assertTrue(connection_uri_validator("postgresql://localhost:5432"))
        self.assertTrue(connection_uri_validator("sqlite:///path/to/db.sqlite3"))
        
    def test_connection_uri_validator_invalid(self):
        """Test connection URI validator with invalid inputs."""
        # Test invalid connection URIs
        self.assertFalse(connection_uri_validator(""))
        self.assertFalse(connection_uri_validator("invalid://localhost"))
        self.assertFalse(connection_uri_validator("mongodb://localhost:27017; DROP TABLE users"))
        self.assertFalse(connection_uri_validator("mongodb://localhost:27017 --"))
        self.assertFalse(connection_uri_validator("mongodb://localhost:27017 /*"))

    def test_form_valid_postgresql(self):
        """Test form validation with valid PostgreSQL data."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Check that default port is set if not provided
        form_data_no_port = form_data.copy()
        form_data_no_port.pop('port')
        form_no_port = DatabaseForm(data=form_data_no_port)
        self.assertTrue(form_no_port.is_valid())
        self.assertEqual(form_no_port.cleaned_data['port'], 5432)

    def test_form_valid_mysql(self):
        """Test form validation with valid MySQL data."""
        form_data = {
            'name': 'test_mysql',
            'db_type': 'mysql',
            'host': 'localhost',
            'port': 3306,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_mysql'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Check that default port is set if not provided
        form_data_no_port = form_data.copy()
        form_data_no_port.pop('port')
        form_no_port = DatabaseForm(data=form_data_no_port)
        self.assertTrue(form_no_port.is_valid())
        self.assertEqual(form_no_port.cleaned_data['port'], 3306)

    def test_form_valid_mongodb(self):
        """Test form validation with valid MongoDB data."""
        form_data = {
            'name': 'test_mongo',
            'db_type': 'mongodb',
            'host': 'localhost',
            'port': 27017,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_mongo'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Check that default port is set if not provided
        form_data_no_port = form_data.copy()
        form_data_no_port.pop('port')
        form_no_port = DatabaseForm(data=form_data_no_port)
        self.assertTrue(form_no_port.is_valid())
        self.assertEqual(form_no_port.cleaned_data['port'], 27017)

    def test_form_valid_mongodb_with_uri(self):
        """Test form validation with valid MongoDB URI."""
        form_data = {
            'name': 'test_mongo_uri',
            'db_type': 'mongodb',
            'connection_uri': 'mongodb://localhost:27017/test_mongo'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_sqlite(self):
        """Test form validation with valid SQLite data."""
        form_data = {
            'name': 'test_sqlite',
            'db_type': 'sqlite',
            'database_name': '/path/to/test.db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_pinecone(self):
        """Test form validation with valid Pinecone data."""
        form_data = {
            'name': 'test_pinecone',
            'db_type': 'pinecone',
            'api_key': 'test_api_key',
            'environment': 'test_env'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_valid_redis(self):
        """Test form validation with valid Redis data."""
        form_data = {
            'name': 'test_redis',
            'db_type': 'redis',
            'host': 'localhost',
            'port': 6379
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Check that default port is set if not provided
        form_data_no_port = form_data.copy()
        form_data_no_port.pop('port')
        form_no_port = DatabaseForm(data=form_data_no_port)
        self.assertTrue(form_no_port.is_valid())
        self.assertEqual(form_no_port.cleaned_data['port'], 6379)

    def test_form_invalid_postgresql_missing_fields(self):
        """Test form validation with missing PostgreSQL fields."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            # Missing host, port, username
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('host', form.errors)
        self.assertIn('port', form.errors)
        self.assertIn('username', form.errors)

    def test_form_invalid_mysql_missing_fields(self):
        """Test form validation with missing MySQL fields."""
        form_data = {
            'name': 'test_mysql',
            'db_type': 'mysql',
            # Missing host, port, username
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('host', form.errors)
        self.assertIn('port', form.errors)
        self.assertIn('username', form.errors)

    def test_form_invalid_mongodb_missing_fields(self):
        """Test form validation with missing MongoDB fields."""
        form_data = {
            'name': 'test_mongo',
            'db_type': 'mongodb',
            # Missing both connection_uri and host+port
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('connection_uri', form.errors)

    def test_form_invalid_sqlite_missing_database(self):
        """Test form validation with missing SQLite database."""
        form_data = {
            'name': 'test_sqlite',
            'db_type': 'sqlite',
            # Missing database_name
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('database_name', form.errors)

    def test_form_invalid_pinecone_missing_fields(self):
        """Test form validation with missing Pinecone fields."""
        form_data = {
            'name': 'test_pinecone',
            'db_type': 'pinecone',
            # Missing api_key, environment
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('api_key', form.errors)
        self.assertIn('environment', form.errors)

    def test_form_invalid_redis_missing_fields(self):
        """Test form validation with missing Redis fields."""
        form_data = {
            'name': 'test_redis',
            'db_type': 'redis',
            # Missing host, port
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('host', form.errors)
        self.assertIn('port', form.errors)

    def test_form_invalid_name(self):
        """Test form validation with invalid name."""
        form_data = {
            'name': 'invalid@name',  # Invalid characters
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('name', form.errors)

    def test_form_invalid_name_too_long(self):
        """Test form validation with name too long."""
        form_data = {
            'name': 'a' * 64,  # 64 characters, exceeds limit
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('name', form.errors)

    def test_form_invalid_username(self):
        """Test form validation with invalid username."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'invalid@user',  # Invalid characters
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('username', form.errors)

    def test_form_invalid_username_too_long(self):
        """Test form validation with username too long."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'a' * 64,  # 64 characters, exceeds limit
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('username', form.errors)

    def test_form_invalid_database_name(self):
        """Test form validation with invalid database name."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'invalid@db'  # Invalid characters
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('database_name', form.errors)

    def test_form_invalid_database_name_too_long(self):
        """Test form validation with database name too long."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'a' * 64  # 64 characters, exceeds limit
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('database_name', form.errors)

    def test_form_invalid_host(self):
        """Test form validation with invalid host."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'invalid@host',  # Invalid characters
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('host', form.errors)

    def test_form_invalid_host_too_long(self):
        """Test form validation with host too long."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'a' * 254,  # 254 characters, exceeds limit
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('host', form.errors)

    def test_form_invalid_port(self):
        """Test form validation with invalid port."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 'invalid_port',  # Not a number
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('port', form.errors)

    def test_form_invalid_port_out_of_range(self):
        """Test form validation with port out of range."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 70000,  # Out of valid range
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('port', form.errors)

    def test_form_invalid_connection_uri(self):
        """Test form validation with invalid connection URI."""
        form_data = {
            'name': 'test_mongo',
            'db_type': 'mongodb',
            'connection_uri': 'invalid://localhost'  # Invalid URI format
        }
        
        form = DatabaseForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Check for specific error messages
        self.assertIn('connection_uri', form.errors)

    def test_form_save(self):
        """Test form save method."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Save the form
        database = form.save()
        
        # Verify the database was created
        self.assertEqual(database.name, 'test_db')
        self.assertEqual(database.db_type, 'postgresql')
        self.assertEqual(database.host, 'localhost')
        self.assertEqual(database.port, 5432)
        self.assertEqual(database.username, 'test_user')
        self.assertEqual(database.database_name, 'test_db')
        
        # Verify password is encrypted
        self.assertNotEqual(database.password, 'test_password')
        self.assertTrue(database.password.startswith('gAAAA'))  # Fernet encrypted strings start with gAAAA

    def test_form_clean_name(self):
        """Test form clean_name method."""
        form_data = {
            'name': 'valid_name',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_name method
        cleaned_name = form.clean_name()
        self.assertEqual(cleaned_name, 'valid_name')

    def test_form_clean_name_invalid(self):
        """Test form clean_name method with invalid name."""
        form_data = {
            'name': 'invalid@name',  # Invalid characters
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_name should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_name()

    def test_form_clean_username(self):
        """Test form clean_username method."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'valid_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_username method
        cleaned_username = form.clean_username()
        self.assertEqual(cleaned_username, 'valid_user')

    def test_form_clean_username_invalid(self):
        """Test form clean_username method with invalid username."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'invalid@user',  # Invalid characters
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_username should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_username()

    def test_form_clean_database_name(self):
        """Test form clean_database_name method."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'valid_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_database_name method
        cleaned_db_name = form.clean_database_name()
        self.assertEqual(cleaned_db_name, 'valid_db')

    def test_form_clean_database_name_invalid(self):
        """Test form clean_database_name method with invalid database name."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'invalid@db'  # Invalid characters
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_database_name should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_database_name()

    def test_form_clean_host(self):
        """Test form clean_host method."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'valid.host',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_host method
        cleaned_host = form.clean_host()
        self.assertEqual(cleaned_host, 'valid.host')

    def test_form_clean_host_invalid(self):
        """Test form clean_host method with invalid host."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'invalid@host',  # Invalid characters
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_host should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_host()

    def test_form_clean_port(self):
        """Test form clean_port method."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 5432,
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_port method
        cleaned_port = form.clean_port()
        self.assertEqual(cleaned_port, 5432)

    def test_form_clean_port_invalid(self):
        """Test form clean_port method with invalid port."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 'invalid_port',  # Not a number
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_port should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_port()

    def test_form_clean_port_out_of_range(self):
        """Test form clean_port method with port out of range."""
        form_data = {
            'name': 'test_db',
            'db_type': 'postgresql',
            'host': 'localhost',
            'port': 70000,  # Out of valid range
            'username': 'test_user',
            'password': 'test_password',
            'database_name': 'test_db'
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_port should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_port()

    def test_form_clean_connection_uri(self):
        """Test form clean_connection_uri method."""
        form_data = {
            'name': 'test_mongo',
            'db_type': 'mongodb',
            'connection_uri': 'mongodb://localhost:27017/test_db'
        }
        
        form = DatabaseForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Test clean_connection_uri method
        cleaned_uri = form.clean_connection_uri()
        self.assertEqual(cleaned_uri, 'mongodb://localhost:27017/test_db')

    def test_form_clean_connection_uri_invalid(self):
        """Test form clean_connection_uri method with invalid URI."""
        form_data = {
            'name': 'test_mongo',
            'db_type': 'mongodb',
            'connection_uri': 'invalid://localhost'  # Invalid URI format
        }
        
        form = DatabaseForm(data=form_data)
        # Even if form is invalid, clean_connection_uri should raise ValidationError
        with self.assertRaises(ValidationError):
            form.clean_connection_uri()