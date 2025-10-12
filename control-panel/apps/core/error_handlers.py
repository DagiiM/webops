"""
Comprehensive Error Handling for WebOps.

Implements "no broken windows" philosophy - handles all possible errors gracefully.
"""

from typing import Any, Dict, Optional
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
import logging
import traceback
import sys

logger = logging.getLogger(__name__)


class ErrorContext:
    """Error context builder for consistent error responses."""

    def __init__(
        self,
        status_code: int,
        error_type: str,
        message: str,
        user_message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.user_message = user_message or self._get_default_user_message(status_code)
        self.details = details or {}

    def _get_default_user_message(self, status_code: int) -> str:
        """Get user-friendly message for status code."""
        messages = {
            400: "The request could not be processed. Please check your input and try again.",
            401: "You need to be logged in to access this resource.",
            403: "You don't have permission to access this resource.",
            404: "The requested resource was not found.",
            405: "This action is not allowed.",
            408: "The request took too long to complete. Please try again.",
            429: "Too many requests. Please slow down and try again later.",
            500: "An unexpected error occurred. We've been notified and will fix it soon.",
            502: "The service is temporarily unavailable. Please try again in a moment.",
            503: "The service is currently under maintenance. Please try again later.",
            504: "The request took too long to complete. Please try again.",
        }
        return messages.get(status_code, "An error occurred. Please try again.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON responses."""
        return {
            'error': True,
            'status': self.status_code,
            'type': self.error_type,
            'message': self.user_message,
            'details': self.details
        }

    def to_json_response(self) -> JsonResponse:
        """Return as JSON response."""
        return JsonResponse(self.to_dict(), status=self.status_code)


def log_error(
    error: Exception,
    request: Optional[HttpRequest] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log error with full context for debugging.

    Args:
        error: The exception that occurred
        request: The HTTP request (if available)
        context: Additional context information
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc()
    }

    if request:
        error_info.update({
            'url': request.get_full_path(),
            'method': request.method,
            'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        })

    if context:
        error_info['context'] = context

    logger.error(
        f"Error occurred: {error_info['error_type']} - {error_info['error_message']}",
        extra=error_info,
        exc_info=True
    )


@requires_csrf_token
def handler400(request: HttpRequest, exception=None) -> Any:
    """Handle 400 Bad Request errors."""
    error_ctx = ErrorContext(
        status_code=400,
        error_type='Bad Request',
        message='Invalid request format',
        details={'exception': str(exception)} if exception else {}
    )

    log_error(
        Exception(f"Bad Request: {exception}"),
        request=request
    )

    if request.META.get('HTTP_ACCEPT') == 'application/json':
        return error_ctx.to_json_response()

    return render(request, 'errors/400.html', {
        'error': error_ctx
    }, status=400)


@requires_csrf_token
def handler403(request: HttpRequest, exception=None) -> Any:
    """Handle 403 Forbidden errors."""
    error_ctx = ErrorContext(
        status_code=403,
        error_type='Forbidden',
        message='Access denied',
        user_message='You don\'t have permission to access this resource. '
                    'If you believe this is an error, please contact support.'
    )

    log_error(
        Exception(f"Forbidden: {exception}"),
        request=request
    )

    if request.META.get('HTTP_ACCEPT') == 'application/json':
        return error_ctx.to_json_response()

    return render(request, 'errors/403.html', {
        'error': error_ctx
    }, status=403)


@requires_csrf_token
def handler404(request: HttpRequest, exception=None) -> Any:
    """Handle 404 Not Found errors."""
    error_ctx = ErrorContext(
        status_code=404,
        error_type='Not Found',
        message='Resource not found',
        user_message=f'The page "{request.path}" was not found. '
                    'It may have been moved or deleted.',
        details={'path': request.path}
    )

    # Don't log 404s for static files and favicon
    if not request.path.startswith('/static/') and request.path != '/favicon.ico':
        logger.warning(f"404 Not Found: {request.path}")

    if request.META.get('HTTP_ACCEPT') == 'application/json':
        return error_ctx.to_json_response()

    return render(request, 'errors/404.html', {
        'error': error_ctx
    }, status=404)


@requires_csrf_token
def handler500(request: HttpRequest) -> Any:
    """Handle 500 Internal Server Error."""
    # Get exception info from sys.exc_info()
    exc_type, exc_value, exc_traceback = sys.exc_info()

    error_ctx = ErrorContext(
        status_code=500,
        error_type='Internal Server Error',
        message='Unexpected server error',
        user_message='An unexpected error occurred. Our team has been notified '
                    'and will investigate the issue.'
    )

    if exc_value:
        log_error(exc_value, request=request)
    else:
        logger.error("500 Internal Server Error (no exception info available)")

    if request.META.get('HTTP_ACCEPT') == 'application/json':
        return error_ctx.to_json_response()

    return render(request, 'errors/500.html', {
        'error': error_ctx
    }, status=500)


class SafeExecutor:
    """
    Context manager for safe execution with error handling.

    Usage:
        with SafeExecutor() as executor:
            result = executor.execute(risky_function, arg1, arg2)
            if executor.has_error:
                # Handle error
                print(executor.error_message)
    """

    def __init__(self, default_value: Any = None, log_errors: bool = True):
        self.default_value = default_value
        self.log_errors = log_errors
        self.error: Optional[Exception] = None
        self.error_message: str = ''
        self.has_error: bool = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if exc_type is not None:
            self.error = exc_value
            self.error_message = str(exc_value)
            self.has_error = True

            if self.log_errors:
                log_error(exc_value)

            # Suppress exception
            return True
        return False

    def execute(self, func, *args, **kwargs) -> Any:
        """Execute function with error handling."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.error = e
            self.error_message = str(e)
            self.has_error = True

            if self.log_errors:
                log_error(e)

            return self.default_value


def safe_json_response(
    func,
    *args,
    error_message: str = "An error occurred",
    **kwargs
) -> JsonResponse:
    """
    Wrapper for functions that return JSON responses.
    Ensures errors are always returned as proper JSON.

    Args:
        func: Function to execute
        *args: Positional arguments for func
        error_message: Error message to return on failure
        **kwargs: Keyword arguments for func

    Returns:
        JsonResponse with success or error data
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_error(e)

        error_ctx = ErrorContext(
            status_code=500,
            error_type=type(e).__name__,
            message=str(e),
            user_message=error_message
        )

        return error_ctx.to_json_response()


def validate_or_error(
    condition: bool,
    status_code: int,
    error_type: str,
    message: str,
    user_message: Optional[str] = None
) -> Optional[JsonResponse]:
    """
    Validate condition and return error response if false.

    Args:
        condition: Condition to validate
        status_code: HTTP status code for error
        error_type: Type of error
        message: Internal error message
        user_message: User-friendly error message

    Returns:
        JsonResponse with error if condition is False, None otherwise
    """
    if not condition:
        error_ctx = ErrorContext(
            status_code=status_code,
            error_type=error_type,
            message=message,
            user_message=user_message
        )
        return error_ctx.to_json_response()
    return None
