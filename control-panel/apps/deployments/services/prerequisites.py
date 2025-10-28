"""
System prerequisites installer for LLM deployments.

This module handles automatic installation of system-level dependencies
required for building and running vLLM deployments.
"""

import subprocess
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PrerequisitePackage:
    """Represents a system package prerequisite."""
    name: str
    description: str
    check_paths: List[str]  # Paths to check if package is installed
    apt_package: str  # APT package name


class SystemPrerequisitesInstaller:
    """
    Service for checking and installing system prerequisites.

    This service can automatically install required system packages
    when properly configured with sudo access.
    """

    # Define all required packages for vLLM CPU builds
    REQUIRED_PACKAGES = [
        PrerequisitePackage(
            name="build-essential",
            description="GNU C/C++ compiler and build tools",
            check_paths=["/usr/bin/gcc", "/usr/bin/g++", "/usr/bin/make"],
            apt_package="build-essential"
        ),
        PrerequisitePackage(
            name="cmake",
            description="CMake build system",
            check_paths=["/usr/bin/cmake"],
            apt_package="cmake"
        ),
        PrerequisitePackage(
            name="ninja-build",
            description="Ninja build tool (faster than make)",
            check_paths=["/usr/bin/ninja"],
            apt_package="ninja-build"
        ),
        PrerequisitePackage(
            name="python3-dev",
            description="Python development headers",
            check_paths=[],  # Checked separately via sysconfig
            apt_package="python3-dev"
        ),
        PrerequisitePackage(
            name="libnuma-dev",
            description="NUMA (Non-Uniform Memory Access) development library",
            check_paths=["/usr/include/numa.h"],
            apt_package="libnuma-dev"
        ),
        PrerequisitePackage(
            name="libgomp1",
            description="GNU OpenMP runtime library",
            check_paths=["/usr/lib/x86_64-linux-gnu/libgomp.so.1"],
            apt_package="libgomp1"
        ),
    ]

    def __init__(self):
        """Initialize the prerequisites installer."""
        self.sudo_available = self._check_sudo_access()

    def _check_sudo_access(self) -> bool:
        """
        Check if sudo access is available without password.

        Returns:
            True if passwordless sudo is available
        """
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Could not check sudo access: {e}")
            return False

    def check_package(self, package: PrerequisitePackage) -> bool:
        """
        Check if a package is installed.

        Args:
            package: Package to check

        Returns:
            True if package is installed
        """
        # Special handling for python3-dev
        if package.name == "python3-dev":
            return self._check_python_dev_headers()

        # Check all paths for the package
        for path in package.check_paths:
            if not Path(path).exists():
                return False

        return True

    def _check_python_dev_headers(self) -> bool:
        """
        Check if Python development headers are installed.

        Returns:
            True if headers are present
        """
        try:
            import sysconfig
            include_dir = sysconfig.get_path('include')
            return include_dir and Path(include_dir).exists()
        except Exception as e:
            logger.warning(f"Could not check Python headers: {e}")
            return False

    def check_all_prerequisites(self) -> Tuple[bool, List[PrerequisitePackage]]:
        """
        Check all required prerequisites.

        Returns:
            Tuple of (all_present, list_of_missing_packages)
        """
        missing = []

        for package in self.REQUIRED_PACKAGES:
            if not self.check_package(package):
                missing.append(package)
                logger.info(f"Missing prerequisite: {package.name}")

        return (len(missing) == 0, missing)

    def install_package(self, package: PrerequisitePackage) -> Tuple[bool, str]:
        """
        Install a single package using apt-get.

        Args:
            package: Package to install

        Returns:
            Tuple of (success, message)
        """
        if not self.sudo_available:
            return False, "Sudo access not available. Please install manually or configure passwordless sudo."

        try:
            logger.info(f"Installing {package.name}...")

            # Run apt-get install with sudo
            result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", package.apt_package],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode == 0:
                logger.info(f"Successfully installed {package.name}")
                return True, f"Successfully installed {package.name}"
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"Failed to install {package.name}: {error_msg}")
                return False, f"Failed to install {package.name}: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, f"Installation of {package.name} timed out"
        except Exception as e:
            return False, f"Error installing {package.name}: {str(e)}"

    def install_all_prerequisites(self, missing_packages: Optional[List[PrerequisitePackage]] = None) -> Tuple[bool, List[str]]:
        """
        Install all missing prerequisites.

        Args:
            missing_packages: List of missing packages (if None, will check first)

        Returns:
            Tuple of (all_successful, list_of_error_messages)
        """
        if missing_packages is None:
            _, missing_packages = self.check_all_prerequisites()

        if not missing_packages:
            return True, []

        if not self.sudo_available:
            return False, ["Sudo access not available. Please install packages manually."]

        errors = []

        # Update apt cache first
        logger.info("Updating apt package cache...")
        try:
            result = subprocess.run(
                ["sudo", "apt-get", "update"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                logger.warning(f"apt-get update had warnings: {result.stderr}")
        except Exception as e:
            logger.warning(f"Could not update apt cache: {e}")

        # Install each missing package
        for package in missing_packages:
            success, message = self.install_package(package)
            if not success:
                errors.append(message)

        return (len(errors) == 0, errors)

    def get_installation_instructions(self, missing_packages: List[PrerequisitePackage]) -> str:
        """
        Generate manual installation instructions for missing packages.

        Args:
            missing_packages: List of missing packages

        Returns:
            Formatted installation instructions
        """
        if not missing_packages:
            return "All prerequisites are installed."

        package_names = [pkg.apt_package for pkg in missing_packages]

        instructions = [
            "Missing system prerequisites. Please install them using:",
            "",
            "sudo apt-get update && sudo apt-get install -y " + " ".join(package_names),
            "",
            "Packages needed:",
        ]

        for pkg in missing_packages:
            instructions.append(f"  • {pkg.name}: {pkg.description}")

        instructions.extend([
            "",
            "After installing, retry the deployment.",
        ])

        return "\n".join(instructions)

    def get_sudo_setup_instructions(self) -> str:
        """
        Get instructions for setting up passwordless sudo.

        Returns:
            Setup instructions
        """
        return """
To enable automatic prerequisite installation, configure passwordless sudo:

1. Edit sudoers file:
   sudo visudo

2. Add this line at the end (replace 'username' with your user):
   username ALL=(ALL) NOPASSWD: /usr/bin/apt-get update, /usr/bin/apt-get install

3. Save and exit

This allows WebOps to install required packages automatically.
Alternatively, install all prerequisites manually:

sudo apt-get update && sudo apt-get install -y \\
  build-essential cmake ninja-build python3-dev libnuma-dev libgomp1
""".strip()
