"""
Service layer for addon business logic.

Provides high-level operations with dependency resolution,
validation, and transaction management.
"""

from typing import Dict, Any, Optional, List, Tuple
from django.db import transaction
from django.utils import timezone

from .models import SystemAddon, Addon, AddonExecution
from .repositories import (
    addon_repository,
    system_addon_repository,
    execution_repository,
)
from .validation import validate_addon_config, ValidationError
from .dependency_resolver import DependencyResolver
from .logging_config import get_logger, log_operation_context

logger = get_logger(__name__)


class AddonService:
    """Service for application addon operations."""

    def __init__(self):
        self.repository = addon_repository

    def get_addon(self, name: str) -> Optional[Addon]:
        """Get addon by name."""
        return self.repository.get_by_name(name)

    def list_addons(self, enabled_only: bool = False) -> List[Addon]:
        """List all addons."""
        return list(self.repository.get_all(enabled_only=enabled_only))

    def toggle_addon(self, name: str, enabled: bool) -> Addon:
        """Enable or disable an addon."""
        addon = self.repository.get_by_name(name)

        if addon is None:
            raise ValidationError(f'Addon {name} not found')

        self.repository.toggle_enabled(addon, enabled)

        logger.info(
            f'Addon {"enabled" if enabled else "disabled"}',
            addon_name=name,
            action='enable' if enabled else 'disable'
        )

        return addon

    def record_execution(self, addon: Addon, success: bool, duration_ms: int = None):
        """Record addon execution metrics."""
        self.repository.update_metrics(addon, success, duration_ms)


class SystemAddonService:
    """Service for system addon operations with dependency resolution."""

    def __init__(self):
        self.repository = system_addon_repository
        self.execution_repository = execution_repository
        self.dependency_resolver = DependencyResolver()

    def get_addon(
        self,
        name: str,
        include_executions: bool = False
    ) -> Optional[SystemAddon]:
        """
        Get system addon by name.

        Args:
            name: Addon name
            include_executions: Whether to include execution history

        Returns:
            SystemAddon or None
        """
        return self.repository.get_by_name(
            name,
            prefetch_executions=include_executions
        )

    def list_addons(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[SystemAddon]:
        """List system addons with filters."""
        return list(self.repository.get_all(status, category, enabled_only))

    def get_statistics(self) -> Dict[str, Any]:
        """Get system addon statistics."""
        return self.repository.get_statistics()

    @transaction.atomic
    def prepare_installation(
        self,
        addon: SystemAddon,
        config: Dict[str, Any],
        user
    ) -> Tuple[AddonExecution, List[str]]:
        """
        Prepare addon for installation.

        Validates configuration, checks dependencies, and creates execution record.

        Args:
            addon: SystemAddon to install
            config: Configuration dict
            user: User requesting installation

        Returns:
            Tuple of (execution record, list of warnings)

        Raises:
            ValidationError: If validation fails
        """
        # Validate configuration
        errors = validate_addon_config(config)
        if errors:
            raise ValidationError(
                'Configuration validation failed',
                errors=errors
            )

        # Check if already installed
        if addon.status == 'installed':
            raise ValidationError(f'Addon {addon.name} is already installed')

        # Check if currently installing/uninstalling
        if addon.status in ['installing', 'uninstalling', 'configuring']:
            raise ValidationError(
                f'Addon {addon.name} is currently {addon.status}'
            )

        # Resolve dependencies
        warnings = []
        try:
            install_order = self.dependency_resolver.resolve_install_order(
                addon.name,
                self._get_dependency_graph()
            )

            # Check if dependencies are installed
            missing_deps = []
            for dep_name in addon.depends_on:
                dep = self.repository.get_by_name(dep_name)
                if not dep or dep.status != 'installed':
                    missing_deps.append(dep_name)

            if missing_deps:
                warnings.append(
                    f'Missing dependencies: {", ".join(missing_deps)}'
                )

        except Exception as e:
            warnings.append(f'Dependency resolution warning: {str(e)}')

        # Check for conflicts
        conflicts = self._check_conflicts(addon)
        if conflicts:
            raise ValidationError(
                f'Conflicts detected with: {", ".join(conflicts)}'
            )

        # Mark addon as installing
        addon.mark_installing(user)

        # Create execution record
        execution = self.execution_repository.create_execution(
            addon=addon,
            operation='install',
            requested_by=user,
            input_data={'config': config}
        )

        logger.info(
            'Prepared installation',
            addon_name=addon.name,
            execution_id=str(execution.id),
            user=user.username if user else None,
            operation='install',
            warnings_count=len(warnings)
        )

        return execution, warnings

    @transaction.atomic
    def complete_installation(
        self,
        execution: AddonExecution,
        success: bool,
        output_data: Dict = None,
        error: str = None
    ):
        """
        Complete installation and update addon status.

        Args:
            execution: AddonExecution record
            success: Whether installation succeeded
            output_data: Output data from installation
            error: Error message if failed
        """
        addon = execution.system_addon

        if success:
            execution.mark_success(output_data or {})

            # Extract version from output if available
            version = None
            if output_data:
                version = output_data.get('version')

            addon.mark_installed(version=version)

            logger.info(
                'Successfully installed addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                version=version,
                operation='install',
                status='success'
            )
        else:
            execution.mark_failed(error or 'Installation failed')
            addon.mark_failed(error or 'Installation failed')

            logger.error(
                'Failed to install addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                error_message=error,
                operation='install',
                status='failure'
            )

    @transaction.atomic
    def prepare_uninstallation(
        self,
        addon: SystemAddon,
        keep_data: bool,
        user
    ) -> Tuple[AddonExecution, List[str]]:
        """
        Prepare addon for uninstallation.

        Checks dependents and creates execution record.

        Args:
            addon: SystemAddon to uninstall
            keep_data: Whether to keep data
            user: User requesting uninstallation

        Returns:
            Tuple of (execution record, list of warnings)

        Raises:
            ValidationError: If uninstallation is not allowed
        """
        # Check if installed
        if addon.status != 'installed':
            raise ValidationError(f'Addon {addon.name} is not installed')

        # Check for dependents
        warnings = []
        dependents = self._get_dependents(addon)

        if dependents:
            warnings.append(
                f'The following addons depend on {addon.name}: {", ".join(dependents)}'
            )

            # Check if any dependents are installed
            installed_dependents = []
            for dep_name in dependents:
                dep = self.repository.get_by_name(dep_name)
                if dep and dep.status == 'installed':
                    installed_dependents.append(dep_name)

            if installed_dependents:
                raise ValidationError(
                    f'Cannot uninstall {addon.name}. '
                    f'The following installed addons depend on it: '
                    f'{", ".join(installed_dependents)}'
                )

        # Mark as uninstalling
        addon.mark_uninstalling()

        # Create execution record
        execution = self.execution_repository.create_execution(
            addon=addon,
            operation='uninstall',
            requested_by=user,
            input_data={'keep_data': keep_data}
        )

        logger.info(
            'Prepared uninstallation',
            addon_name=addon.name,
            execution_id=str(execution.id),
            user=user.username if user else None,
            operation='uninstall',
            keep_data=keep_data,
            warnings_count=len(warnings)
        )

        return execution, warnings

    @transaction.atomic
    def complete_uninstallation(
        self,
        execution: AddonExecution,
        success: bool,
        error: str = None
    ):
        """Complete uninstallation and update addon status."""
        addon = execution.system_addon

        if success:
            execution.mark_success({})
            addon.mark_uninstalled()

            logger.info(
                'Successfully uninstalled addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                operation='uninstall',
                status='success'
            )
        else:
            execution.mark_failed(error or 'Uninstallation failed')
            addon.mark_failed(error or 'Uninstallation failed')

            logger.error(
                'Failed to uninstall addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                error_message=error,
                operation='uninstall',
                status='failure'
            )

    @transaction.atomic
    def prepare_configuration(
        self,
        addon: SystemAddon,
        config: Dict[str, Any],
        user
    ) -> AddonExecution:
        """
        Prepare addon for configuration.

        Validates configuration and creates execution record.

        Args:
            addon: SystemAddon to configure
            config: New configuration
            user: User requesting configuration

        Returns:
            AddonExecution record

        Raises:
            ValidationError: If validation fails
        """
        # Validate configuration
        errors = validate_addon_config(config)
        if errors:
            raise ValidationError(
                'Configuration validation failed',
                errors=errors
            )

        # Check if installed
        if addon.status != 'installed':
            raise ValidationError(
                f'Addon {addon.name} must be installed before configuration'
            )

        # Mark as configuring
        addon.status = 'configuring'
        addon.save(update_fields=['status'])

        # Create execution record
        execution = self.execution_repository.create_execution(
            addon=addon,
            operation='configure',
            requested_by=user,
            input_data={'config': config}
        )

        logger.info(
            'Prepared configuration',
            addon_name=addon.name,
            execution_id=str(execution.id),
            user=user.username if user else None,
            operation='configure'
        )

        return execution

    @transaction.atomic
    def complete_configuration(
        self,
        execution: AddonExecution,
        success: bool,
        error: str = None
    ):
        """Complete configuration and update addon status."""
        addon = execution.system_addon

        if success:
            execution.mark_success({})

            # Update config and status
            addon.config = execution.input_data.get('config', {})
            addon.status = 'installed'
            addon.health = 'healthy'
            addon.save(update_fields=['config', 'status', 'health'])

            logger.info(
                'Successfully configured addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                operation='configure',
                status='success'
            )
        else:
            execution.mark_failed(error or 'Configuration failed')

            # Revert to installed status
            addon.status = 'installed'
            addon.health = 'degraded'
            addon.last_error = error or 'Configuration failed'
            addon.save(update_fields=['status', 'health', 'last_error'])

            logger.error(
                'Failed to configure addon',
                addon_name=addon.name,
                execution_id=str(execution.id),
                error_message=error,
                operation='configure',
                status='failure'
            )

    def _get_dependency_graph(self) -> Dict[str, List[str]]:
        """Build dependency graph for all addons."""
        graph = {}

        for addon in self.repository.get_all():
            graph[addon.name] = addon.depends_on

        return graph

    def _check_conflicts(self, addon: SystemAddon) -> List[str]:
        """
        Check for conflicts with installed addons.

        Returns:
            List of conflicting addon names
        """
        conflicts = []

        for conflict_name in addon.conflicts_with:
            conflict_addon = self.repository.get_by_name(conflict_name)

            if conflict_addon and conflict_addon.status == 'installed':
                conflicts.append(conflict_name)

        return conflicts

    def _get_dependents(self, addon: SystemAddon) -> List[str]:
        """
        Get list of addons that depend on this addon.

        Returns:
            List of dependent addon names
        """
        dependents = []

        for other_addon in self.repository.get_all():
            if addon.name in other_addon.depends_on:
                dependents.append(other_addon.name)

        return dependents


# Global service instances
addon_service = AddonService()
system_addon_service = SystemAddonService()
