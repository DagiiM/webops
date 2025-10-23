from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest import mock
import time

from apps.deployments.models import BaseDeployment
from apps.services.background import factory as bg_factory
from apps.services.background.memory_adapter import InMemoryBackgroundProcessor


class ServiceControlAdapterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.client.login(username='tester', password='pass1234')

        self.calls = []

        def stub_start(deployment_id: int):
            self.calls.append(("start", deployment_id))
            return {"success": True, "message": "started"}

        def stub_stop(deployment_id: int):
            self.calls.append(("stop", deployment_id))
            return {"success": True, "message": "stopped"}

        def stub_restart(deployment_id: int):
            self.calls.append(("restart", deployment_id))
            return {"success": True, "message": "restarted"}

        adapter = InMemoryBackgroundProcessor(registry={
            'services.start_service_task': stub_start,
            'services.stop_service_task': stub_stop,
            'services.restart_service_task': stub_restart,
        })
        bg_factory._processor_instance = adapter

        self._ensure_patch = mock.patch(
            'apps.deployments.shared.service_manager.ServiceManager.ensure_celery_running',
            return_value=(True, 'mocked')
        )
        self._ensure_patch.start()
        self.addCleanup(self._ensure_patch.stop)

    def _wait_for(self, kind: str, deployment_id: int, timeout: float = 1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(c[0] == kind and c[1] == deployment_id for c in self.calls):
                return True
            time.sleep(0.01)
        return False

    def test_start_service_background_queues_adapter_task(self):
        dep = ApplicationDeployment.objects.create(
            name='svc1',
            repo_url='https://github.com/example/repo',
            branch='main',
            deployed_by=self.user,
        )
        url = reverse('monitoring:start_service', kwargs={'deployment_id': dep.id})
        resp = self.client.post(url, data={'background': 'true'})
        self.assertIn(resp.status_code, (302, 200))
        self.assertTrue(self._wait_for('start', dep.id))

    def test_stop_service_background_queues_adapter_task(self):
        dep = ApplicationDeployment.objects.create(
            name='svc2',
            repo_url='https://github.com/example/repo',
            branch='main',
            deployed_by=self.user,
        )
        url = reverse('monitoring:stop_service', kwargs={'deployment_id': dep.id})
        resp = self.client.post(url, data={'background': 'true'})
        self.assertIn(resp.status_code, (302, 200))
        self.assertTrue(self._wait_for('stop', dep.id))

    def test_restart_service_background_queues_adapter_task(self):
        dep = ApplicationDeployment.objects.create(
            name='svc3',
            repo_url='https://github.com/example/repo',
            branch='main',
            deployed_by=self.user,
        )
        url = reverse('monitoring:restart_service', kwargs={'deployment_id': dep.id})
        resp = self.client.post(url, data={'background': 'true'})
        self.assertIn(resp.status_code, (302, 200))
        self.assertTrue(self._wait_for('restart', dep.id))
