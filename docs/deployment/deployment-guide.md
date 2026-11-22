# WebOps Deployment Guide

**Deploy your Django project in minutes with WebOps**

This guide will help you prepare and deploy your Django application using WebOps - a simple, self-hosted deployment platform.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Preparing Your Django Project](#preparing-your-django-project)
3. [Deployment Methods](#deployment-methods)
4. [Environment Variables](#environment-variables)
5. [Database Setup](#database-setup)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Files in Your Repository

Your Django project **must** have these files in the repository root:

- ✅ `manage.py` - Django management script
- ✅ `requirements.txt` - Python dependencies
- ✅ Standard Django project structure

### Supported Configurations

- **Python Version**: 3.11+ (recommended)
- **Django Version**: 5.0+ (any modern version)
- **Database**: PostgreSQL (recommended), SQLite (development only)
- **Repository**: Public or private GitHub repositories

---

## Preparing Your Django Project

### 1. Create `requirements.txt`

WebOps installs dependencies from `requirements.txt`. Generate it with:

```bash
pip freeze > requirements.txt
```

**Minimum requirements for a Django project:**

```txt
Django>=5.0
gunicorn>=21.0
```

**For PostgreSQL database:**

```txt
Django>=5.0
gunicorn>=21.0
psycopg2-binary>=2.9
```

**For static files (recommended):**

```txt
Django>=5.0
gunicorn>=21.0
whitenoise>=6.5
```

### 2. Configure Settings for Production

Update your `settings.py` to handle production deployment:

```python
import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')

# Database - use DATABASE_URL environment variable
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'myapp_db'),
        'USER': os.environ.get('DB_USER', 'myapp_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (if you have user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

**Alternative: Using django-environ (recommended)**

Add to `requirements.txt`:
```txt
django-environ>=0.11
```

In `settings.py`:
```python
import environ

env = environ.Env(
    DEBUG=(bool, False)
)

# Read .env file if it exists
environ.Env.read_env()

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

DATABASES = {
    'default': env.db('DATABASE_URL')
}
```

### 3. Static Files Setup

**Option A: WhiteNoise (Recommended for simplicity)**

Add to `requirements.txt`:
```txt
whitenoise>=6.5
```

In `settings.py`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add this
    # ... other middleware
]

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

**Option B: Nginx static serving (WebOps handles this)**

```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'
```

### 4. Prepare Your Repository

Ensure your `.gitignore` includes:

```gitignore
# Python
*.pyc
__pycache__/
*.py[cod]
*$py.class

# Django
*.log
db.sqlite3
db.sqlite3-journal
/staticfiles/
/media/

# Environment
.env
.env.local
venv/
env/

# IDE
.vscode/
.idea/
*.swp
```

**Commit and push your changes:**

```bash
git add .
git commit -m "Prepare for WebOps deployment"
git push origin main
```

---

## Deployment Methods

### Method 1: Using the Web Interface

1. **Access WebOps Control Panel**
   ```
   http://your-webops-server:8000
   ```

2. **Login** with your credentials

3. **Navigate to Deployments** → "New Deployment"

4. **Fill in the form:**
   - **Name**: `my-django-app` (lowercase, no spaces)
   - **Repository URL**: `https://github.com/yourusername/your-repo`
   - **Branch**: `main` (or your deployment branch)
   - **Domain** (optional): `myapp.example.com`

5. **Add Environment Variables** (click "Add Environment Variable"):
   ```
   SECRET_KEY = your-secret-key-here
   DEBUG = False
   ALLOWED_HOSTS = your-domain.com,www.your-domain.com
   DB_NAME = myapp_db
   DB_USER = myapp_user
   DB_PASSWORD = [generated automatically]
   ```

6. **Click "Deploy"**

7. **Monitor the deployment** in real-time through the logs viewer

### Method 2: Using the CLI

1. **Install WebOps CLI:**
   ```bash
   # From the WebOps repository root
   python -m pip install -e ./cli
   ```

2. **Configure authentication using an approved, least-privileged WebOps API token:**
   ```bash
   webops config --url https://panel.example.com --token "$WEBOPS_CLI_TOKEN" --role developer
   ```
   A token provided as a process argument may be visible to other local processes; use a trusted host and your organization's secret-handling procedure. Do not paste literal credentials into shell history.

3. **Validate the plan, then submit the application deployment explicitly:**
   ```bash
   webops deploy yourusername/your-repo --name my-django-app \
     --branch main --domain myapp.example.com --dry-run

   webops deploy yourusername/your-repo --name my-django-app \
     --branch main --domain myapp.example.com --approve --wait
   ```
   `webops deploy` does **not** accept `--env`. Configure application secrets through the approved WebOps environment/secret management workflow, avoiding plaintext command arguments and repository files.

4. **Inspect WebOps-reported state (not an HTTP health guarantee):**
   ```bash
   webops info my-django-app
   ```

5. **Inspect logs and probe the real application HTTPS endpoint:**
   ```bash
   webops logs my-django-app --tail 100
   # Replace with your actual verified deployment URL / health endpoint
   curl --fail --show-error --silent https://myapp.example.com/health/
   ```
   A reported `running` state from `--wait` is not proof that the application answered the probe.

### Method 3: Using the API

For automation, use the authenticated `webops deploy ... --approve` CLI or follow the deployment API contract exposed by **your installed control-panel version**. Do not copy unverified endpoint paths or authentication schemes from older examples, and do not send application secrets in terminal-visible inline JSON. See the [API reference](../reference/api-reference.md) and the [AI-assisted deployment guide](ai-assisted-github-deployments.md).

---

## Environment Variables

### Essential Variables

Every Django deployment needs these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-xyz123...` |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | `myapp.com,www.myapp.com` |

### Database Variables

WebOps automatically creates a PostgreSQL database for your app and provides:

| Variable | Description | Auto-Generated |
|----------|-------------|----------------|
| `DB_NAME` | Database name | ✅ |
| `DB_USER` | Database username | ✅ |
| `DB_PASSWORD` | Database password | ✅ |
| `DB_HOST` | Database host | ✅ |
| `DB_PORT` | Database port | ✅ |
| `DATABASE_URL` | Full connection string | ✅ |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Settings module | `config.settings` |
| `STATIC_URL` | Static files URL | `/static/` |
| `MEDIA_URL` | Media files URL | `/media/` |

### Generating a Secret Key

**Method 1: Python**
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

**Method 2: OpenSSL**
```bash
openssl rand -base64 50
```

**Method 3: Online**
```
https://djecrety.ir/
```

---

## Database Setup

### Database provisioning and migration verification

Depending on the selected deployment backend, WebOps may provision a database
or coordinate application startup. **Do not assume** a database was created,
credentials were rotated or Django migrations completed until the live worker
and database are inspected.

```bash
webops db:list
webops info my-django-app
webops logs my-django-app --tail 100
```

For migrations, fixture loading or Django superuser creation, connect to the
**approved deployed application's execution context** using your hosting
provider's documented administrative procedure. These operations are not exposed
as a general `webops run` or `webops shell` command. Use secrets from the
approved secret store; never put passwords in command history. Record migration
and backup/restore results before production release.

### Using SQLite (Development Only)

For testing, you can use SQLite:

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

**Note:** SQLite is not recommended for production deployments.

---

## Post-Deployment

### Accessing Your Application

After successful deployment, your app will be available at:

```
http://your-webops-server:PORT
```

Or with custom domain:

```
https://your-domain.com
```

The port number is shown in the deployment details.

### Creating a Django superuser

From the securely authorized **application runtime** (not the WebOps CLI),
run Django's interactive `python manage.py createsuperuser` according to
your runtime's approved administrative procedure. Verify the application's
virtual environment and database selection, and use a unique credential
issued through your identity/secret-management process.

### Collecting Static Files

Confirm that the build pipeline ran `python manage.py collectstatic --noinput`
and that your reverse proxy serves the generated assets correctly. If it did
not, repair the project build/start configuration and rerun the approved
deployment job; `webops logs` only displays logs and does **not** execute
remote commands.

### Setting Up a Custom Domain

1. **Add domain in deployment settings**
2. **Update your DNS records:**
   ```
   A Record: myapp.example.com → your-webops-server-ip
   ```
3. **TLS certificate:** Configure the approved ingress/reverse proxy and
   certificate automation for your deployment. `webops ssl` is not a
   supported CLI command. Verify certificate chain and expiry against
   `https://myapp.example.com` from an external client.

---

## Troubleshooting

### Common Issues and Solutions

#### 1. ImportError: No module named 'X'

**Problem:** Missing dependency

**Solution:**
```bash
# Add to requirements.txt
echo "missing-package-name" >> requirements.txt
git add requirements.txt
git commit -m "Add missing dependency"
git push

# Redeploy
webops deploy yourusername/your-repo --name my-django-app --approve --wait
```

#### 2. DisallowedHost at /

**Problem:** Your domain is not in `ALLOWED_HOSTS`

**Solution:**
```bash
# Update environment variable
webops env:set my-django-app ALLOWED_HOSTS yourdomain.com,www.yourdomain.com

# Restart
webops restart my-django-app
```

#### 3. Static files not loading (404)

**Problem:** Static files not collected or misconfigured

**Solution:**
```bash
# Check your Django project settings and deployment logs.
# In settings.py:
# STATIC_URL = '/static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'
webops logs my-django-app --tail 100

# Run collectstatic via the authenticated application environment only
# after confirming the deployed app's documented execution procedure.
```

#### 4. Database connection refused

**Problem:** Database credentials incorrect

**Solution:**
```bash
# Inspect the database entry, using its actual database name
webops db:list
webops db:credentials myapp_db

# Rotate/update DATABASE_URL through an approved secret manager and
# deployment configuration, not as a plaintext command-line argument.
```

#### 5. Application not starting

**Problem:** Various errors in code or configuration

**Solution:**
```bash
# View application logs
webops logs my-django-app --tail 100

# Check service status
webops info my-django-app

# Restart the service
webops restart my-django-app
```

#### 6. Permission denied errors

**Problem:** File permissions

**Solution:**
```bash
# Diagnose permissions before making changes.
webops system doctor
# On the approved hosting server, an administrator may use:
# sudo webops admin fix-permissions
# Review the command's scope and host paths before running it.
```

### Viewing Logs

**Deployment logs:**
```bash
webops logs my-django-app --tail 100
```

**Application logs:**
```bash
webops logs my-django-app --tail 100
```

**Real-time logs:**
```bash
webops logs my-django-app --follow
```

### Getting Help

- **Documentation:** `/docs` on your WebOps instance
- **Server logs:** `/opt/webops/control-panel/logs/`
- **Application logs:** `/opt/webops/deployments/[app-name]/logs/`

---

## Best Practices

### 1. Use Environment Variables

Never hardcode sensitive data:

```python
# ❌ Bad
SECRET_KEY = 'my-secret-key-123'
DEBUG = True

# ✅ Good
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
```

### 2. Pin Your Dependencies

```txt
# ❌ Bad
Django
requests

# ✅ Good
Django==4.2.7
requests==2.31.0
```

### 3. Use `.env` for Local Development

Create `.env.example` in your repo:

```env
SECRET_KEY=change-me-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:pass@localhost/dbname
```

Don't commit `.env` - add it to `.gitignore`

### 4. Separate Settings for Production

**Option A: Environment-based settings**
```python
# settings.py
if os.environ.get('ENVIRONMENT') == 'production':
    from .settings_prod import *
```

**Option B: Django-environ**
```python
import environ
env = environ.Env()
```

### 5. Use WhiteNoise for Static Files

Simple and efficient:

```txt
# requirements.txt
whitenoise>=6.5
```

```python
# settings.py
MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ...
]
```

### 6. Enable HTTPS

Always use HTTPS in production:

```python
# settings.py (production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 7. Regular Backups

Backups and restore verification must be configured for the selected hosting
database and storage backend. The current CLI does **not** provide
`webops db:backup` or `webops db:download`; use an approved database
backup mechanism and prove that a restore works with disposable data.
Record retention, encryption, and recovery-point/recovery-time objectives.

---

## Example: Complete Django Project

Here's a minimal Django project structure ready for WebOps deployment:

```
my-django-app/
├── manage.py
├── requirements.txt
├── .gitignore
├── .env.example
├── myapp/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── app1/
│   ├── migrations/
│   ├── models.py
│   ├── views.py
│   └── urls.py
└── staticfiles/
    └── (generated by collectstatic)
```

**requirements.txt:**
```txt
Django==4.2.7
gunicorn==21.2.0
psycopg2-binary==2.9.9
whitenoise==6.6.0
django-environ==0.11.2
```

**settings.py:**
```python
import os
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app1',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'myapp.urls'

DATABASES = {
    'default': env.db('DATABASE_URL')
}

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

**.env.example:**
```env
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://user:password@localhost:5432/myapp
```

---

## Quick Reference

### Deployment Commands

```bash
# Deploy
webops deploy user/repo --name myapp --approve --wait

# Status
webops info myapp

# Logs
webops logs myapp --follow

# Restart
webops restart myapp

# Stop
webops stop myapp

# Delete
webops delete myapp

# Environment (do not pass sensitive values through process arguments)
webops env:show myapp
webops env:set myapp DEBUG false
webops env:unset myapp DEBUG

# Database (the argument is the database name)
webops db:list
webops db:credentials myapp_db

# For migration or shell access, follow the hosting runtime's
# approved application procedure; the CLI does not expose
# a general-purpose 'webops run' or 'webops shell' command.
```

---

## Next Steps

After deploying your application:

1. ✅ Create a superuser
2. ✅ Set up custom domain
3. ✅ Enable HTTPS/SSL
4. ✅ Configure email settings
5. ✅ Set up monitoring
6. ✅ Configure backups
7. ✅ Review security settings

---

**Need help?** Contact your WebOps administrator or check the documentation at `/docs`.

**Happy Deploying! 🚀**
