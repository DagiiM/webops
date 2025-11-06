"""
Tests for ownership verification decorators.

Tests the security decorators that enforce resource ownership.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from apps.core.security.decorators import (
    require_resource_ownership,
    require_related_ownership,
    api_require_ownership,
    superuser_required
)
from apps.deployments.models import ApplicationDeployment
from apps.databases.models import Database


class OwnershipDecoratorTests(TestCase):
    """Test ownership verification decorators."""

    def setUp(self):
        """Set up test users and resources."""
        self.factory = RequestFactory()

        # Create test users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

    def test_require_resource_ownership_allows_owner(self):
        """Test that owner can access their own resource."""
        # Create a deployment owned by user1
        deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user1,
            repo_url='https://github.com/test/repo',
            port=8000
        )

        # Create a view decorated with ownership requirement
        @require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def test_view(request, pk):
            return "Success"

        # Create request from owner
        request = self.factory.get(f'/deployment/{deployment.pk}/')
        request.user = self.user1

        # Should succeed
        result = test_view(request, pk=deployment.pk)
        self.assertEqual(result, "Success")

    def test_require_resource_ownership_denies_non_owner(self):
        """Test that non-owner cannot access resource."""
        # Create a deployment owned by user1
        deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user1,
            repo_url='https://github.com/test/repo',
            port=8000
        )

        # Create a view decorated with ownership requirement
        @require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def test_view(request, pk):
            return "Success"

        # Create request from different user
        request = self.factory.get(f'/deployment/{deployment.pk}/')
        request.user = self.user2

        # Should raise PermissionDenied
        with self.assertRaises(PermissionDenied):
            test_view(request, pk=deployment.pk)

    def test_require_related_ownership_allows_owner(self):
        """Test that owner can access related resource."""
        # Create a deployment owned by user1
        deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user1,
            repo_url='https://github.com/test/repo',
            port=8000
        )

        # Create a database linked to that deployment
        database = Database.objects.create(
            name='test_db',
            deployment=deployment,
            db_type='postgresql',
            port=5432,
            host='localhost',
            username='testuser',
            password='testpass'
        )

        # Create a view decorated with related ownership requirement
        @require_related_ownership(Database, relation_path='deployment__deployed_by')
        def test_view(request, pk):
            return "Success"

        # Create request from owner
        request = self.factory.get(f'/database/{database.pk}/')
        request.user = self.user1

        # Should succeed
        result = test_view(request, pk=database.pk)
        self.assertEqual(result, "Success")

    def test_require_related_ownership_denies_non_owner(self):
        """Test that non-owner cannot access related resource."""
        # Create a deployment owned by user1
        deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user1,
            repo_url='https://github.com/test/repo',
            port=8000
        )

        # Create a database linked to that deployment
        database = Database.objects.create(
            name='test_db',
            deployment=deployment,
            db_type='postgresql',
            port=5432,
            host='localhost',
            username='testuser',
            password='testpass'
        )

        # Create a view decorated with related ownership requirement
        @require_related_ownership(Database, relation_path='deployment__deployed_by')
        def test_view(request, pk):
            return "Success"

        # Create request from different user
        request = self.factory.get(f'/database/{database.pk}/')
        request.user = self.user2

        # Should raise PermissionDenied
        with self.assertRaises(PermissionDenied):
            test_view(request, pk=database.pk)

    def test_api_require_ownership_returns_json_error(self):
        """Test that API decorator returns JSON error for non-owner."""
        # Create a deployment owned by user1
        deployment = ApplicationDeployment.objects.create(
            name='test-app',
            deployed_by=self.user1,
            repo_url='https://github.com/test/repo',
            port=8000
        )

        # Create an API view decorated with ownership requirement
        @api_require_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def test_api_view(request, pk):
            return JsonResponse({'status': 'success'})

        # Create request from different user
        request = self.factory.get(f'/api/deployment/{deployment.pk}/')
        request.user = self.user2

        # Should return JSON error response
        response = test_api_view(request, pk=deployment.pk)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)

    def test_superuser_required_allows_superuser(self):
        """Test that superuser can access superuser-only view."""
        @superuser_required
        def test_view(request):
            return "Success"

        request = self.factory.get('/admin/panel/')
        request.user = self.superuser

        result = test_view(request)
        self.assertEqual(result, "Success")

    def test_superuser_required_denies_regular_user(self):
        """Test that regular user cannot access superuser-only view."""
        @superuser_required
        def test_view(request):
            return "Success"

        request = self.factory.get('/admin/panel/')
        request.user = self.user1

        with self.assertRaises(PermissionDenied):
            test_view(request)

    def test_ownership_decorator_with_nonexistent_resource(self):
        """Test that decorator properly handles nonexistent resources."""
        @require_resource_ownership(ApplicationDeployment, ownership_field='deployed_by')
        def test_view(request, pk):
            return "Success"

        request = self.factory.get('/deployment/99999/')
        request.user = self.user1

        # Should raise PermissionDenied (not reveal if resource exists)
        with self.assertRaises(PermissionDenied):
            test_view(request, pk=99999)
