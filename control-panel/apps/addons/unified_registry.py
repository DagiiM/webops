"""
Addon Registry

Centralized registry for discovering and managing both API-level (Python/Django)
and system-level (bash) addons. Provides a unified interface for addon operations.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from django.conf import settings

from .base import BaseAddon, AddonType
from .models import SystemAddon
from .system_addon_wrapper import SystemAddonWrapper

logger = logging.getLogger(__name__)


class AddonRegistry:
    """
    Central registry for all WebOps addons.

    Auto-discovers both system (bash) and application (Python) addons,
    providing a unified interface for management operations.
    """

    def __init__(self):
        self._addons: Dict[str, BaseAddon] = {}
        self._system_addons_path = Path(
            getattr(settings, 'SYSTEM_ADDONS_PATH',
                    '/home/douglas/webops/.webops/versions/v1.0.0/addons')
        )
        self._app_addons_path = Path(
            getattr(settings, 'APP_ADDONS_PATH',
                    '/home/douglas/webops/control-panel/addons')
        )

    def discover_all(self) -> int:
        """
        Discover all addons (system and application).

        Returns:
            Number of addons discovered
        """
        count = 0
        count += self.discover_system_addons()
        count += self.discover_application_addons()
        return count

    def discover_system_addons(self) -> int:
        """
        Discover bash-based system addons.

        Scans the system addons directory for .sh files and creates/updates
        database records for each addon.

        Returns:
            Number of system addons discovered
        """
        if not self._system_addons_path.exists():
            logger.warning(f"System addons path does not exist: {self._system_addons_path}")
            return 0

        discovered = 0

        for script_path in self._system_addons_path.glob("*.sh"):
            try:
                logger.debug(f"Discovering system addon: {script_path.name}")

                # Create wrapper to get metadata
                wrapper = SystemAddonWrapper(script_path)
                metadata = wrapper.metadata

                # Get or create database record
                addon, created = SystemAddon.objects.get_or_create(
                    name=metadata.name,
                    defaults={
                        'display_name': metadata.display_name,
                        'script_path': str(script_path),
                        'version': metadata.version,
                        'description': metadata.description,
                        'category': metadata.category,
                        'depends_on': metadata.depends_on,
                        'provides': metadata.provides,
                        'conflicts_with': metadata.conflicts_with,
                    }
                )

                if not created:
                    # Update existing record
                    addon.display_name = metadata.display_name
                    addon.script_path = str(script_path)
                    addon.description = metadata.description
                    addon.category = metadata.category
                    addon.depends_on = metadata.depends_on
                    addon.provides = metadata.provides
                    addon.conflicts_with = metadata.conflicts_with
                    addon.save()

                # Link database instance to wrapper
                wrapper.db_instance = addon

                # Add to registry
                self._addons[metadata.name] = wrapper
                discovered += 1

                logger.info(f"{'Created' if created else 'Updated'} system addon: {metadata.name}")

            except Exception as e:
                logger.error(f"Error discovering {script_path.name}: {e}")

        logger.info(f"Discovered {discovered} system addons")
        return discovered

    def discover_application_addons(self) -> int:
        """
        Discover Python/Django application addons.

        Scans the application addons directory for Python packages with
        addon manifests.

        Returns:
            Number of application addons discovered
        """
        if not self._app_addons_path.exists():
            logger.warning(f"Application addons path does not exist: {self._app_addons_path}")
            return 0

        discovered = 0

        for addon_dir in self._app_addons_path.iterdir():
            if not addon_dir.is_dir():
                continue

            # Skip __pycache__ and hidden directories
            if addon_dir.name.startswith('.') or addon_dir.name == '__pycache__':
                continue

            try:
                # Look for addon.py or __init__.py that implements BaseAddon
                addon_module = self._load_application_addon(addon_dir)
                if addon_module:
                    self._addons[addon_module.metadata.name] = addon_module
                    discovered += 1
                    logger.info(f"Discovered application addon: {addon_module.metadata.name}")

            except Exception as e:
                logger.error(f"Error discovering application addon {addon_dir.name}: {e}")

        logger.info(f"Discovered {discovered} application addons")
        return discovered

    def _load_application_addon(self, addon_dir: Path) -> Optional[BaseAddon]:
        """
        Load an application addon from a directory.

        Args:
            addon_dir: Path to addon directory

        Returns:
            BaseAddon instance or None if not found
        """
        # This is a placeholder for future application addon loading
        # For now, we'll skip application addons as they use the existing
        # hook registry system
        return None

    def get(self, name: str) -> Optional[BaseAddon]:
        """
        Get an addon by name.

        Args:
            name: Addon name

        Returns:
            BaseAddon instance or None if not found
        """
        return self._addons.get(name)

    def list(self, addon_type: Optional[AddonType] = None) -> List[BaseAddon]:
        """
        List all registered addons.

        Args:
            addon_type: Optional filter by addon type

        Returns:
            List of BaseAddon instances
        """
        addons = list(self._addons.values())

        if addon_type:
            addons = [a for a in addons if a.addon_type == addon_type]

        return addons

    def list_system_addons(self) -> List[SystemAddonWrapper]:
        """
        List all system addons.

        Returns:
            List of SystemAddonWrapper instances
        """
        return [
            addon for addon in self._addons.values()
            if isinstance(addon, SystemAddonWrapper)
        ]

    def get_by_category(self, category: str) -> List[BaseAddon]:
        """
        Get addons by category.

        Args:
            category: Category name

        Returns:
            List of BaseAddon instances in the category
        """
        return [
            addon for addon in self._addons.values()
            if addon.metadata.category == category
        ]

    def install(self, name: str, config: Optional[Dict] = None, user_id: Optional[int] = None) -> str:
        """
        Install an addon (async via Celery).

        Args:
            name: Addon name
            config: Optional configuration dict
            user_id: Optional user ID

        Returns:
            Celery task ID

        Raises:
            ValueError: If addon not found
        """
        addon = self.get(name)
        if not addon:
            raise ValueError(f"Addon '{name}' not found")

        if isinstance(addon, SystemAddonWrapper):
            from .tasks import install_system_addon

            if not addon.db_instance:
                raise ValueError(f"System addon '{name}' has no database instance")

            task = install_system_addon.delay(
                addon_id=addon.db_instance.id,
                config=config,
                user_id=user_id
            )
            return task.id
        else:
            # For application addons, call install directly
            result = addon.install(config=config)
            if not result['success']:
                raise Exception(result['message'])
            return 'completed'

    def uninstall(self, name: str, keep_data: bool = True, user_id: Optional[int] = None) -> str:
        """
        Uninstall an addon (async via Celery).

        Args:
            name: Addon name
            keep_data: Whether to keep data
            user_id: Optional user ID

        Returns:
            Celery task ID

        Raises:
            ValueError: If addon not found
        """
        addon = self.get(name)
        if not addon:
            raise ValueError(f"Addon '{name}' not found")

        if isinstance(addon, SystemAddonWrapper):
            from .tasks import uninstall_system_addon

            if not addon.db_instance:
                raise ValueError(f"System addon '{name}' has no database instance")

            task = uninstall_system_addon.delay(
                addon_id=addon.db_instance.id,
                keep_data=keep_data,
                user_id=user_id
            )
            return task.id
        else:
            result = addon.uninstall(keep_data=keep_data)
            if not result['success']:
                raise Exception(result['message'])
            return 'completed'

    def configure(self, name: str, config: Dict, user_id: Optional[int] = None) -> str:
        """
        Configure an addon (async via Celery).

        Args:
            name: Addon name
            config: Configuration dict
            user_id: Optional user ID

        Returns:
            Celery task ID

        Raises:
            ValueError: If addon not found
        """
        addon = self.get(name)
        if not addon:
            raise ValueError(f"Addon '{name}' not found")

        if isinstance(addon, SystemAddonWrapper):
            from .tasks import configure_system_addon

            if not addon.db_instance:
                raise ValueError(f"System addon '{name}' has no database instance")

            task = configure_system_addon.delay(
                addon_id=addon.db_instance.id,
                config=config,
                user_id=user_id
            )
            return task.id
        else:
            result = addon.configure(config=config)
            if not result['success']:
                raise Exception(result['message'])
            return 'completed'

    def health_check_all(self) -> Dict[str, str]:
        """
        Run health checks on all installed addons.

        Returns:
            Dict mapping addon names to health status
        """
        from .tasks import health_check_system_addons

        # Trigger async health check task
        task = health_check_system_addons.delay()

        return {
            'task_id': task.id,
            'message': 'Health check task started'
        }


# Global singleton instance
addon_registry = AddonRegistry()


def get_addon_registry() -> AddonRegistry:
    """Get the global addon registry."""
    return addon_registry


# Backward compatibility
unified_registry = addon_registry
get_unified_registry = get_addon_registry
UnifiedAddonRegistry = AddonRegistry
