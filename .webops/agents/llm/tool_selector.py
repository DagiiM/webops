"""
LLM Tool Selector Engine

Uses an LLM to intelligently select and sequence actions/tools based on
user intent, context, and system state.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime

try:
    import openai
    from openai import AsyncOpenAI
except ImportError:
    openai = None
    AsyncOpenAI = None


class ToolSelectionStrategy(Enum):
    """Strategies for tool selection."""
    
    DIRECT = "direct"  # Single tool execution
    SEQUENTIAL = "sequential"  # Sequential tool execution
    PARALLEL = "parallel"  # Parallel tool execution
    ADAPTIVE = "adaptive"  # Adaptive based on context


@dataclass
class UserIntent:
    """Represents a user intent for tool execution."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    goal: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    priority: float = 0.5  # 0.0 to 1.0
    confidence: float = 0.0  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'description': self.description,
            'goal': self.goal,
            'context': self.context,
            'constraints': self.constraints,
            'preferences': self.preferences,
            'priority': self.priority,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ToolRecommendation:
    """Recommendation for tool usage."""
    
    action_id: str
    action_name: str
    reasoning: str
    confidence: float = 0.0
    priority: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: float = 0.0
    estimated_cost: float = 0.0
    risk_level: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'action_id': self.action_id,
            'action_name': self.action_name,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'priority': self.priority,
            'parameters': self.parameters,
            'dependencies': self.dependencies,
            'estimated_duration': self.estimated_duration,
            'estimated_cost': self.estimated_cost,
            'risk_level': self.risk_level
        }


@dataclass
class ExecutionPlan:
    """Plan for executing tools."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    intent: UserIntent = None
    recommendations: List[ToolRecommendation] = field(default_factory=list)
    strategy: ToolSelectionStrategy = ToolSelectionStrategy.SEQUENTIAL
    estimated_total_duration: float = 0.0
    estimated_total_cost: float = 0.0
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'intent': self.intent.to_dict() if self.intent else None,
            'recommendations': [rec.to_dict() for rec in self.recommendations],
            'strategy': self.strategy.value,
            'estimated_total_duration': self.estimated_total_duration,
            'estimated_total_cost': self.estimated_total_cost,
            'risk_assessment': self.risk_assessment,
            'created_at': self.created_at.isoformat()
        }


class LLMToolSelector:
    """LLM-powered tool selection engine."""
    
    def __init__(self, config):
        """Initialize the tool selector."""
        self.config = config
        self.logger = logging.getLogger("llm_tool_selector")
        
        # LLM Configuration
        self.llm_provider = config.get('llm_provider', 'openai')
        self.llm_model = config.get('llm_model', 'gpt-4')
        self.llm_api_key = config.get('llm_api_key')
        self.llm_base_url = config.get('llm_base_url')
        self.llm_temperature = config.get('llm_temperature', 0.1)
        
        # Initialize LLM client
        self.client = None
        if self.llm_provider == 'openai' and AsyncOpenAI:
            self.client = AsyncOpenAI(
                api_key=self.llm_api_key,
                base_url=self.llm_base_url
            )
        
        # Available actions library
        self.action_library = None
        
        # Selection strategies
        self.selection_strategies = {
            ToolSelectionStrategy.DIRECT: self._direct_selection,
            ToolSelectionStrategy.SEQUENTIAL: self._sequential_selection,
            ToolSelectionStrategy.PARALLEL: self._parallel_selection,
            ToolSelectionStrategy.ADAPTIVE: self._adaptive_selection
        }
        
        # Prompts
        self._intention_prompt = self._build_intention_prompt()
        self._tool_selection_prompt = self._build_tool_selection_prompt()
        self._reasoning_prompt = self._build_reasoning_prompt()
    
    def set_action_library(self, action_library):
        """Set the available actions library."""
        self.action_library = action_library
    
    async def analyze_intent(self, user_input: str, context: Dict[str, Any] = None) -> UserIntent:
        """Analyze user input to extract intent."""
        if not self.client:
            # Fallback to simple keyword-based analysis
            return self._fallback_intent_analysis(user_input, context)
        
        try:
            system_prompt = self._intention_prompt
            user_prompt = f"""
User Input: "{user_input}"

Context: {json.dumps(context or {}, indent=2)}

Available Actions: {json.dumps(self._get_available_actions_summary(), indent=2)}

Please analyze the user input and extract:
1. A clear description of what the user wants to accomplish
2. The main goal or objective
3. Any constraints or requirements
4. User preferences if any
5. Priority level (0.0 to 1.0)
6. Confidence in the analysis (0.0 to 1.0)

Respond in JSON format.
"""
            
            response = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.llm_temperature,
                response_format={"type": "json_object"}
            )
            
            response_data = json.loads(response.choices[0].message.content)
            
            intent = UserIntent(
                description=response_data.get('description', ''),
                goal=response_data.get('goal', ''),
                context=context or {},
                constraints=response_data.get('constraints', []),
                preferences=response_data.get('preferences', {}),
                priority=response_data.get('priority', 0.5),
                confidence=response_data.get('confidence', 0.5)
            )
            
            self.logger.info(f"Analyzed intent: {intent.description}")
            return intent
        
        except Exception as e:
            self.logger.error(f"Error analyzing intent: {e}")
            return self._fallback_intent_analysis(user_input, context)
    
    async def select_tools(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Select appropriate tools for the given intent."""
        if not self.client:
            return self._fallback_tool_selection(intent, context)
        
        try:
            system_prompt = self._tool_selection_prompt
            user_prompt = f"""
Intent: {intent.description}
Goal: {intent.goal}
Context: {json.dumps(context or {}, indent=2)}
Constraints: {json.dumps(intent.constraints, indent=2)}
Preferences: {json.dumps(intent.preferences, indent=2)}

Available Actions: {json.dumps(self._get_detailed_actions(), indent=2)}

Please select the most appropriate actions to accomplish the intent.
Consider:
1. Action relevance to the goal
2. Required parameters and dependencies
3. Estimated duration and cost
4. Risk level
5. Success probability

Provide a ranked list of recommendations with reasoning.
Respond in JSON format with a list of recommendations.
"""
            
            response = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.llm_temperature,
                response_format={"type": "json_object"}
            )
            
            response_data = json.loads(response.choices[0].message.content)
            recommendations_data = response_data.get('recommendations', [])
            
            recommendations = []
            for rec_data in recommendations_data:
                recommendation = ToolRecommendation(
                    action_id=rec_data.get('action_id', ''),
                    action_name=rec_data.get('action_name', ''),
                    reasoning=rec_data.get('reasoning', ''),
                    confidence=rec_data.get('confidence', 0.0),
                    priority=rec_data.get('priority', 0.0),
                    parameters=rec_data.get('parameters', {}),
                    dependencies=rec_data.get('dependencies', []),
                    estimated_duration=rec_data.get('estimated_duration', 0.0),
                    estimated_cost=rec_data.get('estimated_cost', 0.0),
                    risk_level=rec_data.get('risk_level', 0.0)
                )
                recommendations.append(recommendation)
            
            self.logger.info(f"Selected {len(recommendations)} tools for intent: {intent.goal}")
            return recommendations
        
        except Exception as e:
            self.logger.error(f"Error selecting tools: {e}")
            return self._fallback_tool_selection(intent, context)
    
    async def create_execution_plan(
        self,
        intent: UserIntent,
        recommendations: List[ToolRecommendation],
        strategy: ToolSelectionStrategy = ToolSelectionStrategy.SEQUENTIAL
    ) -> ExecutionPlan:
        """Create an execution plan for the recommendations."""
        # Calculate totals
        total_duration = sum(rec.estimated_duration for rec in recommendations)
        total_cost = sum(rec.estimated_cost for rec in recommendations)
        avg_confidence = sum(rec.confidence for rec in recommendations) / len(recommendations) if recommendations else 0.0
        
        # Risk assessment
        max_risk = max((rec.risk_level for rec in recommendations), default=0.0)
        total_risk = sum(rec.risk_level for rec in recommendations)
        
        risk_assessment = {
            'max_risk_level': max_risk,
            'average_risk_level': total_risk / len(recommendations) if recommendations else 0.0,
            'confidence_level': avg_confidence,
            'risk_factors': [rec.reasoning for rec in recommendations if rec.risk_level > 0.5]
        }
        
        plan = ExecutionPlan(
            intent=intent,
            recommendations=recommendations,
            strategy=strategy,
            estimated_total_duration=total_duration,
            estimated_total_cost=total_cost,
            risk_assessment=risk_assessment
        )
        
        self.logger.info(f"Created execution plan with {len(recommendations)} tools")
        return plan
    
    async def refine_plan(
        self,
        plan: ExecutionPlan,
        feedback: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> ExecutionPlan:
        """Refine execution plan based on feedback."""
        if not self.client:
            return self._fallback_plan_refinement(plan, feedback, context)
        
        try:
            system_prompt = """
You are an expert at optimizing execution plans for AI agents.
Given feedback and the current plan, provide an improved version.
"""
            user_prompt = f"""
Current Plan: {json.dumps(plan.to_dict(), indent=2)}
Feedback: {json.dumps(feedback, indent=2)}
Context: {json.dumps(context or {}, indent=2)}

Provide an improved execution plan considering the feedback.
Respond in JSON format.
"""
            
            response = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.llm_temperature,
                response_format={"type": "json_object"}
            )
            
            response_data = json.loads(response.choices[0].message.content)
            
            # Update plan with improvements
            refined_recommendations = []
            for rec_data in response_data.get('recommendations', []):
                refined_rec = ToolRecommendation(
                    action_id=rec_data.get('action_id'),
                    action_name=rec_data.get('action_name'),
                    reasoning=rec_data.get('reasoning'),
                    confidence=rec_data.get('confidence', 0.0),
                    priority=rec_data.get('priority', 0.0),
                    parameters=rec_data.get('parameters', {}),
                    dependencies=rec_data.get('dependencies', []),
                    estimated_duration=rec_data.get('estimated_duration', 0.0),
                    estimated_cost=rec_data.get('estimated_cost', 0.0),
                    risk_level=rec_data.get('risk_level', 0.0)
                )
                refined_recommendations.append(refined_rec)
            
            # Update plan
            plan.recommendations = refined_recommendations
            plan.estimated_total_duration = sum(rec.estimated_duration for rec in refined_recommendations)
            plan.estimated_total_cost = sum(rec.estimated_cost for rec in refined_recommendations)
            
            self.logger.info(f"Refined execution plan with {len(refined_recommendations)} tools")
            return plan
        
        except Exception as e:
            self.logger.error(f"Error refining plan: {e}")
            return self._fallback_plan_refinement(plan, feedback, context)
    
    def _build_intention_prompt(self) -> str:
        """Build the intention analysis prompt."""
        return """
You are an expert at understanding user intentions and extracting structured intent information from natural language.

Your task is to analyze user input and extract:
1. Clear description of what the user wants to accomplish
2. Main goal or objective
3. Context information
4. Any constraints or requirements
5. User preferences
6. Priority level (0.0 to 1.0, where 1.0 is highest priority)
7. Confidence in your analysis (0.0 to 1.0)

Always respond with valid JSON containing these fields:
- description: A clear, concise description
- goal: The main objective
- context: Relevant context information
- constraints: List of constraints
- preferences: User preferences
- priority: Priority level (float 0.0-1.0)
- confidence: Analysis confidence (float 0.0-1.0)

Be precise and structured in your analysis.
"""
    
    def _build_tool_selection_prompt(self) -> str:
        """Build the tool selection prompt."""
        return """
You are an expert at selecting and sequencing tools for AI agents.

Given a user intent and available actions, you must:
1. Select the most appropriate actions to accomplish the goal
2. Consider dependencies between actions
3. Estimate duration, cost, and risk for each action
4. Provide clear reasoning for each selection
5. Rank actions by relevance and priority

Your response should be a JSON object with a "recommendations" array, where each recommendation contains:
- action_id: The unique identifier of the action
- action_name: Human-readable name
- reasoning: Why this action was selected
- confidence: Confidence in the selection (0.0-1.0)
- priority: Priority level (0.0-1.0)
- parameters: Recommended parameters for the action
- dependencies: Array of action_ids this depends on
- estimated_duration: Estimated time in seconds
- estimated_cost: Estimated cost (0.0-1.0)
- risk_level: Risk level (0.0-1.0, where 1.0 is highest risk)

Focus on practical, achievable goals and avoid overly complex sequences.
"""
    
    def _build_reasoning_prompt(self) -> str:
        """Build the reasoning prompt."""
        return """
You are an expert at providing clear reasoning for AI agent decisions.

Explain:
1. Why specific tools/actions were chosen
2. How the execution sequence was determined
3. What alternatives were considered
4. Risk mitigation strategies
5. Success probability assessment

Be transparent about uncertainties and trade-offs.
"""
    
    def _get_available_actions_summary(self) -> List[Dict[str, str]]:
        """Get summary of available actions."""
        if not self.action_library:
            return []
        
        actions = []
        for action_id, definition in self.action_library._action_definitions.items():
            actions.append({
                'id': action_id,
                'name': definition.name,
                'description': definition.description,
                'category': definition.category,
                'type': definition.action_type.value,
                'tags': definition.tags
            })
        
        return actions
    
    def _get_detailed_actions(self) -> List[Dict[str, Any]]:
        """Get detailed information about available actions."""
        if not self.action_library:
            return []
        
        actions = []
        for action_id, definition in self.action_library._action_definitions.items():
            actions.append({
                'id': action_id,
                'name': definition.name,
                'description': definition.description,
                'category': definition.category,
                'type': definition.action_type.value,
                'parameters': [
                    {
                        'name': param.name,
                        'type': param.type,
                        'required': param.required,
                        'description': param.description,
                        'default': param.default
                    } for param in definition.parameters
                ],
                'authentication_method': definition.authentication_method.value,
                'required_permissions': definition.required_permissions,
                'timeout_seconds': definition.timeout_seconds,
                'cost': definition.cost,
                'tags': definition.tags,
                'is_active': definition.is_active
            })
        
        return actions
    
    def _fallback_intent_analysis(self, user_input: str, context: Dict[str, Any] = None) -> UserIntent:
        """Fallback intent analysis using keyword matching."""
        user_lower = user_input.lower()
        
        # Simple keyword-based intent extraction
        if any(word in user_lower for word in ['deploy', 'deploying', 'deployment']):
            description = "User wants to deploy an application"
            goal = "Deploy application to production"
        elif any(word in user_lower for word in ['status', 'monitor', 'check']):
            description = "User wants to check status or monitor something"
            goal = "Get status information"
        elif any(word in user_lower for word in ['restart', 'start', 'stop']):
            description = "User wants to control a service"
            goal = "Manage service lifecycle"
        else:
            description = "User request analysis"
            goal = "Process user request"
        
        return UserIntent(
            description=description,
            goal=goal,
            context=context or {},
            constraints=[],
            preferences={},
            priority=0.5,
            confidence=0.3  # Lower confidence for fallback
        )
    
    def _fallback_tool_selection(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Fallback tool selection based on keywords."""
        recommendations = []
        
        goal_lower = intent.goal.lower()
        
        # Simple rule-based selection
        if 'deploy' in goal_lower:
            recommendations.append(ToolRecommendation(
                action_id='deploy_application',
                action_name='Deploy Application',
                reasoning='Selected based on deployment intent',
                confidence=0.6,
                priority=1.0
            ))
        elif 'status' in goal_lower:
            recommendations.append(ToolRecommendation(
                action_id='get_deployment_status',
                action_name='Get Deployment Status',
                reasoning='Selected based on status checking intent',
                confidence=0.6,
                priority=1.0
            ))
        
        return recommendations
    
    def _fallback_plan_refinement(self, plan: ExecutionPlan, feedback: Dict[str, Any], context: Dict[str, Any] = None) -> ExecutionPlan:
        """Fallback plan refinement."""
        # Simple feedback-based adjustments
        if feedback.get('success') is False:
            # Reduce priority of failing actions
            for rec in plan.recommendations:
                rec.confidence = max(0.0, rec.confidence - 0.2)
                rec.priority = max(0.0, rec.priority - 0.1)
        
        return plan
    
    async def _direct_selection(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Direct tool selection - single best tool."""
        recommendations = await self.select_tools(intent, context)
        return recommendations[:1] if recommendations else []
    
    async def _sequential_selection(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Sequential tool selection - ordered sequence."""
        recommendations = await self.select_tools(intent, context)
        
        # Sort by priority and dependencies
        sorted_recommendations = sorted(
            recommendations,
            key=lambda x: (x.priority, -x.estimated_cost),
            reverse=True
        )
        
        return sorted_recommendations
    
    async def _parallel_selection(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Parallel tool selection - independent tools."""
        recommendations = await self.select_tools(intent, context)
        
        # Filter for independent actions (no dependencies)
        parallel_actions = [
            rec for rec in recommendations 
            if not rec.dependencies or len(rec.dependencies) == 0
        ]
        
        return parallel_actions
    
    async def _adaptive_selection(self, intent: UserIntent, context: Dict[str, Any] = None) -> List[ToolRecommendation]:
        """Adaptive tool selection - context-aware."""
        # Choose strategy based on context
        complexity = len(intent.constraints) + len(intent.preferences)
        
        if complexity <= 2:
            return await self._direct_selection(intent, context)
        elif complexity <= 5:
            return await self._sequential_selection(intent, context)
        else:
            return await self._parallel_selection(intent, context)


# Example usage and integration functions
async def create_chat_agent_with_tools(
    user_input: str,
    action_library,
    context: Dict[str, Any] = None,
    config: Dict[str, Any] = None
) -> Tuple[UserIntent, ExecutionPlan]:
    """Create a complete chat agent workflow with tool selection."""
    
    # Initialize tool selector
    selector = LLMToolSelector(config or {})
    selector.set_action_library(action_library)
    
    # Analyze intent
    intent = await selector.analyze_intent(user_input, context)
    
    # Select tools
    recommendations = await selector.select_tools(intent, context)
    
    # Create execution plan
    plan = await selector.create_execution_plan(intent, recommendations)
    
    return intent, plan