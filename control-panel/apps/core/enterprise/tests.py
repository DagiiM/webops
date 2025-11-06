"""
Enterprise feature tests.

Tests for:
- Organizations and teams
- Permissions and RBAC
- Audit logging
- Rate limiting
- SSO
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import (
    Organization, Team, Role, OrganizationMember, TeamMember,
    Permission, RolePermission, ResourcePermission
)
from .audit import AuditLog, log_audit, AuditLogQuery
from .permissions import PermissionService, PermissionSeeder
from .ratelimit import RateLimiter, TierLimits
from .sso import SSOProvider, SSOSession, SSOService

User = get_user_model()


class OrganizationTestCase(TestCase):
    """Test organization model and functionality."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )

    def test_create_organization(self):
        """Test organization creation."""
        org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner
        )

        self.assertEqual(org.name, 'Test Org')
        self.assertEqual(org.slug, 'test-org')
        self.assertEqual(org.owner, self.owner)
        self.assertTrue(org.is_active)

    def test_organization_member_limits(self):
        """Test organization member limits."""
        org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner,
            max_members=2
        )

        self.assertTrue(org.can_add_member())
        self.assertEqual(org.member_count(), 0)

    def test_organization_team_limits(self):
        """Test organization team limits."""
        org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner,
            max_teams=3
        )

        self.assertTrue(org.can_add_team())


class TeamTestCase(TestCase):
    """Test team model and functionality."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner
        )

    def test_create_team(self):
        """Test team creation."""
        team = Team.objects.create(
            organization=self.org,
            name='Engineering',
            slug='engineering',
            created_by=self.owner
        )

        self.assertEqual(team.organization, self.org)
        self.assertEqual(team.name, 'Engineering')
        self.assertTrue(team.is_active)

    def test_team_member_limits(self):
        """Test team member limits."""
        team = Team.objects.create(
            organization=self.org,
            name='Engineering',
            slug='engineering',
            max_members=5
        )

        self.assertTrue(team.can_add_member())
        self.assertEqual(team.member_count(), 0)


class PermissionTestCase(TestCase):
    """Test permission system."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@test.com',
            password='testpass123'
        )

        # Seed permissions and roles
        PermissionSeeder.seed_permissions()
        self.roles = PermissionSeeder.seed_roles()

        # Create organization
        self.org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner
        )

        # Add owner to org with owner role
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.owner,
            role=self.roles['owner']
        )

        # Add member to org with member role
        OrganizationMember.objects.create(
            organization=self.org,
            user=self.member,
            role=self.roles['member']
        )

    def test_seed_permissions(self):
        """Test permission seeding."""
        perms = Permission.objects.all()
        self.assertGreater(perms.count(), 0)

        # Check specific permissions
        self.assertTrue(Permission.objects.filter(code_name='deployment.create').exists())
        self.assertTrue(Permission.objects.filter(code_name='database.view').exists())

    def test_seed_roles(self):
        """Test role seeding."""
        self.assertEqual(len(self.roles), 4)
        self.assertIn('owner', self.roles)
        self.assertIn('admin', self.roles)
        self.assertIn('member', self.roles)
        self.assertIn('viewer', self.roles)

    def test_owner_has_all_permissions(self):
        """Test owner has all permissions."""
        service = PermissionService(self.owner)

        self.assertTrue(service.has_permission('deployment.create', organization=self.org))
        self.assertTrue(service.has_permission('database.create', organization=self.org))
        self.assertTrue(service.has_permission('organization.delete', organization=self.org))

    def test_member_has_limited_permissions(self):
        """Test member has limited permissions."""
        service = PermissionService(self.member)

        self.assertTrue(service.has_permission('deployment.create', organization=self.org))
        self.assertTrue(service.has_permission('deployment.view', organization=self.org))
        self.assertFalse(service.has_permission('organization.delete', organization=self.org))

    def test_superuser_has_all_permissions(self):
        """Test superuser bypasses permission checks."""
        superuser = User.objects.create_superuser(
            username='superuser',
            email='superuser@test.com',
            password='testpass123'
        )

        service = PermissionService(superuser)

        self.assertTrue(service.has_permission('deployment.create'))
        self.assertTrue(service.has_permission('organization.delete'))

    def test_resource_permission(self):
        """Test resource-level permissions."""
        # Create a mock deployment object
        class MockDeployment:
            id = '123e4567-e89b-12d3-a456-426614174000'
            organization = None

        deployment = MockDeployment()
        deployment.organization = self.org

        # Grant specific permission to member
        perm = Permission.objects.get(code_name='deployment.delete')
        ResourcePermission.objects.create(
            user=self.member,
            permission=perm,
            resource_type='mockdeployment',  # Must match MockDeployment.__class__.__name__.lower()
            resource_id=deployment.id,
            is_granted=True
        )

        service = PermissionService(self.member)
        self.assertTrue(service.has_resource_permission('deployment.delete', deployment))


class AuditLogTestCase(TestCase):
    """Test audit logging."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.factory = RequestFactory()

    def test_create_audit_log(self):
        """Test audit log creation."""
        log = AuditLog.objects.create(
            user=self.user,
            user_email=self.user.email,
            action=AuditLog.CREATE,
            resource_type='deployment',
            resource_id='123e4567-e89b-12d3-a456-426614174000',
            resource_name='test-deployment',
            success=True
        )

        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action, AuditLog.CREATE)
        self.assertEqual(log.resource_type, 'deployment')
        self.assertTrue(log.success)

    def test_audit_log_immutable(self):
        """Test audit logs are immutable."""
        log = AuditLog.objects.create(
            user=self.user,
            user_email=self.user.email,
            action=AuditLog.CREATE,
            resource_type='deployment',
            success=True
        )

        # Try to update
        with self.assertRaises(ValueError):
            log.action = AuditLog.DELETE
            log.save()

    def test_audit_log_no_delete(self):
        """Test audit logs cannot be deleted."""
        log = AuditLog.objects.create(
            user=self.user,
            user_email=self.user.email,
            action=AuditLog.CREATE,
            resource_type='deployment',
            success=True
        )

        # Try to delete
        with self.assertRaises(ValueError):
            log.delete()

    def test_log_audit_function(self):
        """Test log_audit helper function."""
        request = self.factory.get('/api/deployments/')
        request.user = self.user
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        log_audit(
            user=self.user,
            action=AuditLog.VIEW,
            resource_type='deployment',
            request=request,
            success=True
        )

        logs = AuditLog.objects.filter(user=self.user)
        self.assertEqual(logs.count(), 1)

        log = logs.first()
        self.assertEqual(log.action, AuditLog.VIEW)
        self.assertEqual(log.ip_address, '192.168.1.1')

    def test_audit_query_for_user(self):
        """Test querying audit logs for user."""
        # Create some logs
        for i in range(5):
            AuditLog.objects.create(
                user=self.user,
                user_email=self.user.email,
                action=AuditLog.VIEW,
                resource_type='deployment',
                success=True
            )

        logs = AuditLogQuery.for_user(self.user, days=30)
        self.assertEqual(logs.count(), 5)


class RateLimitTestCase(TestCase):
    """Test rate limiting."""

    def setUp(self):
        self.limiter = RateLimiter()

    def test_rate_limit_allows_within_limit(self):
        """Test rate limit allows requests within limit."""
        key = 'test:user:1'

        # Should allow 10 requests
        for i in range(10):
            allowed, remaining, reset_time = self.limiter.check_limit(key, 10, 60)
            self.assertTrue(allowed)
            self.assertEqual(remaining, 10 - i - 1)

    def test_rate_limit_blocks_over_limit(self):
        """Test rate limit blocks requests over limit."""
        from .ratelimit import RateLimitExceeded

        key = 'test:user:2'

        # Use up limit
        for i in range(10):
            self.limiter.check_limit(key, 10, 60)

        # Next request should be blocked
        with self.assertRaises(RateLimitExceeded):
            self.limiter.check_limit(key, 10, 60)

    def test_tier_limits(self):
        """Test tier-based limits."""
        free_limits = TierLimits.get_limits('free')
        pro_limits = TierLimits.get_limits('pro')

        self.assertEqual(free_limits['api_calls_per_hour'], 100)
        self.assertEqual(pro_limits['api_calls_per_hour'], 10000)
        self.assertGreater(pro_limits['api_calls_per_hour'], free_limits['api_calls_per_hour'])


class SSOTestCase(TestCase):
    """Test SSO functionality."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            slug='test-org',
            owner=self.owner
        )

    def test_create_sso_provider(self):
        """Test SSO provider creation."""
        provider = SSOProvider.objects.create(
            organization=self.org,
            provider_name='Okta',
            provider_type=SSOProvider.SAML,
            saml_entity_id='https://idp.example.com',
            saml_sso_url='https://idp.example.com/sso',
            created_by=self.owner
        )

        self.assertEqual(provider.organization, self.org)
        self.assertEqual(provider.provider_name, 'Okta')
        self.assertTrue(provider.is_active)

    def test_sso_service_enabled(self):
        """Test SSO service enabled check."""
        SSOProvider.objects.create(
            organization=self.org,
            provider_name='Okta',
            provider_type=SSOProvider.SAML,
            created_by=self.owner
        )

        service = SSOService(self.org)
        self.assertTrue(service.is_enabled())

    def test_sso_session_active(self):
        """Test SSO session active check."""
        provider = SSOProvider.objects.create(
            organization=self.org,
            provider_name='Okta',
            provider_type=SSOProvider.SAML,
            created_by=self.owner
        )

        # Active session
        session = SSOSession.objects.create(
            user=self.owner,
            provider=provider,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        self.assertTrue(session.is_active())

        # Expired session
        expired_session = SSOSession.objects.create(
            user=self.owner,
            provider=provider,
            expires_at=timezone.now() - timedelta(hours=1)
        )
        self.assertFalse(expired_session.is_active())

        # Logged out session
        logged_out_session = SSOSession.objects.create(
            user=self.owner,
            provider=provider,
            logged_out_at=timezone.now()
        )
        self.assertFalse(logged_out_session.is_active())
