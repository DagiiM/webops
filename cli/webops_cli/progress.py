"""Backwards compatible progress API for the WebOps CLI.

The current implementation is in webops_cli.ui.progress.  Keep the legacy
import path operational for older CLI integrations and test consumers.
"""
import time  # legacy patch target
from .ui.progress import (  # noqa: F401
    show_progress, show_step_progress, simulate_long_operation
)
from .ui.progress import ProgressManager as _ProgressManager
from .ui.progress import StatusDisplay as _StatusDisplay
from .ui.progress import console as console


class _LegacyConsoleMixin:
    @property
    def console(self):
        return console

    @console.setter
    def console(self, value):
        # Use the module console dynamically so patched CLI output is captured.
        pass


class ProgressManager(_LegacyConsoleMixin, _ProgressManager):
    pass


class StatusDisplay(_LegacyConsoleMixin, _StatusDisplay):
    pass
