"""
Autohealing and retry system for LLM deployments.

This module provides robust error recovery, automatic retries,
and self-healing capabilities for deployment operations.
"""

import time
import logging
from typing import Callable, Any, Optional, Tuple, Dict, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    IMMEDIATE = "immediate"  # Retry immediately
    LINEAR_BACKOFF = "linear"  # Wait 1s, 2s, 3s...
    EXPONENTIAL_BACKOFF = "exponential"  # Wait 1s, 2s, 4s, 8s...
    FIBONACCI = "fibonacci"  # Wait 1s, 1s, 2s, 3s, 5s, 8s...


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # 5 minutes max
    on_retry: Optional[Callable[[int, Exception], None]] = None


@dataclass
class RecoveryAction:
    """Represents a recovery action for a failure."""
    name: str
    action: Callable[[], bool]
    description: str
    auto_execute: bool = False  # Whether to execute automatically


class DeploymentAutoHealer:
    """
    Provides autohealing capabilities for deployment operations.

    Features:
    - Automatic retry with configurable strategies
    - Intelligent error detection and recovery
    - Partial download recovery
    - Build failure recovery
    - Resource cleanup
    """

    def __init__(self):
        """Initialize the autohealer."""
        self.retry_history: Dict[str, List[Dict[str, Any]]] = {}

    def retry_with_backoff(
        self,
        operation: Callable[[], Any],
        config: RetryConfig,
        operation_name: str = "operation"
    ) -> Tuple[bool, Any, Optional[Exception]]:
        """
        Execute an operation with retry and backoff logic.

        Args:
            operation: Function to execute
            config: Retry configuration
            operation_name: Name for logging

        Returns:
            Tuple of (success, result, last_exception)
        """
        last_exception = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                logger.info(f"Attempt {attempt}/{config.max_attempts} for {operation_name}")
                result = operation()

                # Record success
                self._record_attempt(operation_name, attempt, success=True)

                return True, result, None

            except Exception as e:
                last_exception = e
                self._record_attempt(operation_name, attempt, success=False, error=str(e))

                logger.warning(f"{operation_name} failed on attempt {attempt}: {e}")

                # Call retry callback if provided
                if config.on_retry:
                    try:
                        config.on_retry(attempt, e)
                    except Exception as callback_error:
                        logger.error(f"Retry callback failed: {callback_error}")

                # Don't sleep after the last attempt
                if attempt < config.max_attempts:
                    delay = self._calculate_delay(attempt, config)
                    logger.info(f"Waiting {delay:.1f}s before retry...")
                    time.sleep(delay)

        # All attempts failed
        logger.error(f"{operation_name} failed after {config.max_attempts} attempts")
        return False, None, last_exception

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay based on retry strategy."""
        if config.strategy == RetryStrategy.IMMEDIATE:
            return 0

        elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = config.base_delay * attempt

        elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = config.base_delay * (2 ** (attempt - 1))

        elif config.strategy == RetryStrategy.FIBONACCI:
            delay = config.base_delay * self._fibonacci(attempt)

        else:
            delay = config.base_delay

        # Cap at max delay
        return min(delay, config.max_delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number (fast iterative)."""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    def _record_attempt(self, operation: str, attempt: int, success: bool, error: str = ""):
        """Record attempt history for analytics."""
        if operation not in self.retry_history:
            self.retry_history[operation] = []

        self.retry_history[operation].append({
            'attempt': attempt,
            'success': success,
            'error': error,
            'timestamp': time.time()
        })

    def detect_recoverable_errors(self, error: Exception) -> List[RecoveryAction]:
        """
        Detect if an error is recoverable and suggest recovery actions.

        Args:
            error: The exception that occurred

        Returns:
            List of possible recovery actions
        """
        error_str = str(error).lower()
        actions = []

        # Network errors - usually temporary
        if any(keyword in error_str for keyword in ['connection', 'timeout', 'network', 'unreachable']):
            actions.append(RecoveryAction(
                name="wait_and_retry",
                action=lambda: True,
                description="Wait and retry (network issue likely temporary)",
                auto_execute=True
            ))

        # Disk space errors
        if any(keyword in error_str for keyword in ['no space', 'disk full', 'quota exceeded']):
            actions.append(RecoveryAction(
                name="cleanup_cache",
                action=lambda: self._cleanup_old_caches(),
                description="Clean up old model caches to free space",
                auto_execute=False
            ))

        # Permission errors
        if any(keyword in error_str for keyword in ['permission denied', 'access denied']):
            actions.append(RecoveryAction(
                name="fix_permissions",
                action=lambda: self._fix_permissions(),
                description="Attempt to fix file permissions",
                auto_execute=False
            ))

        # Corrupted download
        if any(keyword in error_str for keyword in ['corrupt', 'checksum', 'hash mismatch']):
            actions.append(RecoveryAction(
                name="clear_and_retry",
                action=lambda: True,
                description="Clear corrupted files and retry download",
                auto_execute=True
            ))

        # Build failures
        if any(keyword in error_str for keyword in ['compilation failed', 'build error', 'make error']):
            actions.append(RecoveryAction(
                name="clean_build",
                action=lambda: self._clean_build_artifacts(),
                description="Clean build artifacts and retry",
                auto_execute=True
            ))

        return actions

    def _cleanup_old_caches(self) -> bool:
        """Clean up old model caches."""
        # Placeholder - would implement cache cleanup logic
        logger.info("Cleaning up old caches...")
        return True

    def _fix_permissions(self) -> bool:
        """Attempt to fix file permissions."""
        # Placeholder - would implement permission fixing logic
        logger.info("Attempting to fix permissions...")
        return True

    def _clean_build_artifacts(self) -> bool:
        """Clean build artifacts."""
        logger.info("Cleaning build artifacts...")
        return True

    def auto_recover(
        self,
        operation: Callable[[], Any],
        error: Exception,
        operation_name: str = "operation"
    ) -> Tuple[bool, Any]:
        """
        Automatically attempt to recover from an error.

        Args:
            operation: Operation to retry after recovery
            error: The error that occurred
            operation_name: Name for logging

        Returns:
            Tuple of (success, result)
        """
        logger.info(f"Attempting auto-recovery for {operation_name}")

        # Detect possible recovery actions
        actions = self.detect_recoverable_errors(error)

        # Execute auto-executable actions
        for action in actions:
            if action.auto_execute:
                logger.info(f"Executing recovery action: {action.description}")
                try:
                    if action.action():
                        logger.info(f"Recovery action '{action.name}' succeeded")
                        # Retry the operation
                        try:
                            result = operation()
                            return True, result
                        except Exception as retry_error:
                            logger.warning(f"Operation failed after recovery: {retry_error}")
                    else:
                        logger.warning(f"Recovery action '{action.name}' failed")
                except Exception as action_error:
                    logger.error(f"Recovery action '{action.name}' raised error: {action_error}")

        return False, None

    def cleanup_failed_deployment(self, deployment_path: Path) -> bool:
        """
        Clean up artifacts from a failed deployment.

        Args:
            deployment_path: Path to deployment directory

        Returns:
            True if cleanup succeeded
        """
        try:
            logger.info(f"Cleaning up failed deployment at {deployment_path}")

            # List of patterns to clean
            cleanup_patterns = [
                "**/*.pyc",
                "**/__pycache__",
                "**/build",
                "**/dist",
                "**/*.egg-info",
                "**/venv/build",
                "**/.tmp",
            ]

            for pattern in cleanup_patterns:
                for path in deployment_path.glob(pattern):
                    try:
                        if path.is_file():
                            path.unlink()
                        elif path.is_dir():
                            import shutil
                            shutil.rmtree(path)
                        logger.debug(f"Removed: {path}")
                    except Exception as e:
                        logger.warning(f"Could not remove {path}: {e}")

            logger.info("Cleanup completed")
            return True

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return False

    def verify_deployment_integrity(
        self,
        deployment_path: Path,
        required_files: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Verify deployment has all required files.

        Args:
            deployment_path: Path to deployment
            required_files: List of required file paths (relative)

        Returns:
            Tuple of (is_valid, list_of_missing_files)
        """
        missing = []

        for file_path in required_files:
            full_path = deployment_path / file_path
            if not full_path.exists():
                missing.append(file_path)

        is_valid = len(missing) == 0

        if not is_valid:
            logger.warning(f"Deployment integrity check failed. Missing: {missing}")

        return is_valid, missing

    def get_retry_statistics(self, operation_name: str) -> Dict[str, Any]:
        """
        Get retry statistics for an operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Dictionary with statistics
        """
        if operation_name not in self.retry_history:
            return {
                'total_attempts': 0,
                'successes': 0,
                'failures': 0,
                'success_rate': 0.0
            }

        attempts = self.retry_history[operation_name]
        successes = sum(1 for a in attempts if a['success'])
        failures = len(attempts) - successes

        return {
            'total_attempts': len(attempts),
            'successes': successes,
            'failures': failures,
            'success_rate': successes / len(attempts) if attempts else 0.0,
            'attempts': attempts
        }


# Global instance
autohealer = DeploymentAutoHealer()
