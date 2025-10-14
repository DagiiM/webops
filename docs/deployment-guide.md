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
   pip install webops-cli
   ```

2. **Configure authentication:**
   ```bash
   webops login
   # Enter your WebOps server URL and credentials
   ```

3. **Deploy your application:**
   ```bash
   webops deploy \
     --name my-django-app \
     --repo https://github.com/yourusername/your-repo \
     --branch main \
     --env SECRET_KEY=your-secret-key \
     --env DEBUG=False \
     --env ALLOWED_HOSTS=myapp.example.com
   ```

4. **Check deployment status:**
   ```bash
   webops status my-django-app
   ```

5. **View logs:**
   ```bash
   webops logs my-django-app
   ```

### Method 3: Using the API

```bash
curl -X POST https://your-webops-server/api/deployments/ \
  -H "Authorization: Token your-api-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-django-app",
    "repo_url": "https://github.com/yourusername/your-repo",
    "branch": "main",
    "env_vars": {
      "SECRET_KEY": "your-secret-key",
      "DEBUG": "False",
      "ALLOWED_HOSTS": "myapp.example.com"
    }
  }'
```

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

### Automatic Database Creation

When you deploy a Django app, WebOps automatically:

1. ✅ Creates a PostgreSQL database
2. ✅ Generates secure credentials
3. ✅ Provides connection details via environment variables
4. ✅ Runs `python manage.py migrate`
5. ✅ Creates necessary tables

### Manual Database Operations

**Create superuser:**
```bash
webops run my-django-app "python manage.py createsuperuser"
```

**Run migrations:**
```bash
webops run my-django-app "python manage.py migrate"
```

**Load fixtures:**
```bash
webops run my-django-app "python manage.py loaddata initial_data.json"
```

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

### Creating a Superuser

**Via WebOps CLI:**
```bash
webops shell my-django-app
>>> from django.contrib.auth.models import User
>>> User.objects.create_superuser('admin', 'admin@example.com', 'password')
```

**Via SSH:**
```bash
ssh webops-server
cd /opt/webops/deployments/my-django-app/repo
source ../venv/bin/activate
python manage.py createsuperuser
```

### Collecting Static Files

WebOps runs `collectstatic` automatically, but you can run it manually:

```bash
webops run my-django-app "python manage.py collectstatic --noinput"
```

### Setting Up a Custom Domain

1. **Add domain in deployment settings**
2. **Update your DNS records:**
   ```
   A Record: myapp.example.com → your-webops-server-ip
   ```
3. **SSL Certificate** (automatic with Let's Encrypt):
   ```bash
   webops ssl my-django-app --domain myapp.example.com
   ```

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
webops deploy my-django-app
```

#### 2. DisallowedHost at /

**Problem:** Your domain is not in `ALLOWED_HOSTS`

**Solution:**
```bash
# Update environment variable
webops env:set my-django-app ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Restart
webops restart my-django-app
```

#### 3. Static files not loading (404)

**Problem:** Static files not collected or misconfigured

**Solution:**
```bash
# Manually collect static files
webops run my-django-app "python manage.py collectstatic --noinput"

# Check settings.py
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

#### 4. Database connection refused

**Problem:** Database credentials incorrect

**Solution:**
```bash
# View database credentials
webops db:info my-django-app

# Update DATABASE_URL
webops env:set my-django-app DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

#### 5. Application not starting

**Problem:** Various errors in code or configuration

**Solution:**
```bash
# View application logs
webops logs my-django-app --tail 100

# Check service status
webops status my-django-app

# Restart the service
webops restart my-django-app
```

#### 6. Permission denied errors

**Problem:** File permissions

**Solution:**
```bash
# Fix permissions (run on server)
sudo chown -R webops:webops /opt/webops/deployments/my-django-app
```

### Viewing Logs

**Deployment logs:**
```bash
webops logs my-django-app --deployment
```

**Application logs:**
```bash
webops logs my-django-app --app
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

WebOps handles automatic backups, but you can also:

```bash
# Manual backup
webops db:backup my-django-app

# Download backup
webops db:download my-django-app backup-2024-01-01.sql
```

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
webops deploy --name myapp --repo https://github.com/user/repo

# Status
webops status myapp

# Logs
webops logs myapp --follow

# Restart
webops restart myapp

# Stop
webops stop myapp

# Delete
webops delete myapp

# Environment
webops env:set myapp KEY=value
webops env:get myapp KEY
webops env:list myapp

# Database
webops db:info myapp
webops db:backup myapp
webops db:restore myapp backup.sql

# Shell
webops shell myapp
webops run myapp "python manage.py migrate"
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
