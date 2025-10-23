# WebOps Service Control System

## Overview

The Service Control System provides comprehensive, centralized management for all WebOps services including deployments, Celery workers, and system services. It features automated monitoring, health checks, restart policies, and configuration management.

## Architecture

### Core Components

1. **ServiceController** (`apps/services/service_controller.py`)
   - Centralized service management
   - Start/stop/restart operations
   - Health monitoring and auto-recovery
   - Celery worker management
   - System service status checks

2. **RestartPolicyEnforcer** (`apps/services/restart_policy.py`)
   - Policy-based automated restarts
   - Circuit breaker pattern
   - Exponential backoff
   - Cooldown periods
   - Restart attempt tracking

3. **ConfigurationManager** (`apps/services/config_manager.py`)
   - Database-backed configuration
   - Type-safe access with validation
   - Caching for performance
   - Import/export capabilities

4. **Background Tasks** (`apps/services/tasks.py`)
   - Periodic health checks
   - Resource monitoring
   - Automated recovery
   - Data cleanup
   - Daily reporting

## Features

### 1. Service Lifecycle Management

**Start/Stop/Restart Services:**
```python
from apps.services.service_controller import service_controller

# Start a service
result = service_controller.start_service(deployment)

# Stop a service
result = service_controller.stop_service(deployment)

# Restart a service
result = service_controller.restart_service(deployment)

# Get service status
status = service_controller.get_service_status(deployment)
```

**Bulk Operations:**
```python
# Start all stopped services
result = service_controller.start_all_services()

# Stop all running services
result = service_controller.stop_all_services()

# Restart all running services
result = service_controller.restart_all_services()
```

### 2. Health Monitoring

**Automatic Health Checks:**
- Systemd service status monitoring
- HTTP endpoint health checks
- Resource usage tracking (CPU, memory, disk)
- Celery worker health verification

**Health Check Configuration:**
```python
# Perform health checks with auto-restart
result = service_controller.perform_health_checks(auto_restart=True)

# Check overall system health
health = service_controller.check_system_health()
```

### 3. Restart Policies

**Policy Types:**
- `ALWAYS`: Always restart on any failure
- `ON_FAILURE`: Restart only on failure (default)
- `NEVER`: Never auto-restart
- `BACKOFF`: Exponential backoff with increasing delays

**Create Restart Policy:**
```python
from apps.services.restart_policy import RestartPolicy

policy = RestartPolicy.objects.create(
    deployment=deployment,
    policy_type=RestartPolicy.PolicyType.BACKOFF,
    max_restarts=3,
    time_window_minutes=15,
    initial_delay_seconds=10,
    max_delay_seconds=300,
    backoff_multiplier=2.0,
    cooldown_minutes=5
)
```

**Policy Enforcement:**
```python
from apps.services.restart_policy import restart_policy_enforcer

# Check if restart should occur
should_restart, reason = restart_policy_enforcer.should_restart(deployment)

# Calculate delay
delay = restart_policy_enforcer.calculate_restart_delay(deployment)

# Record attempt
restart_policy_enforcer.record_restart_attempt(
    deployment=deployment,
    success=True,
    delay_seconds=delay,
    reason="Service health check failed"
)
```

### 4. Configuration Management

**Get Configuration:**
```python
from apps.services.config_manager import config_manager

# Get single value
metrics_interval = config_manager.get('monitoring.metrics_interval')

# Get all configuration
all_config = config_manager.get_all()

# Get by category
monitoring_config = config_manager.get_by_category('monitoring')
```

**Set Configuration:**
```python
# Set value
config_manager.set('monitoring.metrics_interval', 300)

# Reset to default
config_manager.reset_to_default('monitoring.metrics_interval')

# Validate all
errors = config_manager.validate_all()
```

**Available Configuration Options:**

**Monitoring:**
- `monitoring.metrics_interval`: System metrics collection interval (seconds)
- `monitoring.health_check_interval`: Health check interval (seconds)
- `monitoring.alert_threshold_cpu`: CPU usage alert threshold (%)
- `monitoring.alert_threshold_memory`: Memory usage alert threshold (%)
- `monitoring.alert_threshold_disk`: Disk usage alert threshold (%)

**Restart Policies:**
- `restart_policy.default_max_restarts`: Default maximum restart attempts
- `restart_policy.default_time_window`: Default time window (minutes)
- `restart_policy.default_cooldown`: Default cooldown period (minutes)

**Celery:**
- `celery.min_workers`: Minimum number of workers
- `celery.auto_restart_workers`: Auto-restart failed workers
- `celery.worker_health_check_interval`: Worker health check interval

**Data Retention:**
- `data_retention.metrics_days`: Days to retain metrics
- `data_retention.logs_days`: Days to retain logs
- `data_retention.health_checks_days`: Days to retain health checks

### 5. Celery Worker Management

**Check Worker Status:**
```python
status = service_controller.check_celery_workers()
# Returns: worker_count, workers details, beat_running status
```

**Restart Workers:**
```python
result = service_controller.restart_celery_workers()
```

## Web Interface

### Service Control Dashboard

Access at `/services/control/`

Features:
- Real-time service status for all deployments
- Start/stop/restart buttons for individual services
- Bulk operations (start/stop/restart all)
- System health overview
- Celery worker status

### Restart Policy Management

Access at `/services/restart-policies/`

Features:
- List all restart policies
- View restart statistics
- Edit policy configuration
- Create new policies

### Configuration Management

Access at `/services/configuration/`

Features:
- View all configuration by category
- Edit configuration values with validation
- Reset to defaults
- Export/import configuration

### Celery Management

Access at `/services/celery/`

Features:
- Worker status and details
- Restart workers
- Beat scheduler status

## API Endpoints

### Service Control API

```bash
# Get service status
GET /services/api/service/{deployment_id}/status/

# Get system health
GET /services/api/system/health/

# Get Celery status
GET /services/api/celery/status/

# Get all configuration
GET /services/api/configuration/
```

### Service Operations

```bash
# Start service
POST /services/control/{deployment_id}/start/

# Stop service
POST /services/control/{deployment_id}/stop/

# Restart service
POST /services/control/{deployment_id}/restart/

# Bulk operations
POST /services/control/bulk/start/
POST /services/control/bulk/stop/
POST /services/control/bulk/restart/
```

## Background Tasks (Celery Beat Schedule)

Automated tasks run periodically:

**Every 2 minutes:**
- `check_all_service_statuses`: Check status of all services

**Every 5 minutes:**
- `collect_system_metrics`: Collect resource metrics
- `perform_health_checks`: Perform HTTP health checks
- `auto_recover_failed_services`: Auto-recover based on policies

**Every 10 minutes:**
- `check_celery_health`: Check Celery worker health
- `check_system_services`: Check Nginx, PostgreSQL, Redis

**Daily (3 AM):**
- `cleanup_old_monitoring_data`: Clean up old metrics data

**Daily (12:05 AM):**
- `generate_daily_report`: Generate daily statistics report

## Configuration via Environment Variables

Add to `.env`:

```bash
# Monitoring intervals (seconds)
MONITORING_METRICS_INTERVAL=300
MONITORING_HEALTH_CHECK_INTERVAL=120

# Alert thresholds
ALERT_THRESHOLD_CPU=80.0
ALERT_THRESHOLD_MEMORY=85.0
ALERT_THRESHOLD_DISK=90.0

# Celery workers
CELERY_MIN_WORKERS=2
CELERY_AUTO_RESTART=True

# Data retention (days)
DATA_RETENTION_METRICS=7
DATA_RETENTION_LOGS=30
```

## Database Models

### RestartPolicy
Stores restart policy configuration for each deployment.

### RestartAttempt
Tracks all restart attempts with timing, result, and reason.

### ServiceStatus
Current status of each deployed service (running, stopped, failed).

### ResourceUsage
Historical system resource metrics (CPU, memory, disk).

### Alert
System alerts for threshold violations and service failures.

### HealthCheck
HTTP health check results for deployments.

## Django Admin

All models are registered in Django admin with enhanced interfaces:

- **ServiceStatus**: View service status with color-coded badges
- **ResourceUsage**: Browse historical resource usage
- **Alert**: Manage and acknowledge alerts with bulk actions
- **HealthCheck**: Review health check history
- **RestartPolicy**: Configure restart policies
- **RestartAttempt**: Audit restart attempt history

Access admin at `/admin/services/`

## Usage Examples

### Example 1: Create Restart Policy for Critical Service

```python
from apps.deployments.models import Deployment
from apps.services.restart_policy import RestartPolicy

# Get deployment
deployment = ApplicationDeployment.objects.get(name='critical-api')

# Create aggressive restart policy
policy = RestartPolicy.objects.create(
    deployment=deployment,
    policy_type=RestartPolicy.PolicyType.BACKOFF,
    enabled=True,
    max_restarts=5,  # More attempts
    time_window_minutes=30,  # Longer window
    initial_delay_seconds=5,  # Quick first retry
    max_delay_seconds=180,  # Cap at 3 minutes
    backoff_multiplier=1.5,  # Slower backoff
    require_health_check=True,
    health_check_retries=2,
    notify_on_restart=True,
    notify_on_max_restarts=True
)
```

### Example 2: Manual Service Recovery

```python
from apps.services.service_controller import service_controller
from apps.deployments.models import Deployment

# Get failed deployments
failed = ApplicationDeployment.objects.filter(status=ApplicationDeployment.Status.FAILED)

for deployment in failed:
    print(f"Recovering {deployment.name}...")
    result = service_controller.restart_service(deployment)

    if result['success']:
        print(f"✓ {deployment.name} restarted successfully")
    else:
        print(f"✗ Failed to restart {deployment.name}: {result['error']}")
```

### Example 3: Custom Configuration

```python
from apps.services.config_manager import config_manager

# Adjust monitoring for high-traffic period
config_manager.set('monitoring.metrics_interval', 60)  # Every minute
config_manager.set('monitoring.health_check_interval', 30)  # Every 30 seconds

# Increase alert thresholds
config_manager.set('monitoring.alert_threshold_cpu', 90.0)
config_manager.set('monitoring.alert_threshold_memory', 90.0)

# After high-traffic period, reset
config_manager.reset_to_default('monitoring.metrics_interval')
config_manager.reset_to_default('monitoring.health_check_interval')
```

## Monitoring and Troubleshooting

### Check System Health

```bash
# Via API
curl http://localhost:8000/services/api/system/health/

# Via Django shell
python manage.py shell
>>> from apps.services.service_controller import service_controller
>>> health = service_controller.check_system_health()
>>> print(health)
```

### View Restart Statistics

```python
from apps.services.restart_policy import restart_policy_enforcer

stats = restart_policy_enforcer.get_restart_statistics(
    deployment=deployment,
    hours=24
)
# Returns: total_attempts, successful, failed, success_rate
```

### Check Celery Workers

```bash
# Via management command
python manage.py shell
>>> from apps.services.service_controller import service_controller
>>> status = service_controller.check_celery_workers()
>>> print(f"Workers: {status['worker_count']}, Beat: {status['beat_running']}")
```

## Security Considerations

1. **Authentication Required**: All endpoints require login
2. **Permissions**: Service control operations require staff/superuser
3. **Audit Trail**: All service operations logged
4. **Rate Limiting**: API endpoints are rate-limited
5. **Input Validation**: All configuration values validated against schema

## Performance Optimization

1. **Caching**: Configuration values cached for 5 minutes
2. **Batch Operations**: Bulk service operations processed efficiently
3. **Background Tasks**: Long-running operations queued via Celery
4. **Database Indexes**: Optimized queries with proper indexes
5. **Data Cleanup**: Automatic cleanup of old monitoring data

## Future Enhancements

- [ ] Service dependency management
- [ ] Rolling restart support
- [ ] Custom health check endpoints per deployment
- [ ] Slack/email notifications for alerts
- [ ] Grafana dashboard integration
- [ ] Service metrics export (Prometheus)
- [ ] Multi-region support
- [ ] Load balancer integration

## Support

For issues or questions:
- Check logs: `tail -f control-panel/logs/webops.log`
- Review Celery logs: `journalctl -u webops-celery`
- Django admin: `/admin/services/`
- GitHub Issues: https://github.com/DagiiM/webops/issues
