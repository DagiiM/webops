"""
Celery tasks for addon operations.

Provides async execution of long-running addon operations like
installation, uninstallation, and health checks.
"""

import logging
from pathlib import Path
from celery import shared_task
from django.utils import timezone
from typing import Dict, Any, Optional

from .models import SystemAddon, AddonExecution
from .system_addon_wrapper import SystemAddonWrapper

logger = logging.getLogger(__name__)


@shared_task(name='addons.install_system_addon', bind=True, max_retries=3)
def install_system_addon(
    self,
    addon_id: int,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Install a system addon asynchronously.

    Args:
        self: Celery task instance
        addon_id: SystemAddon model ID
        config: Optional configuration dict
        user_id: Optional user ID who requested installation

    Returns:
        Dict with success status and message
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        # Get addon from database
        addon = SystemAddon.objects.get(id=addon_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Create execution record
        execution = AddonExecution.objects.create(
            system_addon=addon,
            operation='install',
            status='running',
            requested_by=user,
            input_data=config or {},
            celery_task_id=self.request.id
        )

        # Mark addon as installing
        addon.mark_installing(user=user)

        logger.info(f"Installing system addon: {addon.name}")

        # Create wrapper and execute install
        wrapper = SystemAddonWrapper(
            script_path=Path(addon.script_path),
            db_instance=addon
        )

        result = wrapper.install(config=config)

        if result['success']:
            logger.info(f"Successfully installed {addon.name}")
            execution.mark_success(output=result.get('data', {}))
            return {
                'success': True,
                'addon': addon.name,
                'message': result['message']
            }
        else:
            logger.error(f"Failed to install {addon.name}: {result['message']}")
            execution.mark_failed(
                error=result['message'],
                stderr=result.get('stderr', '')
            )
            return {
                'success': False,
                'addon': addon.name,
                'message': result['message']
            }

    except SystemAddon.DoesNotExist:
        logger.error(f"SystemAddon with id {addon_id} not found")
        return {
            'success': False,
            'message': f"Addon with id {addon_id} not found"
        }
    except Exception as e:
        logger.exception(f"Error installing addon: {e}")

        # Try to update execution if it exists
        try:
            execution.mark_failed(error=str(e))
        except:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(name='addons.uninstall_system_addon', bind=True)
def uninstall_system_addon(
    self,
    addon_id: int,
    keep_data: bool = True,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Uninstall a system addon asynchronously.

    Args:
        self: Celery task instance
        addon_id: SystemAddon model ID
        keep_data: Whether to keep data (default: True)
        user_id: Optional user ID who requested uninstallation

    Returns:
        Dict with success status and message
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        addon = SystemAddon.objects.get(id=addon_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Create execution record
        execution = AddonExecution.objects.create(
            system_addon=addon,
            operation='uninstall',
            status='running',
            requested_by=user,
            input_data={'keep_data': keep_data},
            celery_task_id=self.request.id
        )

        # Mark addon as uninstalling
        addon.mark_uninstalling()

        logger.info(f"Uninstalling system addon: {addon.name} (keep_data={keep_data})")

        # Create wrapper and execute uninstall
        wrapper = SystemAddonWrapper(
            script_path=Path(addon.script_path),
            db_instance=addon
        )

        result = wrapper.uninstall(keep_data=keep_data)

        if result['success']:
            logger.info(f"Successfully uninstalled {addon.name}")
            execution.mark_success(output=result.get('data', {}))
            return {
                'success': True,
                'addon': addon.name,
                'message': result['message']
            }
        else:
            logger.error(f"Failed to uninstall {addon.name}: {result['message']}")
            execution.mark_failed(
                error=result['message'],
                stderr=result.get('stderr', '')
            )
            return {
                'success': False,
                'addon': addon.name,
                'message': result['message']
            }

    except SystemAddon.DoesNotExist:
        logger.error(f"SystemAddon with id {addon_id} not found")
        return {
            'success': False,
            'message': f"Addon with id {addon_id} not found"
        }
    except Exception as e:
        logger.exception(f"Error uninstalling addon: {e}")

        try:
            execution.mark_failed(error=str(e))
        except:
            pass

        return {
            'success': False,
            'message': str(e)
        }


@shared_task(name='addons.configure_system_addon', bind=True)
def configure_system_addon(
    self,
    addon_id: int,
    config: Dict[str, Any],
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Configure a system addon asynchronously.

    Args:
        self: Celery task instance
        addon_id: SystemAddon model ID
        config: Configuration dict
        user_id: Optional user ID who requested configuration

    Returns:
        Dict with success status and message
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        addon = SystemAddon.objects.get(id=addon_id)
        user = User.objects.get(id=user_id) if user_id else None

        # Create execution record
        execution = AddonExecution.objects.create(
            system_addon=addon,
            operation='configure',
            status='running',
            requested_by=user,
            input_data=config,
            celery_task_id=self.request.id
        )

        logger.info(f"Configuring system addon: {addon.name}")

        # Create wrapper and execute configure
        wrapper = SystemAddonWrapper(
            script_path=Path(addon.script_path),
            db_instance=addon
        )

        result = wrapper.configure(config=config)

        if result['success']:
            logger.info(f"Successfully configured {addon.name}")
            execution.mark_success(output=result.get('data', {}))
            return {
                'success': True,
                'addon': addon.name,
                'message': result['message']
            }
        else:
            logger.error(f"Failed to configure {addon.name}: {result['message']}")
            execution.mark_failed(
                error=result['message'],
                stderr=result.get('stderr', '')
            )
            return {
                'success': False,
                'addon': addon.name,
                'message': result['message']
            }

    except SystemAddon.DoesNotExist:
        logger.error(f"SystemAddon with id {addon_id} not found")
        return {
            'success': False,
            'message': f"Addon with id {addon_id} not found"
        }
    except Exception as e:
        logger.exception(f"Error configuring addon: {e}")

        try:
            execution.mark_failed(error=str(e))
        except:
            pass

        return {
            'success': False,
            'message': str(e)
        }


@shared_task(name='addons.health_check_system_addons')
def health_check_system_addons() -> Dict[str, Any]:
    """
    Perform health checks on all installed system addons.

    This task is typically scheduled to run periodically via Celery Beat.

    Returns:
        Dict with health check summary
    """
    logger.info("Running system addon health checks")

    installed_addons = SystemAddon.objects.filter(status='installed')
    results = {
        'total': installed_addons.count(),
        'healthy': 0,
        'unhealthy': 0,
        'degraded': 0,
        'errors': []
    }

    for addon in installed_addons:
        try:
            wrapper = SystemAddonWrapper(
                script_path=Path(addon.script_path),
                db_instance=addon
            )

            health = wrapper.health_check()
            addon.update_health(health.value)

            if health.value == 'healthy':
                results['healthy'] += 1
            elif health.value == 'unhealthy':
                results['unhealthy'] += 1
            elif health.value == 'degraded':
                results['degraded'] += 1

            logger.debug(f"{addon.name}: {health.value}")

        except Exception as e:
            logger.error(f"Health check failed for {addon.name}: {e}")
            addon.update_health('unhealthy')
            results['errors'].append({
                'addon': addon.name,
                'error': str(e)
            })
            results['unhealthy'] += 1

    logger.info(f"Health check complete: {results['healthy']} healthy, "
                f"{results['degraded']} degraded, {results['unhealthy']} unhealthy")

    return results


@shared_task(name='addons.sync_system_addon_status')
def sync_system_addon_status(addon_id: int) -> Dict[str, Any]:
    """
    Sync system addon status from bash script to database.

    Args:
        addon_id: SystemAddon model ID

    Returns:
        Dict with status info
    """
    try:
        addon = SystemAddon.objects.get(id=addon_id)

        wrapper = SystemAddonWrapper(
            script_path=Path(addon.script_path),
            db_instance=addon
        )

        status_info = wrapper.get_status()

        # Update database
        addon.status = status_info.status.value
        addon.health = status_info.health.value
        if status_info.version:
            addon.version = status_info.version
        addon.save()

        return {
            'success': True,
            'addon': addon.name,
            'status': status_info.status.value,
            'health': status_info.health.value
        }

    except SystemAddon.DoesNotExist:
        logger.error(f"SystemAddon with id {addon_id} not found")
        return {
            'success': False,
            'message': f"Addon with id {addon_id} not found"
        }
    except Exception as e:
        logger.exception(f"Error syncing addon status: {e}")
        return {
            'success': False,
            'message': str(e)
        }
