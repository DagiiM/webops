"""
Enterprise permission service for granular RBAC.

Features:
- Efficient permission checking (with caching)
- Role-based permissions
- Resource-level permissions
- Permission inheritance
"""

from django.core.cache import cache
from django.contrib.auth import get_user_model
from .models import (
    Organization, Team, OrganizationMember, TeamMember,
    Role, Permission, RolePermission, ResourcePermission
)

User = get_user_model()


class PermissionService:
    """
    Service for checking user permissions.

    Usage:
        service = PermissionService(user)
        if service.has_permission('deployment.create', organization=org):
            # Allow action

        if service.has_resource_permission('deployment.view', deployment):
            # Allow viewing deployment
    """

    def __init__(self, user):
        self.user = user

    def has_permission(self, permission_code, organization=None, team=None):
        """
        Check if user has permission in context.

        Args:
            permission_code: Permission code (e.g., 'deployment.create')
            organization: Organization context
            team: Team context

        Returns:
            Boolean indicating if user has permission
        """

        # System admins have all permissions
        if self.user.is_superuser:
            return True

        # Check cache first
        cache_key = f"perm:{self.user.id}:{permission_code}:{organization.id if organization else 'none'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Get user's roles
        roles = self._get_user_roles(organization, team)

        # Check if any role has the permission
        has_perm = RolePermission.objects.filter(
            role__in=roles,
            permission__code_name=permission_code
        ).exists()

        # Cache result (5 minutes)
        cache.set(cache_key, has_perm, 300)

        return has_perm

    def has_resource_permission(self, permission_code, resource):
        """
        Check if user has permission on specific resource.

        Args:
            permission_code: Permission code (e.g., 'deployment.view')
            resource: Resource object (deployment, database, etc.)

        Returns:
            Boolean indicating if user has permission
        """

        # System admins have all permissions
        if self.user.is_superuser:
            return True

        # Get resource type and ID
        resource_type = resource.__class__.__name__.lower()
        resource_id = resource.id

        # Convert resource_id to UUID if it's a string
        import uuid
        if isinstance(resource_id, str):
            try:
                resource_id = uuid.UUID(resource_id)
            except (ValueError, AttributeError):
                pass

        # Check explicit resource permission
        resource_perm = ResourcePermission.objects.filter(
            user=self.user,
            permission__code_name=permission_code,
            resource_type=resource_type,
            resource_id=resource_id
        ).first()

        if resource_perm:
            # Check if active
            if resource_perm.is_active():
                return resource_perm.is_granted

        # Fall back to role-based check
        org = self._get_resource_organization(resource)
        team = self._get_resource_team(resource)

        return self.has_permission(permission_code, organization=org, team=team)

    def _get_user_roles(self, organization=None, team=None):
        """Get all roles for user in context."""
        roles = []

        if organization:
            # Organization role
            org_member = OrganizationMember.objects.filter(
                organization=organization,
                user=self.user,
                is_active=True
            ).select_related('role').first()

            if org_member:
                roles.append(org_member.role)

        if team:
            # Team role
            team_member = TeamMember.objects.filter(
                team=team,
                user=self.user,
                is_active=True
            ).select_related('role').first()

            if team_member:
                roles.append(team_member.role)

        return roles

    def _get_resource_organization(self, resource):
        """Get organization for resource."""
        if hasattr(resource, 'organization'):
            return resource.organization
        if hasattr(resource, 'team') and hasattr(resource.team, 'organization'):
            return resource.team.organization
        return None

    def _get_resource_team(self, resource):
        """Get team for resource."""
        if hasattr(resource, 'team'):
            return resource.team
        return None

    def get_accessible_organizations(self):
        """Get all organizations user has access to."""
        return Organization.objects.filter(
            members__user=self.user,
            members__is_active=True
        ).distinct()

    def get_accessible_teams(self, organization=None):
        """Get all teams user has access to."""
        query = Team.objects.filter(
            members__user=self.user,
            members__is_active=True
        )

        if organization:
            query = query.filter(organization=organization)

        return query.distinct()

    @staticmethod
    def clear_user_cache(user_id):
        """Clear permission cache for user."""
        # This would need a more sophisticated cache key pattern
        # For now, using cache.clear() on user permission changes
        pass


def require_permission(permission_code, resource_param=None):
    """
    Decorator to require permission for view.

    Usage:
        @require_permission('deployment.view')
        def view_deployment(request, deployment_id):
            ...

        @require_permission('deployment.delete', resource_param='deployment')
        def delete_deployment(request, deployment):
            ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            from django.core.exceptions import PermissionDenied

            service = PermissionService(request.user)

            # Check resource-level permission if resource provided
            if resource_param and resource_param in kwargs:
                resource = kwargs[resource_param]
                if not service.has_resource_permission(permission_code, resource):
                    raise PermissionDenied(f"You don't have permission to {permission_code} on this resource")
            else:
                # Check general permission
                org = kwargs.get('organization')
                team = kwargs.get('team')
                if not service.has_permission(permission_code, organization=org, team=team):
                    raise PermissionDenied(f"You don't have permission to {permission_code}")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


class PermissionSeeder:
    """
    Utility to seed default permissions and roles.

    Usage:
        PermissionSeeder.seed_permissions()
        PermissionSeeder.seed_roles()
    """

    @staticmethod
    def seed_permissions():
        """Create default system permissions."""
        permissions = [
            # Deployment permissions
            ('deployment', 'create', 'Create deployments'),
            ('deployment', 'view', 'View deployments'),
            ('deployment', 'update', 'Update deployments'),
            ('deployment', 'delete', 'Delete deployments'),
            ('deployment', 'deploy', 'Trigger deployment'),
            ('deployment', 'rollback', 'Rollback deployment'),
            ('deployment', 'logs', 'View deployment logs'),

            # Database permissions
            ('database', 'create', 'Create databases'),
            ('database', 'view', 'View databases'),
            ('database', 'update', 'Update databases'),
            ('database', 'delete', 'Delete databases'),
            ('database', 'backup', 'Backup databases'),
            ('database', 'restore', 'Restore databases'),
            ('database', 'credentials', 'View database credentials'),

            # Team permissions
            ('team', 'create', 'Create teams'),
            ('team', 'view', 'View teams'),
            ('team', 'update', 'Update teams'),
            ('team', 'delete', 'Delete teams'),
            ('team', 'invite', 'Invite team members'),
            ('team', 'remove', 'Remove team members'),

            # Organization permissions
            ('organization', 'view', 'View organization'),
            ('organization', 'update', 'Update organization'),
            ('organization', 'delete', 'Delete organization'),
            ('organization', 'billing', 'Manage billing'),
            ('organization', 'settings', 'Manage settings'),

            # Monitoring permissions
            ('monitoring', 'view', 'View monitoring data'),
            ('monitoring', 'alerts', 'Manage alerts'),

            # Audit permissions
            ('audit', 'view', 'View audit logs'),
            ('audit', 'export', 'Export audit logs'),
        ]

        created_count = 0
        for resource, action, description in permissions:
            permission, created = Permission.objects.get_or_create(
                resource=resource,
                action=action,
                defaults={
                    'description': description,
                    'is_system': True
                }
            )
            if created:
                created_count += 1

        return created_count

    @staticmethod
    def seed_roles():
        """Create default system roles."""
        # Owner role (full access)
        owner_role, created = Role.objects.get_or_create(
            slug='owner',
            is_system=True,
            defaults={
                'name': 'Owner',
                'description': 'Full access to all resources',
                'role_type': Role.OWNER
            }
        )

        if created:
            # Grant all permissions to owner
            permissions = Permission.objects.all()
            for perm in permissions:
                RolePermission.objects.get_or_create(
                    role=owner_role,
                    permission=perm
                )

        # Admin role (administrative access)
        admin_role, created = Role.objects.get_or_create(
            slug='admin',
            is_system=True,
            defaults={
                'name': 'Admin',
                'description': 'Administrative access',
                'role_type': Role.ADMIN
            }
        )

        if created:
            # Grant most permissions except delete org, billing
            permissions = Permission.objects.exclude(
                code_name__in=['organization.delete', 'organization.billing']
            )
            for perm in permissions:
                RolePermission.objects.get_or_create(
                    role=admin_role,
                    permission=perm
                )

        # Member role (standard access)
        member_role, created = Role.objects.get_or_create(
            slug='member',
            is_system=True,
            defaults={
                'name': 'Member',
                'description': 'Standard member access',
                'role_type': Role.MEMBER
            }
        )

        if created:
            # Grant create, view, update permissions
            permissions = Permission.objects.filter(
                action__in=['create', 'view', 'update', 'deploy', 'logs']
            )
            for perm in permissions:
                RolePermission.objects.get_or_create(
                    role=member_role,
                    permission=perm
                )

        # Viewer role (read-only)
        viewer_role, created = Role.objects.get_or_create(
            slug='viewer',
            is_system=True,
            defaults={
                'name': 'Viewer',
                'description': 'Read-only access',
                'role_type': Role.VIEWER
            }
        )

        if created:
            # Grant only view permissions
            permissions = Permission.objects.filter(
                action='view'
            )
            for perm in permissions:
                RolePermission.objects.get_or_create(
                    role=viewer_role,
                    permission=perm
                )

        return {
            'owner': owner_role,
            'admin': admin_role,
            'member': member_role,
            'viewer': viewer_role
        }
