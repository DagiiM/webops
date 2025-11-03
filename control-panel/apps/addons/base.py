"""
Base addon interface for unified WebOps addon system.

This module defines the core interfaces that all addons must implement,
regardless of whether they are Python-based (application) or Bash-based (system).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass


class AddonType(Enum):
    """Type of addon implementation."""
    APPLICATION = "application"  # Pure Django addons (Docker, KVM app layer)
    SYSTEM = "system"           # Bash addons (PostgreSQL, Kubernetes, etc.)
    HYBRID = "hybrid"           # Both layers working together


class AddonStatus(Enum):
    """Installation status of an addon."""
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    CONFIGURING = "configuring"
    FAILED = "failed"
    UNINSTALLING = "uninstalling"
    DEGRADED = "degraded"       # Installed but unhealthy


class AddonHealth(Enum):
    """Health status of an installed addon."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class AddonMetadata:
    """Metadata about an addon."""
    name: str
    display_name: str
    version: str
    description: str
    author: str = "WebOps Team"
    category: str = "general"
    depends_on: List[str] = None
    provides: List[str] = None
    conflicts_with: List[str] = None
    documentation_url: Optional[str] = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []
        if self.provides is None:
            self.provides = []
        if self.conflicts_with is None:
            self.conflicts_with = []


@dataclass
class AddonStatusInfo:
    """Current status information for an addon."""
    status: AddonStatus
    health: AddonHealth
    version: Optional[str] = None
    message: Optional[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class ValidationResult:
    """Result of addon validation checks."""
    valid: bool
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class BaseAddon(ABC):
    """
    Base interface for all WebOps addons.

    All addons (both application and system level) must implement this interface
    to provide consistent lifecycle management, configuration, and monitoring.
    """

    @property
    @abstractmethod
    def metadata(self) -> AddonMetadata:
        """Get addon metadata."""
        pass

    @property
    @abstractmethod
    def addon_type(self) -> AddonType:
        """Get the type of this addon."""
        pass

    @abstractmethod
    def validate(self) -> ValidationResult:
        """
        Run pre-flight validation checks.

        Returns:
            ValidationResult with any errors or warnings.
        """
        pass

    @abstractmethod
    def install(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Install the addon.

        Args:
            config: Optional configuration dictionary.

        Returns:
            Dict with 'success' bool, 'message' str, and optional 'data'.
        """
        pass

    @abstractmethod
    def uninstall(self, keep_data: bool = True) -> Dict[str, Any]:
        """
        Uninstall the addon.

        Args:
            keep_data: Whether to preserve data (default: True for safety).

        Returns:
            Dict with 'success' bool, 'message' str.
        """
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure or reconfigure the addon.

        Args:
            config: Configuration dictionary.

        Returns:
            Dict with 'success' bool, 'message' str.
        """
        pass

    @abstractmethod
    def get_status(self) -> AddonStatusInfo:
        """
        Get current status of the addon.

        Returns:
            AddonStatusInfo with current state.
        """
        pass

    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.

        Returns:
            Dict with current configuration values.
        """
        pass

    @abstractmethod
    def health_check(self) -> AddonHealth:
        """
        Perform health check on installed addon.

        Returns:
            AddonHealth status.
        """
        pass

    def register_hooks(self) -> None:
        """
        Register addon hooks with the hook registry.

        This is called automatically during addon discovery.
        Override to register custom hooks.
        """
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get addon-specific metrics.

        Returns:
            Dict with metric names and values.
        """
        return {}

    def __str__(self) -> str:
        return f"{self.metadata.display_name} ({self.metadata.version})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.metadata.name}>"
