"""
Procedural Memory Module

Stores and retrieves learned procedures and skills for the AI agent.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid


class ProcedureType(Enum):
    """Types of procedures stored in procedural memory."""
    
    WORKFLOW = "workflow"
    ALGORITHM = "algorithm"
    TASK = "task"
    SKILL = "skill"
    PROTOCOL = "protocol"
    METHOD = "method"
    PATTERN = "pattern"
    GENERAL = "general"


class ProcedureStatus(Enum):
    """Status of procedures in procedural memory."""
    
    LEARNING = "learning"
    PRACTICING = "practicing"
    MASTERED = "mastered"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class StepType(Enum):
    """Types of steps in a procedure."""
    
    ACTION = "action"
    DECISION = "decision"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    SEQUENCE = "sequence"
    WAIT = "wait"
    VALIDATION = "validation"


@dataclass
class ProcedureStep:
    """A single step in a procedure."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_type: StepType = StepType.ACTION
    description: str = ""
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    expected_outcome: Optional[str] = None
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 3
    next_steps: List[str] = field(default_factory=list)
    parallel_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        data = asdict(self)
        data['step_type'] = self.step_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcedureStep':
        """Create step from dictionary."""
        if 'step_type' in data and isinstance(data['step_type'], str):
            data['step_type'] = StepType(data['step_type'])
        return cls(**data)


@dataclass
class Procedure:
    """A learned procedure stored in procedural memory."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    procedure_type: ProcedureType = ProcedureType.GENERAL
    steps: List[ProcedureStep] = field(default_factory=list)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    success_rate: float = 0.0
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: ProcedureStatus = ProcedureStatus.LEARNING
    complexity_score: float = 0.0
    estimated_duration: float = 0.0
    required_resources: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert procedure to dictionary."""
        data = asdict(self)
        data['procedure_type'] = self.procedure_type.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['last_executed'] = self.last_executed.isoformat() if self.last_executed else None
        data['steps'] = [step.to_dict() for step in self.steps]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Procedure':
        """Create procedure from dictionary."""
        if 'procedure_type' in data and isinstance(data['procedure_type'], str):
            data['procedure_type'] = ProcedureType(data['procedure_type'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ProcedureStatus(data['status'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_executed' in data and isinstance(data['last_executed'], str):
            data['last_executed'] = datetime.fromisoformat(data['last_executed'])
        if 'steps' in data:
            data['steps'] = [ProcedureStep.from_dict(step) for step in data['steps']]
        return cls(**data)
    
    def calculate_complexity(self) -> float:
        """Calculate procedure complexity score."""
        if not self.steps:
            return 0.0
        
        complexity = 0.0
        
        # Base complexity from number of steps
        complexity += len(self.steps) * 0.1
        
        # Complexity from step types
        for step in self.steps:
            if step.step_type == StepType.DECISION:
                complexity += 0.3
            elif step.step_type == StepType.LOOP:
                complexity += 0.4
            elif step.step_type == StepType.PARALLEL:
                complexity += 0.5
            elif step.step_type == StepType.CONDITION:
                complexity += 0.2
        
        # Complexity from conditions
        total_conditions = sum(len(step.conditions) for step in self.steps)
        complexity += total_conditions * 0.05
        
        # Complexity from parallel steps
        total_parallel = sum(len(step.parallel_steps) for step in self.steps)
        complexity += total_parallel * 0.1
        
        # Normalize to 0-1 range
        return min(1.0, complexity / 2.0)
    
    def estimate_duration(self) -> float:
        """Estimate procedure execution duration in seconds."""
        if not self.steps:
            return 0.0
        
        total_duration = 0.0
        
        for step in self.steps:
            step_duration = step.timeout_seconds
            
            # Adjust based on step type
            if step.step_type == StepType.LOOP:
                step_duration *= 2.0  # Loops take longer
            elif step.step_type == StepType.PARALLEL:
                # Parallel steps run concurrently
                if step.parallel_steps:
                    max_parallel = max(
                        self._get_step_duration(sid) 
                        for sid in step.parallel_steps
                    )
                    step_duration = max(step_duration, max_parallel)
            elif step.step_type == StepType.DECISION:
                step_duration *= 1.5  # Decisions need thinking time
            
            total_duration += step_duration
        
        return total_duration
    
    def _get_step_duration(self, step_id: str) -> float:
        """Get duration of a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step.timeout_seconds
        return 30.0  # Default duration


class Skill:
    """A specialized procedure representing a learned skill."""
    
    def __init__(
        self,
        name: str,
        description: str,
        procedure_id: str,
        proficiency: float = 0.0,
        category: str = "general"
    ):
        self.name = name
        self.description = description
        self.procedure_id = procedure_id
        self.proficiency = proficiency  # 0.0 to 1.0
        self.category = category
        self.practice_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_practiced = None
        self.created_at = datetime.now()
        self.metadata = {}
    
    def update_proficiency(self, success: bool) -> None:
        """Update skill proficiency based on practice outcome."""
        self.practice_count += 1
        self.last_practiced = datetime.now()
        
        if success:
            self.success_count += 1
            # Increase proficiency
            self.proficiency = min(1.0, self.proficiency + 0.05)
        else:
            self.failure_count += 1
            # Decrease proficiency slightly
            self.proficiency = max(0.0, self.proficiency - 0.02)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class ProceduralMemory:
    """Stores and retrieves learned procedures and skills."""
    
    def __init__(self, config):
        """Initialize procedural memory."""
        self.config = config
        self.logger = logging.getLogger("procedural_memory")
        
        # Storage
        self._procedures: Dict[str, Procedure] = {}
        self._skills: Dict[str, Skill] = {}
        
        # Indices
        self._name_index: Dict[str, str] = {}
        self._type_index: Dict[ProcedureType, List[str]] = {
            proc_type: [] for proc_type in ProcedureType
        }
        self._tag_index: Dict[str, List[str]] = {}
        self._category_index: Dict[str, List[str]] = {}
        
        # Execution tracking
        self._execution_history: List[Dict[str, Any]] = []
        
        # Statistics
        self._total_procedures = 0
        self._total_skills = 0
        self._last_cleanup = datetime.now()
    
    async def store_procedure(self, procedure: Procedure) -> str:
        """Store a learned procedure."""
        try:
            # Calculate complexity and duration
            procedure.complexity_score = procedure.calculate_complexity()
            procedure.estimated_duration = procedure.estimate_duration()
            
            # Store procedure
            self._procedures[procedure.id] = procedure
            
            # Update indices
            await self._index_procedure(procedure)
            
            # Update statistics
            self._total_procedures += 1
            
            # Check if cleanup is needed
            await self._check_cleanup()
            
            self.logger.debug(f"Stored procedure: {procedure.id}")
            return procedure.id
            
        except Exception as e:
            self.logger.error(f"Error storing procedure: {e}")
            raise
    
    async def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        """Get a procedure by ID."""
        return self._procedures.get(procedure_id)
    
    async def search_procedures(
        self,
        query: str,
        procedure_type: Optional[ProcedureType] = None,
        category: Optional[str] = None,
        min_success_rate: float = 0.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for procedures."""
        try:
            results = []
            query_lower = query.lower()
            
            for procedure in self._procedures.values():
                # Filter by type
                if procedure_type and procedure.procedure_type != procedure_type:
                    continue
                
                # Filter by category
                if category and procedure.category != category:
                    continue
                
                # Filter by success rate
                if procedure.success_rate < min_success_rate:
                    continue
                
                # Calculate relevance
                relevance = 0.0
                
                # Name match
                if query_lower in procedure.name.lower():
                    relevance += 0.5
                
                # Description match
                if query_lower in procedure.description.lower():
                    relevance += 0.3
                
                # Tag matches
                tag_matches = sum(1 for tag in procedure.tags if query_lower in tag.lower())
                if tag_matches > 0:
                    relevance += 0.2 * (tag_matches / len(procedure.tags)) if procedure.tags else 0.2
                
                if relevance > 0:
                    results.append({
                        'procedure_id': procedure.id,
                        'name': procedure.name,
                        'description': procedure.description,
                        'procedure_type': procedure.procedure_type.value,
                        'success_rate': procedure.success_rate,
                        'complexity_score': procedure.complexity_score,
                        'estimated_duration': procedure.estimated_duration,
                        'execution_count': procedure.execution_count,
                        'relevance': relevance,
                        'tags': procedure.tags,
                        'status': procedure.status.value
                    })
            
            # Sort by relevance
            results.sort(key=lambda x: x['relevance'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            self.logger.error(f"Error searching procedures: {e}")
            return []
    
    async def execute_procedure(
        self,
        procedure_id: str,
        context: Dict[str, Any],
        step_executor: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Execute a procedure."""
        try:
            procedure = self._procedures.get(procedure_id)
            if not procedure:
                return {
                    'success': False,
                    'error': f'Procedure {procedure_id} not found'
                }
            
            # Update execution statistics
            procedure.execution_count += 1
            procedure.last_executed = datetime.now()
            
            # Check preconditions
            precondition_result = await self._check_preconditions(procedure, context)
            if not precondition_result['satisfied']:
                return {
                    'success': False,
                    'error': 'Preconditions not satisfied',
                    'failed_preconditions': precondition_result['failed']
                }
            
            # Execute steps
            execution_result = await self._execute_steps(
                procedure, context, step_executor
            )
            
            # Update procedure based on execution result
            await self._update_procedure_from_execution(
                procedure, execution_result
            )
            
            # Record execution history
            self._execution_history.append({
                'procedure_id': procedure_id,
                'context': context,
                'result': execution_result,
                'timestamp': datetime.now()
            })
            
            # Limit history size
            if len(self._execution_history) > 1000:
                self._execution_history = self._execution_history[-500:]
            
            return execution_result
            
        except Exception as e:
            self.logger.error(f"Error executing procedure: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def learn_skill(
        self,
        name: str,
        description: str,
        procedure_id: str,
        category: str = "general"
    ) -> str:
        """Learn a new skill from a procedure."""
        try:
            # Check if procedure exists
            if procedure_id not in self._procedures:
                raise ValueError(f"Procedure {procedure_id} not found")
            
            # Create skill
            skill = Skill(
                name=name,
                description=description,
                procedure_id=procedure_id,
                category=category
            )
            
            # Store skill
            self._skills[name] = skill
            self._total_skills += 1
            
            # Update category index
            if category not in self._category_index:
                self._category_index[category] = []
            if name not in self._category_index[category]:
                self._category_index[category].append(name)
            
            self.logger.info(f"Learned skill: {name}")
            return name
            
        except Exception as e:
            self.logger.error(f"Error learning skill: {e}")
            raise
    
    async def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(skill_name)
    
    async def practice_skill(
        self,
        skill_name: str,
        context: Dict[str, Any],
        step_executor: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Practice a skill to improve proficiency."""
        try:
            skill = self._skills.get(skill_name)
            if not skill:
                return {
                    'success': False,
                    'error': f'Skill {skill_name} not found'
                }
            
            # Execute the underlying procedure
            procedure_result = await self.execute_procedure(
                skill.procedure_id, context, step_executor
            )
            
            # Update skill proficiency
            skill.update_proficiency(procedure_result.get('success', False))
            
            return {
                'success': procedure_result.get('success', False),
                'skill_name': skill_name,
                'proficiency': skill.proficiency,
                'practice_count': skill.practice_count,
                'procedure_result': procedure_result
            }
            
        except Exception as e:
            self.logger.error(f"Error practicing skill: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def optimize_procedure(self, procedure_id: str) -> bool:
        """Optimize a procedure based on execution history."""
        try:
            procedure = self._procedures.get(procedure_id)
            if not procedure:
                return False
            
            # Get execution history for this procedure
            executions = [
                exec_record for exec_record in self._execution_history
                if exec_record['procedure_id'] == procedure_id
            ]
            
            if len(executions) < 5:
                return False  # Not enough data to optimize
            
            # Analyze failures
            failed_steps = {}
            for execution in executions:
                if not execution['result'].get('success', False):
                    for step_result in execution['result'].get('step_results', []):
                        if not step_result.get('success', False):
                            step_id = step_result.get('step_id')
                            if step_id:
                                failed_steps[step_id] = failed_steps.get(step_id, 0) + 1
            
            # Optimize problematic steps
            optimizations_made = 0
            for step_id, failure_count in failed_steps.items():
                if failure_count > 2:
                    step = next((s for s in procedure.steps if s.id == step_id), None)
                    if step:
                        # Increase timeout
                        step.timeout_seconds = min(step.timeout_seconds * 1.5, 300)
                        # Increase retries
                        step.max_retries = min(step.max_retries + 1, 5)
                        optimizations_made += 1
            
            # Recalculate complexity
            procedure.complexity_score = procedure.calculate_complexity()
            procedure.updated_at = datetime.now()
            
            self.logger.info(f"Optimized procedure {procedure_id}: {optimizations_made} optimizations")
            return True
            
        except Exception as e:
            self.logger.error(f"Error optimizing procedure: {e}")
            return False
    
    async def cleanup_old_procedures(self, cutoff_date: datetime) -> int:
        """Clean up old procedures based on retention policy."""
        try:
            removed_count = 0
            
            # Find old, unused procedures
            old_procedure_ids = [
                pid for pid, procedure in self._procedures.items()
                if (procedure.created_at < cutoff_date and
                    procedure.execution_count == 0 and
                    procedure.success_rate < 0.5)
            ]
            
            # Remove old procedures
            for procedure_id in old_procedure_ids:
                if await self._remove_procedure(procedure_id):
                    removed_count += 1
            
            self.logger.info(f"Cleaned up {removed_count} old procedures")
            return removed_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old procedures: {e}")
            return 0
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get procedural memory statistics."""
        try:
            stats = {
                'total_procedures': len(self._procedures),
                'total_skills': len(self._skills),
                'procedures_by_type': {
                    proc_type.value: len(ids)
                    for proc_type, ids in self._type_index.items()
                },
                'skills_by_category': {
                    category: len(self._category_index.get(category, []))
                    for category in self._category_index.keys()
                },
                'average_success_rate': 0.0,
                'total_executions': len(self._execution_history),
                'last_cleanup': self._last_cleanup.isoformat()
            }
            
            # Calculate average success rate
            if self._procedures:
                stats['average_success_rate'] = sum(
                    proc.success_rate for proc in self._procedures.values()
                ) / len(self._procedures)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _index_procedure(self, procedure: Procedure) -> None:
        """Index a procedure for efficient retrieval."""
        # Name index
        self._name_index[procedure.name.lower()] = procedure.id
        
        # Type index
        if procedure.id not in self._type_index[procedure.procedure_type]:
            self._type_index[procedure.procedure_type].append(procedure.id)
        
        # Tag index
        for tag in procedure.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if procedure.id not in self._tag_index[tag]:
                self._tag_index[tag].append(procedure.id)
    
    async def _unindex_procedure(self, procedure: Procedure) -> None:
        """Remove a procedure from indices."""
        # Name index
        if procedure.name.lower() in self._name_index:
            del self._name_index[procedure.name.lower()]
        
        # Type index
        if procedure.id in self._type_index[procedure.procedure_type]:
            self._type_index[procedure.procedure_type].remove(procedure.id)
        
        # Tag index
        for tag in procedure.tags:
            if tag in self._tag_index and procedure.id in self._tag_index[tag]:
                self._tag_index[tag].remove(procedure.id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]
    
    async def _check_cleanup(self) -> None:
        """Check if cleanup is needed."""
        # Cleanup every hour or if we have too many procedures
        if (datetime.now() - self._last_cleanup > timedelta(hours=1) or
            len(self._procedures) > 1000):
            await self._optimize_all_procedures()
            self._last_cleanup = datetime.now()
    
    async def _check_preconditions(
        self,
        procedure: Procedure,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check if preconditions are satisfied."""
        failed = []
        
        for precondition in procedure.preconditions:
            # Simple condition checking - in practice would be more sophisticated
            condition_type = precondition.get('type', 'equals')
            key = precondition.get('key')
            expected = precondition.get('value')
            
            if key in context:
                actual = context[key]
                
                if condition_type == 'equals' and actual != expected:
                    failed.append(precondition)
                elif condition_type == 'exists' and not actual:
                    failed.append(precondition)
                elif condition_type == 'not_equals' and actual == expected:
                    failed.append(precondition)
        
        return {
            'satisfied': len(failed) == 0,
            'failed': failed
        }
    
    async def _execute_steps(
        self,
        procedure: Procedure,
        context: Dict[str, Any],
        step_executor: Optional[Callable]
    ) -> Dict[str, Any]:
        """Execute procedure steps."""
        step_results = []
        current_steps = [step.id for step in procedure.steps if not step.conditions]
        
        while current_steps:
            step_id = current_steps.pop(0)
            step = next((s for s in procedure.steps if s.id == step_id), None)
            
            if not step:
                continue
            
            step_result = await self._execute_step(
                step, context, step_executor
            )
            
            step_results.append(step_result)
            
            # Determine next steps
            if step_result.get('success', False):
                # Add next steps
                current_steps.extend(step.next_steps)
                
                # Add parallel steps
                current_steps.extend(step.parallel_steps)
            else:
                # Handle failed step
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    current_steps.insert(0, step_id)  # Retry immediately
        
        success = all(result.get('success', False) for result in step_results)
        
        return {
            'success': success,
            'step_results': step_results,
            'steps_executed': len(step_results)
        }
    
    async def _execute_step(
        self,
        step: ProcedureStep,
        context: Dict[str, Any],
        step_executor: Optional[Callable]
    ) -> Dict[str, Any]:
        """Execute a single step."""
        try:
            if step_executor:
                # Use custom step executor
                result = await step_executor(step, context)
            else:
                # Default step execution
                result = await self._default_step_executor(step, context)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing step {step.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'step_id': step.id
            }
    
    async def _default_step_executor(
        self,
        step: ProcedureStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Default step execution logic."""
        # Simulate step execution
        await asyncio.sleep(0.1)  # Simulate work
        
        return {
            'success': True,
            'step_id': step.id,
            'message': f"Executed step: {step.description}"
        }
    
    async def _update_procedure_from_execution(
        self,
        procedure: Procedure,
        execution_result: Dict[str, Any]
    ) -> None:
        """Update procedure based on execution result."""
        success = execution_result.get('success', False)
        
        # Update success rate
        if procedure.execution_count > 0:
            # Weighted average
            old_weight = procedure.execution_count - 1
            new_weight = 1
            total_weight = old_weight + new_weight
            
            procedure.success_rate = (
                (procedure.success_rate * old_weight + (1.0 if success else 0.0) * new_weight) /
                total_weight
            )
        else:
            procedure.success_rate = 1.0 if success else 0.0
        
        # Update status
        if procedure.execution_count >= 10:
            if procedure.success_rate >= 0.9:
                procedure.status = ProcedureStatus.MASTERED
            elif procedure.success_rate >= 0.7:
                procedure.status = ProcedureStatus.PRACTICING
            else:
                procedure.status = ProcedureStatus.LEARNING
        
        procedure.updated_at = datetime.now()
    
    async def _remove_procedure(self, procedure_id: str) -> bool:
        """Remove a procedure from memory."""
        if procedure_id not in self._procedures:
            return False
        
        procedure = self._procedures[procedure_id]
        
        # Remove from indices
        await self._unindex_procedure(procedure)
        
        # Remove from storage
        del self._procedures[procedure_id]
        self._total_procedures -= 1
        
        return True
    
    async def _optimize_all_procedures(self) -> None:
        """Optimize all procedures."""
        for procedure_id in list(self._procedures.keys()):
            await self.optimize_procedure(procedure_id)