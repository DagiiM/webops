import os
import importlib
import logging
from typing import Dict, Any, List, Tuple
import yaml

from django.utils import timezone
from django.db import transaction

from .models import Addon

logger = logging.getLogger(__name__)

DEFAULT_ADDONS_PATH = os.environ.get('ADDONS_PATH')
if not DEFAULT_ADDONS_PATH:
    # Fallback to a conventional path under project root
    DEFAULT_ADDONS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'addons')


def parse_manifest(path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Parse an addon manifest (YAML) and return two dicts:
    - metadata: name, version, description, author, etc.
    - hooks: mapping of hook event -> list of handlers with options

    Manifest example:
    name: example-addon
    version: 1.0.0
    hooks:
      pre_deployment:
        - handler: example.handlers:pre_deploy
          priority: 50
          timeout_ms: 3000
          retries: 2
          enforcement: required
          conditions:
            env: production
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    metadata = {
        'name': data.get('name'),
        'version': str(data.get('version')) if data.get('version') is not None else None,
        'description': data.get('description'),
        'author': data.get('author'),
        'license': data.get('license'),
        'django_app': data.get('django_app') or '',
        'cli_entrypoint': data.get('cli_entrypoint') or '',
        'capabilities': data.get('capabilities') or [],
        'settings_schema': data.get('settings_schema') or {},
    }
    hooks = data.get('hooks') or {}
    return metadata, hooks


def resolve_handler(handler_str: str):
    """
    Resolve a handler string in the form 'module.submodule:func' to a callable
    """
    if ':' not in handler_str:
        raise ValueError(f"Invalid handler reference '{handler_str}'. Expected 'module:func'.")
    module_name, func_name = handler_str.split(':', 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name, None)
    if not callable(func):
        raise ValueError(f"Handler '{handler_str}' is not callable or not found.")
    return func


def discover_addons(addons_path: str = DEFAULT_ADDONS_PATH) -> List[Dict[str, Any]]:
    """
    Discover addons by scanning the addons_path for .yaml/.yml manifest files.
    Returns a list of dicts having: metadata, hooks, manifest_path
    """
    discovered = []
    if not addons_path or not os.path.isdir(addons_path):
        logger.info(f"Addons path '{addons_path}' not found; skipping discovery.")
        return discovered
    for root, _, files in os.walk(addons_path):
        for fname in files:
            if fname.endswith(('.yaml', '.yml')):
                manifest_path = os.path.join(root, fname)
                try:
                    metadata, hooks = parse_manifest(manifest_path)
                    if not metadata.get('name'):
                        logger.warning(f"Manifest '{manifest_path}' missing required 'name'; skipping.")
                        continue
                    discovered.append({
                        'metadata': metadata,
                        'hooks': hooks,
                        'manifest_path': manifest_path,
                    })
                except Exception as e:
                    logger.error(f"Failed to parse manifest '{manifest_path}': {e}")
    return discovered


def sync_addon_record(meta: Dict[str, Any], manifest_path: str) -> None:
    """
    Ensure the Addon record exists and reflects the manifest metadata.
    """
    with transaction.atomic():
        addon, _created = Addon.objects.get_or_create(
            name=meta['name'],
            defaults={
                'version': meta.get('version') or '',
                'description': meta.get('description') or '',
                'author': meta.get('author') or '',
                'license': meta.get('license') or '',
                'enabled': True,
                'django_app': meta.get('django_app') or '',
                'cli_entrypoint': meta.get('cli_entrypoint') or '',
                'manifest_path': manifest_path,
                'capabilities': meta.get('capabilities') or [],
                'settings_schema': meta.get('settings_schema') or {},
            }
        )
        # Update fields if manifest changed
        fields = [
            'version', 'description', 'author', 'license',
            'django_app', 'cli_entrypoint', 'manifest_path',
            'capabilities', 'settings_schema'
        ]
        updated = False
        for f in fields:
            val = meta.get(f) if f in meta else getattr(addon, f)
            if getattr(addon, f) != val:
                setattr(addon, f, val)
                updated = True
        if updated:
            addon.updated_at = timezone.now()
            addon.save()


def register_discovered_addons(registry, addons_path: str = DEFAULT_ADDONS_PATH) -> List[Dict[str, Any]]:
    """
    Given a registry (AddonHookRegistry), parse manifests and register hooks
    with extracted options and resolved handlers.
    Also sync Addon model records for discovered manifests.
    Returns the list of discovered addon dicts.
    """
    addons = discover_addons(addons_path)
    for addon in addons:
        meta = addon['metadata']
        hooks = addon['hooks']
        name = meta.get('name') or 'unknown'
        # Sync DB record
        try:
            sync_addon_record(meta, addon['manifest_path'])
        except Exception as e:
            logger.error(f"Failed to sync Addon record for '{name}': {e}")
        # Register hooks
        for event, handlers in hooks.items():
            if not isinstance(handlers, list):
                logger.warning(f"Hooks for event '{event}' in addon '{name}' must be a list.")
                continue
            for h in handlers:
                try:
                    handler_ref = h.get('handler')
                    if not handler_ref:
                        logger.warning(f"Handler missing for event '{event}' in addon '{name}'.")
                        continue
                    func = resolve_handler(handler_ref)
                    registry.register_hook(
                        event,
                        func,
                        addon_name=name,
                        priority=int(h.get('priority', 100)),
                        timeout_ms=h.get('timeout_ms'),
                        retries=int(h.get('retries', 0)),
                        retry_initial_delay_ms=int(h.get('retry_initial_delay_ms', 250)),
                        retry_backoff=bool(h.get('retry_backoff', True)),
                        enforcement=str(h.get('enforcement', 'optional')),
                        conditions=h.get('conditions'),
                    )
                except Exception as e:
                    logger.error(f"Failed to register handler for event '{event}' in addon '{name}': {e}")
    return addons