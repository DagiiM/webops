"""Security logging and monitoring for WebOps CLI.

This module provides comprehensive security event logging for compliance
with SOC 2 and ISO 27001 requirements.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union
from enum import Enum


class SecurityEventType(Enum):
    """Types of security events for logging."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CONFIGURATION_CHANGE = "configuration_change"
    DATA_ACCESS = "data_access"
    DEPLOYMENT_OPERATION = "deployment_operation"
    ERROR = "error"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_ACCESS = "system_access"


class SecurityLogger:
    """Handles security event logging for compliance and monitoring."""
    
    def __init__(self, log_dir: Optional[Path] = None) -> None:
        """Initialize security logger.
        
        Args:
            log_dir: Directory for security logs. Defaults to ~/.webops/logs
        """
        if log_dir is None:
            log_dir = Path.home() / ".webops" / "logs"
        
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions
        os.chmod(self.log_dir, 0o700)
        
        # Security log file
        self.security_log_file = self.log_dir / "security.log"
        self.audit_log_file = self.log_dir / "audit.log"
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure secure logging handlers."""
        # Security logger for real-time monitoring
        self.security_logger = logging.getLogger('webops_security')
        self.security_logger.setLevel(logging.INFO)
        
        # Audit logger for compliance
        self.audit_logger = logging.getLogger('webops_audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # Prevent propagation to root logger
        self.security_logger.propagate = False
        self.audit_logger.propagate = False
        
        # Clear existing handlers
        self.security_logger.handlers.clear()
        self.audit_logger.handlers.clear()
        
        # Security log handler
        security_handler = logging.FileHandler(self.security_log_file)
        security_handler.setLevel(logging.INFO)
        
        # Audit log handler
        audit_handler = logging.FileHandler(self.audit_log_file)
        audit_handler.setLevel(logging.INFO)
        
        # Set restrictive permissions on log files
        for log_file in [self.security_log_file, self.audit_log_file]:
            if not log_file.exists():
                log_file.touch()
            os.chmod(log_file, 0o600)
        
        # JSON formatter for structured logging
        formatter = logging.Formatter('%(message)s')
        security_handler.setFormatter(formatter)
        audit_handler.setFormatter(formatter)
        
        # Add handlers
        self.security_logger.addHandler(security_handler)
        self.audit_logger.addHandler(audit_handler)
    
    def _create_log_entry(
        self,
        event_type: SecurityEventType,
        message: str,
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "INFO"
    ) -> Dict[str, Any]:
        """Create a structured log entry.
        
        Args:
            event_type: Type of security event
            message: Log message
            user: User identifier
            ip_address: IP address if applicable
            resource: Resource being accessed
            action: Action being performed
            result: Result of the action (SUCCESS, FAILURE, etc.)
            details: Additional details as dictionary
            severity: Log severity level
            
        Returns:
            Structured log entry as dictionary
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "severity": severity,
            "message": message,
            "source": "webops_cli",
            "version": "0.1.0"
        }
        
        # Add optional fields if provided
        if user:
            entry["user"] = user
        if ip_address:
            entry["ip_address"] = ip_address
        if resource:
            entry["resource"] = resource
        if action:
            entry["action"] = action
        if result:
            entry["result"] = result
        if details:
            entry["details"] = details
        
        return entry
    
    def log_authentication(
        self,
        user: str,
        success: bool,
        ip_address: Optional[str] = None,
        method: str = "token",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log authentication attempt.
        
        Args:
            user: User identifier
            success: Whether authentication was successful
            ip_address: IP address of the attempt
            method: Authentication method (token, password, etc.)
            details: Additional details
        """
        status = "SUCCESS" if success else "FAILED"
        message = f"Authentication {status.lower()} for user {user} via {method}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.AUTHENTICATION,
            message=message,
            user=user,
            ip_address=ip_address,
            action="authenticate",
            result=status,
            details=details or {"method": method},
            severity="INFO" if success else "WARNING"
        )
        
        self._write_entry(entry)
    
    def log_authorization(
        self,
        user: str,
        action: str,
        resource: str,
        granted: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log authorization decision.
        
        Args:
            user: User identifier
            action: Action being attempted
            resource: Resource being accessed
            granted: Whether access was granted
            details: Additional details
        """
        status = "GRANTED" if granted else "DENIED"
        message = f"Authorization {status.lower()}: {user} attempted to {action} on {resource}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.AUTHORIZATION,
            message=message,
            user=user,
            action=action,
            resource=resource,
            result=status,
            details=details,
            severity="WARNING" if not granted else "INFO"
        )
        
        self._write_entry(entry)
    
    def log_configuration_change(
        self,
        user: str,
        setting: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log configuration changes.
        
        Args:
            user: User making the change
            setting: Configuration setting being changed
            old_value: Previous value
            new_value: New value
            details: Additional details
        """
        message = f"Configuration change: {setting} updated by {user}"
        
        # Mask sensitive values in logs
        sensitive_keys = ['token', 'password', 'secret', 'key']
        if old_value and any(sensitive in setting.lower() for sensitive in sensitive_keys):
            old_value = "***MASKED***"
        if new_value and any(sensitive in setting.lower() for sensitive in sensitive_keys):
            new_value = "***MASKED***"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.CONFIGURATION_CHANGE,
            message=message,
            user=user,
            action="update_config",
            resource=setting,
            result="SUCCESS",
            details={
                "setting": setting,
                "old_value": old_value,
                "new_value": new_value,
                **(details or {})
            }
        )
        
        self._write_entry(entry)
    
    def log_deployment_operation(
        self,
        user: str,
        operation: str,
        deployment: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log deployment operations.
        
        Args:
            user: User performing the operation
            operation: Operation type (create, start, stop, delete, etc.)
            deployment: Deployment name
            success: Whether operation was successful
            details: Additional details
        """
        status = "SUCCESS" if success else "FAILED"
        message = f"Deployment {operation} {status.lower()}: {deployment} by {user}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.DEPLOYMENT_OPERATION,
            message=message,
            user=user,
            action=operation,
            resource=deployment,
            result=status,
            details=details
        )
        
        self._write_entry(entry)
    
    def log_data_access(
        self,
        user: str,
        resource_type: str,
        resource_name: str,
        action: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log data access events.
        
        Args:
            user: User accessing data
            resource_type: Type of resource (deployment, database, etc.)
            resource_name: Name of the resource
            action: Action performed (read, write, delete)
            details: Additional details
        """
        message = f"Data access: {user} {action} {resource_type} {resource_name}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.DATA_ACCESS,
            message=message,
            user=user,
            action=action,
            resource=f"{resource_type}:{resource_name}",
            result="SUCCESS",
            details=details
        )
        
        self._write_entry(entry)
    
    def log_security_violation(
        self,
        user: Optional[str],
        violation_type: str,
        description: str,
        severity: str = "HIGH",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log security violations.
        
        Args:
            user: User involved in violation (if applicable)
            violation_type: Type of violation
            description: Description of the violation
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            details: Additional details
        """
        message = f"Security violation: {violation_type} - {description}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.SECURITY_VIOLATION,
            message=message,
            user=user,
            action="security_violation",
            result="VIOLATION",
            details={
                "violation_type": violation_type,
                "description": description,
                **(details or {})
            },
            severity=severity
        )
        
        self._write_entry(entry)
    
    def log_error(
        self,
        user: Optional[str],
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error events.
        
        Args:
            user: User who encountered the error
            error_type: Type of error
            error_message: Error message
            details: Additional details
        """
        message = f"Error: {error_type} - {error_message}"
        
        entry = self._create_log_entry(
            event_type=SecurityEventType.ERROR,
            message=message,
            user=user,
            action="error",
            result="ERROR",
            details={
                "error_type": error_type,
                "error_message": error_message,
                **(details or {})
            },
            severity="ERROR"
        )
        
        self._write_entry(entry)
    
    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """Write log entry to both security and audit logs.
        
        Args:
            entry: Log entry to write
        """
        log_line = json.dumps(entry, default=str)
        
        # Write to security log
        self.security_logger.info(log_line)
        
        # Write to audit log for compliance
        self.audit_logger.info(log_line)
    
    def get_user(self) -> Optional[str]:
        """Get current user identifier.
        
        Returns:
            Current user identifier or None
        """
        try:
            # Try to get from environment
            user = os.environ.get('USER') or os.environ.get('USERNAME')
            if user:
                return user
            
            # Fallback to system calls
            import getpass
            return getpass.getuser()
        except Exception:
            return "unknown"
    
    def get_ip_address(self) -> Optional[str]:
        """Get client IP address.
        
        Returns:
            IP address or None
        """
        # For CLI, we can't easily get client IP
        # This would be more relevant in a web context
        return None


# Global security logger instance
_security_logger = None


def get_security_logger() -> SecurityLogger:
    """Get the global security logger instance.
    
    Returns:
        SecurityLogger instance
    """
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger


def log_security_event(
    event_type: SecurityEventType,
    message: str,
    **kwargs
) -> None:
    """Convenience function to log security events.
    
    Args:
        event_type: Type of security event
        message: Log message
        **kwargs: Additional arguments for the log entry
    """
    logger = get_security_logger()
    
    # Route to appropriate logging method
    if event_type == SecurityEventType.AUTHENTICATION:
        logger.log_authentication(
            user=kwargs.get('user', 'unknown'),
            success=kwargs.get('success', False),
            ip_address=kwargs.get('ip_address'),
            method=kwargs.get('method', 'token'),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.AUTHORIZATION:
        logger.log_authorization(
            user=kwargs.get('user', 'unknown'),
            action=kwargs.get('action', 'unknown'),
            resource=kwargs.get('resource', 'unknown'),
            granted=kwargs.get('granted', False),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.CONFIGURATION_CHANGE:
        logger.log_configuration_change(
            user=kwargs.get('user', 'unknown'),
            setting=kwargs.get('setting', 'unknown'),
            old_value=kwargs.get('old_value'),
            new_value=kwargs.get('new_value'),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.DEPLOYMENT_OPERATION:
        logger.log_deployment_operation(
            user=kwargs.get('user', 'unknown'),
            operation=kwargs.get('operation', 'unknown'),
            deployment=kwargs.get('deployment', 'unknown'),
            success=kwargs.get('success', False),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.DATA_ACCESS:
        logger.log_data_access(
            user=kwargs.get('user', 'unknown'),
            resource_type=kwargs.get('resource_type', 'unknown'),
            resource_name=kwargs.get('resource_name', 'unknown'),
            action=kwargs.get('action', 'unknown'),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.SECURITY_VIOLATION:
        logger.log_security_violation(
            user=kwargs.get('user'),
            violation_type=kwargs.get('violation_type', 'unknown'),
            description=kwargs.get('description', 'unknown'),
            severity=kwargs.get('severity', 'MEDIUM'),
            details=kwargs.get('details')
        )
    elif event_type == SecurityEventType.ERROR:
        logger.log_error(
            user=kwargs.get('user'),
            error_type=kwargs.get('error_type', 'unknown'),
            error_message=kwargs.get('error_message', 'unknown'),
            details=kwargs.get('details')
        )
    else:
        # Generic logging
        entry = logger._create_log_entry(
            event_type=event_type,
            message=message,
            **kwargs
        )
        logger._write_entry(entry)