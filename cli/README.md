# WebOps CLI

Command-line interface for the WebOps hosting platform with enhanced terminal experience features.

## Installation

Install the current repository version (a public package-index release has not
been verified for these instructions):

```bash
git clone https://github.com/DagiiM/webops.git
cd webops
python -m pip install -e ./cli
webops --help
```

Use Python 3.11 or later. Run `webops config` after the WebOps control panel is
installed and reachable. The **platform installer** and **CLI installer** are
different operations; see the [installation guide](../docs/getting-started/installation.md).

For model-assisted planning and deployment, see the
[Jani + self-hosted model guide](../docs/deployment/ai-assisted-github-deployments.md).


## Configuration

```bash
# Supply a least-privileged API token from your approved secret store.
# Token arguments may be visible to other processes; use a trusted host.
webops config --url https://panel.example.com --token "$WEBOPS_CLI_TOKEN" --role developer
```

## Basic Usage

### Deploy an application
```bash
# No-write validation
webops deploy user/repo --name myapp --domain myapp.example.com --dry-run

# Explicitly approved submission; --wait checks provider state, not HTTP health
webops deploy user/repo --name myapp --domain myapp.example.com --approve --wait
```

### Optional Jani-assisted deployment

Jani provides an **advisory read-only review** of the exact GitHub checkout.
Configure a self-hosted, OpenAI-compatible model and the installed Jani binary
before running:

```bash
webops deploy user/repo --ai-assist \
  --model qwen3:8b \
  --model-endpoint https://your-private-model-gateway.example/v1 \
  --dry-run

# After verifying the plan and ensuring your deployment runtime can fetch the repo:
webops deploy user/repo --ai-assist \
  --model qwen3:8b \
  --model-endpoint https://your-private-model-gateway.example/v1 \
  --approve --wait
```

The model credential must be in `WEBOPS_MODEL_API_KEY` (or use
`--model-key-env` to select the variable); never put it in the repository.
For private repositories, provision an authorized short-lived read-only
GitHub credential for the CLI's preflight **and** appropriate backend
repository access. A successful `--wait` is **not** verified hosting: inspect
`webops info`, logs, and the actual application HTTPS health endpoint.

The complete setup, credential boundaries, Runpod development model adapter,
and outstanding production gates are documented in the
[AI-assisted deployment guide](../docs/deployment/ai-assisted-github-deployments.md).

### List deployments
```bash
webops list
```

### View deployment details
```bash
webops info myapp
```

### View logs
```bash
webops logs myapp --tail 100 --follow
```

### Control services
```bash
webops start myapp
webops stop myapp
webops restart myapp
```

### Delete deployment
```bash
webops delete myapp
```

## Enhanced Features

### New Command Groups

#### Admin Commands (`webops admin`)

Administrative commands for WebOps system management:

- **`webops admin status`** - Display comprehensive system status including services, processes, and resource usage
- **`webops admin shell`** - Start an interactive shell as the webops user
- **`webops admin run <command>`** - Execute commands as the webops user with proper environment
- **`webops admin fix-permissions`** - Fix file ownership and permissions for WebOps directories
- **`webops admin deployments`** - List all deployed applications with detailed status information
- **`webops admin validate`** - Validate WebOps user setup and configuration

**Note:** Admin commands require root privileges and will prompt for elevation if needed.

#### System Commands (`webops system`)

System monitoring and health check commands:

- **`webops system health`** - Run comprehensive health check of all WebOps components
- **`webops system monitor`** - Real-time system monitoring dashboard with live metrics
- **`webops system services`** - Check detailed status of all WebOps systemd services
- **`webops system disk`** - Show disk usage breakdown for WebOps directories
- **`webops system doctor`** - Automated diagnostics with actionable recommendations

### Enhanced Terminal Experience

#### 1. Rich Terminal Output

All commands now use Rich library for beautiful, colored terminal output:
- Color-coded status indicators (green healthy, yellow warning, red error)
- Formatted tables for structured data
- Progress bars and spinners for long-running operations
- Syntax highlighting for code and configuration

#### 2. Intelligent Error Handling

Enhanced error handling with contextual suggestions:
- Automatic error type detection (connection, permission, configuration, etc.)
- Contextual recovery suggestions based on error patterns
- Graceful handling of common issues with helpful guidance
- Detailed error reporting with troubleshooting steps

#### 3. Progress Indicators

Visual feedback for all operations:
- Spinners for quick operations
- Progress bars for file operations and deployments
- Multi-task progress tracking for complex operations
- Real-time status updates during health checks

#### 4. System Health Monitoring

Comprehensive health checking system:
- Service status monitoring (webops-web, webops-celery, webops-celerybeat)
- Database connectivity and migration status
- Disk usage monitoring with threshold alerts
- System load and resource utilization
- Celery worker health and queue status

#### 5. Automated Diagnostics

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

## API Token

Generate an API token from the WebOps control panel:

1. Login to WebOps
2. Navigate to Settings → API Tokens
3. Create a new token
4. Copy the token and use it with `webops config`

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

## Future Enhancements

Phase 1 lays the foundation for future improvements:
- **Phase 2**: Interactive workflows and guided setup wizards
- **Phase 3**: Real-time monitoring with WebSocket integration
- **Phase 4**: Advanced automation and security audit features
