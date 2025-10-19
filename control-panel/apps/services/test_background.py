from django.test import TestCase
from unittest import mock
import time
import os

from apps.services.background.memory_adapter import InMemoryBackgroundProcessor
from apps.services.background.interface import TaskStatus
from apps.services.background.factory import get_background_processor
from apps.services.background import factory as bg_factory
from apps.services.background.celery_adapter import CeleryBackgroundProcessor


class MemoryAdapterTests(TestCase):
    def test_submit_status_and_result(self):
        calls = []

        def add_one(x):
            calls.append(x)
            return x + 1

        adapter = InMemoryBackgroundProcessor(registry={'test.add_one': add_one})
        handle = adapter.submit('test.add_one', 1)
        # Wait for completion via result API
        result = adapter.result(handle, timeout=1.0)
        self.assertEqual(result, 2)
        self.assertEqual(adapter.status(handle), TaskStatus.SUCCESS)
        self.assertEqual(calls, [1])

    def test_unknown_task_raises(self):
        adapter = InMemoryBackgroundProcessor(registry={})
        with self.assertRaises(ValueError):
            adapter.submit('unknown.task')

    def test_revoke_not_supported(self):
        adapter = InMemoryBackgroundProcessor(registry={'noop': lambda: None})
        handle = adapter.submit('noop')
        # In-memory adapter does not support revoke
        self.assertFalse(adapter.revoke(handle))


class FactorySelectionTests(TestCase):
    def setUp(self):
        # Ensure a clean factory state for each test
        bg_factory._processor_instance = None

    def tearDown(self):
        bg_factory._processor_instance = None

    def test_selects_memory_when_env_set(self):
        with mock.patch.dict(os.environ, {"WEBOPS_BG_PROCESSOR": "memory"}):
            proc = get_background_processor()
            self.assertIsInstance(proc, InMemoryBackgroundProcessor)
            # Singleton behavior
            self.assertIs(proc, get_background_processor())

    def test_fallback_returns_valid_processor(self):
        # Unknown choice should fallback to celery or memory
        with mock.patch.dict(os.environ, {"WEBOPS_BG_PROCESSOR": "unknown"}):
            proc = get_background_processor()
            # Name should be either 'celery' or 'memory' depending on availability
            self.assertIn(proc.name, ("celery", "memory"))
            # Singleton behavior
            self.assertIs(proc, get_background_processor())