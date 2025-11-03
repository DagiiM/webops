"""
Structured logging configuration for addon system.

Provides JSON logging with correlation IDs, context tracking,
and log aggregation for better observability.
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

from django.http import HttpRequest


# ============================================================================
# Log Levels
# ============================================================================

class LogLevel:
    """Standard log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# ============================================================================
# Correlation ID Management
# ============================================================================

class CorrelationIDManager:
    """Manages correlation IDs for request tracking."""

    _current_correlation_id: Optional[str] = None

    @classmethod
    def get_correlation_id(cls) -> str:
        """
        Get current correlation ID or generate a new one.

        Returns:
            Correlation ID string
        """
        if cls._current_correlation_id is None:
            cls._current_correlation_id = str(uuid.uuid4())
        return cls._current_correlation_id

    @classmethod
    def set_correlation_id(cls, correlation_id: str):
        """Set correlation ID for current context."""
        cls._current_correlation_id = correlation_id

    @classmethod
    def clear_correlation_id(cls):
        """Clear current correlation ID."""
        cls._current_correlation_id = None

    @classmethod
    def extract_from_request(cls, request: HttpRequest) -> str:
        """
        Extract or generate correlation ID from HTTP request.

        Args:
            request: Django HTTP request

        Returns:
            Correlation ID
        """
        # Check for existing correlation ID in headers
        correlation_id = request.META.get('HTTP_X_CORRELATION_ID')

        if not correlation_id:
            # Generate new correlation ID
            correlation_id = str(uuid.uuid4())

        cls.set_correlation_id(correlation_id)
        return correlation_id


# ============================================================================
# Structured Logger
# ============================================================================

class StructuredLogger:
    """
    Structured logger with JSON formatting and context.

    Provides consistent log formatting with automatic context injection.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually __name__)
        """
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """
        Set context fields for all subsequent logs.

        Args:
            **kwargs: Context key-value pairs
        """
        self.context.update(kwargs)

    def clear_context(self):
        """Clear all context fields."""
        self.context.clear()

    def _build_log_entry(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """
        Build structured log entry.

        Args:
            level: Log level
            message: Log message
            extra: Additional fields
            exc_info: Exception information

        Returns:
            Dictionary containing log entry
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message,
            'correlation_id': CorrelationIDManager.get_correlation_id(),
            'logger': self.logger.name,
        }

        # Add context
        if self.context:
            entry['context'] = self.context.copy()

        # Add extra fields
        if extra:
            entry['extra'] = extra

        # Add exception info
        if exc_info:
            entry['exception'] = {
                'type': type(exc_info).__name__,
                'message': str(exc_info),
            }

        return entry

    def _log(
        self,
        level: int,
        level_name: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Exception] = None
    ):
        """
        Internal log method.

        Args:
            level: Numeric log level
            level_name: String log level
            message: Log message
            extra: Additional fields
            exc_info: Exception information
        """
        log_entry = self._build_log_entry(level_name, message, extra, exc_info)

        # Log as JSON in production, readable format in development
        if self.logger.isEnabledFor(level):
            self.logger.log(level, json.dumps(log_entry), exc_info=exc_info)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, 'DEBUG', message, kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, 'INFO', message, kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, 'WARNING', message, kwargs)

    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, 'ERROR', message, kwargs, exc_info)

    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, 'CRITICAL', message, kwargs, exc_info)


# ============================================================================
# Logging Decorators
# ============================================================================

def log_operation(operation_name: str, include_args: bool = False):
    """
    Decorator to automatically log operation start/end/duration.

    Args:
        operation_name: Name of operation being logged
        include_args: Whether to include function arguments in logs

    Example:
        @log_operation('install_addon')
        def install_addon(name: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)

            # Build context
            context = {'operation': operation_name}

            if include_args:
                context['args'] = {
                    'positional': [str(arg) for arg in args],
                    'keyword': {k: str(v) for k, v in kwargs.items()}
                }

            logger.info(f'Starting {operation_name}', **context)

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(
                    f'Completed {operation_name}',
                    duration_seconds=duration,
                    status='success',
                    **context
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    f'Failed {operation_name}',
                    exc_info=e,
                    duration_seconds=duration,
                    status='failure',
                    **context
                )

                raise

        return wrapper
    return decorator


def log_api_call(endpoint: str):
    """
    Decorator to log API endpoint calls.

    Args:
        endpoint: API endpoint name

    Example:
        @log_api_call('list_addons')
        def list_addons(request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            logger = StructuredLogger(func.__module__)

            # Extract correlation ID from request
            correlation_id = CorrelationIDManager.extract_from_request(request)

            # Build context
            context = {
                'endpoint': endpoint,
                'method': request.method,
                'path': request.path,
                'user': request.user.username if request.user.is_authenticated else 'anonymous',
                'ip': request.META.get('REMOTE_ADDR'),
            }

            logger.info(f'API call: {endpoint}', **context)

            start_time = time.time()
            try:
                result = func(request, *args, **kwargs)
                duration = time.time() - start_time

                # Get status code from response
                status_code = getattr(result, 'status_code', 200)

                logger.info(
                    f'API call completed: {endpoint}',
                    duration_seconds=duration,
                    status_code=status_code,
                    status='success',
                    **context
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                logger.error(
                    f'API call failed: {endpoint}',
                    exc_info=e,
                    duration_seconds=duration,
                    status='failure',
                    **context
                )

                raise

            finally:
                # Clear correlation ID after request
                CorrelationIDManager.clear_correlation_id()

        return wrapper
    return decorator


# ============================================================================
# Context Managers
# ============================================================================

@contextmanager
def log_context(**kwargs):
    """
    Context manager to add context for a block of code.

    Args:
        **kwargs: Context key-value pairs

    Example:
        with log_context(user='admin', addon='postgresql'):
            logger.info('Installing addon')
    """
    logger = StructuredLogger(__name__)

    # Save previous context
    previous_context = logger.context.copy()

    # Set new context
    logger.set_context(**kwargs)

    try:
        yield logger
    finally:
        # Restore previous context
        logger.context = previous_context


@contextmanager
def log_operation_context(operation: str, **kwargs):
    """
    Context manager for logging an operation with automatic start/end.

    Args:
        operation: Operation name
        **kwargs: Additional context

    Example:
        with log_operation_context('install_addon', addon_name='postgresql'):
            # Installation logic
            pass
    """
    logger = StructuredLogger(__name__)

    context = {'operation': operation}
    context.update(kwargs)

    logger.info(f'Starting {operation}', **context)

    start_time = time.time()
    try:
        yield logger
        duration = time.time() - start_time

        logger.info(
            f'Completed {operation}',
            duration_seconds=duration,
            status='success',
            **context
        )

    except Exception as e:
        duration = time.time() - start_time

        logger.error(
            f'Failed {operation}',
            exc_info=e,
            duration_seconds=duration,
            status='failure',
            **context
        )

        raise


# ============================================================================
# Log Aggregation & Analysis
# ============================================================================

class LogAggregator:
    """Aggregates and analyzes log entries."""

    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def add_log(self, log_entry: Dict[str, Any]):
        """Add a log entry."""
        self.logs.append(log_entry)

    def filter_by_level(self, level: str) -> List[Dict[str, Any]]:
        """Filter logs by level."""
        return [log for log in self.logs if log.get('level') == level]

    def filter_by_correlation_id(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Filter logs by correlation ID."""
        return [log for log in self.logs if log.get('correlation_id') == correlation_id]

    def filter_by_operation(self, operation: str) -> List[Dict[str, Any]]:
        """Filter logs by operation."""
        return [
            log for log in self.logs
            if log.get('context', {}).get('operation') == operation
        ]

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get all error and critical logs."""
        return [
            log for log in self.logs
            if log.get('level') in ['ERROR', 'CRITICAL']
        ]

    def get_operations_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics for operations.

        Returns:
            Dictionary mapping operation names to statistics
        """
        operations = {}

        for log in self.logs:
            context = log.get('context', {})
            operation = context.get('operation')

            if not operation:
                continue

            if operation not in operations:
                operations[operation] = {
                    'count': 0,
                    'success': 0,
                    'failure': 0,
                    'total_duration': 0.0,
                    'durations': []
                }

            operations[operation]['count'] += 1

            status = context.get('status')
            if status == 'success':
                operations[operation]['success'] += 1
            elif status == 'failure':
                operations[operation]['failure'] += 1

            duration = log.get('extra', {}).get('duration_seconds')
            if duration is not None:
                operations[operation]['total_duration'] += duration
                operations[operation]['durations'].append(duration)

        # Calculate averages
        for op_stats in operations.values():
            if op_stats['durations']:
                op_stats['avg_duration'] = (
                    op_stats['total_duration'] / len(op_stats['durations'])
                )
                op_stats['min_duration'] = min(op_stats['durations'])
                op_stats['max_duration'] = max(op_stats['durations'])

            # Remove durations list (not needed in summary)
            del op_stats['durations']

        return operations

    def clear(self):
        """Clear all logs."""
        self.logs.clear()


# ============================================================================
# Helper Functions
# ============================================================================

def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


def format_log_entry(log_entry: Dict[str, Any], pretty: bool = False) -> str:
    """
    Format log entry as JSON string.

    Args:
        log_entry: Log entry dictionary
        pretty: Whether to pretty-print JSON

    Returns:
        JSON string
    """
    if pretty:
        return json.dumps(log_entry, indent=2, sort_keys=True)
    return json.dumps(log_entry)


# ============================================================================
# Global Logger Instance
# ============================================================================

# Create a global logger for addon operations
addon_logger = get_logger('apps.addons')
