"""
Libvirt Manager

Low-level libvirt operations for VM lifecycle management.
"""

import libvirt
import logging
import uuid
from typing import Optional, Dict, Any, List
from pathlib import Path
from lxml import etree

logger = logging.getLogger(__name__)


class LibvirtManager:
    """
    Manages libvirt connections and VM operations.
    """

    def __init__(self, uri: str = "qemu:///system"):
        self.uri = uri
        self._conn: Optional[libvirt.virConnect] = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self) -> libvirt.virConnect:
        """Establish libvirt connection."""
        if self._conn is None:
            try:
                self._conn = libvirt.open(self.uri)
                logger.info(f"Connected to libvirt: {self.uri}")
            except libvirt.libvirtError as e:
                logger.error(f"Failed to connect to libvirt: {e}")
                raise
        return self._conn

    def disconnect(self):
        """Close libvirt connection."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Disconnected from libvirt")
            except libvirt.libvirtError as e:
                logger.warning(f"Error closing libvirt connection: {e}")
            finally:
                self._conn = None

    @property
    def conn(self) -> libvirt.virConnect:
        """Get active connection (auto-connect if needed)."""
        if self._conn is None:
            self.connect()
        return self._conn

    def generate_domain_xml(
        self,
        vm_name: str,
        vcpus: int,
        memory_mb: int,
        disk_path: str,
        network_bridge: str = "virbr-webops",
        vnc_port: Optional[int] = None,
        mac_address: Optional[str] = None,
    ) -> str:
        """
        Generate libvirt domain XML for a VM.

        Args:
            vm_name: VM domain name
            vcpus: Number of virtual CPUs
            memory_mb: RAM in megabytes
            disk_path: Path to disk image
            network_bridge: Network bridge name
            vnc_port: VNC port (optional)
            mac_address: MAC address (optional, auto-generated if None)

        Returns:
            XML string for domain definition
        """
        vm_uuid = str(uuid.uuid4())
        if mac_address is None:
            mac_address = self._generate_mac_address()

        # Build domain XML using lxml for clean formatting
        domain = etree.Element("domain", type="kvm")

        # Basic metadata
        etree.SubElement(domain, "name").text = vm_name
        etree.SubElement(domain, "uuid").text = vm_uuid
        etree.SubElement(domain, "memory", unit="MiB").text = str(memory_mb)
        etree.SubElement(domain, "currentMemory", unit="MiB").text = str(memory_mb)
        etree.SubElement(domain, "vcpu", placement="static").text = str(vcpus)

        # OS configuration
        os_elem = etree.SubElement(domain, "os")
        etree.SubElement(os_elem, "type", arch="x86_64", machine="pc").text = "hvm"
        etree.SubElement(os_elem, "boot", dev="hd")

        # Features
        features = etree.SubElement(domain, "features")
        etree.SubElement(features, "acpi")
        etree.SubElement(features, "apic")

        # CPU configuration
        cpu = etree.SubElement(domain, "cpu", mode="host-passthrough")

        # Clock
        clock = etree.SubElement(domain, "clock", offset="utc")
        etree.SubElement(clock, "timer", name="rtc", tickpolicy="catchup")
        etree.SubElement(clock, "timer", name="pit", tickpolicy="delay")
        etree.SubElement(clock, "timer", name="hpet", present="no")

        # Power management
        etree.SubElement(domain, "on_poweroff").text = "destroy"
        etree.SubElement(domain, "on_reboot").text = "restart"
        etree.SubElement(domain, "on_crash").text = "destroy"

        # Devices
        devices = etree.SubElement(domain, "devices")

        # Disk
        disk = etree.SubElement(devices, "disk", type="file", device="disk")
        etree.SubElement(disk, "driver", name="qemu", type="qcow2", cache="writeback")
        etree.SubElement(disk, "source", file=disk_path)
        etree.SubElement(disk, "target", dev="vda", bus="virtio")

        # Network interface
        interface = etree.SubElement(devices, "interface", type="network")
        etree.SubElement(interface, "mac", address=mac_address)
        etree.SubElement(interface, "source", network=network_bridge)
        etree.SubElement(interface, "model", type="virtio")

        # Graphics (VNC)
        if vnc_port:
            graphics = etree.SubElement(
                devices, "graphics", type="vnc", port=str(vnc_port), listen="127.0.0.1"
            )
        else:
            graphics = etree.SubElement(
                devices, "graphics", type="vnc", port="-1", autoport="yes", listen="127.0.0.1"
            )

        # Serial console
        serial = etree.SubElement(devices, "serial", type="pty")
        etree.SubElement(serial, "target", type="isa-serial", port="0")
        etree.SubElement(serial, "model", name="isa-serial")

        console = etree.SubElement(devices, "console", type="pty")
        etree.SubElement(console, "target", type="serial", port="0")

        # Video
        video = etree.SubElement(devices, "video")
        etree.SubElement(video, "model", type="cirrus", vram="16384", heads="1")

        # Input devices
        etree.SubElement(devices, "input", type="tablet", bus="usb")
        etree.SubElement(devices, "input", type="mouse", bus="ps2")
        etree.SubElement(devices, "input", type="keyboard", bus="ps2")

        return etree.tostring(domain, encoding="unicode", pretty_print=True)

    def _generate_mac_address(self) -> str:
        """Generate a random MAC address for private use."""
        import random
        # Use 52:54:00 prefix (QEMU/KVM standard)
        mac = [0x52, 0x54, 0x00,
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(f'{octet:02x}' for octet in mac)

    def define_domain(self, xml: str) -> libvirt.virDomain:
        """
        Define a new domain from XML.

        Args:
            xml: Domain XML definition

        Returns:
            Defined domain object
        """
        try:
            domain = self.conn.defineXML(xml)
            logger.info(f"Defined domain: {domain.name()}")
            return domain
        except libvirt.libvirtError as e:
            logger.error(f"Failed to define domain: {e}")
            raise

    def start_domain(self, domain_name: str) -> bool:
        """Start a domain by name."""
        try:
            domain = self.conn.lookupByName(domain_name)
            if domain.isActive():
                logger.warning(f"Domain {domain_name} is already running")
                return True

            domain.create()
            logger.info(f"Started domain: {domain_name}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to start domain {domain_name}: {e}")
            return False

    def stop_domain(self, domain_name: str, force: bool = False) -> bool:
        """
        Stop a domain.

        Args:
            domain_name: Domain name
            force: If True, destroy immediately. If False, shutdown gracefully.
        """
        try:
            domain = self.conn.lookupByName(domain_name)
            if not domain.isActive():
                logger.warning(f"Domain {domain_name} is already stopped")
                return True

            if force:
                domain.destroy()
                logger.info(f"Destroyed domain: {domain_name}")
            else:
                domain.shutdown()
                logger.info(f"Shutdown domain: {domain_name}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to stop domain {domain_name}: {e}")
            return False

    def restart_domain(self, domain_name: str) -> bool:
        """Restart a domain."""
        try:
            domain = self.conn.lookupByName(domain_name)
            domain.reboot()
            logger.info(f"Rebooted domain: {domain_name}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to restart domain {domain_name}: {e}")
            return False

    def delete_domain(self, domain_name: str, delete_disk: bool = True) -> bool:
        """
        Delete a domain and optionally its disk.

        Args:
            domain_name: Domain name
            delete_disk: If True, delete associated disk images
        """
        try:
            domain = self.conn.lookupByName(domain_name)

            # Stop if running
            if domain.isActive():
                domain.destroy()

            # Get disk paths before undefining
            disk_paths = []
            if delete_disk:
                xml_desc = domain.XMLDesc()
                root = etree.fromstring(xml_desc)
                for disk in root.xpath("//disk[@type='file']/source"):
                    disk_path = disk.get('file')
                    if disk_path:
                        disk_paths.append(disk_path)

            # Undefine domain
            domain.undefine()
            logger.info(f"Undefined domain: {domain_name}")

            # Delete disk files
            if delete_disk:
                for disk_path in disk_paths:
                    try:
                        Path(disk_path).unlink()
                        logger.info(f"Deleted disk: {disk_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete disk {disk_path}: {e}")

            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to delete domain {domain_name}: {e}")
            return False

    def get_domain_state(self, domain_name: str) -> str:
        """
        Get domain state as string.

        Returns:
            One of: running, stopped, paused, crashed, undefined
        """
        try:
            domain = self.conn.lookupByName(domain_name)
            state, _ = domain.state()

            state_map = {
                libvirt.VIR_DOMAIN_NOSTATE: 'undefined',
                libvirt.VIR_DOMAIN_RUNNING: 'running',
                libvirt.VIR_DOMAIN_BLOCKED: 'blocked',
                libvirt.VIR_DOMAIN_PAUSED: 'paused',
                libvirt.VIR_DOMAIN_SHUTDOWN: 'shutdown',
                libvirt.VIR_DOMAIN_SHUTOFF: 'stopped',
                libvirt.VIR_DOMAIN_CRASHED: 'crashed',
                libvirt.VIR_DOMAIN_PMSUSPENDED: 'suspended',
            }
            return state_map.get(state, 'unknown')
        except libvirt.libvirtError:
            return 'undefined'

    def get_domain_info(self, domain_name: str) -> Dict[str, Any]:
        """Get detailed domain information."""
        try:
            domain = self.conn.lookupByName(domain_name)
            state, max_mem, memory, vcpus, cpu_time = domain.info()

            return {
                'name': domain.name(),
                'uuid': domain.UUIDString(),
                'state': self.get_domain_state(domain_name),
                'max_memory_mb': max_mem // 1024,
                'memory_mb': memory // 1024,
                'vcpus': vcpus,
                'cpu_time_ns': cpu_time,
                'is_active': domain.isActive() == 1,
                'is_persistent': domain.isPersistent() == 1,
            }
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get info for domain {domain_name}: {e}")
            return {}

    def get_domain_ip(self, domain_name: str, timeout: int = 120) -> Optional[str]:
        """
        Wait for domain to get an IP address via DHCP.

        Args:
            domain_name: Domain name
            timeout: Timeout in seconds

        Returns:
            IP address or None if timeout
        """
        import time

        try:
            domain = self.conn.lookupByName(domain_name)
            start_time = time.time()

            while time.time() - start_time < timeout:
                if not domain.isActive():
                    logger.warning(f"Domain {domain_name} is not active")
                    return None

                # Try to get IP from domain interfaces
                try:
                    ifaces = domain.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE)
                    for iface_name, iface in ifaces.items():
                        if iface['addrs']:
                            for addr in iface['addrs']:
                                if addr['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                                    ip = addr['addr']
                                    logger.info(f"Domain {domain_name} got IP: {ip}")
                                    return ip
                except libvirt.libvirtError:
                    pass

                time.sleep(5)

            logger.warning(f"Timeout waiting for IP for domain {domain_name}")
            return None
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get IP for domain {domain_name}: {e}")
            return None

    def create_snapshot(self, domain_name: str, snapshot_name: str, description: str = "") -> str:
        """
        Create a disk snapshot.

        Returns:
            Snapshot XML
        """
        try:
            domain = self.conn.lookupByName(domain_name)

            # Build snapshot XML
            snapshot = etree.Element("domainsnapshot")
            etree.SubElement(snapshot, "name").text = snapshot_name
            etree.SubElement(snapshot, "description").text = description

            snapshot_xml = etree.tostring(snapshot, encoding="unicode")

            # Create snapshot
            domain.snapshotCreateXML(snapshot_xml)
            logger.info(f"Created snapshot {snapshot_name} for domain {domain_name}")

            return snapshot_xml
        except libvirt.libvirtError as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise

    def restore_snapshot(self, domain_name: str, snapshot_name: str) -> bool:
        """Restore a domain to a snapshot."""
        try:
            domain = self.conn.lookupByName(domain_name)
            snapshot = domain.snapshotLookupByName(snapshot_name)
            domain.revertToSnapshot(snapshot)
            logger.info(f"Restored domain {domain_name} to snapshot {snapshot_name}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to restore snapshot: {e}")
            return False

    def delete_snapshot(self, domain_name: str, snapshot_name: str) -> bool:
        """Delete a snapshot."""
        try:
            domain = self.conn.lookupByName(domain_name)
            snapshot = domain.snapshotLookupByName(snapshot_name)
            snapshot.delete()
            logger.info(f"Deleted snapshot {snapshot_name} for domain {domain_name}")
            return True
        except libvirt.libvirtError as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return False

    def list_domains(self) -> List[str]:
        """List all domain names."""
        try:
            domains = self.conn.listAllDomains()
            return [d.name() for d in domains]
        except libvirt.libvirtError as e:
            logger.error(f"Failed to list domains: {e}")
            return []

    def get_hypervisor_info(self) -> Dict[str, Any]:
        """Get hypervisor information."""
        try:
            node_info = self.conn.getInfo()
            return {
                'model': node_info[0],
                'memory_mb': node_info[1],
                'cpus': node_info[2],
                'cpu_mhz': node_info[3],
                'numa_nodes': node_info[4],
                'cpu_sockets': node_info[5],
                'cpu_cores': node_info[6],
                'cpu_threads': node_info[7],
                'hypervisor': self.conn.getType(),
                'version': self.conn.getVersion(),
                'hostname': self.conn.getHostname(),
            }
        except libvirt.libvirtError as e:
            logger.error(f"Failed to get hypervisor info: {e}")
            return {}
