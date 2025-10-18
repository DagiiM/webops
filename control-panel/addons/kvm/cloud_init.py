"""
Cloud-Init Configuration Generator

Generates cloud-init configuration for VM initial setup.
Handles SSH keys, passwords, networking, and package installation.
"""

import yaml
import tempfile
import subprocess
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CloudInitGenerator:
    """
    Generates cloud-init configuration and ISO images.
    """

    def __init__(self):
        pass

    def generate_user_data(
        self,
        hostname: str,
        ssh_public_keys: List[str],
        root_password: Optional[str] = None,
        packages: Optional[List[str]] = None,
        runcmd: Optional[List[str]] = None,
        timezone: str = "UTC",
    ) -> str:
        """
        Generate cloud-init user-data YAML.

        Args:
            hostname: VM hostname
            ssh_public_keys: List of SSH public keys
            root_password: Root password (plain text, will be hashed by cloud-init)
            packages: List of packages to install
            runcmd: List of commands to run on first boot
            timezone: System timezone

        Returns:
            YAML string for user-data
        """
        user_data = {
            '#cloud-config': None,
            'hostname': hostname,
            'fqdn': f"{hostname}.localdomain",
            'manage_etc_hosts': True,
            'timezone': timezone,
        }

        # SSH configuration
        user_data['ssh_pwauth'] = True if root_password else False
        user_data['disable_root'] = False

        if ssh_public_keys:
            user_data['ssh_authorized_keys'] = ssh_public_keys

        # User configuration
        users = [
            {
                'name': 'root',
                'lock_passwd': False if root_password else True,
            }
        ]

        if root_password:
            users[0]['plain_text_passwd'] = root_password
            users[0]['chpasswd'] = {'expire': False}

        user_data['users'] = users

        # Package management
        if packages:
            user_data['packages'] = packages
            user_data['package_update'] = True
            user_data['package_upgrade'] = True

        # Commands to run
        if runcmd:
            user_data['runcmd'] = runcmd

        # Final message
        user_data['final_message'] = f"VM {hostname} is ready!"

        # Convert to YAML with proper header
        yaml_str = yaml.dump(user_data, default_flow_style=False, sort_keys=False)
        return f"#cloud-config\n{yaml_str}"

    def generate_meta_data(
        self,
        instance_id: str,
        hostname: str,
        local_ipv4: Optional[str] = None,
    ) -> str:
        """
        Generate cloud-init meta-data YAML.

        Args:
            instance_id: Unique instance identifier (e.g., VM UUID)
            hostname: VM hostname
            local_ipv4: Local IPv4 address (optional)

        Returns:
            YAML string for meta-data
        """
        meta_data = {
            'instance-id': instance_id,
            'local-hostname': hostname,
        }

        if local_ipv4:
            meta_data['local-ipv4'] = local_ipv4

        return yaml.dump(meta_data, default_flow_style=False)

    def generate_network_config(
        self,
        mac_address: str,
        ip_address: Optional[str] = None,
        netmask: str = "255.255.255.0",
        gateway: Optional[str] = None,
        nameservers: Optional[List[str]] = None,
    ) -> str:
        """
        Generate cloud-init network configuration.

        Args:
            mac_address: VM MAC address
            ip_address: Static IP (if None, use DHCP)
            netmask: Network mask
            gateway: Default gateway
            nameservers: DNS servers

        Returns:
            YAML string for network-config
        """
        if nameservers is None:
            nameservers = ['8.8.8.8', '8.8.4.4']

        if ip_address:
            # Static IP configuration
            network_config = {
                'version': 2,
                'ethernets': {
                    'eth0': {
                        'match': {'macaddress': mac_address},
                        'addresses': [f"{ip_address}/{self._netmask_to_cidr(netmask)}"],
                        'nameservers': {'addresses': nameservers},
                    }
                }
            }
            if gateway:
                network_config['ethernets']['eth0']['routes'] = [
                    {'to': 'default', 'via': gateway}
                ]
        else:
            # DHCP configuration
            network_config = {
                'version': 2,
                'ethernets': {
                    'eth0': {
                        'match': {'macaddress': mac_address},
                        'dhcp4': True,
                        'dhcp6': False,
                    }
                }
            }

        return yaml.dump(network_config, default_flow_style=False)

    def _netmask_to_cidr(self, netmask: str) -> int:
        """Convert netmask to CIDR notation."""
        return sum([bin(int(x)).count('1') for x in netmask.split('.')])

    def create_cloud_init_iso(
        self,
        output_path: str,
        user_data: str,
        meta_data: str,
        network_config: Optional[str] = None,
    ) -> bool:
        """
        Create a cloud-init ISO image.

        Args:
            output_path: Path where ISO will be created
            user_data: user-data content
            meta_data: meta-data content
            network_config: network-config content (optional)

        Returns:
            True if successful
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Write cloud-init files
                (tmpdir_path / 'user-data').write_text(user_data)
                (tmpdir_path / 'meta-data').write_text(meta_data)

                if network_config:
                    (tmpdir_path / 'network-config').write_text(network_config)

                # Create ISO using genisoimage or mkisofs
                cmd = [
                    'genisoimage',
                    '-output', output_path,
                    '-volid', 'cidata',
                    '-joliet',
                    '-rock',
                    str(tmpdir_path / 'user-data'),
                    str(tmpdir_path / 'meta-data'),
                ]

                if network_config:
                    cmd.append(str(tmpdir_path / 'network-config'))

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                logger.info(f"Created cloud-init ISO: {output_path}")
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create cloud-init ISO: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error creating cloud-init ISO: {e}")
            return False

    def inject_into_disk(
        self,
        disk_path: str,
        user_data: str,
        meta_data: str,
        network_config: Optional[str] = None,
    ) -> bool:
        """
        Inject cloud-init data directly into disk image.

        Uses virt-customize to modify the disk image.

        Args:
            disk_path: Path to qcow2 disk image
            user_data: user-data content
            meta_data: meta-data content
            network_config: network-config content (optional)

        Returns:
            True if successful
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Write cloud-init files
                user_data_file = tmpdir_path / 'user-data'
                meta_data_file = tmpdir_path / 'meta-data'

                user_data_file.write_text(user_data)
                meta_data_file.write_text(meta_data)

                # Build virt-customize command
                cmd = [
                    'virt-customize',
                    '-a', disk_path,
                    '--mkdir', '/var/lib/cloud/seed/nocloud',
                    '--upload', f"{user_data_file}:/var/lib/cloud/seed/nocloud/user-data",
                    '--upload', f"{meta_data_file}:/var/lib/cloud/seed/nocloud/meta-data",
                ]

                if network_config:
                    network_config_file = tmpdir_path / 'network-config'
                    network_config_file.write_text(network_config)
                    cmd.extend([
                        '--upload',
                        f"{network_config_file}:/var/lib/cloud/seed/nocloud/network-config"
                    ])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                logger.info(f"Injected cloud-init data into {disk_path}")
                return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to inject cloud-init data: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error injecting cloud-init data: {e}")
            return False

    def generate_default_config(
        self,
        vm_name: str,
        vm_uuid: str,
        ssh_keys: List[str],
        root_password: Optional[str] = None,
        mac_address: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Generate a complete default cloud-init configuration.

        Args:
            vm_name: VM name/hostname
            vm_uuid: VM UUID (for instance-id)
            ssh_keys: List of SSH public keys
            root_password: Root password (optional)
            mac_address: MAC address for networking (optional)

        Returns:
            Dictionary with 'user_data', 'meta_data', 'network_config'
        """
        # Default packages to install
        default_packages = [
            'qemu-guest-agent',
            'curl',
            'wget',
            'vim',
            'htop',
            'net-tools',
        ]

        # Default commands
        default_runcmd = [
            # Start qemu-guest-agent
            'systemctl enable qemu-guest-agent',
            'systemctl start qemu-guest-agent',
            # Update system
            'apt-get update || yum update -y',
        ]

        user_data = self.generate_user_data(
            hostname=vm_name,
            ssh_public_keys=ssh_keys,
            root_password=root_password,
            packages=default_packages,
            runcmd=default_runcmd,
        )

        meta_data = self.generate_meta_data(
            instance_id=vm_uuid,
            hostname=vm_name,
        )

        network_config = None
        if mac_address:
            network_config = self.generate_network_config(
                mac_address=mac_address,
            )

        return {
            'user_data': user_data,
            'meta_data': meta_data,
            'network_config': network_config,
        }
