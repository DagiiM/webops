"""
Basic AI Agent Example

This example demonstrates how to create and use a basic AI agent
with memory systems, decision making, and task execution.
"""

import asyncio
import json
from datetime import datetime

# Import the core agent components
from agents.core.agent_manager import AgentManager
from agents.core.lifecycle import AgentLifecycle
from agents.memory.episodic import Event, EventType, EmotionType, ImportanceLevel
from agents.memory.semantic import Concept, ConceptType
from agents.memory.procedural import Procedure, ProcedureType, StepType
from agents.decision.personality_influence import PersonalityModel
from agents.skills.deployment import DeploymentSkill
from agents.config.config_manager import ConfigurationManager


async def basic_agent_example():
    """Demonstrate basic agent functionality."""
    print("🤖 Starting Basic AI Agent Example\n")
    
    # 1. Initialize the configuration manager
    print("📋 Initializing Configuration Manager...")
    config_manager = ConfigurationManager()
    await config_manager.initialize()
    
    # 2. Create the agent manager
    print("🔧 Creating Agent Manager...")
    agent_manager = AgentManager(config_manager)
    await agent_manager.initialize()
    
    # 3. Define agent personality
    personality = PersonalityModel(
        openness=0.8,
        conscientiousness=0.9,
        extraversion=0.7,
        agreeableness=0.6,
        neuroticism=0.3
    )
    
    # 4. Create an agent
    print("🧠 Creating AI Agent with personality...")
    agent = await agent_manager.create_agent(
        name="deploy-bot-001",
        personality=personality,
        skills=["deployment", "monitoring", "problem_solving"],
        config={
            "memory_limits": {
                "episodic": 5000,
                "semantic": 25000,
                "procedural": 2500
            }
        }
    )
    
    print(f"✅ Agent created: {agent.name} (ID: {agent.id})")
    
    # 5. Demonstrate episodic memory - storing an experience
    print("\n💭 Demonstrating Episodic Memory...")
    deployment_event = Event(
        event_type=EventType.TASK,
        title="First Successful Deployment",
        description="Successfully deployed a Django application to production",
        actors=[],
        emotions=[EmotionType.EXCITED, EmotionType.SATISFIED],
        importance=ImportanceLevel.SIGNIFICANT,
        duration_seconds=180.0,
        outcomes=["Application deployed successfully", "SSL certificate configured"],
        lessons_learned=["Always backup before deployment", "Verify environment variables"],
        tags=["deployment", "django", "production"]
    )
    
    await agent.episodic_memory.store_event(deployment_event)
    print("📝 Stored first deployment experience in episodic memory")
    
    # 6. Demonstrate semantic memory - storing knowledge
    print("\n🧠 Demonstrating Semantic Memory...")
    django_concept = Concept(
        concept_type=ConceptType.FRAMEWORK,
        name="Django",
        description="High-level Python web framework",
        properties={
            "language": "Python",
            "type": "Web Framework",
            "features": ["ORM", "Admin Panel", "Authentication"],
            "complexity": "Medium",
            "ecosystem": "Django ecosystem"
        },
        relations=[
            ("ORM", "uses"),
            ("Python", "written_in"),
            ("WSGI", "protocol")
        ],
        confidence=0.95
    )
    
    await agent.semantic_memory.store_concept(django_concept)
    print("📚 Stored Django knowledge in semantic memory")
    
    # 7. Demonstrate procedural memory - storing a procedure
    print("\n⚙️ Demonstrating Procedural Memory...")
    django_deployment_proc = Procedure(
        name="Deploy Django Application",
        description="Complete procedure for deploying a Django application",
        procedure_type=ProcedureType.WORKFLOW,
        steps=[
            {
                "id": "check-env",
                "step_type": StepType.ACTION,
                "description": "Check environment requirements",
                "action": "verify_environment",
                "parameters": {"requirements": ["python", "git", "nginx"]}
            },
            {
                "id": "clone-repo",
                "step_type": StepType.ACTION,
                "description": "Clone application repository",
                "action": "git_clone",
                "parameters": {"timeout": 60}
            },
            {
                "id": "setup-env",
                "step_type": StepType.ACTION,
                "description": "Setup Python virtual environment",
                "action": "setup_venv",
                "parameters": {"python_version": "3.11"}
            },
            {
                "id": "install-deps",
                "step_type": StepType.ACTION,
                "description": "Install dependencies",
                "action": "pip_install",
                "parameters": {"requirements_file": "requirements.txt"}
            },
            {
                "id": "run-migrations",
                "step_type": StepType.ACTION,
                "description": "Run database migrations",
                "action": "django_migrate",
                "parameters": {"timeout": 120}
            },
            {
                "id": "collect-static",
                "step_type": StepType.ACTION,
                "description": "Collect static files",
                "action": "django_collectstatic",
                "parameters": {}
            },
            {
                "id": "create-service",
                "step_type": StepType.ACTION,
                "description": "Create systemd service",
                "action": "create_systemd_service",
                "parameters": {}
            },
            {
                "id": "configure-nginx",
                "step_type": StepType.ACTION,
                "description": "Configure Nginx reverse proxy",
                "action": "configure_nginx",
                "parameters": {}
            },
            {
                "id": "start-service",
                "step_type": StepType.ACTION,
                "description": "Start the application service",
                "action": "start_service",
                "parameters": {}
            },
            {
                "id": "health-check",
                "step_type": StepType.VALIDATION,
                "description": "Verify application is running",
                "action": "health_check",
                "parameters": {"timeout": 30}
            }
        ],
        tags=["deployment", "django", "workflow"],
        complexity_score=0.7
    )
    
    await agent.procedural_memory.store_procedure(django_deployment_proc)
    print("📋 Stored Django deployment procedure in procedural memory")
    
    # 8. Execute a task using the stored procedure
    print("\n🚀 Executing Deployment Task...")
    task = {
        "type": "deployment",
        "action": "deploy_django_app",
        "parameters": {
            "app_name": "my-django-app",
            "repository": "https://github.com/user/my-django-app.git",
            "environment": "production"
        }
    }
    
    # Use the deployment skill
    deployment_skill = DeploymentSkill(agent)
    result = await deployment_skill.execute_task(task)
    
    print(f"✅ Deployment Result: {result}")
    
    # 9. Demonstrate decision making
    print("\n🎯 Demonstrating Decision Making...")
    decision_options = [
        {
            "id": "option_1",
            "description": "Deploy with minimal setup",
            "pros": ["Fast", "Simple"],
            "cons": ["Less secure", "No monitoring"],
            "risk_level": 0.6,
            "confidence": 0.4
        },
        {
            "id": "option_2",
            "description": "Deploy with full security and monitoring",
            "pros": ["Secure", "Monitored", "Scalable"],
            "cons": ["Takes longer", "More complex"],
            "risk_level": 0.2,
            "confidence": 0.9
        }
    ]
    
    decision = await agent.decision_maker.make_decision(
        context={
            "urgency": "medium",
            "importance": "high",
            "available_time": 60
        },
        options=decision_options,
        criteria=["security", "reliability", "speed"]
    )
    
    print(f"🎯 Decision: {decision}")
    
    # 10. Search memory systems
    print("\n🔍 Searching Memory Systems...")
    
    # Search episodic memory
    recent_events = await agent.episodic_memory.get_recent_events(limit=5)
    print(f"📅 Recent events: {len(recent_events)}")
    
    # Search semantic memory
    django_knowledge = await agent.semantic_memory.search_concepts("Django", limit=5)
    print(f"🧠 Django knowledge found: {len(django_knowledge)}")
    
    # Search procedural memory
    deployment_procedures = await agent.procedural_memory.search_procedures(
        "deployment", limit=5
    )
    print(f"⚙️ Deployment procedures found: {len(deployment_procedures)}")
    
    # 11. Get system status
    print("\n📊 Getting System Status...")
    status = await agent_manager.get_system_status()
    print(f"💻 System Status:")
    print(f"   Active Agents: {status.get('active_agents', 0)}")
    print(f"   Total Tasks: {status.get('total_tasks', 0)}")
    print(f"   Success Rate: {status.get('success_rate', 0):.2%}")
    
    # 12. Store learning experience
    print("\n🎓 Learning from Experience...")
    learning_result = {
        "task_type": "deployment",
        "success": True,
        "duration": 180.0,
        "outcome": "Application deployed successfully",
        "improvements": ["Could optimize database migrations", "Add health check alerts"]
    }
    
    await agent.learning_memory.record_learning_experience(learning_result)
    
    # 13. Extract patterns
    print("\n📈 Extracting Learning Patterns...")
    patterns = await agent.learning_memory.extract_patterns()
    print(f"🔄 Patterns identified: {len(patterns)}")
    for pattern in patterns:
        print(f"   • {pattern['pattern_type']}: {pattern['pattern']}")
    
    print("\n🎉 Basic AI Agent Example Completed!")
    print("\n📋 Summary:")
    print("   ✅ Created intelligent agent with personality")
    print("   ✅ Stored experiences in episodic memory")
    print("   ✅ Stored knowledge in semantic memory")
    print("   ✅ Stored procedures in procedural memory")
    print("   ✅ Executed deployment task")
    print("   ✅ Made informed decision")
    print("   ✅ Searched memory systems")
    print("   ✅ Learned from experience")


async def advanced_agent_example():
    """Demonstrate advanced agent capabilities."""
    print("\n" + "="*60)
    print("🚀 Advanced AI Agent Example")
    print("="*60)
    
    # This would include more complex scenarios like:
    # - Multi-agent coordination
    # - Complex workflow execution
    # - Advanced learning and adaptation
    # - Real-time monitoring and adjustment
    # - Integration with external systems
    
    print("🔧 Setting up multi-agent coordination...")
    
    # Create multiple agents with different personalities
    agent_manager = AgentManager(ConfigurationManager())
    await agent_manager.initialize()
    
    # Create specialized agents
    agents = []
    specializations = [
        ("deploy-master", {"conscientiousness": 0.95, "openness": 0.6}),
        ("monitor-guardian", {"agreeableness": 0.8, "conscientiousness": 0.9}),
        ("debug-detective", {"openness": 0.9, "neuroticism": 0.7}),
        ("optimize-optimizer", {"conscientiousness": 0.85, "extraversion": 0.6})
    ]
    
    for name, personality_traits in specializations:
        agent = await agent_manager.create_agent(
            name=name,
            personality=PersonalityModel(**personality_traits),
            skills=["deployment", "monitoring", "debugging", "optimization"]
        )
        agents.append(agent)
        print(f"   Created {name}")
    
    # Demonstrate coordinated task execution
    print("\n🎯 Executing coordinated deployment...")
    
    # Create a complex deployment workflow
    workflow_tasks = [
        {"step": "planning", "assign_to": "deploy-master"},
        {"step": "deployment", "assign_to": "deploy-master"},
        {"step": "monitoring", "assign_to": "monitor-guardian"},
        {"step": "debugging", "assign_to": "debug-detective"},
        {"step": "optimization", "assign_to": "optimize-optimizer"}
    ]
    
    for i, task in enumerate(workflow_tasks):
        agent = next(a for a in agents if task["assign_to"] in a.name.lower())
        print(f"   Step {i+1}: {task['step']} → {agent.name}")
        
        # Execute task (simplified for example)
        result = await agent.execute_task({
            "type": "workflow_step",
            "step": task["step"],
            "workflow_id": "complex_deployment_001"
        })
        
        print(f"   ✅ {task['step']} completed by {agent.name}")
    
    print("\n🎉 Advanced Multi-Agent Coordination Completed!")
    print("💡 This demonstrates how specialized agents can work together")
    print("   on complex tasks with different skill sets and personalities.")


if __name__ == "__main__":
    async def main():
        """Main example function."""
        try:
            await basic_agent_example()
            await advanced_agent_example()
        except Exception as e:
            print(f"❌ Error running example: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the examples
    print("🌟 WebOps AI Agent System - Examples")
    print("====================================")
    asyncio.run(main())