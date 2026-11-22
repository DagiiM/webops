"""
Database service for WebOps.

"Database Management" section

This module implements database operations:
- PostgreSQL database creation
- User management
- Privilege granting
- Credential encryption
"""

import logging
import re
from typing import Dict, Any, Optional
from django.conf import settings

from apps.core.utils import generate_password, encrypt_password, decrypt_password
from .models import Database

# Import psycopg2 for database operations
try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing PostgreSQL databases."""

    def __init__(self):
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is not installed. "
                "Install with: pip install psycopg2-binary"
            )
        self.postgres_user = 'postgres'
        self.connection_params = {
            'host': 'localhost',
            'port': 5432,
            'user': self.postgres_user,
            'password': None, # Will be set from environment or defaults
            'database': 'postgres'
        }

    def _validate_identifier(self, identifier: str) -> bool:
        """
        Validate that an identifier (database name, username) is safe.
        Only allows alphanumeric characters and underscores.
        Enforces length limits and prevents special characters.
        """
        if not identifier:
            return False
        
        # Length validation to prevent buffer overflow attacks
        if len(identifier) > 63:  # PostgreSQL identifier limit
            return False
            
        # Only allow alphanumeric characters and underscores, starting with letter
        # Prevents SQL injection and command injection
        return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', identifier))

    def _validate_sql_query(self, statement: str) -> bool:
        """Defense in depth for SQL admin queries; not a substitute for parameters."""
        if not isinstance(statement, str) or not statement.strip() or len(statement)>1000000:
            return False
        if re.search(r";|--|/\*|\*/|\bunion\b|\bxp_cmdshell\b",statement,re.I):
            return False
        return bool(re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|GRANT|REVOKE)\b",statement,re.I))

    def _connect_as_superuser(self):
        """
        Create a connection as superuser to perform administrative tasks.
        """
        try:
            # In production, this would connect using a superuser account
            # For now, we'll use the default postgres user with a password
            # In a real implementation, this would be configured securely
            return psycopg2.connect(**self.connection_params)
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL as superuser: {e}")
            raise

    def execute_sql(self, statement: str, database: str = 'postgres',
                    params: Optional[tuple] = None) -> tuple[bool,str]:
        """Run real, parameterized admin SQL. Never simulate writes in DEBUG."""
        if not self._validate_sql_query(statement):
            return False,"Invalid SQL query detected"
        conn=None
        try:
            cp=dict(self.connection_params);cp['database']=database
            conn=psycopg2.connect(**cp)
            with conn.cursor() as cursor:
                try:
                    cursor.execute(statement,params) if params is not None else cursor.execute(statement)
                    out=str(cursor.fetchall()) if cursor.description else f"Query executed successfully. Rows affected: {cursor.rowcount}"
                    conn.commit()
                finally:cursor.close()
            return True,out
        except psycopg2.Error:
            logger.exception("Database operation failed")
            if conn:conn.rollback()
            return False,"Database operation failed"
        except Exception:
            logger.exception("Database unexpected operation failure")
            if conn:conn.rollback()
            return False,"Database operation failed"
        finally:
            if conn:conn.close()

    def _record_exists(self, statement, value):
        conn=None
        try:
            conn=psycopg2.connect(**self.connection_params)
            with conn.cursor() as cursor:
                try:
                    cursor.execute(statement,(value,))
                    return cursor.fetchone() is not None
                finally:cursor.close()
        except psycopg2.Error:
            logger.exception("Database existence check failed")
            return False
        finally:
            if conn:conn.close()

    def database_exists(self, db_name):
        return self._validate_identifier(db_name) and self._record_exists(
            "SELECT 1 FROM pg_database WHERE datname = %s", db_name)

    def user_exists(self, username):
        return self._validate_identifier(username) and self._record_exists(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", username)

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
        # Validate database name
        if not self._validate_identifier(db_name):
            return False, f"Invalid database name: {db_name}"
            
        if owner and not self._validate_identifier(owner):
            return False, f"Invalid owner username: {owner}"
        
        if self.database_exists(db_name):
            return False, f"Database {db_name} already exists"

        if owner:
            sql = "CREATE DATABASE %s WITH OWNER %s"
            success, output = self.execute_sql(sql, params=(db_name, owner))
        else:
            sql = "CREATE DATABASE %s"
            success, output = self.execute_sql(sql, params=(db_name,))

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
        # Validate username
        if not self._validate_identifier(username):
            return False, f"Invalid username: {username}"
        
        if self.user_exists(username):
            return False, f"User {username} already exists"

        # Using psycopg2.sql to safely compose the SQL with the username identifier
        # and password parameter to prevent SQL injection
        from psycopg2 import sql
        query = sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
            sql.Identifier(username)
        )
        
        success, output = self.execute_sql(query.as_string(None), params=(password,))
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
        # Validate inputs
        if not self._validate_identifier(db_name):
            return False, f"Invalid database name: {db_name}"
        
        if not self._validate_identifier(username):
            return False, f"Invalid username: {username}"
        
        # Using psycopg2.sql to safely compose the SQL with identifier parameters
        from psycopg2 import sql
        query = sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
            sql.Identifier(db_name),
            sql.Identifier(username)
        )
        
        success, output = self.execute_sql(query.as_string(None))
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
            # TODO #16: Clean up database user on deletion
            # See: docs/TODO_TRACKING.md for details
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
        # Validate database name
        if not self._validate_identifier(db_name):
            return False, f"Invalid database name: {db_name}"
            
        if not self.database_exists(db_name):
            return False, f"Database {db_name} does not exist"

        # Terminate connections using parameterized query approach
        from psycopg2 import sql
        terminate_query = sql.SQL("""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = %s
          AND pid <> pg_backend_pid();
        """)
        self.execute_sql(terminate_query.as_string(None), params=(db_name,))

        # Drop database using identifier for safety
        drop_query = sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name))
        success, output = self.execute_sql(drop_query.as_string(None))

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
        # Validate username
        if not self._validate_identifier(username):
            return False, f"Invalid username: {username}"
            
        if not self.user_exists(username):
            return False, f"User {username} does not exist"

        # Using psycopg2.sql to safely compose the SQL with identifier parameters
        from psycopg2 import sql
        query = sql.SQL("DROP USER {}").format(sql.Identifier(username))
        success, output = self.execute_sql(query.as_string(None))

        if success:
            logger.info(f"Deleted user: {username}")
            return True, f"User {username} deleted successfully"
        else:
            return False, "Failed to delete user"