"""
Repository pattern for addon data access.

Provides abstraction over database operations with optimized queries,
caching, and transaction management.
"""

from typing import List, Optional, Dict, Any
from django.db.models import QuerySet, Prefetch, Q
from django.core.cache import cache
from django.db import transaction

from .models import SystemAddon, Addon, AddonExecution
from .logging_config import get_logger

logger = get_logger(__name__)


class AddonRepository:
    """Repository for Addon (application addon) data access."""

    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = 'addon'

    def get_by_name(self, name: str) -> Optional[Addon]:
        """Get addon by name with caching."""
        cache_key = f'{self.CACHE_PREFIX}:name:{name}'
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        try:
            addon = Addon.objects.get(name=name)
            cache.set(cache_key, addon, self.CACHE_TTL)
            return addon
        except Addon.DoesNotExist:
            return None

    def get_all(self, enabled_only: bool = False) -> QuerySet:
        """Get all addons with optimized query."""
        queryset = Addon.objects.all()

        if enabled_only:
            queryset = queryset.filter(enabled=True)

        return queryset.order_by('name')

    def get_enabled(self) -> QuerySet:
        """Get all enabled addons."""
        return self.get_all(enabled_only=True)

    def update_metrics(self, addon: Addon, success: bool, duration_ms: int = None):
        """Update addon execution metrics."""
        if success:
            addon.success_count += 1
            addon.last_success_at = timezone.now()
            if duration_ms:
                addon.last_duration_ms = duration_ms
        else:
            addon.failure_count += 1

        addon.last_run_at = timezone.now()
        addon.save(update_fields=[
            'success_count', 'failure_count', 'last_run_at',
            'last_success_at', 'last_duration_ms'
        ])

        # Invalidate cache
        self._invalidate_cache(addon.name)

    def toggle_enabled(self, addon: Addon, enabled: bool):
        """Toggle addon enabled status."""
        addon.enabled = enabled
        addon.save(update_fields=['enabled'])
        self._invalidate_cache(addon.name)

    def _invalidate_cache(self, name: str):
        """Invalidate cache for addon."""
        cache_key = f'{self.CACHE_PREFIX}:name:{name}'
        cache.delete(cache_key)


class SystemAddonRepository:
    """Repository for SystemAddon data access with optimized queries."""

    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = 'system_addon'

    def get_by_name(
        self,
        name: str,
        prefetch_executions: bool = False
    ) -> Optional[SystemAddon]:
        """
        Get system addon by name with optional execution prefetch.

        Args:
            name: Addon name
            prefetch_executions: Whether to prefetch recent executions

        Returns:
            SystemAddon or None
        """
        cache_key = f'{self.CACHE_PREFIX}:name:{name}'

        # Only cache without executions
        if not prefetch_executions:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            queryset = SystemAddon.objects.select_related('installed_by')

            if prefetch_executions:
                # Prefetch last 10 executions with user
                recent_executions = AddonExecution.objects.select_related(
                    'requested_by'
                ).order_by('-started_at')[:10]

                queryset = queryset.prefetch_related(
                    Prefetch('executions', queryset=recent_executions)
                )

            addon = queryset.get(name=name)

            if not prefetch_executions:
                cache.set(cache_key, addon, self.CACHE_TTL)

            return addon
        except SystemAddon.DoesNotExist:
            return None

    def get_all(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        enabled_only: bool = False
    ) -> QuerySet:
        """
        Get all system addons with filters and optimized query.

        Args:
            status: Filter by status
            category: Filter by category
            enabled_only: Only return enabled addons

        Returns:
            Optimized QuerySet
        """
        queryset = SystemAddon.objects.select_related('installed_by')

        if status:
            queryset = queryset.filter(status=status)

        if category:
            queryset = queryset.filter(category=category)

        if enabled_only:
            queryset = queryset.filter(enabled=True)

        return queryset.order_by('display_name')

    def get_installed(self) -> QuerySet:
        """Get all installed system addons."""
        return self.get_all(status='installed')

    def get_healthy(self) -> QuerySet:
        """Get all healthy system addons."""
        return SystemAddon.objects.filter(
            status='installed',
            health='healthy'
        ).select_related('installed_by')

    def get_by_category(self, category: str) -> QuerySet:
        """Get addons by category."""
        return self.get_all(category=category)

    @transaction.atomic
    def create_or_update(self, name: str, metadata: Dict[str, Any]) -> SystemAddon:
        """
        Create or update system addon from metadata.

        Args:
            name: Addon name
            metadata: Addon metadata dict

        Returns:
            SystemAddon instance
        """
        addon, created = SystemAddon.objects.update_or_create(
            name=name,
            defaults={
                'display_name': metadata.get('display_name', name),
                'version': metadata.get('version', ''),
                'description': metadata.get('description', ''),
                'category': metadata.get('category', 'general'),
                'depends_on': metadata.get('depends', []),
                'provides': metadata.get('provides', []),
                'conflicts_with': metadata.get('conflicts', []),
                'script_path': metadata.get('script_path', ''),
            }
        )

        self._invalidate_cache(name)

        if created:
            logger.info(
                'Created system addon',
                addon_name=name,
                action='create'
            )
        else:
            logger.debug(
                'Updated system addon',
                addon_name=name,
                action='update'
            )

        return addon

    @transaction.atomic
    def update_status(
        self,
        addon: SystemAddon,
        status: str,
        health: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Update addon status atomically.

        Args:
            addon: SystemAddon instance
            status: New status
            health: Optional health status
            error: Optional error message
        """
        addon.status = status

        if health:
            addon.health = health

        if error:
            addon.last_error = error

        update_fields = ['status', 'health', 'last_error']
        addon.save(update_fields=update_fields)

        self._invalidate_cache(addon.name)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall system addon statistics.

        Returns:
            Dict with statistics
        """
        cache_key = f'{self.CACHE_PREFIX}:statistics'
        cached = cache.get(cache_key)

        if cached is not None:
            return cached

        from django.db.models import Count, Q

        stats = {
            'total': SystemAddon.objects.count(),
            'installed': SystemAddon.objects.filter(status='installed').count(),
            'healthy': SystemAddon.objects.filter(
                status='installed',
                health='healthy'
            ).count(),
            'unhealthy': SystemAddon.objects.filter(health='unhealthy').count(),
            'degraded': SystemAddon.objects.filter(health='degraded').count(),
            'by_category': dict(
                SystemAddon.objects.values('category').annotate(
                    count=Count('id')
                ).values_list('category', 'count')
            )
        }

        cache.set(cache_key, stats, 60)  # Cache for 1 minute
        return stats

    def _invalidate_cache(self, name: str):
        """Invalidate cache for addon."""
        cache_key = f'{self.CACHE_PREFIX}:name:{name}'
        cache.delete(cache_key)
        cache.delete(f'{self.CACHE_PREFIX}:statistics')


class AddonExecutionRepository:
    """Repository for AddonExecution data access."""

    def create_execution(
        self,
        addon: SystemAddon,
        operation: str,
        requested_by,
        input_data: Dict = None
    ) -> AddonExecution:
        """Create new execution record."""
        return AddonExecution.objects.create(
            system_addon=addon,
            operation=operation,
            status='pending',
            requested_by=requested_by,
            input_data=input_data or {}
        )

    def get_by_addon(
        self,
        addon: SystemAddon,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> QuerySet:
        """
        Get executions for an addon with filters.

        Args:
            addon: SystemAddon instance
            operation: Filter by operation type
            status: Filter by status
            limit: Maximum results

        Returns:
            Optimized QuerySet
        """
        queryset = AddonExecution.objects.filter(
            system_addon=addon
        ).select_related('requested_by')

        if operation:
            queryset = queryset.filter(operation=operation)

        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('-started_at')[:limit]

    def get_recent(self, limit: int = 50) -> QuerySet:
        """Get recent executions across all addons."""
        return AddonExecution.objects.select_related(
            'system_addon',
            'requested_by'
        ).order_by('-started_at')[:limit]

    def get_failed(self, limit: int = 20) -> QuerySet:
        """Get recent failed executions."""
        return AddonExecution.objects.filter(
            status='failed'
        ).select_related(
            'system_addon',
            'requested_by'
        ).order_by('-started_at')[:limit]

    def get_running(self) -> QuerySet:
        """Get currently running executions."""
        return AddonExecution.objects.filter(
            status='running'
        ).select_related('system_addon', 'requested_by')


# Global repository instances
addon_repository = AddonRepository()
system_addon_repository = SystemAddonRepository()
execution_repository = AddonExecutionRepository()
