"""
Agent Bridge - Connects automation workflows with the AI agent system.

This module provides a bridge between the Django automation system and
the independent AI agent system located in .webops/agents/.
"""

import logging
import asyncio
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentBridge:
    """
    Bridge between automation workflows and AI agents.

    This class provides synchronous wrappers around the async agent system,
    making it easy to integrate agents into workflow execution.
    """

    def __init__(self):
        """Initialize the agent bridge."""
        self.agent_system_path = self._get_agent_system_path()
        self._ensure_agent_system_accessible()

    def _get_agent_system_path(self) -> str:
        """Get path to the agent system."""
        # Assuming webops root is 2 levels up from control-panel/apps/automation
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(base_path, '.webops', 'agents')

    def _ensure_agent_system_accessible(self):
        """Ensure the agent system can be imported."""
        if self.agent_system_path not in sys.path:
            sys.path.insert(0, self.agent_system_path)

        # Verify agent system is accessible
        if not os.path.exists(self.agent_system_path):
            logger.warning(f"Agent system not found at {self.agent_system_path}")

    def execute_task(
        self,
        agent_id: str,
        task_description: str,
        task_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a task using an AI agent.

        Args:
            agent_id: ID of the agent to use
            task_description: Description of the task
            task_params: Additional parameters

        Returns:
            Task execution result
        """
        try:
            # Import agent system components
            from core.agent import WebOpsAgent
            from actions.webops_actions import execute_task

            # Get or create agent instance
            agent = self._get_agent(agent_id)

            if not agent:
                return {
                    'status': 'error',
                    'error': f'Agent {agent_id} not found or could not be created'
                }

            # Execute task asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self._async_execute_task(agent, task_description, task_params)
                )
                return result
            finally:
                loop.close()

        except ImportError as e:
            logger.error(f"Failed to import agent system: {e}")
            # Return mock result for development/testing
            return self._mock_task_execution(task_description, task_params)

        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'task': task_description
            }

    async def _async_execute_task(
        self,
        agent,
        task_description: str,
        task_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Async wrapper for agent task execution."""
        # Submit task to agent
        task_id = await agent.submit_task({
            'description': task_description,
            'params': task_params,
            'source': 'workflow'
        })

        # Wait for completion
        result = await agent.get_task_result(task_id, timeout=300)

        return {
            'status': 'completed',
            'result': result,
            'task_id': task_id,
            'agent_id': agent.name
        }

    def process_query(
        self,
        agent_id: str,
        query: str,
        context: Dict[str, Any],
        expected_format: str
    ) -> Dict[str, Any]:
        """
        Process a query using an AI agent.

        Args:
            agent_id: ID of the agent
            query: Query text
            context: Additional context
            expected_format: Expected response format

        Returns:
            Query response
        """
        try:
            from core.agent import WebOpsAgent
            from communication.natural_language import process_query

            agent = self._get_agent(agent_id)

            if not agent:
                return {
                    'answer': None,
                    'confidence': 0.0,
                    'error': f'Agent {agent_id} not found'
                }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                response = loop.run_until_complete(
                    self._async_process_query(agent, query, context, expected_format)
                )
                return response
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_query_response(query, context)

        except Exception as e:
            logger.error(f"Query processing failed: {e}", exc_info=True)
            return {
                'answer': None,
                'confidence': 0.0,
                'error': str(e)
            }

    async def _async_process_query(
        self,
        agent,
        query: str,
        context: Dict[str, Any],
        expected_format: str
    ) -> Dict[str, Any]:
        """Async wrapper for agent query processing."""
        response = await agent.communication.process_query(
            query=query,
            context=context,
            format=expected_format
        )

        return {
            'answer': response.get('answer'),
            'confidence': response.get('confidence', 1.0),
            'reasoning': response.get('reasoning'),
            'format': expected_format
        }

    def store_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store information in agent memory."""
        try:
            from core.agent import WebOpsAgent

            agent = self._get_agent(agent_id)

            if not agent:
                return {'stored': False, 'error': f'Agent {agent_id} not found'}

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                memory_id = loop.run_until_complete(
                    self._async_store_memory(agent, memory_type, content)
                )
                return {
                    'memory_id': memory_id,
                    'stored': True
                }
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_memory_storage(memory_type, content)

        except Exception as e:
            logger.error(f"Memory storage failed: {e}", exc_info=True)
            return {'stored': False, 'error': str(e)}

    async def _async_store_memory(
        self,
        agent,
        memory_type: str,
        content: Dict[str, Any]
    ) -> str:
        """Async wrapper for memory storage."""
        memory_id = await agent.memory.store(
            memory_type=memory_type,
            content=content,
            timestamp=datetime.now()
        )
        return memory_id

    def retrieve_memory(
        self,
        agent_id: str,
        memory_type: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve information from agent memory."""
        try:
            from core.agent import WebOpsAgent

            agent = self._get_agent(agent_id)

            if not agent:
                return {'data': None, 'count': 0, 'error': f'Agent {agent_id} not found'}

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                data = loop.run_until_complete(
                    self._async_retrieve_memory(agent, memory_type, criteria)
                )
                return {
                    'data': data,
                    'count': len(data) if isinstance(data, list) else 1
                }
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_memory_retrieval(memory_type, criteria)

        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}", exc_info=True)
            return {'data': None, 'count': 0, 'error': str(e)}

    async def _async_retrieve_memory(
        self,
        agent,
        memory_type: str,
        criteria: Dict[str, Any]
    ) -> Any:
        """Async wrapper for memory retrieval."""
        data = await agent.memory.retrieve(
            memory_type=memory_type,
            criteria=criteria
        )
        return data

    def search_memory(
        self,
        agent_id: str,
        memory_type: str,
        query: str,
        filters: Dict[str, Any],
        limit: int
    ) -> Dict[str, Any]:
        """Search agent memory."""
        try:
            from core.agent import WebOpsAgent

            agent = self._get_agent(agent_id)

            if not agent:
                return {'results': [], 'count': 0, 'error': f'Agent {agent_id} not found'}

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(
                    self._async_search_memory(agent, memory_type, query, filters, limit)
                )
                return {
                    'results': results,
                    'count': len(results)
                }
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_memory_search(memory_type, query, limit)

        except Exception as e:
            logger.error(f"Memory search failed: {e}", exc_info=True)
            return {'results': [], 'count': 0, 'error': str(e)}

    async def _async_search_memory(
        self,
        agent,
        memory_type: str,
        query: str,
        filters: Dict[str, Any],
        limit: int
    ) -> List[Any]:
        """Async wrapper for memory search."""
        results = await agent.memory.search(
            memory_type=memory_type,
            query=query,
            filters=filters,
            limit=limit
        )
        return results

    def make_decision(
        self,
        agent_id: str,
        context: Dict[str, Any],
        options: List[str],
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Request a decision from an AI agent."""
        try:
            from core.agent import WebOpsAgent

            agent = self._get_agent(agent_id)

            if not agent:
                return {
                    'selected_option': None,
                    'confidence': 0.0,
                    'error': f'Agent {agent_id} not found'
                }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                decision = loop.run_until_complete(
                    self._async_make_decision(agent, context, options, criteria)
                )
                return decision
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_decision(options, criteria)

        except Exception as e:
            logger.error(f"Decision making failed: {e}", exc_info=True)
            return {
                'selected_option': None,
                'confidence': 0.0,
                'error': str(e)
            }

    async def _async_make_decision(
        self,
        agent,
        context: Dict[str, Any],
        options: List[str],
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Async wrapper for decision making."""
        decision = await agent.decision_engine.make_decision(
            context=context,
            options=options,
            criteria=criteria
        )

        return {
            'selected_option': decision['option'],
            'confidence': decision.get('confidence', 1.0),
            'reasoning': decision.get('reasoning'),
            'analysis': decision.get('analysis')
        }

    def process_learning(
        self,
        agent_id: str,
        feedback_type: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide learning feedback to an AI agent."""
        try:
            from core.agent import WebOpsAgent

            agent = self._get_agent(agent_id)

            if not agent:
                return {
                    'processed': False,
                    'error': f'Agent {agent_id} not found'
                }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(
                    self._async_process_learning(agent, feedback_type, feedback_data)
                )
                return result
            finally:
                loop.close()

        except ImportError:
            # Return mock result
            return self._mock_learning(feedback_type, feedback_data)

        except Exception as e:
            logger.error(f"Learning processing failed: {e}", exc_info=True)
            return {
                'processed': False,
                'error': str(e)
            }

    async def _async_process_learning(
        self,
        agent,
        feedback_type: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Async wrapper for learning processing."""
        result = await agent.process_feedback(
            feedback_type=feedback_type,
            feedback_data=feedback_data
        )

        return {
            'processed': True,
            'learning_impact': result.get('impact'),
            'adjustments_made': result.get('adjustments')
        }

    def _get_agent(self, agent_id: str):
        """Get an agent instance."""
        # In a production system, this would retrieve or create an agent
        # For now, this is a placeholder that will be implemented when
        # the agent system is fully integrated
        try:
            from core.agent import WebOpsAgent
            # Load agent from persistent storage or create new one
            # This is a simplified version
            return None  # Placeholder
        except ImportError:
            return None

    # Mock methods for development/testing when agent system is not available

    def _mock_task_execution(
        self,
        task_description: str,
        task_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock task execution for development."""
        return {
            'status': 'completed',
            'result': f'Mock execution of: {task_description}',
            'task_id': 'mock-task-id',
            'agent_id': 'mock-agent',
            'note': 'This is a mock result. Agent system not available.'
        }

    def _mock_query_response(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock query response for development."""
        return {
            'answer': f'Mock response to: {query}',
            'confidence': 0.95,
            'reasoning': 'This is a mock response for development purposes.',
            'note': 'Agent system not available. Using mock data.'
        }

    def _mock_memory_storage(
        self,
        memory_type: str,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock memory storage for development."""
        return {
            'memory_id': f'mock-memory-{datetime.now().timestamp()}',
            'stored': True,
            'note': 'Mock storage. Agent system not available.'
        }

    def _mock_memory_retrieval(
        self,
        memory_type: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock memory retrieval for development."""
        return {
            'data': {'mock_data': 'Retrieved mock memory'},
            'count': 1,
            'note': 'Mock retrieval. Agent system not available.'
        }

    def _mock_memory_search(
        self,
        memory_type: str,
        query: str,
        limit: int
    ) -> Dict[str, Any]:
        """Mock memory search for development."""
        return {
            'results': [
                {'id': 1, 'content': f'Mock result 1 for query: {query}'},
                {'id': 2, 'content': f'Mock result 2 for query: {query}'}
            ],
            'count': 2,
            'note': 'Mock search. Agent system not available.'
        }

    def _mock_decision(
        self,
        options: List[str],
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Mock decision for development."""
        return {
            'selected_option': options[0] if options else None,
            'confidence': 0.85,
            'reasoning': f'Selected based on criteria: {", ".join(criteria)}',
            'analysis': {'option_scores': {opt: 0.8 for opt in options}},
            'note': 'Mock decision. Agent system not available.'
        }

    def _mock_learning(
        self,
        feedback_type: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mock learning for development."""
        return {
            'processed': True,
            'learning_impact': 0.1,
            'adjustments_made': [f'Mock adjustment from {feedback_type} feedback'],
            'note': 'Mock learning. Agent system not available.'
        }
