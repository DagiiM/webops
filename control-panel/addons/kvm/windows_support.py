"""
Windows VM Support

Specialized handling for Windows virtual machines.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from lxml import etree

logger = logging.getLogger(__name__)


class WindowsVMManager:
    """
    Manages Windows-specific VM configurations and drivers.
    """

    # VirtIO driver ISO URLs (latest stable)
    VIRTIO_WIN_ISO_URL = 'https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso'

    def __init__(self):
        self.virtio_iso_path = '/var/lib/webops/drivers/virtio-win.iso'

    def generate_windows_domain_xml(
        self,
        vm_name: str,
        vcpus: int,
        memory_mb: int,
        disk_path: str,
        iso_path: Optional[str] = None,
        network_bridge: str = 'virbr-webops',
        vnc_port: Optional[int] = None,
    ) -> str:
        """
        Generate libvirt domain XML optimized for Windows.

        Key differences from Linux VMs:
        - UEFI firmware (OVMF) instead of BIOS
        - Hyper-V enlightenments for better performance
        - VirtIO drivers with fallback
        - RTC clock
        - More video RAM

        Args:
            vm_name: VM domain name
            vcpus: Number of vCPUs
            memory_mb: RAM in MB
            disk_path: Path to Windows disk
            iso_path: Windows installation ISO (for first boot)
            network_bridge: Network bridge name
            vnc_port: VNC port

        Returns:
            XML string
        """
        import uuid as uuid_module

        vm_uuid = str(uuid_module.uuid4())

        domain = etree.Element("domain", type="kvm")

        # Basic metadata
        etree.SubElement(domain, "name").text = vm_name
        etree.SubElement(domain, "uuid").text = vm_uuid
        etree.SubElement(domain, "memory", unit="MiB").text = str(memory_mb)
        etree.SubElement(domain, "currentMemory", unit="MiB").text = str(memory_mb)
        etree.SubElement(domain, "vcpu", placement="static").text = str(vcpus)

        # OS configuration (UEFI for Windows)
        os_elem = etree.SubElement(domain, "os")
        etree.SubElement(os_elem, "type", arch="x86_64", machine="pc-q35-6.2").text = "hvm"

        # UEFI firmware (OVMF)
        loader = etree.SubElement(
            os_elem, "loader",
            readonly="yes",
            type="pflash"
        )
        loader.text = "/usr/share/OVMF/OVMF_CODE.fd"

        nvram = etree.SubElement(os_elem, "nvram")
        nvram.text = f"/var/lib/libvirt/qemu/nvram/{vm_name}_VARS.fd"

        # Boot order
        etree.SubElement(os_elem, "boot", dev="hd")
        if iso_path:
            etree.SubElement(os_elem, "boot", dev="cdrom")

        # Features
        features = etree.SubElement(domain, "features")
        etree.SubElement(features, "acpi")
        etree.SubElement(features, "apic")

        # Hyper-V enlightenments for Windows
        hyperv = etree.SubElement(features, "hyperv")
        etree.SubElement(hyperv, "relaxed", state="on")
        etree.SubElement(hyperv, "vapic", state="on")
        etree.SubElement(hyperv, "spinlocks", state="on", retries="8191")
        etree.SubElement(hyperv, "vpindex", state="on")
        etree.SubElement(hyperv, "runtime", state="on")
        etree.SubElement(hyperv, "synic", state="on")
        etree.SubElement(hyperv, "stimer", state="on")
        etree.SubElement(hyperv, "reset", state="on")
        etree.SubElement(hyperv, "vendor_id", state="on", value="WebOpsKVM")
        etree.SubElement(hyperv, "frequencies", state="on")

        # CPU configuration
        cpu = etree.SubElement(domain, "cpu", mode="host-passthrough", check="none")
        topology = etree.SubElement(
            cpu, "topology",
            sockets="1",
            dies="1",
            cores=str(vcpus),
            threads="1"
        )

        # Clock (Windows prefers RTC)
        clock = etree.SubElement(domain, "clock", offset="localtime")
        etree.SubElement(clock, "timer", name="rtc", tickpolicy="catchup")
        etree.SubElement(clock, "timer", name="pit", tickpolicy="delay")
        etree.SubElement(clock, "timer", name="hpet", present="no")
        etree.SubElement(clock, "timer", name="hypervclock", present="yes")

        # Power management
        etree.SubElement(domain, "on_poweroff").text = "destroy"
        etree.SubElement(domain, "on_reboot").text = "restart"
        etree.SubElement(domain, "on_crash").text = "destroy"

        # Devices
        devices = etree.SubElement(domain, "devices")

        # Disk (VirtIO)
        disk = etree.SubElement(devices, "disk", type="file", device="disk")
        etree.SubElement(disk, "driver", name="qemu", type="qcow2", cache="writeback")
        etree.SubElement(disk, "source", file=disk_path)
        etree.SubElement(disk, "target", dev="vda", bus="virtio")
        etree.SubElement(disk, "address", type="pci", domain="0x0000", bus="0x04", slot="0x00", function="0x0")

        # CD-ROM for Windows ISO (if provided)
        if iso_path:
            cdrom = etree.SubElement(devices, "disk", type="file", device="cdrom")
            etree.SubElement(cdrom, "driver", name="qemu", type="raw")
            etree.SubElement(cdrom, "source", file=iso_path)
            etree.SubElement(cdrom, "target", dev="sda", bus="sata")
            etree.SubElement(cdrom, "readonly")

        # CD-ROM for VirtIO drivers
        if Path(self.virtio_iso_path).exists():
            virtio_cdrom = etree.SubElement(devices, "disk", type="file", device="cdrom")
            etree.SubElement(virtio_cdrom, "driver", name="qemu", type="raw")
            etree.SubElement(virtio_cdrom, "source", file=self.virtio_iso_path)
            etree.SubElement(virtio_cdrom, "target", dev="sdb", bus="sata")
            etree.SubElement(virtio_cdrom, "readonly")

        # Network (VirtIO)
        interface = etree.SubElement(devices, "interface", type="network")
        etree.SubElement(interface, "mac", address=self._generate_mac())
        etree.SubElement(interface, "source", network=network_bridge)
        etree.SubElement(interface, "model", type="virtio")

        # Graphics (VNC)
        if vnc_port:
            graphics = etree.SubElement(
                devices, "graphics",
                type="vnc",
                port=str(vnc_port),
                listen="127.0.0.1"
            )
        else:
            graphics = etree.SubElement(
                devices, "graphics",
                type="vnc",
                port="-1",
                autoport="yes",
                listen="127.0.0.1"
            )

        # Video (more VRAM for Windows)
        video = etree.SubElement(devices, "video")
        etree.SubElement(
            video, "model",
            type="qxl",
            vram="65536",  # 64MB
            heads="1"
        )

        # Input devices
        etree.SubElement(devices, "input", type="tablet", bus="usb")
        etree.SubElement(devices, "input", type="mouse", bus="ps2")
        etree.SubElement(devices, "input", type="keyboard", bus="ps2")

        # Sound (optional, for desktop Windows)
        sound = etree.SubElement(devices, "sound", model="ich9")

        # Channel for QEMU guest agent
        channel = etree.SubElement(devices, "channel", type="unix")
        etree.SubElement(channel, "target", type="virtio", name="org.qemu.guest_agent.0")

        return etree.tostring(domain, encoding="unicode", pretty_print=True)

    def _generate_mac(self) -> str:
        """Generate MAC address."""
        import random
        mac = [0x52, 0x54, 0x00,
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(f'{octet:02x}' for octet in mac)

    def download_virtio_drivers(self) -> bool:
        """
        Download VirtIO drivers ISO for Windows.

        Required for Windows to use VirtIO storage/network.
        """
        import urllib.request

        drivers_dir = Path(self.virtio_iso_path).parent
        drivers_dir.mkdir(parents=True, exist_ok=True)

        if Path(self.virtio_iso_path).exists():
            logger.info("VirtIO drivers ISO already exists")
            return True

        try:
            logger.info(f"Downloading VirtIO drivers from {self.VIRTIO_WIN_ISO_URL}")
            urllib.request.urlretrieve(
                self.VIRTIO_WIN_ISO_URL,
                self.virtio_iso_path
            )
            logger.info(f"VirtIO drivers downloaded to {self.virtio_iso_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to download VirtIO drivers: {e}")
            return False

    def create_windows_autounattend(
        self,
        admin_password: str,
        computer_name: str,
        product_key: Optional[str] = None,
    ) -> str:
        """
        Generate Autounattend.xml for automated Windows installation.

        Args:
            admin_password: Administrator password
            computer_name: Computer name
            product_key: Windows product key (optional)

        Returns:
            Autounattend.xml content
        """
        # Simplified autounattend - full version would be much longer
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
    <settings pass="windowsPE">
        <component name="Microsoft-Windows-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <UserData>
                <AcceptEula>true</AcceptEula>
                {"<ProductKey><Key>" + product_key + "</Key></ProductKey>" if product_key else ""}
            </UserData>
        </component>
    </settings>
    <settings pass="specialize">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <ComputerName>{computer_name}</ComputerName>
        </component>
    </settings>
    <settings pass="oobeSystem">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <UserAccounts>
                <AdministratorPassword>
                    <Value>{admin_password}</Value>
                    <PlainText>true</PlainText>
                </AdministratorPassword>
            </UserAccounts>
            <OOBE>
                <HideEULAPage>true</HideEULAPage>
                <ProtectYourPC>1</ProtectYourPC>
                <NetworkLocation>Work</NetworkLocation>
            </OOBE>
        </component>
    </settings>
</unattend>
"""
        return xml
