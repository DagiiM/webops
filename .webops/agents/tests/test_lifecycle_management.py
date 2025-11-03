"""
Tests for Lifecycle Management System

Comprehensive tests for lifecycle and resource management.
"""

import unittest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
import time
from datetime import datetime, timedelta

# Import the lifecycle modules
import sys
sys.path.append('.')

from lifecycle.lifecycle_manager import (
    LifecycleManager, LifecycleState, LifecycleStatus, StateTransition,
    ResourceManager, ResourceType, ResourceStatus, Resource,
    LifecycleEvent, EventType, LifecycleTransitionHandler
)


class TestLifecycleManager(unittest.TestCase):
    """Test lifecycle manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.config.max_memory_mb = 1024
        self.config.max_cpu_percent = 80
        self.config.max_disk_gb = 10
        self.config.cleanup_interval_seconds = 60
        
        self.manager = LifecycleManager(self.config)
    
    async def test_agent_initialization(self):
        """Test agent initialization."""
        agent_config = {
            'name': 'test_agent',
            'version': '1.0.0',
            'capabilities': ['communication', 'problem_solving']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        
        self.assertIsNotNone(agent_id)
        self.assertEqual(agent_config['name'], 'test_agent')
        self.assertEqual(self.manager.current_state, LifecycleState.INITIALIZING)
    
    async def test_agent_startup(self):
        """Test agent startup process."""
        agent_config = {
            'name': 'startup_agent',
            'version': '1.0.0',
            'capabilities': ['communication']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        startup_result = await self.manager.startup_agent(agent_id)
        
        self.assertTrue(startup_result['success'])
        self.assertIn('startup_time', startup_result)
        self.assertEqual(self.manager.current_state, LifecycleState.ACTIVE)
    
    async def test_agent_shutdown(self):
        """Test agent shutdown process."""
        agent_config = {
            'name': 'shutdown_agent',
            'version': '1.0.0',
            'capabilities': ['communication']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        await self.manager.startup_agent(agent_id)
        
        shutdown_result = await self.manager.shutdown_agent(agent_id)
        
        self.assertTrue(shutdown_result['success'])
        self.assertIn('shutdown_time', shutdown_result)
        self.assertEqual(self.manager.current_state, LifecycleState.SHUTDOWN)
    
    async def test_agent_pause_resume(self):
        """Test agent pause and resume functionality."""
        agent_config = {
            'name': 'pause_agent',
            'version': '1.0.0',
            'capabilities': ['communication']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        await self.manager.startup_agent(agent_id)
        
        # Test pause
        pause_result = await self.manager.pause_agent(agent_id)
        self.assertTrue(pause_result['success'])
        self.assertEqual(self.manager.current_state, LifecycleState.PAUSED)
        
        # Test resume
        resume_result = await self.manager.resume_agent(agent_id)
        self.assertTrue(resume_result['success'])
        self.assertEqual(self.manager.current_state, LifecycleState.ACTIVE)
    
    async def test_state_transition_validation(self):
        """Test state transition validation."""
        # Valid transitions
        valid_transitions = [
            (LifecycleState.INITIALIZING, LifecycleState.ACTIVE),
            (LifecycleState.ACTIVE, LifecycleState.PAUSED),
            (LifecycleState.PAUSED, LifecycleState.ACTIVE),
            (LifecycleState.ACTIVE, LifecycleState.SHUTDOWN),
        ]
        
        for from_state, to_state in valid_transitions:
            self.manager.current_state = from_state
            is_valid = await self.manager.validate_transition(to_state)
            self.assertTrue(is_valid, f"Transition from {from_state} to {to_state} should be valid")
        
        # Invalid transitions
        invalid_transitions = [
            (LifecycleState.SHUTDOWN, LifecycleState.ACTIVE),
            (LifecycleState.PAUSED, LifecycleState.INITIALIZING),
            (LifecycleState.ACTIVE, LifecycleState.ERROR),
        ]
        
        for from_state, to_state in invalid_transitions:
            self.manager.current_state = from_state
            is_valid = await self.manager.validate_transition(to_state)
            self.assertFalse(is_valid, f"Transition from {from_state} to {to_state} should be invalid")
    
    async def test_lifecycle_monitoring(self):
        """Test lifecycle monitoring."""
        agent_config = {
            'name': 'monitor_agent',
            'version': '1.0.0',
            'capabilities': ['monitoring']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        
        # Start monitoring
        monitoring_result = await self.manager.start_monitoring(agent_id)
        self.assertTrue(monitoring_result['success'])
        
        # Check monitoring status
        status = await self.manager.get_lifecycle_status(agent_id)
        self.assertIn('monitoring', status)
        self.assertEqual(status['monitoring']['active'], True)
    
    async def test_graceful_shutdown_sequence(self):
        """Test graceful shutdown sequence."""
        agent_config = {
            'name': 'graceful_agent',
            'version': '1.0.0',
            'capabilities': ['communication', 'problem_solving']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        await self.manager.startup_agent(agent_id)
        
        # Trigger graceful shutdown
        shutdown_result = await self.manager.graceful_shutdown(agent_id)
        
        self.assertTrue(shutdown_result['success'])
        self.assertEqual(self.manager.current_state, LifecycleState.SHUTDOWN)
        self.assertIn('shutdown_duration', shutdown_result)
        self.assertGreater(shutdown_result['shutdown_duration'], 0)
    
    async def test_health_check(self):
        """Test agent health check."""
        agent_config = {
            'name': 'health_agent',
            'version': '1.0.0',
            'capabilities': ['monitoring']
        }
        
        agent_id = await self.manager.initialize_agent(agent_config)
        
        # Perform health check
        health_result = await self.manager.perform_health_check(agent_id)
        
        self.assertIn('overall_health', health_result)
        self.assertIn('health_score', health_result)
        self.assertIn('components', health_result)
        
        # Health score should be between 0 and 1
        self.assertGreaterEqual(health_result['health_score'], 0.0)
        self.assertLessEqual(health_result['health_score'], 1.0)


class TestResourceManager(unittest.TestCase):
    """Test resource manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.config.max_memory_mb = 1024
        self.config.max_cpu_percent = 80
        self.config.max_disk_gb = 10
        self.config.resource_limits = {
            'cpu_cores': 4,
            'memory_gb': 2,
            'disk_gb': 5
        }
        
        self.resource_manager = ResourceManager(self.config)
    
    async def test_resource_allocation(self):
        """Test resource allocation."""
        allocation_request = {
            'type': ResourceType.MEMORY,
            'amount': 512,
            'unit': 'mb',
            'priority': 'normal'
        }
        
        allocation_id = await self.resource_manager.allocate_resource(allocation_request)
        
        self.assertIsNotNone(allocation_id)
        self.assertIn(allocation_id, self.resource_manager.allocations)
    
    async def test_resource_deallocation(self):
        """Test resource deallocation."""
        # First allocate a resource
        allocation_request = {
            'type': ResourceType.MEMORY,
            'amount': 256,
            'unit': 'mb'
        }
        
        allocation_id = await self.resource_manager.allocate_resource(allocation_request)
        
        # Then deallocate it
        deallocation_result = await self.resource_manager.deallocate_resource(allocation_id)
        self.assertTrue(deallocation_result)
        
        # Check that allocation is removed
        self.assertNotIn(allocation_id, self.resource_manager.allocations)
    
    async def test_resource_monitoring(self):
        """Test resource monitoring."""
        # Allocate some resources
        await self.resource_manager.allocate_resource({
            'type': ResourceType.MEMORY,
            'amount': 512,
            'unit': 'mb'
        })
        
        await self.resource_manager.allocate_resource({
            'type': ResourceType.CPU,
            'amount': 50,
            'unit': 'percent'
        })
        
        # Get resource utilization
        utilization = await self.resource_manager.get_resource_utilization()
        
        self.assertIn('memory', utilization)
        self.assertIn('cpu', utilization)
        self.assertIn('disk', utilization)
        self.assertIn('network', utilization)
        
        # Check that utilization values are reasonable
        for resource_type, stats in utilization.items():
            self.assertIn('used', stats)
            self.assertIn('available', stats)
            self.assertIn('usage_percent', stats)
            self.assertGreaterEqual(stats['usage_percent'], 0.0)
            self.assertLessEqual(stats['usage_percent'], 100.0)
    
    async def test_resource_optimization(self):
        """Test resource optimization."""
        # Simulate some resource usage
        await self.resource_manager.allocate_resource({
            'type': ResourceType.MEMORY,
            'amount': 800,
            'unit': 'mb'
        })
        
        await self.resource_manager.allocate_resource({
            'type': ResourceType.CPU,
            'amount': 70,
            'unit': 'percent'
        })
        
        # Run optimization
        optimization_result = await self.resource_manager.optimize_resources()
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('optimizations_applied', optimization_result)
        self.assertIn('efficiency_improvement', optimization_result)
    
    async def test_resource_limits_enforcement(self):
        """Test resource limits enforcement."""
        # Try to allocate more resources than allowed
        large_allocation = {
            'type': ResourceType.MEMORY,
            'amount': 2000,  # More than configured limit
            'unit': 'mb'
        }
        
        allocation_id = await self.resource_manager.allocate_resource(large_allocation)
        
        # Should fail due to limits
        self.assertIsNone(allocation_id)
    
    async def test_resource_preemption(self):
        """Test resource preemption."""
        # Allocate multiple resources
        allocation1 = await self.resource_manager.allocate_resource({
            'type': ResourceType.MEMORY,
            'amount': 300,
            'unit': 'mb',
            'priority': 'low'
        })
        
        allocation2 = await self.resource_manager.allocate_resource({
            'type': ResourceType.MEMORY,
            'amount': 400,
            'unit': 'mb',
            'priority': 'high'
        })
        
        # Try to allocate more than available (should trigger preemption)
        allocation3 = await self.resource_manager.allocate_resource({
            'type': ResourceType.MEMORY,
            'amount': 500,
            'unit': 'mb',
            'priority': 'normal'
        })
        
        # Should be None due to resource constraints
        self.assertIsNone(allocation3)


class TestLifecycleEventSystem(unittest.TestCase):
    """Test lifecycle event system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.manager = LifecycleManager(self.config)
        self.handler_called = False
        self.handler_data = None
    
    async def test_event_registration(self):
        """Test event handler registration."""
        async def test_handler(event):
            self.handler_called = True
            self.handler_data = event
        
        # Register event handler
        handler_id = await self.manager.register_event_handler(
            LifecycleEvent.AGENT_STARTED,
            test_handler
        )
        
        self.assertIsNotNone(handler_id)
        self.assertIn(handler_id, self.manager.event_handlers[LifecycleEvent.AGENT_STARTED])
    
    async def test_event_dispatch(self):
        """Test event dispatch to handlers."""
        async def test_handler(event):
            self.handler_called = True
            self.handler_data = event
        
        # Register handler and trigger event
        await self.manager.register_event_handler(LifecycleEvent.AGENT_STARTED, test_handler)
        
        test_event = LifecycleEvent(
            event_type=LifecycleEvent.AGENT_STARTED,
            agent_id="test_agent",
            timestamp=datetime.now(),
            data={'test': 'data'}
        )
        
        await self.manager.dispatch_event(test_event)
        
        # Verify handler was called
        self.assertTrue(self.handler_called)
        self.assertIsNotNone(self.handler_data)
        self.assertEqual(self.handler_data.event_type, LifecycleEvent.AGENT_STARTED)
    
    async def test_event_filtering(self):
        """Test event filtering and prioritization."""
        events_received = []
        
        async def priority_handler(event):
            events_received.append(('high', event))
        
        async def normal_handler(event):
            events_received.append(('normal', event))
        
        # Register handlers with different priorities
        await self.manager.register_event_handler(
            LifecycleEvent.AGENT_STARTED,
            priority_handler,
            priority=10
        )
        
        await self.manager.register_event_handler(
            LifecycleEvent.AGENT_STARTED,
            normal_handler,
            priority=5
        )
        
        # Trigger event
        test_event = LifecycleEvent(
            event_type=LifecycleEvent.AGENT_STARTED,
            agent_id="test_agent",
            timestamp=datetime.now()
        )
        
        await self.manager.dispatch_event(test_event)
        
        # Check order (high priority should be processed first)
        self.assertEqual(len(events_received), 2)
        self.assertEqual(events_received[0][0], 'high')  # High priority first


async def run_async_tests():
    """Run all async tests."""
    print("Running Lifecycle Management Tests...")
    
    # Test LifecycleManager
    lifecycle_test = TestLifecycleManager()
    lifecycle_test.setUp()
    
    try:
        await lifecycle_test.test_agent_initialization()
        print("✓ LifecycleManager: initialization test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: initialization test failed: {e}")
    
    try:
        await lifecycle_test.test_agent_startup()
        print("✓ LifecycleManager: startup test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: startup test failed: {e}")
    
    try:
        await lifecycle_test.test_agent_shutdown()
        print("✓ LifecycleManager: shutdown test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: shutdown test failed: {e}")
    
    try:
        await lifecycle_test.test_agent_pause_resume()
        print("✓ LifecycleManager: pause/resume test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: pause/resume test failed: {e}")
    
    try:
        await lifecycle_test.test_state_transition_validation()
        print("✓ LifecycleManager: state transition validation test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: state transition validation test failed: {e}")
    
    try:
        await lifecycle_test.test_graceful_shutdown_sequence()
        print("✓ LifecycleManager: graceful shutdown test passed")
    except Exception as e:
        print(f"✗ LifecycleManager: graceful shutdown test failed: {e}")
    
    # Test ResourceManager
    resource_test = TestResourceManager()
    resource_test.setUp()
    
    try:
        await resource_test.test_resource_allocation()
        print("✓ ResourceManager: allocation test passed")
    except Exception as e:
        print(f"✗ ResourceManager: allocation test failed: {e}")
    
    try:
        await resource_test.test_resource_deallocation()
        print("✓ ResourceManager: deallocation test passed")
    except Exception as e:
        print(f"✗ ResourceManager: deallocation test failed: {e}")
    
    try:
        await resource_test.test_resource_monitoring()
        print("✓ ResourceManager: monitoring test passed")
    except Exception as e:
        print(f"✗ ResourceManager: monitoring test failed: {e}")
    
    try:
        await resource_test.test_resource_optimization()
        print("✓ ResourceManager: optimization test passed")
    except Exception as e:
        print(f"✗ ResourceManager: optimization test failed: {e}")
    
    try:
        await resource_test.test_resource_limits_enforcement()
        print("✓ ResourceManager: limits enforcement test passed")
    except Exception as e:
        print(f"✗ ResourceManager: limits enforcement test failed: {e}")
    
    # Test Event System
    event_test = TestLifecycleEventSystem()
    event_test.setUp()
    
    try:
        await event_test.test_event_registration()
        print("✓ LifecycleEventSystem: registration test passed")
    except Exception as e:
        print(f"✗ LifecycleEventSystem: registration test failed: {e}")
    
    try:
        await event_test.test_event_dispatch()
        print("✓ LifecycleEventSystem: dispatch test passed")
    except Exception as e:
        print(f"✗ LifecycleEventSystem: dispatch test failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_async_tests())
    print("Lifecycle management tests completed!")