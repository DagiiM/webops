"""
Database service for WebOps.

"Database Management" section

This module implements database operations:
- PostgreSQL database creation
- User management
- Privilege granting
- Credential encryption
"""

import subprocess
import logging
from typing import Dict, Any, Optional
from django.conf import settings

from apps.core.utils import generate_password, encrypt_password, decrypt_password
from .models import Database

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing PostgreSQL databases."""

    def __init__(self):
        self.postgres_user = 'postgres'

    def execute_sql(self, sql: str, database: str = 'postgres') -> tuple[bool, str]:
        """
        Execute SQL command as postgres user.

        Args:
            sql: SQL command to execute
            database: Database to connect to

        Returns:
            Tuple of (success, output)
        """
        # Development mode: Skip actual PostgreSQL operations if DEBUG is True
        if getattr(settings, 'DEBUG', False):
            logger.info(f"[DEV MODE] Would execute SQL: {sql}")
            return True, "Development mode: SQL simulated"

        try:
            result = subprocess.run(
                ['sudo', '-u', self.postgres_user, 'psql', '-d', database, '-c', sql],
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"SQL execution failed: {e.stderr}")
            return False, e.stderr

    def database_exists(self, db_name: str) -> bool:
        """
        Check if database exists.

        Args:
            db_name: Database name

        Returns:
            True if exists, False otherwise
        """
        # Development mode: Check our database model instead
        if getattr(settings, 'DEBUG', False):
            return Database.objects.filter(name=db_name).exists()

        sql = f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"
        success, output = self.execute_sql(sql)
        return success and '1 row' in output

    def user_exists(self, username: str) -> bool:
        """
        Check if PostgreSQL user exists.

        Args:
            username: Username to check

        Returns:
            True if exists, False otherwise
        """
        # Development mode: Check our database model instead
        if getattr(settings, 'DEBUG', False):
            return Database.objects.filter(username=username).exists()

        sql = f"SELECT 1 FROM pg_roles WHERE rolname='{username}'"
        success, output = self.execute_sql(sql)
        return success and '1 row' in output

    def create_database(
        self,
        db_name: str,
        owner: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Create PostgreSQL database.

        Args:
            db_name: Database name
            owner: Optional owner username

        Returns:
            Tuple of (success, message)
        """
        if self.database_exists(db_name):
            return False, f"Database {db_name} already exists"

        owner_clause = f"OWNER {owner}" if owner else ""
        sql = f"CREATE DATABASE {db_name} {owner_clause}"

        success, output = self.execute_sql(sql)
        if success:
            logger.info(f"Created database: {db_name}")
            return True, f"Database {db_name} created successfully"
        else:
            return False, f"Failed to create database: {output}"

    def create_user(
        self,
        username: str,
        password: str
    ) -> tuple[bool, str]:
        """
        Create PostgreSQL user.

        Args:
            username: Username
            password: User password

        Returns:
            Tuple of (success, message)
        """
        if self.user_exists(username):
            return False, f"User {username} already exists"

        sql = f"CREATE USER {username} WITH PASSWORD '{password}'"

        success, output = self.execute_sql(sql)
        if success:
            logger.info(f"Created user: {username}")
            return True, f"User {username} created successfully"
        else:
            return False, f"Failed to create user: {output}"

    def grant_privileges(
        self,
        db_name: str,
        username: str
    ) -> tuple[bool, str]:
        """
        Grant all privileges on database to user.

        Args:
            db_name: Database name
            username: Username

        Returns:
            Tuple of (success, message)
        """
        sql = f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {username}"

        success, output = self.execute_sql(sql)
        if success:
            logger.info(f"Granted privileges on {db_name} to {username}")
            return True, "Privileges granted successfully"
        else:
            return False, f"Failed to grant privileges: {output}"

    def create_database_for_deployment(
        self,
        deployment,
        db_name: Optional[str] = None
    ) -> Optional[Database]:
        """
        Create database for a deployment.

        Args:
            deployment: Deployment instance
            db_name: Optional database name (defaults to deployment name)

        Returns:
            Database instance or None if failed
        """
        if db_name is None:
            db_name = f"{deployment.name.replace('-', '_')}_db"

        username = f"{deployment.name.replace('-', '_')}_user"
        password = generate_password(32)

        # Create user
        success, message = self.create_user(username, password)
        if not success:
            logger.error(f"Failed to create user for {deployment.name}: {message}")
            return None

        # Create database
        success, message = self.create_database(db_name, owner=username)
        if not success:
            logger.error(f"Failed to create database for {deployment.name}: {message}")
            # TODO: Clean up user
            return None

        # Grant privileges
        success, message = self.grant_privileges(db_name, username)
        if not success:
            logger.warning(f"Failed to grant privileges: {message}")

        # Encrypt password and save to database
        encrypted_password = encrypt_password(password)

        db = Database.objects.create(
            name=db_name,
            username=username,
            password=encrypted_password,
            host='localhost',
            port=5432,
            deployment=deployment
        )

        logger.info(f"Created database {db_name} for deployment {deployment.name}")
        return db

    def get_connection_string(
        self,
        database: Database,
        decrypted: bool = True
    ) -> str:
        """
        Get database connection string.

        Args:
            database: Database instance
            decrypted: If True, decrypt password

        Returns:
            PostgreSQL connection string
        """
        if decrypted:
            password = decrypt_password(database.password)
        else:
            password = '****'

        return database.get_connection_string(password)

    def delete_database(self, db_name: str) -> tuple[bool, str]:
        """
        Delete PostgreSQL database.

        Args:
            db_name: Database name

        Returns:
            Tuple of (success, message)
        """
        if not self.database_exists(db_name):
            return False, f"Database {db_name} does not exist"

        # Terminate connections
        terminate_sql = f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{db_name}'
          AND pid <> pg_backend_pid();
        """
        self.execute_sql(terminate_sql)

        # Drop database
        sql = f"DROP DATABASE {db_name}"
        success, output = self.execute_sql(sql)

        if success:
            logger.info(f"Deleted database: {db_name}")
            return True, f"Database {db_name} deleted successfully"
        else:
            return False, f"Failed to delete database: {output}"

    def delete_user(self, username: str) -> tuple[bool, str]:
        """
        Delete PostgreSQL user.

        Args:
            username: Username

        Returns:
            Tuple of (success, message)
        """
        if not self.user_exists(username):
            return False, f"User {username} does not exist"

        sql = f"DROP USER {username}"
        success, output = self.execute_sql(sql)

        if success:
            logger.info(f"Deleted user: {username}")
            return True, f"User {username} deleted successfully"
        else:
            return False, f"Failed to delete user: {output}"