"""
Memory Manager Module

Orchestrates all memory systems for the AI agent,
providing unified access to episodic, semantic, and procedural memory.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .episodic import EpisodicMemory, Experience
from .semantic import SemanticMemory, Fact, Knowledge
from .procedural import ProceduralMemory, Procedure, Skill
from .learning import LearningSystem, LearningResult


class MemoryType(Enum):
    """Types of memory storage."""
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


@dataclass
class MemoryConfig:
    """Configuration for memory systems."""
    max_size_mb: int = 1024
    retention_days: int = 30
    consolidation_interval_hours: int = 24
    compression_enabled: bool = True
    indexing_enabled: bool = True
    backup_enabled: bool = True
    backup_path: Optional[str] = None


@dataclass
class MemoryStats:
    """Memory system statistics."""
    total_memories: int = 0
    episodic_count: int = 0
    semantic_count: int = 0
    procedural_count: int = 0
    working_count: int = 0
    size_mb: float = 0.0
    last_consolidation: Optional[datetime] = None
    access_count: int = 0
    hit_rate: float = 0.0


class MemoryManager:
    """
    Manages all memory systems for the AI agent.
    
    Provides unified interface for storing and retrieving memories
    across different memory types.
    """
    
    def __init__(self, config: MemoryConfig):
        """Initialize memory manager."""
        self.config = config
        self.logger = logging.getLogger("memory_manager")
        
        # Initialize memory systems
        self.episodic = EpisodicMemory(config)
        self.semantic = SemanticMemory(config)
        self.procedural = ProceduralMemory(config)
        self.learning = LearningSystem(config)
        
        # Working memory (temporary storage)
        self.working_memory: Dict[str, Any] = {}
        
        # Memory statistics
        self.stats = MemoryStats()
        self._access_count = 0
        self._hit_count = 0
        
        # Background tasks
        self._consolidation_task = None
        self._cleanup_task = None
        
        # Start background tasks
        self._start_background_tasks()
    
    async def store_experience(self, experience: Dict[str, Any]) -> str:
        """
        Store an experience in episodic memory.
        
        Args:
            experience: Experience data to store
            
        Returns:
            Experience ID
        """
        try:
            # Create experience object
            exp = Experience(
                timestamp=datetime.now(),
                context=experience.get('context', {}),
                events=experience.get('events', []),
                outcomes=experience.get('outcomes', []),
                emotional_state=experience.get('emotional_state', {}),
                importance=experience.get('importance', 0.5)
            )
            
            # Store in episodic memory
            experience_id = await self.episodic.store_experience(exp)
            
            # Update statistics
            self.stats.episodic_count += 1
            self.stats.total_memories += 1
            
            # Trigger learning if enabled
            if self.config.indexing_enabled:
                asyncio.create_task(self._trigger_learning(experience))
            
            return experience_id
            
        except Exception as e:
            self.logger.error(f"Error storing experience: {e}")
            raise
    
    async def store_fact(self, fact: Dict[str, Any]) -> str:
        """
        Store a fact in semantic memory.
        
        Args:
            fact: Fact data to store
            
        Returns:
            Fact ID
        """
        try:
            # Create fact object
            fact_obj = Fact(
                content=fact.get('content', ''),
                category=fact.get('category', 'general'),
                confidence=fact.get('confidence', 0.5),
                source=fact.get('source', 'agent'),
                tags=fact.get('tags', []),
                timestamp=datetime.now()
            )
            
            # Store in semantic memory
            fact_id = await self.semantic.store_fact(fact_obj)
            
            # Update statistics
            self.stats.semantic_count += 1
            self.stats.total_memories += 1
            
            return fact_id
            
        except Exception as e:
            self.logger.error(f"Error storing fact: {e}")
            raise
    
    async def store_procedure(self, procedure: Dict[str, Any]) -> str:
        """
        Store a procedure in procedural memory.
        
        Args:
            procedure: Procedure data to store
            
        Returns:
            Procedure ID
        """
        try:
            # Create procedure object
            proc = Procedure(
                name=procedure.get('name', ''),
                steps=procedure.get('steps', []),
                preconditions=procedure.get('preconditions', []),
                outcomes=procedure.get('outcomes', []),
                success_rate=procedure.get('success_rate', 0.0),
                timestamp=datetime.now()
            )
            
            # Store in procedural memory
            procedure_id = await self.procedural.store_procedure(proc)
            
            # Update statistics
            self.stats.procedural_count += 1
            self.stats.total_memories += 1
            
            return procedure_id
            
        except Exception as e:
            self.logger.error(f"Error storing procedure: {e}")
            raise
    
    async def recall_similar(self, stimulus: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recall similar experiences from memory.
        
        Args:
            stimulus: Stimulus to match against
            limit: Maximum number of results
            
        Returns:
            List of similar memories
        """
        try:
            self._access_count += 1
            
            # Search across all memory types
            results = []
            
            # Search episodic memory
            episodic_results = await self.episodic.search_similar(stimulus, limit // 2)
            for result in episodic_results:
                result['memory_type'] = MemoryType.EPISODIC.value
                results.append(result)
            
            # Search semantic memory
            semantic_results = await self.semantic.search_facts(stimulus, limit // 2)
            for result in semantic_results:
                result['memory_type'] = MemoryType.SEMANTIC.value
                results.append(result)
            
            # Search procedural memory
            procedural_results = await self.procedural.search_procedures(stimulus, limit // 2)
            for result in procedural_results:
                result['memory_type'] = MemoryType.PROCEDURAL.value
                results.append(result)
            
            # Sort by relevance and limit
            results.sort(key=lambda x: x.get('relevance', 0.0), reverse=True)
            results = results[:limit]
            
            if results:
                self._hit_count += 1
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error recalling similar memories: {e}")
            return []
    
    async def get_recent_experiences(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent experiences from episodic memory.
        
        Args:
            limit: Maximum number of experiences
            
        Returns:
            List of recent experiences
        """
        try:
            experiences = await self.episodic.get_recent_experiences(limit)
            
            # Convert to dictionaries
            return [exp.to_dict() for exp in experiences]
            
        except Exception as e:
            self.logger.error(f"Error getting recent experiences: {e}")
            return []
    
    async def store_thinking_process(self, stimulus: Dict[str, Any], thoughts: Dict[str, Any]) -> str:
        """
        Store thinking process in working memory.
        
        Args:
            stimulus: Original stimulus
            thoughts: Generated thoughts
            
        Returns:
            Thinking process ID
        """
        try:
            thinking_id = f"thinking_{datetime.now().timestamp()}"
            
            self.working_memory[thinking_id] = {
                'stimulus': stimulus,
                'thoughts': thoughts,
                'timestamp': datetime.now(),
                'type': 'thinking_process'
            }
            
            # Update statistics
            self.stats.working_count += 1
            
            # Clean old working memory
            await self._cleanup_working_memory()
            
            return thinking_id
            
        except Exception as e:
            self.logger.error(f"Error storing thinking process: {e}")
            raise
    
    async def store_conversation(self, conversation: Dict[str, Any]) -> str:
        """
        Store conversation in episodic memory.
        
        Args:
            conversation: Conversation data
            
        Returns:
            Conversation ID
        """
        try:
            # Create experience from conversation
            experience = Experience(
                timestamp=datetime.now(),
                context=conversation.get('context', {}),
                events=[
                    {'type': 'message', 'content': conversation.get('message', '')},
                    {'type': 'response', 'content': conversation.get('response', '')}
                ],
                outcomes=[{'type': 'conversation_completed'}],
                emotional_state=conversation.get('emotional_state', {}),
                importance=0.7  # Conversations are important
            )
            
            return await self.episodic.store_experience(experience)
            
        except Exception as e:
            self.logger.error(f"Error storing conversation: {e}")
            raise
    
    async def store_learning_experience(self, learning_data: Dict[str, Any]) -> str:
        """
        Store learning experience in semantic memory.
        
        Args:
            learning_data: Learning experience data
            
        Returns:
            Learning experience ID
        """
        try:
            # Create fact from learning experience
            fact = Fact(
                content=f"Learned skill: {learning_data.get('skill', '')}",
                category='learning',
                confidence=learning_data.get('result', {}).get('success', False),
                source='agent_learning',
                tags=['skill', 'learning', learning_data.get('skill', '')],
                timestamp=datetime.now()
            )
            
            return await self.semantic.store_fact(fact)
            
        except Exception as e:
            self.logger.error(f"Error storing learning experience: {e}")
            raise
    
    async def identify_patterns(self, decision: Dict[str, Any], results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Identify patterns in decision-making and results.
        
        Args:
            decision: Decision that was made
            results: Results of the decision
            
        Returns:
            List of identified patterns
        """
        try:
            patterns = []
            
            # Analyze success patterns
            success_rate = sum(1 for r in results if r.get('success', False)) / len(results)
            
            if success_rate > 0.8:
                patterns.append({
                    'type': 'success_pattern',
                    'decision_type': decision.get('type', 'unknown'),
                    'context': decision.get('context', {}),
                    'confidence': success_rate,
                    'timestamp': datetime.now()
                })
            
            # Analyze failure patterns
            if success_rate < 0.3:
                patterns.append({
                    'type': 'failure_pattern',
                    'decision_type': decision.get('type', 'unknown'),
                    'context': decision.get('context', {}),
                    'confidence': 1.0 - success_rate,
                    'timestamp': datetime.now()
                })
            
            # Store patterns in semantic memory
            for pattern in patterns:
                await self.store_fact({
                    'content': json.dumps(pattern),
                    category='pattern',
                    confidence=pattern['confidence'],
                    source='pattern_recognition',
                    tags=['pattern', pattern['type']]
                })
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error identifying patterns: {e}")
            return []
    
    async def consolidate_learning(self) -> None:
        """Consolidate learning across all memory systems."""
        try:
            self.logger.info("Starting learning consolidation")
            
            # Consolidate episodic memories
            await self.episodic.consolidate_memories()
            
            # Consolidate semantic knowledge
            await self.semantic.consolidate_knowledge()
            
            # Optimize procedural memory
            await self.procedural.optimize_procedures()
            
            # Update statistics
            self.stats.last_consolidation = datetime.now()
            
            self.logger.info("Learning consolidation completed")
            
        except Exception as e:
            self.logger.error(f"Error consolidating learning: {e}")
    
    async def cleanup_old_memories(self) -> None:
        """Clean up old memories based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            
            # Clean episodic memory
            await self.episodic.cleanup_old_memories(cutoff_date)
            
            # Clean semantic memory
            await self.semantic.cleanup_old_facts(cutoff_date)
            
            # Clean procedural memory
            await self.procedural.cleanup_old_procedures(cutoff_date)
            
            self.logger.info(f"Cleaned up memories older than {cutoff_date}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old memories: {e}")
    
    async def save_agent_state(self, state: Dict[str, Any]) -> None:
        """
        Save agent state to persistent storage.
        
        Args:
            state: Agent state to save
        """
        try:
            if not self.config.backup_enabled:
                return
            
            # Save to file or database
            backup_path = self.config.backup_path or f"agent_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(backup_path, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            self.logger.info(f"Agent state saved to {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving agent state: {e}")
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        try:
            # Update hit rate
            if self._access_count > 0:
                self.stats.hit_rate = self._hit_count / self._access_count
            
            # Get memory sizes
            self.stats.size_mb = await self._calculate_memory_size()
            
            return {
                'total_memories': self.stats.total_memories,
                'episodic_count': self.stats.episodic_count,
                'semantic_count': self.stats.semantic_count,
                'procedural_count': self.stats.procedural_count,
                'working_count': self.stats.working_count,
                'size_mb': self.stats.size_mb,
                'hit_rate': self.stats.hit_rate,
                'last_consolidation': self.stats.last_consolidation.isoformat() if self.stats.last_consolidation else None
            }
            
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _trigger_learning(self, experience: Experience) -> None:
        """Trigger learning from new experience."""
        try:
            # Convert experience to learning format
            learning_data = {
                'experience': experience.to_dict(),
                'type': 'experience_learning'
            }
            
            # Trigger learning system
            await self.learning.learn_from_experience(learning_data)
            
        except Exception as e:
            self.logger.error(f"Error triggering learning: {e}")
    
    async def _cleanup_working_memory(self) -> None:
        """Clean up old working memory entries."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            # Remove old entries
            to_remove = []
            for key, value in self.working_memory.items():
                if isinstance(value, dict) and 'timestamp' in value:
                    if value['timestamp'] < cutoff_time:
                        to_remove.append(key)
            
            for key in to_remove:
                del self.working_memory[key]
            
            self.stats.working_count = len(self.working_memory)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up working memory: {e}")
    
    async def _calculate_memory_size(self) -> float:
        """Calculate total memory size in MB."""
        try:
            # This is a simplified calculation
            # In practice, would use actual memory profiling
            
            episodic_size = self.stats.episodic_count * 0.1  # MB per experience
            semantic_size = self.stats.semantic_count * 0.05   # MB per fact
            procedural_size = self.stats.procedural_count * 0.2  # MB per procedure
            working_size = self.stats.working_count * 0.01     # MB per working memory item
            
            return episodic_size + semantic_size + procedural_size + working_size
            
        except Exception as e:
            self.logger.error(f"Error calculating memory size: {e}")
            return 0.0
    
    def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        try:
            # Start consolidation task
            self._consolidation_task = asyncio.create_task(self._consolidation_loop())
            
            # Start cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
        except Exception as e:
            self.logger.error(f"Error starting background tasks: {e}")
    
    async def _consolidation_loop(self) -> None:
        """Background consolidation loop."""
        while True:
            try:
                # Wait for consolidation interval
                await asyncio.sleep(self.config.consolidation_interval_hours * 3600)
                
                # Run consolidation
                await self.consolidate_learning()
                
            except Exception as e:
                self.logger.error(f"Error in consolidation loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                # Wait for cleanup interval (daily)
                await asyncio.sleep(24 * 3600)
                
                # Run cleanup
                await self.cleanup_old_memories()
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying