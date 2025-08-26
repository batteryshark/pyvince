"""
Tests for security utilities.
"""

import pytest
import re

from src.security import PasswordManager, generate_key_id, generate_secret


class TestPasswordManager:
    """Test password hashing and verification."""
    
    def test_password_hashing(self):
        """Test password hashing."""
        pm = PasswordManager()
        password = "test_password_123"
        
        hash_str = pm.hash_password(password)
        
        # Should be an Argon2id hash
        assert hash_str.startswith("$argon2id$")
        assert len(hash_str) > 50  # Reasonable hash length
    
    def test_password_verification_success(self):
        """Test successful password verification."""
        pm = PasswordManager()
        password = "test_password_123"
        
        hash_str = pm.hash_password(password)
        
        # Verify correct password
        assert pm.verify_password(password, hash_str) is True
    
    def test_password_verification_failure(self):
        """Test failed password verification."""
        pm = PasswordManager()
        password = "test_password_123"
        wrong_password = "wrong_password"
        
        hash_str = pm.hash_password(password)
        
        # Verify wrong password
        assert pm.verify_password(wrong_password, hash_str) is False
    
    def test_password_verification_invalid_hash(self):
        """Test verification with invalid hash."""
        pm = PasswordManager()
        password = "test_password_123"
        invalid_hash = "invalid_hash_string"
        
        # Should return False for invalid hash
        assert pm.verify_password(password, invalid_hash) is False
    
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        pm = PasswordManager()
        password1 = "password1"
        password2 = "password2"
        
        hash1 = pm.hash_password(password1)
        hash2 = pm.hash_password(password2)
        
        assert hash1 != hash2
    
    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        pm = PasswordManager()
        password = "test_password_123"
        
        hash1 = pm.hash_password(password)
        hash2 = pm.hash_password(password)
        
        # Hashes should be different due to different salts
        assert hash1 != hash2
        
        # But both should verify the same password
        assert pm.verify_password(password, hash1) is True
        assert pm.verify_password(password, hash2) is True


class TestKeyGeneration:
    """Test key and secret generation functions."""
    
    def test_generate_key_id_format(self):
        """Test key ID generation format."""
        key_id = generate_key_id()
        
        # Should match pattern k_XXXXXXX (k_ followed by 7 alphanumeric chars)
        pattern = r"^k_[a-zA-Z0-9]{7}$"
        assert re.match(pattern, key_id)
    
    def test_generate_key_id_uniqueness(self):
        """Test that generated key IDs are unique."""
        key_ids = [generate_key_id() for _ in range(100)]
        
        # All should be unique
        assert len(set(key_ids)) == 100
    
    def test_generate_secret_default_length(self):
        """Test secret generation with default length."""
        secret = generate_secret()
        
        # Default length should be 32
        assert len(secret) == 32
        
        # Should only contain allowed characters
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        assert set(secret).issubset(allowed_chars)
    
    def test_generate_secret_custom_length(self):
        """Test secret generation with custom length."""
        length = 16
        secret = generate_secret(length)
        
        assert len(secret) == length
    
    def test_generate_secret_uniqueness(self):
        """Test that generated secrets are unique."""
        secrets = [generate_secret() for _ in range(100)]
        
        # All should be unique
        assert len(set(secrets)) == 100
    
    def test_generate_secret_randomness(self):
        """Test that generated secrets are sufficiently random."""
        secret = generate_secret(1000)  # Long secret for statistical analysis
        
        # Check character distribution
        char_counts = {}
        for char in secret:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # With 1000 characters and ~64 possible characters,
        # we expect roughly 15-16 of each on average
        # Allow for reasonable variation
        for count in char_counts.values():
            assert 5 <= count <= 30  # Reasonable range for randomness
