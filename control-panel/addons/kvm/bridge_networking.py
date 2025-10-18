"""
Bridge Networking Support

Provides bridge networking as an alternative to NAT.
Allows VMs to get public IPs directly.
"""

import logging
import subprocess
from typing import Optional, List
import ipaddress

logger = logging.getLogger(__name__)


class BridgeNetworkManager:
    """
    Manages bridge networking for VMs.
    """

    def __init__(self, bridge_name: str = 'br0'):
        self.bridge_name = bridge_name

    def create_bridge(
        self,
        physical_interface: str,
        bridge_ip: Optional[str] = None,
        netmask: str = '255.255.255.0',
    ) -> bool:
        """
        Create a Linux bridge and attach physical interface.

        Args:
            physical_interface: Physical NIC (e.g., 'eth0')
            bridge_ip: Bridge IP address (optional)
            netmask: Network mask

        Returns:
            True if successful
        """
        try:
            logger.info(f"Creating bridge {self.bridge_name} on {physical_interface}")

            # Create bridge
            subprocess.run(
                ['sudo', 'ip', 'link', 'add', self.bridge_name, 'type', 'bridge'],
                check=True,
                capture_output=True,
            )

            # Attach physical interface to bridge
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', physical_interface, 'master', self.bridge_name],
                check=True,
                capture_output=True,
            )

            # Bring bridge up
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', self.bridge_name, 'up'],
                check=True,
                capture_output=True,
            )

            # Bring physical interface up
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', physical_interface, 'up'],
                check=True,
                capture_output=True,
            )

            # Assign IP to bridge if provided
            if bridge_ip:
                subprocess.run(
                    ['sudo', 'ip', 'addr', 'add', f'{bridge_ip}/{self._netmask_to_cidr(netmask)}', 'dev', self.bridge_name],
                    check=True,
                    capture_output=True,
                )

            logger.info(f"Bridge {self.bridge_name} created successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create bridge: {e.stderr}")
            return False

    def delete_bridge(self) -> bool:
        """Delete the bridge."""
        try:
            # Bring bridge down
            subprocess.run(
                ['sudo', 'ip', 'link', 'set', self.bridge_name, 'down'],
                check=True,
                capture_output=True,
            )

            # Delete bridge
            subprocess.run(
                ['sudo', 'ip', 'link', 'delete', self.bridge_name, 'type', 'bridge'],
                check=True,
                capture_output=True,
            )

            logger.info(f"Bridge {self.bridge_name} deleted")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete bridge: {e.stderr}")
            return False

    def bridge_exists(self) -> bool:
        """Check if bridge exists."""
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', self.bridge_name],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_bridge_info(self) -> dict:
        """Get bridge information."""
        try:
            result = subprocess.run(
                ['ip', 'addr', 'show', self.bridge_name],
                capture_output=True,
                text=True,
                check=True,
            )

            info = {
                'name': self.bridge_name,
                'exists': True,
                'output': result.stdout,
            }

            # Parse IP addresses
            import re
            ip_pattern = r'inet (\d+\.\d+\.\d+\.\d+/\d+)'
            matches = re.findall(ip_pattern, result.stdout)
            info['ip_addresses'] = matches

            return info

        except subprocess.CalledProcessError:
            return {'name': self.bridge_name, 'exists': False}

    def create_libvirt_bridge_network(
        self,
        network_name: str = 'webops-bridge',
        subnet: Optional[str] = None,
    ) -> bool:
        """
        Create a libvirt bridge network definition.

        Args:
            network_name: Name of the network
            subnet: Subnet for DHCP (e.g., '192.168.1.0/24')

        Returns:
            True if successful
        """
        if subnet:
            # Bridge with DHCP
            network = ipaddress.IPv4Network(subnet)
            gateway = str(network.network_address + 1)
            dhcp_start = str(network.network_address + 10)
            dhcp_end = str(network.network_address + 254)

            xml = f"""
<network>
  <name>{network_name}</name>
  <forward mode='bridge'/>
  <bridge name='{self.bridge_name}'/>
  <ip address='{gateway}' netmask='{network.netmask}'>
    <dhcp>
      <range start='{dhcp_start}' end='{dhcp_end}'/>
    </dhcp>
  </ip>
</network>
"""
        else:
            # Bridge without DHCP (VMs get IPs from external DHCP)
            xml = f"""
<network>
  <name>{network_name}</name>
  <forward mode='bridge'/>
  <bridge name='{self.bridge_name}'/>
</network>
"""

        try:
            import tempfile
            import os

            # Write XML to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                f.write(xml)
                xml_file = f.name

            try:
                # Define network
                subprocess.run(
                    ['sudo', 'virsh', 'net-define', xml_file],
                    check=True,
                    capture_output=True,
                )

                # Start network
                subprocess.run(
                    ['sudo', 'virsh', 'net-start', network_name],
                    check=True,
                    capture_output=True,
                )

                # Autostart network
                subprocess.run(
                    ['sudo', 'virsh', 'net-autostart', network_name],
                    check=True,
                    capture_output=True,
                )

                logger.info(f"Created libvirt bridge network: {network_name}")
                return True

            finally:
                os.unlink(xml_file)

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create libvirt network: {e.stderr}")
            return False

    def assign_static_ip(
        self,
        mac_address: str,
        ip_address: str,
        network_name: str = 'webops-bridge',
    ) -> bool:
        """
        Assign a static IP to a MAC address in libvirt DHCP.

        Args:
            mac_address: VM MAC address
            ip_address: Static IP to assign
            network_name: Libvirt network name

        Returns:
            True if successful
        """
        try:
            subprocess.run(
                [
                    'sudo', 'virsh', 'net-update', network_name,
                    'add', 'ip-dhcp-host',
                    f"<host mac='{mac_address}' ip='{ip_address}'/>",
                    '--live', '--config',
                ],
                check=True,
                capture_output=True,
            )

            logger.info(f"Assigned static IP {ip_address} to MAC {mac_address}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to assign static IP: {e.stderr}")
            return False

    def _netmask_to_cidr(self, netmask: str) -> int:
        """Convert netmask to CIDR notation."""
        return sum([bin(int(x)).count('1') for x in netmask.split('.')])

    def configure_persistent_bridge(
        self,
        physical_interface: str,
        bridge_ip: str,
        netmask: str,
        gateway: str,
    ) -> bool:
        """
        Configure persistent bridge using netplan (Ubuntu) or ifcfg (CentOS/RHEL).

        Args:
            physical_interface: Physical NIC
            bridge_ip: Bridge IP address
            netmask: Network mask
            gateway: Default gateway

        Returns:
            True if successful
        """
        # Check OS type
        import platform
        import os

        if os.path.exists('/etc/netplan'):
            return self._configure_netplan_bridge(
                physical_interface, bridge_ip, netmask, gateway
            )
        elif os.path.exists('/etc/sysconfig/network-scripts'):
            return self._configure_ifcfg_bridge(
                physical_interface, bridge_ip, netmask, gateway
            )
        else:
            logger.warning("Unknown network configuration system")
            return False

    def _configure_netplan_bridge(
        self,
        physical_interface: str,
        bridge_ip: str,
        netmask: str,
        gateway: str,
    ) -> bool:
        """Configure bridge using netplan (Ubuntu)."""
        cidr = self._netmask_to_cidr(netmask)

        netplan_config = f"""
network:
  version: 2
  ethernets:
    {physical_interface}:
      dhcp4: no
  bridges:
    {self.bridge_name}:
      interfaces: [{physical_interface}]
      dhcp4: no
      addresses:
        - {bridge_ip}/{cidr}
      routes:
        - to: default
          via: {gateway}
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
"""

        try:
            config_file = f'/etc/netplan/99-{self.bridge_name}.yaml'

            with open(config_file, 'w') as f:
                f.write(netplan_config)

            # Apply configuration
            subprocess.run(['sudo', 'netplan', 'apply'], check=True)

            logger.info(f"Netplan bridge configuration applied")
            return True

        except Exception as e:
            logger.error(f"Failed to configure netplan bridge: {e}")
            return False

    def _configure_ifcfg_bridge(
        self,
        physical_interface: str,
        bridge_ip: str,
        netmask: str,
        gateway: str,
    ) -> bool:
        """Configure bridge using ifcfg (CentOS/RHEL)."""
        # TODO: Implement ifcfg configuration
        logger.warning("ifcfg bridge configuration not yet implemented")
        return False
