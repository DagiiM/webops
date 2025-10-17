from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class AddonsConfig(AppConfig):
    name = 'apps.addons'
    verbose_name = 'Addons'

    def ready(self):
        # Perform discovery and registration at app startup
        try:
            from .registry import hook_registry
            from .loader import register_discovered_addons
            register_discovered_addons(hook_registry)
            logger.info('Addons discovered and hooks registered at startup.')
        except Exception as e:
            logger.error(f'Failed to initialize addons: {e}')