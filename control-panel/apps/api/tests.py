from django.test import TestCase, Client, override_settings
from django.urls import reverse
from unittest import mock
import time

from django.contrib.auth.models import User
from apps.api.models import APIToken
from apps.deployments.models import BaseDeployment
from apps.services.background.memory_adapter import InMemoryBackgroundProcessor


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class APIDeploymentAdapterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='apiuser', password='pass')
        self.token = APIToken.objects.create(user=self.user, name='test-token')
        self.auth_header = {'HTTP_AUTHORIZATION': f'Bearer {self.token.token}'}

    def test_deployment_create_uses_background_adapter(self):
        calls = []

        def deploy_stub(deployment_id):
            calls.append(deployment_id)
            return {'success': True, 'deployment_id': deployment_id}

        adapter = InMemoryBackgroundProcessor(
            registry={'apps.deployments.tasks.deploy_application': deploy_stub}
        )

        with mock.patch('apps.api.views.get_background_processor', return_value=adapter), \
             mock.patch('apps.deployments.shared.service_manager.ServiceManager.ensure_celery_running', return_value=None):
            payload = {
                'name': 'api-test-app',
                'repo_url': 'https://github.com/user/repo',
                'branch': 'main',
            }
            resp = self.client.post(
                reverse('api_deployment_create'),
                data=payload,
                content_type='application/json',
                **self.auth_header,
            )
            self.assertEqual(resp.status_code, 201, resp.content)
            data = resp.json()
            self.assertIn('id', data)
            # Wait briefly for background thread to execute stub
            for _ in range(50):
                if calls:
                    break
                time.sleep(0.01)
            # Ensure adapter received the correct deployment id
            self.assertEqual(calls, [data['id']])

    def test_deployment_delete_uses_background_adapter(self):
        calls = []

        def delete_stub(deployment_id):
            calls.append(deployment_id)
            return {'success': True, 'deployment_id': deployment_id}

        adapter = InMemoryBackgroundProcessor(
            registry={'apps.deployments.tasks.delete_deployment': delete_stub}
        )

        # Create a deployment owned by the API user
        dep = ApplicationDeployment.objects.create(
            name='api-delete-app',
            repo_url='https://github.com/user/repo',
            branch='main',
            domain='',
            env_vars={},
            deployed_by=self.user,
            status=ApplicationDeployment.Status.PENDING,
        )

        with mock.patch('apps.api.views.get_background_processor', return_value=adapter), \
             mock.patch('apps.deployments.shared.service_manager.ServiceManager.ensure_celery_running', return_value=None):
            resp = self.client.delete(
                reverse('api_deployment_delete', kwargs={'name': dep.name}),
                **self.auth_header,
            )
            self.assertEqual(resp.status_code, 200, resp.content)
            # Wait briefly for background thread to execute stub
            for _ in range(50):
                if calls:
                    break
                time.sleep(0.01)
            # Ensure adapter received the correct deployment id
            self.assertEqual(calls, [dep.id])

    def test_authentication_required(self):
        resp = self.client.get(reverse('api_deployment_list'))
        self.assertEqual(resp.status_code, 401)
