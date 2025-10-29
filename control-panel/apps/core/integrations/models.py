"""
Integration models for WebOps.

"Database Models" section
Architecture: OAuth connections for GitHub, Hugging Face, and Google.
"""

from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel


class GitHubConnection(BaseModel):
    """
    GitHub OAuth connection for deploying private repositories.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='github_connection'
    )
    github_user_id = models.IntegerField(unique=True)
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=255)  # Encrypted
    refresh_token = models.CharField(max_length=255, blank=True)  # Encrypted
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_github_connection'
        verbose_name = 'GitHub Connection'
        verbose_name_plural = 'GitHub Connections'

    def __str__(self) -> str:
        return f"{self.user.username} → GitHub @{self.username}"


class HuggingFaceConnection(BaseModel):
    """
    Hugging Face API token connection for deploying models and accessing private repos.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='huggingface_connection'
    )
    username = models.CharField(max_length=100)
    access_token = models.CharField(max_length=500)  # Encrypted (Hugging Face tokens are longer)
    token_type = models.CharField(
        max_length=20,
        choices=[
            ('read', 'Read-only'),
            ('write', 'Write'),
            ('fine-grained', 'Fine-grained'),
        ],
        default='read'
    )
    last_synced = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    last_validation_error = models.TextField(blank=True)

    class Meta:
        db_table = 'core_huggingface_connection'
        verbose_name = 'Hugging Face Connection'
        verbose_name_plural = 'Hugging Face Connections'

    def __str__(self) -> str:
        return f"{self.user.username} → Hugging Face @{self.username}"


class GoogleConnection(BaseModel):
    """
    Google OAuth connection for SSO and integrations.

    Inherits from BaseModel to get:
    - created_at, updated_at: Timestamp tracking
    - Soft-delete functionality (is_deleted, deleted_at, deleted_by)
    - Notification dispatch (send_notification, notify_*)
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='google_connection'
    )
    google_user_id = models.CharField(max_length=100, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=150, blank=True)
    access_token = models.CharField(max_length=500)  # Encrypted
    refresh_token = models.CharField(max_length=500, blank=True)  # Encrypted
    id_token = models.CharField(max_length=1024, blank=True)  # Encrypted
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list)
    last_synced = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    last_validation_error = models.TextField(blank=True)

    class Meta:
        db_table = 'core_google_connection'
        verbose_name = 'Google Connection'
        verbose_name_plural = 'Google Connections'

    def __str__(self) -> str:
        return f"{self.user.username} → Google {self.email}"
