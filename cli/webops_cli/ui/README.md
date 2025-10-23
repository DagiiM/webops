# WebOps CLI UI Components

This directory contains all UI-related components for the WebOps CLI, organized for better maintainability and separation of concerns.

## Structure

- [`terminal.py`](./terminal.py) - Terminal UI components including dashboards, panels, and log viewers
- [`interactive.py`](./interactive.py) - Interactive command implementations with enhanced UX
- [`progress.py`](./progress.py) - Progress indicators and status displays
- [`__init__.py`](./__init__.py) - Package initialization with convenient exports

## Usage

```python
# Import specific components
from webops_cli.ui.terminal import TerminalUI
from webops_cli.ui.interactive import InteractiveCommands
from webops_cli.ui.progress import ProgressManager

# Or import all from the package
from webops_cli.ui import (
    TerminalUI,
    InteractiveCommands,
    ProgressManager,
    StatusDisplay,
    show_progress,
    show_step_progress,
    simulate_long_operation
)
```

## Components

### TerminalUI
Provides enhanced terminal UI components for better user experience, including:
- Interactive status dashboards
- Formatted tables and panels
- Log viewers with syntax highlighting
- Progress indicators with step tracking

### InteractiveCommands
Implements interactive command implementations with enhanced UX:
- Real-time status monitoring
- Interactive deployment management
- Live log viewing
- User-friendly wizards for complex operations

### ProgressManager
Manages different types of progress indicators:
- Spinners for indeterminate progress
- Progress bars for determinate operations
- Multi-task progress displays
- Specialized progress for deployment, health checks, and backups

### StatusDisplay
Displays real-time status information:
- Service status tables
- Deployment status with health indicators
- System metrics with color-coded status
- Formatted output for various WebOps entities