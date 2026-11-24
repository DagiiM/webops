"""Optional runtime selection. Systemd remains the default."""
import os
from django.conf import settings

def portable_runtime():
    name = getattr(settings, "WEBOPS_RUNTIME", os.getenv("WEBOPS_RUNTIME", "systemd"))
    if name == "systemd":
        return None
    if name == "supervisor":
        from .supervisor_adapter import SupervisorRuntime
        return SupervisorRuntime()
    raise ValueError("Unknown WebOps runtime: " + name)
