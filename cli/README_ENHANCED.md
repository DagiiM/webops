# WebOps CLI Enhanced Features

This document describes the enhanced terminal experience features added to the WebOps CLI in Phase 1 of the terminal experience improvement project.

## New Command Groups

### Admin Commands (`webops admin`)

Administrative commands for WebOps system management:

- **`webops admin status`** - Display comprehensive system status including services, processes, and resource usage
- **`webops admin shell`** - Start an interactive shell as the webops user
- **`webops admin run <command>`** - Execute commands as the webops user with proper environment
- **`webops admin fix-permissions`** - Fix file ownership and permissions for WebOps directories
- **`webops admin deployments`** - List all deployed applications with detailed status information
- **`webops admin validate`** - Validate WebOps user setup and configuration

**Note:** Admin commands require root privileges and will prompt for elevation if needed.

### System Commands (`webops system`)

System monitoring and health check commands:

- **`webops system health`** - Run comprehensive health check of all WebOps components
- **`webops system monitor`** - Real-time system monitoring dashboard with live metrics
- **`webops system services`** - Check detailed status of all WebOps systemd services
- **`webops system disk`** - Show disk usage breakdown for WebOps directories
- **`webops system doctor`** - Automated diagnostics with actionable recommendations

## Enhanced Features

### 1. Rich Terminal Output

All commands now use Rich library for beautiful, colored terminal output:
- Color-coded status indicators (🟢 healthy, 🟡 warning, 🔴 error)
- Formatted tables for structured data
- Progress bars and spinners for long-running operations
- Syntax highlighting for code and configuration

### 2. Intelligent Error Handling

Enhanced error handling with contextual suggestions:
- Automatic error type detection (connection, permission, configuration, etc.)
- Contextual recovery suggestions based on error patterns
- Graceful handling of common issues with helpful guidance
- Detailed error reporting with troubleshooting steps

### 3. Progress Indicators

Visual feedback for all operations:
- Spinners for quick operations
- Progress bars for file operations and deployments
- Multi-task progress tracking for complex operations
- Real-time status updates during health checks

### 4. System Health Monitoring

Comprehensive health checking system:
- Service status monitoring (webops-web, webops-celery, webops-celerybeat)
- Database connectivity and migration status
- Disk usage monitoring with threshold alerts
- System load and resource utilization
- Celery worker health and queue status

### 5. Automated Diagnostics

The `webops system doctor` command provides:
- Automated problem detection across all system components
- Prioritized recommendations for fixing issues
- JSON export capability for integration with monitoring systems
- Detailed diagnostic reports with actionable steps

## Usage Examples

### Check System Health
```bash
# Quick health overview
webops system health

# Detailed service status
webops system services

# Automated diagnostics with recommendations
webops system doctor

# Save diagnostic results to file
webops system doctor --output /tmp/webops-health.json
```

### Administrative Tasks
```bash
# Check overall system status (requires root)
sudo webops admin status

# Fix file permissions (requires root)
sudo webops admin fix-permissions

# Run command as webops user (requires root)
sudo webops admin run "python manage.py check"

# List all deployments with status
sudo webops admin deployments
```

### Real-time Monitoring
```bash
# Live system monitoring dashboard
webops system monitor

# Monitor disk usage
webops system disk
```

## Error Handling Examples

The enhanced error handling provides contextual help:

```bash
# Connection error example
$ webops status
❌ Connection Error: Could not connect to WebOps control panel

💡 Suggestions:
  • Check if the WebOps control panel is running: sudo systemctl status webops-web
  • Verify the configured URL in your WebOps CLI configuration
  • Check network connectivity to the control panel
  • Review WebOps logs: sudo journalctl -u webops-web -f

# Permission error example
$ webops admin status
❌ Permission Error: This operation requires root privileges

💡 Suggestions:
  • Run the command with sudo: sudo webops admin status
  • Ensure you have administrative access to this system
  • Contact your system administrator if you need elevated privileges
```

## Configuration Validation

Enhanced configuration validation ensures:
- WebOps CLI is properly configured before operations
- Valid API endpoints and authentication tokens
- Proper file permissions and directory structure
- Service dependencies are met

## Integration with Existing Commands

All existing WebOps CLI commands continue to work unchanged, with enhanced:
- Error reporting and recovery suggestions
- Progress indicators for long-running operations
- Consistent Rich-based output formatting
- Better handling of edge cases and failures

## Technical Implementation

### Architecture
- **Modular Design**: Separate modules for admin, system, errors, and progress
- **Type Safety**: Full type annotations with Pyright strict mode
- **Error Handling**: Centralized error management with contextual suggestions
- **Progress Feedback**: Rich-based progress indicators for all operations
- **Extensibility**: Easy to add new commands and monitoring capabilities

### Dependencies
- **Rich**: Terminal formatting and progress indicators
- **Click**: Command-line interface framework
- **psutil**: System and process monitoring
- **subprocess**: System command execution
- **pathlib**: Modern path handling

### Testing
Comprehensive test suite covering:
- Error handling scenarios
- Progress indicator functionality
- System monitoring capabilities
- Admin command operations
- Configuration validation

## Future Enhancements

Phase 1 lays the foundation for future improvements:
- **Phase 2**: Interactive workflows and guided setup wizards
- **Phase 3**: Real-time monitoring with WebSocket integration
- **Phase 4**: Advanced automation and security audit features

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`
2. **Permission Denied**: Admin commands require root privileges: `sudo webops admin <command>`
3. **Service Not Found**: Verify WebOps services are installed and configured
4. **Configuration Missing**: Run `webops config` to set up CLI configuration

### Getting Help

- Use `--help` with any command for detailed usage information
- Run `webops system doctor` for automated diagnostics
- Check WebOps logs: `sudo journalctl -u webops-web -f`
- Review the main WebOps documentation for system setup

## Conclusion

The enhanced WebOps CLI provides a significantly improved terminal experience with:
- Beautiful, informative output
- Intelligent error handling and recovery
- Comprehensive system monitoring
- Automated diagnostics and recommendations
- Seamless integration with existing workflows

These improvements make WebOps administration more efficient, user-friendly, and reliable.