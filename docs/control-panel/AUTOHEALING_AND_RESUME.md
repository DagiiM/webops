# Autohealing and Resume Capabilities

This document describes WebOps's robust autohealing and resume features for LLM deployments.

## Overview

LLM deployments involve long-running operations (downloads, builds) that can fail due to network issues, resource constraints, or transient errors. WebOps provides comprehensive autohealing and resume capabilities to ensure deployments complete successfully even in the face of failures.

## Resume Functionality

### Model Download Resume

**How It Works:**
- HuggingFace's `snapshot_download` automatically resumes partial downloads
- WebOps detects existing partial downloads and logs the amount already downloaded
- Downloads pick up where they left off, saving time and bandwidth

**What You'll See:**
```
[10:01:05 PM] [INFO] Preparing to download model: deepseek-ai/deepseek-ocr
[10:01:06 PM] [INFO] Found existing download (1.5GB). Resuming download...
[10:01:07 PM] [INFO] Downloading model (this may take 10-60 minutes)
[10:01:15 PM] [INFO] Downloaded 1.7GB...
[10:01:28 PM] [INFO] Downloaded 2.1GB...
```

**Technical Details:**
- Partial files are stored in the model cache directory
- HuggingFace uses `.gitattributes` and lockfiles to track download state
- Corrupted files are automatically detected via checksums and re-downloaded

### Build Resume

**How It Works:**
- vLLM build artifacts are preserved between attempts
- CMake and Ninja automatically detect completed compilation units
- Only changed or failed components are rebuilt

**Scenarios:**
1. **Full rebuild needed**: If vLLM source is missing or corrupted
2. **Partial rebuild**: If build was interrupted mid-compilation
3. **No rebuild**: If vLLM is already successfully built

## Autohealing System

### Architecture

The autohealing system consists of three layers:

```
┌─────────────────────────────────────────┐
│         User Operation Request          │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Retry Layer (with backoff)          │
│  - Configurable retry attempts          │
│  - Multiple backoff strategies          │
│  - Attempt logging                      │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Recovery Layer (intelligent)        │
│  - Error pattern detection              │
│  - Automatic recovery actions           │
│  - Resource cleanup                     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     Actual Operation                    │
│  - Download, Build, Deploy              │
└─────────────────────────────────────────┘
```

### Retry Strategies

WebOps supports multiple retry strategies:

#### 1. Immediate Retry
- No delay between attempts
- **Use case**: Quick operations, non-network errors

#### 2. Linear Backoff
- Delay increases linearly: 1s, 2s, 3s, 4s...
- **Use case**: Moderate load scenarios

#### 3. Exponential Backoff (Default)
- Delay doubles each time: 1s, 2s, 4s, 8s, 16s...
- **Use case**: Network issues, API rate limits
- **Configuration**:
  - Base delay: 5 seconds
  - Max delay: 60 seconds
  - Max attempts: 3

#### 4. Fibonacci Backoff
- Delay follows Fibonacci sequence: 1s, 1s, 2s, 3s, 5s, 8s...
- **Use case**: Balanced approach between linear and exponential

### Automatic Error Recovery

The system automatically detects and recovers from common errors:

| Error Type | Detection Pattern | Recovery Action | Auto-Execute |
|------------|-------------------|-----------------|--------------|
| Network timeout | `connection`, `timeout`, `unreachable` | Wait and retry | ✅ Yes |
| Disk full | `no space`, `disk full`, `quota` | Cleanup old caches | ❌ Manual |
| Permission error | `permission denied`, `access denied` | Fix permissions | ❌ Manual |
| Corrupted download | `corrupt`, `checksum`, `hash mismatch` | Clear and retry | ✅ Yes |
| Build failure | `compilation failed`, `build error` | Clean artifacts and retry | ✅ Yes |

### Example Flow

**Normal Download with One Network Interruption:**

```
[10:01:05 PM] [INFO] Preparing to download model: deepseek-ai/deepseek-ocr
[10:01:07 PM] [INFO] Downloading model (this may take 10-60 minutes)
[10:01:15 PM] [INFO] Downloaded 500MB...
[10:02:05 PM] [INFO] Downloaded 1.0GB...
[10:03:15 PM] [WARNING] Download attempt 1 failed: Connection timeout. Retrying...
[10:03:20 PM] [INFO] Waiting 5.0s before retry...
[10:03:25 PM] [INFO] Attempt 2/3 for download_deepseek-ai/deepseek-ocr
[10:03:26 PM] [INFO] Found existing download (1.0GB). Resuming download...
[10:03:35 PM] [INFO] Downloaded 1.2GB...
[10:04:05 PM] [INFO] Downloaded 1.5GB...
[10:05:45 PM] [SUCCESS] Model downloaded successfully
```

**Download with Auto-Recovery:**

```
[10:01:05 PM] [INFO] Downloading model...
[10:03:15 PM] [WARNING] Download attempt 1 failed: Checksum mismatch. Retrying...
[10:03:20 PM] [INFO] Attempting automatic recovery...
[10:03:21 PM] [INFO] Executing recovery action: Clear corrupted files and retry download
[10:03:22 PM] [INFO] Recovery action 'clear_and_retry' succeeded
[10:03:23 PM] [INFO] Downloaded 100MB...
[10:05:45 PM] [SUCCESS] Model downloaded successfully
```

## Configuration

### Model Download Retries

```python
# Default configuration
download_model(deployment, max_retries=3)

# Custom configuration
download_model(deployment, max_retries=5)  # More aggressive retries
```

### Retry Strategy Customization

```python
from apps.deployments.services.autohealing import RetryConfig, RetryStrategy

# Custom retry configuration
config = RetryConfig(
    max_attempts=5,
    strategy=RetryStrategy.FIBONACCI,
    base_delay=2.0,
    max_delay=120.0
)
```

## Monitoring and Debugging

### Retry Statistics

The autohealing system tracks all retry attempts:

```python
from apps.deployments.services.autohealing import autohealer

# Get statistics for a specific operation
stats = autohealer.get_retry_statistics("download_deepseek-ai/deepseek-ocr")

# Returns:
{
    'total_attempts': 5,
    'successes': 3,
    'failures': 2,
    'success_rate': 0.6,
    'attempts': [
        {'attempt': 1, 'success': False, 'error': '...', 'timestamp': 1234567890},
        {'attempt': 2, 'success': True, 'error': '', 'timestamp': 1234567895},
        # ...
    ]
}
```

### Deployment Logs

All retry and recovery attempts are logged to the deployment logs:

- **INFO**: Normal progress and successful retries
- **WARNING**: Failed attempts with retry
- **ERROR**: Final failure after all retries exhausted

### System Logs

Detailed technical logs are written to Django logs:

```bash
# View Celery logs
tail -f /tmp/celery_webops.log

# Filter for autohealing events
grep -i "retry\|recovery\|autohealer" /tmp/celery_webops.log
```

## Best Practices

### 1. Configure Appropriate Retries

**For stable networks:**
```python
download_model(deployment, max_retries=2)  # Fewer retries
```

**For unstable networks:**
```python
download_model(deployment, max_retries=5)  # More retries
```

### 2. Monitor Disk Space

Ensure sufficient disk space before large downloads:

```bash
# Check available space
df -h /opt/webops

# Clean old deployments if needed
rm -rf /opt/webops/llm-deployments/old-deployment-*
```

### 3. Handle Manual Recovery

Some errors require manual intervention:

**Disk Space Issues:**
```bash
# Clean up old caches
rm -rf /opt/webops/llm-deployments/*/model_cache/old-models
```

**Permission Issues:**
```bash
# Fix ownership
sudo chown -R webops:webops /opt/webops/llm-deployments
```

### 4. Resume After System Restart

If the system restarts during deployment:

1. **Check deployment status** in WebOps UI
2. **Retry the deployment** - it will automatically resume from cache
3. **Monitor logs** for "Found existing download" message

## Failure Scenarios

### Complete Failure After All Retries

If all retries are exhausted:

1. **Check deployment logs** for specific error
2. **Verify connectivity**: `ping huggingface.co`
3. **Check disk space**: `df -h`
4. **Check prerequisites**: `libnuma-dev`, `build-essential`, etc.
5. **Manually retry** the deployment from UI

### Partial Download Corruption

If downloads consistently fail with checksum errors:

```bash
# Clear the corrupted cache
rm -rf /opt/webops/llm-deployments/deployment-name/model_cache/*

# Retry the deployment
```

### Build Failures After Retry

If build consistently fails:

```bash
# Check build dependencies
dpkg -l | grep -E "(build-essential|cmake|ninja-build|libnuma-dev)"

# View detailed build logs
cat /opt/webops/llm-deployments/deployment-name/logs/build.log
```

## Advanced Features

### Custom Recovery Actions

Developers can add custom recovery actions:

```python
from apps.deployments.services.autohealing import RecoveryAction

custom_action = RecoveryAction(
    name="custom_cleanup",
    action=lambda: my_cleanup_function(),
    description="Clean up custom resources",
    auto_execute=True
)
```

### Deployment Integrity Verification

Verify a deployment has all required files:

```python
from apps.deployments.services.autohealing import autohealer

is_valid, missing = autohealer.verify_deployment_integrity(
    deployment_path,
    required_files=['venv/bin/python', 'model_cache', 'config.json']
)
```

### Cleanup Failed Deployments

Automatically clean up artifacts from failed deployments:

```python
from apps.deployments.services.autohealing import autohealer

autohealer.cleanup_failed_deployment(deployment_path)
```

## Performance Impact

### Resume Benefits

- **Bandwidth savings**: Only download new/changed files
- **Time savings**: Can save hours on large models
- **Resource efficiency**: No wasted work

### Retry Overhead

- **Minimal for success**: No overhead if operation succeeds first try
- **Acceptable for transient errors**: Exponential backoff prevents server overload
- **Capped delays**: Max 60 seconds between retries

## Future Enhancements

Planned improvements to the autohealing system:

1. **Predictive failure detection**: ML-based prediction of likely failures
2. **Adaptive retry strategies**: Automatically adjust strategy based on error patterns
3. **Distributed caching**: Share model caches across multiple nodes
4. **Health dashboards**: Real-time visualization of retry statistics
5. **Alert integration**: Notify admins of repeated failures
6. **Smart cleanup**: Automatically free space when needed

## Related Documentation

- [LLM Prerequisites](./LLM_PREREQUISITES.md) - System dependencies
- [Progress Tracking](./LLM_PROGRESS_TRACKING.md) - Download progress
- [Deployment Service](../apps/deployments/services/llm.py) - Source code
- [Autohealing Module](../apps/deployments/services/autohealing.py) - Autohealing implementation

## Support

If you encounter persistent deployment failures:

1. Review deployment logs in WebOps UI
2. Check system resources (`df -h`, `free -h`)
3. Verify network connectivity
4. Review this documentation for common solutions
5. Check GitHub issues for similar problems
6. Create a new issue with detailed logs
