"""
Context processors for addon system.

Makes enabled addons and their capabilities available in all templates.
"""

from typing import Dict, Any
from django.http import HttpRequest
from .models import Addon


def enabled_addons(request: HttpRequest) -> Dict[str, Any]:
    """
    Add enabled addons information to template context.

    This allows templates to conditionally show features based on
    enabled addons.

    Usage in templates:
        {% if 'docker' in enabled_addon_names %}
            <!-- Show Docker options -->
        {% endif %}

        {% if 'container_management' in addon_capabilities %}
            <!-- Show container management features -->
        {% endif %}
    """
    try:
        # Get all enabled addons
        addons = Addon.objects.filter(enabled=True).values('name', 'capabilities')

        # Create a set of enabled addon names for quick lookup
        addon_names = {addon['name'] for addon in addons}

        # Collect all capabilities from enabled addons
        capabilities = set()
        for addon in addons:
            if addon['capabilities']:
                capabilities.update(addon['capabilities'])

        # Create a dictionary for easy template access
        addons_dict = {}
        for addon in Addon.objects.filter(enabled=True):
            addons_dict[addon.name] = {
                'enabled': True,
                'version': addon.version,
                'capabilities': addon.capabilities or [],
            }

        return {
            'enabled_addon_names': addon_names,
            'addon_capabilities': capabilities,
            'enabled_addons': addons_dict,
        }
    except Exception:
        # If database is not ready or any error occurs, return empty context
        return {
            'enabled_addon_names': set(),
            'addon_capabilities': set(),
            'enabled_addons': {},
        }
