"""
Tests for Redis client operations.
"""

import pytest
from datetime import datetime

from src.redis_client import RedisKeyManager
from src.models import APIKeyDocument, ProjectDocument, AuditEvent, ParsedAPIKey
from src.security import password_manager


class TestRedisKeyManager:
    """Test Redis key manager operations."""
    
    @pytest.mark.asyncio
    async def test_store_and_get_api_key(self, clean_redis: RedisKeyManager, sample_project: ProjectDocument):
        """Test storing and retrieving API key."""
        secret = "test_secret_123"
        secret_hash = password_manager.hash_password(secret)
        
        api_key_doc = APIKeyDocument(
            key_id="k_test123",
            project_id=sample_project.project_id,
            owner="Test User",
            server_name="test-server",
            secret_hash=secret_hash,
            disabled=False,
            created_at=datetime.now().timestamp(),
            expires_at=None
        )
        
        # Store API key
        success = await clean_redis.store_api_key(api_key_doc)
        assert success is True
        
        # Retrieve API key
        retrieved = await clean_redis.get_api_key(sample_project.project_id, "k_test123")
        assert retrieved is not None
        assert retrieved.key_id == "k_test123"
        assert retrieved.project_id == sample_project.project_id
        assert retrieved.owner == "Test User"
        assert retrieved.server_name == "test-server"
        assert retrieved.disabled is False
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_api_key(self, clean_redis: RedisKeyManager):
        """Test retrieving non-existent API key."""
        retrieved = await clean_redis.get_api_key("nonexistent", "k_nonexistent")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, clean_redis: RedisKeyManager, sample_api_key: APIKeyDocument):
        """Test revoking an API key."""
        # Revoke the key
        success = await clean_redis.revoke_api_key(sample_api_key.project_id, sample_api_key.key_id)
        assert success is True
        
        # Verify key is disabled
        retrieved = await clean_redis.get_api_key(sample_api_key.project_id, sample_api_key.key_id)
        assert retrieved is not None
        assert retrieved.disabled is True
    
    @pytest.mark.asyncio
    async def test_revoke_nonexistent_api_key(self, clean_redis: RedisKeyManager):
        """Test revoking non-existent API key."""
        success = await clean_redis.revoke_api_key("nonexistent", "k_nonexistent")
        assert success is False
    
    @pytest.mark.asyncio
    async def test_store_and_get_project(self, clean_redis: RedisKeyManager):
        """Test storing and retrieving project."""
        project_doc = ProjectDocument(
            project_id="test_project_2",
            label="Test Project 2",
            owner="Test Owner 2",
            created_at=datetime.now().timestamp()
        )
        
        # Store project
        success = await clean_redis.store_project(project_doc)
        assert success is True
        
        # Retrieve project
        retrieved = await clean_redis.get_project("test_project_2")
        assert retrieved is not None
        assert retrieved.project_id == "test_project_2"
        assert retrieved.label == "Test Project 2"
        assert retrieved.owner == "Test Owner 2"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self, clean_redis: RedisKeyManager):
        """Test retrieving non-existent project."""
        retrieved = await clean_redis.get_project("nonexistent")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_list_project_keys(self, clean_redis: RedisKeyManager, sample_project: ProjectDocument):
        """Test listing API keys for a project."""
        # Create multiple API keys
        for i in range(3):
            secret_hash = password_manager.hash_password(f"secret_{i}")
            api_key_doc = APIKeyDocument(
                key_id=f"k_test{i}",
                project_id=sample_project.project_id,
                owner=f"User {i}",
                server_name=f"server-{i}",
                secret_hash=secret_hash,
                disabled=False,
                created_at=datetime.now().timestamp(),
                expires_at=None
            )
            await clean_redis.store_api_key(api_key_doc)
        
        # List keys
        keys = await clean_redis.list_project_keys(sample_project.project_id)
        assert len(keys) == 3
        
        # Verify key IDs
        key_ids = {key.key_id for key in keys}
        assert key_ids == {"k_test0", "k_test1", "k_test2"}
    
    @pytest.mark.asyncio
    async def test_list_project_keys_pagination(self, clean_redis: RedisKeyManager, sample_project: ProjectDocument):
        """Test listing API keys with pagination."""
        # Create 5 API keys
        for i in range(5):
            secret_hash = password_manager.hash_password(f"secret_{i}")
            api_key_doc = APIKeyDocument(
                key_id=f"k_page{i}",
                project_id=sample_project.project_id,
                owner=f"User {i}",
                server_name=f"server-{i}",
                secret_hash=secret_hash,
                disabled=False,
                created_at=datetime.now().timestamp(),
                expires_at=None
            )
            await clean_redis.store_api_key(api_key_doc)
        
        # Get first page
        keys_page1 = await clean_redis.list_project_keys(sample_project.project_id, offset=0, limit=3)
        assert len(keys_page1) == 3
        
        # Get second page
        keys_page2 = await clean_redis.list_project_keys(sample_project.project_id, offset=3, limit=3)
        assert len(keys_page2) == 2  # Only 2 remaining
        
        # Verify no overlap
        page1_ids = {key.key_id for key in keys_page1}
        page2_ids = {key.key_id for key in keys_page2}
        assert page1_ids.isdisjoint(page2_ids)
    
    @pytest.mark.asyncio
    async def test_log_audit_event(self, clean_redis: RedisKeyManager):
        """Test logging audit events."""
        event = AuditEvent(
            project_id="test_project",
            key_id="k_test123",
            result="ok"
        )
        
        success = await clean_redis.log_audit_event(event)
        assert success is True
        
        # Verify event was stored in stream
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        assert stream_name == "audit:keylookup"
        assert len(entries) == 1
        
        entry_id, fields = entries[0]
        assert fields["project_id"] == "test_project"
        assert fields["key_id"] == "k_test123"
        assert fields["result"] == "ok"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, clean_redis: RedisKeyManager):
        """Test rate limiting - requests within limit."""
        project_id = "test_project"
        key_id = "k_test123"
        
        # Make requests within limit
        for i in range(5):
            allowed = await clean_redis.check_rate_limit(project_id, key_id, limit_per_minute=10)
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, clean_redis: RedisKeyManager):
        """Test rate limiting - requests exceed limit."""
        project_id = "test_project"
        key_id = "k_test123"
        limit = 3
        
        # Make requests up to limit
        for i in range(limit):
            allowed = await clean_redis.check_rate_limit(project_id, key_id, limit_per_minute=limit)
            assert allowed is True
        
        # Next request should be rate limited
        allowed = await clean_redis.check_rate_limit(project_id, key_id, limit_per_minute=limit)
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_update_key_usage(self, clean_redis: RedisKeyManager):
        """Test updating key usage metadata."""
        project_id = "test_project"
        key_id = "k_test123"
        
        # Update usage multiple times
        for i in range(3):
            await clean_redis.update_key_usage(project_id, key_id)
        
        # Check usage count
        meta_key = clean_redis._apimeta_key(project_id, key_id)
        usage_count = clean_redis.client.hget(meta_key, "usage_count")
        last_used = clean_redis.client.hget(meta_key, "last_used")
        
        assert int(usage_count) == 3
        assert last_used is not None  # Should have a timestamp
    
    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, clean_redis: RedisKeyManager, sample_api_key: APIKeyDocument):
        """Test complete API key validation - success case."""
        # Create API key string
        parsed_key = ParsedAPIKey(
            project_id=sample_api_key.project_id,
            key_id=sample_api_key.key_id,
            secret=sample_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is not None
        assert result.key_id == sample_api_key.key_id
        assert result.project_id == sample_api_key.project_id
        
        # Check audit log
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        entry_id, fields = entries[0]
        assert fields["result"] == "ok"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_wrong_secret(self, clean_redis: RedisKeyManager, sample_api_key: APIKeyDocument):
        """Test API key validation with wrong secret."""
        # Create API key string with wrong secret
        parsed_key = ParsedAPIKey(
            project_id=sample_api_key.project_id,
            key_id=sample_api_key.key_id,
            secret="wrong_secret"
        )
        api_key = parsed_key.format_key()
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is None
        
        # Check audit log shows denial
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        entry_id, fields = entries[0]
        assert fields["result"] == "denied"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_disabled(self, clean_redis: RedisKeyManager, disabled_api_key: APIKeyDocument):
        """Test API key validation with disabled key."""
        # Create API key string
        parsed_key = ParsedAPIKey(
            project_id=disabled_api_key.project_id,
            key_id=disabled_api_key.key_id,
            secret=disabled_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is None
        
        # Check audit log shows denial
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        entry_id, fields = entries[0]
        assert fields["result"] == "denied"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_expired(self, clean_redis: RedisKeyManager, expired_api_key: APIKeyDocument):
        """Test API key validation with expired key."""
        # Create API key string
        parsed_key = ParsedAPIKey(
            project_id=expired_api_key.project_id,
            key_id=expired_api_key.key_id,
            secret=expired_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is None
        
        # Check audit log shows denial
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        entry_id, fields = entries[0]
        assert fields["result"] == "denied"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_nonexistent(self, clean_redis: RedisKeyManager):
        """Test API key validation with non-existent key."""
        api_key = "sk-proj.nonexistent.k_nonexistent.secret"
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is None
        
        # Check audit log shows denial
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 1
        
        stream_name, entries = stream_entries[0]
        entry_id, fields = entries[0]
        assert fields["result"] == "denied"
    
    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_format(self, clean_redis: RedisKeyManager):
        """Test API key validation with invalid format."""
        api_key = "invalid-format-key"
        
        # Validate
        result = await clean_redis.validate_api_key(api_key)
        
        assert result is None
        
        # Should not create audit log for invalid format
        stream_entries = clean_redis.client.xread(streams={"audit:keylookup": "0"})
        assert len(stream_entries) == 0
