"""
Lifecycle Management Module

Manages the AI agent's lifecycle states, transitions, and operational phases.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import threading
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor


class LifecycleState(Enum):
    """Lifecycle states of the AI agent."""
    
    INITIALIZING = "initializing"
    STARTING = "starting"
    ACTIVE = "active"
    BUSY = "busy"
    IDLE = "idle"
    SUSPENDING = "suspending"
    SUSPENDED = "suspended"
    RESUMING = "resuming"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UPDATING = "upgrading"


class TransitionType(Enum):
    """Types of lifecycle transitions."""
    
    SPONTANEOUS = "spontaneous"  # State change initiated internally
    TRIGGERED = "triggered"  # State change triggered by external event
    SCHEDULED = "scheduled"  # State change scheduled by timer/event
    RECOVERY = "recovery"  # State change for recovery from error
    MANUAL = "manual"  # State change manually requested


class TransitionReason(Enum):
    """Reasons for lifecycle transitions."""
    
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    RESOURCE_CONSTRAINT = "resource_constraint"
    ERROR_RECOVERY = "error_recovery"
    SCHEDULED_MAINTENANCE = "scheduled_maintenance"
    USER_REQUEST = "user_request"
    WORKLOAD_CHANGE = "workload_change"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    VERSION_UPDATE = "version_update"
    IDLE_DETECTION = "idle_detection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    HEALTH_CHECK = "health_check"


@dataclass
class LifecycleTransition:
    """Represents a lifecycle state transition."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_state: Optional[LifecycleState] = None
    to_state: LifecycleState = LifecycleState.ACTIVE
    transition_type: TransitionType = TransitionType.SPONTANEOUS
    reason: TransitionReason = TransitionReason.SYSTEM_STARTUP
    triggered_by: str = "system"
    initiated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transition to dictionary."""
        data = asdict(self)
        data['from_state'] = from_state.value if self.from_state else None
        data['to_state'] = self.to_state.value
        data['transition_type'] = self.transition_type.value
        data['reason'] = self.reason.value
        data['initiated_at'] = self.initiated_at.isoformat()
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LifecycleTransition':
        """Create transition from dictionary."""
        if 'from_state' in data and data['from_state']:
            data['from_state'] = LifecycleState(data['from_state'])
        if 'to_state' in data and isinstance(data['to_state'], str):
            data['to_state'] = LifecycleState(data['to_state'])
        if 'transition_type' in data and isinstance(data['transition_type'], str):
            data['transition_type'] = TransitionType(data['transition_type'])
        if 'reason' in data and isinstance(data['reason'], str):
            data['reason'] = TransitionReason(data['reason'])
        if 'initiated_at' in data and isinstance(data['initiated_at'], str):
            data['initiated_at'] = datetime.fromisoformat(data['initiated_at'])
        if 'completed_at' in data and isinstance(data['completed_at'], str):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        return cls(**data)


@dataclass
class LifecycleEvent:
    """An event that affects the agent's lifecycle."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    source: str = "system"
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10, where 10 is highest
    category: str = "operational"  # operational, maintenance, error, security, etc.
    data: Dict[str, Any] = field(default_factory=dict)
    handled: bool = False
    handled_at: Optional[datetime] = None
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['handled_at'] = self.handled_at.isoformat() if self.handled_at else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LifecycleEvent':
        """Create event from dictionary."""
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'handled_at' in data and isinstance(data['handled_at'], str):
            data['handled_at'] = datetime.fromisoformat(data['handled_at'])
        return cls(**data)


@dataclass
class LifecycleConfiguration:
    """Configuration for lifecycle management."""
    
    idle_timeout_minutes: int = 30  # Transition to idle after this period
    busy_timeout_minutes: int = 120  # Max time in busy state
    maintenance_schedule: Dict[str, datetime] = field(default_factory=dict)  # day -> time
    auto_maintenance: bool = True
    health_check_interval_seconds: int = 30
    state_transition_timeout_seconds: int = 60
    max_transition_history: int = 100
    max_event_history: int = 1000
    suspend_on_resource_exhaustion: bool = True
    resume_after_maintenance: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class LifecycleManager:
    """Manages the AI agent's lifecycle and state transitions."""
    
    def __init__(self, config):
        """Initialize the lifecycle manager."""
        self.config = config
        self.logger = logging.getLogger("lifecycle_manager")
        
        # State management
        self._current_state: LifecycleState = LifecycleState.INITIALIZING
        self._previous_state: Optional[LifecycleState] = None
        self._state_lock = threading.RLock()
        
        # Event handling
        self._event_queue = asyncio.Queue()
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_history: deque = deque(maxlen=1000)
        
        # Transition management
        self._transition_history: deque = deque(maxlen=100)
        self._active_transition: Optional[LifecycleTransition] = None
        self._transition_handlers: Dict[LifecycleState, List[Callable]] = defaultdict(list)
        
        # Monitoring
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._health_check_interval = 30  # seconds
        self._last_heartbeat = datetime.now()
        
        # Statistics
        self._total_transitions = 0
        self._total_events_processed = 0
        self._state_durations: Dict[LifecycleState, List[float]] = defaultdict(list)
        self._state_entry_times: Dict[LifecycleState, datetime] = {}
        
        # Configuration
        self._lifecycle_config = LifecycleConfiguration()
        
        # Background tasks
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def initialize(self) -> None:
        """Initialize the lifecycle manager."""
        try:
            # Set initial state
            await self._transition_to_state(
                LifecycleState.INITIALIZING,
                TransitionReason.SYSTEM_STARTUP
            )
            
            # Set up event handlers
            await self._setup_event_handlers()
            
            # Start monitoring
            await self._start_monitoring()
            
            # Load configuration
            await self._load_configuration()
            
            # Start event processing
            asyncio.create_task(self._process_events())
            
            # Transition to active state
            await self._transition_to_state(
                LifecycleState.ACTIVE,
                TransitionReason.SYSTEM_STARTUP
            )
            
            self.logger.info("Lifecycle manager initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing lifecycle manager: {e}")
            await self._handle_initialization_error(e)
            raise
    
    async def shutdown(self, reason: TransitionReason = TransitionReason.SYSTEM_SHUTDOWN) -> None:
        """Shutdown the lifecycle manager."""
        try:
            self.logger.info("Starting lifecycle manager shutdown")
            
            # Transition to shutting down state
            await self._transition_to_state(
                LifecycleState.SHUTTING_DOWN,
                reason
            )
            
            # Stop monitoring
            self._monitoring_active = False
            
            # Cancel background tasks
            for task_name, task in self._background_tasks.items():
                if not task.done():
                    task.cancel()
                    self.logger.debug(f"Cancelled background task: {task_name}")
            
            # Process remaining events
            await self._drain_event_queue()
            
            # Save state
            await self._save_state()
            
            # Transition to shutdown state
            await self._transition_to_state(
                LifecycleState.SHUTDOWN,
                reason
            )
            
            # Shutdown executor
            self._executor.shutdown(wait=True)
            
            self.logger.info("Lifecycle manager shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during lifecycle manager shutdown: {e}")
    
    async def transition_to_state(
        self,
        target_state: LifecycleState,
        reason: TransitionReason,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Request a transition to a specific state."""
        try:
            with self._state_lock:
                # Validate transition
                if not await self._validate_transition(self._current_state, target_state):
                    self.logger.warning(
                        f"Invalid transition from {self._current_state.value} to {target_state.value}"
                    )
                    return False
                
                # Create transition
                transition = LifecycleTransition(
                    from_state=self._current_state,
                    to_state=target_state,
                    reason=reason,
                    triggered_by="user",
                    metadata=metadata or {}
                )
                
                return await self._execute_transition(transition)
                
        except Exception as e:
            self.logger.error(f"Error requesting state transition: {e}")
            return False
    
    async def get_current_state(self) -> Dict[str, Any]:
        """Get current lifecycle state information."""
        try:
            with self._state_lock:
                state_info = {
                    'current_state': self._current_state.value,
                    'previous_state': self._previous_state.value if self._previous_state else None,
                    'state_entered_at': self._state_entry_times.get(
                        self._current_state, datetime.now()
                    ).isoformat(),
                    'time_in_state_seconds': (
                        datetime.now() - self._state_entry_times[self._current_state]
                    ).total_seconds() if self._current_state in self._state_entry_times else 0,
                    'active_transition': self._active_transition.to_dict() if self._active_transition else None,
                    'monitoring_active': self._monitoring_active,
                    'last_heartbeat': self._last_heartbeat.isoformat(),
                    'total_transitions': self._total_transitions,
                    'total_events_processed': self._total_events_processed
                }
                
                # Add state duration statistics
                if self._current_state in self._state_durations:
                    durations = self._state_durations[self._current_state]
                    state_info['state_durations'] = {
                        'count': len(durations),
                        'average_seconds': sum(durations) / len(durations) if durations else 0,
                        'min_seconds': min(durations) if durations else 0,
                        'max_seconds': max(durations) if durations else 0
                    }
                
                return state_info
                
        except Exception as e:
            self.logger.error(f"Error getting current state: {e}")
            return {'error': str(e)}
    
    async def get_transition_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transition history."""
        try:
            history = list(self._transition_history)[-limit:]
            return [transition.to_dict() for transition in reversed(history)]
            
        except Exception as e:
            self.logger.error(f"Error getting transition history: {e}")
            return []
    
    async def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent event history."""
        try:
            events = list(self._event_history)[-limit:]
            return [event.to_dict() for event in reversed(events)]
            
        except Exception as e:
            self.logger.error(f"Error getting event history: {e}")
            return []
    
    async def register_event_handler(
        self,
        event_type: str,
        handler: Callable,
        priority: int = 5
    ) -> bool:
        """Register an event handler."""
        try:
            # Insert handler in priority order
            handlers = self._event_handlers[event_type]
            handlers.append((priority, handler))
            handlers.sort(key=lambda x: x[0], reverse=True)  # Higher priority first
            
            self.logger.debug(f"Registered event handler for {event_type} with priority {priority}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering event handler: {e}")
            return False
    
    async def register_state_handler(
        self,
        state: LifecycleState,
        handler: Callable
    ) -> bool:
        """Register a state transition handler."""
        try:
            self._transition_handlers[state].append(handler)
            self.logger.debug(f"Registered state handler for {state.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering state handler: {e}")
            return False
    
    async def emit_event(
        self,
        event_type: str,
        source: str = "system",
        description: str = "",
        priority: int = 5,
        category: str = "operational",
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Emit a lifecycle event."""
        try:
            event = LifecycleEvent(
                event_type=event_type,
                source=source,
                description=description,
                priority=priority,
                category=category,
                data=data or {}
            )
            
            await self._event_queue.put(event)
            self.logger.debug(f"Emitted event: {event_type}")
            
            return event.id
            
        except Exception as e:
            self.logger.error(f"Error emitting event: {e}")
            return ""
    
    async def is_state_available(self, state: LifecycleState) -> bool:
        """Check if a state is available for transition."""
        try:
            # Define allowed transitions
            allowed_transitions = {
                LifecycleState.INITIALIZING: [LifecycleState.STARTING, LifecycleState.ERROR],
                LifecycleState.STARTING: [LifecycleState.ACTIVE, LifecycleState.ERROR],
                LifecycleState.ACTIVE: [LifecycleState.BUSY, LifecycleState.IDLE, LifecycleState.MAINTENANCE, LifecycleState.SUSPENDING, LifecycleState.ERROR],
                LifecycleState.BUSY: [LifecycleState.ACTIVE, LifecycleState.SUSPENDING, LifecycleState.ERROR],
                LifecycleState.IDLE: [LifecycleState.ACTIVE, LifecycleState.SUSPENDING, LifecycleState.SHUTTING_DOWN, LifecycleState.ERROR],
                LifecycleState.SUSPENDING: [LifecycleState.SUSPENDED, LifecycleState.ACTIVE, LifecycleState.ERROR],
                LifecycleState.SUSPENDED: [LifecycleState.RESUMING, LifecycleState.SHUTTING_DOWN],
                LifecycleState.RESUMING: [LifecycleState.ACTIVE, LifecycleState.SUSPENDED, LifecycleState.ERROR],
                LifecycleState.MAINTENANCE: [LifecycleState.ACTIVE, LifecycleState.ERROR],
                LifecycleState.SHUTTING_DOWN: [LifecycleState.SHUTDOWN, LifecycleState.ACTIVE],
                LifecycleState.SHUTDOWN: [LifecycleState.STARTING],
                LifecycleState.ERROR: [LifecycleState.ACTIVE, LifecycleState.SUSPENDED, LifecycleState.SHUTTING_DOWN],
                LifecycleState.UPDATING: [LifecycleState.ACTIVE, LifecycleState.ERROR]
            }
            
            return state in allowed_transitions.get(self._current_state, [])
            
        except Exception as e:
            self.logger.error(f"Error checking state availability: {e}")
            return False
    
    async def force_transition(
        self,
        target_state: LifecycleState,
        reason: TransitionReason,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Force a transition to a specific state (bypasses validation)."""
        try:
            with self._state_lock:
                transition = LifecycleTransition(
                    from_state=self._current_state,
                    to_state=target_state,
                    reason=reason,
                    triggered_by="system_force",
                    metadata=metadata or {}
                )
                
                self.logger.warning(f"Forcing transition to {target_state.value}")
                return await self._execute_transition(transition)
                
        except Exception as e:
            self.logger.error(f"Error forcing state transition: {e}")
            return False
    
    async def get_lifecycle_statistics(self) -> Dict[str, Any]:
        """Get lifecycle management statistics."""
        try:
            stats = {
                'timestamp': datetime.now().isoformat(),
                'states': {
                    'current_state': self._current_state.value,
                    'previous_state': self._previous_state.value if self._previous_state else None,
                    'total_state_changes': self._total_transitions
                },
                'events': {
                    'total_processed': self._total_events_processed,
                    'queue_size': self._event_queue.qsize(),
                    'history_size': len(self._event_history)
                },
                'transitions': {
                    'total_transitions': self._total_transitions,
                    'history_size': len(self._transition_history),
                    'active_transition': self._active_transition is not None
                },
                'monitoring': {
                    'monitoring_active': self._monitoring_active,
                    'last_heartbeat': self._last_heartbeat.isoformat(),
                    'background_tasks': len(self._background_tasks)
                },
                'state_durations': {},
                'transition_types': {},
                'transition_reasons': {}
            }
            
            # Calculate state duration statistics
            for state, durations in self._state_durations.items():
                if durations:
                    stats['state_durations'][state.value] = {
                        'count': len(durations),
                        'average_seconds': sum(durations) / len(durations),
                        'min_seconds': min(durations),
                        'max_seconds': max(durations)
                    }
            
            # Calculate transition statistics
            transition_types = defaultdict(int)
            transition_reasons = defaultdict(int)
            
            for transition in self._transition_history:
                transition_types[transition.transition_type.value] += 1
                transition_reasons[transition.reason.value] += 1
            
            stats['transition_types'] = dict(transition_types)
            stats['transition_reasons'] = dict(transition_reasons)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting lifecycle statistics: {e}")
            return {'error': str(e)}
    
    async def _transition_to_state(
        self,
        target_state: LifecycleState,
        reason: TransitionReason,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Internal method to transition to a state."""
        try:
            with self._state_lock:
                transition = LifecycleTransition(
                    from_state=self._current_state,
                    to_state=target_state,
                    reason=reason,
                    triggered_by="system",
                    metadata=metadata or {}
                )
                
                return await self._execute_transition(transition)
                
        except Exception as e:
            self.logger.error(f"Error transitioning to state: {e}")
            return False
    
    async def _execute_transition(self, transition: LifecycleTransition) -> bool:
        """Execute a lifecycle state transition."""
        try:
            # Check if transition is already in progress
            if self._active_transition:
                self.logger.warning("Transition already in progress")
                return False
            
            # Set active transition
            self._active_transition = transition
            
            # Execute pre-transition handlers
            success = await self._execute_pre_transition_handlers(transition)
            if not success:
                self.logger.error("Pre-transition handlers failed")
                transition.success = False
                transition.error_message = "Pre-transition handlers failed"
                self._active_transition = None
                return False
            
            # Perform the transition
            old_state = self._current_state
            self._previous_state = self._current_state
            self._current_state = transition.to_state
            self._state_entry_times[self._current_state] = datetime.now()
            
            # Update statistics
            self._total_transitions += 1
            
            # Execute post-transition handlers
            await self._execute_post_transition_handlers(transition)
            
            # Complete transition
            transition.completed_at = datetime.now()
            transition.duration_seconds = (
                transition.completed_at - transition.initiated_at
            ).total_seconds()
            transition.success = True
            
            # Add to history
            self._transition_history.append(transition)
            
            # Update state durations
            if self._previous_state in self._state_entry_times:
                duration = (
                    datetime.now() - self._state_entry_times[self._previous_state]
                ).total_seconds()
                self._state_durations[self._previous_state].append(duration)
            
            # Clear active transition
            self._active_transition = None
            
            self.logger.info(
                f"Transitioned from {old_state.value} to {self._current_state.value} "
                f"({transition.reason.value})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing transition: {e}")
            if self._active_transition:
                self._active_transition.success = False
                self._active_transition.error_message = str(e)
                self._active_transition = None
            return False
    
    async def _validate_transition(
        self,
        from_state: LifecycleState,
        to_state: LifecycleState
    ) -> bool:
        """Validate if a transition is allowed."""
        # Allow self-transitions (no change)
        if from_state == to_state:
            return True
        
        return await self.is_state_available(to_state)
    
    async def _execute_pre_transition_handlers(self, transition: LifecycleTransition) -> bool:
        """Execute pre-transition handlers."""
        try:
            # Execute handlers for the target state
            handlers = self._transition_handlers.get(transition.to_state, [])
            
            for handler in handlers:
                try:
                    result = handler(transition)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    self.logger.error(f"Pre-transition handler failed: {e}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing pre-transition handlers: {e}")
            return False
    
    async def _execute_post_transition_handlers(self, transition: LifecycleTransition) -> None:
        """Execute post-transition handlers."""
        try:
            # Execute handlers for the current state
            handlers = self._transition_handlers.get(self._current_state, [])
            
            for handler in handlers:
                try:
                    result = handler(transition)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    self.logger.error(f"Post-transition handler failed: {e}")
            
        except Exception as e:
            self.logger.error(f"Error executing post-transition handlers: {e}")
    
    async def _setup_event_handlers(self) -> None:
        """Set up default event handlers."""
        # High priority events
        await self.register_event_handler("critical_error", self._handle_critical_error, priority=10)
        await self.register_event_handler("resource_exhaustion", self._handle_resource_exhaustion, priority=9)
        await self.register_event_handler("system_shutdown", self._handle_shutdown_request, priority=8)
        
        # Medium priority events
        await self.register_event_handler("maintenance_scheduled", self._handle_maintenance_scheduled, priority=6)
        await self.register_event_handler("workload_change", self._handle_workload_change, priority=5)
        await self.register_event_handler("health_check", self._handle_health_check, priority=5)
        
        # Low priority events
        await self.register_event_handler("idle_detected", self._handle_idle_detected, priority=3)
        await self.register_event_handler("routine_maintenance", self._handle_routine_maintenance, priority=2)
    
    async def _handle_critical_error(self, event: LifecycleEvent) -> bool:
        """Handle critical error events."""
        try:
            self.logger.error(f"Critical error detected: {event.description}")
            
            # Transition to error state if not already there
            if self._current_state != LifecycleState.ERROR:
                await self._transition_to_state(
                    LifecycleState.ERROR,
                    TransitionReason.ERROR_RECOVERY,
                    event.data
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling critical error: {e}")
            return False
    
    async def _handle_resource_exhaustion(self, event: LifecycleEvent) -> bool:
        """Handle resource exhaustion events."""
        try:
            resource_type = event.data.get('resource_type', 'unknown')
            utilization = event.data.get('utilization', 0.0)
            
            self.logger.warning(f"Resource exhaustion detected: {resource_type} at {utilization:.1%}")
            
            # Suspend if configured to do so
            if self._lifecycle_config.suspend_on_resource_exhaustion:
                await self._transition_to_state(
                    LifecycleState.SUSPENDING,
                    TransitionReason.RESOURCE_EXHAUSTION,
                    event.data
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling resource exhaustion: {e}")
            return False
    
    async def _handle_shutdown_request(self, event: LifecycleEvent) -> bool:
        """Handle shutdown request events."""
        try:
            self.logger.info("Shutdown request received")
            await self.shutdown(TransitionReason.USER_REQUEST)
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling shutdown request: {e}")
            return False
    
    async def _handle_maintenance_scheduled(self, event: LifecycleEvent) -> bool:
        """Handle scheduled maintenance events."""
        try:
            maintenance_time = event.data.get('scheduled_time')
            self.logger.info(f"Maintenance scheduled for {maintenance_time}")
            
            # Transition to maintenance state
            await self._transition_to_state(
                LifecycleState.MAINTENANCE,
                TransitionReason.SCHEDULED_MAINTENANCE,
                event.data
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling scheduled maintenance: {e}")
            return False
    
    async def _handle_workload_change(self, event: LifecycleEvent) -> bool:
        """Handle workload change events."""
        try:
            new_workload = event.data.get('workload_level', 'normal')
            self.logger.debug(f"Workload change detected: {new_workload}")
            
            # Adjust state based on workload
            if new_workload == 'high':
                if self._current_state == LifecycleState.IDLE:
                    await self._transition_to_state(
                        LifecycleState.ACTIVE,
                        TransitionReason.WORKLOAD_CHANGE
                    )
            elif new_workload == 'low':
                if self._current_state in [LifecycleState.ACTIVE, LifecycleState.BUSY]:
                    await self._transition_to_state(
                        LifecycleState.IDLE,
                        TransitionReason.WORKLOAD_CHANGE
                    )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling workload change: {e}")
            return False
    
    async def _handle_health_check(self, event: LifecycleEvent) -> bool:
        """Handle health check events."""
        try:
            self._last_heartbeat = datetime.now()
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling health check: {e}")
            return False
    
    async def _handle_idle_detected(self, event: LifecycleEvent) -> bool:
        """Handle idle detection events."""
        try:
            idle_duration = event.data.get('idle_duration_minutes', 0)
            self.logger.debug(f"Idle detected for {idle_duration} minutes")
            
            # Transition to idle state if appropriate
            if self._current_state == LifecycleState.ACTIVE:
                await self._transition_to_state(
                    LifecycleState.IDLE,
                    TransitionReason.IDLE_DETECTION
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling idle detection: {e}")
            return False
    
    async def _handle_routine_maintenance(self, event: LifecycleEvent) -> bool:
        """Handle routine maintenance events."""
        try:
            # Check if auto-maintenance is enabled
            if not self._lifecycle_config.auto_maintenance:
                return True
            
            # Perform routine maintenance tasks
            if self._current_state == LifecycleState.IDLE:
                await self._transition_to_state(
                    LifecycleState.MAINTENANCE,
                    TransitionReason.SCHEDULED_MAINTENANCE
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling routine maintenance: {e}")
            return False
    
    async def _process_events(self) -> None:
        """Process events from the event queue."""
        while True:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                
                start_time = time.time()
                event.handled = await self._handle_event(event)
                event.handled_at = datetime.now()
                event.processing_time_ms = (time.time() - start_time) * 1000
                
                self._total_events_processed += 1
                self._event_history.append(event)
                
                if event.handled:
                    self.logger.debug(f"Event processed: {event.event_type} in {event.processing_time_ms:.2f}ms")
                else:
                    self.logger.warning(f"Event not handled: {event.event_type}")
                
            except asyncio.TimeoutError:
                # No events to process
                continue
            except Exception as e:
                self.logger.error(f"Error processing events: {e}")
                await asyncio.sleep(1)
    
    async def _handle_event(self, event: LifecycleEvent) -> bool:
        """Handle a single event."""
        try:
            handlers = self._event_handlers.get(event.event_type, [])
            
            for priority, handler in handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        handled = await result
                    else:
                        handled = result
                    
                    if handled:
                        return True
                        
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error handling event: {e}")
            return False
    
    async def _start_monitoring(self) -> None:
        """Start lifecycle monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        self.logger.info("Lifecycle monitoring started")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._perform_health_checks()
                await self._check_state_timeouts()
                await self._process_scheduled_events()
                
                time.sleep(self._health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self._health_check_interval)
    
    async def _perform_health_checks(self) -> None:
        """Perform periodic health checks."""
        try:
            # Check if agent is responsive
            if (datetime.now() - self._last_heartbeat).total_seconds() > 300:  # 5 minutes
                self.logger.warning("Agent heartbeat overdue")
                
                # Emit critical event
                await self.emit_event(
                    "heartbeat_overdue",
                    "monitor",
                    "Agent heartbeat is overdue",
                    priority=8,
                    category="health",
                    data={'last_heartbeat': self._last_heartbeat.isoformat()}
                )
            
            # Emit regular health check event
            await self.emit_event(
                "health_check",
                "monitor",
                "Periodic health check",
                priority=1,
                category="health"
            )
            
        except Exception as e:
            self.logger.error(f"Error performing health checks: {e}")
    
    async def _check_state_timeouts(self) -> None:
        """Check for state timeouts."""
        try:
            current_time = datetime.now()
            
            # Check busy state timeout
            if (self._current_state == LifecycleState.BUSY and
                self._current_state in self._state_entry_times):
                
                time_in_state = (current_time - self._state_entry_times[self._current_state]).total_seconds()
                busy_timeout = self._lifecycle_config.busy_timeout_minutes * 60
                
                if time_in_state > busy_timeout:
                    self.logger.warning(f"Busy state timeout after {time_in_state:.0f} seconds")
                    await self._transition_to_state(
                        LifecycleState.ACTIVE,
                        TransitionReason.PERFORMANCE_OPTIMIZATION
                    )
            
            # Check idle timeout
            elif (self._current_state == LifecycleState.IDLE and
                  self._current_state in self._state_entry_times):
                
                time_in_state = (current_time - self._state_entry_times[self._current_state]).total_seconds()
                idle_timeout = self._lifecycle_config.idle_timeout_minutes * 60
                
                if time_in_state > idle_timeout:
                    self.logger.info(f"Idle timeout after {time_in_state:.0f} seconds")
                    await self.emit_event(
                        "idle_timeout",
                        "monitor",
                        f"Agent idle for {self._lifecycle_config.idle_timeout_minutes} minutes",
                        priority=4,
                        category="operational",
                        data={'idle_duration_minutes': self._lifecycle_config.idle_timeout_minutes}
                    )
            
        except Exception as e:
            self.logger.error(f"Error checking state timeouts: {e}")
    
    async def _process_scheduled_events(self) -> None:
        """Process scheduled events."""
        try:
            # Check for scheduled maintenance
            if self._lifecycle_config.maintenance_schedule:
                current_time = datetime.now()
                
                for day_name, maintenance_time in self._lifecycle_config.maintenance_schedule.items():
                    # Check if maintenance should be triggered today
                    if day_name.lower() == current_time.strftime('%A').lower():
                        time_diff = (current_time - maintenance_time).total_seconds()
                        
                        # Trigger maintenance if within 1 hour window
                        if -3600 <= time_diff <= 3600:  # 1 hour before to 1 hour after
                            await self.emit_event(
                                "maintenance_scheduled",
                                "scheduler",
                                f"Scheduled maintenance for {day_name}",
                                priority=6,
                                category="maintenance",
                                data={'scheduled_time': maintenance_time.isoformat()}
                            )
            
        except Exception as e:
            self.logger.error(f"Error processing scheduled events: {e}")
    
    async def _drain_event_queue(self) -> None:
        """Drain the event queue."""
        try:
            # Process remaining events
            while not self._event_queue.empty():
                try:
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
                    await self._handle_event(event)
                except asyncio.TimeoutError:
                    break
            
        except Exception as e:
            self.logger.error(f"Error draining event queue: {e}")
    
    async def _handle_initialization_error(self, error: Exception) -> None:
        """Handle initialization errors."""
        try:
            self.logger.error(f"Initialization error: {error}")
            
            # Try to transition to error state
            try:
                await self._transition_to_state(
                    LifecycleState.ERROR,
                    TransitionReason.SYSTEM_STARTUP,
                    {'error': str(error)}
                )
            except Exception as transition_error:
                self.logger.error(f"Failed to transition to error state: {transition_error}")
            
        except Exception as e:
            self.logger.error(f"Error handling initialization error: {e}")
    
    async def _load_configuration(self) -> None:
        """Load lifecycle configuration."""
        # In a real implementation, this would load from configuration files
        # For now, use default configuration
        pass
    
    async def _save_state(self) -> None:
        """Save current state."""
        # In a real implementation, this would save to persistent storage
        # For now, just log the event
        self.logger.info("Lifecycle manager state saved")