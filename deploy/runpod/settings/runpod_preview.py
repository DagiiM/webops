"""Settings for the single-pod Runpod deployment (copied into config/ by deploy/runpod/boot.sh)."""
import os

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .settings import *  # noqa: F401,F403

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "webops-pod"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
WEBOPS_RUNTIME = "supervisor"
WEBOPS_WORKLOAD_POLICY = "restricted"
WEBOPS_REQUIRE_DEPLOYMENT_APPROVAL = True
WEBOPS_WORKER_TRUSTED_OWNERS = os.environ.get("WEBOPS_WORKER_TRUSTED_OWNERS", "ifinsta")
WEBOPS_SUPERVISORCTL = os.environ.get("WEBOPS_SUPERVISORCTL", "supervisorctl")

# Managed databases run on the pod's fast local disk and are backed up to the persistent volume
# (see deploy/runpod/boot.sh and docs/databases/managed-databases.md).
WEBOPS_DATABASES_ROOT = os.environ.get("WEBOPS_DATABASES_ROOT", "/var/lib/webops-databases")
WEBOPS_DATABASE_BACKUP_DIR = os.environ.get("WEBOPS_DATABASE_BACKUP_DIR", "/workspace/webops-data/backups/databases")

MIDDLEWARE = [*MIDDLEWARE, "config.runpod_preview.PodAccessMiddleware"]  # noqa: F405

_PUBLIC_PREFIXES = ("/static/", "/api/llm/v1/", "/auth/password-reset/")
_PUBLIC_PATHS = {"/api/mcp/", "/auth/login/", "/auth/register/", "/auth/2fa/verify/"}


class PodAccessMiddleware:
    """Anonymous visitors only reach login/registration and the bearer-token APIs; webhooks are off."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith("/webhooks/"):
            return HttpResponseForbidden("Webhooks are disabled on this deployment.")
        public = (path.startswith(_PUBLIC_PREFIXES) or path in _PUBLIC_PATHS
                  or (path.startswith("/api/") and request.headers.get("Authorization", "").startswith("Bearer ")))
        if not request.user.is_authenticated and not public:
            return redirect("/auth/login/")
        return self.get_response(request)
