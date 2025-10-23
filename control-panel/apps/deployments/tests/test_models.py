from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from unittest import mock
import time

from apps.deployments.models import BaseDeployment
from apps.services.background import factory as bg_factory
from apps.services.background.memory_adapter import InMemoryBackgroundProcessor


class DeploymentAdapterSubmissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='pass1234')
        self.client.login(username='tester', password='pass1234')

        # Capture calls from stubbed tasks
        self.calls = []

        def stub_deploy(deployment_id: int):
            self.calls.append(("deploy", deployment_id))
            return {"success": True}

        def stub_delete(deployment_id: int):
            self.calls.append(("delete", deployment_id))
            return {"success": True}

        # Inject memory adapter with registry mapping dotted task names to stubs
        adapter = InMemoryBackgroundProcessor(registry={
            'apps.deployments.tasks.application.deploy_application': stub_deploy,
            'apps.deployments.tasks.application.delete_deployment': stub_delete,
        })
        bg_factory._processor_instance = adapter

        # Avoid systemctl calls during tests
        self._ensure_patch = mock.patch(
            'apps.deployments.shared.service_manager.ServiceManager.ensure_celery_running',
            return_value=(True, 'mocked')
        )
        self._ensure_patch.start()
        self.addCleanup(self._ensure_patch.stop)

    def _wait_for_call(self, kind: str, deployment_id: int, timeout: float = 1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(c[0] == kind and c[1] == deployment_id for c in self.calls):
                return True
            time.sleep(0.01)
        return False

    def test_deployment_create_submits_task_via_adapter(self):
        resp = self.client.post(reverse('deployments:deployment_create'), data={
            'name': 'My App',
            'repo_url': 'https://github.com/example/repo',
            'branch': 'main',
        })
        # Should redirect to detail page
        self.assertEqual(resp.status_code, 302)

        # Deployment should be created with sanitized name
        dep = ApplicationDeployment.objects.get(name='my-app')

        # Verify background submission invoked stub via adapter
        self.assertTrue(self._wait_for_call('deploy', dep.id))

    def test_deployment_delete_submits_task_via_adapter(self):
        dep = ApplicationDeployment.objects.create(
            name='deleteme',
            repo_url='https://github.com/example/repo',
            branch='main',
            deployed_by=self.user,
        )

        resp = self.client.post(reverse('deployments:deployment_delete', kwargs={'pk': dep.id}))
        # Should redirect to list page
        self.assertEqual(resp.status_code, 302)

        # Verify background submission invoked stub via adapter
        self.assertTrue(self._wait_for_call('delete', dep.id))
