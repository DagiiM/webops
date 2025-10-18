"""
Network Manager

Handles NAT networking, port allocation, and iptables configuration.
"""

import logging
import subprocess
from typing import Optional, Set
from django.core.cache import cache

logger = logging.getLogger(__name__)


class NetworkManager:
    """
    Manages networking for VMs (NAT, port forwarding, DHCP).
    """

    # Port ranges (from addon settings)
    SSH_PORT_MIN = 2200
    SSH_PORT_MAX = 2299
    VNC_PORT_MIN = 5900
    VNC_PORT_MAX = 5999

    # Cache keys for allocated ports
    SSH_PORTS_CACHE_KEY = 'kvm:allocated_ssh_ports'
    VNC_PORTS_CACHE_KEY = 'kvm:allocated_vnc_ports'

    def __init__(self):
        pass

    def allocate_ssh_port(self) -> Optional[int]:
        """
        Allocate an available SSH port for NAT forwarding.

        Returns:
            Port number or None if all ports are allocated
        """
        return self._allocate_port(
            self.SSH_PORT_MIN,
            self.SSH_PORT_MAX,
            self.SSH_PORTS_CACHE_KEY,
        )

    def allocate_vnc_port(self) -> Optional[int]:
        """
        Allocate an available VNC port.

        Returns:
            Port number or None if all ports are allocated
        """
        return self._allocate_port(
            self.VNC_PORT_MIN,
            self.VNC_PORT_MAX,
            self.VNC_PORTS_CACHE_KEY,
        )

    def free_ssh_port(self, port: int):
        """Free an SSH port."""
        self._free_port(port, self.SSH_PORTS_CACHE_KEY)

    def free_vnc_port(self, port: int):
        """Free a VNC port."""
        self._free_port(port, self.VNC_PORTS_CACHE_KEY)

    def _allocate_port(
        self,
        min_port: int,
        max_port: int,
        cache_key: str,
    ) -> Optional[int]:
        """
        Generic port allocation logic.

        Uses cache to track allocated ports and database for persistence.
        """
        from .models import VMDeployment

        # Get currently allocated ports from database
        if 'ssh' in cache_key:
            db_ports = set(
                VMDeployment.objects.filter(
                    ssh_port__isnull=False
                ).values_list('ssh_port', flat=True)
            )
        else:
            db_ports = set(
                VMDeployment.objects.filter(
                    vnc_port__isnull=False
                ).values_list('vnc_port', flat=True)
            )

        # Find first available port
        for port in range(min_port, max_port + 1):
            if port not in db_ports:
                logger.info(f"Allocated port: {port}")
                return port

        logger.error(f"No available ports in range {min_port}-{max_port}")
        return None

    def _free_port(self, port: int, cache_key: str):
        """Free a port (for cleanup)."""
        logger.info(f"Freed port: {port}")

    def setup_nat_forwarding(
        self,
        host_ip: str,
        host_port: int,
        guest_ip: str,
        guest_port: int,
        protocol: str = 'tcp',
    ) -> bool:
        """
        Setup iptables NAT port forwarding from host to guest VM.

        Args:
            host_ip: Host IP address (can be 0.0.0.0 for all interfaces)
            host_port: Host port to forward from
            guest_ip: Guest VM IP address
            guest_port: Guest VM port to forward to
            protocol: Protocol (tcp or udp)

        Returns:
            True if successful
        """
        try:
            # PREROUTING rule (for external traffic)
            prerouting_cmd = [
                'sudo', 'iptables', '-t', 'nat', '-A', 'PREROUTING',
                '-p', protocol,
                '--dport', str(host_port),
                '-j', 'DNAT',
                '--to-destination', f"{guest_ip}:{guest_port}",
            ]

            # POSTROUTING rule (for response traffic)
            postrouting_cmd = [
                'sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING',
                '-p', protocol,
                '-d', guest_ip,
                '--dport', str(guest_port),
                '-j', 'MASQUERADE',
            ]

            # FORWARD rule (allow forwarding)
            forward_cmd = [
                'sudo', 'iptables', '-A', 'FORWARD',
                '-p', protocol,
                '-d', guest_ip,
                '--dport', str(guest_port),
                '-j', 'ACCEPT',
            ]

            # Execute rules
            subprocess.run(prerouting_cmd, check=True, capture_output=True)
            subprocess.run(postrouting_cmd, check=True, capture_output=True)
            subprocess.run(forward_cmd, check=True, capture_output=True)

            logger.info(
                f"Setup NAT forwarding: {host_ip}:{host_port} -> {guest_ip}:{guest_port}"
            )
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to setup NAT forwarding: {e.stderr}")
            return False

    def remove_nat_forwarding(
        self,
        host_ip: str,
        host_port: int,
    ) -> bool:
        """
        Remove iptables NAT port forwarding rules.

        Args:
            host_ip: Host IP address
            host_port: Host port

        Returns:
            True if successful
        """
        try:
            # List all rules and find matching ones
            list_cmd = ['sudo', 'iptables', '-t', 'nat', '-L', 'PREROUTING', '--line-numbers', '-n']
            result = subprocess.run(list_cmd, capture_output=True, text=True, check=True)

            # Parse output to find rule numbers to delete
            # This is a simplified approach - in production, you'd want more robust parsing
            lines = result.stdout.split('\n')
            for line in lines:
                if f"dpt:{host_port}" in line:
                    # Extract rule number and delete
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        rule_num = parts[0]
                        delete_cmd = [
                            'sudo', 'iptables', '-t', 'nat', '-D', 'PREROUTING', rule_num
                        ]
                        subprocess.run(delete_cmd, check=True, capture_output=True)
                        logger.info(f"Removed NAT forwarding for port {host_port}")

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to remove NAT forwarding: {e.stderr}")
            return False

    def create_nat_network(self, network_name: str = 'webops-nat') -> bool:
        """
        Create a libvirt NAT network for VMs.

        Args:
            network_name: Name of the network

        Returns:
            True if successful
        """
        network_xml = f"""
<network>
  <name>{network_name}</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <bridge name='virbr-webops' stp='on' delay='0'/>
  <ip address='192.168.100.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.100.10' end='192.168.100.254'/>
    </dhcp>
  </ip>
</network>
"""

        try:
            import tempfile
            from .libvirt_manager import LibvirtManager

            # Write XML to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                f.write(network_xml)
                xml_file = f.name

            # Define network using virsh
            cmd = ['sudo', 'virsh', 'net-define', xml_file]
            subprocess.run(cmd, check=True, capture_output=True)

            # Start network
            cmd = ['sudo', 'virsh', 'net-start', network_name]
            subprocess.run(cmd, check=True, capture_output=True)

            # Autostart network
            cmd = ['sudo', 'virsh', 'net-autostart', network_name]
            subprocess.run(cmd, check=True, capture_output=True)

            logger.info(f"Created NAT network: {network_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create NAT network: {e.stderr}")
            return False
        finally:
            import os
            if 'xml_file' in locals():
                try:
                    os.unlink(xml_file)
                except:
                    pass

    def check_network_exists(self, network_name: str = 'webops-nat') -> bool:
        """Check if NAT network exists."""
        try:
            cmd = ['sudo', 'virsh', 'net-list', '--all']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return network_name in result.stdout
        except subprocess.CalledProcessError:
            return False
