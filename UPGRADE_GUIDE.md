# Service Control System - Upgrade Guide

## Overview

This guide helps you upgrade an existing WebOps installation to include the new service control system features.

## Prerequisites

- Existing WebOps installation (v1.0.3 or later)
- Database backup recommended
- Celery workers access
- Admin/superuser credentials

## Upgrade Steps

### Step 1: Backup Your Data

```bash
# Backup database
cd control-panel
python manage.py dumpdata > backup_$(date +%Y%m%d).json

# Backup configuration
cp .env .env.backup
```

### Step 2: Pull Latest Code

```bash
cd /path/to/webops
git pull origin main
```

### Step 3: Update Dependencies

```bash
cd control-panel
source venv/bin/activate
pip install -r requirements.txt
```

No new dependencies are required - all functionality uses existing packages.

### Step 4: Run Database Migrations

```bash
# Check for new migrations
python manage.py showmigrations services

# Run migrations
python manage.py makemigrations services
python manage.py migrate services

# Verify migration success
python manage.py showmigrations services
```

Expected output:
```
services
 [X] 0001_initial
 [X] 0002_restart_policy
```

### Step 5: Initialize Configuration

```python
python manage.py shell

>>> from apps.services.config_manager import config_manager
>>> # Initialize with defaults
>>> config = config_manager.get_all()
>>> print(f"Loaded {len(config)} configuration values")
>>> exit()
```

### Step 6: Restart Celery Workers

```bash
# Stop existing workers
pkill -f "celery worker"
pkill -f "celery beat"

# Start with new schedule
./start_celery.sh

# Verify workers started
ps aux | grep celery
```

You should see:
- Celery worker processes
- Celery beat scheduler
- New periodic tasks in beat schedule

### Step 7: Verify Installation

```bash
python manage.py shell

>>> from apps.services.service_controller import service_controller
>>> # Check system health
>>> health = service_controller.check_system_health()
>>> print(f"System healthy: {health['healthy']}")
>>>
>>> # Check Celery
>>> celery_status = service_controller.check_celery_workers()
>>> print(f"Workers: {celery_status['worker_count']}, Beat: {celery_status['beat_running']}")
>>> exit()
```

### Step 8: Access New Features

Open your browser and navigate to:

1. **Service Control Dashboard**
   - URL: `http://your-server:8000/services/control/`
   - Verify all deployments are listed
   - Test start/stop/restart buttons

2. **Restart Policies**
   - URL: `http://your-server:8000/services/restart-policies/`
   - Create a policy for one deployment
   - Verify it appears in the list

3. **Configuration Management**
   - URL: `http://your-server:8000/services/configuration/`
   - Review default configuration
   - Adjust thresholds if needed

4. **Celery Management**
   - URL: `http://your-server:8000/services/celery/`
   - Verify worker status
   - Check beat scheduler

5. **Django Admin**
   - URL: `http://your-server:8000/admin/services/`
   - Browse new models
   - Check that data is being collected

### Step 9: Configure Restart Policies (Optional)

For critical services, set up restart policies:

```python
python manage.py shell

>>> from apps.deployments.models import Deployment
>>> from apps.services.restart_policy import RestartPolicy
>>>
>>> # Get your critical deployment
>>> deployment = Deployment.objects.get(name='your-critical-service')
>>>
>>> # Create restart policy
>>> policy = RestartPolicy.objects.create(
...     deployment=deployment,
...     policy_type=RestartPolicy.PolicyType.BACKOFF,
...     enabled=True,
...     max_restarts=5,
...     time_window_minutes=30,
...     initial_delay_seconds=10,
...     max_delay_seconds=300,
...     backoff_multiplier=2.0,
...     cooldown_minutes=10,
...     require_health_check=True,
...     health_check_retries=3,
...     notify_on_restart=True,
...     notify_on_max_restarts=True
... )
>>> print(f"Created restart policy for {deployment.name}")
>>> exit()
```

### Step 10: Customize Configuration (Optional)

Adjust monitoring intervals and thresholds:

```python
python manage.py shell

>>> from apps.services.config_manager import config_manager
>>>
>>> # Adjust monitoring intervals (in seconds)
>>> config_manager.set('monitoring.metrics_interval', 300)  # 5 minutes
>>> config_manager.set('monitoring.health_check_interval', 120)  # 2 minutes
>>>
>>> # Adjust alert thresholds (percentages)
>>> config_manager.set('monitoring.alert_threshold_cpu', 85.0)
>>> config_manager.set('monitoring.alert_threshold_memory', 90.0)
>>> config_manager.set('monitoring.alert_threshold_disk', 90.0)
>>>
>>> # Adjust data retention (days)
>>> config_manager.set('data_retention.metrics_days', 14)
>>> config_manager.set('data_retention.logs_days', 30)
>>>
>>> # Verify changes
>>> print(config_manager.get_all())
>>> exit()
```

## Post-Upgrade Verification

### Check Background Tasks

Wait 5-10 minutes, then verify tasks are running:

```bash
python manage.py shell

>>> from apps.services.models import ResourceUsage, ServiceStatus
>>> from django.utils import timezone
>>> from datetime import timedelta
>>>
>>> # Check if metrics are being collected
>>> recent_metrics = ResourceUsage.objects.filter(
...     created_at__gte=timezone.now() - timedelta(minutes=10)
... )
>>> print(f"Recent metrics: {recent_metrics.count()}")
>>>
>>> # Check if service statuses are being updated
>>> recent_statuses = ServiceStatus.objects.filter(
...     last_checked__gte=timezone.now() - timedelta(minutes=10)
... )
>>> print(f"Recent status checks: {recent_statuses.count()}")
>>> exit()
```

Expected:
- At least 1-2 metric records (collected every 5 min)
- Service status records for your deployments (checked every 2 min)

### Check Celery Beat Schedule

```bash
python manage.py shell

>>> from config.celery_app import app
>>>
>>> print("Celery Beat Schedule:")
>>> for task_name, config in app.conf.beat_schedule.items():
...     schedule = config['schedule']
...     if isinstance(schedule, (int, float)):
...         schedule_str = f"{schedule}s"
...     else:
...         schedule_str = str(schedule)
...     print(f"  {task_name}: {schedule_str}")
>>> exit()
```

You should see:
- `collect-system-metrics-every-5-minutes: 300.0s`
- `check-service-statuses-every-2-minutes: 120.0s`
- `perform-health-checks-every-5-minutes: 300.0s`
- `auto-recover-failed-services-every-5-minutes: 300.0s`
- And more...

### Check Logs

```bash
# Check application logs for errors
tail -50 control-panel/logs/webops.log

# Check Celery worker logs
tail -50 control-panel/logs/celery-worker.log

# Check Celery beat logs
tail -50 control-panel/logs/celery-beat.log
```

Look for:
- ✅ No ERROR messages
- ✅ "Collected metrics" messages every 5 minutes
- ✅ "Service status check" messages every 2 minutes
- ✅ "Health checks completed" messages every 5 minutes

## Rollback Procedure

If you encounter issues and need to rollback:

### Step 1: Stop Celery
```bash
pkill -f "celery worker"
pkill -f "celery beat"
```

### Step 2: Restore Code
```bash
git checkout v1.0.3  # Or your previous version
```

### Step 3: Rollback Database
```bash
cd control-panel
python manage.py migrate services 0001_initial
```

### Step 4: Restore Configuration
```bash
cp .env.backup .env
```

### Step 5: Start Celery
```bash
./start_celery.sh
```

### Step 6: Restore Data (if needed)
```bash
python manage.py loaddata backup_YYYYMMDD.json
```

## Troubleshooting

### Issue: Migrations Fail

**Symptom**: `django.db.utils.OperationalError`

**Solution**:
```bash
# Check database connection
python manage.py dbshell

# Try running migrations with --fake-initial
python manage.py migrate services --fake-initial

# If still failing, check for conflicting migrations
python manage.py showmigrations
```

### Issue: Celery Tasks Not Running

**Symptom**: No metrics being collected

**Solution**:
```bash
# Verify Celery is running
ps aux | grep celery

# Check Celery logs for errors
tail -100 control-panel/logs/celery-worker.log

# Verify Redis is running
redis-cli ping

# Restart Celery
pkill -f celery
./start_celery.sh
```

### Issue: Configuration Not Saving

**Symptom**: Changes don't persist

**Solution**:
```python
# Check database connection
from apps.core.models import Configuration
print(Configuration.objects.count())

# Clear cache
from django.core.cache import cache
cache.clear()

# Try setting again
from apps.services.config_manager import config_manager
config_manager.set('monitoring.metrics_interval', 300)
```

### Issue: Services Not Auto-Restarting

**Symptom**: Failed services stay failed

**Solution**:
```python
# Check if policies exist
from apps.services.restart_policy import RestartPolicy
policies = RestartPolicy.objects.filter(enabled=True)
print(f"Active policies: {policies.count()}")

# Check if auto-recovery task is running
from apps.services.tasks import auto_recover_failed_services
result = auto_recover_failed_services.delay()
print(result.get())
```

### Issue: "Table doesn't exist" Error

**Symptom**: `django.db.utils.OperationalError: no such table: restart_policies`

**Solution**:
```bash
# Run migrations
python manage.py migrate services

# If that fails, create tables manually
python manage.py migrate services --run-syncdb
```

## Configuration Reference

### Recommended Settings for Different Environments

#### Development
```python
config_manager.set('monitoring.metrics_interval', 60)  # 1 minute
config_manager.set('monitoring.health_check_interval', 30)  # 30 seconds
config_manager.set('data_retention.metrics_days', 3)
```

#### Staging
```python
config_manager.set('monitoring.metrics_interval', 180)  # 3 minutes
config_manager.set('monitoring.health_check_interval', 60)  # 1 minute
config_manager.set('data_retention.metrics_days', 7)
```

#### Production
```python
config_manager.set('monitoring.metrics_interval', 300)  # 5 minutes
config_manager.set('monitoring.health_check_interval', 120)  # 2 minutes
config_manager.set('monitoring.alert_threshold_cpu', 85.0)
config_manager.set('monitoring.alert_threshold_memory', 90.0)
config_manager.set('data_retention.metrics_days', 14)
config_manager.set('data_retention.logs_days', 30)
```

## Performance Impact

The service control system is designed to have minimal performance impact:

- **CPU**: < 1% average (monitoring tasks)
- **Memory**: ~50-100 MB (cached configuration + task workers)
- **Disk I/O**: Minimal (periodic database writes)
- **Network**: Negligible (local health checks only)

### Resource Usage Over Time

- **Database Growth**: ~10-50 MB per day (metrics + logs)
- **Cleanup**: Automatic daily cleanup prevents unbounded growth
- **Queries**: Indexed for efficiency, minimal impact

## Support

If you encounter issues during upgrade:

1. **Check Logs**: Look for error messages in logs
2. **Documentation**: Review SERVICE_CONTROL_README.md
3. **Django Admin**: Browse /admin/services/ for data
4. **GitHub Issues**: Report at https://github.com/DagiiM/webops/issues

## Additional Resources

- **User Guide**: `SERVICE_CONTROL_README.md`
- **Implementation Details**: `SERVICE_CONTROL_IMPLEMENTATION.md`
- **Quick Reference**: `SERVICES_SUMMARY.md`
- **This Guide**: `UPGRADE_GUIDE.md`

---

**Upgrade Status Checklist:**

- [ ] Database backed up
- [ ] Code pulled/updated
- [ ] Dependencies installed
- [ ] Migrations run successfully
- [ ] Configuration initialized
- [ ] Celery restarted
- [ ] Web interfaces accessible
- [ ] Background tasks running
- [ ] Restart policies configured (optional)
- [ ] Configuration customized (optional)
- [ ] Post-upgrade verification complete

Once all items are checked, your upgrade is complete!
