# LLM Deployment Progress Tracking

This document describes the real-time progress tracking implementation for LLM model downloads in WebOps.

## Overview

When deploying LLM models, WebOps provides real-time progress updates as models are downloaded from HuggingFace. The progress tracking monitors actual file sizes on disk and provides clear, human-readable updates.

## Progress Display Format

### When Total Size is Unknown (default)
```
Downloaded 150MB...
Downloaded 350MB...
Downloaded 550MB...
```

### When Total Size is Known
```
Download progress: 975MB/1.2GB ~ 81.3%
Download progress: 1.1GB/1.2GB ~ 91.7%
```

## Formatting Rules

### 1. Unit Selection
- **B** (bytes): For sizes < 1,000 bytes
- **KB** (kilobytes): For sizes >= 1,000 bytes and < 1,000,000 bytes
- **MB** (megabytes): For sizes >= 1,000,000 bytes and < 1,000,000,000 bytes
- **GB** (gigabytes): For sizes >= 1,000,000,000 bytes

Units are based on SI units (1000-based), not binary units (1024-based).

### 2. Precision Rules
- **Values >= 100**: Show as integers (e.g., `150MB`, `1GB`)
- **Values 10-99**: Show with 1 decimal place (e.g., `99.5MB`, `5.5GB`)
- **Values < 10**: Show with 1-2 decimal places (e.g., `1.2GB`, `0.95MB`)

### 3. Percentage Calculation
- Calculated to **1 decimal place**
- Uses **standard rounding** (round half up): 81.25% → 81.3%
- Not Python's banker's rounding: 81.25% ↛ 81.2%

### 4. Comparative Display
When showing current/total:
- Each value uses the most appropriate unit independently
- Example: `975MB/1.2GB ~ 81.3%` (not `0.98GB/1.2GB`)
- This prioritizes readability over unit consistency

## Examples

| Downloaded (bytes) | Total (bytes) | Display |
|-------------------|---------------|---------|
| 975,000,000 | 1,200,000,000 | `975MB/1.2GB ~ 81.3%` |
| 150,000,000 | 500,000,000 | `150MB/500MB ~ 30.0%` |
| 5,500,000,000 | 8,000,000,000 | `5.5GB/8.0GB ~ 68.8%` |
| 99,500,000 | 200,000,000 | `99.5MB/200MB ~ 49.8%` |
| 350,000,000 | (unknown) | `Downloaded 350MB...` |

## Implementation Details

### Progress Monitoring
The system monitors download progress using three mechanisms:

1. **File Size Monitoring**:
   - Checks cache directory every 5 seconds
   - Reports progress every 100MB downloaded
   - Provides actual bytes-on-disk measurement

2. **Output Stream Capture**:
   - Captures stdout/stderr from HuggingFace CLI
   - Logs download events (Downloading, Fetching, etc.)
   - Detects error conditions in real-time

3. **Keepalive Messages**:
   - Logs status every 60 seconds if no visible progress
   - Prevents downloads from appearing "stuck"
   - Shows current download size

### Code Location
- **Service**: `control-panel/apps/deployments/services/llm.py`
- **Method**: `LLMDeploymentService.download_model()`
- **Helper**: `format_bytes()` function (nested)

## User Experience

### Normal Download Flow
```
[10:01:06 PM] [INFO] Preparing to download model: deepseek-ai/deepseek-ocr
[10:01:08 PM] [INFO] Downloading model (this may take 10-60 minutes)
[10:01:15 PM] [INFO] Downloaded 150MB...
[10:01:28 PM] [INFO] Downloaded 350MB...
[10:02:05 PM] [INFO] Downloaded 550MB...
[10:02:30 PM] [INFO] Downloaded 750MB...
[10:03:15 PM] [INFO] Downloaded 1.0GB...
[10:05:45 PM] [SUCCESS] Model downloaded successfully
```

### With Estimated Total
```
[10:01:15 PM] [INFO] Download progress: 150MB/1.2GB ~ 12.5%
[10:01:28 PM] [INFO] Download progress: 350MB/1.2GB ~ 29.2%
[10:02:05 PM] [INFO] Download progress: 550MB/1.2GB ~ 45.8%
[10:02:30 PM] [INFO] Download progress: 750MB/1.2GB ~ 62.5%
[10:03:15 PM] [INFO] Download progress: 975MB/1.2GB ~ 81.3%
[10:05:45 PM] [SUCCESS] Model downloaded successfully
```

## Benefits

1. **Real-time feedback**: Users see actual progress, not just start/end markers
2. **Accurate measurements**: Based on actual file sizes, not estimates
3. **Human-readable**: Units and precision chosen for clarity
4. **Standard formatting**: Follows common conventions (SI units, standard rounding)
5. **Fault tolerance**: Continues working even if total size is unknown

## Troubleshooting

### No Progress Updates Visible
**Cause**: Model may already be cached
**Solution**: Check logs for "Model downloaded successfully" without intermediate progress

### Progress Appears Stuck
**Cause**: Large files being downloaded as single chunks
**Solution**: Wait for next 100MB threshold or check keepalive messages in logs

### Inaccurate Percentages
**Cause**: Total size estimation may be incorrect
**Solution**: Percentages are estimates when total is unknown; trust file size progress

## Future Enhancements

Potential improvements to consider:

1. **Total Size Detection**: Parse HuggingFace API to get exact total size before download
2. **Speed Tracking**: Show download speed (MB/s)
3. **ETA Calculation**: Estimate time remaining based on current speed
4. **File-level Progress**: Show which specific model files are being downloaded
5. **Parallel Downloads**: Track multiple files downloading simultaneously

## Technical Notes

- Uses Python's `pathlib` for file operations
- Threading for non-blocking progress monitoring
- Decimal module for precise percentage rounding
- Environment variables to control HuggingFace progress bars
- Graceful degradation when total size unknown

## Related Documentation

- [LLM Prerequisites](./LLM_PREREQUISITES.md) - System dependencies
- [LLM Deployment Guide](../CLAUDE.md#llm-deployment-prerequisites) - Quick setup
- [Deployment Service](../apps/deployments/services/llm.py) - Source code
