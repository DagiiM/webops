"""
Tests for Skills System

Comprehensive tests for the skills management system.
"""

import unittest
import asyncio
import json
from unittest.mock import Mock, patch
import time

# Import the skills modules
import sys
sys.path.append('.')

from skills.base_skills import (
    BaseSkill, SkillType, SkillLevel, SkillStatus, SkillContext, SkillResult,
    CommunicationSkill, ProblemSolvingSkill, MonitoringSkill, LearningSkill,
    SkillManager
)


class TestBaseSkill(unittest.TestCase):
    """Test base skill functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        class TestSkill(BaseSkill):
            async def execute(self, context):
                return SkillResult(
                    skill_id=self.skill_id,
                    success=True,
                    status=SkillStatus.COMPLETED,
                    output="test output"
                )
        
        self.skill = TestSkill(
            skill_id="test_skill",
            name="Test Skill",
            description="A test skill",
            skill_type=SkillType.TECHNICAL
        )
    
    async def test_skill_creation(self):
        """Test skill creation and initialization."""
        self.assertEqual(self.skill.skill_id, "test_skill")
        self.assertEqual(self.skill.name, "Test Skill")
        self.assertEqual(self.skill.skill_type, SkillType.TECHNICAL)
        self.assertEqual(self.skill.status, SkillStatus.IDLE)
        self.assertEqual(self.skill.execution_count, 0)
    
    async def test_skill_execution(self):
        """Test skill execution."""
        context = SkillContext(
            skill_id="test_skill",
            skill_type=SkillType.TECHNICAL,
            parameters={"test_param": "test_value"}
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertEqual(result.status, SkillStatus.COMPLETED)
        self.assertEqual(result.output, "test output")
        self.assertEqual(self.skill.execution_count, 1)
        self.assertEqual(self.skill.success_count, 1)
    
    async def test_skill_info(self):
        """Test getting skill information."""
        info = await self.skill.get_skill_info()
        
        self.assertEqual(info['skill_id'], "test_skill")
        self.assertEqual(info['name'], "Test Skill")
        self.assertEqual(info['skill_type'], SkillType.TECHNICAL.value)
        self.assertEqual(info['execution_count'], 0)
        self.assertEqual(info['success_rate'], 0.0)


class TestCommunicationSkill(unittest.TestCase):
    """Test communication skill functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.skill = CommunicationSkill()
    
    async def test_text_analysis(self):
        """Test text analysis functionality."""
        context = SkillContext(
            skill_id="communication_base",
            skill_type=SkillType.COMMUNICATION,
            parameters={
                'task_type': 'text_analysis',
                'text': 'This is a sample text with multiple words and sentences.'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('word_count', result.output)
        self.assertIn('character_count', result.output)
        self.assertIn('sentence_count', result.output)
    
    async def test_sentiment_analysis(self):
        """Test sentiment analysis functionality."""
        context = SkillContext(
            skill_id="communication_base",
            skill_type=SkillType.COMMUNICATION,
            parameters={
                'task_type': 'sentiment_analysis',
                'text': 'I love this great product! It is excellent and wonderful.'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('sentiment', result.output)
        self.assertIn('confidence', result.output)
        self.assertEqual(result.output['sentiment'], 'positive')
    
    async def test_intent_recognition(self):
        """Test intent recognition functionality."""
        context = SkillContext(
            skill_id="communication_base",
            skill_type=SkillType.COMMUNICATION,
            parameters={
                'task_type': 'intent_recognition',
                'text': 'Hello, how can you help me today?'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('intents', result.output)
        self.assertIn('primary_intent', result.output)
        self.assertEqual(result.output['primary_intent'], 'greeting')
    
    async def test_response_generation(self):
        """Test response generation functionality."""
        context = SkillContext(
            skill_id="communication_base",
            skill_type=SkillType.COMMUNICATION,
            parameters={
                'task_type': 'response_generation',
                'text': 'Hello',
                'intent': 'greeting'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('response', result.output)
        self.assertIn('intent', result.output)


class TestProblemSolvingSkill(unittest.TestCase):
    """Test problem-solving skill functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.skill = ProblemSolvingSkill()
    
    async def test_problem_analysis(self):
        """Test problem analysis functionality."""
        context = SkillContext(
            skill_id="problem_solving",
            skill_type=SkillType.PROBLEM_SOLVING,
            parameters={
                'type': 'analysis',
                'problem': 'The system is slow and users are experiencing delays.'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('problem_statement', result.output)
        self.assertIn('domain', result.output)
        self.assertIn('complexity_score', result.output)
    
    async def test_problem_decomposition(self):
        """Test problem decomposition functionality."""
        context = SkillContext(
            skill_id="problem_solving",
            skill_type=SkillType.PROBLEM_SOLVING,
            parameters={
                'type': 'decomposition',
                'problem': 'First step is to identify the issue. Second step is to implement a solution. Third step is to test the solution.'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('sub_problems', result.output)
        self.assertIn('total_sub_problems', result.output)
        self.assertGreater(result.output['total_sub_problems'], 0)
    
    async def test_solution_generation(self):
        """Test solution generation functionality."""
        context = SkillContext(
            skill_id="problem_solving",
            skill_type=SkillType.PROBLEM_SOLVING,
            parameters={
                'type': 'solution_generation',
                'problem': 'System performance issues',
                'solutions_count': 3
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('solutions', result.output)
        self.assertEqual(len(result.output['solutions']), 3)
        
        for solution in result.output['solutions']:
            self.assertIn('id', solution)
            self.assertIn('description', solution)
            self.assertIn('feasibility_score', solution)


class TestMonitoringSkill(unittest.TestCase):
    """Test monitoring skill functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.skill = MonitoringSkill()
    
    async def test_health_check(self):
        """Test health check functionality."""
        context = SkillContext(
            skill_id="monitoring",
            skill_type=SkillType.MONITORING,
            parameters={
                'type': 'health_check',
                'targets': ['system', 'database', 'api']
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('overall_status', result.output)
        self.assertIn('overall_score', result.output)
        self.assertIn('individual_status', result.output)
    
    async def test_performance_monitoring(self):
        """Test performance monitoring functionality."""
        context = SkillContext(
            skill_id="monitoring",
            skill_type=SkillType.MONITORING,
            parameters={
                'type': 'performance_monitor',
                'metrics': ['cpu', 'memory', 'disk']
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('metrics', result.output)
        self.assertIn('performance_data', result.output)
        self.assertIn('performance_score', result.output)
    
    async def test_alert_check(self):
        """Test alert checking functionality."""
        context = SkillContext(
            skill_id="monitoring",
            skill_type=SkillType.MONITORING,
            parameters={
                'type': 'alert_check'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('active_alerts', result.output)
        self.assertIn('total_alerts', result.output)


class TestLearningSkill(unittest.TestCase):
    """Test learning skill functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.skill = LearningSkill()
    
    async def test_pattern_recognition(self):
        """Test pattern recognition functionality."""
        context = SkillContext(
            skill_id="learning",
            skill_type=SkillType.LEARNING,
            parameters={
                'type': 'pattern_recognition',
                'pattern_type': 'sequence',
                'data': ['step1', 'step2', 'step2', 'step3', 'step3', 'step3']
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('patterns_found', result.output)
        self.assertIn('total_patterns', result.output)
        self.assertGreater(result.output['total_patterns'], 0)
    
    async def test_experience_learning(self):
        """Test experience learning functionality."""
        context = SkillContext(
            skill_id="learning",
            skill_type=SkillType.LEARNING,
            parameters={
                'type': 'experience_learning',
                'experience': {'action': 'deploy', 'result': 'success'},
                'outcome': 'success'
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('experience_processed', result.output)
        self.assertIn('insights_generated', result.output)
    
    async def test_adaptation(self):
        """Test behavior adaptation functionality."""
        context = SkillContext(
            skill_id="learning",
            skill_type=SkillType.LEARNING,
            parameters={
                'type': 'adaptation',
                'behavior': {'approach': 'method1'},
                'feedback': {'score': 0.3}
            }
        )
        
        result = await self.skill.execute(context)
        
        self.assertTrue(result.success)
        self.assertIn('adaptation_suggestions', result.output)


class TestSkillManager(unittest.TestCase):
    """Test skill manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = SkillManager()
    
    async def test_skill_registration(self):
        """Test skill registration."""
        class TestSkill(BaseSkill):
            async def execute(self, context):
                return SkillResult(
                    skill_id=self.skill_id,
                    success=True,
                    status=SkillStatus.COMPLETED,
                    output="test"
                )
        
        skill = TestSkill(
            skill_id="test_skill",
            name="Test Skill",
            description="Test skill for registration",
            skill_type=SkillType.TECHNICAL
        )
        
        success = await self.manager.register_skill(skill)
        self.assertTrue(success)
        self.assertIn("test_skill", self.manager.skills)
    
    async def test_skill_execution(self):
        """Test skill execution through manager."""
        skill = CommunicationSkill()
        await self.manager.register_skill(skill)
        
        result = await self.manager.execute_skill(
            "communication_base",
            parameters={
                'task_type': 'text_analysis',
                'text': 'This is a test.'
            }
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.status, SkillStatus.COMPLETED)
    
    async def test_skill_sequence_execution(self):
        """Test sequence skill execution."""
        comm_skill = CommunicationSkill()
        monitoring_skill = MonitoringSkill()
        
        await self.manager.register_skill(comm_skill)
        await self.manager.register_skill(monitoring_skill)
        
        sequence = [
            {
                'skill_id': 'communication_base',
                'parameters': {
                    'task_type': 'intent_recognition',
                    'text': 'Hello there'
                },
                'stop_on_failure': True
            },
            {
                'skill_id': 'monitoring',
                'parameters': {
                    'type': 'health_check'
                },
                'stop_on_failure': True
            }
        ]
        
        results = await self.manager.execute_skill_sequence(sequence)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
    
    async def test_list_skills(self):
        """Test listing skills."""
        skill = CommunicationSkill()
        await self.manager.register_skill(skill)
        
        all_skills = await self.manager.list_skills()
        self.assertEqual(len(all_skills), 1)
        self.assertEqual(all_skills[0]['skill_id'], 'communication_base')
        
        communication_skills = await self.manager.list_skills(SkillType.COMMUNICATION)
        self.assertEqual(len(communication_skills), 1)
    
    async def test_skill_performance(self):
        """Test skill performance metrics."""
        skill = CommunicationSkill()
        await self.manager.register_skill(skill)
        
        # Execute skill to generate metrics
        await self.manager.execute_skill(
            "communication_base",
            parameters={'task_type': 'general'}
        )
        
        performance = await self.manager.get_skill_performance()
        
        self.assertIn('timestamp', performance)
        self.assertIn('total_skills', performance)
        self.assertIn('skill_performance', performance)
        self.assertEqual(performance['total_skills'], 1)


async def run_async_tests():
    """Run all async tests."""
    print("Running Skills System Tests...")
    
    # Test BaseSkill
    base_test = TestBaseSkill()
    base_test.setUp()
    
    try:
        await base_test.test_skill_creation()
        print("✓ BaseSkill: creation test passed")
    except Exception as e:
        print(f"✗ BaseSkill: creation test failed: {e}")
    
    try:
        await base_test.test_skill_execution()
        print("✓ BaseSkill: execution test passed")
    except Exception as e:
        print(f"✗ BaseSkill: execution test failed: {e}")
    
    # Test CommunicationSkill
    comm_test = TestCommunicationSkill()
    comm_test.setUp()
    
    try:
        await comm_test.test_text_analysis()
        print("✓ CommunicationSkill: text analysis test passed")
    except Exception as e:
        print(f"✗ CommunicationSkill: text analysis test failed: {e}")
    
    try:
        await comm_test.test_sentiment_analysis()
        print("✓ CommunicationSkill: sentiment analysis test passed")
    except Exception as e:
        print(f"✗ CommunicationSkill: sentiment analysis test failed: {e}")
    
    try:
        await comm_test.test_intent_recognition()
        print("✓ CommunicationSkill: intent recognition test passed")
    except Exception as e:
        print(f"✗ CommunicationSkill: intent recognition test failed: {e}")
    
    # Test ProblemSolvingSkill
    problem_test = TestProblemSolvingSkill()
    problem_test.setUp()
    
    try:
        await problem_test.test_problem_analysis()
        print("✓ ProblemSolvingSkill: problem analysis test passed")
    except Exception as e:
        print(f"✗ ProblemSolvingSkill: problem analysis test failed: {e}")
    
    try:
        await problem_test.test_solution_generation()
        print("✓ ProblemSolvingSkill: solution generation test passed")
    except Exception as e:
        print(f"✗ ProblemSolvingSkill: solution generation test failed: {e}")
    
    # Test MonitoringSkill
    monitor_test = TestMonitoringSkill()
    monitor_test.setUp()
    
    try:
        await monitor_test.test_health_check()
        print("✓ MonitoringSkill: health check test passed")
    except Exception as e:
        print(f"✗ MonitoringSkill: health check test failed: {e}")
    
    try:
        await monitor_test.test_performance_monitoring()
        print("✓ MonitoringSkill: performance monitoring test passed")
    except Exception as e:
        print(f"✗ MonitoringSkill: performance monitoring test failed: {e}")
    
    # Test LearningSkill
    learning_test = TestLearningSkill()
    learning_test.setUp()
    
    try:
        await learning_test.test_pattern_recognition()
        print("✓ LearningSkill: pattern recognition test passed")
    except Exception as e:
        print(f"✗ LearningSkill: pattern recognition test failed: {e}")
    
    # Test SkillManager
    manager_test = TestSkillManager()
    manager_test.setUp()
    
    try:
        await manager_test.test_skill_registration()
        print("✓ SkillManager: registration test passed")
    except Exception as e:
        print(f"✗ SkillManager: registration test failed: {e}")
    
    try:
        await manager_test.test_skill_execution()
        print("✓ SkillManager: execution test passed")
    except Exception as e:
        print(f"✗ SkillManager: execution test failed: {e}")
    
    try:
        await manager_test.test_skill_sequence_execution()
        print("✓ SkillManager: sequence execution test passed")
    except Exception as e:
        print(f"✗ SkillManager: sequence execution test failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_async_tests())
    print("Skills system tests completed!")