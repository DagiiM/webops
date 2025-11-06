"""
Automated Backup System

Manages scheduled VM backups with retention policies.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models

from .models import VMDeployment, VMSnapshot, BaseModel
from .deployment_service import KVMDeploymentService

logger = logging.getLogger(__name__)


class BackupSchedule(BaseModel):
    """
    Backup schedule configuration for VMs.
    """
    vm_deployment = models.ForeignKey(
        VMDeployment,
        on_delete=models.CASCADE,
        related_name='backup_schedules'
    )

    enabled = models.BooleanField(default=True)

    # Schedule
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily'
    )

    hour = models.IntegerField(
        default=2,
        help_text="Hour of day for backup (0-23)"
    )

    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of week for weekly backups (0=Monday)"
    )

    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of month for monthly backups (1-31)"
    )

    # Retention
    retention_count = models.IntegerField(
        default=7,
        help_text="Number of backups to keep"
    )

    retention_days = models.IntegerField(
        default=30,
        help_text="Maximum age of backups in days"
    )

    # Last run
    last_run = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)

    # Storage
    backup_location = models.CharField(
        max_length=500,
        blank=True,
        help_text="Custom backup location (default: /var/lib/webops/backups)"
    )

    compress = models.BooleanField(
        default=True,
        help_text="Compress backups"
    )

    class Meta:
        verbose_name = "Backup Schedule"
        verbose_name_plural = "Backup Schedules"

    def __str__(self):
        return f"{self.vm_deployment.vm_name} - {self.frequency}"


class BackupRecord(BaseModel):
    """
    Record of a backup operation.
    """
    backup_schedule = models.ForeignKey(
        BackupSchedule,
        on_delete=models.CASCADE,
        related_name='backups'
    )

    snapshot = models.ForeignKey(
        VMSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='backup_records'
    )

    backup_path = models.CharField(max_length=500)
    backup_size_mb = models.IntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )

    error_message = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Backup Record"
        verbose_name_plural = "Backup Records"

    def __str__(self):
        return f"{self.backup_schedule.vm_deployment.vm_name} - {self.created_at}"


class BackupManager:
    """
    Manages VM backup operations.
    """

    def __init__(self):
        self.default_backup_path = Path('/var/lib/webops/backups')
        self.default_backup_path.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        vm_deployment: VMDeployment,
        backup_name: Optional[str] = None,
        compress: bool = True,
    ) -> BackupRecord:
        """
        Create a backup of a VM.

        Args:
            vm_deployment: VM to backup
            backup_name: Custom backup name
            compress: Compress backup files

        Returns:
            BackupRecord instance
        """
        if not backup_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{vm_deployment.vm_name}_{timestamp}"

        logger.info(f"Starting backup: {backup_name}")

        # Create backup record
        backup_record = BackupRecord.objects.create(
            backup_schedule=None,  # Manual backup
            backup_path='',
            status='running',
            started_at=timezone.now()
        )

        try:
            # 1. Create snapshot
            service = KVMDeploymentService()
            snapshot_name = f"backup_{backup_name}"

            success = service.create_snapshot(
                vm_deployment,
                snapshot_name,
                f"Automated backup: {backup_name}"
            )

            if not success:
                raise Exception("Snapshot creation failed")

            snapshot = VMSnapshot.objects.get(
                vm_deployment=vm_deployment,
                name=snapshot_name
            )

            # 2. Export disk
            backup_dir = self.default_backup_path / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)

            disk_backup = self._export_disk(
                vm_deployment.disk_path,
                backup_dir,
                compress=compress
            )

            # 3. Save VM metadata
            metadata = self._export_metadata(vm_deployment, backup_dir)

            # 4. Calculate total size
            total_size_mb = sum(
                f.stat().st_size
                for f in backup_dir.rglob('*')
                if f.is_file()
            ) / (1024 * 1024)

            # Update record
            backup_record.snapshot = snapshot
            backup_record.backup_path = str(backup_dir)
            backup_record.backup_size_mb = int(total_size_mb)
            backup_record.status = 'completed'
            backup_record.completed_at = timezone.now()
            backup_record.save()

            logger.info(f"Backup completed: {backup_name} ({total_size_mb:.1f}MB)")

            return backup_record

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            backup_record.status = 'failed'
            backup_record.error_message = str(e)
            backup_record.completed_at = timezone.now()
            backup_record.save()
            raise

    def _export_disk(
        self,
        source_disk: str,
        backup_dir: Path,
        compress: bool = True
    ) -> Path:
        """Export VM disk to backup directory."""
        import shutil
        import gzip

        disk_name = Path(source_disk).name
        output_file = backup_dir / (f"{disk_name}.gz" if compress else disk_name)

        logger.info(f"Exporting disk to {output_file}")

        # SECURITY FIX: Use Python libraries instead of shell=True
        if compress:
            # Use gzip module instead of shell command
            with open(source_disk, 'rb') as f_in:
                with gzip.open(output_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Use shutil.copy2 instead of shell command
            shutil.copy2(source_disk, output_file)

        return output_file

    def _export_metadata(self, vm_deployment: VMDeployment, backup_dir: Path) -> Path:
        """Export VM metadata (config, plan, etc.)."""
        import json

        metadata = {
            'vm_name': vm_deployment.vm_name,
            'vm_uuid': vm_deployment.vm_uuid,
            'plan': {
                'name': vm_deployment.vm_plan.name,
                'vcpus': vm_deployment.vcpus,
                'memory_mb': vm_deployment.memory_mb,
                'disk_gb': vm_deployment.disk_gb,
            },
            'os_template': vm_deployment.os_template.name,
            'ip_address': vm_deployment.ip_address,
            'mac_address': vm_deployment.mac_address,
            'ssh_public_keys': vm_deployment.ssh_public_keys,
            'backup_timestamp': datetime.now().isoformat(),
        }

        metadata_file = backup_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Exported metadata to {metadata_file}")
        return metadata_file

    def restore_backup(
        self,
        backup_record: BackupRecord,
        target_node: Optional['ComputeNode'] = None
    ) -> VMDeployment:
        """
        Restore a VM from backup.

        Args:
            backup_record: Backup to restore
            target_node: Target compute node (optional)

        Returns:
            Restored VMDeployment
        """
        backup_dir = Path(backup_record.backup_path)

        if not backup_dir.exists():
            raise FileNotFoundError(f"Backup not found: {backup_dir}")

        # Load metadata
        import json
        metadata_file = backup_dir / 'metadata.json'
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        logger.info(f"Restoring backup: {metadata['vm_name']}")

        # TODO: Implement full restoration
        # 1. Create new deployment record
        # 2. Restore disk from backup
        # 3. Create VM with restored disk
        # 4. Apply metadata

        raise NotImplementedError("Backup restoration not yet implemented")

    def cleanup_old_backups(self, schedule: BackupSchedule):
        """
        Clean up old backups according to retention policy.

        Args:
            schedule: Backup schedule with retention settings
        """
        backups = BackupRecord.objects.filter(
            backup_schedule=schedule,
            status='completed'
        ).order_by('-created_at')

        # Apply retention count
        if schedule.retention_count > 0:
            to_delete = backups[schedule.retention_count:]

            for backup in to_delete:
                logger.info(f"Deleting old backup: {backup.backup_path}")
                self._delete_backup(backup)

        # Apply retention days
        if schedule.retention_days > 0:
            cutoff_date = timezone.now() - timedelta(days=schedule.retention_days)
            old_backups = backups.filter(created_at__lt=cutoff_date)

            for backup in old_backups:
                logger.info(f"Deleting expired backup: {backup.backup_path}")
                self._delete_backup(backup)

    def _delete_backup(self, backup_record: BackupRecord):
        """Delete backup files and record."""
        import shutil

        backup_path = Path(backup_record.backup_path)

        if backup_path.exists():
            shutil.rmtree(backup_path)

        # Delete snapshot if exists
        if backup_record.snapshot:
            # TODO: Delete libvirt snapshot
            pass

        backup_record.delete()


# Celery task for scheduled backups
def run_scheduled_backups():
    """
    Celery task to run scheduled backups.

    Should be called hourly to check for due backups.
    """
    from celery import shared_task

    @shared_task
    def _run_scheduled_backups():
        from .backup import BackupSchedule, BackupManager

        now = timezone.now()
        manager = BackupManager()

        schedules = BackupSchedule.objects.filter(enabled=True)

        for schedule in schedules:
            if should_run_backup(schedule, now):
                try:
                    logger.info(f"Running scheduled backup for {schedule.vm_deployment.vm_name}")

                    backup_record = manager.create_backup(
                        schedule.vm_deployment,
                        compress=schedule.compress
                    )

                    backup_record.backup_schedule = schedule
                    backup_record.save()

                    schedule.last_run = now
                    schedule.last_success = now
                    schedule.save()

                    # Cleanup old backups
                    manager.cleanup_old_backups(schedule)

                except Exception as e:
                    logger.error(f"Scheduled backup failed: {e}")
                    schedule.last_run = now
                    schedule.save()

    return _run_scheduled_backups


def should_run_backup(schedule: BackupSchedule, now: datetime) -> bool:
    """Check if backup should run based on schedule."""
    if not schedule.last_run:
        return True

    time_since_last = now - schedule.last_run

    if schedule.frequency == 'hourly':
        return time_since_last >= timedelta(hours=1)
    elif schedule.frequency == 'daily':
        return (
            time_since_last >= timedelta(days=1) and
            now.hour == schedule.hour
        )
    elif schedule.frequency == 'weekly':
        return (
            time_since_last >= timedelta(days=7) and
            now.weekday() == schedule.day_of_week and
            now.hour == schedule.hour
        )
    elif schedule.frequency == 'monthly':
        return (
            time_since_last >= timedelta(days=28) and
            now.day == schedule.day_of_month and
            now.hour == schedule.hour
        )

    return False
