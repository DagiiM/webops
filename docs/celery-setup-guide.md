# Celery Setup and Management Guide

## Overview

This guide covers the complete setup, configuration, and management of Celery workers in the WebOps project. Celery is used for asynchronous task processing, particularly for deployment operations and health checks.

## Prerequisites

- Python 3.13+
- Django 5.2.6+
- Redis (as message broker)
- Virtual environment activated

## Installation and Configuration

### 1. Dependencies

The following packages are required and included in `requirements.txt`:
```
celery==5.3.4
redis==5.0.1
```

### 2. Celery Configuration

The Celery app is configured in `/control-panel/config/celery_app.py`:

```python
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('webops')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

### 3. Django Settings

Key Celery settings in `/control-panel/config/settings.py`:

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
```

## Celery Worker Management

### Using the Startup Script

A comprehensive startup script is provided at `/control-panel/start_celery.sh` with the following commands:

#### Start Celery Worker
```bash
./start_celery.sh start
```

#### Stop Celery Worker
```bash
./start_celery.sh stop
```

#### Restart Celery Worker
```bash
./start_celery.sh restart
```

#### Check Status
```bash
./start_celery.sh status
```

#### View Logs
```bash
./start_celery.sh logs
```

### Manual Commands

#### Start Worker Manually
```bash
cd $WEBOPS_DIR/control-panel
source venv/bin/activate
celery -A config worker --loglevel=info --concurrency=4 --detach --pidfile=/tmp/celery_webops.pid --logfile=/tmp/celery_webops.log
```

#### Monitor Worker
```bash
celery -A config inspect active
celery -A config inspect stats
```

#### Purge All Tasks
```bash
celery -A config purge
```

## Task Management

### Available Tasks

1. **deploy_application**: Handles application deployment
2. **run_all_health_checks**: Performs health checks on all deployments
3. **cleanup_old_deployments**: Removes old deployment artifacts

### Task Execution Examples

#### Queue a Deployment Task
```python
from apps.deployments.tasks import deploy_application
result = deploy_application.delay(deployment_id=1)
print(f"Task ID: {result.id}")
```

#### Check Task Status
```python
from celery.result import AsyncResult
result = AsyncResult('task-id-here')
print(f"Status: {result.status}")
print(f"Result: {result.result}")
```

#### Queue Health Checks
```python
from apps.deployments.tasks import run_all_health_checks
result = run_all_health_checks.delay()
```

## Monitoring and Debugging

### Log Files

- **Celery Worker Logs**: `/tmp/celery_webops.log`
- **PID File**: `/tmp/celery_webops.pid`

### Common Commands

#### View Real-time Logs
```bash
tail -f /tmp/celery_webops.log
```

#### Check Worker Process
```bash
ps aux | grep celery
```

#### Monitor Redis Connection
```bash
redis-cli ping
redis-cli monitor
```

### Debugging Failed Tasks

1. Check the task result for error details:
```python
from celery.result import AsyncResult
result = AsyncResult('failed-task-id')
print(result.traceback)
```

2. Review worker logs for detailed error messages
3. Verify Redis connectivity
4. Check Django settings configuration

## Troubleshooting

### Common Issues

#### 1. Worker Won't Start
- **Symptom**: `./start_celery.sh start` fails
- **Solutions**:
  - Check if Redis is running: `redis-cli ping`
  - Verify virtual environment is activated
  - Check for existing PID file: `rm /tmp/celery_webops.pid`
  - Review log file: `cat /tmp/celery_webops.log`

#### 2. Tasks Stuck in PENDING
- **Symptom**: Tasks never execute
- **Solutions**:
  - Verify worker is running: `./start_celery.sh status`
  - Check Redis connection
  - Restart worker: `./start_celery.sh restart`

#### 3. Import Errors
- **Symptom**: Tasks fail with import errors
- **Solutions**:
  - Ensure Django settings are properly configured
  - Verify all dependencies are installed
  - Check PYTHONPATH includes project directory

#### 4. Memory Issues
- **Symptom**: Worker crashes or becomes unresponsive
- **Solutions**:
  - Reduce concurrency: Modify `CONCURRENCY` in startup script
  - Monitor system resources: `htop`
  - Restart worker regularly in production

### Performance Optimization

1. **Concurrency**: Adjust based on CPU cores and workload
2. **Task Time Limits**: Set appropriate soft and hard time limits
3. **Result Backend**: Consider using database for persistent results
4. **Monitoring**: Implement Flower for web-based monitoring

## Production Deployment

### Systemd Service (Recommended)

Create `/etc/systemd/system/celery-webops.service`:

```ini
[Unit]
Description=Celery Worker for WebOps
After=network.target redis.service

[Service]
Type=forking
User=douglas
Group=douglas
WorkingDirectory=$WEBOPS_DIR/control-panel
Environment=PATH=$WEBOPS_DIR/control-panel/venv/bin
ExecStart=$WEBOPS_DIR/control-panel/start_celery.sh start
ExecStop=$WEBOPS_DIR/control-panel/start_celery.sh stop
ExecReload=$WEBOPS_DIR/control-panel/start_celery.sh restart
PIDFile=/tmp/celery_webops.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable celery-webops
sudo systemctl start celery-webops
```

### Security Considerations

1. **User Permissions**: Run worker as non-root user
2. **File Permissions**: Secure log and PID files
3. **Network Security**: Secure Redis instance
4. **Resource Limits**: Set appropriate ulimits

## Testing

### Verify Installation
```bash
# Test basic functionality
python manage.py shell -c "
from apps.deployments.tasks import run_all_health_checks
result = run_all_health_checks.delay()
print(f'Task queued: {result.id}')
"

# Check task completion
python manage.py shell -c "
from celery.result import AsyncResult
result = AsyncResult('task-id-from-above')
print(f'Status: {result.status}')
print(f'Result: {result.result}')
"
```

### Load Testing
```python
# Queue multiple tasks
for i in range(10):
    result = run_all_health_checks.delay()
    print(f"Task {i}: {result.id}")
```

## Maintenance

### Regular Tasks

1. **Log Rotation**: Implement logrotate for `/tmp/celery_webops.log`
2. **Monitoring**: Check worker health daily
3. **Updates**: Keep Celery and Redis updated
4. **Cleanup**: Purge old task results periodically

### Backup Considerations

- Redis data (if using persistent results)
- Configuration files
- Log files (for debugging historical issues)

## Support

For issues or questions:
1. Check this documentation
2. Review log files
3. Consult Celery official documentation
4. Contact: support@ifinsta.com

---

**Last Updated**: $(date)
**Version**: 1.0
**Author**: Douglas Mutethia, Eleso Solutions