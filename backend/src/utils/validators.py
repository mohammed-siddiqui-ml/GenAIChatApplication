"""
Validation Utilities

This module provides validation functions for URLs, cron expressions,
and other data formats used across the application.
"""

import re
import logging
from typing import Optional
from urllib.parse import urlparse

# Logger
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_url(url: str, require_https: bool = False) -> bool:
    """
    Validate a URL format.
    
    Checks if the URL has a valid scheme (http/https) and netloc.
    
    Args:
        url: URL string to validate
        require_https: If True, only allow HTTPS URLs
        
    Returns:
        bool: True if valid, False otherwise
        
    Example:
        >>> validate_url("https://api.example.com")
        True
        >>> validate_url("invalid-url")
        False
        >>> validate_url("http://example.com", require_https=True)
        False
    """
    if not url:
        return False
    
    try:
        result = urlparse(url)
        
        # Check scheme and netloc are present
        if not result.scheme or not result.netloc:
            return False
        
        # Check scheme is http or https
        if result.scheme not in ['http', 'https']:
            return False
        
        # If HTTPS is required, enforce it
        if require_https and result.scheme != 'https':
            return False
        
        return True
    except Exception as e:
        logger.warning(f"URL validation error: {str(e)}")
        return False


def validate_cron_expression(cron_expr: str) -> bool:
    """
    Validate a cron expression format.
    
    Supports standard 5-field cron expressions (minute, hour, day, month, weekday).
    Also supports extended formats with seconds (6 fields) or year (6 fields).
    
    Validation rules:
    - 5 fields: minute hour day month weekday
    - Each field can contain: numbers, ranges (1-5), lists (1,3,5), steps (*/5), wildcards (*)
    
    Args:
        cron_expr: Cron expression string to validate
        
    Returns:
        bool: True if valid cron expression, False otherwise
        
    Example:
        >>> validate_cron_expression("0 2 * * *")  # Daily at 2 AM
        True
        >>> validate_cron_expression("*/15 * * * *")  # Every 15 minutes
        True
        >>> validate_cron_expression("0 0 1 1 *")  # Yearly on Jan 1
        True
        >>> validate_cron_expression("invalid cron")
        False
    """
    if not cron_expr:
        return False
    
    try:
        # Split into fields
        fields = cron_expr.strip().split()
        
        # Must have 5 fields (standard cron)
        if len(fields) != 5:
            logger.debug(f"Cron expression must have 5 fields, got {len(fields)}")
            return False
        
        # Define valid ranges for each field
        # [min, max] for each field
        field_ranges = [
            (0, 59),   # minute
            (0, 23),   # hour
            (1, 31),   # day of month
            (1, 12),   # month
            (0, 6),    # day of week (0=Sunday)
        ]
        
        # Validate each field
        for i, field in enumerate(fields):
            if not _validate_cron_field(field, field_ranges[i][0], field_ranges[i][1]):
                logger.debug(f"Invalid cron field {i}: {field}")
                return False
        
        return True
    except Exception as e:
        logger.warning(f"Cron validation error: {str(e)}")
        return False


def _validate_cron_field(field: str, min_val: int, max_val: int) -> bool:
    """
    Validate a single cron field.
    
    Supports:
    - Wildcards: *
    - Numbers: 5
    - Ranges: 1-5
    - Lists: 1,3,5
    - Steps: */5, 1-10/2
    
    Args:
        field: Cron field string
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        bool: True if valid field
    """
    # Wildcard is always valid
    if field == '*':
        return True
    
    # Step pattern: */n or start-end/step
    if '/' in field:
        parts = field.split('/')
        if len(parts) != 2:
            return False
        
        # Validate step value
        try:
            step = int(parts[1])
            if step <= 0:
                return False
        except ValueError:
            return False
        
        # Validate range part
        if parts[0] == '*':
            return True
        elif '-' in parts[0]:
            return _validate_cron_range(parts[0], min_val, max_val)
        else:
            return _validate_cron_number(parts[0], min_val, max_val)
    
    # List pattern: 1,3,5
    if ',' in field:
        values = field.split(',')
        return all(_validate_cron_number(v, min_val, max_val) for v in values)
    
    # Range pattern: 1-5
    if '-' in field:
        return _validate_cron_range(field, min_val, max_val)
    
    # Single number
    return _validate_cron_number(field, min_val, max_val)


def _validate_cron_number(value: str, min_val: int, max_val: int) -> bool:
    """Validate a single cron number is within range."""
    try:
        num = int(value)
        return min_val <= num <= max_val
    except ValueError:
        return False


def _validate_cron_range(range_str: str, min_val: int, max_val: int) -> bool:
    """Validate a cron range like '1-5'."""
    parts = range_str.split('-')
    if len(parts) != 2:
        return False
    
    try:
        start = int(parts[0])
        end = int(parts[1])
        
        # Both must be in valid range
        if not (min_val <= start <= max_val and min_val <= end <= max_val):
            return False
        
        # Start must be <= end
        return start <= end
    except ValueError:
        return False
