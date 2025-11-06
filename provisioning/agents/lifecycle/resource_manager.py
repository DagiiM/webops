"""
Resource Management Module

Manages system resources, allocation, and monitoring for the AI agent.
"""

import asyncio
import json
import logging
import psutil
import threading
import time
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import uuid
import gc
import os


class ResourceType(Enum):
    """Types of system resources."""
    
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    STORAGE = "storage"
    GPU = "gpu"
    THREADS = "threads"
    FILE_HANDLES = "file_handles"
    DATABASE_CONNECTIONS = "database_connections"
    API_REQUESTS = "api_requests"
    TEMPORARY_STORAGE = "temporary_storage"


class ResourceState(Enum):
    """States of system resources."""
    
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    RESERVED = "reserved"
    THROTTLED = "throttled"
    EXHAUSTED = "exhausted"
    ERROR = "error"


class ResourcePriority(Enum):
    """Priority levels for resource allocation."""
    
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class Resource:
    """A system resource with properties."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    state: ResourceState = ResourceState.AVAILABLE
    total_capacity: float = 0.0  # Total available capacity
    available_capacity: float = 0.0  # Currently available capacity
    allocated_capacity: float = 0.0  # Currently allocated capacity
    used_capacity: float = 0.0  # Currently used capacity
    utilization_rate: float = 0.0  # 0.0 to 1.0
    priority: ResourcePriority = ResourcePriority.MEDIUM
    max_allocation: float = 1.0  # Maximum allocation for this resource
    min_allocation: float = 0.0  # Minimum allocation for this resource
    allocation_unit: str = "units"  # What unit is used (cores, MB, etc.)
    reserved_capacity: float = 0.0  # Capacity reserved for system use
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert resource to dictionary."""
        data = asdict(self)
        data['resource_type'] = self.resource_type.value
        data['state'] = self.state.value
        data['priority'] = self.priority.value
        data['last_updated'] = self.last_updated.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Resource':
        """Create resource from dictionary."""
        if 'resource_type' in data and isinstance(data['resource_type'], str):
            data['resource_type'] = ResourceType(data['resource_type'])
        if 'state' in data and isinstance(data['state'], str):
            data['state'] = ResourceState(data['state'])
        if 'priority' in data and isinstance(data['priority'], str):
            data['priority'] = ResourcePriority(data['priority'])
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        return cls(**data)


@dataclass
class ResourceAllocation:
    """Allocation of resources to a specific purpose."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    allocated_to: str = ""  # Task or component ID
    purpose: str = ""
    allocated_amount: float = 0.0
    allocated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    status: str = "active"  # active, expired, released, error
    actual_usage: float = 0.0  # Actual usage compared to allocation
    efficiency: float = 1.0  # How efficiently the allocation is being used
    priority: ResourcePriority = ResourcePriority.MEDIUM
    parent_allocation: Optional[str] = None  # Parent allocation ID
    children_allocations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert allocation to dictionary."""
        data = asdict(self)
        data['allocated_at'] = self.allocated_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceAllocation':
        """Create allocation from dictionary."""
        if 'allocated_at' in data and isinstance(data['allocated_at'], str):
            data['allocated_at'] = datetime.fromisoformat(data['allocated_at'])
        if 'expires_at' in data and isinstance(data['expires_at'], str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if 'priority' in data and isinstance(data['priority'], str):
            data['priority'] = ResourcePriority(data['priority'])
        return cls(**data)


@dataclass
class ResourcePool:
    """A pool of similar resources."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    resource_type: ResourceType = ResourceType.CPU
    resources: List[str] = field(default_factory=list)  # Resource IDs
    total_capacity: float = 0.0
    available_capacity: float = 0.0
    allocated_capacity: float = 0.0
    utilization_rate: float = 0.0
    max_utilization: float = 0.9  # Maximum utilization threshold
    min_reserved_capacity: float = 0.1  # Minimum reserved capacity
    allocation_strategy: str = "round_robin"  # round_robin, priority, first_fit, best_fit
    auto_scaling: bool = False
    scaling_triggers: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pool to dictionary."""
        data = asdict(self)
        data['resource_type'] = self.resource_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourcePool':
        """Create pool from dictionary."""
        if 'resource_type' in data and isinstance(data['resource_type'], str):
            data['resource_type'] = ResourceType(data['resource_type'])
        return cls(**data)


class ResourceManager:
    """Manages system resources and allocations."""
    
    def __init__(self, config):
        """Initialize the resource manager."""
        self.config = config
        self.logger = logging.getLogger("resource_manager")
        
        # Storage
        self._resources: Dict[str, Resource] = {}
        self._allocations: Dict[str, ResourceAllocation] = {}
        self._pools: Dict[str, ResourcePool] = {}
        
        # Monitoring
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._monitoring_interval = 5.0  # seconds
        self._resource_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Statistics
        self._total_allocations = 0
        self._total_freed = 0
        self._peak_utilization: Dict[ResourceType, float] = {
            resource_type: 0.0 for resource_type in ResourceType
        }
        self._allocation_history: List[Dict[str, Any]] = []
        
        # Thresholds and limits
        self._thresholds = {
            ResourceType.CPU: 0.8,
            ResourceType.MEMORY: 0.85,
            ResourceType.DISK: 0.9,
            ResourceType.NETWORK: 0.7,
            ResourceType.STORAGE: 0.9
        }
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    async def initialize(self) -> None:
        """Initialize the resource manager."""
        try:
            # Initialize system resource discovery
            await self._discover_system_resources()
            
            # Start monitoring
            await self.start_monitoring()
            
            # Load saved state
            await self._load_saved_state()
            
            self.logger.info("Resource manager initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing resource manager: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown the resource manager."""
        try:
            # Stop monitoring
            await self.stop_monitoring()
            
            # Clean up resources
            await self._cleanup_resources()
            
            # Save state
            await self._save_state()
            
            self.logger.info("Resource manager shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during resource manager shutdown: {e}")
    
    async def allocate_resource(
        self,
        resource_type: ResourceType,
        amount: float,
        purpose: str,
        allocated_to: str,
        priority: ResourcePriority = ResourcePriority.MEDIUM,
        expires_at: Optional[datetime] = None
    ) -> Optional[str]:
        """Allocate resources of a specific type."""
        try:
            with self._lock:
                # Find best resource pool
                pool = await self._find_best_pool(resource_type, amount, priority)
                if not pool:
                    self.logger.warning(f"No suitable pool found for {resource_type.value}")
                    return None
                
                # Find best resource in pool
                resource = await self._find_best_resource(pool, amount)
                if not resource:
                    self.logger.warning(f"No suitable resource found in pool {pool.id}")
                    return None
                
                # Create allocation
                allocation = ResourceAllocation(
                    resource_id=resource.id,
                    allocated_to=allocated_to,
                    purpose=purpose,
                    allocated_amount=amount,
                    expires_at=expires_at,
                    priority=priority
                )
                
                # Update resource state
                resource.available_capacity -= amount
                resource.allocated_capacity += amount
                resource.state = ResourceState.ALLOCATED if resource.available_capacity <= 0 else ResourceState.RESERVED
                resource.last_updated = datetime.now()
                
                # Update pool state
                pool.available_capacity -= amount
                pool.allocated_capacity += amount
                pool.utilization_rate = pool.allocated_capacity / pool.total_capacity if pool.total_capacity > 0 else 0.0
                
                # Store allocation
                self._allocations[allocation.id] = allocation
                
                # Update statistics
                self._total_allocations += 1
                
                # Check for auto-scaling
                if pool.auto_scaling:
                    await self._check_scaling_triggers(pool)
                
                self.logger.info(
                    f"Allocated {amount} {resource.allocation_unit} of {resource_type.value} "
                    f"to {allocated_to} (allocation ID: {allocation.id})"
                )
                
                return allocation.id
                
        except Exception as e:
            self.logger.error(f"Error allocating resource: {e}")
            return None
    
    async def release_resource(self, allocation_id: str) -> bool:
        """Release a resource allocation."""
        try:
            with self._lock:
                if allocation_id not in self._allocations:
                    self.logger.warning(f"Allocation {allocation_id} not found")
                    return False
                
                allocation = self._allocations[allocation_id]
                
                if allocation.status != "active":
                    self.logger.warning(f"Allocation {allocation_id} is not active")
                    return False
                
                # Find resource
                resource = self._resources.get(allocation.resource_id)
                if not resource:
                    self.logger.error(f"Resource {allocation.resource_id} not found")
                    return False
                
                # Release allocation
                allocation.status = "released"
                allocation.expires_at = datetime.now()
                
                # Update resource state
                resource.available_capacity += allocation.allocated_amount
                resource.allocated_capacity -= allocation.allocated_amount
                resource.state = ResourceState.AVAILABLE if resource.available_capacity > 0 else ResourceState.RESERVED
                resource.last_updated = datetime.now()
                
                # Update pool state
                pool = self._get_pool_for_resource(resource.id)
                if pool:
                    pool.available_capacity += allocation.allocated_amount
                    pool.allocated_capacity -= allocation.allocated_amount
                    pool.utilization_rate = pool.allocated_capacity / pool.total_capacity if pool.total_capacity > 0 else 0.0
                
                # Update statistics
                self._total_freed += 1
                
                self.logger.info(f"Released allocation {allocation_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error releasing resource: {e}")
            return False
    
    async def get_resource_status(
        self,
        resource_type: Optional[ResourceType] = None,
        allocation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get current resource status."""
        try:
            with self._lock:
                status = {
                    'timestamp': datetime.now().isoformat(),
                    'resources': {},
                    'pools': {},
                    'allocations': {},
                    'summary': {}
                }
                
                # Filter by resource type if specified
                filtered_resources = self._resources
                if resource_type:
                    filtered_resources = {
                        rid: resource for rid, resource in self._resources.items()
                        if resource.resource_type == resource_type
                    }
                
                # Get resource status
                for resource_id, resource in filtered_resources.items():
                    status['resources'][resource_id] = resource.to_dict()
                
                # Get pool status
                for pool_id, pool in self._pools.items():
                    status['pools'][pool_id] = pool.to_dict()
                
                # Filter by allocation ID if specified
                filtered_allocations = self._allocations
                if allocation_id:
                    filtered_allocations = {
                        aid: allocation for aid, allocation in self._allocations.items()
                        if aid == allocation_id
                    }
                
                # Get allocation status
                for allocation_id, allocation in filtered_allocations.items():
                    status['allocations'][allocation_id] = allocation.to_dict()
                
                # Generate summary
                summary = await self._generate_summary()
                status['summary'] = summary
                
                return status
                
        except Exception as e:
            self.logger.error(f"Error getting resource status: {e}")
            return {'error': str(e)}
    
    async def check_resource_availability(
        self,
        resource_type: ResourceType,
        amount: float
    ) -> Dict[str, Any]:
        """Check if resources are available."""
        try:
            # Find suitable pools
            suitable_pools = [
                pool for pool in self._pools.values()
                if pool.resource_type == resource_type and pool.available_capacity >= amount
            ]
            
            # Find suitable resources
            suitable_resources = [
                resource for resource in self._resources.values()
                if (resource.resource_type == resource_type and
                    resource.available_capacity >= amount)
            ]
            
            availability = {
                'available': len(suitable_resources) > 0,
                'suitable_pools': len(suitable_pools),
                'suitable_resources': len(suitable_resources),
                'total_available_capacity': sum(
                    resource.available_capacity
                    for resource in suitable_resources
                ),
                'requested_amount': amount,
                'allocation_recommendation': None
            }
            
            # Provide allocation recommendation
            if suitable_resources:
                best_resource = max(
                    suitable_resources,
                    key=lambda r: r.available_capacity
                )
                availability['allocation_recommendation'] = {
                    'resource_id': best_resource.id,
                    'resource_name': best_resource.name,
                    'available_capacity': best_resource.available_capacity
                }
            
            return availability
            
        except Exception as e:
            self.logger.error(f"Error checking resource availability: {e}")
            return {'error': str(e)}
    
    async def optimize_allocation(self, allocation_id: str) -> Dict[str, Any]:
        """Optimize a resource allocation."""
        try:
            if allocation_id not in self._allocations:
                return {'error': 'Allocation not found'}
            
            allocation = self._allocations[allocation_id]
            resource = self._resources.get(allocation.resource_id)
            
            if not resource:
                return {'error': 'Resource not found'}
            
            # Calculate optimal allocation based on usage patterns
            optimal_allocation = await self._calculate_optimal_allocation(allocation)
            
            # Adjust allocation if needed
            if abs(optimal_allocation - allocation.allocated_amount) > 0.1:
                allocation.allocated_amount = optimal_allocation
                allocation.efficiency = min(1.0, allocation.actual_usage / optimal_allocation)
                
                self.logger.info(f"Optimized allocation {allocation_id} to {optimal_allocation}")
            
            return {
                'allocation_id': allocation_id,
                'current_allocation': allocation.allocated_amount,
                'optimal_allocation': optimal_allocation,
                'efficiency': allocation.efficiency,
                'adjustment_needed': abs(optimal_allocation - allocation.allocated_amount) > 0.1
            }
            
        except Exception as e:
            self.logger.error(f"Error optimizing allocation: {e}")
            return {'error': str(e)}
    
    async def get_resource_statistics(self) -> Dict[str, Any]:
        """Get resource management statistics."""
        try:
            with self._lock:
                stats = {
                    'timestamp': datetime.now().isoformat(),
                    'resources': {
                        'total': len(self._resources),
                        'by_type': {},
                        'by_state': {}
                    },
                    'allocations': {
                        'total': len(self._allocations),
                        'active': len([a for a in self._allocations.values() if a.status == 'active']),
                        'expired': len([a for a in self._allocations.values() if a.expires_at and a.expires_at < datetime.now()]),
                        'total_allocated': sum(a.allocated_amount for a in self._allocations.values() if a.status == 'active')
                    },
                    'pools': {
                        'total': len(self._pools),
                        'by_type': {},
                        'auto_scaling': len([p for p in self._pools.values() if p.auto_scaling])
                    },
                    'performance': {
                        'total_allocations': self._total_allocations,
                        'total_freed': self._total_freed,
                        'peak_utilization': {rt.value: peak for rt, peak in self._peak_utilization.items()},
                        'utilization_by_type': await self._calculate_utilization_by_type()
                    },
                    'alerts': {
                        'resource_warnings': len([r for r in self._resources.values() if r.warnings]),
                        'resource_errors': len([r for r in self._resources.values() if r.errors]),
                        'throttled_resources': len([r for r in self._resources.values() if r.state == ResourceState.THROTTLED])
                    }
                }
                
                # Resource by type
                for resource_type in ResourceType:
                    count = len([r for r in self._resources.values() if r.resource_type == resource_type])
                    stats['resources']['by_type'][resource_type.value] = count
                
                # Resource by state
                for state in ResourceState:
                    count = len([r for r in self._resources.values() if r.state == state])
                    stats['resources']['by_state'][state.value] = count
                
                # Pools by type
                for resource_type in ResourceType:
                    count = len([p for p in self._pools.values() if p.resource_type == resource_type])
                    stats['pools']['by_type'][resource_type.value] = count
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting resource statistics: {e}")
            return {'error': str(e)}
    
    async def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        
        self.logger.info("Resource monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self._monitoring_active = False
        
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=10)
            self._monitoring_thread = None
        
        self.logger.info("Resource monitoring stopped")
    
    async def cleanup_expired_allocations(self) -> int:
        """Clean up expired allocations."""
        cleaned_count = 0
        current_time = datetime.now()
        
        with self._lock:
            expired_allocation_ids = [
                allocation_id for allocation_id, allocation in self._allocations.items()
                if allocation.expires_at and allocation.expires_at < current_time and allocation.status == 'active'
            ]
            
            for allocation_id in expired_allocation_ids:
                if await self.release_resource(allocation_id):
                    cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} expired allocations")
        
        return cleaned_count
    
    async def _discover_system_resources(self) -> None:
        """Discover system resources."""
        try:
            # CPU resources
            cpu_resource = Resource(
                name="CPU Pool",
                resource_type=ResourceType.CPU,
                total_capacity=psutil.cpu_count(),
                available_capacity=psutil.cpu_count(),
                allocation_unit="cores"
            )
            self._resources[cpu_resource.id] = cpu_resource
            
            # Memory resources
            memory = psutil.virtual_memory()
            memory_resource = Resource(
                name="Memory Pool",
                resource_type=ResourceType.MEMORY,
                total_capacity=memory.total,
                available_capacity=memory.available,
                allocation_unit="bytes",
                min_allocation=1024 * 1024 * 1024  # 1 GB minimum
            )
            self._resources[memory_resource.id] = memory_resource
            
            # Disk resources
            disk = psutil.disk_usage('/')
            disk_resource = Resource(
                name="Disk Pool",
                resource_type=ResourceType.DISK,
                total_capacity=disk.total,
                available_capacity=disk.free,
                allocation_unit="bytes"
            )
            self._resources[disk_resource.id] = disk_resource
            
            # Thread pool
            thread_resource = Resource(
                name="Thread Pool",
                resource_type=ResourceType.THREADS,
                total_capacity=1024,  # System-dependent
                available_capacity=1000,
                allocation_unit="threads"
            )
            self._resources[thread_resource.id] = thread_resource
            
            # Create resource pools
            await self._create_resource_pools()
            
            self.logger.info("System resources discovered")
            
        except Exception as e:
            self.logger.error(f"Error discovering system resources: {e}")
    
    async def _create_resource_pools(self) -> None:
        """Create resource pools."""
        try:
            # CPU pool
            cpu_resources = [rid for rid, r in self._resources.items() if r.resource_type == ResourceType.CPU]
            cpu_pool = ResourcePool(
                name="CPU Pool",
                resource_type=ResourceType.CPU,
                resources=cpu_resources,
                total_capacity=sum(self._resources[rid].total_capacity for rid in cpu_resources),
                available_capacity=sum(self._resources[rid].available_capacity for rid in cpu_resources)
            )
            self._pools[cpu_pool.id] = cpu_pool
            
            # Memory pool
            memory_resources = [rid for rid, r in self._resources.items() if r.resource_type == ResourceType.MEMORY]
            memory_pool = ResourcePool(
                name="Memory Pool",
                resource_type=ResourceType.MEMORY,
                resources=memory_resources,
                total_capacity=sum(self._resources[rid].total_capacity for rid in memory_resources),
                available_capacity=sum(self._resources[rid].available_capacity for rid in memory_resources)
            )
            self._pools[memory_pool.id] = memory_pool
            
            # Disk pool
            disk_resources = [rid for rid, r in self._resources.items() if r.resource_type == ResourceType.DISK]
            disk_pool = ResourcePool(
                name="Disk Pool",
                resource_type=ResourceType.DISK,
                resources=disk_resources,
                total_capacity=sum(self._resources[rid].total_capacity for rid in disk_resources),
                available_capacity=sum(self._resources[rid].available_capacity for rid in disk_resources)
            )
            self._pools[disk_pool.id] = disk_pool
            
            # Thread pool
            thread_resources = [rid for rid, r in self._resources.items() if r.resource_type == ResourceType.THREADS]
            thread_pool = ResourcePool(
                name="Thread Pool",
                resource_type=ResourceType.THREADS,
                resources=thread_resources,
                total_capacity=sum(self._resources[rid].total_capacity for rid in thread_resources),
                available_capacity=sum(self._resources[rid].available_capacity for rid in thread_resources)
            )
            self._pools[thread_pool.id] = thread_pool
            
            self.logger.info("Resource pools created")
            
        except Exception as e:
            self.logger.error(f"Error creating resource pools: {e}")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                await self._update_resource_metrics()
                await self._check_resource_thresholds()
                await self._cleanup_expired_allocations()
                await self._record_resource_history()
                
                time.sleep(self._monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self._monitoring_interval)
    
    async def _update_resource_metrics(self) -> None:
        """Update real-time resource metrics."""
        try:
            # Update CPU metrics
            cpu_percent = psutil.cpu_percent()
            cpu_resource = next((r for r in self._resources.values() if r.resource_type == ResourceType.CPU), None)
            if cpu_resource:
                cpu_resource.utilization_rate = cpu_percent / 100.0
                cpu_resource.used_capacity = cpu_resource.total_capacity * cpu_resource.utilization_rate
                cpu_resource.last_updated = datetime.now()
            
            # Update memory metrics
            memory = psutil.virtual_memory()
            memory_resource = next((r for r in self._resources.values() if r.resource_type == ResourceType.MEMORY), None)
            if memory_resource:
                memory_resource.utilization_rate = memory.percent / 100.0
                memory_resource.available_capacity = memory.available
                memory_resource.used_capacity = memory.total - memory.available
                memory_resource.last_updated = datetime.now()
            
            # Update disk metrics
            disk = psutil.disk_usage('/')
            disk_resource = next((r for r in self._resources.values() if r.resource_type == ResourceType.DISK), None)
            if disk_resource:
                disk_resource.utilization_rate = (disk.total - disk.free) / disk.total if disk.total > 0 else 0.0
                disk_resource.available_capacity = disk.free
                disk_resource.used_capacity = disk.total - disk.free
                disk_resource.last_updated = datetime.now()
            
            # Update peak utilization
            for resource in self._resources.values():
                resource_type = resource.resource_type
                current_utilization = resource.utilization_rate
                if current_utilization > self._peak_utilization[resource_type]:
                    self._peak_utilization[resource_type] = current_utilization
            
        except Exception as e:
            self.logger.error(f"Error updating resource metrics: {e}")
    
    async def _check_resource_thresholds(self) -> None:
        """Check resource usage against thresholds."""
        try:
            for resource in self._resources.values():
                threshold = self._thresholds.get(resource.resource_type, 0.9)
                
                # Check for high usage
                if resource.utilization_rate > threshold:
                    if ResourceState.THROTTLED not in resource.state:
                        resource.warnings.append(f"High utilization: {resource.utilization_rate:.2%}")
                        resource.state = ResourceState.THROTTLED
                        
                        self.logger.warning(
                            f"Resource {resource.name} throttled due to high utilization: {resource.utilization_rate:.2%}"
                        )
                
                # Check for critical usage
                if resource.utilization_rate > threshold * 1.1:
                    resource.errors.append(f"Critical utilization: {resource.utilization_rate:.2%}")
                    resource.state = ResourceState.ERROR
                    
                    self.logger.error(
                        f"Resource {resource.name} in error state: {resource.utilization_rate:.2%}"
                    )
                
                # Clear warnings if usage is back to normal
                elif resource.utilization_rate < threshold * 0.8:
                    resource.warnings.clear()
                    if resource.state in [ResourceState.THROTTLED, ResourceState.ERROR]:
                        resource.state = ResourceState.AVAILABLE
                
                resource.last_updated = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error checking resource thresholds: {e}")
    
    async def _find_best_pool(
        self,
        resource_type: ResourceType,
        amount: float,
        priority: ResourcePriority
    ) -> Optional[ResourcePool]:
        """Find the best pool for allocation."""
        suitable_pools = [
            pool for pool in self._pools.values()
            if (pool.resource_type == resource_type and
                pool.available_capacity >= amount and
                pool.utilization_rate < pool.max_utilization)
        ]
        
        if not suitable_pools:
            return None
        
        # Sort by priority and availability
        suitable_pools.sort(key=lambda p: (p.utilization_rate, -p.available_capacity))
        
        return suitable_pools[0]
    
    async def _find_best_resource(
        self,
        pool: ResourcePool,
        amount: float
    ) -> Optional[Resource]:
        """Find the best resource in a pool."""
        pool_resources = [self._resources[rid] for rid in pool.resources if rid in self._resources]
        
        suitable_resources = [
            resource for resource in pool_resources
            if resource.available_capacity >= amount
        ]
        
        if not suitable_resources:
            return None
        
        # Sort by availability and utilization
        suitable_resources.sort(key=lambda r: (r.utilization_rate, -r.available_capacity))
        
        return suitable_resources[0]
    
    async def _get_pool_for_resource(self, resource_id: str) -> Optional[ResourcePool]:
        """Get the pool that contains a resource."""
        for pool in self._pools.values():
            if resource_id in pool.resources:
                return pool
        return None
    
    async def _calculate_optimal_allocation(self, allocation: ResourceAllocation) -> float:
        """Calculate optimal allocation based on usage patterns."""
        # This is a simplified calculation
        # In a real implementation, this would use historical data
        base_allocation = allocation.allocated_amount
        efficiency = allocation.efficiency
        
        # Adjust based on efficiency
        if efficiency > 0.9:
            # High efficiency, consider reducing allocation
            optimal = base_allocation * 0.9
        elif efficiency < 0.5:
            # Low efficiency, consider increasing allocation
            optimal = base_allocation * 1.1
        else:
            # Moderate efficiency, keep allocation
            optimal = base_allocation
        
        return max(allocation.allocated_amount * 0.5, optimal)  # Don't reduce below 50%
    
    async def _check_scaling_triggers(self, pool: ResourcePool) -> None:
        """Check if auto-scaling should be triggered."""
        try:
            if not pool.auto_scaling or not pool.scaling_triggers:
                return
            
            current_utilization = pool.utilization_rate
            
            # Scale up if utilization is high
            for trigger_name, trigger_threshold in pool.scaling_triggers.items():
                if trigger_name == "scale_up_threshold" and current_utilization > trigger_threshold:
                    await self._scale_pool_up(pool)
                    self.logger.info(f"Scaled up pool {pool.name} due to high utilization")
                    break
                
                elif trigger_name == "scale_down_threshold" and current_utilization < trigger_threshold:
                    await self._scale_pool_down(pool)
                    self.logger.info(f"Scaled down pool {pool.name} due to low utilization")
                    break
            
        except Exception as e:
            self.logger.error(f"Error checking scaling triggers: {e}")
    
    async def _scale_pool_up(self, pool: ResourcePool) -> None:
        """Scale a pool up (add more resources)."""
        # This is a simplified scaling implementation
        # In a real system, this would involve provisioning new resources
        pool.total_capacity *= 1.1
        pool.available_capacity *= 1.1
        self.logger.info(f"Scaled up pool {pool.name}")
    
    async def _scale_pool_down(self, pool: ResourcePool) -> None:
        """Scale a pool down (remove resources)."""
        # This is a simplified scaling implementation
        # In a real system, this would involve deprovisioning resources
        pool.total_capacity *= 0.9
        pool.available_capacity *= 0.9
        self.logger.info(f"Scaled down pool {pool.name}")
    
    async def _generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of resource status."""
        total_resources = len(self._resources)
        total_allocations = len(self._allocations)
        active_allocations = len([a for a in self._allocations.values() if a.status == 'active'])
        
        # Calculate overall utilization
        overall_utilization = 0.0
        if total_resources > 0:
            total_utilization = sum(r.utilization_rate for r in self._resources.values())
            overall_utilization = total_utilization / total_resources
        
        # Count resources by state
        resources_by_state = {}
        for state in ResourceState:
            count = len([r for r in self._resources.values() if r.state == state])
            resources_by_state[state.value] = count
        
        return {
            'total_resources': total_resources,
            'total_allocations': total_allocations,
            'active_allocations': active_allocations,
            'overall_utilization': overall_utilization,
            'resources_by_state': resources_by_state,
            'monitoring_active': self._monitoring_active
        }
    
    async def _calculate_utilization_by_type(self) -> Dict[str, float]:
        """Calculate utilization by resource type."""
        utilization_by_type = {}
        
        for resource_type in ResourceType:
            type_resources = [
                r for r in self._resources.values()
                if r.resource_type == resource_type
            ]
            
            if type_resources:
                avg_utilization = sum(r.utilization_rate for r in type_resources) / len(type_resources)
                utilization_by_type[resource_type.value] = avg_utilization
            else:
                utilization_by_type[resource_type.value] = 0.0
        
        return utilization_by_type
    
    async def _record_resource_history(self) -> None:
        """Record resource history for analysis."""
        try:
            current_time = datetime.now()
            
            for resource_id, resource in self._resources.items():
                if resource_id not in self._resource_history:
                    self._resource_history[resource_id] = []
                
                history_entry = {
                    'timestamp': current_time.isoformat(),
                    'utilization_rate': resource.utilization_rate,
                    'available_capacity': resource.available_capacity,
                    'allocated_capacity': resource.allocated_capacity,
                    'used_capacity': resource.used_capacity,
                    'state': resource.state.value
                }
                
                self._resource_history[resource_id].append(history_entry)
                
                # Keep history manageable
                if len(self._resource_history[resource_id]) > 1000:
                    self._resource_history[resource_id] = self._resource_history[resource_id][-500:]
            
        except Exception as e:
            self.logger.error(f"Error recording resource history: {e}")
    
    async def _cleanup_resources(self) -> None:
        """Clean up resources during shutdown."""
        try:
            # Release all active allocations
            active_allocation_ids = [
                allocation_id for allocation_id, allocation in self._allocations.items()
                if allocation.status == 'active'
            ]
            
            for allocation_id in active_allocation_ids:
                await self.release_resource(allocation_id)
            
            # Clear resource history to save memory
            self._resource_history.clear()
            
            self.logger.info("Resources cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up resources: {e}")
    
    async def _load_saved_state(self) -> None:
        """Load saved resource manager state."""
        # In a real implementation, this would load from persistent storage
        # For now, just initialize empty collections
        pass
    
    async def _save_state(self) -> None:
        """Save resource manager state."""
        # In a real implementation, this would save to persistent storage
        # For now, just log the event
        self.logger.info("Resource manager state saved")