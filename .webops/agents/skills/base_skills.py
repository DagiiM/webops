"""
Base Skills Module

Core skill implementations for the AI agent system.
"""

import asyncio
import logging
import json
import time
import re
import hashlib
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from enum import Enum
import uuid


class SkillType(Enum):
    """Types of skills available to the agent."""
    
    COMMUNICATION = "communication"
    PROBLEM_SOLVING = "problem_solving"
    LEARNING = "learning"
    MONITORING = "monitoring"
    SECURITY = "security"
    AUTOMATION = "automation"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    SOCIAL = "social"
    TECHNICAL = "technical"


class SkillLevel(Enum):
    """Proficiency levels for skills."""
    
    NOVICE = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5
    MASTER = 6


class SkillStatus(Enum):
    """Status of skill execution."""
    
    IDLE = "idle"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SkillContext:
    """Context information for skill execution."""
    
    skill_id: str
    skill_type: SkillType
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            'skill_id': self.skill_id,
            'skill_type': self.skill_type.value,
            'parameters': self.parameters,
            'environment': self.environment,
            'preferences': self.preferences,
            'constraints': self.constraints,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class SkillResult:
    """Result of skill execution."""
    
    skill_id: str
    success: bool
    status: SkillStatus
    output: Any = None
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'skill_id': self.skill_id,
            'success': self.success,
            'status': self.status.value,
            'output': self.output,
            'error_message': self.error_message,
            'execution_time_seconds': self.execution_time_seconds,
            'confidence_score': self.confidence_score,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class BaseSkill(ABC):
    """Base class for all skills."""
    
    def __init__(
        self,
        skill_id: str,
        name: str,
        description: str,
        skill_type: SkillType,
        level: SkillLevel = SkillLevel.NOVICE,
        dependencies: List[str] = None,
        parameters: Dict[str, Any] = None
    ):
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.skill_type = skill_type
        self.level = level
        self.dependencies = dependencies or []
        self.parameters = parameters or {}
        self.logger = logging.getLogger(f"skill.{skill_id}")
        
        # Execution tracking
        self.execution_count = 0
        self.success_count = 0
        self.total_execution_time = 0.0
        self.last_executed = None
        self.average_execution_time = 0.0
        
        # Status
        self.status = SkillStatus.IDLE
        self.current_execution_id = None
    
    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute the skill with the given context."""
        pass
    
    async def validate(self, context: SkillContext) -> bool:
        """Validate that the skill can be executed with the given context."""
        return True
    
    async def cleanup(self) -> None:
        """Cleanup any resources used by the skill."""
        pass
    
    async def get_skill_info(self) -> Dict[str, Any]:
        """Get information about the skill."""
        return {
            'skill_id': self.skill_id,
            'name': self.name,
            'description': self.description,
            'skill_type': self.skill_type.value,
            'level': self.level.value,
            'dependencies': self.dependencies,
            'parameters': self.parameters,
            'execution_count': self.execution_count,
            'success_rate': self.success_count / max(1, self.execution_count),
            'average_execution_time': self.average_execution_time,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None
        }
    
    async def _track_execution(self, start_time: float, success: bool, execution_id: str) -> None:
        """Track execution statistics."""
        execution_time = time.time() - start_time
        
        self.execution_count += 1
        if success:
            self.success_count += 1
        
        self.total_execution_time += execution_time
        self.average_execution_time = self.total_execution_time / self.execution_count
        self.last_executed = datetime.now()
    
    def _create_execution_id(self) -> str:
        """Create a unique execution ID."""
        timestamp = str(time.time())
        return hashlib.md5(f"{self.skill_id}_{timestamp}".encode()).hexdigest()[:8]


class CommunicationSkill(BaseSkill):
    """Base communication skill."""
    
    def __init__(self):
        super().__init__(
            skill_id="communication_base",
            name="Communication Skill",
            description="Base communication skill for natural language processing",
            skill_type=SkillType.COMMUNICATION
        )
        
        self.message_history = []
        self.active_conversations = {}
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute communication skill."""
        start_time = time.time()
        execution_id = self._create_execution_id()
        self.current_execution_id = execution_id
        
        try:
            self.status = SkillStatus.EXECUTING
            
            # Process different types of communication tasks
            task_type = context.parameters.get('task_type', 'general')
            
            if task_type == 'text_analysis':
                result = await self._analyze_text(context)
            elif task_type == 'sentiment_analysis':
                result = await self._analyze_sentiment(context)
            elif task_type == 'intent_recognition':
                result = await self._recognize_intent(context)
            elif task_type == 'response_generation':
                result = await self._generate_response(context)
            elif task_type == 'conversation_management':
                result = await self._manage_conversation(context)
            else:
                result = await self._general_communication(context)
            
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=True,
                status=SkillStatus.COMPLETED,
                output=result,
                confidence_score=0.8
            )
            
            await self._track_execution(start_time, True, execution_id)
            return skill_result
            
        except Exception as e:
            self.logger.error(f"Communication skill execution failed: {e}")
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=False,
                status=SkillStatus.FAILED,
                error_message=str(e),
                confidence_score=0.0
            )
            await self._track_execution(start_time, False, execution_id)
            return skill_result
        
        finally:
            self.status = SkillStatus.IDLE
            self.current_execution_id = None
    
    async def _analyze_text(self, context: SkillContext) -> Dict[str, Any]:
        """Analyze text content."""
        text = context.parameters.get('text', '')
        
        # Simple text analysis (in real implementation, would use NLP libraries)
        words = text.split()
        sentences = text.split('.')
        
        analysis = {
            'word_count': len(words),
            'character_count': len(text),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'average_word_length': sum(len(word) for word in words) / max(1, len(words)),
            'contains_numbers': bool(re.search(r'\d', text)),
            'contains_punctuation': bool(re.search(r'[^\w\s]', text)),
            'language_guess': 'english'  # Simplified
        }
        
        return analysis
    
    async def _analyze_sentiment(self, context: SkillContext) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        text = context.parameters.get('text', '').lower()
        
        # Simple sentiment analysis using keyword matching
        positive_words = ['good', 'great', 'excellent', 'wonderful', 'amazing', 'love', 'like']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'horrible', 'worst']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            sentiment = 'positive'
            confidence = min(0.9, 0.6 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment = 'negative'
            confidence = min(0.9, 0.6 + (negative_count - positive_count) * 0.1)
        else:
            sentiment = 'neutral'
            confidence = 0.5
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'positive_score': positive_count,
            'negative_score': negative_count
        }
    
    async def _recognize_intent(self, context: SkillContext) -> Dict[str, Any]:
        """Recognize intent from user input."""
        text = context.parameters.get('text', '').lower()
        
        # Simple intent recognition using patterns
        intents = {
            'greeting': ['hello', 'hi', 'hey', 'greetings'],
            'question': ['what', 'how', 'why', 'when', 'where', 'who'],
            'request': ['please', 'can you', 'could you', 'would you'],
            'goodbye': ['bye', 'goodbye', 'see you', 'farewell'],
            'help': ['help', 'assist', 'support', 'guidance']
        }
        
        recognized_intents = []
        for intent, keywords in intents.items():
            if any(keyword in text for keyword in keywords):
                recognized_intents.append(intent)
        
        return {
            'intents': recognized_intents,
            'primary_intent': recognized_intents[0] if recognized_intents else 'unknown',
            'confidence': 0.7 if recognized_intents else 0.1
        }
    
    async def _generate_response(self, context: SkillContext) -> Dict[str, Any]:
        """Generate a response to user input."""
        text = context.parameters.get('text', '')
        intent = context.parameters.get('intent', 'general')
        
        # Simple response generation based on intent
        responses = {
            'greeting': 'Hello! How can I help you today?',
            'question': 'That\'s an interesting question. Let me think about that.',
            'request': 'I\'ll be happy to help you with that request.',
            'goodbye': 'Goodbye! Have a great day!',
            'help': 'I\'m here to help. What would you like assistance with?',
            'general': 'I understand. How can I assist you further?'
        }
        
        response = responses.get(intent, responses['general'])
        
        return {
            'response': response,
            'intent': intent,
            'confidence': 0.8
        }
    
    async def _manage_conversation(self, context: SkillContext) -> Dict[str, Any]:
        """Manage conversation state and flow."""
        conversation_id = context.parameters.get('conversation_id')
        action = context.parameters.get('action', 'get_state')
        
        if action == 'start':
            conversation_id = str(uuid.uuid4())
            self.active_conversations[conversation_id] = {
                'start_time': datetime.now(),
                'message_count': 0,
                'context': {}
            }
        
        elif action == 'add_message':
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id]['message_count'] += 1
                self.active_conversations[conversation_id]['last_message_time'] = datetime.now()
        
        elif action == 'get_state':
            conversation_id = context.parameters.get('conversation_id')
        
        return {
            'conversation_id': conversation_id,
            'action': action,
            'active_conversations': len(self.active_conversations),
            'total_messages': sum(conv['message_count'] for conv in self.active_conversations.values())
        }
    
    async def _general_communication(self, context: SkillContext) -> Dict[str, Any]:
        """General communication processing."""
        return {
            'processed': True,
            'timestamp': datetime.now().isoformat(),
            'skill_used': self.skill_id
        }


class ProblemSolvingSkill(BaseSkill):
    """Problem-solving and analytical skill."""
    
    def __init__(self):
        super().__init__(
            skill_id="problem_solving",
            name="Problem Solving Skill",
            description="Analyzes problems and generates solutions",
            skill_type=SkillType.PROBLEM_SOLVING,
            level=SkillLevel.INTERMEDIATE
        )
        
        self.problem_history = []
        self.solution_templates = {}
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute problem-solving skill."""
        start_time = time.time()
        execution_id = self._create_execution_id()
        self.current_execution_id = execution_id
        
        try:
            self.status = SkillStatus.EXECUTING
            
            problem_description = context.parameters.get('problem', '')
            problem_type = context.parameters.get('type', 'general')
            
            if problem_type == 'analysis':
                result = await self._analyze_problem(context)
            elif problem_type == 'decomposition':
                result = await self._decompose_problem(context)
            elif problem_type == 'solution_generation':
                result = await self._generate_solutions(context)
            elif problem_type == 'evaluation':
                result = await self._evaluate_solutions(context)
            else:
                result = await self._general_problem_solving(context)
            
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=True,
                status=SkillStatus.COMPLETED,
                output=result,
                confidence_score=0.75
            )
            
            await self._track_execution(start_time, True, execution_id)
            return skill_result
            
        except Exception as e:
            self.logger.error(f"Problem solving execution failed: {e}")
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=False,
                status=SkillStatus.FAILED,
                error_message=str(e),
                confidence_score=0.0
            )
            await self._track_execution(start_time, False, execution_id)
            return skill_result
        
        finally:
            self.status = SkillStatus.IDLE
            self.current_execution_id = None
    
    async def _analyze_problem(self, context: SkillContext) -> Dict[str, Any]:
        """Analyze a problem to understand its nature."""
        problem = context.parameters.get('problem', '')
        
        # Simple problem analysis
        analysis = {
            'problem_statement': problem,
            'complexity_score': min(1.0, len(problem) / 100.0),
            'domain': self._identify_domain(problem),
            'constraints_identified': self._extract_constraints(problem),
            'objectives_identified': self._extract_objectives(problem),
            'stakeholders': self._identify_stakeholders(problem)
        }
        
        return analysis
    
    async def _decompose_problem(self, context: SkillContext) -> Dict[str, Any]:
        """Decompose a complex problem into sub-problems."""
        problem = context.parameters.get('problem', '')
        
        # Simple decomposition based on keywords and structure
        sentences = [s.strip() for s in problem.split('.') if s.strip()]
        sub_problems = []
        
        for i, sentence in enumerate(sentences):
            if len(sentence) > 20:  # Only substantial sentences
                sub_problems.append({
                    'id': f'sub_problem_{i+1}',
                    'description': sentence,
                    'priority': 'medium',
                    'estimated_effort': len(sentence) / 10
                })
        
        return {
            'original_problem': problem,
            'sub_problems': sub_problems,
            'total_sub_problems': len(sub_problems),
            'decomposition_method': 'sentence_based'
        }
    
    async def _generate_solutions(self, context: SkillContext) -> Dict[str, Any]:
        """Generate potential solutions to a problem."""
        problem = context.parameters.get('problem', '')
        solutions_count = context.parameters.get('solutions_count', 3)
        
        # Simple solution generation based on problem patterns
        solutions = []
        
        for i in range(solutions_count):
            solution = {
                'id': f'solution_{i+1}',
                'description': f'Solution approach {i+1} for: {problem[:50]}...',
                'approach': self._determine_approach(problem, i),
                'pros': ['Addresses the core issue', 'Feasible implementation'],
                'cons': ['May have limitations', 'Requires resources'],
                'feasibility_score': 0.7 - (i * 0.1),
                'estimated_effectiveness': 0.8 - (i * 0.15)
            }
            solutions.append(solution)
        
        return {
            'problem': problem,
            'solutions': solutions,
            'generation_method': 'template_based'
        }
    
    async def _evaluate_solutions(self, context: SkillContext) -> Dict[str, Any]:
        """Evaluate and rank solutions."""
        solutions = context.parameters.get('solutions', [])
        
        evaluations = []
        for solution in solutions:
            evaluation = {
                'solution_id': solution.get('id'),
                'overall_score': solution.get('feasibility_score', 0.5) * solution.get('estimated_effectiveness', 0.5),
                'feasibility_rating': self._rate_feasibility(solution),
                'effectiveness_rating': self._rate_effectiveness(solution),
                'risk_assessment': self._assess_risk(solution),
                'recommendation': 'recommended' if solution.get('feasibility_score', 0) > 0.6 else 'consider_alternatives'
            }
            evaluations.append(evaluation)
        
        # Sort by overall score
        evaluations.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return {
            'evaluations': evaluations,
            'top_recommendation': evaluations[0] if evaluations else None,
            'evaluation_criteria': ['feasibility', 'effectiveness', 'risk']
        }
    
    async def _general_problem_solving(self, context: SkillContext) -> Dict[str, Any]:
        """General problem-solving process."""
        return {
            'process_steps': ['analyze', 'decompose', 'generate_solutions', 'evaluate'],
            'methodology': 'systematic_analysis',
            'confidence': 0.7
        }
    
    def _identify_domain(self, problem: str) -> str:
        """Identify the domain of a problem."""
        technical_keywords = ['code', 'software', 'algorithm', 'system', 'database']
        business_keywords = ['strategy', 'process', 'workflow', 'efficiency', 'optimization']
        
        problem_lower = problem.lower()
        
        if any(keyword in problem_lower for keyword in technical_keywords):
            return 'technical'
        elif any(keyword in problem_lower for keyword in business_keywords):
            return 'business'
        else:
            return 'general'
    
    def _extract_constraints(self, problem: str) -> List[str]:
        """Extract constraints from problem description."""
        constraint_keywords = ['must', 'cannot', 'should not', 'limited to', 'restricted']
        constraints = []
        
        problem_lower = problem.lower()
        for keyword in constraint_keywords:
            if keyword in problem_lower:
                constraints.append(f'Constraint related to: {keyword}')
        
        return constraints
    
    def _extract_objectives(self, problem: str) -> List[str]:
        """Extract objectives from problem description."""
        objective_keywords = ['goal', 'objective', 'aim', 'target', 'want to']
        objectives = []
        
        problem_lower = problem.lower()
        for keyword in objective_keywords:
            if keyword in problem_lower:
                objectives.append(f'Objective related to: {keyword}')
        
        return objectives
    
    def _identify_stakeholders(self, problem: str) -> List[str]:
        """Identify stakeholders in a problem."""
        stakeholder_keywords = ['user', 'customer', 'team', 'management', 'stakeholder']
        stakeholders = []
        
        problem_lower = problem.lower()
        for keyword in stakeholder_keywords:
            if keyword in problem_lower:
                stakeholders.append(f'Stakeholder: {keyword}')
        
        return stakeholders if stakeholders else ['Primary user']
    
    def _determine_approach(self, problem: str, index: int) -> str:
        """Determine approach for solution."""
        approaches = ['analytical', 'creative', 'systematic', 'incremental', 'innovative']
        return approaches[index % len(approaches)]
    
    def _rate_feasibility(self, solution: Dict[str, Any]) -> str:
        """Rate solution feasibility."""
        score = solution.get('feasibility_score', 0.5)
        if score > 0.7:
            return 'high'
        elif score > 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _rate_effectiveness(self, solution: Dict[str, Any]) -> str:
        """Rate solution effectiveness."""
        score = solution.get('estimated_effectiveness', 0.5)
        if score > 0.7:
            return 'high'
        elif score > 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _assess_risk(self, solution: Dict[str, Any]) -> str:
        """Assess risk level of solution."""
        # Simple risk assessment based on feasibility
        feasibility = solution.get('feasibility_score', 0.5)
        if feasibility > 0.7:
            return 'low'
        elif feasibility > 0.4:
            return 'medium'
        else:
            return 'high'


class MonitoringSkill(BaseSkill):
    """System monitoring and health check skill."""
    
    def __init__(self):
        super().__init__(
            skill_id="monitoring",
            name="Monitoring Skill",
            description="Monitors system health and performance",
            skill_type=SkillType.MONITORING,
            level=SkillLevel.INTERMEDIATE
        )
        
        self.monitoring_targets = {}
        self.health_history = []
        self.alert_thresholds = {}
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute monitoring skill."""
        start_time = time.time()
        execution_id = self._create_execution_id()
        self.current_execution_id = execution_id
        
        try:
            self.status = SkillStatus.EXECUTING
            
            monitoring_type = context.parameters.get('type', 'health_check')
            
            if monitoring_type == 'health_check':
                result = await self._perform_health_check(context)
            elif monitoring_type == 'performance_monitor':
                result = await self._monitor_performance(context)
            elif monitoring_type == 'alert_check':
                result = await self._check_alerts(context)
            elif monitoring_type == 'metric_collection':
                result = await self._collect_metrics(context)
            else:
                result = await self._general_monitoring(context)
            
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=True,
                status=SkillStatus.COMPLETED,
                output=result,
                confidence_score=0.9
            )
            
            await self._track_execution(start_time, True, execution_id)
            return skill_result
            
        except Exception as e:
            self.logger.error(f"Monitoring execution failed: {e}")
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=False,
                status=SkillStatus.FAILED,
                error_message=str(e),
                confidence_score=0.0
            )
            await self._track_execution(start_time, False, execution_id)
            return skill_result
        
        finally:
            self.status = SkillStatus.IDLE
            self.current_execution_id = None
    
    async def _perform_health_check(self, context: SkillContext) -> Dict[str, Any]:
        """Perform system health check."""
        targets = context.parameters.get('targets', ['system'])
        
        health_status = {}
        for target in targets:
            health_status[target] = await self._check_target_health(target)
        
        overall_health = self._calculate_overall_health(health_status)
        
        health_check_result = {
            'timestamp': datetime.now().isoformat(),
            'targets_checked': targets,
            'overall_status': overall_health['status'],
            'overall_score': overall_health['score'],
            'individual_status': health_status,
            'recommendations': self._generate_health_recommendations(health_status)
        }
        
        # Store in history
        self.health_history.append(health_check_result)
        
        return health_check_result
    
    async def _monitor_performance(self, context: SkillContext) -> Dict[str, Any]:
        """Monitor system performance."""
        metrics = context.parameters.get('metrics', ['cpu', 'memory', 'disk'])
        
        performance_data = {}
        for metric in metrics:
            performance_data[metric] = await self._get_performance_metric(metric)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'performance_data': performance_data,
            'performance_score': self._calculate_performance_score(performance_data)
        }
    
    async def _check_alerts(self, context: SkillContext) -> Dict[str, Any]:
        """Check for alerts and warnings."""
        active_alerts = []
        
        # Simulate alert checking
        alert_conditions = [
            {'condition': 'high_cpu', 'value': 0.85, 'severity': 'warning'},
            {'condition': 'low_memory', 'value': 0.1, 'severity': 'critical'},
            {'condition': 'disk_space', 'value': 0.9, 'severity': 'warning'}
        ]
        
        for condition in alert_conditions:
            if await self._check_alert_condition(condition):
                active_alerts.append({
                    'condition': condition['condition'],
                    'severity': condition['severity'],
                    'timestamp': datetime.now().isoformat(),
                    'message': f"Alert triggered: {condition['condition']}"
                })
        
        return {
            'timestamp': datetime.now().isoformat(),
            'active_alerts': active_alerts,
            'total_alerts': len(active_alerts),
            'critical_alerts': len([a for a in active_alerts if a['severity'] == 'critical'])
        }
    
    async def _collect_metrics(self, context: SkillContext) -> Dict[str, Any]:
        """Collect system metrics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics_collected': ['cpu_usage', 'memory_usage', 'disk_usage', 'network_activity'],
            'collection_method': 'simulated'
        }
    
    async def _general_monitoring(self, context: SkillContext) -> Dict[str, Any]:
        """General monitoring operation."""
        return {
            'status': 'monitoring_active',
            'last_check': datetime.now().isoformat(),
            'monitoring_duration': 'continuous'
        }
    
    async def _check_target_health(self, target: str) -> Dict[str, Any]:
        """Check health of a specific target."""
        # Simulate health check
        import random
        health_score = random.uniform(0.7, 1.0)
        
        status = 'healthy' if health_score > 0.8 else 'warning' if health_score > 0.6 else 'critical'
        
        return {
            'target': target,
            'status': status,
            'health_score': health_score,
            'last_check': datetime.now().isoformat(),
            'checks_performed': ['connectivity', 'response_time', 'error_rate']
        }
    
    def _calculate_overall_health(self, health_status: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall system health."""
        if not health_status:
            return {'status': 'unknown', 'score': 0.0}
        
        total_score = sum(target['health_score'] for target in health_status.values())
        average_score = total_score / len(health_status)
        
        if average_score > 0.8:
            status = 'healthy'
        elif average_score > 0.6:
            status = 'warning'
        else:
            status = 'critical'
        
        return {'status': status, 'score': average_score}
    
    def _generate_health_recommendations(self, health_status: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on health status."""
        recommendations = []
        
        for target, status in health_status.items():
            if status['health_score'] < 0.7:
                recommendations.append(f"Investigate {target} performance issues")
            if status['status'] == 'critical':
                recommendations.append(f"Immediate attention required for {target}")
        
        if not recommendations:
            recommendations.append("System is operating normally")
        
        return recommendations
    
    async def _get_performance_metric(self, metric: str) -> Dict[str, Any]:
        """Get performance metric value."""
        # Simulate metric collection
        import random
        
        metric_ranges = {
            'cpu': (0.1, 0.9),
            'memory': (0.2, 0.85),
            'disk': (0.3, 0.95),
            'network': (0.0, 1.0)
        }
        
        min_val, max_val = metric_ranges.get(metric, (0.0, 1.0))
        value = random.uniform(min_val, max_val)
        
        return {
            'metric': metric,
            'value': value,
            'unit': 'percentage' if metric != 'network' else 'connections',
            'timestamp': datetime.now().isoformat(),
            'status': 'normal' if value < 0.8 else 'high' if value < 0.95 else 'critical'
        }
    
    def _calculate_performance_score(self, performance_data: Dict[str, Any]) -> float:
        """Calculate overall performance score."""
        if not performance_data:
            return 0.0
        
        total_score = 0.0
        for metric_data in performance_data.values():
            value = metric_data['value']
            # Invert score so lower values are better
            score = 1.0 - value
            total_score += score
        
        return total_score / len(performance_data)
    
    async def _check_alert_condition(self, condition: Dict[str, Any]) -> bool:
        """Check if an alert condition is met."""
        # Simulate alert condition checking
        import random
        return random.random() < 0.1  # 10% chance of alert


class LearningSkill(BaseSkill):
    """Learning and adaptation skill."""
    
    def __init__(self):
        super().__init__(
            skill_id="learning",
            name="Learning Skill",
            description="Learns from experiences and adapts behavior",
            skill_type=SkillType.LEARNING,
            level=SkillLevel.BEGINNER
        )
        
        self.learning_history = []
        self.patterns_learned = {}
        self.adaptation_rules = {}
    
    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute learning skill."""
        start_time = time.time()
        execution_id = self._create_execution_id()
        self.current_execution_id = execution_id
        
        try:
            self.status = SkillStatus.EXECUTING
            
            learning_type = context.parameters.get('type', 'pattern_recognition')
            
            if learning_type == 'pattern_recognition':
                result = await self._recognize_patterns(context)
            elif learning_type == 'experience_learning':
                result = await self._learn_from_experience(context)
            elif learning_type == 'adaptation':
                result = await self._adapt_behavior(context)
            elif learning_type == 'knowledge_update':
                result = await self._update_knowledge(context)
            else:
                result = await self._general_learning(context)
            
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=True,
                status=SkillStatus.COMPLETED,
                output=result,
                confidence_score=0.7
            )
            
            await self._track_execution(start_time, True, execution_id)
            return skill_result
            
        except Exception as e:
            self.logger.error(f"Learning execution failed: {e}")
            skill_result = SkillResult(
                skill_id=self.skill_id,
                success=False,
                status=SkillStatus.FAILED,
                error_message=str(e),
                confidence_score=0.0
            )
            await self._track_execution(start_time, False, execution_id)
            return skill_result
        
        finally:
            self.status = SkillStatus.IDLE
            self.current_execution_id = None
    
    async def _recognize_patterns(self, context: SkillContext) -> Dict[str, Any]:
        """Recognize patterns in data or behavior."""
        data = context.parameters.get('data', [])
        pattern_type = context.parameters.get('pattern_type', 'sequence')
        
        if not data:
            return {'error': 'No data provided for pattern recognition'}
        
        patterns = []
        
        if pattern_type == 'sequence':
            patterns = await self._find_sequence_patterns(data)
        elif pattern_type == 'frequency':
            patterns = await self._find_frequency_patterns(data)
        elif pattern_type == 'temporal':
            patterns = await self._find_temporal_patterns(data)
        else:
            patterns = await self._find_general_patterns(data)
        
        # Store learned patterns
        for pattern in patterns:
            pattern_id = hashlib.md5(str(pattern).encode()).hexdigest()[:8]
            self.patterns_learned[pattern_id] = {
                'pattern': pattern,
                'confidence': pattern.get('confidence', 0.5),
                'learned_at': datetime.now().isoformat(),
                'usage_count': 0
            }
        
        return {
            'pattern_type': pattern_type,
            'patterns_found': patterns,
            'total_patterns': len(patterns),
            'confidence_average': sum(p.get('confidence', 0.5) for p in patterns) / max(1, len(patterns))
        }
    
    async def _learn_from_experience(self, context: SkillContext) -> Dict[str, Any]:
        """Learn from previous experiences."""
        experience = context.parameters.get('experience', {})
        outcome = context.parameters.get('outcome', 'unknown')
        
        learning_entry = {
            'experience': experience,
            'outcome': outcome,
            'timestamp': datetime.now().isoformat(),
            'learned_at': datetime.now().isoformat()
        }
        
        self.learning_history.append(learning_entry)
        
        # Generate insights from experience
        insights = await self._extract_insights(experience, outcome)
        
        return {
            'experience_processed': True,
            'outcome': outcome,
            'insights_generated': insights,
            'total_experiences': len(self.learning_history)
        }
    
    async def _adapt_behavior(self, context: SkillContext) -> Dict[str, Any]:
        """Adapt behavior based on learning."""
        current_behavior = context.parameters.get('behavior', {})
        feedback = context.parameters.get('feedback', {})
        
        adaptation_suggestions = await self._generate_adaptations(current_behavior, feedback)
        
        # Update adaptation rules
        for suggestion in adaptation_suggestions:
            rule_id = suggestion.get('rule_id')
            if rule_id:
                self.adaptation_rules[rule_id] = suggestion
        
        return {
            'adaptation_suggestions': adaptation_suggestions,
            'total_adaptation_rules': len(self.adaptation_rules)
        }
    
    async def _update_knowledge(self, context: SkillContext) -> Dict[str, Any]:
        """Update knowledge base."""
        knowledge_update = context.parameters.get('knowledge', {})
        source = context.parameters.get('source', 'unknown')
        
        return {
            'knowledge_updated': True,
            'source': source,
            'update_type': 'incremental',
            'knowledge_items_processed': len(knowledge_update)
        }
    
    async def _general_learning(self, context: SkillContext) -> Dict[str, Any]:
        """General learning operation."""
        return {
            'learning_type': 'general',
            'knowledge_base_size': len(self.patterns_learned),
            'experiences_learned': len(self.learning_history),
            'adaptation_rules_active': len(self.adaptation_rules)
        }
    
    async def _find_sequence_patterns(self, data: List[Any]) -> List[Dict[str, Any]]:
        """Find sequential patterns in data."""
        patterns = []
        
        if len(data) < 2:
            return patterns
        
        # Simple pattern detection
        for i in range(len(data) - 1):
            if data[i] == data[i + 1]:
                patterns.append({
                    'type': 'repetition',
                    'pattern': [data[i], data[i + 1]],
                    'position': i,
                    'confidence': 0.8,
                    'frequency': 1
                })
        
        return patterns
    
    async def _find_frequency_patterns(self, data: List[Any]) -> List[Dict[str, Any]]:
        """Find frequency-based patterns."""
        from collections import Counter
        
        frequency_count = Counter(data)
        total_items = len(data)
        
        patterns = []
        for item, count in frequency_count.items():
            if count > 1:  # Only patterns that occur more than once
                patterns.append({
                    'type': 'frequency',
                    'pattern': item,
                    'count': count,
                    'frequency': count / total_items,
                    'confidence': min(1.0, count / total_items * 2)
                })
        
        return patterns
    
    async def _find_temporal_patterns(self, data: List[Any]) -> List[Dict[str, Any]]:
        """Find temporal patterns in data."""
        # Simplified temporal pattern detection
        return [{
            'type': 'temporal',
            'pattern': 'time_based_trend',
            'confidence': 0.6,
            'description': 'Data shows temporal patterns'
        }]
    
    async def _find_general_patterns(self, data: List[Any]) -> List[Dict[str, Any]]:
        """Find general patterns in data."""
        # Simplified general pattern detection
        return [{
            'type': 'general',
            'pattern': 'data_structure',
            'confidence': 0.5,
            'description': f'Data contains {len(data)} items'
        }]
    
    async def _extract_insights(self, experience: Dict[str, Any], outcome: str) -> List[str]:
        """Extract insights from experience."""
        insights = []
        
        # Simple insight extraction
        if outcome == 'success':
            insights.append('Successful approach identified')
            insights.append('Positive outcome pattern detected')
        elif outcome == 'failure':
            insights.append('Failed approach identified')
            insights.append('Risk factors noted')
        else:
            insights.append('Outcome recorded for future analysis')
        
        return insights
    
    async def _generate_adaptations(self, behavior: Dict[str, Any], feedback: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate behavior adaptations."""
        suggestions = []
        
        feedback_score = feedback.get('score', 0.5)
        
        if feedback_score < 0.6:
            suggestions.append({
                'rule_id': 'improve_approach',
                'type': 'behavior_modification',
                'suggestion': 'Consider alternative approach',
                'priority': 'high',
                'confidence': 0.7
            })
        elif feedback_score > 0.8:
            suggestions.append({
                'rule_id': 'reinforce_success',
                'type': 'behavior_reinforcement',
                'suggestion': 'Continue current approach',
                'priority': 'medium',
                'confidence': 0.8
            })
        
        return suggestions


class SkillManager:
    """Manages and coordinates multiple skills."""
    
    def __init__(self):
        """Initialize the skill manager."""
        self.logger = logging.getLogger("skill_manager")
        
        # Skill registry
        self.skills: Dict[str, BaseSkill] = {}
        
        # Skill execution tracking
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
        # Skill dependencies
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Skill performance metrics
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}
    
    async def register_skill(self, skill: BaseSkill) -> bool:
        """Register a skill with the manager."""
        try:
            self.skills[skill.skill_id] = skill
            self.dependency_graph[skill.skill_id] = skill.dependencies
            
            # Initialize performance metrics
            self.performance_metrics[skill.skill_id] = {
                'total_executions': 0,
                'successful_executions': 0,
                'average_execution_time': 0.0,
                'success_rate': 0.0
            }
            
            self.logger.info(f"Registered skill: {skill.name} ({skill.skill_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error registering skill {skill.skill_id}: {e}")
            return False
    
    async def execute_skill(
        self,
        skill_id: str,
        parameters: Dict[str, Any] = None,
        skill_type: SkillType = None,
        context_override: Dict[str, Any] = None
    ) -> SkillResult:
        """Execute a skill."""
        try:
            skill = self.skills.get(skill_id)
            if not skill:
                return SkillResult(
                    skill_id=skill_id,
                    success=False,
                    status=SkillStatus.FAILED,
                    error_message=f"Skill {skill_id} not found"
                )
            
            # Create context
            context = SkillContext(
                skill_id=skill_id,
                skill_type=skill.skill_type,
                parameters=parameters or {},
                metadata=context_override or {}
            )
            
            # Validate skill execution
            if not await skill.validate(context):
                return SkillResult(
                    skill_id=skill_id,
                    success=False,
                    status=SkillStatus.FAILED,
                    error_message="Skill validation failed"
                )
            
            # Check dependencies
            dependency_check = await self._check_dependencies(skill_id)
            if not dependency_check['satisfied']:
                return SkillResult(
                    skill_id=skill_id,
                    success=False,
                    status=SkillStatus.FAILED,
                    error_message=f"Dependencies not satisfied: {dependency_check['missing']}"
                )
            
            # Execute skill
            result = await skill.execute(context)
            
            # Update performance metrics
            await self._update_performance_metrics(skill_id, result)
            
            # Record execution
            self._record_execution(skill_id, context, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing skill {skill_id}: {e}")
            return SkillResult(
                skill_id=skill_id,
                success=False,
                status=SkillStatus.FAILED,
                error_message=str(e)
            )
    
    async def execute_skill_sequence(
        self,
        skill_sequence: List[Dict[str, Any]],
        parallel: bool = False
    ) -> List[SkillResult]:
        """Execute a sequence of skills."""
        results = []
        
        if parallel:
            # Execute skills in parallel
            tasks = []
            for skill_config in skill_sequence:
                skill_id = skill_config['skill_id']
                parameters = skill_config.get('parameters', {})
                task = asyncio.create_task(self.execute_skill(skill_id, parameters))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to failed results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    results[i] = SkillResult(
                        skill_id=skill_sequence[i]['skill_id'],
                        success=False,
                        status=SkillStatus.FAILED,
                        error_message=str(result)
                    )
        
        else:
            # Execute skills sequentially
            for skill_config in skill_sequence:
                skill_id = skill_config['skill_id']
                parameters = skill_config.get('parameters', {})
                
                result = await self.execute_skill(skill_id, parameters)
                results.append(result)
                
                # Stop on first failure if configured
                if not result.success and skill_config.get('stop_on_failure', True):
                    break
        
        return results
    
    async def get_skill_info(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific skill."""
        skill = self.skills.get(skill_id)
        if not skill:
            return None
        
        skill_info = await skill.get_skill_info()
        skill_info.update({
            'performance_metrics': self.performance_metrics.get(skill_id, {}),
            'dependencies': self.dependency_graph.get(skill_id, [])
        })
        
        return skill_info
    
    async def list_skills(self, skill_type: Optional[SkillType] = None) -> List[Dict[str, Any]]:
        """List all registered skills."""
        skills_info = []
        
        for skill_id, skill in self.skills.items():
            if skill_type is None or skill.skill_type == skill_type:
                skill_info = await self.get_skill_info(skill_id)
                skills_info.append(skill_info)
        
        return skills_info
    
    async def get_skill_performance(self) -> Dict[str, Any]:
        """Get performance metrics for all skills."""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_skills': len(self.skills),
            'skill_performance': self.performance_metrics,
            'execution_history_size': len(self.execution_history)
        }
    
    async def cleanup_skills(self) -> None:
        """Cleanup all registered skills."""
        for skill in self.skills.values():
            await skill.cleanup()
        
        self.skills.clear()
        self.performance_metrics.clear()
        self.dependency_graph.clear()
        self.active_executions.clear()
        self.execution_history.clear()
        
        self.logger.info("All skills cleaned up")
    
    async def _check_dependencies(self, skill_id: str) -> Dict[str, Any]:
        """Check if skill dependencies are satisfied."""
        dependencies = self.dependency_graph.get(skill_id, [])
        missing = []
        
        for dependency in dependencies:
            if dependency not in self.skills:
                missing.append(dependency)
        
        return {
            'satisfied': len(missing) == 0,
            'missing': missing,
            'dependencies_count': len(dependencies)
        }
    
    async def _update_performance_metrics(self, skill_id: str, result: SkillResult) -> None:
        """Update performance metrics for a skill."""
        if skill_id not in self.performance_metrics:
            return
        
        metrics = self.performance_metrics[skill_id]
        metrics['total_executions'] += 1
        
        if result.success:
            metrics['successful_executions'] += 1
        
        # Update average execution time
        current_avg = metrics['average_execution_time']
        total_executions = metrics['total_executions']
        new_execution_time = result.execution_time_seconds
        
        metrics['average_execution_time'] = (
            (current_avg * (total_executions - 1) + new_execution_time) / total_executions
        )
        
        # Update success rate
        metrics['success_rate'] = (
            metrics['successful_executions'] / metrics['total_executions']
        )
    
    def _record_execution(
        self,
        skill_id: str,
        context: SkillContext,
        result: SkillResult
    ) -> None:
        """Record skill execution in history."""
        execution_record = {
            'skill_id': skill_id,
            'timestamp': datetime.now().isoformat(),
            'context': context.to_dict(),
            'result': result.to_dict()
        }
        
        self.execution_history.append(execution_record)
        
        # Keep history manageable
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]


# Initialize default skills
async def initialize_default_skills(manager: SkillManager) -> None:
    """Initialize the default skill set."""
    
    # Communication skill
    communication_skill = CommunicationSkill()
    await manager.register_skill(communication_skill)
    
    # Problem-solving skill
    problem_solving_skill = ProblemSolvingSkill()
    await manager.register_skill(problem_solving_skill)
    
    # Monitoring skill
    monitoring_skill = MonitoringSkill()
    await manager.register_skill(monitoring_skill)
    
    # Learning skill
    learning_skill = LearningSkill()
    await manager.register_skill(learning_skill)
    
    logger = logging.getLogger("skill_manager")
    logger.info("Default skills initialized")