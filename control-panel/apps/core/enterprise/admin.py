"""
Django admin interface for enterprise models.
"""

from django.contrib import admin
from .models import (
    Organization, Team, Role, OrganizationMember, TeamMember,
    Permission, RolePermission, ResourcePermission
)
from .audit import AuditLog
from .sso import SSOProvider, SSOSession


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'owner', 'is_active', 'member_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'owner__username', 'owner__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'owner')
        }),
        ('Limits', {
            'fields': ('max_members', 'max_teams', 'max_deployments')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'is_active', 'member_count', 'created_at']
    list_filter = ['is_active', 'organization', 'created_at']
    search_fields = ['name', 'slug', 'organization__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'name', 'slug', 'description')
        }),
        ('Settings', {
            'fields': ('is_active', 'max_members')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'role_type', 'is_system', 'created_at']
    list_filter = ['is_system', 'role_type', 'organization']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Show system roles and org-specific roles
        return qs


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'is_active', 'joined_at']
    list_filter = ['is_active', 'organization', 'role', 'joined_at']
    search_fields = ['user__username', 'user__email', 'organization__name']
    readonly_fields = ['id', 'joined_at']


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'team', 'role', 'is_active', 'joined_at']
    list_filter = ['is_active', 'team__organization', 'role', 'joined_at']
    search_fields = ['user__username', 'user__email', 'team__name']
    readonly_fields = ['id', 'joined_at']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['code_name', 'resource', 'action', 'is_system']
    list_filter = ['is_system', 'resource']
    search_fields = ['code_name', 'resource', 'action', 'description']
    readonly_fields = ['id']


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'permission']
    list_filter = ['role__is_system', 'role__organization']
    search_fields = ['role__name', 'permission__code_name']
    readonly_fields = ['id']


@admin.register(ResourcePermission)
class ResourcePermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission', 'resource_type', 'is_granted', 'granted_at']
    list_filter = ['is_granted', 'resource_type', 'granted_at']
    search_fields = ['user__username', 'permission__code_name', 'resource_type']
    readonly_fields = ['id', 'granted_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'action', 'resource_type', 'success', 'timestamp']
    list_filter = ['action', 'resource_type', 'success', 'timestamp']
    search_fields = ['user_email', 'resource_name', 'ip_address']
    readonly_fields = [
        'id', 'user', 'user_email', 'action', 'resource_type',
        'resource_id', 'resource_name', 'organization_id', 'team_id',
        'ip_address', 'user_agent', 'request_path', 'request_method',
        'changes', 'metadata', 'success', 'error_message', 'timestamp'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SSOProvider)
class SSOProviderAdmin(admin.ModelAdmin):
    list_display = ['provider_name', 'organization', 'provider_type', 'is_active', 'created_at']
    list_filter = ['provider_type', 'is_active', 'created_at']
    search_fields = ['provider_name', 'organization__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'organization', 'provider_name', 'provider_type')
        }),
        ('SAML Configuration', {
            'fields': (
                'saml_entity_id', 'saml_sso_url', 'saml_slo_url', 'saml_x509_cert',
                'saml_sp_entity_id', 'saml_acs_url', 'saml_metadata_url'
            ),
            'classes': ('collapse',)
        }),
        ('OAuth/OIDC Configuration', {
            'fields': (
                'oauth_client_id', 'oauth_client_secret',
                'oauth_authorization_url', 'oauth_token_url', 'oauth_userinfo_url'
            ),
            'classes': ('collapse',)
        }),
        ('User Provisioning', {
            'fields': (
                'enable_jit_provisioning', 'default_role_slug',
                'attr_map_email', 'attr_map_first_name', 'attr_map_last_name'
            )
        }),
        ('Settings', {
            'fields': ('is_active', 'force_authn', 'sign_requests')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SSOSession)
class SSOSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'provider', 'authenticated_at', 'expires_at', 'is_active']
    list_filter = ['provider', 'authenticated_at']
    search_fields = ['user__username', 'user__email', 'ip_address']
    readonly_fields = [
        'id', 'user', 'provider', 'saml_session_index', 'saml_name_id',
        'ip_address', 'user_agent', 'authenticated_at', 'expires_at', 'logged_out_at'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
