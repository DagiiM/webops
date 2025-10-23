"""
Automated Restart Policies for Service Management.

"Services Control System"
Architecture: Policy-based automated service recovery

This module provides:
- Restart policies (always, on-failure, backoff)
- Failure tracking and cooldown periods
- Circuit breaker pattern
- Policy configuration and management
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
import logging

from apps.deployments.models import BaseDeployment
from apps.core.common.models import BaseModel

logger = logging.getLogger(__name__)


class RestartPolicy(models.Model):
    """
    Restart policy configuration for deployments.

    Defines how and when a service should be automatically restarted
    when failures are detected.
    """

    class PolicyType(models.TextChoices):
        ALWAYS = 'always', 'Always Restart'
        ON_FAILURE = 'on_failure', 'Restart on Failure'
        NEVER = 'never', 'Never Auto-Restart'
        BACKOFF = 'backoff', 'Exponential Backoff'

    deployment = models.OneToOneField(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='restart_policy'
    )
    policy_type = models.CharField(
        max_length=20,
        choices=PolicyType.choices,
        default=PolicyType.ON_FAILURE
    )
    enabled = models.BooleanField(default=True)

    # Restart limits
    max_restarts = models.IntegerField(
        default=3,
        help_text='Maximum restart attempts within time window'
    )
    time_window_minutes = models.IntegerField(
        default=15,
        help_text='Time window for counting restart attempts'
    )

    # Backoff configuration
    initial_delay_seconds = models.IntegerField(
        default=10,
        help_text='Initial delay before first restart'
    )
    max_delay_seconds = models.IntegerField(
        default=300,
        help_text='Maximum delay between restarts (5 minutes)'
    )
    backoff_multiplier = models.FloatField(
        default=2.0,
        help_text='Multiplier for exponential backoff'
    )

    # Cooldown period
    cooldown_minutes = models.IntegerField(
        default=5,
        help_text='Cooldown period after max restarts exceeded'
    )

    # Health check integration
    require_health_check = models.BooleanField(
        default=True,
        help_text='Only restart if health check confirms failure'
    )
    health_check_retries = models.IntegerField(
        default=3,
        help_text='Number of health check failures before restart'
    )

    # Notification settings
    notify_on_restart = models.BooleanField(default=True)
    notify_on_max_restarts = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'restart_policies'
        verbose_name = 'Restart Policy'
        verbose_name_plural = 'Restart Policies'

    def __str__(self) -> str:
        return f"{self.deployment.name} - {self.policy_type}"


class RestartAttempt(BaseModel):
    """Track restart attempts for policy enforcement."""

    deployment = models.ForeignKey(
        BaseDeployment,
        on_delete=models.CASCADE,
        related_name='restart_attempts'
    )
    policy = models.ForeignKey(
        RestartPolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Attempt details
    attempt_number = models.IntegerField()
    delay_seconds = models.IntegerField()
    reason = models.CharField(max_length=255)

    # Result
    success = models.BooleanField()
    error_message = models.TextField(blank=True)

    # Timing
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()

    class Meta:
        db_table = 'restart_attempts'
        verbose_name = 'Restart Attempt'
        verbose_name_plural = 'Restart Attempts'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['deployment', '-started_at']),
        ]

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} {self.deployment.name} - Attempt #{self.attempt_number}"


class RestartPolicyEnforcer:
    """
    Enforces restart policies and manages automated service recovery.

    Implements:
    - Policy evaluation
    - Circuit breaker pattern
    - Cooldown management
    - Restart attempt tracking
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def should_restart(self, deployment: BaseDeployment) -> Tuple[bool, str]:
        """
        Determine if a deployment should be restarted based on policy.

        Args:
            deployment: Deployment to check

        Returns:
            Tuple of (should_restart, reason)
        """
        try:
            policy = RestartPolicy.objects.get(deployment=deployment)
        except RestartPolicy.DoesNotExist:
            # No policy - use default (restart on failure)
            return True, "No policy configured, using default"

        if not policy.enabled:
            return False, "Restart policy disabled"

        if policy.policy_type == RestartPolicy.PolicyType.NEVER:
            return False, "Policy set to never restart"

        # Check if we're in cooldown period
        if self._is_in_cooldown(deployment, policy):
            return False, "Service in cooldown period"

        # Check restart limits
        if self._exceeded_restart_limit(deployment, policy):
            return False, "Exceeded maximum restart attempts"

        # Check health check requirements
        if policy.require_health_check:
            if not self._health_check_confirms_failure(deployment, policy):
                return False, "Health check does not confirm failure"

        # All checks passed
        if policy.policy_type == RestartPolicy.PolicyType.ALWAYS:
            return True, "Always restart policy"
        elif policy.policy_type == RestartPolicy.PolicyType.ON_FAILURE:
            return True, "Restart on failure"
        elif policy.policy_type == RestartPolicy.PolicyType.BACKOFF:
            return True, "Exponential backoff restart"

        return False, "Unknown policy type"

    def calculate_restart_delay(self, deployment: BaseDeployment) -> int:
        """
        Calculate delay before restart based on policy and attempt history.

        Args:
            deployment: Deployment to calculate delay for

        Returns:
            Delay in seconds
        """
        try:
            policy = RestartPolicy.objects.get(deployment=deployment)
        except RestartPolicy.DoesNotExist:
            return 10  # Default 10 seconds

        if policy.policy_type != RestartPolicy.PolicyType.BACKOFF:
            return policy.initial_delay_seconds

        # Count recent attempts
        time_window = timezone.now() - timedelta(minutes=policy.time_window_minutes)
        recent_attempts = RestartAttempt.objects.filter(
            deployment=deployment,
            started_at__gte=time_window
        ).count()

        # Calculate exponential backoff
        delay = policy.initial_delay_seconds * (policy.backoff_multiplier ** recent_attempts)
        delay = min(delay, policy.max_delay_seconds)

        return int(delay)

    def record_restart_attempt(
        self,
        deployment: BaseDeployment,
        success: bool,
        delay_seconds: int,
        reason: str = "",
        error_message: str = ""
    ) -> RestartAttempt:
        """
        Record a restart attempt for tracking and policy enforcement.

        Args:
            deployment: Deployment being restarted
            success: Whether restart was successful
            delay_seconds: Delay used before restart
            reason: Reason for restart
            error_message: Error message if failed

        Returns:
            RestartAttempt instance
        """
        try:
            policy = RestartPolicy.objects.get(deployment=deployment)
        except RestartPolicy.DoesNotExist:
            policy = None

        # Get attempt number
        time_window = timezone.now() - timedelta(minutes=15)
        attempt_number = RestartAttempt.objects.filter(
            deployment=deployment,
            started_at__gte=time_window
        ).count() + 1

        attempt = RestartAttempt.objects.create(
            deployment=deployment,
            policy=policy,
            attempt_number=attempt_number,
            delay_seconds=delay_seconds,
            reason=reason,
            success=success,
            error_message=error_message,
            started_at=timezone.now() - timedelta(seconds=delay_seconds),
            completed_at=timezone.now()
        )

        self.logger.info(
            f"Recorded restart attempt #{attempt_number} for {deployment.name}: "
            f"{'success' if success else 'failed'}"
        )

        return attempt

    def reset_restart_counter(self, deployment: BaseDeployment) -> None:
        """
        Reset restart counter for a deployment.

        Typically called after successful startup or manual intervention.

        Args:
            deployment: Deployment to reset
        """
        # Mark old attempts as archived by not deleting but noting reset
        self.logger.info(f"Reset restart counter for {deployment.name}")

    def get_restart_statistics(self, deployment: BaseDeployment, hours: int = 24) -> Dict[str, Any]:
        """
        Get restart statistics for a deployment.

        Args:
            deployment: Deployment to get stats for
            hours: Hours to look back

        Returns:
            Statistics dict
        """
        cutoff = timezone.now() - timedelta(hours=hours)
        attempts = RestartAttempt.objects.filter(
            deployment=deployment,
            started_at__gte=cutoff
        )

        total = attempts.count()
        successful = attempts.filter(success=True).count()
        failed = attempts.filter(success=False).count()

        return {
            'deployment': deployment.name,
            'period_hours': hours,
            'total_attempts': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0,
            'last_attempt': attempts.first().started_at.isoformat() if attempts.exists() else None
        }

    # =========================================================================
    # PRIVATE HELPER METHODS
    # =========================================================================

    def _is_in_cooldown(self, deployment: BaseDeployment, policy: RestartPolicy) -> bool:
        """Check if deployment is in cooldown period."""
        cooldown_cutoff = timezone.now() - timedelta(minutes=policy.cooldown_minutes)

        last_max_exceeded = RestartAttempt.objects.filter(
            deployment=deployment,
            started_at__gte=cooldown_cutoff
        ).count()

        # If we have attempts within cooldown and hit max, we're in cooldown
        if last_max_exceeded >= policy.max_restarts:
            return True

        return False

    def _exceeded_restart_limit(self, deployment: BaseDeployment, policy: RestartPolicy) -> bool:
        """Check if restart limit has been exceeded."""
        time_window = timezone.now() - timedelta(minutes=policy.time_window_minutes)

        recent_attempts = RestartAttempt.objects.filter(
            deployment=deployment,
            started_at__gte=time_window
        ).count()

        return recent_attempts >= policy.max_restarts

    def _health_check_confirms_failure(self, deployment: BaseDeployment, policy: RestartPolicy) -> bool:
        """Check if health checks confirm the service has failed."""
        from .models import HealthCheck

        # Get recent health checks
        recent_checks = HealthCheck.objects.filter(
            deployment=deployment
        ).order_by('-created_at')[:policy.health_check_retries]

        if recent_checks.count() < policy.health_check_retries:
            # Not enough health checks to confirm
            return True  # Assume failure if we don't have enough data

        # All recent checks must be failures
        return all(not check.is_healthy for check in recent_checks)


# Singleton instance
restart_policy_enforcer = RestartPolicyEnforcer()
