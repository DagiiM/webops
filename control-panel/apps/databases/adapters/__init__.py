"""
Database adapters for WebOps.

This package provides adapters for different database engines
through a unified interface.
"""

from .base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    DatabaseType,
    DatabaseException,
    ConnectionException,
    QueryExecutionException,
    TransactionException,
    ConfigurationException,
)

from .factory import DatabaseFactory, adapter_registry

__all__ = [
    'DatabaseAdapter',
    'ConnectionConfig',
    'QueryResult',
    'DatabaseType',
    'DatabaseException',
    'ConnectionException',
    'QueryExecutionException',
    'TransactionException',
    'ConfigurationException',
    'DatabaseFactory',
    'adapter_registry',
]