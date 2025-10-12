"""
Context processors for WebOps.

Makes branding settings available globally in all templates.
Reference: CLAUDE.md "Django App Structure" section
"""

from apps.core.models import BrandingSettings


def branding(request):
    """
    Add branding settings to template context.

    Makes branding settings available in all templates as 'branding'.
    """
    return {
        'branding': BrandingSettings.get_settings()
    }
