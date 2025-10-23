"""
Management command to initialize WebOps directory structure.

This command creates all necessary directories for WebOps with proper permissions.
Run with sudo in production environments where WEBOPS_INSTALL_PATH requires elevated permissions.

Usage:
    # Development (no sudo needed if path is writable):
    python manage.py init_webops_dirs

    # Production (requires sudo for /opt/webops):
    sudo python manage.py init_webops_dirs

"File System Layout" section
"""

import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Initialize WebOps directory structure with proper permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            default=settings.WEBOPS_USER,
            help='User to own the directories (default: from settings)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating'
        )

    def handle(self, *args, **options):
        user = options['user']
        dry_run = options['dry_run']
        base_path = Path(settings.WEBOPS_INSTALL_PATH)

        self.stdout.write(self.style.MIGRATE_HEADING('Initializing WebOps Directory Structure'))
        self.stdout.write(f'Base path: {base_path}')
        self.stdout.write(f'Owner: {user}')
        self.stdout.write('')

        # Define directory structure based on CLAUDE.md
        directories = [
            base_path,
            base_path / 'deployments',
            base_path / 'backups',
            base_path / 'backups' / 'postgres',
            base_path / 'backups' / 'control-panel',
            base_path / 'tmp',
        ]

        # Check if we need elevated permissions
        if not base_path.parent.exists():
            self.stdout.write(
                self.style.ERROR(f'Parent directory {base_path.parent} does not exist!')
            )
            raise CommandError(f'Parent directory {base_path.parent} must exist first')

        # Test write permissions
        can_write = os.access(base_path.parent, os.W_OK) if base_path.parent.exists() else False

        if not can_write and os.geteuid() != 0:
            self.stdout.write(
                self.style.WARNING(
                    f'\nPermission denied for {base_path.parent}. '
                    'You may need to run this command with sudo:\n'
                    f'  sudo {" ".join(sys.argv)}\n'
                )
            )
            if not dry_run:
                raise CommandError('Insufficient permissions. Try running with sudo.')

        # Create directories
        created_count = 0
        existing_count = 0
        failed = []

        for directory in directories:
            status_msg = f'  {directory}'

            if dry_run:
                if directory.exists():
                    self.stdout.write(f'{status_msg} ' + self.style.SUCCESS('[exists]'))
                    existing_count += 1
                else:
                    self.stdout.write(f'{status_msg} ' + self.style.MIGRATE_LABEL('[would create]'))
                    created_count += 1
                continue

            try:
                if directory.exists():
                    self.stdout.write(f'{status_msg} ' + self.style.SUCCESS('[exists]'))
                    existing_count += 1
                else:
                    directory.mkdir(parents=True, exist_ok=True)

                    # Set proper permissions (755 for directories)
                    directory.chmod(0o755)

                    # Change ownership if running as root
                    if os.geteuid() == 0:
                        import pwd
                        try:
                            uid = pwd.getpwnam(user).pw_uid
                            gid = pwd.getpwnam(user).pw_gid
                            os.chown(directory, uid, gid)
                            self.stdout.write(
                                f'{status_msg} ' +
                                self.style.SUCCESS(f'[created, owner: {user}]')
                            )
                        except KeyError:
                            self.stdout.write(
                                f'{status_msg} ' +
                                self.style.WARNING(f'[created, but user {user} not found]')
                            )
                    else:
                        self.stdout.write(f'{status_msg} ' + self.style.SUCCESS('[created]'))

                    created_count += 1

            except PermissionError as e:
                self.stdout.write(f'{status_msg} ' + self.style.ERROR(f'[failed: {e}]'))
                failed.append(str(directory))
            except Exception as e:
                self.stdout.write(f'{status_msg} ' + self.style.ERROR(f'[error: {e}]'))
                failed.append(str(directory))

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Summary:'))

        if dry_run:
            self.stdout.write(f'  Would create: {created_count} directories')
            self.stdout.write(f'  Already exist: {existing_count} directories')
        else:
            self.stdout.write(f'  Created: {created_count} directories')
            self.stdout.write(f'  Already existed: {existing_count} directories')

            if failed:
                self.stdout.write(f'  Failed: {len(failed)} directories')
                self.stdout.write(self.style.ERROR('Failed directories:'))
                for fail_dir in failed:
                    self.stdout.write(f'    - {fail_dir}')
                raise CommandError('Some directories could not be created')

        self.stdout.write('')

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS('Dry run completed. Remove --dry-run to actually create directories.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('WebOps directory structure initialized successfully!')
            )
            self.stdout.write('')
            self.stdout.write('Next steps:')
            self.stdout.write('  1. Verify deployments work: python manage.py runserver')
            self.stdout.write('  2. Create a test deployment through the control panel')
            self.stdout.write('')
