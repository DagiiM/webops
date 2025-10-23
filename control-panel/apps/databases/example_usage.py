"""
Example usage of the database abstraction layer.

This script demonstrates how to use the database adapters
to connect to different database types.
"""

from apps.databases.adapters.factory import DatabaseFactory
from apps.databases.adapters.base import ConnectionConfig, DatabaseType


def example_sqlite_usage():
    """Example of using SQLite adapter."""
    print("=== SQLite Example ===")
    
    # Create configuration
    config = ConnectionConfig(
        db_type=DatabaseType.SQLITE,
        database="/tmp/example.db"
    )
    
    # Create adapter using factory
    factory = DatabaseFactory()
    adapter = factory.create_adapter(config)
    
    # Use with context manager
    with adapter:
        # Execute queries
        result = adapter.execute_query(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"
        )
        print(f"Create table result: {result.success}")
        
        result = adapter.execute_query(
            "INSERT INTO users (name) VALUES (?)",
            {"name": "Alice"}
        )
        print(f"Insert result: {result.success}, rows affected: {result.rows_affected}")
        
        result = adapter.execute_query("SELECT * FROM users")
        print(f"Select result: {result.success}")
        if result.data:
            for row in result.data:
                print(f"  User: {row}")
        
        # Check health
        is_healthy = adapter.health_check()
        print(f"Database healthy: {is_healthy}")
        
        # Get metadata
        metadata = adapter.get_metadata()
        print(f"Database metadata: {metadata}")


def example_postgresql_usage():
    """Example of using PostgreSQL adapter."""
    print("\n=== PostgreSQL Example ===")
    
    # Create configuration
    config = ConnectionConfig(
        db_type=DatabaseType.POSTGRESQL,
        host="localhost",
        port=5432,
        database="webops_test",
        username="webops_user",
        password="secure_password",
        ssl_enabled=True,
        pool_size=5
    )
    
    # Create adapter using factory
    factory = DatabaseFactory()
    adapter = factory.create_adapter(config)
    
    # Use with context manager
    with adapter:
        # Execute queries with parameterized queries
        result = adapter.execute_query(
            "SELECT version() as version, current_database() as database"
        )
        print(f"Query result: {result.success}")
        if result.data:
            for row in result.data:
                print(f"  PostgreSQL {row['version']}, Database: {row['database']}")
        
        # Transaction example
        adapter.start_transaction()
        try:
            adapter.execute_query(
                "CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, name TEXT)"
            )
            adapter.execute_query(
                "INSERT INTO products (name) VALUES (%(name)s)",
                {"name": "Sample Product"}
            )
            adapter.commit_transaction()
            print("Transaction committed successfully")
        except Exception as e:
            adapter.rollback_transaction()
            print(f"Transaction rolled back: {e}")
        
        # Get metadata
        metadata = adapter.get_metadata()
        print(f"Database metadata: {metadata}")


def example_mongodb_usage():
    """Example of using MongoDB adapter."""
    print("\n=== MongoDB Example ===")
    
    # Create configuration
    config = ConnectionConfig(
        db_type=DatabaseType.MONGODB,
        host="localhost",
        port=27017,
        database="webops_test",
        username="mongo_user",
        password="secure_password",
        ssl_enabled=True
    )
    
    # Create adapter using factory
    factory = DatabaseFactory()
    adapter = factory.create_adapter(config)
    
    # Use with context manager
    with adapter:
        # Execute MongoDB operations
        # Note: For MongoDB, queries are JSON strings
        find_query = '{"operation": "find", "collection": "users", "filter": {}}'
        result = adapter.execute_query(find_query)
        print(f"Find result: {result.success}")
        if result.data:
            for doc in result.data:
                print(f"  Document: {doc}")
        
        # Insert a document
        insert_query = '{"operation": "insert_one", "collection": "logs", "document": {"level": "info", "message": "Test log"}}'
        result = adapter.execute_query(insert_query)
        print(f"Insert result: {result.success}, rows affected: {result.rows_affected}")
        
        # Get metadata
        metadata = adapter.get_metadata()
        print(f"Database metadata: {metadata}")


def list_available_adapters():
    """List all available database adapters."""
    print("=== Available Database Adapters ===")
    
    factory = DatabaseFactory()
    databases = factory.get_available_databases()
    
    for db_type, info in databases.items():
        print(f"\n{db_type.value.title()}:")
        print(f"  Description: {info['description']}")
        if info['dependencies']:
            print(f"  Dependencies: {', '.join(info['dependencies'])}")
        if info['install_command']:
            print(f"  Install: {info['install_command']}")


if __name__ == "__main__":
    # List available adapters
    list_available_adapters()
    
    # Run examples (commented out since they require actual databases)
    # example_sqlite_usage()
    # example_postgresql_usage()
    # example_mongodb_usage()
    
    print("\n=== Usage Instructions ===")
    print("1. Install required dependencies for your database type")
    print("2. Create a ConnectionConfig with your database details")
    print("3. Use DatabaseFactory to create an adapter")
    print("4. Use the adapter with a context manager (with statement)")
    print("5. Execute queries using execute_query() method")
    print("6. Use transactions with start_transaction(), commit_transaction(), rollback_transaction()")