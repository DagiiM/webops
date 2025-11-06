"""
Enterprise models for WebOps - Organizations, Teams, and RBAC.

Architecture:
- Organization: Top-level tenant (complete isolation)
- Team: Group within organization
- Member: User membership in team/org with role
- Permission: Granular resource-level access control
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.utils import timezone
import uuid

User = get_user_model()


class Organization(models.Model):
    """
    Top-level tenant for complete data isolation.

    Enterprise features:
    - Multi-tenancy with complete isolation
    - Billing per organization
    - Custom branding per org
    - SSO/SAML per org
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, validators=[MinLengthValidator(2)])
    slug = models.SlugField(max_length=255, unique=True, db_index=True)

    # Owner
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='owned_organizations'
    )

    # Settings
    is_active = models.BooleanField(default=True, db_index=True)
    max_members = models.IntegerField(default=5)  # Limit for tier
    max_teams = models.IntegerField(default=3)
    max_deployments = models.IntegerField(default=10)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        return self.name

    def member_count(self):
        """Get current member count."""
        return self.members.filter(is_active=True).count()

    def can_add_member(self):
        """Check if can add more members."""
        return self.member_count() < self.max_members

    def can_add_team(self):
        """Check if can add more teams."""
        return self.teams.filter(is_active=True).count() < self.max_teams


class Team(models.Model):
    """
    Group within organization for collaboration.

    Features:
    - Multiple teams per organization
    - Team-level permissions
    - Resource ownership by team
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teams'
    )

    name = models.CharField(max_length=255, validators=[MinLengthValidator(2)])
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)

    # Settings
    is_active = models.BooleanField(default=True, db_index=True)
    max_members = models.IntegerField(default=10)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_teams'
    )

    class Meta:
        db_table = 'teams'
        ordering = ['organization', 'name']
        unique_together = [('organization', 'slug')]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['organization', 'slug']),
        ]

    def __str__(self):
        return f"{self.organization.name} / {self.name}"

    def member_count(self):
        """Get current member count."""
        return self.members.filter(is_active=True).count()

    def can_add_member(self):
        """Check if can add more members."""
        return self.member_count() < self.max_members


class Role(models.Model):
    """
    Role defines a set of permissions.

    Built-in roles:
    - owner: Full access
    - admin: Administrative access
    - member: Standard access
    - viewer: Read-only access

    Custom roles can be created per organization.
    """

    # Built-in role types
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'
    VIEWER = 'viewer'

    ROLE_CHOICES = [
        (OWNER, 'Owner'),
        (ADMIN, 'Admin'),
        (MEMBER, 'Member'),
        (VIEWER, 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='roles',
        null=True,
        blank=True  # Null for system-wide roles
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)

    # Built-in role or custom
    is_system = models.BooleanField(default=False)
    role_type = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        null=True,
        blank=True
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        unique_together = [('organization', 'slug')]
        indexes = [
            models.Index(fields=['organization', 'slug']),
            models.Index(fields=['is_system']),
        ]

    def __str__(self):
        if self.organization:
            return f"{self.organization.name} / {self.name}"
        return f"System / {self.name}"


class OrganizationMember(models.Model):
    """
    User membership in organization with role.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='organization_members'
    )

    # Status
    is_active = models.BooleanField(default=True, db_index=True)

    # Metadata
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invited_org_members'
    )

    class Meta:
        db_table = 'organization_members'
        unique_together = [('organization', 'user')]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.organization.name} ({self.role.name})"


class TeamMember(models.Model):
    """
    User membership in team with role.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='team_members'
    )

    # Status
    is_active = models.BooleanField(default=True, db_index=True)

    # Metadata
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invited_team_members'
    )

    class Meta:
        db_table = 'team_members'
        unique_together = [('team', 'user')]
        indexes = [
            models.Index(fields=['team', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.team.name} ({self.role.name})"


class Permission(models.Model):
    """
    Granular permission for specific actions on resources.

    Format: <resource>.<action>
    Examples:
    - deployment.create
    - deployment.view
    - deployment.update
    - deployment.delete
    - database.create
    - database.backup
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Permission definition
    resource = models.CharField(max_length=100, db_index=True)  # deployment, database, etc.
    action = models.CharField(max_length=100, db_index=True)     # create, view, update, delete
    code_name = models.CharField(max_length=200, unique=True)    # deployment.create

    description = models.TextField(blank=True)

    # System or custom
    is_system = models.BooleanField(default=True)

    class Meta:
        db_table = 'permissions'
        unique_together = [('resource', 'action')]
        indexes = [
            models.Index(fields=['resource']),
            models.Index(fields=['code_name']),
        ]

    def __str__(self):
        return self.code_name

    def save(self, *args, **kwargs):
        # Auto-generate code_name
        if not self.code_name:
            self.code_name = f"{self.resource}.{self.action}"
        super().save(*args, **kwargs)


class RolePermission(models.Model):
    """
    Maps permissions to roles.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='roles'
    )

    class Meta:
        db_table = 'role_permissions'
        unique_together = [('role', 'permission')]
        indexes = [
            models.Index(fields=['role', 'permission']),
        ]

    def __str__(self):
        return f"{self.role.name}: {self.permission.code_name}"


class ResourcePermission(models.Model):
    """
    Resource-level permission override.

    Allows granting specific permissions on individual resources.
    Example: Grant user X permission to view deployment Y.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='resource_permissions'
    )

    # What
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='resource_grants'
    )

    # On which resource
    resource_type = models.CharField(max_length=100)  # deployment, database, etc.
    resource_id = models.UUIDField()  # ID of the resource

    # Grant or deny
    is_granted = models.BooleanField(default=True)

    # Metadata
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granted_permissions'
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'resource_permissions'
        indexes = [
            models.Index(fields=['user', 'resource_type', 'resource_id']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        grant = "GRANT" if self.is_granted else "DENY"
        return f"{grant} {self.permission.code_name} on {self.resource_type}:{self.resource_id} to {self.user.username}"

    def is_active(self):
        """Check if permission is still active."""
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
