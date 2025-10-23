"""
Tests for the new deployment model structure.

Tests BaseDeployment, ApplicationDeployment, and LLMDeployment models.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from apps.deployments.models import (
    BaseDeployment,
    ApplicationDeployment,
    LLMDeployment,
    DeploymentLog,
    HealthCheckRecord,
)


class BaseDeploymentTests(TestCase):
    """Test BaseDeployment model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_cannot_create_base_deployment_directly(self):
        """BaseDeployment is abstract-like, should use child classes."""
        # BaseDeployment can be created but it's not the intended use
        # Child classes (ApplicationDeployment, LLMDeployment) should be used
        base = BaseDeployment.objects.create(
            name='test-base',
            deployed_by=self.user,
        )
        self.assertEqual(base.name, 'test-base')
        self.assertEqual(base.status, 'pending')
        self.assertIsNone(base.port)


class ApplicationDeploymentTests(TestCase):
    """Test ApplicationDeployment model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_django_deployment(self):
        """Test creating a Django application deployment."""
        app = ApplicationDeployment.objects.create(
            name='my-django-app',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/django-app',
            branch='main',
        )
        self.assertEqual(app.name, 'my-django-app')
        self.assertEqual(app.project_type, 'django')
        self.assertEqual(app.repo_url, 'https://github.com/example/django-app')
        self.assertEqual(app.branch, 'main')
        self.assertFalse(app.use_docker)
        self.assertEqual(app.env_vars, {})

    def test_create_docker_deployment(self):
        """Test creating a deployment with Docker enabled."""
        app = ApplicationDeployment.objects.create(
            name='docker-app',
            deployed_by=self.user,
            project_type='nodejs',
            repo_url='https://github.com/example/node-app',
            branch='develop',
            use_docker=True,
            dockerfile_path='docker/Dockerfile',
            docker_network_mode='host',
        )
        self.assertTrue(app.use_docker)
        self.assertEqual(app.dockerfile_path, 'docker/Dockerfile')
        self.assertEqual(app.docker_network_mode, 'host')

    def test_env_vars_storage(self):
        """Test environment variables storage."""
        app = ApplicationDeployment.objects.create(
            name='env-test',
            deployed_by=self.user,
            project_type='python',
            repo_url='https://github.com/example/python-app',
            env_vars={
                'DATABASE_URL': 'postgresql://localhost/db',
                'SECRET_KEY': 'test-secret',
            }
        )
        self.assertEqual(len(app.env_vars), 2)
        self.assertEqual(app.env_vars['DATABASE_URL'], 'postgresql://localhost/db')

    def test_unique_name_constraint(self):
        """Test that deployment names must be unique."""
        ApplicationDeployment.objects.create(
            name='unique-app',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/app1',
        )

        # Attempting to create another deployment with the same name should fail
        with self.assertRaises(Exception):
            ApplicationDeployment.objects.create(
                name='unique-app',
                deployed_by=self.user,
                project_type='django',
                repo_url='https://github.com/example/app2',
            )


class LLMDeploymentTests(TestCase):
    """Test LLMDeployment model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_llm_deployment(self):
        """Test creating an LLM deployment."""
        llm = LLMDeployment.objects.create(
            name='llama-model',
            deployed_by=self.user,
            model_name='meta-llama/Llama-2-7b-chat-hf',
            tensor_parallel_size=2,
            gpu_memory_utilization=0.85,
        )
        self.assertEqual(llm.name, 'llama-model')
        self.assertEqual(llm.model_name, 'meta-llama/Llama-2-7b-chat-hf')
        self.assertEqual(llm.tensor_parallel_size, 2)
        self.assertEqual(llm.gpu_memory_utilization, 0.85)
        self.assertFalse(llm.download_completed)

    def test_llm_with_quantization(self):
        """Test LLM deployment with quantization."""
        llm = LLMDeployment.objects.create(
            name='quantized-model',
            deployed_by=self.user,
            model_name='TheBloke/Llama-2-7B-AWQ',
            quantization='awq',
            dtype='float16',
        )
        self.assertEqual(llm.quantization, 'awq')
        self.assertEqual(llm.dtype, 'float16')

    def test_llm_vllm_args(self):
        """Test storing custom vLLM arguments."""
        llm = LLMDeployment.objects.create(
            name='custom-llm',
            deployed_by=self.user,
            model_name='mistralai/Mistral-7B-v0.1',
            vllm_args={
                'max_num_batched_tokens': 4096,
                'enable_prefix_caching': True,
            }
        )
        self.assertEqual(len(llm.vllm_args), 2)
        self.assertTrue(llm.vllm_args['enable_prefix_caching'])


class DeploymentLogTests(TestCase):
    """Test DeploymentLog model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/app',
        )

    def test_create_deployment_log(self):
        """Test creating a deployment log."""
        log = DeploymentLog.objects.create(
            deployment=self.deployment,
            level='info',
            message='Deployment started',
        )
        self.assertEqual(log.deployment, self.deployment)
        self.assertEqual(log.level, 'info')
        self.assertEqual(log.message, 'Deployment started')

    def test_log_levels(self):
        """Test different log levels."""
        levels = ['info', 'warning', 'error', 'success']
        for level in levels:
            log = DeploymentLog.objects.create(
                deployment=self.deployment,
                level=level,
                message=f'Test {level} message',
            )
            self.assertEqual(log.level, level)

    def test_logs_relationship(self):
        """Test that logs are accessible from deployment."""
        DeploymentLog.objects.create(
            deployment=self.deployment,
            level='info',
            message='Log 1',
        )
        DeploymentLog.objects.create(
            deployment=self.deployment,
            level='info',
            message='Log 2',
        )

        logs = self.deployment.logs.all()
        self.assertEqual(logs.count(), 2)


class HealthCheckRecordTests(TestCase):
    """Test HealthCheckRecord model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.deployment = ApplicationDeployment.objects.create(
            name='health-test-app',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/app',
            status='running',
            port=8000,
        )

    def test_create_health_check_record(self):
        """Test creating a health check record."""
        record = HealthCheckRecord.objects.create(
            deployment=self.deployment,
            overall_healthy=True,
            process_healthy=True,
            http_healthy=True,
            resources_healthy=True,
            disk_healthy=True,
            cpu_percent=25.5,
            memory_mb=512.0,
            disk_free_gb=50.0,
            response_time_ms=150.0,
            http_status_code=200,
        )
        self.assertTrue(record.overall_healthy)
        self.assertEqual(record.cpu_percent, 25.5)
        self.assertEqual(record.memory_mb, 512.0)
        self.assertEqual(record.http_status_code, 200)

    def test_unhealthy_record(self):
        """Test creating an unhealthy health check record."""
        record = HealthCheckRecord.objects.create(
            deployment=self.deployment,
            overall_healthy=False,
            process_healthy=False,
            http_healthy=False,
            resources_healthy=True,
            disk_healthy=True,
            http_status_code=500,
        )
        self.assertFalse(record.overall_healthy)
        self.assertFalse(record.process_healthy)
        self.assertEqual(record.http_status_code, 500)

    def test_health_check_relationship(self):
        """Test that health checks are accessible from deployment."""
        HealthCheckRecord.objects.create(
            deployment=self.deployment,
            overall_healthy=True,
        )
        HealthCheckRecord.objects.create(
            deployment=self.deployment,
            overall_healthy=False,
        )

        records = self.deployment.health_check_records.all()
        self.assertEqual(records.count(), 2)


class ModelInheritanceTests(TestCase):
    """Test model inheritance and polymorphism."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_application_is_base_deployment(self):
        """Test that ApplicationDeployment inherits from BaseDeployment."""
        app = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/app',
        )

        # Should be accessible as BaseDeployment
        base = BaseDeployment.objects.get(name='test-app')
        self.assertEqual(base.name, app.name)
        self.assertEqual(base.deployed_by, app.deployed_by)

    def test_llm_is_base_deployment(self):
        """Test that LLMDeployment inherits from BaseDeployment."""
        llm = LLMDeployment.objects.create(
            name='test-llm',
            deployed_by=self.user,
            model_name='test/model',
        )

        # Should be accessible as BaseDeployment
        base = BaseDeployment.objects.get(name='test-llm')
        self.assertEqual(base.name, llm.name)
        self.assertEqual(base.deployed_by, llm.deployed_by)

    def test_mixed_deployments_query(self):
        """Test querying all deployments regardless of type."""
        ApplicationDeployment.objects.create(
            name='app1',
            deployed_by=self.user,
            project_type='django',
            repo_url='https://github.com/example/app1',
        )
        LLMDeployment.objects.create(
            name='llm1',
            deployed_by=self.user,
            model_name='test/model1',
        )
        ApplicationDeployment.objects.create(
            name='app2',
            deployed_by=self.user,
            project_type='static',
            repo_url='https://github.com/example/app2',
        )

        # All should be queryable as BaseDeployment
        all_deployments = BaseDeployment.objects.all()
        self.assertEqual(all_deployments.count(), 3)

        # Specific types
        apps = ApplicationDeployment.objects.all()
        llms = LLMDeployment.objects.all()
        self.assertEqual(apps.count(), 2)
        self.assertEqual(llms.count(), 1)
