# Environment Setup Fix

## Issue
WebOps installations may complete without creating the required `.env` configuration file, causing services to fail to start with errors like:
- Missing environment variables
- Configuration not found
- Database connection failures
- Redis connection failures
- Services unable to authenticate to PostgreSQL/Redis

## Root Cause
The installation process was missing a critical step to:
1. Create the main `.env` file from `.env.example`
2. Generate secure random passwords for services during installation
3. Use the generated passwords when creating database users and configuring services
4. Link the control panel to the main configuration

## Solution
We've implemented a centralized configuration approach:

1. **Main `.env` file at `/opt/webops/.env`** - Single source of truth for all configuration
2. **Environment setup script** - Creates `.env` from `.env.example` with generated passwords
3. **Password integration** - Services use passwords from the main `.env` during setup
4. **Symlinked configuration** - Control panel uses the main `.env` via symlink

## Files Created

### 1. Environment Setup Script
**Location:** `provisioning/versions/v1.0.0/setup/env-setup.sh`

This script:
- Creates `/opt/webops/.env` from `.env.example`
- Generates secure random passwords for all services:
  - `SECRET_KEY` (Django session security)
  - `ENCRYPTION_KEY` (Database encryption)
  - `REDIS_PASSWORD` (Redis authentication)
  - `DATABASE_URL` (PostgreSQL connection with generated password)
- Creates symlink from `/opt/webops/control-panel/.env` to main `.env`
- Configures Redis to use the generated password
- Verifies all required environment variables are present

### 2. Quick Fix Script
**Location:** `fix-missing-env.sh`

A user-friendly wrapper script that:
- Detects WebOps installation location
- Runs the environment setup script
- Provides clear next steps

## Changes Made

### Modified Files
- `provisioning/versions/v1.0.0/setup/django.sh`:
  - Now calls `env-setup.sh` early in the installation process
  - Reads database password from main `.env` when creating PostgreSQL user
  - Verifies `.env` symlink exists instead of creating separate file

### New Files
- `provisioning/versions/v1.0.0/setup/env-setup.sh` - Core environment setup script
- `fix-missing-env.sh` - Quick fix wrapper for existing installations
- `ENV_SETUP_FIX.md` - This documentation

## For New Installations

The fix is automatically applied during installation:
1. `env-setup.sh` creates `/opt/webops/.env` from `.env.example`
2. Secure passwords are generated for all services
3. PostgreSQL user is created with the password from `.env`
4. Redis is configured with the password from `.env`
5. Control panel symlinks to the main `.env`

## For Existing Installations

If your installation is already complete but services aren't starting due to missing `.env`:

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

- **Main configuration:** `/opt/webops/.env` (required, created from `.env.example`)
- **Control panel:** `/opt/webops/control-panel/.env` (symlink to main `.env`)

Verify with:
```bash
# Check main .env exists
ls -la /opt/webops/.env

# Check control panel symlink
ls -la /opt/webops/control-panel/.env
# Should show: .env -> /opt/webops/.env
```

## Generated Credentials

The environment setup automatically generates:

| Variable | Purpose | Security |
|----------|---------|----------|
| `SECRET_KEY` | Django session signing | 50-char random token |
| `ENCRYPTION_KEY` | Encrypts credentials in database | Fernet key (32-byte base64) |
| `REDIS_PASSWORD` | Redis authentication | 32-byte base64 random |

## Manual Configuration

After running the fix, you may want to customize the main `.env` file:

1. **Database credentials (if needed):**
   ```bash
   # Edit main .env
   sudo nano /opt/webops/.env

   # The DATABASE_URL is already set with a generated password
   # Only change if you need a specific password:
   DATABASE_URL=postgresql://webops:YOUR_PASSWORD@localhost:5432/webops_db

   # Then update PostgreSQL user password to match:
   sudo -u postgres psql -c "ALTER USER webops WITH PASSWORD 'YOUR_PASSWORD';"
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
# Check main .env exists
test -f /opt/webops/.env && echo "✓ Main .env exists" || echo "✗ Main .env missing"

# Check control panel symlink
test -L /opt/webops/control-panel/.env && echo "✓ Control panel .env is symlink" || echo "✗ Not a symlink"

# Check required variables in main .env
grep -q "^SECRET_KEY=" /opt/webops/.env && echo "✓ SECRET_KEY set"
grep -q "^DATABASE_URL=" /opt/webops/.env && echo "✓ DATABASE_URL set"
grep -q "^ENCRYPTION_KEY=" /opt/webops/.env && echo "✓ ENCRYPTION_KEY set"
grep -q "^REDIS_PASSWORD=" /opt/webops/.env && echo "✓ REDIS_PASSWORD set"

# Verify PostgreSQL user can connect with password from .env
DB_PASSWORD=$(grep "^DATABASE_URL=" /opt/webops/.env | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
PGPASSWORD="$DB_PASSWORD" psql -U webops -d webops_db -c "SELECT 1" &>/dev/null && echo "✓ Database authentication works"

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
