from typing import Callable, Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class HookRegistration:
    def __init__(
        self,
        hook_name: str,
        callback: Callable[[Dict[str, Any]], None],
        addon_name: str,
        priority: int = 100,
        timeout_ms: Optional[int] = 5000,
        retries: int = 0,
        retry_initial_delay_ms: int = 250,
        retry_backoff: bool = True,
        enforcement: str = 'optional',  # 'required' | 'optional'
        conditions: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.hook_name = hook_name
        self.callback = callback
        self.addon_name = addon_name
        self.priority = priority
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.retry_initial_delay_ms = retry_initial_delay_ms
        self.retry_backoff = retry_backoff
        self.enforcement = enforcement
        self.conditions = conditions or {}

class EventRegistry:
    def __init__(self) -> None:
        self.hooks: Dict[str, List[HookRegistration]] = {
            'pre_deployment': [],
            'post_deployment': [],
            'service_health_check': [],
            'pre_backup': [],
            'post_backup': [],
        }

    def register_hook(self, event: str, callback: Callable[[Dict[str, Any]], None], *, addon_name: str = 'unknown', priority: int = 100, timeout_ms: Optional[int] = 5000, retries: int = 0, retry_initial_delay_ms: int = 250, retry_backoff: bool = True, enforcement: str = 'optional', conditions: Optional[Dict[str, Any]] = None) -> None:
        if event not in self.hooks:
            self.hooks[event] = []
        self.hooks[event].append(HookRegistration(
            hook_name=event,
            callback=callback,
            addon_name=addon_name,
            priority=priority,
            timeout_ms=timeout_ms,
            retries=retries,
            retry_initial_delay_ms=retry_initial_delay_ms,
            retry_backoff=retry_backoff,
            enforcement=enforcement,
            conditions=conditions,
        ))

    def get_hooks(self, event: str) -> List[HookRegistration]:
        return list(self.hooks.get(event, []))

    def trigger(self, event: str, context: Dict[str, Any]) -> None:
        # Backward-compatible method; execute callbacks directly
        registrations = self.get_hooks(event)
        # Sort by priority
        registrations.sort(key=lambda r: r.priority)
        for reg in registrations:
            try:
                reg.callback(context)
            except Exception as e:
                logger.warning(f"Addon hook '{event}' failed in {reg.callback}: {e}")

event_registry = EventRegistry()

# Backward compatibility
hook_registry = event_registry
AddonHookRegistry = EventRegistry