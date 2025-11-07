# Environment Setup Fix

## Issue
WebOps installations may complete without creating the required `.env` configuration files, causing services to fail to start with errors like:
- Missing environment variables
- Configuration not found
- Database connection failures
- Redis connection failures

## Root Cause
The installation process was missing a critical step to ensure `.env` files are created with proper configuration before services start.

## Solution
We've added:
1. **New environment setup script** (`provisioning/versions/v1.0.0/setup/env-setup.sh`) that ensures all required `.env` files exist
2. **Updated Django installation** (`provisioning/versions/v1.0.0/setup/django.sh`) to call the environment setup script
3. **Quick fix script** (`fix-missing-env.sh`) for existing installations

## Files Created

### 1. Environment Setup Script
**Location:** `provisioning/versions/v1.0.0/setup/env-setup.sh`

This script:
- Creates `/opt/webops/.env` from `.env.example` (if it exists)
- Creates `/opt/webops/control-panel/.env` with all required Django settings
- Generates secure random values for:
  - `SECRET_KEY` (Django secret key)
  - `ENCRYPTION_KEY` (for encrypting sensitive data)
  - `REDIS_PASSWORD` (for Redis authentication)
- Configures Redis to use the generated password
- Verifies all required environment variables are present

### 2. Quick Fix Script
**Location:** `fix-missing-env.sh`

A user-friendly wrapper script that:
- Detects WebOps installation location
- Runs the environment setup script
- Provides clear next steps

## For New Installations

The fix is automatically applied during installation. The updated `django.sh` now calls `env-setup.sh` to ensure environment files exist before starting services.

## For Existing Installations

If your installation is already complete but services aren't starting due to missing `.env` files:

### Option 1: Use the Quick Fix Script

```bash
cd /opt/webops
sudo ./fix-missing-env.sh
```

This will:
1. Create missing `.env` files
2. Generate secure credentials
3. Configure Redis authentication
4. Show you next steps

### Option 2: Run the Setup Script Directly

```bash
sudo /opt/webops/provisioning/versions/v1.0.0/setup/env-setup.sh
```

### After Running the Fix

1. **Verify the .env file was created:**
   ```bash
   ls -la /opt/webops/control-panel/.env
   cat /opt/webops/control-panel/.env
   ```

2. **Update Redis configuration (if not done automatically):**
   ```bash
   # Get the Redis password from .env
   REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" /opt/webops/control-panel/.env | cut -d'=' -f2)

   # Add to Redis config
   echo "requirepass ${REDIS_PASSWORD}" | sudo tee -a /etc/redis/redis.conf

   # Restart Redis
   sudo systemctl restart redis-server
   ```

3. **Restart WebOps services:**
   ```bash
   sudo systemctl restart webops-web webops-worker webops-beat webops-channels
   ```

4. **Check service status:**
   ```bash
   sudo systemctl status webops-web webops-worker webops-beat webops-channels
   ```

5. **View service logs if there are issues:**
   ```bash
   sudo journalctl -u webops-web -n 50
   ```

## Environment File Locations

After the fix, you should have:

- **Root level:** `/opt/webops/.env` (optional, created from `.env.example` if it exists)
- **Control panel:** `/opt/webops/control-panel/.env` (required, auto-generated)

## Generated Credentials

The environment setup automatically generates:

| Variable | Purpose | Security |
|----------|---------|----------|
| `SECRET_KEY` | Django session signing | 50-char random token |
| `ENCRYPTION_KEY` | Encrypts credentials in database | Fernet key (32-byte base64) |
| `REDIS_PASSWORD` | Redis authentication | 32-byte base64 random |

## Manual Configuration

After running the fix, you may want to customize:

1. **Database credentials:**
   ```bash
   # Edit .env
   sudo nano /opt/webops/control-panel/.env

   # Update this line if your PostgreSQL password is different:
   DATABASE_URL=postgresql://webops:YOUR_PASSWORD@localhost:5432/webops
   ```

2. **GitHub OAuth (optional):**
   ```bash
   # Add these to .env if you want GitHub integration:
   GITHUB_OAUTH_CLIENT_ID=your_client_id
   GITHUB_OAUTH_CLIENT_SECRET=your_client_secret
   GITHUB_OAUTH_REDIRECT_URI=http://YOUR_IP:8000/integrations/github/callback
   ```

3. **Email notifications (optional):**
   ```bash
   # Add these to .env if you want email notifications:
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=your_email@gmail.com
   EMAIL_HOST_PASSWORD=your_app_password
   EMAIL_USE_TLS=True
   ```

## Verification

To verify the fix worked:

```bash
# Check .env exists
test -f /opt/webops/control-panel/.env && echo "✓ .env exists" || echo "✗ .env missing"

# Check required variables
grep -q "^SECRET_KEY=" /opt/webops/control-panel/.env && echo "✓ SECRET_KEY set"
grep -q "^DATABASE_URL=" /opt/webops/control-panel/.env && echo "✓ DATABASE_URL set"
grep -q "^ENCRYPTION_KEY=" /opt/webops/control-panel/.env && echo "✓ ENCRYPTION_KEY set"
grep -q "^REDIS_PASSWORD=" /opt/webops/control-panel/.env && echo "✓ REDIS_PASSWORD set"

# Check services are running
systemctl is-active webops-web && echo "✓ webops-web running"
systemctl is-active webops-worker && echo "✓ webops-worker running"
```

## Security Notes

1. **File Permissions:** The `.env` file is created with `600` permissions (owner read/write only)
2. **Ownership:** Owned by the `webops` user for security
3. **Secrets:** Never commit `.env` files to version control (already in `.gitignore`)
4. **Redis:** After setup, Redis requires password authentication
5. **Production:** Always change default passwords in production

## Troubleshooting

### Services still failing after fix

```bash
# Check logs for specific errors
sudo journalctl -u webops-web -n 100

# Common issues:
# 1. PostgreSQL not running
sudo systemctl status postgresql
sudo systemctl start postgresql

# 2. Redis not running
sudo systemctl status redis-server
sudo systemctl start redis-server

# 3. Redis password mismatch
# Make sure Redis config matches .env file
grep requirepass /etc/redis/redis.conf
grep REDIS_PASSWORD /opt/webops/control-panel/.env
```

### Permission errors

```bash
# Fix ownership
sudo chown -R webops:webops /opt/webops/control-panel

# Fix .env permissions
sudo chmod 600 /opt/webops/control-panel/.env
sudo chown webops:webops /opt/webops/control-panel/.env
```

### Database connection errors

```bash
# Check if webops database exists
sudo -u postgres psql -c "\l" | grep webops

# Create if missing
sudo -u postgres createdb webops
sudo -u postgres psql -c "CREATE USER webops WITH PASSWORD 'webops';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE webops TO webops;"

# Run migrations
cd /opt/webops/control-panel
sudo -u webops ./venv/bin/python manage.py migrate
```

## Changes Made

### Modified Files
- `provisioning/versions/v1.0.0/setup/django.sh` - Added call to env-setup.sh

### New Files
- `provisioning/versions/v1.0.0/setup/env-setup.sh` - Environment setup script
- `fix-missing-env.sh` - Quick fix wrapper script
- `ENV_SETUP_FIX.md` - This documentation

## Testing

To test the fix on a fresh installation:

```bash
# 1. Install WebOps normally
sudo provisioning/versions/v1.0.0/lifecycle/install.sh

# 2. Verify .env was created
ls -la /opt/webops/control-panel/.env

# 3. Check services are running
systemctl status webops-web webops-worker webops-beat

# 4. Access control panel
curl http://localhost:8000/
```

## Future Improvements

- [ ] Add .env validation during health checks
- [ ] Create .env template migration for major version upgrades
- [ ] Add .env backup/restore functionality
- [ ] Implement .env encryption at rest
- [ ] Add environment variable documentation generator

---

**Date:** 2025-11-07
**Issue:** Missing .env setup in installation process
**Resolution:** Added env-setup.sh script and quick fix for existing installations
**Status:** ✓ Fixed
