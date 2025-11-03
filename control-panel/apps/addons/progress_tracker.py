"""
Progress tracking for long-running addon operations.

Provides real-time progress updates for installation, uninstallation,
and configuration operations with percentage completion, current step,
and estimated time remaining.
"""

import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from dataclasses import dataclass, asdict
from enum import Enum

from .logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Progress Status Enum
# ============================================================================

class ProgressStatus(str, Enum):
    """Progress status values."""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


# ============================================================================
# Progress Data Classes
# ============================================================================

@dataclass
class ProgressStep:
    """Represents a single step in progress."""
    name: str
    weight: float = 1.0  # Relative weight for progress calculation
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ProgressStatus = ProgressStatus.PENDING
    message: str = ''
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert datetime to ISO format
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


@dataclass
class ProgressInfo:
    """Complete progress information."""
    operation_id: str
    operation_type: str  # install, uninstall, configure
    addon_name: str
    status: ProgressStatus
    current_step: str
    steps: List[ProgressStep]
    percentage: float  # 0-100
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: str = ''
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type,
            'addon_name': self.addon_name,
            'status': self.status.value,
            'current_step': self.current_step,
            'steps': [step.to_dict() for step in self.steps],
            'percentage': round(self.percentage, 2),
            'started_at': self.started_at.isoformat(),
            'estimated_completion': (
                self.estimated_completion.isoformat()
                if self.estimated_completion else None
            ),
            'completed_at': (
                self.completed_at.isoformat()
                if self.completed_at else None
            ),
            'message': self.message,
            'error': self.error,
        }


# ============================================================================
# Progress Tracker
# ============================================================================

class ProgressTracker:
    """
    Tracks progress of long-running addon operations.

    Stores progress in cache for real-time retrieval and provides
    percentage calculation, ETA estimation, and step management.
    """

    CACHE_PREFIX = 'addon_progress'
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, operation_id: str, operation_type: str, addon_name: str):
        """
        Initialize progress tracker.

        Args:
            operation_id: Unique identifier for operation
            operation_type: Type of operation (install, uninstall, configure)
            addon_name: Name of addon
        """
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.addon_name = addon_name
        self.cache_key = f'{self.CACHE_PREFIX}:{operation_id}'

    def start(self, steps: List[Dict[str, Any]]):
        """
        Start tracking progress.

        Args:
            steps: List of step definitions with 'name' and optional 'weight'
        """
        # Create ProgressStep objects
        progress_steps = [
            ProgressStep(
                name=step['name'],
                weight=step.get('weight', 1.0)
            )
            for step in steps
        ]

        # Create ProgressInfo
        progress_info = ProgressInfo(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            addon_name=self.addon_name,
            status=ProgressStatus.RUNNING,
            current_step=progress_steps[0].name if progress_steps else '',
            steps=progress_steps,
            percentage=0.0,
            started_at=timezone.now(),
            message='Starting operation...'
        )

        # Save to cache
        self._save_progress(progress_info)

        logger.info(
            'Started progress tracking',
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            addon_name=self.addon_name,
            step_count=len(steps)
        )

    def update_step(
        self,
        step_name: str,
        status: ProgressStatus,
        message: str = '',
        error: Optional[str] = None
    ):
        """
        Update a specific step's status.

        Args:
            step_name: Name of step to update
            status: New status
            message: Status message
            error: Error message if failed
        """
        progress = self._load_progress()
        if not progress:
            logger.warning(
                'Progress not found for update',
                operation_id=self.operation_id,
                step_name=step_name
            )
            return

        # Find and update step
        step_found = False
        for step in progress.steps:
            if step.name == step_name:
                step.status = status
                step.message = message
                step.error = error

                if status == ProgressStatus.RUNNING:
                    step.started_at = timezone.now()
                    progress.current_step = step_name
                elif status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED]:
                    step.completed_at = timezone.now()

                step_found = True
                break

        if not step_found:
            logger.warning(
                'Step not found',
                operation_id=self.operation_id,
                step_name=step_name
            )
            return

        # Recalculate percentage
        progress.percentage = self._calculate_percentage(progress)
        progress.message = message

        # Update ETA
        progress.estimated_completion = self._estimate_completion(progress)

        # Save updated progress
        self._save_progress(progress)

        logger.debug(
            'Updated step',
            operation_id=self.operation_id,
            step_name=step_name,
            status=status.value,
            percentage=progress.percentage
        )

    def complete(self, success: bool, message: str = '', error: Optional[str] = None):
        """
        Mark operation as completed.

        Args:
            success: Whether operation succeeded
            message: Completion message
            error: Error message if failed
        """
        progress = self._load_progress()
        if not progress:
            logger.warning(
                'Progress not found for completion',
                operation_id=self.operation_id
            )
            return

        progress.status = ProgressStatus.COMPLETED if success else ProgressStatus.FAILED
        progress.percentage = 100.0 if success else progress.percentage
        progress.completed_at = timezone.now()
        progress.message = message
        progress.error = error

        self._save_progress(progress)

        logger.info(
            'Completed operation',
            operation_id=self.operation_id,
            success=success,
            duration_seconds=(
                (progress.completed_at - progress.started_at).total_seconds()
            )
        )

    def get_progress(self) -> Optional[Dict[str, Any]]:
        """
        Get current progress information.

        Returns:
            Progress dictionary or None if not found
        """
        progress = self._load_progress()
        return progress.to_dict() if progress else None

    def _calculate_percentage(self, progress: ProgressInfo) -> float:
        """
        Calculate overall percentage based on weighted steps.

        Args:
            progress: ProgressInfo object

        Returns:
            Percentage (0-100)
        """
        if not progress.steps:
            return 0.0

        total_weight = sum(step.weight for step in progress.steps)
        if total_weight == 0:
            return 0.0

        completed_weight = sum(
            step.weight
            for step in progress.steps
            if step.status == ProgressStatus.COMPLETED
        )

        # Add partial credit for running step (50% of its weight)
        for step in progress.steps:
            if step.status == ProgressStatus.RUNNING:
                completed_weight += step.weight * 0.5
                break

        return (completed_weight / total_weight) * 100.0

    def _estimate_completion(self, progress: ProgressInfo) -> Optional[datetime]:
        """
        Estimate completion time based on current progress.

        Args:
            progress: ProgressInfo object

        Returns:
            Estimated completion datetime or None
        """
        if progress.percentage <= 0:
            return None

        elapsed = (timezone.now() - progress.started_at).total_seconds()
        if elapsed == 0:
            return None

        # Calculate rate of progress
        rate = progress.percentage / elapsed  # percentage per second

        if rate <= 0:
            return None

        # Calculate remaining time
        remaining_percentage = 100.0 - progress.percentage
        remaining_seconds = remaining_percentage / rate

        return timezone.now() + timedelta(seconds=remaining_seconds)

    def _save_progress(self, progress: ProgressInfo):
        """Save progress to cache."""
        try:
            cache.set(self.cache_key, progress.to_dict(), self.CACHE_TTL)
        except Exception as e:
            logger.error(
                'Failed to save progress to cache',
                exc_info=e,
                operation_id=self.operation_id
            )

    def _load_progress(self) -> Optional[ProgressInfo]:
        """Load progress from cache."""
        try:
            data = cache.get(self.cache_key)
            if not data:
                return None

            # Reconstruct ProgressInfo from dictionary
            steps = [
                ProgressStep(
                    name=s['name'],
                    weight=s['weight'],
                    started_at=(
                        datetime.fromisoformat(s['started_at'])
                        if s['started_at'] else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(s['completed_at'])
                        if s['completed_at'] else None
                    ),
                    status=ProgressStatus(s['status']),
                    message=s['message'],
                    error=s['error']
                )
                for s in data['steps']
            ]

            return ProgressInfo(
                operation_id=data['operation_id'],
                operation_type=data['operation_type'],
                addon_name=data['addon_name'],
                status=ProgressStatus(data['status']),
                current_step=data['current_step'],
                steps=steps,
                percentage=data['percentage'],
                started_at=datetime.fromisoformat(data['started_at']),
                estimated_completion=(
                    datetime.fromisoformat(data['estimated_completion'])
                    if data['estimated_completion'] else None
                ),
                completed_at=(
                    datetime.fromisoformat(data['completed_at'])
                    if data['completed_at'] else None
                ),
                message=data['message'],
                error=data['error']
            )
        except Exception as e:
            logger.error(
                'Failed to load progress from cache',
                exc_info=e,
                operation_id=self.operation_id
            )
            return None


# ============================================================================
# Predefined Step Configurations
# ============================================================================

class ProgressSteps:
    """Predefined step configurations for common operations."""

    INSTALL_STEPS = [
        {'name': 'validate_config', 'weight': 0.5},
        {'name': 'check_dependencies', 'weight': 1.0},
        {'name': 'download_addon', 'weight': 3.0},
        {'name': 'extract_files', 'weight': 1.0},
        {'name': 'install_dependencies', 'weight': 4.0},
        {'name': 'configure_addon', 'weight': 1.0},
        {'name': 'start_service', 'weight': 0.5},
        {'name': 'verify_installation', 'weight': 1.0},
    ]

    UNINSTALL_STEPS = [
        {'name': 'check_dependents', 'weight': 0.5},
        {'name': 'stop_service', 'weight': 0.5},
        {'name': 'backup_data', 'weight': 2.0},
        {'name': 'remove_files', 'weight': 1.0},
        {'name': 'cleanup_config', 'weight': 0.5},
        {'name': 'verify_removal', 'weight': 0.5},
    ]

    CONFIGURE_STEPS = [
        {'name': 'validate_config', 'weight': 0.5},
        {'name': 'backup_current_config', 'weight': 1.0},
        {'name': 'apply_configuration', 'weight': 2.0},
        {'name': 'restart_service', 'weight': 1.0},
        {'name': 'verify_configuration', 'weight': 1.0},
    ]


# ============================================================================
# Context Manager for Progress Tracking
# ============================================================================

class ProgressContext:
    """Context manager for automatic progress tracking."""

    def __init__(
        self,
        operation_id: str,
        operation_type: str,
        addon_name: str,
        steps: List[Dict[str, Any]]
    ):
        """
        Initialize progress context.

        Args:
            operation_id: Unique operation ID
            operation_type: Type of operation
            addon_name: Addon name
            steps: List of step definitions
        """
        self.tracker = ProgressTracker(operation_id, operation_type, addon_name)
        self.steps = steps

    def __enter__(self):
        """Start tracking."""
        self.tracker.start(self.steps)
        return self.tracker

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete tracking."""
        success = exc_type is None
        error = str(exc_val) if exc_val else None
        message = 'Operation completed successfully' if success else 'Operation failed'

        self.tracker.complete(success, message, error)
        return False  # Don't suppress exceptions


# ============================================================================
# Helper Functions
# ============================================================================

def get_progress(operation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get progress for an operation.

    Args:
        operation_id: Operation ID

    Returns:
        Progress dictionary or None
    """
    tracker = ProgressTracker(operation_id, '', '')
    return tracker.get_progress()


def clear_progress(operation_id: str):
    """
    Clear progress for an operation.

    Args:
        operation_id: Operation ID
    """
    cache_key = f'{ProgressTracker.CACHE_PREFIX}:{operation_id}'
    cache.delete(cache_key)

    logger.debug(
        'Cleared progress',
        operation_id=operation_id
    )
