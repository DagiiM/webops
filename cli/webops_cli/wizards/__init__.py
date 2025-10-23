"""WebOps CLI Wizards Package.

This package contains interactive wizards for various WebOps operations.
"""

# Lazy imports to avoid dependency issues during module loading
def __getattr__(name):
    if name == 'InteractiveWizard':
        from .wizards import InteractiveWizard
        return InteractiveWizard
    elif name == 'SetupWizard':
        from .wizards import SetupWizard
        return SetupWizard
    elif name == 'DeploymentWizard':
        from .deployment_wizard import DeploymentWizard
        return DeploymentWizard
    elif name == 'TroubleshootingWizard':
        from .troubleshooting_wizard import TroubleshootingWizard
        return TroubleshootingWizard
    else:
        raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    'InteractiveWizard',
    'SetupWizard',
    'DeploymentWizard',
    'TroubleshootingWizard'
]