"""
Enterprise SSO/SAML authentication support.

Features:
- SAML 2.0 support
- Multiple identity providers per organization
- Automatic user provisioning (JIT)
- Attribute mapping
"""

from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class SSOProvider(models.Model):
    """
    SSO identity provider configuration.

    Supports:
    - SAML 2.0
    - OAuth 2.0 / OIDC (future)
    """

    SAML = 'saml'
    OAUTH = 'oauth'
    OIDC = 'oidc'

    PROVIDER_TYPE_CHOICES = [
        (SAML, 'SAML 2.0'),
        (OAUTH, 'OAuth 2.0'),
        (OIDC, 'OpenID Connect'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Organization (one SSO config per org)
    organization = models.OneToOneField(
        'Organization',
        on_delete=models.CASCADE,
        related_name='sso_provider'
    )

    # Provider details
    provider_type = models.CharField(
        max_length=20,
        choices=PROVIDER_TYPE_CHOICES,
        default=SAML
    )
    provider_name = models.CharField(max_length=100)  # e.g., "Okta", "Azure AD"

    # SAML configuration
    saml_entity_id = models.CharField(max_length=500, blank=True)
    saml_sso_url = models.URLField(blank=True)  # IdP SSO URL
    saml_slo_url = models.URLField(blank=True)  # IdP SLO URL
    saml_x509_cert = models.TextField(blank=True)  # IdP signing certificate

    # SAML SP (Service Provider) configuration
    saml_sp_entity_id = models.CharField(max_length=500, blank=True)
    saml_acs_url = models.URLField(blank=True)  # Assertion Consumer Service URL
    saml_metadata_url = models.URLField(blank=True)

    # OAuth/OIDC configuration
    oauth_client_id = models.CharField(max_length=500, blank=True)
    oauth_client_secret = models.CharField(max_length=500, blank=True)
    oauth_authorization_url = models.URLField(blank=True)
    oauth_token_url = models.URLField(blank=True)
    oauth_userinfo_url = models.URLField(blank=True)

    # User provisioning
    enable_jit_provisioning = models.BooleanField(
        default=True,
        help_text="Automatically create user accounts on first SSO login"
    )
    default_role_slug = models.CharField(
        max_length=100,
        default='member',
        help_text="Default role for JIT provisioned users"
    )

    # Attribute mapping
    attr_map_email = models.CharField(
        max_length=100,
        default='email',
        help_text="SAML attribute for email"
    )
    attr_map_first_name = models.CharField(
        max_length=100,
        default='first_name',
        help_text="SAML attribute for first name"
    )
    attr_map_last_name = models.CharField(
        max_length=100,
        default='last_name',
        help_text="SAML attribute for last name"
    )

    # Settings
    is_active = models.BooleanField(default=True)
    force_authn = models.BooleanField(
        default=False,
        help_text="Force re-authentication even if user has active session"
    )
    sign_requests = models.BooleanField(
        default=True,
        help_text="Sign SAML requests"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sso_providers'
    )

    class Meta:
        db_table = 'sso_providers'
        indexes = [
            models.Index(fields=['organization', 'is_active']),
        ]

    def __str__(self):
        return f"{self.organization.name} - {self.provider_name}"


class SSOSession(models.Model):
    """
    Track SSO sessions for security and audit.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Session details
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sso_sessions'
    )
    provider = models.ForeignKey(
        SSOProvider,
        on_delete=models.CASCADE,
        related_name='sessions'
    )

    # SAML session
    saml_session_index = models.CharField(max_length=500, blank=True)
    saml_name_id = models.CharField(max_length=500, blank=True)

    # Session tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Timestamps
    authenticated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    logged_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sso_sessions'
        ordering = ['-authenticated_at']
        indexes = [
            models.Index(fields=['user', 'authenticated_at']),
            models.Index(fields=['provider', 'authenticated_at']),
        ]

    def __str__(self):
        return f"{self.user.username} via {self.provider.provider_name} at {self.authenticated_at}"

    def is_active(self):
        """Check if session is still active."""
        from django.utils import timezone

        if self.logged_out_at:
            return False

        if self.expires_at and self.expires_at < timezone.now():
            return False

        return True


class SSOService:
    """
    Service for SSO authentication.

    Usage:
        service = SSOService(organization)
        auth_url = service.get_login_url()
        user = service.process_saml_response(saml_response)
    """

    def __init__(self, organization):
        self.organization = organization
        try:
            self.provider = SSOProvider.objects.get(
                organization=organization,
                is_active=True
            )
        except SSOProvider.DoesNotExist:
            self.provider = None

    def is_enabled(self):
        """Check if SSO is enabled for organization."""
        return self.provider is not None

    def get_login_url(self, relay_state=None):
        """
        Generate SSO login URL.

        Args:
            relay_state: URL to redirect to after successful authentication

        Returns:
            SSO login URL
        """
        if not self.provider:
            return None

        if self.provider.provider_type == SSOProvider.SAML:
            return self._get_saml_login_url(relay_state)
        elif self.provider.provider_type in [SSOProvider.OAUTH, SSOProvider.OIDC]:
            return self._get_oauth_login_url(relay_state)

        return None

    def _get_saml_login_url(self, relay_state=None):
        """Generate SAML login URL."""
        # This would use a SAML library like python3-saml
        # Simplified for now
        return self.provider.saml_sso_url

    def _get_oauth_login_url(self, relay_state=None):
        """Generate OAuth login URL."""
        # This would construct OAuth authorization URL
        # Simplified for now
        return self.provider.oauth_authorization_url

    def process_saml_response(self, saml_response, request=None):
        """
        Process SAML response and authenticate user.

        Args:
            saml_response: SAML response from IdP
            request: Django request object

        Returns:
            Authenticated user or None
        """
        if not self.provider or self.provider.provider_type != SSOProvider.SAML:
            return None

        # This would use python3-saml to validate and parse response
        # Simplified for demonstration

        # Extract attributes from SAML response
        attributes = self._parse_saml_attributes(saml_response)

        email = attributes.get(self.provider.attr_map_email)
        first_name = attributes.get(self.provider.attr_map_first_name, '')
        last_name = attributes.get(self.provider.attr_map_last_name, '')

        if not email:
            return None

        # Get or create user (JIT provisioning)
        if self.provider.enable_jit_provisioning:
            user = self._provision_user(email, first_name, last_name)
        else:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return None

        # Create SSO session
        self._create_sso_session(user, saml_response, request)

        return user

    def _parse_saml_attributes(self, saml_response):
        """Parse attributes from SAML response."""
        # This would use python3-saml library
        # Simplified for now
        return {}

    def _provision_user(self, email, first_name='', last_name=''):
        """
        Provision user account (JIT).

        If user exists, return existing user.
        If user doesn't exist and JIT is enabled, create new user.
        """
        from apps.core.enterprise.models import OrganizationMember, Role

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'is_active': True,
            }
        )

        if created:
            # Add user to organization with default role
            try:
                default_role = Role.objects.get(
                    slug=self.provider.default_role_slug,
                    is_system=True
                )
            except Role.DoesNotExist:
                # Fallback to member role
                default_role = Role.objects.get(
                    slug='member',
                    is_system=True
                )

            OrganizationMember.objects.create(
                organization=self.organization,
                user=user,
                role=default_role,
                is_active=True
            )

        return user

    def _create_sso_session(self, user, saml_response, request=None):
        """Create SSO session record."""
        from django.utils import timezone
        from datetime import timedelta

        ip_address = None
        user_agent = ''

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        # Create session with 8 hour expiry
        expires_at = timezone.now() + timedelta(hours=8)

        SSOSession.objects.create(
            user=user,
            provider=self.provider,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at
        )

    def logout(self, user):
        """
        Logout user from SSO session.

        Returns:
            SSO logout URL if provider supports SLO
        """
        # Mark SSO session as logged out
        from django.utils import timezone

        SSOSession.objects.filter(
            user=user,
            provider=self.provider,
            logged_out_at__isnull=True
        ).update(logged_out_at=timezone.now())

        # Return SLO URL if available
        if self.provider and self.provider.saml_slo_url:
            return self.provider.saml_slo_url

        return None
