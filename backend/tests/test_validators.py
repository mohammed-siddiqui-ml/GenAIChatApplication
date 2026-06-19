"""
Tests for Validation Utilities (Task-026)

This test module validates:
- URL format validation (HTTP/HTTPS)
- HTTPS requirement validation
- Cron expression validation (5-field format)
- Cron field validation (wildcards, ranges, lists, steps)
"""

import pytest
from utils.validators import (
    validate_url,
    validate_cron_expression,
    _validate_cron_field,
    _validate_cron_number,
    _validate_cron_range,
    ValidationError
)


# ========== URL Validation Tests ==========

def test_validate_url_https():
    """TC-B1: Validate HTTPS URLs."""
    assert validate_url("https://confluence.example.com") is True
    assert validate_url("https://api.example.com/path") is True
    assert validate_url("https://wiki.company.com") is True


def test_validate_url_http():
    """TC-B1: Validate HTTP URLs."""
    assert validate_url("http://jira.example.com") is True
    assert validate_url("http://localhost:8080") is True
    assert validate_url("http://192.168.1.1") is True


def test_validate_url_with_path():
    """TC-B1: Validate URLs with paths and query params."""
    assert validate_url("https://wiki.company.com/path/to/page") is True
    assert validate_url("https://api.example.com/v1/endpoint?param=value") is True


def test_validate_url_invalid_format():
    """TC-B2: Reject invalid URL formats."""
    assert validate_url("not-a-url") is False
    assert validate_url("invalid") is False
    assert validate_url("just-text") is False


def test_validate_url_invalid_scheme():
    """TC-B2: Reject URLs with invalid schemes."""
    assert validate_url("ftp://invalid.com") is False
    assert validate_url("ssh://example.com") is False
    assert validate_url("file:///path/to/file") is False


def test_validate_url_empty():
    """TC-B2: Reject empty URLs."""
    assert validate_url("") is False
    assert validate_url(None) is False


def test_validate_url_https_required():
    """TC-B6: Enforce HTTPS requirement when specified."""
    assert validate_url("https://example.com", require_https=True) is True
    assert validate_url("http://example.com", require_https=True) is False


def test_validate_url_missing_netloc():
    """TC-B2: Reject URLs without netloc."""
    assert validate_url("https://") is False
    assert validate_url("http://") is False


# ========== Cron Expression Validation Tests ==========

def test_validate_cron_daily():
    """TC-B3: Validate daily cron expression."""
    assert validate_cron_expression("0 2 * * *") is True  # Daily at 2 AM


def test_validate_cron_every_15_minutes():
    """TC-B3: Validate cron with step pattern."""
    assert validate_cron_expression("*/15 * * * *") is True  # Every 15 minutes


def test_validate_cron_yearly():
    """TC-B3: Validate yearly cron expression."""
    assert validate_cron_expression("0 0 1 1 *") is True  # Jan 1 at midnight


def test_validate_cron_weekdays():
    """TC-B4: Validate cron with ranges."""
    assert validate_cron_expression("30 9-17 * * 1-5") is True  # Weekdays 9:30 AM - 5:30 PM


def test_validate_cron_every_2_hours():
    """TC-B4: Validate cron with hour steps."""
    assert validate_cron_expression("0 */2 * * *") is True  # Every 2 hours


def test_validate_cron_list_pattern():
    """TC-B4: Validate cron with list pattern."""
    assert validate_cron_expression("0,30 * * * *") is True  # Every hour at :00 and :30


def test_validate_cron_invalid_field_count():
    """TC-B5: Reject cron with wrong field count."""
    assert validate_cron_expression("0 2 * *") is False  # 4 fields instead of 5
    assert validate_cron_expression("0 2 * * * *") is False  # 6 fields instead of 5


def test_validate_cron_minute_out_of_range():
    """TC-B5: Reject cron with minute out of range."""
    assert validate_cron_expression("60 2 * * *") is False  # Minute must be 0-59


def test_validate_cron_hour_out_of_range():
    """TC-B5: Reject cron with hour out of range."""
    assert validate_cron_expression("0 25 * * *") is False  # Hour must be 0-23
    assert validate_cron_expression("0 24 * * *") is False  # Hour must be 0-23


def test_validate_cron_day_out_of_range():
    """TC-B5: Reject cron with day out of range."""
    assert validate_cron_expression("0 0 32 * *") is False  # Day must be 1-31
    assert validate_cron_expression("0 0 0 * *") is False  # Day must be 1-31


def test_validate_cron_month_out_of_range():
    """TC-B5: Reject cron with month out of range."""
    assert validate_cron_expression("0 0 1 13 *") is False  # Month must be 1-12
    assert validate_cron_expression("0 0 1 0 *") is False  # Month must be 1-12


def test_validate_cron_weekday_out_of_range():
    """TC-B5: Reject cron with weekday out of range."""
    assert validate_cron_expression("0 0 * * 7") is False  # Weekday must be 0-6


def test_validate_cron_invalid_format():
    """TC-B5: Reject invalid cron format."""
    assert validate_cron_expression("invalid") is False
    assert validate_cron_expression("not a cron") is False
    assert validate_cron_expression("abc def ghi jkl mno") is False


def test_validate_cron_empty():
    """TC-B5: Reject empty cron expression."""
    assert validate_cron_expression("") is False
    assert validate_cron_expression(None) is False


# ========== Cron Field Validation Tests ==========

def test_validate_cron_field_wildcard():
    """TC-B4: Validate wildcard field."""
    assert _validate_cron_field("*", 0, 59) is True


def test_validate_cron_field_number():
    """TC-B4: Validate single number field."""
    assert _validate_cron_field("30", 0, 59) is True
    assert _validate_cron_field("0", 0, 23) is True


def test_validate_cron_field_range():
    """TC-B4: Validate range field."""
    assert _validate_cron_field("1-5", 0, 6) is True
    assert _validate_cron_field("9-17", 0, 23) is True


def test_validate_cron_field_list():
    """TC-B4: Validate list field."""
    assert _validate_cron_field("0,15,30,45", 0, 59) is True
    assert _validate_cron_field("1,3,5", 1, 31) is True


def test_validate_cron_field_step():
    """TC-B4: Validate step field."""
    assert _validate_cron_field("*/5", 0, 59) is True
    assert _validate_cron_field("*/10", 0, 23) is True


def test_validate_cron_number_valid():
    """Validate number within range."""
    assert _validate_cron_number("30", 0, 59) is True
    assert _validate_cron_number("0", 0, 23) is True


def test_validate_cron_number_out_of_range():
    """Reject number out of range."""
    assert _validate_cron_number("60", 0, 59) is False
    assert _validate_cron_number("-1", 0, 23) is False


def test_validate_cron_range_valid():
    """Validate valid range."""
    assert _validate_cron_range("1-5", 0, 6) is True
    assert _validate_cron_range("0-23", 0, 23) is True
