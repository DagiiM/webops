"""
App Contract Parser and Validator for WebOps.

This module handles reading, parsing, and validating app contracts (webops.yml)
that define resource requirements, permissions, and services for deployments.

Reference: docs/APP-CONTRACT.md
"""

import re
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
import json
from dataclasses import dataclass, field


@dataclass
class ResourceLimits:
    """Resource limits for a deployment."""
    memory: str = "256M"
    cpu: str = "0.25"
    disk: str = "1G"

    def memory_bytes(self) -> int:
        """Convert memory string to bytes."""
        return self._parse_size(self.memory)

    def disk_bytes(self) -> int:
        """Convert disk string to bytes."""
        return self._parse_size(self.disk)

    def cpu_float(self) -> float:
        """Get CPU as float value."""
        return float(self.cpu)

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """Parse size string like '512M' or '2G' to bytes."""
        units = {
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4,
        }

        match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT])$', size_str.upper())
        if not match:
            raise ValueError(f"Invalid size format: {size_str}")

        value, unit = match.groups()
        return int(float(value) * units[unit])


@dataclass
class DatabaseService:
    """Database service configuration."""
    enabled: bool = False
    type: str = "postgresql"
    version: Optional[str] = None


@dataclass
class CacheService:
    """Cache service configuration."""
    enabled: bool = False
    type: str = "redis"


@dataclass
class BackgroundTasksService:
    """Background tasks configuration."""
    enabled: bool = False
    type: str = "celery"
    workers: int = 2
    beat: bool = False


@dataclass
class StorageService:
    """Storage service configuration."""
    enabled: bool = False
    type: str = "local"
    quota: str = "1G"


@dataclass
class Services:
    """All services configuration."""
    database: DatabaseService = field(default_factory=DatabaseService)
    cache: CacheService = field(default_factory=CacheService)
    storage: StorageService = field(default_factory=StorageService)
    background_tasks: BackgroundTasksService = field(default_factory=BackgroundTasksService)


@dataclass
class Network:
    """Network configuration."""
    http_port: bool = True
    https: bool = False
    websockets: bool = False


@dataclass
class Permissions:
    """Security permissions."""
    filesystem: Dict[str, List[str]] = field(default_factory=lambda: {
        'read': [],
        'write': []
    })
    network: Dict[str, Any] = field(default_factory=lambda: {
        'outbound': True,
        'allowed_hosts': []
    })
    processes: Dict[str, Any] = field(default_factory=lambda: {
        'max_processes': 10,
        'can_fork': True
    })


@dataclass
class AppContract:
    """Complete app contract specification."""
    version: str = "1.0"
    name: str = ""
    type: str = "django"
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    services: Services = field(default_factory=Services)
    network: Network = field(default_factory=Network)
    permissions: Permissions = field(default_factory=Permissions)
    build: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=dict)
    hooks: Dict[str, List[str]] = field(default_factory=dict)
    monitoring: Dict[str, Any] = field(default_factory=dict)
    backup: Dict[str, Any] = field(default_factory=dict)


class ContractParser:
    """Parse and validate app contracts."""

    ALLOWED_TYPES = ['django', 'static', 'nodejs', 'docker']
    CONTRACT_FILENAMES = ['webops.yml', 'webops.yaml', '.webops.yml', 'webops.json']

    def __init__(self, repo_path: Path):
        """
        Initialize contract parser.

        Args:
            repo_path: Path to cloned repository
        """
        self.repo_path = Path(repo_path)

    def find_contract_file(self) -> Optional[Path]:
        """Find contract file in repository."""
        for filename in self.CONTRACT_FILENAMES:
            contract_path = self.repo_path / filename
            if contract_path.exists():
                return contract_path
        return None

    def parse(self) -> AppContract:
        """
        Parse contract file or auto-detect configuration.

        Returns:
            AppContract instance

        Raises:
            ValueError: If contract is invalid
        """
        contract_file = self.find_contract_file()

        if contract_file:
            return self._parse_file(contract_file)
        else:
            return self._auto_detect()

    def _parse_file(self, contract_path: Path) -> AppContract:
        """Parse contract from YAML or JSON file."""
        with open(contract_path, 'r') as f:
            if contract_path.suffix in ['.yml', '.yaml']:
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        return self._dict_to_contract(data)

    def _dict_to_contract(self, data: Dict[str, Any]) -> AppContract:
        """Convert dictionary to AppContract."""
        contract = AppContract()

        # Basic fields
        contract.version = data.get('version', '1.0')
        contract.name = data.get('name', '')
        contract.type = data.get('type', 'django')

        # Validate type
        if contract.type not in self.ALLOWED_TYPES:
            raise ValueError(
                f"Invalid app type '{contract.type}'. "
                f"Allowed: {', '.join(self.ALLOWED_TYPES)}"
            )

        # Resources
        if 'resources' in data:
            r = data['resources']
            contract.resources = ResourceLimits(
                memory=r.get('memory', '256M'),
                cpu=r.get('cpu', '0.25'),
                disk=r.get('disk', '1G')
            )

        # Services
        if 'services' in data:
            services = data['services']

            if 'database' in services:
                db = services['database']
                contract.services.database = DatabaseService(
                    enabled=db.get('enabled', False),
                    type=db.get('type', 'postgresql'),
                    version=db.get('version')
                )

            if 'cache' in services:
                cache = services['cache']
                contract.services.cache = CacheService(
                    enabled=cache.get('enabled', False),
                    type=cache.get('type', 'redis')
                )

            if 'background_tasks' in services:
                bg = services['background_tasks']
                contract.services.background_tasks = BackgroundTasksService(
                    enabled=bg.get('enabled', False),
                    type=bg.get('type', 'celery'),
                    workers=bg.get('workers', 2),
                    beat=bg.get('beat', False)
                )

            if 'storage' in services:
                storage = services['storage']
                contract.services.storage = StorageService(
                    enabled=storage.get('enabled', False),
                    type=storage.get('type', 'local'),
                    quota=storage.get('quota', '1G')
                )

        # Network
        if 'network' in data:
            n = data['network']
            contract.network = Network(
                http_port=n.get('http_port', True),
                https=n.get('https', False),
                websockets=n.get('websockets', False)
            )

        # Permissions
        if 'permissions' in data:
            p = data['permissions']
            contract.permissions = Permissions(
                filesystem=p.get('filesystem', {'read': [], 'write': []}),
                network=p.get('network', {'outbound': True, 'allowed_hosts': []}),
                processes=p.get('processes', {'max_processes': 10, 'can_fork': True})
            )

        # Optional fields
        contract.build = data.get('build', {})
        contract.runtime = data.get('runtime', {})
        contract.hooks = data.get('hooks', {})
        contract.monitoring = data.get('monitoring', {})
        contract.backup = data.get('backup', {})

        return contract

    def _auto_detect(self) -> AppContract:
        """Auto-detect app type and generate default contract."""
        contract = AppContract()

        # Detect Django
        if (self.repo_path / 'manage.py').exists():
            contract.type = 'django'
            contract.services.database.enabled = True
            contract.network.https = True
            return contract

        # Detect Node.js
        if (self.repo_path / 'package.json').exists():
            contract.type = 'nodejs'
            contract.network.https = True
            return contract

        # Detect static site
        if (self.repo_path / 'index.html').exists():
            contract.type = 'static'
            contract.resources.memory = '128M'
            contract.resources.cpu = '0.1'
            contract.network.https = True
            return contract

        # Default to Django
        contract.type = 'django'
        contract.services.database.enabled = True
        return contract

    def validate(self, contract: AppContract) -> List[str]:
        """
        Validate contract for security and resource constraints.

        Args:
            contract: Contract to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate resource limits
        try:
            memory_mb = contract.resources.memory_bytes() / (1024 ** 2)
            if memory_mb < 128:
                errors.append("Memory must be at least 128M")
            elif memory_mb > 8192:
                errors.append("Memory cannot exceed 8G")
        except ValueError as e:
            errors.append(f"Invalid memory format: {e}")

        try:
            cpu = contract.resources.cpu_float()
            if cpu < 0.1:
                errors.append("CPU must be at least 0.1")
            elif cpu > 4.0:
                errors.append("CPU cannot exceed 4.0")
        except ValueError:
            errors.append("Invalid CPU format")

        try:
            disk_gb = contract.resources.disk_bytes() / (1024 ** 3)
            if disk_gb < 0.1:
                errors.append("Disk must be at least 100M")
            elif disk_gb > 50:
                errors.append("Disk cannot exceed 50G")
        except ValueError as e:
            errors.append(f"Invalid disk format: {e}")

        # Validate filesystem permissions
        for path in contract.permissions.filesystem.get('write', []):
            if not self._is_safe_path(path):
                errors.append(f"Unsafe write path: {path}")

        # Validate processes
        max_proc = contract.permissions.processes.get('max_processes', 10)
        if max_proc < 1 or max_proc > 100:
            errors.append("max_processes must be between 1 and 100")

        return errors

    def _is_safe_path(self, path: str) -> bool:
        """Check if filesystem path is safe for app access."""
        # Prevent access to sensitive paths
        forbidden_prefixes = [
            '/etc',
            '/root',
            '/var/log',
            '/usr/bin',
            '/usr/sbin',
            '/opt/webops/control-panel',
        ]

        for prefix in forbidden_prefixes:
            if path.startswith(prefix):
                return False

        # Only allow paths within deployment dir or shared dir
        allowed_prefixes = [
            '/opt/webops/deployments/',
            '/opt/webops/shared/',
        ]

        return any(path.startswith(prefix) for prefix in allowed_prefixes)
