"""
Cryptographic Utilities for Data Encryption

This module provides AES-256 encryption/decryption utilities for securing
sensitive configuration data like API tokens and credentials.
"""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.config import settings

# Logger
logger = logging.getLogger(__name__)


class CryptoError(Exception):
    """Custom exception for cryptographic operations."""
    pass


def _get_encryption_key() -> bytes:
    """
    Derive a Fernet-compatible encryption key from the SECRET_KEY.
    
    Uses PBKDF2 to derive a 32-byte key from the application's SECRET_KEY,
    ensuring consistent encryption/decryption across application restarts.
    
    Returns:
        bytes: Base64-encoded Fernet encryption key
    """
    # Use a fixed salt derived from project name for consistency
    # In production, this should ideally be stored securely
    salt = settings.PROJECT_NAME.encode()[:16].ljust(16, b'\0')

    # Derive key using PBKDF2HMAC
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return key


def encrypt_config_field(plaintext: str) -> str:
    """
    Encrypt a sensitive configuration field using AES-256.
    
    Uses Fernet (AES-256-CBC with HMAC authentication) to encrypt
    sensitive data like API tokens, passwords, and credentials.
    
    Args:
        plaintext: Plain text string to encrypt
        
    Returns:
        str: Base64-encoded encrypted string
        
    Raises:
        CryptoError: If encryption fails
        
    Example:
        >>> encrypted = encrypt_config_field("my-api-token-12345")
        >>> decrypted = decrypt_config_field(encrypted)
        >>> assert decrypted == "my-api-token-12345"
    """
    if not plaintext:
        return plaintext
    
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = f.encrypt(plaintext.encode('utf-8'))
        encrypted_str = encrypted_bytes.decode('utf-8')
        logger.debug("Configuration field encrypted successfully")
        return encrypted_str
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}")
        raise CryptoError(f"Failed to encrypt configuration field: {str(e)}")


def decrypt_config_field(encrypted: str) -> str:
    """
    Decrypt a sensitive configuration field encrypted with AES-256.
    
    Decrypts data previously encrypted with encrypt_config_field().
    
    Args:
        encrypted: Base64-encoded encrypted string
        
    Returns:
        str: Decrypted plain text string
        
    Raises:
        CryptoError: If decryption fails (invalid key, corrupted data, etc.)
    """
    if not encrypted:
        return encrypted
    
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted_bytes = f.decrypt(encrypted.encode('utf-8'))
        decrypted_str = decrypted_bytes.decode('utf-8')
        logger.debug("Configuration field decrypted successfully")
        return decrypted_str
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}")
        raise CryptoError(f"Failed to decrypt configuration field: {str(e)}")


def encrypt_config_dict(config: dict, sensitive_fields: list[str]) -> dict:
    """
    Encrypt sensitive fields in a configuration dictionary.
    
    Creates a copy of the config dict and encrypts specified sensitive fields.
    Non-sensitive fields and missing fields are left unchanged.
    
    Args:
        config: Configuration dictionary
        sensitive_fields: List of field names to encrypt
        
    Returns:
        dict: New dictionary with encrypted sensitive fields
        
    Example:
        >>> config = {"url": "https://api.example.com", "api_token": "secret123"}
        >>> encrypted = encrypt_config_dict(config, ["api_token"])
        >>> encrypted["url"] == "https://api.example.com"
        True
        >>> encrypted["api_token"] != "secret123"
        True
    """
    if not config:
        return config
    
    encrypted_config = config.copy()
    for field in sensitive_fields:
        if field in encrypted_config and encrypted_config[field]:
            encrypted_config[field] = encrypt_config_field(str(encrypted_config[field]))
    
    return encrypted_config


def decrypt_config_dict(config: dict, sensitive_fields: list[str]) -> dict:
    """
    Decrypt sensitive fields in a configuration dictionary.
    
    Creates a copy of the config dict and decrypts specified sensitive fields.
    
    Args:
        config: Configuration dictionary with encrypted fields
        sensitive_fields: List of field names to decrypt
        
    Returns:
        dict: New dictionary with decrypted sensitive fields
    """
    if not config:
        return config
    
    decrypted_config = config.copy()
    for field in sensitive_fields:
        if field in decrypted_config and decrypted_config[field]:
            decrypted_config[field] = decrypt_config_field(str(decrypted_config[field]))
    
    return decrypted_config
