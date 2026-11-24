"""
API models for WebOps.

"API Design" section

This module implements API-specific models:
- API tokens for authentication
- API usage tracking
"""

import secrets
from django.db import models
from django.contrib.auth.models import User
from apps.core.common.models import BaseModel


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


class MCPAccessToken(models.Model):
    """Dedicated, hashed assistant credential; never accepted by the general REST API."""
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="mcp_tokens")
    name = models.CharField(max_length=100)
    digest = models.CharField(max_length=64,unique=True,editable=False)
    can_control = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used = models.DateTimeField(null=True,blank=True)
    revoked_at = models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering = ["-created_at"]


class LLMAccessKey(models.Model):
    """Dedicated, hashed, inference-only key for the public LLM API.

    Unlike APIToken it can only call /api/llm/v1/ (list models, run bounded completions on the
    owner's own running reviewed CPU models). It is never accepted by the REST API, MCP or the UI,
    so a leaked key cannot manage deployments. Only a SHA-256 digest is stored; the key is shown once.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="llm_keys")
    name = models.CharField(max_length=100)
    digest = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.user.username})"


class AIProvider(models.Model):
    """An OpenAI-compatible model a user has configured for WebOps' AI features.

    ``local``: one of the user's own running, reviewed CPU models (served on 127.0.0.1, never leaves the host).
    ``external``: any OpenAI-compatible HTTPS endpoint (OpenAI, OpenRouter, Groq, a self-hosted vLLM...).

    The API key is encrypted at rest and never shown again; only the last four characters are kept as a hint.
    """
    LOCAL = "local"
    EXTERNAL = "external"
    KINDS = [(LOCAL, "Local WebOps model"), (EXTERNAL, "External OpenAI-compatible")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_providers")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KINDS)
    base_url = models.CharField(max_length=300, blank=True)           # external only, e.g. https://api.openai.com/v1
    model = models.CharField(max_length=200, blank=True)              # external: model id; local: deployment name
    api_key_enc = models.TextField(blank=True, editable=False)
    key_hint = models.CharField(max_length=8, blank=True, editable=False)
    allow_private_repos = models.BooleanField(default=False)          # external only: may private repo excerpts be sent?
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    last_ok = models.BooleanField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-is_default", "name"]
        constraints = [models.UniqueConstraint(fields=["user", "name"], name="ai_provider_unique_name_per_user")]

    _PREFIX = "enc1:"

    def set_api_key(self, plain: str) -> None:
        from apps.core.services.security_services import EncryptionService
        plain = (plain or "").strip()
        if not plain:
            self.api_key_enc, self.key_hint = "", ""
            return
        self.api_key_enc = self._PREFIX + EncryptionService.encrypt(plain)
        self.key_hint = plain[-4:]

    def get_api_key(self) -> str:
        """Decrypted key, or '' when none is stored. Raises ValueError if it can no longer be decrypted."""
        if not self.api_key_enc:
            return ""
        from apps.core.services.security_services import EncryptionService
        if not self.api_key_enc.startswith(self._PREFIX):
            raise ValueError("stored key is not in the expected format")
        token = self.api_key_enc[len(self._PREFIX):]
        plain = EncryptionService.decrypt(token)
        if plain == token:  # EncryptionService returns its input when decryption fails
            raise ValueError("stored key could not be decrypted")
        return plain

    @classmethod
    def default_for(cls, user):
        qs = cls.objects.filter(user=user)
        return qs.filter(is_default=True).first() or (qs.first() if qs.count() == 1 else None)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"
