# AI Agent Tool Usage Guide

**Version**: 1.0.0
**Last Updated**: 2025-11-02

## Overview

AI agents in the WebOps system use tools through a structured **Skill Execution Framework**. Tools are wrapped as skills that agents can learn, execute, and improve over time. This approach provides:

- **Standardized Interface**: All tools follow the same skill contract
- **Personality Integration**: Tool usage is influenced by agent personality
- **Learning Capability**: Agents improve tool usage through experience
- **Safety Mechanisms**: Tool execution includes validation and risk assessment

## Tool Architecture

### 1. Skill-Based Tool Wrapping

All external tools are wrapped as skills:

```python
class ToolSkill(Skill):
    """Base class for tool-based skills."""
    
    def __init__(self, tool_name: str, tool_config: Dict[str, Any]):
        super().__init__(SkillMetadata(
            name=tool_name,
            description=f"Tool skill for {tool_name}",
            category=SkillCategory.TECHNICAL,
            parameters=tool_config.get('parameters', {}),
            examples=tool_config.get('examples', [])
        ))
        self.tool = self._initialize_tool(tool_name, tool_config)
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Apply personality influence to tool usage
        influenced_params = self._apply_personality_influence(parameters, context)
        
        # Execute tool with safety checks
        result = await self._execute_tool_safely(influenced_params, context)
        
        # Learn from execution
        await self._learn_from_execution(parameters, result, context)
        
        return result
```

### 2. Tool Categories

Tools are organized by category:

#### Technical Tools
- **Deployment Tools**: Deploy applications, services, infrastructure
- **Monitoring Tools**: Check system health, metrics, logs
- **Security Tools**: Scan vulnerabilities, manage permissions
- **Backup Tools**: Create and restore backups

#### Communication Tools
- **Notification Tools**: Send alerts, emails, messages
- **Reporting Tools**: Generate reports, summaries
- **Collaboration Tools**: Coordinate with other agents

#### Analytical Tools
- **Data Analysis**: Process metrics, identify patterns
- **Performance Analysis**: Analyze system performance
- **Log Analysis**: Parse and analyze log files

### 3. Tool Discovery and Registration

Agents discover and register tools dynamically:

```python
# Tool registration
await agent.skills.register_tool(
    tool_name="deploy_service",
    tool_class=DeployServiceTool,
    metadata={
        "description": "Deploy a service to specified environment",
        "category": "deployment",
        "parameters": {
            "service_name": {
                "type": "string",
                "required": True,
                "description": "Name of service to deploy"
            },
            "environment": {
                "type": "string",
                "required": True,
                "description": "Target environment (dev/staging/prod)"
            }
        },
        "examples": [
            {
                "description": "Deploy web service to production",
                "command": "deploy_service --name=web-app --env=production"
            }
        ]
    }
)
```

## Tool Execution Process

### 1. Decision Making

When an agent needs to use a tool:

1. **Analyze Situation**: Understand what needs to be done
2. **Identify Available Tools**: Check registered tools
3. **Select Appropriate Tool**: Based on personality and context
4. **Plan Execution**: Create execution plan with parameters

### 2. Personality Influence

Personality affects tool selection and usage:

```python
# Guardian personality - prefers safe, proven tools
if agent.personality.conscientiousness > 0.7:
    # Prefer tools with high success rate
    selected_tool = self._select_reliable_tool(available_tools)

# Innovator personality - tries new, creative approaches
if agent.personality.openness > 0.7:
    # Prefer newer or experimental tools
    selected_tool = self._select_innovative_tool(available_tools)
```

### 3. Safety Validation

Before tool execution:

```python
# Validate parameters
validation = await tool.validate_parameters(parameters)
if not validation['valid']:
    return {
        'success': False,
        'error': validation['error'],
        'suggestions': validation['suggestions']
    }

# Check permissions
if not await self._check_permissions(tool, context):
    return {
        'success': False,
        'error': 'Insufficient permissions for tool usage'
    }

# Assess risk
risk = await self.risk_assessment.assess_tool_risk(tool, parameters)
if risk.level > agent.max_acceptable_risk:
    return {
        'success': False,
        'error': f"Tool risk ({risk.level}) exceeds acceptable level"
    }
```

### 4. Execution with Monitoring

During tool execution:

```python
# Execute with timeout and monitoring
try:
    result = await asyncio.wait_for(
        tool.execute(parameters),
        timeout=tool.max_execution_time
    )
    
    # Log execution
    await self._log_tool_execution(tool, parameters, result)
    
    return result
    
except asyncio.TimeoutError:
    return {
        'success': False,
        'error': 'Tool execution timeout',
        'partial_results': await tool.get_partial_results()
    }
```

### 5. Learning from Results

After tool execution:

```python
# Update tool proficiency
await agent.skills.update_proficiency(
    tool_name=tool.name,
    success=result['success'],
    execution_time=result['execution_time']
)

# Learn patterns
if result['success']:
    await agent.memory.store_pattern({
        'type': 'tool_success_pattern',
        'tool': tool.name,
        'parameters': parameters,
        'context': context,
        'outcome': result
    })
else:
    await agent.memory.store_pattern({
        'type': 'tool_failure_pattern',
        'tool': tool.name,
        'parameters': parameters,
        'context': context,
        'error': result.get('error'),
        'outcome': result
    })
```

## Example Tool Implementations

### 1. Deployment Tool

```python
class DeployServiceTool(ToolSkill):
    """Tool for deploying services."""
    
    def __init__(self):
        super().__init__(
            tool_name="deploy_service",
            tool_config={
                "description": "Deploy a service to specified environment",
                "parameters": {
                    "service_name": {
                        "type": "string",
                        "required": True,
                        "description": "Name of service to deploy"
                    },
                    "environment": {
                        "type": "string",
                        "required": True,
                        "description": "Target environment"
                    },
                    "version": {
                        "type": "string",
                        "required": False,
                        "description": "Service version to deploy"
                    }
                },
                "examples": [
                    {
                        "description": "Deploy web service",
                        "command": "deploy_service --name=web-app --env=production --version=v1.2.0"
                    }
                ]
            }
        )
    
    async def _execute_tool_safely(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute deployment with safety checks."""
        
        # Pre-deployment checks
        if not await self._validate_deployment_parameters(parameters):
            return {
                'success': False,
                'error': 'Invalid deployment parameters'
            }
        
        # Create deployment plan
        plan = await self._create_deployment_plan(parameters)
        
        # Execute deployment steps
        results = []
        for step in plan.steps:
            step_result = await self._execute_deployment_step(step)
            results.append(step_result)
            
            # Check if step failed
            if not step_result['success']:
                # Attempt rollback
                await self._rollback_deployment(plan.steps[:plan.steps.index(step)])
                return {
                    'success': False,
                    'error': f"Deployment failed at step: {step.name}",
                    'step_results': results
                }
        
        # Post-deployment verification
        verification = await self._verify_deployment(parameters)
        
        return {
            'success': verification['success'],
            'deployment_id': plan.deployment_id,
            'step_results': results,
            'verification': verification,
            'execution_time': plan.total_time
        }
```

### 2. Monitoring Tool

```python
class SystemMonitorTool(ToolSkill):
    """Tool for system monitoring."""
    
    async def _execute_tool_safely(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute monitoring with personality influence."""
        
        # Get monitoring targets
        targets = parameters.get('targets', ['cpu', 'memory', 'disk'])
        
        # Apply personality to monitoring approach
        if self.agent.personality.conscientiousness > 0.7:
            # Thorough monitoring - check everything
            targets = ['cpu', 'memory', 'disk', 'network', 'processes', 'logs']
        elif self.agent.personality.openness > 0.7:
            # Creative monitoring - try new metrics
            targets.extend(['custom_metrics', 'performance_indicators'])
        
        # Collect metrics
        metrics = {}
        for target in targets:
            metrics[target] = await self._collect_metric(target, parameters)
        
        # Analyze metrics
        analysis = await self._analyze_metrics(metrics, context)
        
        # Generate alerts if needed
        if analysis['alerts']:
            await self._send_alerts(analysis['alerts'])
        
        return {
            'success': True,
            'metrics': metrics,
            'analysis': analysis,
            'monitoring_period': parameters.get('period', 300),
            'targets_monitored': targets
        }
```

### 3. Communication Tool

```python
class NotificationTool(ToolSkill):
    """Tool for sending notifications."""
    
    async def _execute_tool_safely(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Send notifications with personality style."""
        
        # Get notification details
        message = parameters.get('message', '')
        recipients = parameters.get('recipients', [])
        urgency = parameters.get('urgency', 'normal')
        
        # Apply personality to message
        styled_message = self.agent.personality.affect_communication(message)
        
        # Choose communication method based on personality
        if self.agent.personality.extraversion > 0.7:
            # Social - prefer direct communication
            method = 'direct_message'
        elif self.agent.personality.agreeableness > 0.7:
            # Cooperative - prefer team notification
            method = 'team_broadcast'
        else:
            # Default - use standard notification
            method = 'standard_notification'
        
        # Send notification
        results = []
        for recipient in recipients:
            result = await self._send_notification(
                recipient=recipient,
                message=styled_message,
                method=method,
                urgency=urgency
            )
            results.append(result)
        
        return {
            'success': all(r['success'] for r in results),
            'message': styled_message,
            'method': method,
            'recipients': recipients,
            'results': results
        }
```

## Tool Learning and Adaptation

### 1. Proficiency Tracking

Agents track tool proficiency over time:

```python
class ToolProficiency:
    """Tracks agent's proficiency with specific tools."""
    
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.usage_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.avg_execution_time = 0.0
        self.last_used = None
        self.proficiency_score = 0.5  # 0.0 to 1.0
    
    def update_usage(self, success: bool, execution_time: float) -> None:
        """Update proficiency based on usage."""
        self.usage_count += 1
        self.last_used = datetime.now()
        
        if success:
            self.success_count += 1
            self.proficiency_score = min(1.0, self.proficiency_score + 0.01)
        else:
            self.failure_count += 1
            self.proficiency_score = max(0.0, self.proficiency_score - 0.005)
        
        # Update average execution time
        self.avg_execution_time = (
            (self.avg_execution_time * (self.usage_count - 1) + execution_time) / 
            self.usage_count
        )
```

### 2. Pattern Recognition

Agents learn patterns in tool usage:

```python
async def _learn_tool_patterns(self, tool_name: str, usage_history: List[Dict]) -> None:
    """Learn patterns from tool usage history."""
    
    # Identify successful patterns
    successful_patterns = self._extract_successful_patterns(usage_history)
    
    # Identify failure patterns
    failure_patterns = self._extract_failure_patterns(usage_history)
    
    # Store patterns in semantic memory
    for pattern in successful_patterns:
        await self.agent.memory.store_fact({
            'content': f"Successful {tool_name} pattern: {pattern['description']}",
            'category': 'tool_pattern',
            'confidence': pattern['confidence'],
            'tags': [tool_name, 'success', 'pattern']
        })
    
    for pattern in failure_patterns:
        await self.agent.memory.store_fact({
            'content': f"Failed {tool_name} pattern: {pattern['description']}",
            'category': 'tool_pattern',
            'confidence': pattern['confidence'],
            'tags': [tool_name, 'failure', 'pattern']
        })
```

### 3. Adaptive Tool Selection

Agents improve tool selection based on experience:

```python
async def _select_best_tool(self, task: Dict[str, Any], available_tools: List[str]) -> str:
    """Select best tool based on experience and personality."""
    
    tool_scores = {}
    
    for tool_name in available_tools:
        # Get tool proficiency
        proficiency = await self.agent.skills.get_proficiency(tool_name)
        
        # Get success patterns for this tool/task combination
        patterns = await self.agent.memory.search_facts({
            'query': f"{tool_name} {task['type']}",
            'category': 'tool_pattern'
        })
        
        # Calculate base score
        score = proficiency.proficiency if proficiency else 0.5
        
        # Adjust based on patterns
        for pattern in patterns:
            if pattern['tags'].includes('success'):
                score += 0.1 * pattern['confidence']
            elif pattern['tags'].includes('failure'):
                score -= 0.1 * pattern['confidence']
        
        # Apply personality influence
        personality_modifier = self._get_personality_tool_modifier(tool_name)
        score *= personality_modifier
        
        tool_scores[tool_name] = score
    
    # Select tool with highest score
    return max(tool_scores, key=tool_scores.get)
```

## Tool Safety and Security

### 1. Permission System

Tools require specific permissions:

```python
class ToolPermissions:
    """Manages tool access permissions."""
    
    PERMISSIONS = {
        'deploy': ['deployment_write', 'service_manage'],
        'monitor': ['system_read', 'metrics_access'],
        'security_scan': ['security_read', 'vulnerability_scan'],
        'backup': ['data_read', 'storage_write'],
        'notify': ['communication_send', 'alert_create']
    }
    
    @classmethod
    def check_permissions(cls, tool_name: str, user_permissions: List[str]) -> bool:
        """Check if user has required permissions."""
        required = cls.PERMISSIONS.get(tool_name, [])
        return all(perm in user_permissions for perm in required)
```

### 2. Risk Assessment

Tools are assessed for risk before execution:

```python
class ToolRiskAssessment:
    """Assesses and manages tool execution risks."""
    
    RISK_LEVELS = {
        'deploy': 'medium',
        'delete': 'high',
        'modify_config': 'medium',
        'monitor': 'low',
        'backup': 'low',
        'security_scan': 'medium'
    }
    
    @classmethod
    def assess_tool_risk(cls, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk of tool execution."""
        base_risk = cls.RISK_LEVELS.get(tool_name, 'medium')
        
        # Adjust risk based on parameters
        if 'environment' in parameters and parameters['environment'] == 'production':
            # Higher risk in production
            risk_levels = {'low': 0.2, 'medium': 0.5, 'high': 0.8}
            base_risk = cls._increase_risk_level(base_risk, 0.3)
        
        # Check for dangerous parameters
        dangerous_params = ['force', 'skip_checks', 'ignore_errors']
        if any(param in str(parameters) for param in dangerous_params):
            base_risk = cls._increase_risk_level(base_risk, 0.4)
        
        return {
            'risk_level': base_risk,
            'risk_factors': cls._identify_risk_factors(tool_name, parameters),
            'mitigation_strategies': cls._get_mitigation_strategies(base_risk)
        }
```

## Best Practices for Tool Usage

### 1. Tool Design
- Use consistent parameter naming
- Provide clear descriptions and examples
- Include proper error handling
- Implement timeout and retry logic
- Log all operations for audit

### 2. Agent Configuration
- Set appropriate risk tolerance based on agent personality
- Configure tool preferences based on past experience
- Implement tool-specific learning rates
- Monitor tool performance and adapt

### 3. Safety First
- Always validate parameters before execution
- Check permissions before tool access
- Implement rollback mechanisms for dangerous operations
- Use circuit breakers for failing tools
- Log all tool executions for audit

### 4. Continuous Learning
- Track tool success and failure patterns
- Update tool selection based on outcomes
- Share successful patterns with other agents
- Regularly re-evaluate tool preferences

## Conclusion

The WebOps AI Agent system provides a comprehensive framework for tool usage that:

1. **Wraps all tools as skills** with consistent interfaces
2. **Applies personality influence** to tool selection and usage
3. **Learns from experience** to improve tool effectiveness
4. **Ensures safety** through validation and risk assessment
5. **Adapts over time** based on patterns and outcomes

This approach creates agents that not only use tools effectively but also learn and adapt their tool usage strategies based on their personality and experience, making them more reliable and efficient over time.