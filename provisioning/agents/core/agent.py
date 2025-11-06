"""
WebOps AI Agent - Main Agent Class

This module implements the main WebOpsAgent class that orchestrates
all components to create an AI agent with human-like characteristics.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..personality.traits import PersonalityProfile
from ..personality.emotions import EmotionalState
from ..memory.memory_manager import MemoryManager
from ..communication.communication_manager import CommunicationManager
from ..skills.skill_registry import SkillRegistry
from ..decision.decision_engine import DecisionEngine
from .lifecycle import AgentLifecycle, AgentState
from .resources import ResourceManager, ResourceLimits


class AgentStatus(Enum):
    """Agent operational status."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    LEARNING = "learning"
    RESTING = "resting"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class AgentConfig:
    """Configuration for agent initialization."""
    name: str
    personality: PersonalityProfile
    skills: List[str] = field(default_factory=list)
    memory_size_mb: int = 1024
    learning_rate: float = 0.01
    communication_protocols: List[str] = field(default_factory=lambda: ["websocket", "rest"])
    resource_limits: Optional[ResourceLimits] = None
    auto_save_interval: int = 300  # seconds
    max_concurrent_tasks: int = 5


@dataclass
class AgentMetrics:
    """Agent performance and behavior metrics."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    decisions_made: int = 0
    skills_learned: int = 0
    interactions_count: int = 0
    uptime_seconds: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    last_activity: Optional[datetime] = None
    mood_score: float = 0.5  # -1.0 to 1.0


class WebOpsAgent:
    """
    Main WebOps Agent class with human-like characteristics.
    
    This class orchestrates all components to create an intelligent agent
    that can learn, adapt, communicate, and make decisions based on
    personality traits and past experiences.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize the WebOps Agent."""
        self.config = config
        self.name = config.name
        self.status = AgentStatus.INITIALIZING
        self.created_at = datetime.now()
        
        # Core components
        self.personality = config.personality
        self.emotional_state = EmotionalState(self.personality)
        self.lifecycle = AgentLifecycle(self)
        self.resource_manager = ResourceManager(config.resource_limits)
        
        # Functional components
        self.memory = MemoryManager(config.memory_size_mb)
        self.skills = SkillRegistry()
        self.communication = CommunicationManager(self)
        self.decision_engine = DecisionEngine(self)
        
        # Runtime state
        self.metrics = AgentMetrics()
        self._running = False
        self._task_queue = asyncio.Queue()
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Logging
        self.logger = logging.getLogger(f"agent.{self.name}")
        
        # Initialize skills
        asyncio.create_task(self._initialize_skills(config.skills))
    
    async def start(self) -> None:
        """Start the agent and begin operation."""
        try:
            self.logger.info(f"Starting agent {self.name}")
            self.status = AgentStatus.INITIALIZING
            
            # Initialize lifecycle
            await self.lifecycle.initialize()
            
            # Start resource monitoring
            await self.resource_manager.start_monitoring()
            
            # Start communication channels
            await self.communication.start()
            
            # Start main operation loops
            self._running = True
            await asyncio.gather(
                self._main_loop(),
                self._learning_loop(),
                self._resource_monitoring_loop(),
                self._auto_save_loop()
            )
            
            self.status = AgentStatus.ACTIVE
            self.logger.info(f"Agent {self.name} started successfully")
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Failed to start agent {self.name}: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the agent gracefully."""
        self.logger.info(f"Stopping agent {self.name}")
        self.status = AgentStatus.SHUTDOWN
        self._running = False
        
        # Save final state
        await self._save_state()
        
        # Stop components
        await self.communication.stop()
        await self.resource_manager.stop_monitoring()
        await self.lifecycle.shutdown()
        
        self.logger.info(f"Agent {self.name} stopped")
    
    async def think(self, stimulus: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process stimulus and generate thoughts.
        
        Args:
            stimulus: Input data to process
            
        Returns:
            Generated thoughts and analysis
        """
        try:
            # Update emotional state based on stimulus
            await self.emotional_state.update_from_stimulus(stimulus)
            
            # Retrieve relevant memories
            relevant_memories = await self.memory.recall_similar(stimulus)
            
            # Analyze situation
            analysis = await self.decision_engine.analyze_situation(
                stimulus, relevant_memories, self.emotional_state.current_state
            )
            
            # Generate thoughts
            thoughts = await self.decision_engine.generate_thoughts(
                analysis, self.personality, self.emotional_state
            )
            
            # Store thinking process
            await self.memory.store_thinking_process(stimulus, thoughts)
            
            return {
                'analysis': analysis,
                'thoughts': thoughts,
                'emotional_state': self.emotional_state.current_state,
                'confidence': thoughts.get('confidence', 0.5)
            }
            
        except Exception as e:
            self.logger.error(f"Error in think method: {e}")
            return {'error': str(e)}
    
    async def act(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute actions based on decisions.
        
        Args:
            decision: Decision to execute
            
        Returns:
            Action results
        """
        try:
            self.status = AgentStatus.BUSY
            self.metrics.last_activity = datetime.now()
            
            # Validate decision
            validation = await self.decision_engine.validate_decision(decision)
            if not validation['valid']:
                return {'error': validation['reason']}
            
            # Select and execute skills
            action_results = []
            for action in decision.get('actions', []):
                skill_name = action.get('skill')
                if await self.skills.has_skill(skill_name):
                    result = await self.skills.execute_skill(
                        skill_name, action.get('parameters', {}), self._get_context()
                    )
                    action_results.append(result)
                else:
                    action_results.append({
                        'skill': skill_name,
                        'error': f'Skill {skill_name} not available'
                    })
            
            # Update metrics
            self.metrics.decisions_made += 1
            if all(r.get('success', False) for r in action_results):
                self.metrics.tasks_completed += 1
            else:
                self.metrics.tasks_failed += 1
            
            # Store experience
            await self.memory.store_experience({
                'decision': decision,
                'results': action_results,
                'emotional_state': self.emotional_state.current_state,
                'timestamp': datetime.now()
            })
            
            # Learn from experience
            await self._learn_from_experience(decision, action_results)
            
            self.status = AgentStatus.ACTIVE
            return {
                'success': True,
                'results': action_results,
                'emotional_impact': self.emotional_state.get_recent_changes()
            }
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Error in act method: {e}")
            return {'error': str(e)}
    
    async def chat(self, message: str, context: Optional[Dict] = None) -> str:
        """
        Chat with the agent.
        
        Args:
            message: Chat message
            context: Additional context
            
        Returns:
            Agent response
        """
        try:
            self.metrics.interactions_count += 1
            
            # Process message through communication layer
            response = await self.communication.process_message(
                message, context or {}, self._get_context()
            )
            
            # Update emotional state based on interaction
            await self.emotional_state.update_from_interaction(message, response)
            
            # Store conversation
            await self.memory.store_conversation({
                'message': message,
                'response': response,
                'context': context,
                'timestamp': datetime.now()
            })
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in chat method: {e}")
            return f"Sorry, I encountered an error: {e}"
    
    async def assign_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assign a task to the agent.
        
        Args:
            task: Task definition
            
        Returns:
            Task execution result
        """
        try:
            # Add to task queue
            await self._task_queue.put(task)
            
            return {
                'success': True,
                'message': f"Task queued for {self.name}",
                'task_id': task.get('id', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Error assigning task: {e}")
            return {'error': str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status and metrics."""
        return {
            'name': self.name,
            'status': self.status.value,
            'uptime_seconds': self.metrics.uptime_seconds,
            'tasks_completed': self.metrics.tasks_completed,
            'tasks_failed': self.metrics.tasks_failed,
            'decisions_made': self.metrics.decisions_made,
            'skills_learned': self.metrics.skills_learned,
            'interactions_count': self.metrics.interactions_count,
            'current_mood': self.emotional_state.get_mood(),
            'personality': self.personality.to_dict(),
            'memory_usage_mb': self.metrics.memory_usage_mb,
            'cpu_usage_percent': self.metrics.cpu_usage_percent,
            'last_activity': self.metrics.last_activity.isoformat() if self.metrics.last_activity else None
        }
    
    async def learn_skill(self, skill_name: str, training_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Learn a new skill.
        
        Args:
            skill_name: Name of skill to learn
            training_data: Training data for the skill
            
        Returns:
            Learning result
        """
        try:
            self.status = AgentStatus.LEARNING
            
            # Learn the skill
            result = await self.skills.learn_skill(skill_name, training_data)
            
            if result['success']:
                self.metrics.skills_learned += 1
                
                # Store learning experience
                await self.memory.store_learning_experience({
                    'skill': skill_name,
                    'training_data': training_data,
                    'result': result,
                    'timestamp': datetime.now()
                })
            
            self.status = AgentStatus.ACTIVE
            return result
            
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error(f"Error learning skill {skill_name}: {e}")
            return {'error': str(e)}
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current agent context for decision making."""
        return {
            'name': self.name,
            'personality': self.personality,
            'emotional_state': self.emotional_state.current_state,
            'available_skills': self.skills.list_skills(),
            'metrics': self.metrics,
            'current_time': datetime.now()
        }
    
    async def _initialize_skills(self, skill_names: List[str]) -> None:
        """Initialize agent with default skills."""
        for skill_name in skill_names:
            try:
                await self.skills.load_skill(skill_name)
                self.logger.info(f"Loaded skill: {skill_name}")
            except Exception as e:
                self.logger.warning(f"Failed to load skill {skill_name}: {e}")
    
    async def _main_loop(self) -> None:
        """Main agent operation loop."""
        while self._running:
            try:
                # Process queued tasks
                if not self._task_queue.empty():
                    task = await self._task_queue.get()
                    await self._process_task(task)
                
                # Rest if no tasks
                if self._task_queue.empty():
                    self.status = AgentStatus.RESTING
                    await asyncio.sleep(1)
                else:
                    self.status = AgentStatus.ACTIVE
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)
    
    async def _learning_loop(self) -> None:
        """Continuous learning loop."""
        while self._running:
            try:
                # Consolidate learning
                await self.memory.consolidate_learning()
                
                # Update personality based on experiences
                await self._update_personality()
                
                # Sleep for learning interval
                await asyncio.sleep(60)  # Learn every minute
                
            except Exception as e:
                self.logger.error(f"Error in learning loop: {e}")
                await asyncio.sleep(30)
    
    async def _resource_monitoring_loop(self) -> None:
        """Resource monitoring loop."""
        while self._running:
            try:
                # Update resource metrics
                resource_usage = await self.resource_manager.get_current_usage()
                self.metrics.memory_usage_mb = resource_usage.memory_mb
                self.metrics.cpu_usage_percent = resource_usage.cpu_percent
                
                # Check resource limits
                if await self.resource_manager.is_near_limit():
                    self.logger.warning("Resource usage near limits")
                    await self._optimize_resource_usage()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _auto_save_loop(self) -> None:
        """Auto-save loop for agent state."""
        while self._running:
            try:
                await self._save_state()
                await asyncio.sleep(self.config.auto_save_interval)
                
            except Exception as e:
                self.logger.error(f"Error in auto-save: {e}")
                await asyncio.sleep(60)
    
    async def _process_task(self, task: Dict[str, Any]) -> None:
        """Process a single task."""
        try:
            # Think about the task
            thinking = await self.think(task)
            
            # Make decision
            decision = await self.decision_engine.make_decision(
                thinking, self._get_context()
            )
            
            # Act on decision
            result = await self.act(decision)
            
            # Emit task completion event
            await self._emit_event('task_completed', {
                'task': task,
                'result': result
            })
            
        except Exception as e:
            self.logger.error(f"Error processing task: {e}")
            await self._emit_event('task_failed', {
                'task': task,
                'error': str(e)
            })
    
    async def _learn_from_experience(self, decision: Dict[str, Any], results: List[Dict]) -> None:
        """Learn from action results."""
        try:
            # Calculate success rate
            success_rate = sum(1 for r in results if r.get('success', False)) / len(results)
            
            # Update emotional state
            await self.emotional_state.update_from_results(success_rate)
            
            # Learn from patterns
            patterns = await self.memory.identify_patterns(decision, results)
            for pattern in patterns:
                await self.skills.update_from_pattern(pattern)
            
        except Exception as e:
            self.logger.error(f"Error learning from experience: {e}")
    
    async def _update_personality(self) -> None:
        """Update personality based on experiences."""
        try:
            # Get recent experiences
            recent_experiences = await self.memory.get_recent_experiences(100)
            
            # Calculate personality adjustments
            adjustments = self.personality.calculate_adjustments(recent_experiences)
            
            # Apply adjustments if significant
            if any(abs(adj) > 0.01 for adj in adjustments.values()):
                self.personality.apply_adjustments(adjustments)
                self.logger.info(f"Personality updated: {adjustments}")
            
        except Exception as e:
            self.logger.error(f"Error updating personality: {e}")
    
    async def _optimize_resource_usage(self) -> None:
        """Optimize resource usage when near limits."""
        try:
            # Clean old memories
            await self.memory.cleanup_old_memories()
            
            # Optimize skill storage
            await self.skills.optimize_storage()
            
            self.logger.info("Resource optimization completed")
            
        except Exception as e:
            self.logger.error(f"Error optimizing resources: {e}")
    
    async def _save_state(self) -> None:
        """Save agent state to persistent storage."""
        try:
            state = {
                'name': self.name,
                'personality': self.personality.to_dict(),
                'metrics': self.metrics.__dict__,
                'emotional_state': self.emotional_state.to_dict(),
                'saved_at': datetime.now().isoformat()
            }
            
            # Save to file or database
            await self.memory.save_agent_state(state)
            
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to registered handlers."""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.error(f"Error in event handler: {e}")
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def unregister_event_handler(self, event_type: str, handler: Callable) -> None:
        """Unregister an event handler."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass  # Handler not found