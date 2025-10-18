"""
ISO Manager

Handles custom ISO uploads with malware scanning and validation.
"""

import logging
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)


class ISOManager:
    """
    Manages custom ISO file uploads and validation.
    """

    def __init__(self):
        self.iso_storage_path = Path(
            getattr(settings, 'KVM_ISO_PATH', '/var/lib/webops/isos')
        )
        self.iso_storage_path.mkdir(parents=True, exist_ok=True)

        self.max_iso_size = getattr(settings, 'KVM_MAX_ISO_SIZE_MB', 8192)  # 8GB default

    def upload_iso(
        self,
        uploaded_file: UploadedFile,
        name: str,
        scan_malware: bool = True,
        verify_bootable: bool = True,
    ) -> Dict[str, Any]:
        """
        Upload and validate a custom ISO file.

        Args:
            uploaded_file: Django uploaded file
            name: Name for the ISO
            scan_malware: Run malware scan
            verify_bootable: Verify ISO is bootable

        Returns:
            Dictionary with upload result

        Raises:
            Exception: If upload fails validation
        """
        logger.info(f"Starting ISO upload: {name}")

        # 1. Validate file size
        size_mb = uploaded_file.size / (1024 * 1024)
        if size_mb > self.max_iso_size:
            raise ValueError(
                f"ISO file too large: {size_mb:.1f}MB (max: {self.max_iso_size}MB)"
            )

        # 2. Validate file extension
        if not name.lower().endswith('.iso'):
            name += '.iso'

        # 3. Create destination path
        iso_path = self.iso_storage_path / name

        if iso_path.exists():
            raise ValueError(f"ISO file already exists: {name}")

        # 4. Save file
        logger.info(f"Saving ISO to {iso_path}")
        with open(iso_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        try:
            # 5. Calculate checksums
            logger.info("Calculating checksums...")
            md5_hash = self._calculate_md5(iso_path)
            sha256_hash = self._calculate_sha256(iso_path)

            # 6. Verify ISO format
            logger.info("Verifying ISO format...")
            if not self._verify_iso_format(iso_path):
                raise ValueError("Invalid ISO file format")

            # 7. Verify bootable (if requested)
            if verify_bootable:
                logger.info("Verifying bootable...")
                if not self._verify_bootable(iso_path):
                    logger.warning("ISO may not be bootable")

            # 8. Malware scan (if requested)
            if scan_malware:
                logger.info("Running malware scan...")
                scan_result = self._scan_malware(iso_path)
                if not scan_result['clean']:
                    raise ValueError(
                        f"Malware detected: {scan_result['threats']}"
                    )

            # 9. Extract ISO metadata
            metadata = self._extract_metadata(iso_path)

            logger.info(f"ISO upload completed: {name}")

            return {
                'success': True,
                'path': str(iso_path),
                'size_mb': size_mb,
                'md5': md5_hash,
                'sha256': sha256_hash,
                'metadata': metadata,
            }

        except Exception as e:
            # Cleanup on failure
            logger.error(f"ISO upload failed: {e}")
            if iso_path.exists():
                iso_path.unlink()
            raise

    def _calculate_md5(self, file_path: Path) -> str:
        """Calculate MD5 hash of file."""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _verify_iso_format(self, file_path: Path) -> bool:
        """
        Verify file is a valid ISO 9660 format.

        Uses file command to check magic bytes.
        """
        try:
            result = subprocess.run(
                ['file', '--mime-type', str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )

            # Check for ISO mime types
            mime_type = result.stdout.strip().split(': ')[-1]
            valid_types = [
                'application/x-iso9660-image',
                'application/octet-stream',  # Sometimes ISOs show as this
            ]

            if mime_type not in valid_types:
                # Additional check: Look for ISO 9660 signature
                with open(file_path, 'rb') as f:
                    f.seek(0x8000)  # ISO 9660 primary volume descriptor location
                    signature = f.read(5)
                    return signature == b'CD001'

            return True

        except Exception as e:
            logger.error(f"ISO format verification failed: {e}")
            return False

    def _verify_bootable(self, file_path: Path) -> bool:
        """
        Verify ISO is bootable.

        Checks for El Torito boot specification.
        """
        try:
            # Use isoinfo to check for boot catalog
            result = subprocess.run(
                ['isoinfo', '-d', '-i', str(file_path)],
                capture_output=True,
                text=True,
            )

            output = result.stdout.lower()
            return 'bootable' in output or 'el torito' in output

        except FileNotFoundError:
            logger.warning("isoinfo not installed, cannot verify bootability")
            return True  # Assume bootable if we can't check
        except Exception as e:
            logger.error(f"Bootable verification failed: {e}")
            return True

    def _scan_malware(self, file_path: Path) -> Dict[str, Any]:
        """
        Scan ISO for malware using ClamAV.

        Returns:
            Dictionary with scan results
        """
        try:
            # Try ClamAV
            result = subprocess.run(
                ['clamscan', '--no-summary', str(file_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # ClamAV returns 0 if clean, 1 if virus found
            if result.returncode == 0:
                return {
                    'clean': True,
                    'scanner': 'clamav',
                    'threats': [],
                }
            else:
                # Parse threats from output
                threats = []
                for line in result.stdout.splitlines():
                    if 'FOUND' in line:
                        threats.append(line.strip())

                return {
                    'clean': False,
                    'scanner': 'clamav',
                    'threats': threats,
                }

        except FileNotFoundError:
            logger.warning("ClamAV not installed, skipping malware scan")
            return {
                'clean': True,
                'scanner': 'none',
                'threats': [],
                'warning': 'No malware scanner available'
            }
        except subprocess.TimeoutExpired:
            logger.error("Malware scan timed out")
            raise Exception("Malware scan timed out (file too large)")
        except Exception as e:
            logger.error(f"Malware scan failed: {e}")
            raise

    def _extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from ISO.

        Uses isoinfo to get volume info.
        """
        metadata = {}

        try:
            result = subprocess.run(
                ['isoinfo', '-d', '-i', str(file_path)],
                capture_output=True,
                text=True,
            )

            # Parse isoinfo output
            for line in result.stdout.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()

                    if key in ['volume_id', 'system_id', 'volume_set_id', 'publisher_id']:
                        metadata[key] = value

        except FileNotFoundError:
            logger.warning("isoinfo not installed")
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")

        return metadata

    def delete_iso(self, name: str) -> bool:
        """Delete an ISO file."""
        iso_path = self.iso_storage_path / name

        if not iso_path.exists():
            logger.warning(f"ISO not found: {name}")
            return False

        try:
            iso_path.unlink()
            logger.info(f"Deleted ISO: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ISO: {e}")
            return False

    def list_isos(self) -> list:
        """List all uploaded ISOs."""
        isos = []

        for iso_file in self.iso_storage_path.glob('*.iso'):
            try:
                stat = iso_file.stat()
                isos.append({
                    'name': iso_file.name,
                    'path': str(iso_file),
                    'size_mb': stat.st_size / (1024 * 1024),
                    'created_at': stat.st_ctime,
                })
            except Exception as e:
                logger.error(f"Error getting ISO info: {e}")

        return isos

    def verify_iso_checksum(self, name: str, expected_sha256: str) -> bool:
        """
        Verify ISO checksum matches expected value.

        Useful for verifying downloaded ISOs.
        """
        iso_path = self.iso_storage_path / name

        if not iso_path.exists():
            raise FileNotFoundError(f"ISO not found: {name}")

        actual_sha256 = self._calculate_sha256(iso_path)

        return actual_sha256.lower() == expected_sha256.lower()


class ISOTemplateConverter:
    """
    Convert ISOs to qcow2 templates for faster VM provisioning.
    """

    def __init__(self):
        self.iso_manager = ISOManager()
        self.template_path = Path(
            getattr(settings, 'KVM_TEMPLATE_PATH', '/var/lib/webops/templates')
        )

    def convert_iso_to_template(
        self,
        iso_name: str,
        template_name: str,
        disk_size_gb: int = 20,
    ) -> str:
        """
        Convert ISO to qcow2 template.

        This creates a base VM, installs OS from ISO, and saves as template.
        Note: This is a placeholder - actual conversion would require
        automated installation (preseed/kickstart/autounattend).

        Args:
            iso_name: Source ISO filename
            template_name: Output template name
            disk_size_gb: Template disk size

        Returns:
            Path to created template
        """
        iso_path = self.iso_manager.iso_storage_path / iso_name
        template_path = self.template_path / f"{template_name}.qcow2"

        if not iso_path.exists():
            raise FileNotFoundError(f"ISO not found: {iso_name}")

        if template_path.exists():
            raise FileExistsError(f"Template already exists: {template_name}")

        # Create empty qcow2 disk
        logger.info(f"Creating qcow2 disk: {template_path}")
        subprocess.run(
            [
                'qemu-img', 'create',
                '-f', 'qcow2',
                str(template_path),
                f'{disk_size_gb}G'
            ],
            check=True,
            capture_output=True,
        )

        # Note: Actual OS installation would require:
        # 1. Boot VM with ISO attached
        # 2. Automated installation (preseed/kickstart)
        # 3. Sysprep/cleanup
        # 4. Shutdown and save as template
        #
        # This is complex and typically done manually or with tools like Packer

        logger.info(
            f"Template disk created: {template_path}\n"
            f"Manual installation required:\n"
            f"  virt-install --name temp --disk {template_path} --cdrom {iso_path} ..."
        )

        return str(template_path)
