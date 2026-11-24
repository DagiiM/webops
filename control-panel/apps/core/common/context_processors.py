"""
Context processors for WebOps.

Makes branding settings available globally in all templates.
"Django App Structure" section
"""

from apps.core.branding.models import BrandingSettings


def branding(request):
    """
    Add branding settings to template context.

    Makes branding settings available in all templates as 'branding'.
    """
    return {
        'branding': BrandingSettings.get_settings()
    }


# Ordered: the first matching prefix wins, so specific paths sit above general ones.
_NAV_RULES = (
    ('/deployments/llm', 'llm'),
    ('/deployments', 'deployments'),
    ('/databases', 'databases'),
    ('/monitoring/alerts', 'alerts'),
    ('/monitoring/control', 'services'),
    ('/monitoring/restart-policies', 'services'),
    ('/monitoring/configuration', 'services'),
    ('/monitoring/background', 'services'),
    ('/monitoring/celery', 'services'),
    ('/monitoring/service', 'services'),
    ('/monitoring/ssl', 'services'),
    ('/monitoring', 'monitor'),
    ('/automation', 'workflows'),
    ('/auth/integrations', 'integrations'),
    ('/addons', 'addons'),
    ('/compliance', 'compliance'),
    ('/api/tokens', 'tokens'),
    ('/api/mcp', 'assistants'),
    ('/api/ai', 'ai'),
    ('/api/docs', 'docs'),
    ('/auth/2fa', 'two_factor'),
    ('/auth/settings/branding', 'branding'),
    ('/auth/settings', 'settings'),
    ('/trash', 'trash'),
)


def navigation(request):
    """Expose the active sidebar item and a small attention count.

    ``nav_active`` is a key such as ``deployments`` or ``alerts``; the sidebar marks the
    matching item with ``aria-current="page"``. The server decides, so the sidebar does not
    depend on substring checks in the template.
    """
    path = request.path or '/'
    active = 'dashboard' if path in ('/', '/dashboard/') else ''
    if not active:
        for prefix, key in _NAV_RULES:
            if path.startswith(prefix):
                active = key
                break

    attention = 0
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        try:
            from apps.deployments.models import BaseDeployment
            attention = BaseDeployment.objects.filter(
                deployed_by=user, is_deleted=False, status='failed'
            ).count()
        except Exception:  # never let the sidebar break a page
            attention = 0
    return {'nav_active': active, 'nav_attention': attention}
