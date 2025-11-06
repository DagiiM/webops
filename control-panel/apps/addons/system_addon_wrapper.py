"""
System Addon Wrapper

Wraps bash-based system addons to provide a Python interface that implements
the BaseAddon interface. Handles subprocess execution, JSON parsing, and
error handling for system addon operations.
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from django.conf import settings

from .base import (
    BaseAddon,
    AddonType,
    AddonMetadata,
    AddonStatusInfo,
    AddonStatus,
    AddonHealth,
    ValidationResult,
)
from .models import SystemAddon, AddonExecution

logger = logging.getLogger(__name__)


class SystemAddonWrapper(BaseAddon):
    """
    Wrapper for bash-based system addons.

    Provides a Python interface to bash addon scripts that follow the
    system addon contract.
    """

    # Default path to system addons
    SYSTEM_ADDONS_PATH = Path(
        getattr(settings, 'SYSTEM_ADDONS_PATH', '/home/douglas/webops/provisioning/versions/v1.0.0/addons')
    )

    # Default timeout for operations (in seconds)
    DEFAULT_TIMEOUT = 300  # 5 minutes
    INSTALL_TIMEOUT = 1800  # 30 minutes
    UNINSTALL_TIMEOUT = 600  # 10 minutes

    def __init__(self, script_path: Path, db_instance: Optional[SystemAddon] = None):
        """
        Initialize the system addon wrapper.

        Args:
            script_path: Path to the bash addon script
            db_instance: Optional SystemAddon model instance
        """
        self.script_path = script_path
        self._db_instance = db_instance
        self._metadata: Optional[AddonMetadata] = None
        self._load_metadata()

    def _call_function(
        self,
        function_name: str,
        args: list = None,
        stdin_data: str = None,
        timeout: int = None
    ) -> Dict[str, Any]:
        """
        Call a bash function from the addon script.

        Args:
            function_name: Name of the bash function to call
            args: Optional list of arguments to pass
            stdin_data: Optional data to pass via stdin
            timeout: Optional timeout in seconds

        Returns:
            Dict with execution results
        """
        if args is None:
            args = []
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT

        # Build command to source script and call function
        args_str = ' '.join(f'"{arg}"' for arg in args)
        cmd = f'source "{self.script_path}" && {function_name} {args_str}'

        logger.debug(f"Executing: {cmd}")

        try:
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data,
                env=self._get_env()
            )

            # Try to parse JSON output
            output = {}
            if result.stdout.strip():
                try:
                    output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    # Not JSON, treat as plain text
                    output = {'output': result.stdout}

            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'output': output
            }

        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout executing {function_name}: {e}")
            return {
                'success': False,
                'error': f"Timeout after {timeout} seconds",
                'stdout': e.stdout.decode() if e.stdout else '',
                'stderr': e.stderr.decode() if e.stderr else ''
            }
        except Exception as e:
            logger.error(f"Error executing {function_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }

    def _get_env(self) -> Dict[str, str]:
        """Get environment variables for addon execution."""
        import os
        env = os.environ.copy()

        # Add WebOps-specific environment variables
        env['WEBOPS_ROOT'] = '/home/douglas/webops'
        env['WEBOPS_CONFIG'] = '/home/douglas/webops/provisioning/config.env'

        # Add addon config if available
        if self._db_instance and self._db_instance.config:
            for key, value in self._db_instance.config.items():
                env_key = f"ADDON_{key.upper()}"
                env[env_key] = str(value)

        return env

    def _load_metadata(self) -> None:
        """Load metadata from the addon script."""
        result = self._call_function('addon_metadata')

        if not result['success']:
            logger.warning(f"Failed to load metadata for {self.script_path.name}")
            # Use defaults
            self._metadata = AddonMetadata(
                name=self.script_path.stem,
                display_name=self.script_path.stem.replace('_', ' ').title(),
                version='unknown',
                description='System addon (metadata unavailable)'
            )
            return

        try:
            meta_data = result['output']
            self._metadata = AddonMetadata(
                name=meta_data.get('name', self.script_path.stem),
                display_name=meta_data.get('display_name', meta_data.get('name', '')),
                version=meta_data.get('version', '1.0.0'),
                description=meta_data.get('description', ''),
                author=meta_data.get('maintainer', 'WebOps Team'),
                category=meta_data.get('category', 'system'),
                depends_on=meta_data.get('depends', []),
                provides=meta_data.get('provides', []),
                conflicts_with=meta_data.get('conflicts', []),
                documentation_url=meta_data.get('documentation_url')
            )
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing metadata: {e}")
            self._metadata = AddonMetadata(
                name=self.script_path.stem,
                display_name=self.script_path.stem.replace('_', ' ').title(),
                version='unknown',
                description='System addon'
            )

    @property
    def metadata(self) -> AddonMetadata:
        """Get addon metadata."""
        return self._metadata

    @property
    def addon_type(self) -> AddonType:
        """Get addon type (always SYSTEM for this wrapper)."""
        return AddonType.SYSTEM

    def validate(self) -> ValidationResult:
        """Run pre-flight validation checks."""
        result = self._call_function('addon_validate')

        if not result['success']:
            return ValidationResult(
                valid=False,
                errors=[f"Validation failed: {result.get('error', result.get('stderr', 'Unknown error'))}"]
            )

        try:
            output = result['output']
            return ValidationResult(
                valid=output.get('valid', False),
                errors=output.get('errors', []),
                warnings=output.get('warnings', [])
            )
        except (KeyError, TypeError):
            return ValidationResult(
                valid=result['returncode'] == 0,
                errors=[] if result['returncode'] == 0 else [result.get('stderr', 'Unknown error')]
            )

    def install(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Install the addon.

        This is typically called via Celery task for async execution.
        """
        # Prepare config as JSON for stdin
        config_json = json.dumps(config or {})

        result = self._call_function(
            'addon_install',
            stdin_data=config_json,
            timeout=self.INSTALL_TIMEOUT
        )

        if result['success']:
            # Update database instance if available
            if self._db_instance:
                version = result['output'].get('version', self.metadata.version)
                self._db_instance.mark_installed(version=version)

            return {
                'success': True,
                'message': 'Addon installed successfully',
                'data': result['output']
            }
        else:
            if self._db_instance:
                error_msg = result.get('error', result.get('stderr', 'Installation failed'))
                self._db_instance.mark_failed(error_msg)

            return {
                'success': False,
                'message': result.get('error', result.get('stderr', 'Installation failed')),
                'stderr': result.get('stderr', '')
            }

    def uninstall(self, keep_data: bool = True) -> Dict[str, Any]:
        """Uninstall the addon."""
        args = ['true' if keep_data else 'false']

        result = self._call_function(
            'addon_uninstall',
            args=args,
            timeout=self.UNINSTALL_TIMEOUT
        )

        if result['success']:
            if self._db_instance:
                self._db_instance.mark_uninstalled()

            return {
                'success': True,
                'message': 'Addon uninstalled successfully',
                'data': result['output']
            }
        else:
            return {
                'success': False,
                'message': result.get('error', result.get('stderr', 'Uninstall failed')),
                'stderr': result.get('stderr', '')
            }

    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure the addon."""
        config_json = json.dumps(config)

        result = self._call_function(
            'addon_configure',
            stdin_data=config_json
        )

        if result['success']:
            if self._db_instance:
                self._db_instance.config = config
                self._db_instance.save()

            return {
                'success': True,
                'message': 'Addon configured successfully',
                'data': result['output']
            }
        else:
            return {
                'success': False,
                'message': result.get('error', result.get('stderr', 'Configuration failed')),
                'stderr': result.get('stderr', '')
            }

    def get_status(self) -> AddonStatusInfo:
        """Get current status of the addon."""
        result = self._call_function('addon_status')

        if not result['success']:
            return AddonStatusInfo(
                status=AddonStatus.NOT_INSTALLED,
                health=AddonHealth.UNKNOWN,
                message=result.get('error', 'Unable to get status')
            )

        try:
            output = result['output']
            status_str = output.get('status', 'not_installed')
            health_str = output.get('health', 'unknown')

            # Map string values to enums
            status_map = {
                'not_installed': AddonStatus.NOT_INSTALLED,
                'installing': AddonStatus.INSTALLING,
                'installed': AddonStatus.INSTALLED,
                'failed': AddonStatus.FAILED,
                'degraded': AddonStatus.DEGRADED,
            }

            health_map = {
                'healthy': AddonHealth.HEALTHY,
                'unhealthy': AddonHealth.UNHEALTHY,
                'degraded': AddonHealth.DEGRADED,
                'unknown': AddonHealth.UNKNOWN,
            }

            return AddonStatusInfo(
                status=status_map.get(status_str, AddonStatus.NOT_INSTALLED),
                health=health_map.get(health_str, AddonHealth.UNKNOWN),
                version=output.get('version'),
                message=output.get('message'),
                details=output.get('details', {})
            )
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing status: {e}")
            return AddonStatusInfo(
                status=AddonStatus.NOT_INSTALLED,
                health=AddonHealth.UNKNOWN,
                message=str(e)
            )

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        if self._db_instance:
            return self._db_instance.config
        return {}

    def health_check(self) -> AddonHealth:
        """Perform health check."""
        status_info = self.get_status()
        return status_info.health

    @property
    def db_instance(self) -> Optional[SystemAddon]:
        """Get the database instance."""
        return self._db_instance

    @db_instance.setter
    def db_instance(self, value: SystemAddon) -> None:
        """Set the database instance."""
        self._db_instance = value
