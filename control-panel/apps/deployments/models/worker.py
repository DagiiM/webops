"""Remote build workers and the jobs they run.

A worker is a separate machine that builds approved projects, so repository code never runs on the panel's
own host. Workers only ever connect OUT to the panel (they poll), authenticate with a hashed bearer token and
can do nothing but claim queued jobs and report on them.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .application import ApplicationDeployment


class WorkerNode(models.Model):
    ONLINE_SECONDS = 90

    name = models.CharField(max_length=60, unique=True)
    digest = models.CharField(max_length=64, unique=True, editable=False)      # SHA-256 of the token; the token is shown once
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    info = models.JSONField(default=dict, blank=True)                           # cpus, memory, agent version, isolation level

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_online(self):
        return bool(self.revoked_at is None and self.last_seen and timezone.now() - self.last_seen < timedelta(seconds=self.ONLINE_SECONDS))


class BuildJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CLAIMED = "claimed", "Claimed"
        BUILDING = "building", "Building"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE = (Status.QUEUED, Status.CLAIMED, Status.BUILDING)
    MAX_LOG = 200_000
    MAX_ATTEMPTS = 3

    deployment = models.ForeignKey(ApplicationDeployment, on_delete=models.CASCADE, related_name="build_jobs")
    kind = models.CharField(max_length=20)                                      # rust | node | python (fixed catalog)
    commit = models.CharField(max_length=40)                                    # the exact commit that is built
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    worker = models.ForeignKey(WorkerNode, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    limits = models.JSONField(default=dict)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    log = models.TextField(blank=True)
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"job {self.pk} ({self.kind}, {self.status})"
