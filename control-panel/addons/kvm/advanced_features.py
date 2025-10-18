"""
Advanced Features

VM cloning, GPU passthrough, and other advanced capabilities.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from lxml import etree

from .models import VMDeployment, ComputeNode
from .libvirt_manager import LibvirtManager

logger = logging.getLogger(__name__)


class VMCloner:
    """
    Clone VMs for scaling and testing.
    """

    def clone_vm(
        self,
        source_vm: VMDeployment,
        new_name: str,
        target_node: Optional[ComputeNode] = None,
    ) -> VMDeployment:
        """
        Clone a VM to create an identical copy.

        Args:
            source_vm: Source VM to clone
            new_name: Name for the cloned VM
            target_node: Target node (same as source if None)

        Returns:
            New VMDeployment instance
        """
        if not target_node:
            target_node = source_vm.compute_node

        logger.info(f"Cloning VM {source_vm.vm_name} to {new_name}")

        # 1. Clone disk
        new_disk_path = self._clone_disk(source_vm.disk_path, new_name)

        # 2. Get source VM XML
        with LibvirtManager(source_vm.compute_node.libvirt_uri) as mgr:
            domain = mgr.conn.lookupByName(source_vm.vm_name)
            xml = domain.XMLDesc()

        # 3. Modify XML for new VM
        root = etree.fromstring(xml)

        # Change name
        name_elem = root.find('name')
        name_elem.text = f"webops-vm-clone-{new_name}"

        # Remove UUID (will be auto-generated)
        uuid_elem = root.find('uuid')
        if uuid_elem is not None:
            root.remove(uuid_elem)

        # Update disk path
        for disk in root.xpath("//disk[@type='file']/source"):
            old_path = disk.get('file')
            if old_path == source_vm.disk_path:
                disk.set('file', new_disk_path)

        # Generate new MAC address
        for mac in root.xpath("//interface/mac"):
            mac.set('address', self._generate_mac())

        new_xml = etree.tostring(root, encoding='unicode')

        # 4. Define and start cloned VM
        with LibvirtManager(target_node.libvirt_uri) as mgr:
            new_domain = mgr.define_domain(new_xml)
            mgr.start_domain(new_domain.name())

            # Wait for IP
            ip_address = mgr.get_domain_ip(new_domain.name(), timeout=120)

        # 5. Create VMDeployment record
        # Note: Would need to create parent Deployment first
        # This is simplified - full implementation would handle this

        logger.info(f"VM cloned successfully: {new_name}")

        return None  # Return new VMDeployment in full implementation

    def _clone_disk(self, source_disk: str, clone_name: str) -> str:
        """Clone VM disk using qemu-img."""
        source_path = Path(source_disk)
        clone_path = source_path.parent / f"{clone_name}.qcow2"

        logger.info(f"Cloning disk: {source_disk} -> {clone_path}")

        # Use qemu-img to create linked clone (fast)
        subprocess.run(
            [
                'qemu-img', 'create',
                '-f', 'qcow2',
                '-F', 'qcow2',
                '-b', source_disk,
                str(clone_path),
            ],
            check=True,
            capture_output=True,
        )

        return str(clone_path)

    def _generate_mac(self) -> str:
        """Generate random MAC address."""
        import random
        mac = [0x52, 0x54, 0x00,
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(f'{octet:02x}' for octet in mac)


class GPUPassthrough:
    """
    GPU passthrough configuration for VMs.
    """

    def __init__(self):
        pass

    def list_available_gpus(self) -> List[Dict[str, Any]]:
        """
        List GPUs available for passthrough.

        Returns:
            List of GPU information dictionaries
        """
        gpus = []

        try:
            # List PCI devices
            result = subprocess.run(
                ['lspci', '-nn'],
                capture_output=True,
                text=True,
                check=True
            )

            for line in result.stdout.splitlines():
                if 'VGA' in line or 'Display' in line or '3D' in line:
                    # Parse PCI address and info
                    parts = line.split(' ', 1)
                    pci_address = parts[0]
                    info = parts[1] if len(parts) > 1 else ''

                    # Get IOMMU group
                    iommu_group = self._get_iommu_group(pci_address)

                    gpus.append({
                        'pci_address': pci_address,
                        'info': info,
                        'iommu_group': iommu_group,
                        'available': iommu_group is not None,
                    })

        except Exception as e:
            logger.error(f"Failed to list GPUs: {e}")

        return gpus

    def _get_iommu_group(self, pci_address: str) -> Optional[int]:
        """Get IOMMU group for PCI device."""
        try:
            iommu_path = Path(f"/sys/bus/pci/devices/0000:{pci_address}/iommu_group")
            if iommu_path.exists():
                group = iommu_path.resolve().name
                return int(group)
        except Exception:
            pass
        return None

    def configure_gpu_passthrough(
        self,
        vm_deployment: VMDeployment,
        gpu_pci_address: str,
    ) -> bool:
        """
        Configure GPU passthrough for a VM.

        Args:
            vm_deployment: VM to configure
            gpu_pci_address: PCI address of GPU (e.g., '01:00.0')

        Returns:
            True if successful
        """
        logger.info(f"Configuring GPU passthrough for {vm_deployment.vm_name}: {gpu_pci_address}")

        try:
            # 1. Unbind GPU from host driver
            self._unbind_device(gpu_pci_address)

            # 2. Bind to VFIO driver
            self._bind_to_vfio(gpu_pci_address)

            # 3. Update VM XML
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
                domain = mgr.conn.lookupByName(vm_deployment.vm_name)
                xml = domain.XMLDesc()

                root = etree.fromstring(xml)

                # Add hostdev element for GPU
                devices = root.find('devices')

                hostdev = etree.SubElement(
                    devices,
                    'hostdev',
                    mode='subsystem',
                    type='pci',
                    managed='yes'
                )

                source = etree.SubElement(hostdev, 'source')

                # Parse PCI address
                bus, slot_func = gpu_pci_address.split(':')
                slot, func = slot_func.split('.')

                address = etree.SubElement(
                    source,
                    'address',
                    domain='0x0000',
                    bus=f'0x{bus}',
                    slot=f'0x{slot}',
                    function=f'0x{func}'
                )

                new_xml = etree.tostring(root, encoding='unicode')

                # Redefine VM
                mgr.conn.defineXML(new_xml)

            logger.info(f"GPU passthrough configured successfully")
            return True

        except Exception as e:
            logger.error(f"GPU passthrough configuration failed: {e}")
            return False

    def _unbind_device(self, pci_address: str):
        """Unbind device from current driver."""
        driver_path = Path(f"/sys/bus/pci/devices/0000:{pci_address}/driver/unbind")
        if driver_path.exists():
            with open(driver_path, 'w') as f:
                f.write(f"0000:{pci_address}")

    def _bind_to_vfio(self, pci_address: str):
        """Bind device to VFIO driver."""
        # Get vendor and device ID
        with open(f"/sys/bus/pci/devices/0000:{pci_address}/vendor") as f:
            vendor = f.read().strip()
        with open(f"/sys/bus/pci/devices/0000:{pci_address}/device") as f:
            device = f.read().strip()

        # Bind to vfio-pci
        with open("/sys/bus/pci/drivers/vfio-pci/new_id", 'w') as f:
            f.write(f"{vendor[2:]} {device[2:]}")

    def check_iommu_enabled(self) -> bool:
        """Check if IOMMU is enabled."""
        try:
            result = subprocess.run(
                ['dmesg', '|', 'grep', '-e', 'DMAR', '-e', 'IOMMU'],
                shell=True,
                capture_output=True,
                text=True
            )
            return 'IOMMU enabled' in result.stdout or 'DMAR' in result.stdout
        except Exception:
            return False


class AdvancedMonitoring:
    """
    Advanced monitoring and performance metrics.
    """

    def get_vm_performance_stats(self, vm_deployment: VMDeployment) -> Dict[str, Any]:
        """
        Get detailed performance statistics for a VM.

        Returns:
            Dictionary with CPU, memory, disk, network stats
        """
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
                domain = mgr.conn.lookupByName(vm_deployment.vm_name)

                # CPU stats
                cpu_stats = domain.getCPUStats(True)

                # Memory stats
                mem_stats = domain.memoryStats()

                # Block I/O stats
                block_stats = {}
                try:
                    block_stats = domain.blockStats('vda')
                except:
                    pass

                # Network stats
                net_stats = {}
                try:
                    ifaces = domain.interfaceStats('vnet0')
                    net_stats = {
                        'rx_bytes': ifaces[0],
                        'rx_packets': ifaces[1],
                        'tx_bytes': ifaces[4],
                        'tx_packets': ifaces[5],
                    }
                except:
                    pass

                return {
                    'cpu': cpu_stats,
                    'memory': mem_stats,
                    'block': block_stats,
                    'network': net_stats,
                    'timestamp': timezone.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get VM stats: {e}")
            return {}

    def get_vm_console_screenshot(self, vm_deployment: VMDeployment) -> Optional[bytes]:
        """
        Capture a screenshot of VM console.

        Returns:
            PNG image data or None
        """
        try:
            with LibvirtManager(vm_deployment.compute_node.libvirt_uri) as mgr:
                domain = mgr.conn.lookupByName(vm_deployment.vm_name)

                # Get screenshot stream
                stream = mgr.conn.newStream()
                mime_type = domain.screenshot(stream, 0)

                # Read screenshot data
                screenshot_data = b''

                def handler(stream, data, opaque):
                    nonlocal screenshot_data
                    screenshot_data += data

                stream.recvAll(handler, None)
                stream.finish()

                return screenshot_data

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None
