"""Compatibility import path for the security-enforced WebOps API client."""
import requests  # noqa: F401 - existing integrations patch requests at this path

from .api import RBACError, Role, Permission, RBACManager, WebOpsAPIClient


class EnhancedWebOpsAPIClient(WebOpsAPIClient):
    """WebOps API client with RBAC, validation and auditing enabled by default."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("enable_security", True)
        super().__init__(*args, **kwargs)
