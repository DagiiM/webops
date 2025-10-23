"""
Formatting utilities for WebOps.

Handles formatting of bytes, uptime, and other values for display.
"""


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human readable format.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.2 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_uptime(seconds: int) -> str:
    """
    Format uptime in seconds to human readable format.
    
    Args:
        seconds: Uptime in seconds
        
    Returns:
        Formatted string (e.g., "2 days, 3 hours")
    """
    if seconds < 60:
        return f"{seconds} seconds"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    minutes = minutes % 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    
    days = hours // 24
    hours = hours % 24
    return f"{days}d {hours}h"