"""
Safe command execution utilities for WebOps.

This module provides secure command execution functions that prevent command injection
vulnerabilities. All functions validate and sanitize commands before execution.

SECURITY PRINCIPLES:
1. Never use shell=True
2. Always parse commands into argument lists
3. Validate commands against whitelist
4. Sanitize all user input
5. Use timeouts to prevent DoS
6. Capture and log all command execution
"""

import shlex
import subprocess
import logging
from typing import List, Optional, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


# Whitelist of allowed command bases
ALLOWED_COMMANDS = {
    # Package managers
    'npm', 'yarn', 'pnpm',
    'pip', 'pip3', 'poetry', 'pipenv',
    'bundle', 'gem',
    'composer',
    'go',
    'cargo',
    'mvn', 'gradle',

    # Build tools
    'make', 'cmake',
    'webpack', 'vite', 'rollup',
    'tsc', 'babel',

    # Runtime commands
    'node', 'python', 'python3',
    'ruby',
    'php',
    'java',

    # Database migrations
    'python3 manage.py migrate',
    'python3 manage.py collectstatic',
    'rails db:migrate',
    'php artisan migrate',

    # Testing
    'pytest', 'python3 -m pytest',
    'npm test', 'yarn test',
    'php artisan test',

    # Git (read-only operations)
    'git clone', 'git pull', 'git fetch', 'git checkout',

    # Docker (if needed - use with extreme caution)
    # Commented out by default - enable only if absolutely necessary
    # 'docker', 'docker-compose',
}

# Dangerous command patterns that should never be allowed
DANGEROUS_PATTERNS = [
    'rm -rf',
    '&&',
    '||',
    ';',
    '|',
    '>',
    '<',
    '`',
    '$(',
    '$((',
    '../',
    'eval',
    'exec',
    'sudo',
    'su',
    'chmod',
    'chown',
    'curl',
    'wget',
    '/etc/',
    '/root/',
    '~/',
]


class CommandExecutionError(Exception):
    """Exception raised for command execution errors."""
    pass


class CommandValidationError(Exception):
    """Exception raised when command validation fails."""
    pass


def validate_command(command: str) -> Tuple[bool, str]:
    """
    Validate a command against security rules.

    Args:
        command: Command string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for dangerous patterns
    command_lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command_lower:
            return False, f"Dangerous pattern detected: {pattern}"

    # Parse command to get base command
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"

    if not parts:
        return False, "Empty command"

    # Get the base command (first part)
    base_command = parts[0]

    # For compound commands like "python3 manage.py", check up to 3 parts
    if len(parts) >= 2:
        two_part = f"{parts[0]} {parts[1]}"
        if two_part in ALLOWED_COMMANDS:
            return True, ""

    if len(parts) >= 3:
        three_part = f"{parts[0]} {parts[1]} {parts[2]}"
        if three_part in ALLOWED_COMMANDS:
            return True, ""

    # Check if base command is in whitelist
    if base_command not in ALLOWED_COMMANDS:
        return False, f"Command not in whitelist: {base_command}"

    return True, ""


def safe_run(
    command: str,
    cwd: Optional[Path] = None,
    timeout: int = 300,
    capture_output: bool = True,
    check: bool = True,
    env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    """
    Execute a command safely without shell=True.

    Args:
        command: Command string to execute (will be parsed)
        cwd: Working directory
        timeout: Timeout in seconds (default 5 minutes)
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise exception on non-zero exit
        env: Environment variables

    Returns:
        CompletedProcess instance

    Raises:
        CommandValidationError: If command fails validation
        CommandExecutionError: If command execution fails
        subprocess.TimeoutExpired: If command times out
    """
    # Validate command
    is_valid, error_msg = validate_command(command)
    if not is_valid:
        logger.error(f"Command validation failed: {error_msg}")
        raise CommandValidationError(f"Command validation failed: {error_msg}")

    # Parse command into argument list (SECURE: no shell=True)
    try:
        args = shlex.split(command)
    except ValueError as e:
        raise CommandValidationError(f"Failed to parse command: {e}")

    logger.info(f"Executing command: {' '.join(args)}")
    logger.debug(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            args,  # SECURITY: Using list, not string
            shell=False,  # SECURITY: Never use shell=True
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            check=check,
            env=env
        )

        logger.info(f"Command completed with exit code: {result.returncode}")
        return result

    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {e.stderr}")
        raise CommandExecutionError(f"Command failed: {e.stderr}") from e

    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after {timeout} seconds")
        raise


def safe_run_install_command(
    command: str,
    cwd: Path,
    timeout: int = 600
) -> Tuple[bool, str]:
    """
    Safely execute an installation command (npm install, pip install, etc.).

    This is a convenience wrapper for safe_run with appropriate defaults
    for package installation.

    Args:
        command: Install command string
        cwd: Working directory (project root)
        timeout: Timeout in seconds (default 10 minutes)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        result = safe_run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            check=True
        )
        return True, "Dependencies installed successfully"

    except CommandValidationError as e:
        return False, f"Invalid install command: {e}"

    except CommandExecutionError as e:
        return False, f"Installation failed: {e}"

    except subprocess.TimeoutExpired:
        return False, f"Installation timed out after {timeout} seconds"

    except Exception as e:
        logger.exception("Unexpected error during installation")
        return False, f"Unexpected error: {e}"


def safe_run_build_command(
    command: str,
    cwd: Path,
    timeout: int = 900
) -> Tuple[bool, str]:
    """
    Safely execute a build command (npm run build, make, etc.).

    Args:
        command: Build command string
        cwd: Working directory (project root)
        timeout: Timeout in seconds (default 15 minutes)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        result = safe_run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            check=True
        )
        return True, "Build completed successfully"

    except CommandValidationError as e:
        return False, f"Invalid build command: {e}"

    except CommandExecutionError as e:
        return False, f"Build failed: {e}"

    except subprocess.TimeoutExpired:
        return False, f"Build timed out after {timeout} seconds"

    except Exception as e:
        logger.exception("Unexpected error during build")
        return False, f"Unexpected error: {e}"


def is_command_allowed(command: str) -> bool:
    """
    Quick check if a command would be allowed.

    Useful for validation before attempting execution.

    Args:
        command: Command string to check

    Returns:
        True if command would be allowed, False otherwise
    """
    is_valid, _ = validate_command(command)
    return is_valid


def get_allowed_commands() -> List[str]:
    """
    Get list of allowed command bases.

    Returns:
        List of allowed commands
    """
    return sorted(list(ALLOWED_COMMANDS))


def add_allowed_command(command: str) -> None:
    """
    Add a command to the whitelist.

    WARNING: Use with extreme caution. Only add commands that are absolutely
    necessary and have been thoroughly vetted for security.

    Args:
        command: Command to add to whitelist
    """
    logger.warning(f"Adding command to whitelist: {command}")
    ALLOWED_COMMANDS.add(command)


def sanitize_path(path: str) -> str:
    """
    Sanitize a file path to prevent directory traversal.

    Args:
        path: Path string to sanitize

    Returns:
        Sanitized path

    Raises:
        ValueError: If path is dangerous
    """
    # Remove any parent directory references
    if '..' in path:
        raise ValueError("Path contains parent directory reference")

    # Remove leading slash (should be relative)
    path = path.lstrip('/')

    # Check for absolute path indicators
    if path.startswith('~') or path.startswith('/'):
        raise ValueError("Absolute paths not allowed")

    return path
