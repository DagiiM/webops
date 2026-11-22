"""Preserve and encrypt legacy 2FA and webhook secrets on existing installations.

The old DB columns are named 'secret'; models now expose '_secret_encrypted'.
RenameField followed by AlterField preserves the original column/data instead of
accidentally deleting and recreating it.  No placeholder secret is ever used.
"""
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations, models


def encrypt_legacy_secrets(apps, schema_editor):
    cipher = None
    for model_name in ("TwoFactorAuth", "Webhook"):
        model = apps.get_model("core", model_name)
        qs = model.objects.using(schema_editor.connection.alias)
        for entry in qs.iterator():
            value = entry._secret_encrypted
            if not value:
                continue
            if cipher is None:
                # Missing or incorrect keys must fail migration rather than corrupt data.
                cipher = Fernet(settings.ENCRYPTION_KEY)
            if value.startswith("gAAAAA"):
                # Verify that the configured key can decrypt existing encrypted values.
                cipher.decrypt(value.encode("utf-8"))
                continue
            encrypted = cipher.encrypt(value.encode("utf-8")).decode("utf-8")
            if len(encrypted) > 256:
                raise ValueError("Encrypted secret exceeds the schema limit")
            qs.filter(pk=entry.pk).update(_secret_encrypted=encrypted)


class Migration(migrations.Migration):
    dependencies = [("core", "0006_usernotification")]
    operations = [
        migrations.RenameField(model_name="twofactorauth", old_name="secret", new_name="_secret_encrypted"),
        migrations.AlterField(
            model_name="twofactorauth", name="_secret_encrypted",
            field=models.CharField(max_length=256, unique=True, db_column="secret", help_text="Encrypted TOTP secret"),
        ),
        # Drop the old index before renaming a field it references (SQLite rebuild).
        migrations.RemoveIndex(model_name="webhook", name="core_webhoo_secret_94f437_idx"),
        migrations.RenameField(model_name="webhook", old_name="secret", new_name="_secret_encrypted"),
        migrations.AlterField(
            model_name="webhook", name="_secret_encrypted",
            field=models.CharField(max_length=256, unique=True, db_column="secret", help_text="Encrypted webhook secret for request validation"),
        ),
        migrations.AddIndex(model_name="webhook", index=models.Index(
            fields=["_secret_encrypted"], name="core_webhoo_secret_94f437_idx"
        )),
        migrations.RunPython(encrypt_legacy_secrets),
    ]
