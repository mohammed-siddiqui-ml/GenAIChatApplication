"""
Tests for Cryptographic Utilities (Task-026)

This test module validates:
- AES-256 encryption/decryption of sensitive fields
- Key derivation consistency
- Config dict encryption/decryption
- Error handling for invalid encrypted data
"""

import pytest
from utils.crypto import (
    encrypt_config_field,
    decrypt_config_field,
    encrypt_config_dict,
    decrypt_config_dict,
    CryptoError,
    _get_encryption_key
)


# ========== Test Data ==========

TEST_PLAINTEXT = "my-secret-token-12345"
TEST_CONFIG = {
    "url": "https://api.example.com",
    "api_token": "secret123",
    "username": "admin@example.com",
    "password": "pass456"
}
SENSITIVE_FIELDS = ["api_token", "password"]


# ========== Encryption/Decryption Tests ==========

def test_encrypt_config_field():
    """TC-A1: Encrypt a sensitive configuration field."""
    encrypted = encrypt_config_field(TEST_PLAINTEXT)
    
    # Verify encrypted value is not equal to plaintext
    assert encrypted != TEST_PLAINTEXT, "Encrypted value should differ from plaintext"
    
    # Verify encrypted value is a non-empty string
    assert isinstance(encrypted, str), "Encrypted value should be a string"
    assert len(encrypted) > 0, "Encrypted value should not be empty"
    
    # Fernet uses base64 encoding, check for base64-like pattern
    assert encrypted.startswith("gAAAAA"), "Fernet encrypted strings typically start with 'gAAAAA'"


def test_decrypt_config_field():
    """TC-A1: Decrypt a configuration field (round-trip test)."""
    encrypted = encrypt_config_field(TEST_PLAINTEXT)
    decrypted = decrypt_config_field(encrypted)
    
    # Verify decrypted value matches original
    assert decrypted == TEST_PLAINTEXT, "Decrypted value should match original plaintext"


def test_encrypt_decrypt_round_trip():
    """TC-A1: Verify encryption/decryption round-trip consistency."""
    original = "my-api-token-67890"
    
    # Encrypt
    encrypted = encrypt_config_field(original)
    assert encrypted != original
    
    # Decrypt
    decrypted = decrypt_config_field(encrypted)
    assert decrypted == original


def test_encrypt_config_field_empty_string():
    """TC-A4: Handle empty string gracefully."""
    result = encrypt_config_field("")
    assert result == "", "Empty string should remain empty"


def test_decrypt_config_field_empty_string():
    """TC-A4: Handle empty string decryption gracefully."""
    result = decrypt_config_field("")
    assert result == "", "Empty string should remain empty"


def test_key_derivation_consistency():
    """TC-A3: Verify key derivation is consistent across calls."""
    key1 = _get_encryption_key()
    key2 = _get_encryption_key()
    
    assert key1 == key2, "Key derivation should be deterministic (same key each time)"


def test_encrypt_config_dict():
    """TC-A2: Encrypt sensitive fields in configuration dictionary."""
    config = TEST_CONFIG.copy()
    encrypted_config = encrypt_config_dict(config, SENSITIVE_FIELDS)
    
    # Verify non-sensitive fields remain unchanged
    assert encrypted_config["url"] == config["url"], "Non-sensitive fields should remain unchanged"
    assert encrypted_config["username"] == config["username"], "Non-sensitive fields should remain unchanged"
    
    # Verify sensitive fields are encrypted
    assert encrypted_config["api_token"] != config["api_token"], "api_token should be encrypted"
    assert encrypted_config["password"] != config["password"], "password should be encrypted"
    
    # Verify encrypted values are strings
    assert isinstance(encrypted_config["api_token"], str), "Encrypted api_token should be string"
    assert isinstance(encrypted_config["password"], str), "Encrypted password should be string"


def test_decrypt_config_dict():
    """TC-A2: Decrypt sensitive fields in configuration dictionary."""
    config = TEST_CONFIG.copy()
    
    # Encrypt first
    encrypted_config = encrypt_config_dict(config, SENSITIVE_FIELDS)
    
    # Decrypt
    decrypted_config = decrypt_config_dict(encrypted_config, SENSITIVE_FIELDS)
    
    # Verify all fields match original
    assert decrypted_config["url"] == config["url"]
    assert decrypted_config["username"] == config["username"]
    assert decrypted_config["api_token"] == config["api_token"]
    assert decrypted_config["password"] == config["password"]


def test_encrypt_config_dict_missing_field():
    """TC-A2: Handle missing sensitive field gracefully."""
    config = {"url": "https://example.com", "username": "user"}
    encrypted_config = encrypt_config_dict(config, ["api_token"])
    
    # Should not raise error, just skip missing field
    assert encrypted_config["url"] == config["url"]
    assert encrypted_config["username"] == config["username"]
    assert "api_token" not in encrypted_config


def test_encrypt_config_dict_none_value():
    """TC-A4: Handle None values in config dict."""
    config = {"url": "https://example.com", "api_token": None}
    encrypted_config = encrypt_config_dict(config, ["api_token"])
    
    # None should remain None (not encrypted)
    assert encrypted_config["api_token"] is None


def test_decrypt_invalid_data():
    """TC-A2: Verify decryption of invalid data raises CryptoError."""
    with pytest.raises(CryptoError):
        decrypt_config_field("invalid-encrypted-data-not-base64")


def test_encryption_different_from_plaintext():
    """TC-A5: Verify encrypted output is different from plaintext."""
    plaintext = "my-secret-value"
    encrypted = encrypt_config_field(plaintext)
    
    assert encrypted != plaintext, "Encrypted value must differ from plaintext"
    assert len(encrypted) > len(plaintext), "Encrypted value typically longer due to encoding"
