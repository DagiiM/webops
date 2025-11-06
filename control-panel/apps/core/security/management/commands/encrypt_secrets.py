"""
Django management command to encrypt existing unencrypted secrets.

This command will:
1. Find all TwoFactorAuth records with unencrypted secrets
2. Find all Webhook records with unencrypted secrets
3. Encrypt them using the current ENCRYPTION_KEY
4. Save the encrypted values back to the database

Usage:
    python manage.py encrypt_secrets [--dry-run]

Options:
    --dry-run: Show what would be encrypted without making changes
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from apps.core.auth.models import TwoFactorAuth
from apps.core.webhooks.models import Webhook
from apps.core.security.encryption import encrypt_field, is_encrypted


class Command(BaseCommand):
    help = 'Encrypt existing unencrypted secrets (2FA TOTP secrets and webhook secrets)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be encrypted without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if not settings.ENCRYPTION_KEY:
            raise CommandError(
                'ENCRYPTION_KEY not configured. '
                'Set it in your .env file before running this command.'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')

        # Encrypt TwoFactorAuth secrets
        self.stdout.write(self.style.MIGRATE_HEADING('Encrypting 2FA TOTP Secrets'))
        self.encrypt_2fa_secrets(dry_run)

        # Encrypt Webhook secrets
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Encrypting Webhook Secrets'))
        self.encrypt_webhook_secrets(dry_run)

        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'This was a dry run. Run without --dry-run to apply changes.'
            ))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✓ All secrets encrypted successfully!'))

    def encrypt_2fa_secrets(self, dry_run):
        """Encrypt unencrypted 2FA TOTP secrets."""
        total = 0
        encrypted = 0
        already_encrypted = 0

        for twofa in TwoFactorAuth.objects.all():
            total += 1

            if not twofa._secret_encrypted:
                self.stdout.write(f"  Skipping {twofa.user.username}: empty secret")
                continue

            if is_encrypted(twofa._secret_encrypted):
                already_encrypted += 1
                continue

            # This is an unencrypted secret
            self.stdout.write(
                self.style.WARNING(
                    f"  Found unencrypted secret for user: {twofa.user.username}"
                )
            )

            if not dry_run:
                # Encrypt it by reading and writing through the property
                plain_secret = twofa._secret_encrypted
                twofa.secret = plain_secret  # This will encrypt it
                twofa.save(update_fields=['_secret_encrypted'])
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Encrypted for {twofa.user.username}")
                )

            encrypted += 1

        self.stdout.write('')
        self.stdout.write(f"  Total 2FA records: {total}")
        self.stdout.write(f"  Already encrypted: {already_encrypted}")
        self.stdout.write(f"  Newly encrypted: {encrypted}")

    def encrypt_webhook_secrets(self, dry_run):
        """Encrypt unencrypted webhook secrets."""
        total = 0
        encrypted = 0
        already_encrypted = 0

        for webhook in Webhook.objects.all():
            total += 1

            if not webhook._secret_encrypted:
                self.stdout.write(f"  Skipping {webhook.name}: empty secret")
                continue

            if is_encrypted(webhook._secret_encrypted):
                already_encrypted += 1
                continue

            # This is an unencrypted secret
            self.stdout.write(
                self.style.WARNING(
                    f"  Found unencrypted secret for webhook: {webhook.name}"
                )
            )

            if not dry_run:
                # Encrypt it by reading and writing through the property
                plain_secret = webhook._secret_encrypted
                webhook.secret = plain_secret  # This will encrypt it
                webhook.save(update_fields=['_secret_encrypted'])
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Encrypted for {webhook.name}")
                )

            encrypted += 1

        self.stdout.write('')
        self.stdout.write(f"  Total webhook records: {total}")
        self.stdout.write(f"  Already encrypted: {already_encrypted}")
        self.stdout.write(f"  Newly encrypted: {encrypted}")
