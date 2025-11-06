"""
Django management command to rotate the encryption key.

This command will:
1. Decrypt all secrets with the old key
2. Re-encrypt them with the new key
3. Save the updated values

Usage:
    # Set both keys in environment
    export OLD_ENCRYPTION_KEY=<old_key>
    export ENCRYPTION_KEY=<new_key>
    python manage.py rotate_encryption_key [--dry-run]

Options:
    --dry-run: Show what would be rotated without making changes
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
from apps.core.auth.models import TwoFactorAuth
from apps.core.webhooks.models import Webhook
from apps.core.security.encryption import rotate_encryption


class Command(BaseCommand):
    help = 'Rotate encryption key for all encrypted secrets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be rotated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Get old and new keys
        old_key = os.environ.get('OLD_ENCRYPTION_KEY')
        new_key = settings.ENCRYPTION_KEY

        if not old_key:
            raise CommandError(
                'OLD_ENCRYPTION_KEY environment variable not set. '
                'Set it to the current encryption key before rotating.'
            )

        if not new_key:
            raise CommandError(
                'ENCRYPTION_KEY not configured. '
                'Set the new encryption key in your .env file.'
            )

        if old_key == new_key:
            raise CommandError('Old and new encryption keys are the same!')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')

        self.stdout.write(self.style.MIGRATE_HEADING('Rotating Encryption Key'))
        self.stdout.write(f"  Old key: {old_key[:20]}...")
        self.stdout.write(f"  New key: {new_key[:20]}...")
        self.stdout.write('')

        # Rotate 2FA secrets
        self.stdout.write(self.style.MIGRATE_HEADING('Rotating 2FA TOTP Secrets'))
        self.rotate_2fa_secrets(old_key, new_key, dry_run)

        # Rotate webhook secrets
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Rotating Webhook Secrets'))
        self.rotate_webhook_secrets(old_key, new_key, dry_run)

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'This was a dry run. Run without --dry-run to apply changes.'
            ))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ All secrets rotated successfully!'))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'IMPORTANT: You can now remove OLD_ENCRYPTION_KEY from your environment'
            ))

    def rotate_2fa_secrets(self, old_key, new_key, dry_run):
        """Rotate 2FA TOTP secrets to new encryption key."""
        total = 0
        rotated = 0
        errors = 0

        for twofa in TwoFactorAuth.objects.all():
            total += 1

            if not twofa._secret_encrypted:
                continue

            try:
                # Rotate the encryption
                new_encrypted = rotate_encryption(
                    twofa._secret_encrypted,
                    old_key,
                    new_key
                )

                if not dry_run:
                    twofa._secret_encrypted = new_encrypted
                    twofa.save(update_fields=['_secret_encrypted'])

                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Rotated for user: {twofa.user.username}")
                )
                rotated += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Failed to rotate for {twofa.user.username}: {e}"
                    )
                )
                errors += 1

        self.stdout.write('')
        self.stdout.write(f"  Total 2FA records: {total}")
        self.stdout.write(f"  Successfully rotated: {rotated}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {errors}"))

    def rotate_webhook_secrets(self, old_key, new_key, dry_run):
        """Rotate webhook secrets to new encryption key."""
        total = 0
        rotated = 0
        errors = 0

        for webhook in Webhook.objects.all():
            total += 1

            if not webhook._secret_encrypted:
                continue

            try:
                # Rotate the encryption
                new_encrypted = rotate_encryption(
                    webhook._secret_encrypted,
                    old_key,
                    new_key
                )

                if not dry_run:
                    webhook._secret_encrypted = new_encrypted
                    webhook.save(update_fields=['_secret_encrypted'])

                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Rotated for webhook: {webhook.name}")
                )
                rotated += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ Failed to rotate for {webhook.name}: {e}"
                    )
                )
                errors += 1

        self.stdout.write('')
        self.stdout.write(f"  Total webhook records: {total}")
        self.stdout.write(f"  Successfully rotated: {rotated}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {errors}"))
