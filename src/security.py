"""
Security utilities for the API Key Manager.

Provides password hashing using Argon2id and other security functions.
"""

import secrets
import string
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class PasswordManager:
    """Manages password hashing and verification using Argon2id."""
    
    def __init__(self):
        # Using Argon2id with secure defaults
        # These parameters provide good security while maintaining reasonable performance
        self.hasher = PasswordHasher(
            time_cost=3,      # 3 iterations
            memory_cost=65536,  # 64 MB
            parallelism=1,    # 1 thread
            hash_len=32,      # 32 byte hash
            salt_len=16,      # 16 byte salt
        )
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using Argon2id.
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Argon2id hash string
        """
        return self.hasher.hash(password)
    
    def verify_password(self, password: str, hash_str: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            hash_str: Argon2id hash to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            self.hasher.verify(hash_str, password)
            return True
        except VerifyMismatchError:
            return False


def generate_key_id() -> str:
    """
    Generate a random key ID.
    
    Returns:
        Random alphanumeric key ID (e.g., "k_2J6Hqk3")
    """
    # Generate 7 random alphanumeric characters
    chars = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(chars) for _ in range(7))
    return f"k_{random_part}"


def generate_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure random secret.
    
    Args:
        length: Length of the secret in characters
        
    Returns:
        Random secret string
    """
    # Use URL-safe base64 characters for the secret
    chars = string.ascii_letters + string.digits + '-_'
    return ''.join(secrets.choice(chars) for _ in range(length))


# Global password manager instance
password_manager = PasswordManager()
