# Security Key Management Guide

## Overview

WebOps uses **Fernet symmetric encryption** (AES-128-CBC + HMAC) to protect sensitive data at rest:
- 2FA TOTP secrets
- Webhook secrets
- Database passwords
- API tokens

This document provides procedures for key generation, rotation, and management.

---

## Table of Contents

1. [Generating Encryption Keys](#generating-encryption-keys)
2. [Initial Setup](#initial-setup)
3. [Encrypting Existing Data](#encrypting-existing-data)
4. [Key Rotation](#key-rotation)
5. [Backup and Recovery](#backup-and-recovery)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Generating Encryption Keys

### Generate a New Fernet Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Output example:**
```
Ixmh9heL7hp0k27wIXcO8j22zrB_VWXAHQ3YJOXEwLI=
```

⚠️ **CRITICAL:** Each environment (development, staging, production) MUST use a different encryption key.

---

## Initial Setup

### 1. Generate Your Encryption Key

```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Add to Environment

```bash
# In your .env file
ENCRYPTION_KEY=<your_generated_key_here>
```

### 3. Verify Configuration

```bash
cd control-panel
python manage.py shell

>>> from django.conf import settings
>>> print(settings.ENCRYPTION_KEY[:20])  # Should print first 20 chars
>>> from cryptography.fernet import Fernet
>>> Fernet(settings.ENCRYPTION_KEY.encode())  # Should not raise error
>>> exit()
```

---

## Encrypting Existing Data

If you're upgrading from a version without encryption, you need to encrypt existing secrets.

### Dry Run (Check What Will Be Encrypted)

```bash
cd control-panel
python manage.py encrypt_secrets --dry-run
```

### Encrypt All Secrets

```bash
python manage.py encrypt_secrets
```

**Expected output:**
```
Encrypting 2FA TOTP Secrets
  Found unencrypted secret for user: admin
    ✓ Encrypted for admin
  Found unencrypted secret for user: john
    ✓ Encrypted for john

  Total 2FA records: 5
  Already encrypted: 3
  Newly encrypted: 2

Encrypting Webhook Secrets
  Found unencrypted secret for webhook: GitHub Deploy Hook
    ✓ Encrypted for GitHub Deploy Hook

  Total webhook records: 3
  Already encrypted: 2
  Newly encrypted: 1

✓ All secrets encrypted successfully!
```

---

## Key Rotation

Rotate your encryption key periodically (recommended: every 90 days) or immediately if compromised.

### 1. Generate New Key

```bash
# Generate a NEW encryption key
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "New key: $NEW_KEY"
```

### 2. Set Environment Variables

```bash
# Set BOTH old and new keys
export OLD_ENCRYPTION_KEY="<current_key_from_.env>"
export ENCRYPTION_KEY="$NEW_KEY"
```

### 3. Dry Run

```bash
cd control-panel
python manage.py rotate_encryption_key --dry-run
```

### 4. Perform Rotation

```bash
python manage.py rotate_encryption_key
```

**Expected output:**
```
Rotating Encryption Key
  Old key: Ixmh9heL7hp0k27wIX...
  New key: YjNmODE4ZGUtNGY4Zi...

Rotating 2FA TOTP Secrets
  ✓ Rotated for user: admin
  ✓ Rotated for user: john

  Total 2FA records: 2
  Successfully rotated: 2

Rotating Webhook Secrets
  ✓ Rotated for webhook: GitHub Deploy Hook

  Total webhook records: 1
  Successfully rotated: 1

✓ All secrets rotated successfully!

IMPORTANT: You can now remove OLD_ENCRYPTION_KEY from your environment
```

### 5. Update .env File

```bash
# Update .env with the new key
echo "ENCRYPTION_KEY=$NEW_KEY" >> .env.new
# Then replace the old .env file
mv .env .env.backup
mv .env.new .env
```

### 6. Restart Application

```bash
# Restart Django application
sudo systemctl restart webops-control-panel

# Restart Celery workers
sudo systemctl restart webops-celery-worker
```

### 7. Clean Up

```bash
# Remove OLD_ENCRYPTION_KEY from environment
unset OLD_ENCRYPTION_KEY

# Verify rotation was successful
cd control-panel
python manage.py shell

>>> from apps.core.auth.models import TwoFactorAuth
>>> tfa = TwoFactorAuth.objects.first()
>>> secret = tfa.secret  # This should decrypt successfully
>>> print(len(secret))  # Should print 32 (TOTP secret length)
>>> exit()
```

---

## Backup and Recovery

### Backing Up Encryption Keys

⚠️ **CRITICAL:** Store encryption keys securely. If you lose the key, you CANNOT decrypt the data.

#### Option 1: Password Manager (Recommended)

Store in a password manager like:
- 1Password
- LastPass
- Bitwarden
- KeePass

#### Option 2: Hardware Security Module (HSM)

For production:
- AWS KMS (Key Management Service)
- Azure Key Vault
- Google Cloud KMS
- HashiCorp Vault

#### Option 3: Encrypted File (Development Only)

```bash
# Create encrypted backup
echo "ENCRYPTION_KEY=<your_key>" | gpg --symmetric --armor > encryption_key.gpg

# Restore from backup
gpg --decrypt encryption_key.gpg
```

### Disaster Recovery

If you lose your encryption key:

**❌ You CANNOT recover the encrypted data.**

However, you can:

1. **Generate a new key**
2. **Users must re-enable 2FA** (new TOTP secrets)
3. **Webhooks must be recreated** (new webhook secrets)

```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env
ENCRYPTION_KEY=<new_key>

# Restart services
sudo systemctl restart webops-control-panel webops-celery-worker
```

---

## Security Best Practices

### ✅ DO

- **Generate unique keys per environment** (dev, staging, prod)
- **Rotate keys every 90 days** or when employees leave
- **Store keys in a password manager** or HSM
- **Use environment variables**, never hard-code keys
- **Restrict key access** to only necessary personnel
- **Audit key usage** regularly
- **Test disaster recovery** procedures
- **Keep encrypted backups** of your key vault

### ❌ DON'T

- ❌ Commit encryption keys to version control
- ❌ Use the same key across multiple environments
- ❌ Share keys via email, Slack, or chat
- ❌ Store keys in plain text files
- ❌ Hard-code keys in source code
- ❌ Give everyone access to production keys
- ❌ Forget to rotate keys regularly
- ❌ Skip backing up your encryption keys

---

## Troubleshooting

### Problem: "ENCRYPTION_KEY not configured"

**Cause:** Missing ENCRYPTION_KEY in .env file

**Solution:**
```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env
echo "ENCRYPTION_KEY=<generated_key>" >> .env

# Restart application
sudo systemctl restart webops-control-panel
```

### Problem: "Invalid ENCRYPTION_KEY: must be 32 url-safe base64-encoded bytes"

**Cause:** Invalid key format

**Solution:**
```bash
# Generate a valid Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env with the new key
```

### Problem: "InvalidToken" when decrypting

**Cause:** Data was encrypted with a different key

**Solutions:**

1. **If you have the old key:** Rotate encryption from old to new key
   ```bash
   export OLD_ENCRYPTION_KEY="<old_key>"
   export ENCRYPTION_KEY="<new_key>"
   python manage.py rotate_encryption_key
   ```

2. **If you don't have the old key:** Data cannot be decrypted
   - Users must re-enable 2FA
   - Webhooks must be recreated

### Problem: "TwoFactorAuth has unencrypted secret" warning

**Cause:** Legacy data from before encryption was implemented

**Solution:**
```bash
python manage.py encrypt_secrets
```

### Problem: Key rotation fails halfway through

**Cause:** Database error or crash during rotation

**Solution:**
```bash
# Some records may be encrypted with old key, some with new key
# You need to manually fix this

# Check what's encrypted with which key
cd control-panel
python manage.py shell

>>> from apps.core.auth.models import TwoFactorAuth
>>> from cryptography.fernet import Fernet, InvalidToken
>>>
>>> old_key = Fernet(b"<old_key>")
>>> new_key = Fernet(b"<new_key>")
>>>
>>> for tfa in TwoFactorAuth.objects.all():
...     try:
...         old_key.decrypt(tfa._secret_encrypted.encode())
...         print(f"{tfa.user.username}: OLD KEY")
...     except InvalidToken:
...         try:
...             new_key.decrypt(tfa._secret_encrypted.encode())
...             print(f"{tfa.user.username}: NEW KEY")
...         except InvalidToken:
...             print(f"{tfa.user.username}: UNKNOWN KEY or CORRUPT")
```

Then rotate only the records still using the old key.

---

## Key Rotation Schedule

| Environment | Rotation Frequency | Reason |
|------------|-------------------|---------|
| **Development** | Every 180 days | Lower risk, but still good practice |
| **Staging** | Every 90 days | Matches production for testing |
| **Production** | Every 90 days | Compliance requirement (SOC 2, HIPAA) |
| **After Compromise** | Immediately | Security incident response |
| **After Employee Departure** | Within 24 hours | Access revocation |

---

## Compliance Notes

### SOC 2

- **Key rotation required:** Every 90 days
- **Access auditing required:** Log all key access
- **Separation of duties:** Different personnel for dev vs prod keys

### HIPAA

- **Encryption required:** For all PHI (Protected Health Information)
- **Key management required:** Documented key rotation procedures
- **Audit trail required:** Log all encryption key operations

### GDPR

- **Encryption recommended:** For personal data
- **Right to be forgotten:** Ability to delete encrypted data
- **Data portability:** Ability to decrypt for export

---

## Emergency Contacts

If you suspect your encryption key has been compromised:

1. **Immediately rotate the key** (see Key Rotation section)
2. **Notify security team:** security@your-company.com
3. **Check audit logs** for unauthorized access
4. **Force password resets** for all users
5. **Review 2FA and webhook configurations**

---

## Additional Resources

- [Fernet Specification](https://github.com/fernet/spec/)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)
- [NIST Guidelines](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
