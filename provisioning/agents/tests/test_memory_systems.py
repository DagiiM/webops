"""
Tests for Memory Systems

Comprehensive tests for all memory system components.
"""

import unittest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import tempfile
import os

# Import the memory modules
import sys
sys.path.append('.')

from memory.episodic import EpisodicMemory, Event, EventType, EmotionType, ImportanceLevel, Actor, Context
from memory.semantic import SemanticMemory, Concept, ConceptType, Relationship, RelationshipType
from memory.procedural import ProceduralMemory, Procedure, ProcedureType, ProcedureStatus, StepType, ProcedureStep
from memory.learning import LearningMemory, LearningPattern, LearningType


class TestEpisodicMemory(unittest.TestCase):
    """Test episodic memory functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.memory = EpisodicMemory(self.config)
        
        # Create test events
        self.test_event = Event(
            event_type=EventType.INTERACTION,
            title="Test Interaction",
            description="A test interaction event",
            importance=ImportanceLevel.MODERATE,
            emotions=[EmotionType.NEUTRAL],
            actors=[
                Actor(name="TestUser", role="user")
            ]
        )
        
        self.context = Context(
            location="Test Environment",
            environment="testing"
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.memory = None
    
    async def test_store_event(self):
        """Test storing an event."""
        event_id = await self.memory.store_event(self.test_event)
        
        # Verify event was stored
        self.assertIsNotNone(event_id)
        stored_event = await self.memory.get_event(event_id)
        self.assertIsNotNone(stored_event)
        self.assertEqual(stored_event.title, "Test Interaction")
    
    async def test_search_events(self):
        """Test searching events."""
        await self.memory.store_event(self.test_event)
        
        # Search for the event
        results = await self.memory.search_events("Test Interaction")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Test Interaction")
    
    async def test_get_recent_events(self):
        """Test getting recent events."""
        await self.memory.store_event(self.test_event)
        
        # Get recent events
        recent_events = await self.memory.get_recent_events(days=7)
        
        self.assertEqual(len(recent_events), 1)
        self.assertEqual(recent_events[0]['title'], "Test Interaction")
    
    async def test_event_salience_calculation(self):
        """Test event salience calculation."""
        # Create high-salience event
        high_importance_event = Event(
            event_type=EventType.INTERACTION,
            title="High Importance Event",
            description="This is very important",
            importance=ImportanceLevel.CRITICAL,
            emotions=[EmotionType.FRUSTRATED, EmotionType.ANXIOUS],
            duration_seconds=3600.0,  # 1 hour
            actors=[
                Actor(name="User1", role="user"),
                Actor(name="User2", role="assistant")
            ],
            outcomes=["Problem solved"],
            lessons_learned=["Always check the logs first"]
        )
        
        salience = high_importance_event.calculate_salience()
        self.assertGreater(salience, 0.5)  # Should be high salience
        
        # Create low-salience event
        low_importance_event = Event(
            event_type=EventType.INTERNAL_EVENT,
            title="Internal Thought",
            description="Random thought",
            importance=ImportanceLevel.TRIVIAL
        )
        
        salience = low_importance_event.calculate_salience()
        self.assertLess(salience, 0.3)  # Should be low salience


class TestSemanticMemory(unittest.TestCase):
    """Test semantic memory functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.memory = SemanticMemory(self.config)
        
        # Create test concepts
        self.ai_concept = Concept(
            name="Artificial Intelligence",
            concept_type=ConceptType.DOMAIN,
            description="AI is a field of computer science",
            attributes={"field": "computer_science", "type": "technology"},
            confidence=0.9
        )
        
        self.python_concept = Concept(
            name="Python",
            concept_type=ConceptType.TECHNOLOGY,
            description="Python is a programming language",
            attributes={"type": "programming_language", "paradigm": "object_oriented"},
            confidence=0.95
        )
    
    async def test_store_concept(self):
        """Test storing a concept."""
        concept_id = await self.memory.store_concept(self.ai_concept)
        
        self.assertIsNotNone(concept_id)
        stored_concept = await self.memory.get_concept(concept_id)
        self.assertIsNotNone(stored_concept)
        self.assertEqual(stored_concept.name, "Artificial Intelligence")
    
    async def test_create_relationship(self):
        """Test creating relationships between concepts."""
        ai_id = await self.memory.store_concept(self.ai_concept)
        python_id = await self.memory.store_concept(self.python_concept)
        
        # Create relationship
        relationship = Relationship(
            source_concept_id=ai_id,
            target_concept_id=python_id,
            relationship_type=RelationshipType.CONTAINS,
            strength=0.8
        )
        
        relationship_id = await self.memory.create_relationship(relationship)
        self.assertIsNotNone(relationship_id)
    
    async def test_semantic_similarity(self):
        """Test semantic similarity calculation."""
        # Store concepts
        ai_id = await self.memory.store_concept(self.ai_concept)
        python_id = await self.memory.store_concept(self.python_concept)
        
        # Create overlapping attributes
        self.ai_concept.attributes = {"category": "technology", "complexity": "high"}
        self.python_concept.attributes = {"category": "technology", "complexity": "medium"}
        
        await self.memory.update_concept(self.ai_concept)
        await self.memory.update_concept(self.python_concept)
        
        similarity = await self.memory.calculate_concept_similarity(ai_id, python_id)
        self.assertGreater(similarity, 0.5)  # Should have some similarity
    
    async def test_find_related_concepts(self):
        """Test finding related concepts."""
        ai_id = await self.memory.store_concept(self.ai_concept)
        python_id = await self.memory.store_concept(self.python_concept)
        
        # Create relationship
        relationship = Relationship(
            source_concept_id=ai_id,
            target_concept_id=python_id,
            relationship_type=RelationshipType.CONTAINS,
            strength=0.8
        )
        
        await self.memory.create_relationship(relationship)
        
        # Find related concepts
        related = await self.memory.find_related_concepts(ai_id)
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]['concept_id'], python_id)


class TestProceduralMemory(unittest.TestCase):
    """Test procedural memory functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.memory = ProceduralMemory(self.config)
        
        # Create test procedure
        self.test_procedure = Procedure(
            name="Deploy Application",
            description="Deploy a web application to production",
            procedure_type=ProcedureType.WORKFLOW,
            success_rate=0.8,
            execution_count=10
        )
        
        # Create test steps
        step1 = ProcedureStep(
            description="Clone repository",
            action="git_clone",
            timeout_seconds=30
        )
        
        step2 = ProcedureStep(
            description="Install dependencies",
            action="pip_install",
            timeout_seconds=120
        )
        
        step3 = ProcedureStep(
            description="Run tests",
            action="run_tests",
            timeout_seconds=60,
            expected_outcome="All tests pass"
        )
        
        self.test_procedure.steps = [step1, step2, step3]
    
    async def test_store_procedure(self):
        """Test storing a procedure."""
        procedure_id = await self.memory.store_procedure(self.test_procedure)
        
        self.assertIsNotNone(procedure_id)
        stored_procedure = await self.memory.get_procedure(procedure_id)
        self.assertIsNotNone(stored_procedure)
        self.assertEqual(stored_procedure.name, "Deploy Application")
    
    async def test_search_procedures(self):
        """Test searching procedures."""
        await self.memory.store_procedure(self.test_procedure)
        
        # Search for the procedure
        results = await self.memory.search_procedures("Deploy")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], "Deploy Application")
    
    async def test_learn_skill(self):
        """Test learning skills from procedures."""
        procedure_id = await self.memory.store_procedure(self.test_procedure)
        
        # Learn skill
        skill_name = await self.memory.learn_skill(
            name="Web Application Deployment",
            description="Deploy web applications using Git and pip",
            procedure_id=procedure_id,
            category="devops"
        )
        
        self.assertIsNotNone(skill_name)
        skill = await self.memory.get_skill(skill_name)
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "Web Application Deployment")
    
    async def test_procedure_complexity_calculation(self):
        """Test procedure complexity calculation."""
        # Add more complex steps
        decision_step = ProcedureStep(
            description="Check if tests pass",
            step_type=StepType.DECISION,
            timeout_seconds=5
        )
        
        loop_step = ProcedureStep(
            description="Deploy to multiple servers",
            step_type=StepType.LOOP,
            timeout_seconds=300
        )
        
        parallel_step = ProcedureStep(
            description="Run health checks",
            step_type=StepType.PARALLEL,
            timeout_seconds=30,
            parallel_steps=["check_db", "check_api", "check_web"]
        )
        
        self.test_procedure.steps.extend([decision_step, loop_step, parallel_step])
        
        complexity = self.test_procedure.calculate_complexity()
        self.assertGreater(complexity, 0.5)  # Should be complex
    
    async def test_execute_procedure(self):
        """Test procedure execution."""
        procedure_id = await self.memory.store_procedure(self.test_procedure)
        
        # Test with mock executor
        async def mock_step_executor(step, context):
            return {
                'success': True,
                'step_id': step.id,
                'message': f"Executed {step.action}"
            }
        
        # Execute procedure
        result = await self.memory.execute_procedure(
            procedure_id,
            {},
            step_executor=mock_step_executor
        )
        
        self.assertIsNotNone(result)
        self.assertIn('success', result)
        self.assertIn('step_results', result)


class TestLearningMemory(unittest.TestCase):
    """Test learning memory functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = Mock()
        self.memory = LearningMemory(self.config)
    
    async def test_learn_pattern(self):
        """Test learning patterns from data."""
        # Create learning pattern
        pattern = LearningPattern(
            pattern_type=LearningType.SEQUENCE,
            pattern_data=["step1", "step2", "step3"],
            context={"domain": "deployment"},
            confidence=0.7,
            success_rate=0.8
        )
        
        pattern_id = await self.memory.learn_pattern(pattern)
        self.assertIsNotNone(pattern_id)
        
        stored_pattern = await self.memory.get_learning_pattern(pattern_id)
        self.assertIsNotNone(stored_pattern)
        self.assertEqual(stored_pattern.pattern_type, LearningType.SEQUENCE)
    
    async def test_get_adaptation_suggestions(self):
        """Test getting adaptation suggestions."""
        # Learn a pattern first
        pattern = LearningPattern(
            pattern_type=LearningType.BEHAVIORAL,
            pattern_data={"action": "deploy", "outcome": "success"},
            confidence=0.6
        )
        
        await self.memory.learn_pattern(pattern)
        
        # Get adaptation suggestions
        suggestions = await self.memory.get_adaptation_suggestions()
        
        self.assertIsInstance(suggestions, list)
    
    async def test_optimize_behavior(self):
        """Test behavior optimization."""
        # Learn multiple patterns with different success rates
        pattern1 = LearningPattern(
            pattern_type=LearningType.PROCEDURAL,
            pattern_data=["option1", "option2"],
            success_rate=0.9,
            confidence=0.8
        )
        
        pattern2 = LearningPattern(
            pattern_type=LearningType.PROCEDURAL,
            pattern_data=["option1", "option3"],
            success_rate=0.4,
            confidence=0.7
        )
        
        await self.memory.learn_pattern(pattern1)
        await self.memory.learn_pattern(pattern2)
        
        # Optimize behavior
        optimization_result = await self.memory.optimize_behavior()
        
        self.assertIsInstance(optimization_result, dict)
        self.assertIn('recommendations', optimization_result)


async def run_async_tests():
    """Run all async tests."""
    # Test EpisodicMemory
    episodic_test = TestEpisodicMemory()
    episodic_test.setUp()
    
    try:
        await episodic_test.test_store_event()
        print("✓ EpisodicMemory: store_event test passed")
    except Exception as e:
        print(f"✗ EpisodicMemory: store_event test failed: {e}")
    
    try:
        await episodic_test.test_search_events()
        print("✓ EpisodicMemory: search_events test passed")
    except Exception as e:
        print(f"✗ EpisodicMemory: search_events test failed: {e}")
    
    try:
        await episodic_test.test_event_salience_calculation()
        print("✓ EpisodicMemory: salience calculation test passed")
    except Exception as e:
        print(f"✗ EpisodicMemory: salience calculation test failed: {e}")
    
    # Test SemanticMemory
    semantic_test = TestSemanticMemory()
    semantic_test.setUp()
    
    try:
        await semantic_test.test_store_concept()
        print("✓ SemanticMemory: store_concept test passed")
    except Exception as e:
        print(f"✗ SemanticMemory: store_concept test failed: {e}")
    
    try:
        await semantic_test.test_create_relationship()
        print("✓ SemanticMemory: create_relationship test passed")
    except Exception as e:
        print(f"✗ SemanticMemory: create_relationship test failed: {e}")
    
    # Test ProceduralMemory
    procedural_test = TestProceduralMemory()
    procedural_test.setUp()
    
    try:
        await procedural_test.test_store_procedure()
        print("✓ ProceduralMemory: store_procedure test passed")
    except Exception as e:
        print(f"✗ ProceduralMemory: store_procedure test failed: {e}")
    
    try:
        await procedural_test.test_learn_skill()
        print("✓ ProceduralMemory: learn_skill test passed")
    except Exception as e:
        print(f"✗ ProceduralMemory: learn_skill test failed: {e}")
    
    # Test LearningMemory
    learning_test = TestLearningMemory()
    learning_test.setUp()
    
    try:
        await learning_test.test_learn_pattern()
        print("✓ LearningMemory: learn_pattern test passed")
    except Exception as e:
        print(f"✗ LearningMemory: learn_pattern test failed: {e}")
    
    try:
        await learning_test.test_get_adaptation_suggestions()
        print("✓ LearningMemory: get_adaptation_suggestions test passed")
    except Exception as e:
        print(f"✗ LearningMemory: get_adaptation_suggestions test failed: {e}")


if __name__ == "__main__":
    print("Running Memory Systems Tests...")
    asyncio.run(run_async_tests())
    print("Memory systems tests completed!")