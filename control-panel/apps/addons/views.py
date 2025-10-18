"""
Views for addon management.

Provides UI for viewing, enabling, and disabling addons.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Addon
from .registry import hook_registry


@login_required
def addons_list(request):
    """Display list of all addons with their status and metrics."""
    addons = Addon.objects.all().order_by('name')

    # Calculate statistics
    enabled_count = addons.filter(enabled=True).count()
    disabled_count = addons.filter(enabled=False).count()

    # Get hook counts for each addon
    addon_hooks = {}
    for addon in addons:
        if addon.enabled:
            hook_count = 0
            for event in hook_registry.hooks.keys():
                hooks = [h for h in hook_registry.get_hooks(event) if h.addon_name == addon.name]
                hook_count += len(hooks)
            addon_hooks[addon.name] = hook_count
        else:
            addon_hooks[addon.name] = 0

    context = {
        'addons': addons,
        'enabled_count': enabled_count,
        'disabled_count': disabled_count,
        'total_count': addons.count(),
        'addon_hooks': addon_hooks,
    }

    return render(request, 'addons/list.html', context)


@login_required
@require_http_methods(["POST"])
def addon_toggle(request, addon_name):
    """Toggle an addon's enabled status."""
    addon = get_object_or_404(Addon, name=addon_name)

    # Toggle enabled status
    addon.enabled = not addon.enabled
    addon.save()

    action = "enabled" if addon.enabled else "disabled"
    messages.success(
        request,
        f'Addon "{addon.name}" has been {action}. '
        'Restart WebOps for changes to take effect.'
    )

    return redirect('addons:addons_list')


@login_required
@require_http_methods(["POST"])
def addon_enable(request, addon_name):
    """Enable a specific addon."""
    addon = get_object_or_404(Addon, name=addon_name)

    if addon.enabled:
        messages.info(request, f'Addon "{addon.name}" is already enabled.')
    else:
        addon.enabled = True
        addon.save()
        messages.success(
            request,
            f'Addon "{addon.name}" has been enabled. '
            'Restart WebOps for changes to take effect.'
        )

    return redirect('addons:addons_list')


@login_required
@require_http_methods(["POST"])
def addon_disable(request, addon_name):
    """Disable a specific addon."""
    addon = get_object_or_404(Addon, name=addon_name)

    if not addon.enabled:
        messages.info(request, f'Addon "{addon.name}" is already disabled.')
    else:
        addon.enabled = False
        addon.save()
        messages.warning(
            request,
            f'Addon "{addon.name}" has been disabled. '
            'Restart WebOps for changes to take effect.'
        )

    return redirect('addons:addons_list')


@login_required
def addon_detail(request, addon_name):
    """Display detailed information about a specific addon."""
    addon = get_object_or_404(Addon, name=addon_name)

    # Get registered hooks for this addon
    registered_hooks = {}
    if addon.enabled:
        for event in hook_registry.hooks.keys():
            hooks = [h for h in hook_registry.get_hooks(event) if h.addon_name == addon.name]
            if hooks:
                registered_hooks[event] = hooks

    # Calculate success rate
    total_runs = addon.success_count + addon.failure_count
    success_rate = (addon.success_count / total_runs * 100) if total_runs > 0 else 0

    context = {
        'addon': addon,
        'registered_hooks': registered_hooks,
        'total_runs': total_runs,
        'success_rate': success_rate,
    }

    return render(request, 'addons/detail.html', context)


@login_required
@require_http_methods(["POST"])
def addon_toggle_ajax(request, addon_name):
    """AJAX endpoint to toggle addon status without page reload."""
    addon = get_object_or_404(Addon, name=addon_name)

    # Toggle enabled status
    addon.enabled = not addon.enabled
    addon.save()

    action = "enabled" if addon.enabled else "disabled"

    return JsonResponse({
        'success': True,
        'enabled': addon.enabled,
        'message': f'Addon "{addon.name}" has been {action}. Restart WebOps for changes to take effect.',
        'action': action
    })