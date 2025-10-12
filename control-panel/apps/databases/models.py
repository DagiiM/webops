"""
Database models for WebOps.

Reference: CLAUDE.md "Database Models" section
"""

from django.db import models
from apps.core.models import BaseModel
from apps.deployments.models import Deployment


class Database(BaseModel):
    """PostgreSQL database credentials."""

    name = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=500)  # Encrypted
    host = models.CharField(max_length=255, default='localhost')
    port = models.IntegerField(default=5432)
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name='databases',
        null=True,
        blank=True
    )

    def __str__(self) -> str:
        return self.name

    def get_connection_string(self, decrypted_password: str) -> str:
        """Generate PostgreSQL connection string."""
        return f"postgresql://{self.username}:{decrypted_password}@{self.host}:{self.port}/{self.name}"

    class Meta:
        db_table = 'databases'
        verbose_name = 'Database'
        verbose_name_plural = 'Databases'