"""
API models for WebOps.

Reference: CLAUDE.md "API Design" section

This module implements API-specific models:
- API tokens for authentication
- API usage tracking
"""

import secrets
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import BaseModel


class APIToken(BaseModel):
    """API authentication token."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_tokens'
    )
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this token"
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        editable=False
    )
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Generate token on first save."""
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.user.username})"

    class Meta:
        db_table = 'api_tokens'
        verbose_name = 'API Token'
        verbose_name_plural = 'API Tokens'
        ordering = ['-created_at']
