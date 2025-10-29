# WebOps Configuration Guide

## Overview

WebOps uses environment variables for all configuration, following the 12-factor app methodology. This document outlines all available configuration options, their defaults, and recommended values for different deployment environments.

## Configuration Philosophy

WebOps follows a security-first configuration approach:
- **Environment Variables Only**: All configuration via environment variables (no configuration files)
- **Security by Default**: Secure defaults for all sensitive options
- **Minimal Dependencies**: Configuration requires only the system environment
- **Zero npm Dependencies**: Pure HTML/CSS/JS frontend with no build tools

## Environment Variable Configuration

All WebOps configuration uses `python-decouple` for environment variable management:

```python
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='')
```

## Core Configuration

### Application Settings

```bash
# Django Settings
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# WebOps Settings
WEBOPS_ENV=production
WEBOPS_DOMAIN=your-domain.com
WEBOPS_PORT=8009
```

### Database Configuration

```bash
# PostgreSQL Configuration (Production)
DATABASE_URL=postgresql://username:password@localhost:5432/webops_db

# SQLite Configuration (Development)
DATABASE_URL=sqlite:///path/to/webops.db
```

### Security Configuration

```bash
# Encryption Settings
ENCRYPTION_KEY=your-32-character-encryption-key-here

# Session Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax

# CSRF Protection
CSRF_COOKIE_SECURE=True
CSRF_COOKIE_HTTPONLY=True

# CORS Settings
CORS_ALLOW_CREDENTIALS=True
CORS_ALLOWED_ORIGINS=https://your-domain.com
```

### Redis and Celery Configuration

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Celery Worker Settings
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=600
```

### File Storage Configuration

```bash
# Media and Static Files
MEDIA_ROOT=/var/www/webops/media
STATIC_ROOT=/var/www/webops/static
STATIC_URL=/static/

# Backup Storage
BACKUP_STORAGE_PATH=/var/backups/webops
MAX_BACKUP_RETENTION_DAYS=30
```

### Deployment Configuration

```bash
# Port Allocation Range
MIN_PORT=8000
MAX_PORT=9000

# Deployment Settings
DEPLOYMENT_TIMEOUT=1800
MAX_CONCURRENT_DEPLOYMENTS=5
DEPLOYMENT_RETRY_ATTEMPTS=3

# System User for Deployments
WEBOPS_USER=webops
WEBOPS_GROUP=webops
```

### SSL and HTTPS Configuration

```bash
# SSL Certificate Settings
SSL_CERT_PATH=/etc/ssl/certs/webops.crt
SSL_KEY_PATH=/etc/ssl/private/webops.key
SSL_CA_PATH=/etc/ssl/certs/ca-bundle.crt

# Let's Encrypt Integration
LETSENCRYPT_EMAIL=admin@your-domain.com
LETSENCRYPT_STAGING=False
```

### Monitoring and Logging

```bash
# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/webops/webops.log
LOG_MAX_SIZE=100MB
LOG_BACKUP_COUNT=5

# Health Check Settings
HEALTH_CHECK_TIMEOUT=30
MONITORING_INTERVAL=60
```

## Environment-Specific Configurations

### Development Environment

```bash
# Development Settings
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Development Database
DATABASE_URL=sqlite:///webops_dev.db

# Disable SSL for local development
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
CORS_ALLOW_CREDENTIALS=False

# Development Redis
REDIS_URL=redis://localhost:6379/1
```

### Staging Environment

```bash
# Staging Settings
WEBOPS_ENV=staging
DEBUG=False
SECRET_KEY=staging-secret-key-here
ALLOWED_HOSTS=staging.your-domain.com

# Staging Database
DATABASE_URL=postgresql://webops_staging:password@staging-db:5432/webops_staging

# Enable SSL
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CORS_ALLOW_CREDENTIALS=True
```

### Production Environment

```bash
# Production Settings
WEBOPS_ENV=production
DEBUG=False
SECRET_KEY=production-secret-key-256-chars-minimum
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Production Database
DATABASE_URL=postgresql://webops_prod:secure-password@prod-db:5432/webops_prod

# Enhanced Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Strict
CSRF_COOKIE_SECURE=True
CSRF_COOKIE_HTTPONLY=True

# Production Redis Cluster
REDIS_URL=redis://prod-redis-cluster:6379/0
```

## Security Configuration

### Content Security Policy

```bash
# CSP Settings
CSP_DEFAULT_SRC="'self'"
CSP_SCRIPT_SRC="'self' 'unsafe-inline'"
CSP_STYLE_SRC="'self' 'unsafe-inline'"
CSP_IMG_SRC="'self' data: https:"
CSP_FONT_SRC="'self'"
CSP_CONNECT_SRC="'self'"
```

### Rate Limiting

```bash
# Rate Limiting Settings
RATE_LIMIT_ENABLED=True
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000

# API Rate Limiting
API_RATE_LIMIT_PER_MINUTE=60
API_RATE_LIMIT_PER_HOUR=1000
```

### Authentication

```bash
# Authentication Settings
AUTH_TOKEN_EXPIRE_HOURS=24
MAX_LOGIN_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=30

# Password Policy
MIN_PASSWORD_LENGTH=12
REQUIRE_PASSWORD_COMPLEXITY=True
```

## Integration Configuration

### Git Integration

```bash
# Git Settings
GIT_TIMEOUT=300
GIT_MAX_CLONE_SIZE=500MB
GIT_SSL_VERIFY=True

# GitHub Integration
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# GitLab Integration
GITLAB_CLIENT_ID=your-gitlab-client-id
GITLAB_CLIENT_SECRET=your-gitlab-client-secret
```

### Email Configuration

```bash
# Email Settings
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.your-domain.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@your-domain.com
EMAIL_HOST_PASSWORD=your-email-password

# Notification Settings
NOTIFICATION_EMAIL_ENABLED=True
ADMIN_EMAIL=admin@your-domain.com
```

### Monitoring Integrations

```bash
# Sentry Configuration
SENTRY_DSN=your-sentry-dsn-here
SENTRY_ENVIRONMENT=production

# Health Check Endpoint
HEALTH_CHECK_ENDPOINT=/health/
METRICS_ENDPOINT=/metrics/
```

## CLI Configuration

### WebOps CLI Settings

```bash
# CLI Configuration
WEBOPS_CLI_TIMEOUT=30
WEBOPS_CLI_MAX_RETRIES=3
WEBOPS_CLI_API_URL=https://your-domain.com/api/v1/

# Interactive Wizard Settings
WIZARD_TIMEOUT=300
WIZARD_AUTO_COMPLETE=True
```

## Addon Configuration

### Addon System Settings

```bash
# Addon Configuration
ADDONS_PATH=/opt/webops/addons
ADDONS_ENABLED=True
ADDONS_AUTO_DISCOVERY=True
ADDONS_SECURITY_SANDBOX=True

# Addon Security
ADDONS_MAX_MEMORY_MB=512
ADDONS_MAX_CPU_PERCENT=50
ADDONS_ALLOWED_IMPORTS=json,urllib,datetime
```

## Backup and Recovery

### Backup Configuration

```bash
# Backup Settings
BACKUP_ENABLED=True
BACKUP_INTERVAL_HOURS=24
BACKUP_COMPRESSION=gzip
BACKUP_ENCRYPTION=True

# Database Backup
DB_BACKUP_RETENTION_DAYS=30
DB_BACKUP_ENCRYPTION_KEY=your-backup-encryption-key

# File Backup
FILE_BACKUP_PATHS=/var/www/webops/media,/etc/webops
FILE_BACKUP_EXCLUDE_PATHS=*.log,*.tmp,/cache
```

## Performance Configuration

### Application Performance

```bash
# Django Settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_TIMEOUT=300

# Static Files
STATICFILES_STORAGE=django.contrib.staticfiles.storage.StaticFilesStorage
CDN_URL=https://cdn.your-domain.com
```

### Worker Configuration

```bash
# Celery Performance
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_ACKS_LATE=True
CELERY_TASK_IGNORE_RESULT=False

# Task Timeouts
DEPLOYMENT_TASK_TIMEOUT=3600
BACKUP_TASK_TIMEOUT=1800
HEALTH_CHECK_TIMEOUT=30
```

## Environment Variable Management

### .env File Template

Create a `.env` file in your WebOps directory:

```bash
# Copy this template and customize for your environment
cp .env.template .env

# Edit the file with your specific settings
nano .env
```

### Environment Validation

```bash
# Validate configuration
python manage.py validate_config

# Check environment setup
python manage.py check --deploy

# Test database connection
python manage.py test_db_connection
```

### Security Considerations

1. **Never commit .env files to version control**
2. **Use strong, unique secrets for each environment**
3. **Rotate encryption keys regularly**
4. **Use environment-specific prefixes for staging/production**
5. **Validate all configuration on startup**

## Troubleshooting Configuration

### Common Issues

1. **Configuration not loading**
   - Check environment variable names match exactly
   - Verify .env file location and permissions
   - Restart application after configuration changes

2. **Database connection failures**
   - Verify DATABASE_URL format
   - Check database service status
   - Validate credentials

3. **SSL/TLS errors**
   - Verify certificate paths
   - Check file permissions
   - Validate domain names in ALLOWED_HOSTS

### Configuration Testing

```bash
# Test configuration
python manage.py shell -c "from django.conf import settings; print('Config OK')"

# Debug configuration
DEBUG=true python manage.py check --settings=config.settings.development

# Environment info
python manage.py environment_info
```

## Best Practices

### Configuration Management

1. **Use configuration templates for different environments**
2. **Document all environment variables**
3. **Use descriptive variable names**
4. **Implement configuration validation**
5. **Monitor configuration changes**

### Security Best Practices

1. **Use strong encryption keys**
2. **Enable all security features in production**
3. **Regular security audits**
4. **Monitor failed authentication attempts**
5. **Implement proper access controls**

### Performance Optimization

1. **Use connection pooling for databases**
2. **Configure appropriate timeouts**
3. **Optimize cache settings**
4. **Monitor resource usage**
5. **Scale worker processes appropriately**

---

**Last Updated**: October 2025  
**Version**: 2.0  
**Maintainer**: WebOps Development Team