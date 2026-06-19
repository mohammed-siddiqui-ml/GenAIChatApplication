#!/usr/bin/env python3
"""
Test script for Loki logging configuration.

This script validates that the structured logging setup is working correctly
by checking log output format and required fields.
"""

import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from core.logging import CustomJsonFormatter, set_trace_id, set_user_id


def test_json_formatter():
    """Test that CustomJsonFormatter produces correct JSON output."""
    print("Testing CustomJsonFormatter...")
    
    # Create a logger with JSON formatter
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # Create handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set context
    trace_id = set_trace_id()
    set_user_id("test_user_123")
    
    print("\nSample log output:")
    print("-" * 80)
    
    # Generate test logs
    logger.info("Test INFO message")
    logger.warning("Test WARNING message")
    logger.error("Test ERROR message")
    
    print("-" * 80)
    print("✓ JSON formatter test complete\n")


def test_log_structure():
    """Test that log output contains all required fields."""
    print("Testing log structure...")
    
    # Create string stream to capture log output
    import io
    log_stream = io.StringIO()
    
    logger = logging.getLogger("structure_test")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    handler = logging.StreamHandler(log_stream)
    formatter = CustomJsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set context
    set_trace_id("test-trace-123")
    set_user_id("test-user-456")
    
    # Generate log
    logger.info("Test message", extra={"service": "fastapi"})
    
    # Parse log output
    log_output = log_stream.getvalue().strip()
    
    try:
        log_entry = json.loads(log_output)
        
        # Check required fields
        required_fields = [
            "timestamp",
            "level",
            "service",
            "message",
            "trace_id",
            "user_id",
            "environment",
            "application"
        ]
        
        missing_fields = [f for f in required_fields if f not in log_entry]
        
        if missing_fields:
            print(f"✗ Missing fields: {missing_fields}")
            return False
        
        print("✓ All required fields present:")
        for field in required_fields:
            value = log_entry.get(field, "")
            # Truncate long values for display
            display_value = str(value)[:50]
            print(f"  - {field}: {display_value}")
        
        print()
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ Log output is not valid JSON: {e}")
        print(f"Output: {log_output}")
        return False


def test_context_vars():
    """Test that context variables work correctly."""
    print("Testing context variables...")
    
    from core.logging import get_trace_id, get_user_id
    
    # Set values
    trace_id = set_trace_id("custom-trace-id")
    set_user_id("custom-user-id")
    
    # Get values
    retrieved_trace = get_trace_id()
    retrieved_user = get_user_id()
    
    # Verify
    assert retrieved_trace == "custom-trace-id", "Trace ID mismatch"
    assert retrieved_user == "custom-user-id", "User ID mismatch"
    
    print("✓ Context variables working correctly")
    print(f"  - Trace ID: {retrieved_trace}")
    print(f"  - User ID: {retrieved_user}")
    print()


def test_middleware_import():
    """Test that middleware can be imported."""
    print("Testing middleware imports...")
    
    try:
        from middleware.logging_middleware import LoggingMiddleware, CeleryLoggingContextFilter
        print("✓ LoggingMiddleware imported successfully")
        print("✓ CeleryLoggingContextFilter imported successfully")
        print()
        return True
    except ImportError as e:
        print(f"✗ Failed to import middleware: {e}")
        print()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("LOKI LOGGING CONFIGURATION TEST")
    print("=" * 80)
    print()
    
    tests = [
        ("Context Variables", test_context_vars),
        ("Log Structure", test_log_structure),
        ("Middleware Import", test_middleware_import),
        ("JSON Formatter", test_json_formatter),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result is not False:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            failed += 1
    
    print("=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
