"""
Chat Agent with Action Library and LLM Tool Selection

This example demonstrates a complete chat-based AI agent that:
1. Processes natural language input
2. Uses LLM to understand intent and select appropriate actions
3. Executes authenticated WebOps actions
4. Provides intelligent responses and feedback
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid

# Import the action library and LLM components
from actions.action_library import WebOpsActionLibrary, AuthenticationMethod
from actions.webops_actions import DeployApplicationAction, GetDeploymentStatusAction
from llm.tool_selector import LLMToolSelector, UserIntent, ExecutionPlan, ToolSelectionStrategy
from core.agent_manager import AgentManager
from memory.episodic import Event, EventType, EmotionType, ImportanceLevel


class ChatAgent:
    """Chat-based AI agent with action library and LLM tool selection."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the chat agent."""
        self.config = config
        self.logger = logging.getLogger("chat_agent")
        
        # Initialize components
        self.action_library = WebOpsActionLibrary()
        self.tool_selector = LLMToolSelector(config.get('llm_config', {}))
        self.agent_manager = AgentManager(config.get('agent_config', {}))
        
        # Chat state
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.conversation_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Setup components
        self._setup_action_library()
        self.tool_selector.set_action_library(self.action_library)
    
    def _setup_action_library(self):
        """Setup the action library with WebOps actions."""
        # Register WebOps actions
        deploy_action = DeployApplicationAction()
        status_action = GetDeploymentStatusAction()
        
        self.action_library.register_action(deploy_action)
        self.action_library.register_action(status_action)
        
        # Add more actions as needed
        # self.action_library.register_action(RestartApplicationAction())
        # self.action_library.register_action(GetLogsAction())
        # self.action_library.register_action(ScaleApplicationAction())
        
        self.logger.info(f"Initialized action library with {len(self.action_library._actions)} actions")
    
    async def create_chat_session(self, user_id: str, context: Dict[str, Any] = None) -> str:
        """Create a new chat session."""
        session_id = str(uuid.uuid4())
        
        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'created_at': datetime.now(),
            'context': context or {},
            'auth_tokens': {},
            'current_plan': None,
            'last_interaction': datetime.now(),
            'preferences': {}
        }
        
        self.active_sessions[session_id] = session_data
        self.conversation_history[session_id] = []
        
        self.logger.info(f"Created chat session {session_id} for user {user_id}")
        return session_id
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        message_type: str = "user_message"
    ) -> Dict[str, Any]:
        """Process a user message and generate a response."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        session['last_interaction'] = datetime.now()
        
        # Add message to history
        message_entry = {
            'timestamp': datetime.now(),
            'type': message_type,
            'content': message,
            'session_id': session_id
        }
        self.conversation_history[session_id].append(message_entry)
        
        try:
            # Step 1: Analyze intent
            intent = await self.tool_selector.analyze_intent(
                message,
                session['context']
            )
            
            # Step 2: Select appropriate actions
            recommendations = await self.tool_selector.select_tools(
                intent,
                session['context']
            )
            
            # Step 3: Create execution plan
            plan = await self.tool_selector.create_execution_plan(
                intent,
                recommendations
            )
            
            session['current_plan'] = plan
            
            # Step 4: Execute the plan
            execution_results = await self._execute_plan(
                session_id,
                plan,
                session
            )
            
            # Step 5: Generate response
            response = await self._generate_response(
                session_id,
                intent,
                plan,
                execution_results
            )
            
            # Add response to history
            response_entry = {
                'timestamp': datetime.now(),
                'type': 'agent_response',
                'content': response,
                'session_id': session_id
            }
            self.conversation_history[session_id].append(response_entry)
            
            return {
                'success': True,
                'session_id': session_id,
                'intent': intent.to_dict(),
                'plan': plan.to_dict(),
                'response': response,
                'execution_results': execution_results,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            error_response = await self._generate_error_response(session_id, str(e))
            return {
                'success': False,
                'session_id': session_id,
                'error': str(e),
                'response': error_response,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _execute_plan(
        self,
        session_id: str,
        plan: ExecutionPlan,
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the execution plan."""
        results = []
        success_count = 0
        
        # Execute each action in the plan
        for recommendation in plan.recommendations:
            try:
                # Execute the action
                action_result = await self.action_library.execute_action(
                    recommendation.action_id,
                    recommendation.parameters,
                    session['auth_tokens']
                )
                
                results.append({
                    'recommendation': recommendation.to_dict(),
                    'result': action_result,
                    'success': action_result.get('success', False),
                    'timestamp': datetime.now().isoformat()
                })
                
                if action_result.get('success', False):
                    success_count += 1
                
                # Update session context with results
                session['context'][f"{recommendation.action_name}_result"] = action_result
                
            except Exception as e:
                self.logger.error(f"Error executing action {recommendation.action_id}: {e}")
                results.append({
                    'recommendation': recommendation.to_dict(),
                    'result': {
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    },
                    'success': False,
                    'timestamp': datetime.now().isoformat()
                })
        
        return {
            'results': results,
            'success_count': success_count,
            'total_count': len(plan.recommendations),
            'success_rate': success_count / len(plan.recommendations) if plan.recommendations else 0.0
        }
    
    async def _generate_response(
        self,
        session_id: str,
        intent: UserIntent,
        plan: ExecutionPlan,
        execution_results: Dict[str, Any]
    ) -> str:
        """Generate a natural language response."""
        
        # Analyze results
        total_actions = len(plan.recommendations)
        successful_actions = execution_results['success_count']
        
        # Generate response based on intent and results
        if intent.goal.lower().startswith('deploy'):
            if successful_actions > 0:
                response = f"✅ Successfully started deployment for {intent.goal}. "
                response += f"Deployment plan includes {total_actions} steps. "
                response += f"Current status: {successful_actions}/{total_actions} steps completed.\n\n"
                
                # Add specific details from results
                for result in execution_results['results']:
                    if result['result'].get('success'):
                        action_name = result['recommendation']['action_name']
                        response += f"• {action_name}: ✅ Completed\n"
                    else:
                        action_name = result['recommendation']['action_name']
                        response += f"• {action_name}: ❌ {result['result'].get('error', 'Unknown error')}\n"
            else:
                response = f"❌ Unable to deploy application. Please check your input parameters and try again."
        
        elif intent.goal.lower().startswith('status'):
            if successful_actions > 0:
                response = f"📊 Retrieved deployment status as requested. "
                response += f"Found {successful_actions} relevant status updates.\n\n"
                
                # Parse status results
                for result in execution_results['results']:
                    if result['result'].get('success'):
                        data = result['result'].get('data', {})
                        response += f"• {data.get('name', 'Application')}: {data.get('status', 'Unknown')}\n"
            else:
                response = "📊 No deployment status found. Please ensure you have active deployments or specify a deployment ID."
        
        else:
            # Generic response
            if successful_actions > 0:
                response = f"✅ Successfully processed your request: {intent.goal}. "
                response += f"Completed {successful_actions} of {total_actions} actions.\n\n"
                
                for result in execution_results['results']:
                    if result['result'].get('success'):
                        response += f"• {result['recommendation']['action_name']}: ✅\n"
                    else:
                        response += f"• {result['recommendation']['action_name']}: ❌ {result['result'].get('error', 'Error')}\n"
            else:
                response = f"❌ Unable to complete your request: {intent.goal}. "
                response += "Please check the parameters and try again."
        
        # Add helpful next steps
        response += "\n\n💡 Next steps you can try:"
        response += "\n• Ask about deployment status"
        response += "\n• Request to restart an application"
        response += "\n• Check system health"
        response += "\n• Get help with specific commands"
        
        return response
    
    async def _generate_error_response(self, session_id: str, error: str) -> str:
        """Generate an error response."""
        session = self.active_sessions.get(session_id, {})
        
        response = "❌ I'm sorry, I encountered an error while processing your request.\n\n"
        response += f"Error details: {error}\n\n"
        response += "Here are some things you can try:\n"
        response += "• Make sure you're authenticated with the proper credentials\n"
        response += "• Check that your request parameters are valid\n"
        response += "• Try rephrasing your request\n"
        response += "• Ask for help with available commands\n"
        response += "• Contact support if the issue persists"
        
        return response
    
    async def authenticate_session(
        self,
        session_id: str,
        auth_method: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Authenticate a session with WebOps."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        
        # Store authentication credentials
        if auth_method == 'bearer_token':
            session['auth_tokens']['bearer_token'] = credentials.get('token')
        elif auth_method == 'api_key':
            session['auth_tokens']['api_key'] = credentials.get('api_key')
        elif auth_method == 'basic_auth':
            session['auth_tokens']['username'] = credentials.get('username')
            session['auth_tokens']['password'] = credentials.get('password')
        
        # Test authentication
        try:
            # Try to execute a simple status check
            status_action = GetDeploymentStatusAction()
            auth_context = session['auth_tokens']
            
            # Initialize the session
            await status_action.authenticate(auth_context)
            
            return {
                'success': True,
                'message': 'Authentication successful',
                'auth_method': auth_method,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Authentication failed: {str(e)}',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a chat session."""
        if session_id not in self.active_sessions:
            return {}
        
        session = self.active_sessions[session_id]
        history = self.conversation_history.get(session_id, [])
        
        return {
            'session_id': session_id,
            'user_id': session['user_id'],
            'created_at': session['created_at'].isoformat(),
            'last_interaction': session['last_interaction'].isoformat(),
            'message_count': len(history),
            'authenticated': bool(session['auth_tokens']),
            'current_plan': session['current_plan'].to_dict() if session['current_plan'] else None,
            'preferences': session['preferences']
        }
    
    async def end_session(self, session_id: str) -> bool:
        """End a chat session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
        
        self.logger.info(f"Ended chat session {session_id}")
        return True
    
    async def get_available_actions(self) -> List[Dict[str, Any]]:
        """Get list of available actions."""
        actions = []
        for action_id, definition in self.action_library._action_definitions.items():
            actions.append(definition.to_dict())
        return actions
    
    async def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        if session_id not in self.conversation_history:
            return []
        
        history = self.conversation_history[session_id]
        return [
            {
                'timestamp': msg['timestamp'].isoformat(),
                'type': msg['type'],
                'content': msg['content']
            }
            for msg in history[-limit:]
        ]


async def chat_agent_demo():
    """Demonstrate the chat agent functionality."""
    print("🤖 WebOps Chat Agent Demo")
    print("=" * 50)
    
    # Initialize the chat agent
    config = {
        'llm_config': {
            'llm_provider': 'openai',
            'llm_model': 'gpt-4',
            'llm_api_key': 'your-api-key-here',
            'llm_temperature': 0.1
        },
        'agent_config': {
            'max_memory_size': 10000,
            'max_concurrent_agents': 5
        }
    }
    
    chat_agent = ChatAgent(config)
    
    # Create a chat session
    session_id = await chat_agent.create_chat_session(
        user_id="demo_user",
        context={'user_role': 'admin', 'environment': 'production'}
    )
    print(f"✅ Created chat session: {session_id}")
    
    # Authenticate the session
    print("\n🔐 Authenticating session...")
    auth_result = await chat_agent.authenticate_session(
        session_id=session_id,
        auth_method='bearer_token',
        credentials={'token': 'demo-token-12345'}
    )
    print(f"Authentication result: {auth_result['success']}")
    
    # Test various user inputs
    test_inputs = [
        "I want to deploy a new Django application",
        "Check the status of my deployments",
        "Show me what actions are available",
        "Deploy an application called my-app from repository https://github.com/user/my-app.git",
        "Get the status of deployment abc123"
    ]
    
    print("\n💬 Testing chat interactions:")
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n--- Test {i} ---")
        print(f"User: {user_input}")
        
        try:
            response = await chat_agent.process_message(session_id, user_input)
            
            if response['success']:
                print(f"Agent: {response['response']}")
                print(f"Intent: {response['intent']['description']}")
                print(f"Plan: {len(response['plan']['recommendations'])} actions")
            else:
                print(f"Agent: {response['response']}")
                print(f"Error: {response['error']}")
        
        except Exception as e:
            print(f"Error: {str(e)}")
        
        # Small delay between messages
        await asyncio.sleep(0.5)
    
    # Get session info
    print("\n📊 Session Information:")
    session_info = await chat_agent.get_session_info(session_id)
    print(json.dumps(session_info, indent=2))
    
    # Show conversation history
    print("\n📝 Conversation History:")
    history = await chat_agent.get_conversation_history(session_id, limit=10)
    for msg in history:
        print(f"[{msg['timestamp']}] {msg['type']}: {msg['content'][:100]}...")
    
    # Show available actions
    print("\n⚡ Available Actions:")
    actions = await chat_agent.get_available_actions()
    for action in actions:
        print(f"• {action['name']}: {action['description']}")
    
    # End the session
    await chat_agent.end_session(session_id)
    print(f"\n✅ Ended chat session: {session_id}")


async def webops_integration_example():
    """Example of integrating the chat agent with WebOps."""
    print("\n" + "="*50)
    print("🌐 WebOps Integration Example")
    print("="*50)
    
    # This would be used in a real WebOps environment
    config = {
        'llm_config': {
            'llm_provider': 'openai',
            'llm_model': 'gpt-4',
            'llm_api_key': 'your-openai-api-key'
        },
        'webops_config': {
            'api_url': 'http://localhost:8000',
            'api_version': 'v1'
        }
    }
    
    chat_agent = ChatAgent(config)
    
    # Simulate a WebOps administrator using the chat agent
    print("\n🔧 WebOps Administrator Chat Session:")
    
    # Create session for WebOps admin
    session_id = await chat_agent.create_chat_session(
        user_id="webops_admin",
        context={
            'role': 'administrator',
            'permissions': ['deploy', 'manage', 'monitor'],
            'environment': 'production'
        }
    )
    
    # Authenticate with WebOps API
    auth_result = await chat_agent.authenticate_session(
        session_id=session_id,
        auth_method='bearer_token',
        credentials={'token': 'webops-admin-token'}
    )
    
    if auth_result['success']:
        print("✅ Authenticated with WebOps control panel")
        
        # Sample workflow
        admin_requests = [
            "Deploy a new microservice called user-api",
            "What's the health status of all deployments?",
            "Scale up the payment-service to handle more load",
            "Get logs for the authentication-service",
            "Restart the notification service"
        ]
        
        for request in admin_requests:
            print(f"\n👨‍💼 Admin: {request}")
            
            response = await chat_agent.process_message(session_id, request)
            
            if response['success']:
                print(f"🤖 Agent: {response['response']}")
            else:
                print(f"🤖 Agent: {response['response']}")
    else:
        print(f"❌ Authentication failed: {auth_result['message']}")


if __name__ == "__main__":
    async def main():
        """Run the chat agent demonstrations."""
        logging.basicConfig(level=logging.INFO)
        
        try:
            await chat_agent_demo()
            await webops_integration_example()
        except Exception as e:
            print(f"❌ Demo error: {e}")
            import traceback
            traceback.print_exc()
    
    # Run the demos
    print("🌟 WebOps AI Chat Agent System")
    print("=" * 60)
    asyncio.run(main())