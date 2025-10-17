# WebOps Migration Guide

## Overview

This guide provides comprehensive instructions for migrating between different versions of WebOps, upgrading from legacy systems, and handling database schema changes. Follow these procedures to ensure smooth and successful migrations with minimal downtime.

## Version Migration

### WebOps 1.x to 2.x Migration

#### Pre-Migration Checklist

```bash
# Pre-migration validation script
#!/bin/bash

# Check current version
echo "Current WebOps version:"
python manage.py --version

# Check database compatibility
echo "Database compatibility check:"
python manage.py check --database default

# Verify backup existence
echo "Backup verification:"
if [ -f "/backups/latest-backup.sql.gz.enc" ]; then
    echo "✓ Latest backup exists"
else
    echo "✗ No recent backup found"
    exit 1
fi

# Check disk space
echo "Disk space check:"
df -h /var/lib/postgresql

# Verify dependencies
echo "Dependency compatibility:"
pip check

# Test current functionality
echo "Pre-migration smoke test:"
python manage.py test core.tests.SmokeTest --failfast
```

#### Migration Procedure

```python
# migration/version_upgrade.py
import subprocess
import time
from datetime import datetime

class VersionMigration:
    """WebOps version migration utilities."""
    
    def migrate_1x_to_2x(self):
        """Execute migration from WebOps 1.x to 2.x."""
        steps = [
            self.create_pre_migration_backup,
            self.install_new_dependencies,
            self.run_database_migrations,
            self.migrate_data_structures,
            self.update_configuration,
            self.run_post_migration_tests,
            self.verify_migration_success,
        ]
        
        return self.execute_migration_steps(steps)
    
    def create_pre_migration_backup(self):
        """Create comprehensive backup before migration."""
        backup_commands = [
            'python manage.py dumpdata --all --natural-foreign --natural-primary > pre_migration_backup.json',
            'pg_dump -h localhost -U webops webops | gzip > pre_migration_db_backup.sql.gz',
            'tar czf pre_migration_files_backup.tar.gz /app/media /app/static',
        ]
        
        for cmd in backup_commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Backup failed: {result.stderr}")
        
        return "Backup completed successfully"
    
    def install_new_dependencies(self):
        """Install new version dependencies."""
        commands = [
            'pip uninstall -y webops',
            'pip install webops>=2.0,<3.0',
            'pip install -r requirements.txt',
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Dependency installation failed: {result.stderr}")
        
        return "Dependencies installed successfully"
    
    def run_database_migrations(self):
        """Execute database schema migrations."""
        migration_commands = [
            'python manage.py makemigrations',
            'python manage.py migrate',
            'python manage.py migrate --database=analytics',
        ]
        
        for cmd in migration_commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Migration failed: {result.stderr}")
        
        return "Database migrations completed successfully"
    
    def migrate_data_structures(self):
        """Migrate data to new structures."""
        data_migration_scripts = [
            'python manage.py migrate_users',
            'python manage.py migrate_content',
            'python manage.py migrate_settings',
        ]
        
        for script in data_migration_scripts:
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Data migration failed: {result.stderr}")
        
        return "Data migration completed successfully"
    
    def execute_migration_steps(self, steps):
        """Execute migration steps with error handling."""
        results = {}
        
        for step in steps:
            try:
                start_time = time.time()
                result = step()
                duration = time.time() - start_time
                
                results[step.__name__] = {
                    'success': True,
                    'result': result,
                    'duration': duration
                }
                
            except Exception as e:
                results[step.__name__] = {
                    'success': False,
                    'error': str(e),
                    'duration': time.time() - start_time
                }
                # Stop migration on critical failure
                if self.is_critical_step(step):
                    break
        
        return results
```

#### Post-Migration Validation

```bash
# Post-migration validation script
#!/bin/bash

# Verify new version
echo "New WebOps version:"
python manage.py --version

# Check database integrity
echo "Database integrity check:"
python manage.py check --database default

# Run comprehensive tests
echo "Running post-migration tests:"
python manage.py test

# Verify all services
echo "Service status check:"
systemctl status webops.service
systemctl status webops-celery.service
systemctl status webops-beat.service

# Check application health
echo "Application health check:"
curl -f http://localhost:8000/health/
curl -f http://localhost:8000/api/health/

# Verify data consistency
echo "Data consistency check:"
python manage.py verify_data_consistency
```

### Database Migration Strategies

#### Zero-Downtime Migrations

```python
# migration/zero_downtime.py
from django.db import connection, connections
from contextlib import contextmanager
import time

class ZeroDowntimeMigration:
    """Zero-downtime database migration utilities."""
    
    @contextmanager
    def maintenance_mode(self, enable=True):
        """Context manager for maintenance mode."""
        if enable:
            self.enable_maintenance_mode()
        try:
            yield
        finally:
            if enable:
                self.disable_maintenance_mode()
    
    def enable_maintenance_mode(self):
        """Enable maintenance mode."""
        # Update maintenance mode flag in database
        # Redirect traffic to maintenance page
        # Drain connections gracefully
        pass
    
    def disable_maintenance_mode(self):
        """Disable maintenance mode."""
        # Clear maintenance mode flag
        # Restore normal traffic routing
        # Verify system health
        pass
    
    def migrate_large_tables(self, table_name, batch_size=1000):
        """Migrate large tables in batches."""
        with self.maintenance_mode(enable=False):
            # Get total row count
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                total_rows = cursor.fetchone()[0]
            
            # Process in batches
            for offset in range(0, total_rows, batch_size):
                self.migrate_batch(table_name, offset, batch_size)
                time.sleep(0.1)  # Prevent database overload
    
    def migrate_batch(self, table_name, offset, batch_size):
        """Migrate a single batch of records."""
        # Implement batch migration logic
        # Use efficient SQL queries
        # Handle conflicts and errors
        pass
```

#### Schema Migration Best Practices

```sql
-- Safe schema migration example
BEGIN;

-- Create new table with new schema
CREATE TABLE new_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    -- New columns
    display_name VARCHAR(255),
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Copy data from old table
INSERT INTO new_users (id, username, email, created_at, updated_at)
SELECT id, username, email, created, modified
FROM users;

-- Update sequences
SELECT setval('new_users_id_seq', (SELECT MAX(id) FROM new_users));

-- Create indexes
CREATE INDEX idx_new_users_email ON new_users(email);
CREATE INDEX idx_new_users_username ON new_users(username);

-- Verify data integrity
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM new_users;

-- Atomic switch
ALTER TABLE users RENAME TO old_users;
ALTER TABLE new_users RENAME TO users;

COMMIT;

-- Cleanup (after verification)
-- DROP TABLE old_users;
```

## Data Migration

### User Data Migration

```python
# migration/user_migration.py
from django.contrib.auth import get_user_model
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class UserDataMigration:
    """User data migration utilities."""
    
    def __init__(self):
        self.User = get_user_model()
    
    @transaction.atomic
    def migrate_user_profiles(self, batch_size=100):
        """Migrate user profiles to new structure."""
        users = self.User.objects.all()
        
        migrated_count = 0
        errors = []
        
        for user in users:
            try:
                self.migrate_single_user(user)
                migrated_count += 1
                
                if migrated_count % batch_size == 0:
                    logger.info(f"Migrated {migrated_count} users")
                    
            except Exception as e:
                errors.append({
                    'user_id': user.id,
                    'username': user.username,
                    'error': str(e)
                })
                logger.error(f"Failed to migrate user {user.username}: {e}")
        
        return {
            'migrated_count': migrated_count,
            'error_count': len(errors),
            'errors': errors
        }
    
    def migrate_single_user(self, user):
        """Migrate a single user's data."""
        # Create user profile if it doesn't exist
        if not hasattr(user, 'profile'):
            from accounts.models import UserProfile
            UserProfile.objects.create(user=user)
        
        # Migrate user preferences
        self.migrate_user_preferences(user)
        
        # Migrate user settings
        self.migrate_user_settings(user)
        
        # Update user permissions
        self.update_user_permissions(user)
        
        logger.debug(f"Successfully migrated user {user.username}")
    
    def migrate_user_preferences(self, user):
        """Migrate user preferences."""
        # Implement preference migration logic
        # Handle different preference formats
        pass
    
    def migrate_user_settings(self, user):
        """Migrate user settings."""
        # Implement settings migration logic
        # Convert old settings format to new format
        pass
```

### Content Migration

```python
# migration/content_migration.py
from django.db import transaction
from django.core.files.base import ContentFile
import os
import shutil

class ContentMigration:
    """Content migration utilities."""
    
    def migrate_media_files(self, source_dir, target_dir):
        """Migrate media files to new structure."""
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        
        migrated_files = []
        errors = []
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                source_path = os.path.join(root, file)
                relative_path = os.path.relpath(source_path, source_dir)
                target_path = os.path.join(target_dir, relative_path)
                
                # Create target directory if it doesn't exist
                target_file_dir = os.path.dirname(target_path)
                if not os.path.exists(target_file_dir):
                    os.makedirs(target_file_dir)
                
                try:
                    # Copy file with metadata preservation
                    shutil.copy2(source_path, target_path)
                    migrated_files.append(relative_path)
                    
                except Exception as e:
                    errors.append({
                        'file': relative_path,
                        'error': str(e)
                    })
        
        return {
            'migrated_files': migrated_files,
            'error_count': len(errors),
            'errors': errors
        }
    
    def migrate_database_content(self):
        """Migrate database content to new models."""
        migration_tasks = [
            self.migrate_blog_posts,
            self.migrate_pages,
            self.migrate_comments,
            self.migrate_categories,
        ]
        
        results = {}
        
        for task in migration_tasks:
            try:
                result = task()
                results[task.__name__] = {
                    'success': True,
                    'result': result
                }
            except Exception as e:
                results[task.__name__] = {
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    def migrate_blog_posts(self):
        """Migrate blog posts to new content model."""
        from legacy.models import LegacyPost
        from content.models import BlogPost
        
        migrated_count = 0
        
        for legacy_post in LegacyPost.objects.all():
            blog_post = BlogPost.objects.create(
                title=legacy_post.title,
                content=legacy_post.content,
                author=legacy_post.author,
                published_date=legacy_post.publish_date,
                status='published' if legacy_post.published else 'draft',
                # Map additional fields as needed
            )
            
            # Migrate categories
            self.migrate_post_categories(legacy_post, blog_post)
            
            # Migrate tags
            self.migrate_post_tags(legacy_post, blog_post)
            
            # Migrate comments
            self.migrate_post_comments(legacy_post, blog_post)
            
            migrated_count += 1
        
        return f"Migrated {migrated_count} blog posts"
```

## Configuration Migration

### Settings Migration

```python
# migration/settings_migration.py
import json
import yaml
from django.conf import settings
from django.core.cache import caches

class SettingsMigration:
    """Configuration settings migration."""
    
    def migrate_settings_file(self, old_settings_path, new_settings_path):
        """Migrate settings from old format to new format."""
        with open(old_settings_path, 'r') as f:
            old_settings = self.parse_settings_file(f.read())
        
        new_settings = self.convert_settings(old_settings)
        
        with open(new_settings_path, 'w') as f:
            self.write_settings_file(new_settings, f)
        
        return "Settings migrated successfully"
    
    def parse_settings_file(self, content):
        """Parse settings file based on format."""
        try:
            # Try JSON first
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                # Try YAML
                return yaml.safe_load(content)
            except yaml.YAMLError:
                # Try Python format (simplified)
                return self.parse_python_settings(content)
    
    def convert_settings(self, old_settings):
        """Convert old settings format to new format."""
        new_settings = {}
        
        # Map old setting names to new ones
        setting_mappings = {
            'DATABASE_URL': 'DATABASES.default',
            'REDIS_URL': 'CACHES.default.URL',
            'SECRET_KEY': 'SECRET_KEY',
            'DEBUG': 'DEBUG',
            'ALLOWED_HOSTS': 'ALLOWED_HOSTS',
        }
        
        for old_key, new_key in setting_mappings.items():
            if old_key in old_settings:
                self.set_nested_value(new_settings, new_key, old_settings[old_key])
        
        # Add new default settings
        new_settings.setdefault('SECURE_SSL_REDIRECT', True)
        new_settings.setdefault('SECURE_HSTS_SECONDS', 31536000)
        new_settings.setdefault('SESSION_COOKIE_SECURE', True)
        
        return new_settings
    
    def set_nested_value(self, obj, key_path, value):
        """Set nested value using dot notation."""
        keys = key_path.split('.')
        current = obj
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
```

### Environment Migration

```bash
# Environment migration script
#!/bin/bash

# Backup current environment
echo "Backing up current environment..."
env > environment_backup.txt

# Migrate environment variables
echo "Migrating environment variables..."

# Map old variables to new ones
declare -A env_mapping=(
    ["OLD_DB_URL"]="DATABASE_URL"
    ["LEGACY_REDIS_URL"]="REDIS_URL"
    ["APP_SECRET"]="SECRET_KEY"
    ["DEBUG_MODE"]="DEBUG"
)

for old_var in "${!env_mapping[@]}"; do
    new_var="${env_mapping[$old_var]}"
    if [ -n "${!old_var}" ]; then
        export "$new_var=${!old_var}"
        echo "Migrated $old_var to $new_var"
    fi
done

# Set new default values
export CELERY_BROKER_URL="${REDIS_URL}/0"
export CELERY_RESULT_BACKEND="${REDIS_URL}/1"

# Generate new .env file
echo "Generating new .env file..."
cat > .env << EOF
DATABASE_URL=${DATABASE_URL}
REDIS_URL=${REDIS_URL}
SECRET_KEY=${SECRET_KEY}
DEBUG=${DEBUG}
CELERY_BROKER_URL=${CELERY_BROKER_URL}
CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
ALLOWED_HOSTS=localhost,127.0.0.1,.example.com
EOF

echo "Environment migration completed!"
```

## Third-Party Service Migration

### Email Service Migration

```python
# migration/email_migration.py
import imaplib
import smtplib
import email
from email.mime.text import MIMEText

class EmailServiceMigration:
    """Email service migration utilities."""
    
    def migrate_emails(self, source_server, target_server, username, password):
        """Migrate emails between servers."""
        try:
            # Connect to source server
            source_conn = imaplib.IMAP4_SSL(source_server)
            source_conn.login(username, password)
            
            # Connect to target server
            target_conn = imaplib.IMAP4_SSL(target_server)
            target_conn.login(username, password)
            
            # Select all mailboxes
            source_conn.select('INBOX')
            
            # Search for all emails
            status, messages = source_conn.search(None, 'ALL')
            if status != 'OK':
                raise Exception("Failed to search emails")
            
            email_ids = messages[0].split()
            migrated_count = 0
            
            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = source_conn.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        continue
                    
                    # Parse email
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Upload to target server
                    self.upload_email(target_conn, email_message)
                    
                    migrated_count += 1
                    
                    if migrated_count % 100 == 0:
                        print(f"Migrated {migrated_count} emails")
                        
                except Exception as e:
                    print(f"Failed to migrate email {email_id}: {e}")
                    continue
            
            return f"Successfully migrated {migrated_count} emails"
            
        finally:
            # Clean up connections
            try:
                source_conn.close()
                source_conn.logout()
            except:
                pass
            try:
                target_conn.close()
                target_conn.logout()
            except:
                pass
    
    def upload_email(self, connection, email_message):
        """Upload email to target server."""
        # Convert email to string
        email_str = email_message.as_string()
        
        # Append to target mailbox
        connection.append('INBOX', None, None, email_str.encode())
```

### Storage Service Migration

```python
# migration/storage_migration.py
import boto3
from botocore.exceptions import ClientError
import os
from django.core.files.storage import default_storage

class StorageServiceMigration:
    """Cloud storage migration utilities."""
    
    def migrate_s3_buckets(self, source_bucket, target_bucket, 
                         source_credentials, target_credentials):
        """Migrate files between S3 buckets."""
        # Create S3 clients
        source_s3 = boto3.client(
            's3',
            aws_access_key_id=source_credentials['access_key'],
            aws_secret_access_key=source_credentials['secret_key'],
            region_name=source_credentials.get('region', 'us-east-1')
        )
        
        target_s3 = boto3.client(
            's3',
            aws_access_key_id=target_credentials['access_key'],
            aws_secret_access_key=target_credentials['secret_key'],
            region_name=target_credentials.get('region', 'us-east-1')
        )
        
        # List all objects in source bucket
        paginator = source_s3.get_paginator('list_objects_v2')
        migrated_count = 0
        errors = []
        
        for page in paginator.paginate(Bucket=source_bucket):
            for obj in page.get('Contents', []):
                try:
                    # Copy object to target bucket
                    copy_source = {'Bucket': source_bucket, 'Key': obj['Key']}
                    target_s3.copy_object(
                        Bucket=target_bucket,
                        Key=obj['Key'],
                        CopySource=copy_source
                    )
                    
                    migrated_count += 1
                    
                    if migrated_count % 100 == 0:
                        print(f"Migrated {migrated_count} files")
                        
                except ClientError as e:
                    errors.append({
                        'key': obj['Key'],
                        'error': str(e)
                    })
                    print(f"Failed to migrate {obj['Key']}: {e}")
        
        return {
            'migrated_count': migrated_count,
            'error_count': len(errors),
            'errors': errors
        }
```

## Rollback Procedures

### Migration Rollback

```python
# migration/rollback.py
import subprocess
import shutil
from datetime import datetime

class MigrationRollback:
    """Migration rollback utilities."""
    
    def __init__(self, backup_dir='/backups'):
        self.backup_dir = backup_dir
    
    def rollback_migration(self, migration_id):
        """Rollback a specific migration."""
        backup_path = f"{self.backup_dir}/migration_{migration_id}"
        
        if not os.path.exists(backup_path):
            raise Exception(f"Backup for migration {migration_id} not found")
        
        rollback_steps = [
            self.stop_services,
            self.restore_database,
            self.restore_files,
            self.revert_dependencies,
            self.start_services,
            self.verify_rollback,
        ]
        
        return self.execute_rollback_steps(rollback_steps, backup_path)
    
    def restore_database(self, backup_path):
        """Restore database from backup."""
        db_backup = f"{backup_path}/database_backup.sql"
        
        if os.path.exists(db_backup):
            # Restore PostgreSQL database
            restore_cmd = f"psql -h localhost -U webops webops < {db_backup}"
            result = subprocess.run(restore_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Database restore failed: {result.stderr}")
            
            return "Database restored successfully"
        
        return "No database backup found"
    
    def restore_files(self, backup_path):
        """Restore application files."""
        files_backup = f"{backup_path}/files_backup.tar.gz"
        
        if os.path.exists(files_backup):
            # Extract files backup
            extract_cmd = f"tar xzf {files_backup} -C /"
            result = subprocess.run(extract_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Files restore failed: {result.stderr}")
            
            return "Files restored successfully"
        
        return "No files backup found"
    
    def execute_rollback_steps(self, steps, backup_path):
        """Execute rollback steps."""
        results = {}
        
        for step in steps:
            try:
                result = step(backup_path)
                results[step.__name__] = {
                    'success': True,
                    'result': result
                }
            except Exception as e:
                results[step.__name__] = {
                    'success': False,
                    'error': str(e)
                }
                # Decide whether to continue rollback
                if self.is_critical_step(step):
                    break
        
        return results
```

### Emergency Rollback Script

```bash
#!/bin/bash
# emergency_rollback.sh

# Configuration
BACKUP_DIR="/backups"
MIGRATION_ID="$1"
SERVICES=("webops" "webops-celery" "webops-beat")

# Validate migration ID
if [ -z "$MIGRATION_ID" ]; then
    echo "Usage: $0 <migration_id>"
    exit 1
fi

# Check if backup exists
BACKUP_PATH="$BACKUP_DIR/migration_$MIGRATION_ID"
if [ ! -d "$BACKUP_PATH" ]; then
    echo "Error: Backup for migration $MIGRATION_ID not found"
    exit 1
fi

echo "Starting emergency rollback for migration $MIGRATION_ID"
echo "===================================================="

# Stop services
echo "Stopping services..."
for service in "${SERVICES[@]}"; do
    sudo systemctl stop "$service"
done

# Restore database
echo "Restoring database..."
DB_BACKUP="$BACKUP_PATH/database_backup.sql"
if [ -f "$DB_BACKUP" ]; then
    export PGPASSWORD="$DB_PASSWORD"
    psql -h localhost -U webops webops < "$DB_BACKUP"
    if [ $? -eq 0 ]; then
        echo "✓ Database restored successfully"
    else
        echo "✗ Database restore failed"
        exit 1
    fi
else
    echo "⚠ No database backup found"
fi

# Restore files
echo "Restoring files..."
FILES_BACKUP="$BACKUP_PATH/files_backup.tar.gz"
if [ -f "$FILES_BACKUP" ]; then
    tar xzf "$FILES_BACKUP" -C /
    if [ $? -eq 0 ]; then
        echo "✓ Files restored successfully"
    else
        echo "✗ Files restore failed"
        exit 1
    fi
else
    echo "⚠ No files backup found"
fi

# Start services
echo "Starting services..."
for service in "${SERVICES[@]}"; do
    sudo systemctl start "$service"
done

# Verify rollback
echo "Verifying rollback..."
sleep 5

# Check service status
for service in "${SERVICES[@]}"; do
    if sudo systemctl is-active --quiet "$service"; then
        echo "✓ Service $service is running"
    else
        echo "✗ Service $service is not running"
        exit 1
    fi
done

# Test application
echo "Testing application..."
if curl -f http://localhost:8000/health/ >/dev/null 2>&1; then
    echo "✓ Application health check passed"
else
    echo "✗ Application health check failed"
    exit 1
fi

echo ""
echo "Rollback completed successfully!"
echo "System has been restored to state before migration $MIGRATION_ID"
```

## Migration Monitoring and Logging

### Migration Progress Tracking

```python
# migration/monitoring.py
import time
import logging
from datetime import datetime
from django.db import connection

class MigrationMonitor:
    """Migration progress monitoring and logging."""
    
    def __init__(self, migration_id):
        self.migration_id = migration_id
        self.start_time = time.time()
        self.logger = logging.getLogger(f'migration.{migration_id}')
    
    def log_progress(self, step_name, current, total, additional_info=None):
        """Log migration progress."""
        elapsed = time.time() - self.start_time
        percentage = (current / total) * 100 if total > 0 else 0
        
        log_data = {
            'migration_id': self.migration_id,
            'step': step_name,
            'progress': {
                'current': current,
                'total': total,
                'percentage': round(percentage, 2)
            },
            'elapsed_time': round(elapsed, 2),
            'timestamp': datetime.now().isoformat(),
        }
        
        if additional_info:
            log_data['additional_info'] = additional_info
        
        self.logger.info(f"Migration progress: {step_name} - {current}/{total} ({percentage:.2f}%)", 
                        extra=log_data)
    
    def log_error(self, step_name, error, context=None):
        """Log migration error."""
        error_data = {
            'migration_id': self.migration_id,
            'step': step_name,
            'error': str(error),
            'timestamp': datetime.now().isoformat(),
        }
        
        if context:
            error_data['context'] = context
        
        self.logger.error(f"Migration error in {step_name}: {error}", extra=error_data)
    
    def log_completion(self, step_name, result):
        """Log migration step completion."""
        completion_data = {
            'migration_id': self.migration_id,
            'step': step_name,
            'result': result,
            'elapsed_time': round(time.time() - self.start_time, 2),
            'timestamp': datetime.now().isoformat(),
        }
        
        self.logger.info(f"Migration step completed: {step_name}", extra=completion_data)
    
    def get_performance_metrics(self):
        """Get migration performance metrics."""
        elapsed = time.time() - self.start_time
        
        # Get database performance metrics
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    SUM(xact_commit) as commits,
                    SUM(xact_rollback) as rollbacks,
                    SUM(blks_read) as blocks_read,
                    SUM(blks_hit) as blocks_hit
                FROM pg_stat_database 
                WHERE datname = current_database()
            """)
            db_stats = cursor.fetchone()
        
        return {
            'elapsed_time': round(elapsed, 2),
            'database_metrics': {
                'commits': db_stats[0] if db_stats else 0,
                'rollbacks': db_stats[1] if db_stats else 0,
                'blocks_read': db_stats[2] if db_stats else 0,
                'blocks_hit': db_stats[3] if db_stats else 0,
                'cache_hit_ratio': db_stats[3] / (db_stats[2] + db_stats[3]) if db_stats and (db_stats[2] + db_stats[3]) > 0 else 0
            }
        }

### Real-time Migration Dashboard

```python
# migration/dashboard.py
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
import json

@method_decorator(never_cache, name='dispatch')
class MigrationDashboardView(View):
    """Real-time migration progress dashboard."""
    
    def get(self, request, migration_id):
        """Get current migration status."""
        from .monitoring import MigrationMonitor
        
        monitor = MigrationMonitor(migration_id)
        
        status = {
            'migration_id': migration_id,
            'status': self.get_migration_status(migration_id),
            'progress': self.get_progress_percentage(migration_id),
            'metrics': monitor.get_performance_metrics(),
            'current_step': self.get_current_step(migration_id),
            'estimated_completion': self.get_estimated_completion(migration_id),
            'warnings': self.get_warnings(migration_id),
            'errors': self.get_errors(migration_id),
        }
        
        return JsonResponse(status)
    
    def get_migration_status(self, migration_id):
        """Get overall migration status."""
        # Implement status checking logic
        return 'in_progress'
    
    def get_progress_percentage(self, migration_id):
        """Get overall progress percentage."""
        # Implement progress calculation
        return 75.5
    
    def get_current_step(self, migration_id):
        """Get current migration step."""
        # Implement current step detection
        return 'data_migration'
    
    def get_estimated_completion(self, migration_id):
        """Get estimated completion time."""
        # Implement ETA calculation
        return '2024-01-15T14:30:00Z'
    
    def get_warnings(self, migration_id):
        """Get migration warnings."""
        # Implement warning collection
        return []
    
    def get_errors(self, migration_id):
        """Get migration errors."""
        # Implement error collection
        return []
```

## Migration Testing and Validation

### Pre-Migration Testing

```python
# migration/testing.py
from django.test import TestCase
from django.db import connections
import time

class MigrationTestCase(TestCase):
    """Comprehensive migration testing."""
    
    def test_migration_readiness(self):
        """Test if system is ready for migration."""
        # Test database connectivity
        for conn_name in connections:
            with self.subTest(connection=conn_name):
                conn = connections[conn_name]
                try:
                    conn.ensure_connection()
                    self.assertTrue(conn.is_usable())
                except Exception as e:
                    self.fail(f"Database {conn_name} not ready: {e}")
        
        # Test disk space
        self.assertGreater(self.get_free_disk_space('/'), 10 * 1024 * 1024 * 1024)  # 10GB
        
        # Test memory availability
        self.assertGreater(self.get_available_memory(), 2 * 1024 * 1024 * 1024)  # 2GB
        
        # Test network connectivity
        self.assertTrue(self.test_network_connectivity())
    
    def test_migration_performance(self):
        """Test migration performance characteristics."""
        # Test database write performance
        write_speed = self.measure_write_performance()
        self.assertGreater(write_speed, 1000)  # 1000 records/second
        
        # Test file copy performance
        copy_speed = self.measure_file_copy_performance()
        self.assertGreater(copy_speed, 50 * 1024 * 1024)  # 50 MB/s
        
        # Test network throughput
        network_speed = self.measure_network_throughput()
        self.assertGreater(network_speed, 100 * 1024 * 1024)  # 100 Mbps
    
    def get_free_disk_space(self, path):
        """Get free disk space in bytes."""
        import shutil
        return shutil.disk_usage(path).free
    
    def get_available_memory(self):
        """Get available memory in bytes."""
        import psutil
        return psutil.virtual_memory().available
    
    def test_network_connectivity(self):
        """Test network connectivity to essential services."""
        import socket
        
        test_hosts = [
            ('database', 5432),
            ('redis', 6379),
            ('api-service', 8000),
        ]
        
        for host, port in test_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result != 0:
                    return False
                    
            except socket.error:
                return False
        
        return True
```

### Post-Migration Validation

```python
# migration/validation.py
from django.db import transaction
from django.core.exceptions import ValidationError

class PostMigrationValidator:
    """Post-migration validation and verification."""
    
    def validate_migration(self):
        """Comprehensive post-migration validation."""
        validation_results = {
            'database_integrity': self.validate_database_integrity(),
            'data_consistency': self.validate_data_consistency(),
            'application_functionality': self.validate_application_functionality(),
            'performance_metrics': self.validate_performance_metrics(),
            'security_configuration': self.validate_security_configuration(),
        }
        
        # Check if any validation failed
        failed_validations = [
            key for key, result in validation_results.items() 
            if not result.get('success', False)
        ]
        
        return {
            'overall_success': len(failed_validations) == 0,
            'failed_validations': failed_validations,
            'details': validation_results
        }
    
    def validate_database_integrity(self):
        """Validate database integrity after migration."""
        try:
            # Check foreign key constraints
            self.check_foreign_keys()
            
            # Check unique constraints
            self.check_unique_constraints()
            
            # Check data types
            self.check_data_types()
            
            return {'success': True, 'message': 'Database integrity validated'}
            
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': 'Database integrity check failed'}
    
    def validate_data_consistency(self):
        """Validate data consistency between old and new systems."""
        try:
            # Compare record counts
            old_count = self.get_old_record_count()
            new_count = self.get_new_record_count()
            
            if old_count != new_count:
                raise ValidationError(f"Record count mismatch: old={old_count}, new={new_count}")
            
            # Sample data comparison
            sample_records = self.get_sample_records()
            for old_record, new_record in sample_records:
                if not self.records_match(old_record, new_record):
                    raise ValidationError("Sample record mismatch")
            
            return {'success': True, 'message': 'Data consistency validated'}
            
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': 'Data consistency check failed'}
    
    def validate_application_functionality(self):
        """Validate application functionality after migration."""
        test_cases = [
            self.test_user_authentication,
            self.test_data_retrieval,
            self.test_data_modification,
            self.test_api_endpoints,
            self.test_background_tasks,
        ]
        
        results = []
        
        for test_case in test_cases:
            try:
                result = test_case()
                results.append({
                    'test_case': test_case.__name__,
                    'success': True,
                    'result': result
                })
            except Exception as e:
                results.append({
                    'test_case': test_case.__name__,
                    'success': False,
                    'error': str(e)
                })
        
        failed_tests = [r for r in results if not r['success']]
        
        return {
            'success': len(failed_tests) == 0,
            'test_results': results,
            'failed_count': len(failed_tests)
        }
```

## Migration Automation

### Automated Migration Pipeline

```yaml
# .github/workflows/migration.yml
name: WebOps Migration Pipeline

on:
  workflow_dispatch:
    inputs:
      target_version:
        description: 'Target WebOps version'
        required: true
        type: string
      dry_run:
        description: 'Dry run (no changes)'
        required: false
        type: boolean
        default: false

jobs:
  pre-migration-checks:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run pre-migration tests
      run: python manage.py test migration.tests.MigrationTestCase
    
    - name: Generate migration plan
      run: python manage.py generate_migration_plan --version ${{ inputs.target_version }}
    
    - name: Upload migration plan
      uses: actions/upload-artifact@v3
      with:
        name: migration-plan
        path: migration_plan.json

  execute-migration:
    needs: pre-migration-checks
    if: ${{ !inputs.dry_run }}
    runs-on: ubuntu-latest
    steps:
    - name: Download migration plan
      uses: actions/download-artifact@v3
      with:
        name: migration-plan
    
    - name: Execute migration
      run: python manage.py execute_migration --plan migration_plan.json
    
    - name: Run post-migration validation
      run: python manage.py validate_migration
    
    - name: Deploy new version
      run: ./deploy.sh

  dry-run:
    needs: pre-migration-checks
    if: ${{ inputs.dry_run }}
    runs-on: ubuntu-latest
    steps:
    - name: Simulate migration
      run: python manage.py simulate_migration --plan migration_plan.json
    
    - name: Generate dry-run report
      run: python manage.py generate_migration_report --dry-run
    
    - name: Upload dry-run report
      uses: actions/upload-artifact@v3
      with:
        name: dry-run-report
        path: migration_report.html
```

### Migration Management Commands

```python
# management/commands/migrate_version.py
from django.core.management.base import BaseCommand
from django.conf import settings
import json

class Command(BaseCommand):
    """Manage WebOps version migrations."""
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--version',
            type=str,
            required=True,
            help='Target WebOps version'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate migration without making changes'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration despite warnings'
        )
    
    def handle(self, *args, **options):
        target_version = options['version']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(f"Starting migration to WebOps {target_version}")
        
        if dry_run:
            self.stdout.write("Running in dry-run mode (no changes will be made)")
        
        # Execute migration steps
        migration_steps = [
            self.backup_system,
            self.install_dependencies,
            self.migrate_database,
            self.migrate_data,
            self.update_configuration,
            self.verify_migration,
        ]
        
        results = {}
        
        for step in migration_steps:
            step_name = step.__name__
            self.stdout.write(f"Executing step: {step_name}")
            
            try:
                if dry_run:
                    result = f"DRY-RUN: Would execute {step_name}"
                else:
                    result = step(target_version, force)
                
                results[step_name] = {'success': True, 'result': result}
                self.stdout.write(self.style.SUCCESS(f"✓ {step_name} completed"))
                
            except Exception as e:
                results[step_name] = {'success': False, 'error': str(e)}
                self.stdout.write(self.style.ERROR(f"✗ {step_name} failed: {e}"))
                
                if not force:
                    self.stdout.write(self.style.ERROR("Migration aborted"))
                    break
        
        # Generate migration report
        self.generate_report(results, target_version, dry_run)
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run completed successfully"))
        else:
            successful_steps = sum(1 for r in results.values() if r['success'])
            total_steps = len(results)
            
            if successful_steps == total_steps:
                self.stdout.write(self.style.SUCCESS("Migration completed successfully!"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Migration completed with {total_steps - successful_steps} failures"
                ))
    
    def generate_report(self, results, target_version, dry_run):
        """Generate migration report."""
        report = {
            'migration_version': target_version,
            'dry_run': dry_run,
            'timestamp': self.get_current_timestamp(),
            'results': results,
            'summary': self.generate_summary(results),
        }
        
        report_path = f"migration_report_{target_version}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.stdout.write(f"Migration report saved to {report_path}")
    
    def generate_summary(self, results):
        """Generate migration summary."""
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        
        return {
            'total_steps': total,
            'successful_steps': successful,
            'failed_steps': total - successful,
            'success_rate': (successful / total) * 100 if total > 0 else 0,
        }
```

## Best Practices and Recommendations

### Migration Planning

1. **Thorough Testing**: Always test migrations in a staging environment first
2. **Comprehensive Backups**: Create complete backups before starting any migration
3. **Rollback Planning**: Have a well-defined rollback procedure ready
4. **Communication Plan**: Notify all stakeholders about migration schedule and potential downtime
5. **Monitoring Setup**: Implement real-time monitoring during migration

### Performance Optimization

1. **Batch Processing**: Process data in batches to avoid memory issues
2. **Index Management**: Create appropriate indexes for migration queries
3. **Connection Pooling**: Use connection pooling for database operations
4. **Parallel Processing**: Utilize parallel processing where possible
5. **Resource Monitoring**: Monitor system resources during migration

### Security Considerations

1. **Data Encryption**: Encrypt sensitive data during transfer and storage
2. **Access Control**: Implement proper access controls for migration tools
3. **Audit Logging**: Maintain comprehensive audit logs of all migration activities
4. **Data Validation**: Validate data integrity and security after migration
5. **Compliance**: Ensure migration processes comply with relevant regulations

## Troubleshooting

### Common Migration Issues

1. **Database Connection Issues**: Verify database credentials and network connectivity
2. **Permission Problems**: Check file and database permissions
3. **Disk Space Exhaustion**: Monitor disk space and clean up temporary files
4. **Memory Constraints**: Optimize memory usage and consider increasing resources
5. **Network Timeouts**: Adjust timeout settings and implement retry logic

### Debugging Techniques

1. **Verbose Logging**: Enable detailed logging for migration processes
2. **Progress Monitoring**: Implement real-time progress tracking
3. **Error Handling**: Create comprehensive error handling and reporting
4. **Performance Profiling**: Profile migration performance to identify bottlenecks
5. **Data Sampling**: Test migrations with sample data before full execution

## Support

For assistance with WebOps migrations, contact:

- **Documentation**: [WebOps Migration Guide](https://webops.example.com/docs/migration)
- **Support Team**: support@webops.example.com
- **Community Forum**: [WebOps Community](https://community.webops.example.com)
- **Emergency Support**: +1-555-MIGRATE (644-7283)

---

*This migration guide is part of WebOps documentation. Always refer to the latest version for the most current information and procedures.*