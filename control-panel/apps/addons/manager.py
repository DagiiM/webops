"""
Addon Manager orchestrates addon discovery, registration, and hook execution.

Design goals:
- Typed HookContext and HookResult for clarity and maintainability
- Minimal dependencies: use standard library (concurrent.futures, logging, time)
- Safe execution with timeouts, retries, and optional enforcement
- Deterministic ordering via per-hook priority
- Basic metrics updates on the Addon model

Notes:
- The manager uses the singleton event registry (event_registry) populated at app startup
  via AddonsConfig.ready(). This avoids duplicate registries and ensures consistent state.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from django.db import transaction
from django.utils import timezone

from .models import Addon
from .registry import HookRegistration, event_registry

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """
    Context passed to addon hook handlers.

    Keep this minimal and focused. Handlers should read only what they need.
    """
    event: str
    deployment_name: Optional[str] = None
    deployment_id: Optional[int] = None
    project_type: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    user_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HookResult:
    addon_name: str
    hook_name: str
    success: bool
    error: Optional[str]
    duration_ms: int
    attempts: int
    skipped: bool = False


class AddonHookEnforcementError(Exception):
    """Raised when a required hook fails and enforcement is enabled."""


class AddonManager:
    def __init__(self) -> None:
        # Use the shared registry populated by app startup discovery
        self.registry = event_registry

    def trigger(self, event: str, context: HookContext, fail_fast: bool = False) -> List[HookResult]:
        """
        Execute hooks for a given event with safety mechanisms.

        - Respects per-hook conditions and priorities
        - Applies timeout and retries
        - Updates Addon metrics in the database
        - If fail_fast and a required hook fails, raises AddonHookEnforcementError
        """
        registrations: List[HookRegistration] = self.registry.get_hooks(event)
        # Sort by priority (lower number = higher priority)
        registrations.sort(key=lambda r: r.priority)

        results: List[HookResult] = []
        for reg in registrations:
            # Conditions: all keys must match context.metadata or top-level fields
            if not self._conditions_match(reg.conditions, context):
                results.append(HookResult(
                    addon_name=reg.addon_name,
                    hook_name=reg.hook_name,
                    success=True,
                    error=None,
                    duration_ms=0,
                    attempts=0,
                    skipped=True,
                ))
                continue

            attempts = 0
            start_ns = time.perf_counter_ns()
            error_str: Optional[str] = None
            success = False
            duration_ms = 0
            try:
                while attempts <= reg.retries:
                    attempts += 1
                    try:
                        # Execute with timeout using a thread
                        with ThreadPoolExecutor(max_workers=1) as ex:
                            future = ex.submit(reg.callback, self._context_to_dict(context))
                            future.result(timeout=(reg.timeout_ms / 1000.0) if reg.timeout_ms else None)
                        success = True
                        break
                    except TimeoutError:
                        error_str = f"Timeout after {reg.timeout_ms}ms"
                        if attempts <= reg.retries:
                            self._backoff_sleep(attempts, reg)
                        continue
                    except Exception as e:
                        error_str = str(e)
                        if attempts <= reg.retries:
                            self._backoff_sleep(attempts, reg)
                        continue
            finally:
                end_ns = time.perf_counter_ns()
                duration_ms = int((end_ns - start_ns) / 1_000_000)

            # Update metrics for the addon
            try:
                self._update_addon_metrics(reg.addon_name, success, duration_ms, error_str)
            except Exception as e:
                logger.warning(f"Failed to update metrics for addon '{reg.addon_name}': {e}")

            result = HookResult(
                addon_name=reg.addon_name,
                hook_name=reg.hook_name,
                success=success,
                error=error_str,
                duration_ms=duration_ms,
                attempts=attempts,
                skipped=False,
            )
            results.append(result)

            if fail_fast and not success and reg.enforcement == 'required':
                raise AddonHookEnforcementError(
                    f"Required hook '{reg.hook_name}' in addon '{reg.addon_name}' failed: {error_str}"
                )

        return results

    @staticmethod
    def _context_to_dict(context: HookContext) -> Dict[str, Any]:
        # Handlers expect a dict to avoid tight coupling with dataclass
        return {
            'event': context.event,
            'deployment_name': context.deployment_name,
            'deployment_id': context.deployment_id,
            'project_type': context.project_type,
            'env': context.env,
            'user_id': context.user_id,
            'metadata': context.metadata,
            'settings': context.settings,
        }

    @staticmethod
    def _conditions_match(conditions: Dict[str, Any], context: HookContext) -> bool:
        if not conditions:
            return True
        # Check both top-level attributes and metadata
        for key, expected in conditions.items():
            actual = getattr(context, key, None)
            if actual is None:
                actual = context.metadata.get(key)
            if actual != expected:
                return False
        return True

    @staticmethod
    def _backoff_sleep(attempt: int, reg: HookRegistration) -> None:
        # Basic exponential backoff with optional backoff disabled
        delay_ms = reg.retry_initial_delay_ms * (2 ** (attempt - 1)) if reg.retry_backoff else reg.retry_initial_delay_ms
        time.sleep(delay_ms / 1000.0)

    @staticmethod
    def _update_addon_metrics(addon_name: str, success: bool, duration_ms: int, error: Optional[str]) -> None:
        with transaction.atomic():
            addon = Addon.objects.select_for_update().get(name=addon_name)
            addon.last_run_at = timezone.now()
            addon.last_duration_ms = duration_ms
            if success:
                addon.success_count += 1
                addon.last_success_at = addon.last_run_at
                addon.last_error = ''
            else:
                addon.failure_count += 1
                addon.last_error = (error or '').strip()[:1000]
            addon.save(update_fields=[
                'last_run_at', 'last_duration_ms', 'success_count', 'failure_count', 'last_success_at', 'last_error'
            ])


# Singleton instance used across the app
addon_manager = AddonManager()