"""
Views for addon management.

Provides UI for viewing, enabling, and disabling addons.
Supports both application and system addons through unified interface.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Addon, SystemAddon
from .registry import event_registry


@login_required
def addons_list(request):
    """Display list of all addons (both application and system) with their status and metrics."""
    # Get application addons
    app_addons = Addon.objects.all().order_by('name')

    # Get system addons
    system_addons = SystemAddon.objects.all().order_by('display_name')

    # Calculate statistics
    app_enabled = app_addons.filter(enabled=True).count()
    app_disabled = app_addons.filter(enabled=False).count()

    system_installed = system_addons.filter(status='installed').count()
    system_healthy = system_addons.filter(health='healthy').count()

    # Get hook counts for application addons
    addon_hooks = {}
    for addon in app_addons:
        if addon.enabled:
            hook_count = 0
            for event in event_registry.hooks.keys():
                hooks = [h for h in event_registry.get_hooks(event) if h.addon_name == addon.name]
                hook_count += len(hooks)
            addon_hooks[addon.name] = hook_count
        else:
            addon_hooks[addon.name] = 0

    # Combine addons for display
    combined_addons = []

    # Add application addons
    for addon in app_addons:
        combined_addons.append({
            'type': 'application',
            'name': addon.name,
            'display_name': addon.name,
            'version': addon.version,
            'enabled': addon.enabled,
            'status': 'enabled' if addon.enabled else 'disabled',
            'health': 'unknown',
            'description': addon.description,
            'success_count': addon.success_count,
            'failure_count': addon.failure_count,
            'hook_count': addon_hooks.get(addon.name, 0)
        })

    # Add system addons
    for addon in system_addons:
        combined_addons.append({
            'type': 'system',
            'name': addon.name,
            'display_name': addon.display_name,
            'version': addon.version or 'unknown',
            'enabled': addon.enabled,
            'status': addon.status,
            'health': addon.health,
            'description': addon.description,
            'success_count': addon.success_count,
            'failure_count': addon.failure_count,
            'category': addon.category,
            'installed_at': addon.installed_at,
        })

    context = {
        'addons': combined_addons,
        'app_addons': app_addons,
        'system_addons': system_addons,
        'app_enabled_count': app_enabled,
        'app_disabled_count': app_disabled,
        'system_installed_count': system_installed,
        'system_healthy_count': system_healthy,
        'total_count': len(combined_addons),
    }

    return render(request, 'addons/list.html', context)


@login_required
@require_http_methods(["POST"])
def addon_toggle(request, addon_name):
    """Toggle an addon's enabled status (supports both addon types)."""
    # Try application addon first
    try:
        addon = Addon.objects.get(name=addon_name)
        addon_type = 'application'
    except Addon.DoesNotExist:
        # Try system addon
        try:
            addon = SystemAddon.objects.get(name=addon_name)
            addon_type = 'system'
        except SystemAddon.DoesNotExist:
            messages.error(request, f'Addon "{addon_name}" not found.')
            return redirect('addons:addons_list')

    # Toggle enabled status
    addon.enabled = not addon.enabled
    addon.save()

    action = "enabled" if addon.enabled else "disabled"
    display_name = addon.display_name if addon_type == 'system' else addon.name

    messages.success(
        request,
        f'{addon_type.title()} addon "{display_name}" has been {action}. '
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
    """Display detailed information about a specific addon (supports both types)."""
    # Try application addon first
    addon = None
    addon_type = None
    try:
        addon = Addon.objects.get(name=addon_name)
        addon_type = 'application'
    except Addon.DoesNotExist:
        # Try system addon
        try:
            addon = SystemAddon.objects.get(name=addon_name)
            addon_type = 'system'
        except SystemAddon.DoesNotExist:
            messages.error(request, f'Addon "{addon_name}" not found.')
            return redirect('addons:addons_list')

    # Get registered hooks for application addons
    registered_hooks = {}
    if addon_type == 'application' and addon.enabled:
        for event in hook_registry.hooks.keys():
            hooks = [h for h in hook_registry.get_hooks(event) if h.addon_name == addon.name]
            if hooks:
                registered_hooks[event] = hooks

    # Get execution history for system addons
    executions = []
    if addon_type == 'system':
        executions = addon.executions.all().order_by('-started_at')[:10]

    # Calculate success rate
    total_runs = addon.success_count + addon.failure_count
    success_rate = (addon.success_count / total_runs * 100) if total_runs > 0 else 0

    context = {
        'addon': addon,
        'addon_type': addon_type,
        'registered_hooks': registered_hooks,
        'executions': executions,
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