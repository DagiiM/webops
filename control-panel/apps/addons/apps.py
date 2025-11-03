from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)

class AddonsConfig(AppConfig):
    name = 'apps.addons'
    verbose_name = 'Addons'

    def ready(self):
        # Import registry and loader but defer database operations until after migration
        try:
            from .registry import event_registry
            from .loader import register_discovered_addons

            # Use post_migrate signal to perform database operations after migrations
            post_migrate.connect(
                self._register_addons_after_migration,
                sender=self,
                dispatch_uid='addons_register_after_migration'
            )

            logger.info('Addons initialization deferred until after migration.')
        except Exception as e:
            logger.error(f'Failed to setup addons initialization: {e}')

    def _register_addons_after_migration(self, sender, **kwargs):
        """Register addons after database migration is complete."""
        try:
            from .registry import event_registry
            from .loader import register_discovered_addons
            register_discovered_addons(event_registry)
            logger.info('Addons discovered and hooks registered after migration.')
        except Exception as e:
            logger.error(f'Failed to initialize addons after migration: {e}')