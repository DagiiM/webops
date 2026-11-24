"""Explicit deployment policy. Restricted hosts must not execute repository code."""
import os
from django.conf import settings

def restricted():
    return getattr(settings,"WEBOPS_WORKLOAD_POLICY",os.getenv("WEBOPS_WORKLOAD_POLICY","trusted"))!="trusted"

def executable_block_reason():
    return "Executable application builds require a separate isolated worker. This host supports static publication and reviewed CPU models only."

def sandbox_ready():
    from .sandbox import available
    return available() if restricted() else False

def application_allowed(deployment):
    return not restricted() or deployment.static_only
