"""
Tests for Pydantic models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.models import (
    APIKeyDocument, ProjectDocument, AuditEvent, ParsedAPIKey,
    ValidateKeyRequest, MintKeyRequest, RevokeKeyRequest
)


class TestAPIKeyDocument:
    """Test APIKeyDocument model."""
    
    def test_valid_api_key_document(self):
        """Test creating a valid API key document."""
        doc = APIKeyDocument(
            key_id="k_test123",
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            secret_hash="argon2id$...",
            disabled=False,
            created_at=datetime.now().timestamp(),
            expires_at=None
        )
        
        assert doc.key_id == "k_test123"
        assert doc.project_id == "test_project"
        assert doc.disabled is False
        assert doc.expires_at is None
    
    def test_api_key_document_with_expiry(self):
        """Test API key document with expiry time."""
        future_time = datetime.now().timestamp() + 3600  # 1 hour from now
        
        doc = APIKeyDocument(
            key_id="k_test123",
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            secret_hash="argon2id$...",
            disabled=False,
            created_at=datetime.now().timestamp(),
            expires_at=future_time
        )
        
        assert doc.expires_at == future_time
        assert not doc.is_expired()
        assert doc.is_valid()
    
    def test_expired_api_key(self):
        """Test expired API key detection."""
        past_time = datetime.now().timestamp() - 3600  # 1 hour ago
        
        doc = APIKeyDocument(
            key_id="k_test123",
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            secret_hash="argon2id$...",
            disabled=False,
            created_at=datetime.now().timestamp(),
            expires_at=past_time
        )
        
        assert doc.is_expired()
        assert not doc.is_valid()
    
    def test_disabled_api_key(self):
        """Test disabled API key detection."""
        doc = APIKeyDocument(
            key_id="k_test123",
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            secret_hash="argon2id$...",
            disabled=True,
            created_at=datetime.now().timestamp(),
            expires_at=None
        )
        
        assert not doc.is_valid()
    
    def test_invalid_extra_field(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            APIKeyDocument(
                key_id="k_test123",
                project_id="test_project",
                owner="Test User",
                server_name="test-server",
                secret_hash="argon2id$...",
                disabled=False,
                created_at=datetime.now().timestamp(),
                expires_at=None,
                extra_field="not_allowed"  # This should fail
            )


class TestProjectDocument:
    """Test ProjectDocument model."""
    
    def test_valid_project_document(self):
        """Test creating a valid project document."""
        doc = ProjectDocument(
            project_id="test_project",
            label="Test Project",
            owner="Test Owner",
            created_at=datetime.now().timestamp()
        )
        
        assert doc.project_id == "test_project"
        assert doc.label == "Test Project"
        assert doc.owner == "Test Owner"
    
    def test_invalid_extra_field(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            ProjectDocument(
                project_id="test_project",
                label="Test Project",
                owner="Test Owner",
                created_at=datetime.now().timestamp(),
                extra_field="not_allowed"  # This should fail
            )


class TestParsedAPIKey:
    """Test ParsedAPIKey model."""
    
    def test_valid_api_key_parsing(self):
        """Test parsing a valid API key."""
        api_key = "sk-proj.test_project.k_abc123.secret_xyz"
        
        parsed = ParsedAPIKey.parse(api_key)
        
        assert parsed.project_id == "test_project"
        assert parsed.key_id == "k_abc123"
        assert parsed.secret == "secret_xyz"
    
    def test_format_api_key(self):
        """Test formatting API key back to string."""
        parsed = ParsedAPIKey(
            project_id="test_project",
            key_id="k_abc123",
            secret="secret_xyz"
        )
        
        formatted = parsed.format_key()
        assert formatted == "sk-proj.test_project.k_abc123.secret_xyz"
    
    def test_invalid_api_key_prefix(self):
        """Test parsing API key with invalid prefix."""
        api_key = "invalid.test_project.k_abc123.secret_xyz"
        
        with pytest.raises(ValueError, match="Invalid API key format"):
            ParsedAPIKey.parse(api_key)
    
    def test_invalid_api_key_parts(self):
        """Test parsing API key with wrong number of parts."""
        api_key = "sk-proj.test_project.k_abc123"  # Missing secret
        
        with pytest.raises(ValueError, match="Invalid API key format"):
            ParsedAPIKey.parse(api_key)


class TestAuditEvent:
    """Test AuditEvent model."""
    
    def test_audit_event_creation(self):
        """Test creating an audit event."""
        event = AuditEvent(
            project_id="test_project",
            key_id="k_test123",
            result="ok"
        )
        
        assert event.project_id == "test_project"
        assert event.key_id == "k_test123"
        assert event.result == "ok"
        assert event.client == "keymanager"
        assert isinstance(event.ts, float)
    
    def test_audit_event_stream_fields(self):
        """Test converting audit event to stream fields."""
        event = AuditEvent(
            ts=1234567890.123,
            project_id="test_project",
            key_id="k_test123",
            result="denied"
        )
        
        fields = event.to_stream_fields()
        
        assert fields["ts"] == "1234567890.123"
        assert fields["project_id"] == "test_project"
        assert fields["key_id"] == "k_test123"
        assert fields["result"] == "denied"
        assert fields["client"] == "keymanager"


class TestRequestModels:
    """Test API request models."""
    
    def test_validate_key_request(self):
        """Test ValidateKeyRequest model."""
        request = ValidateKeyRequest(
            api_key="sk-proj.test_project.k_abc123.secret_xyz"
        )
        
        assert request.api_key == "sk-proj.test_project.k_abc123.secret_xyz"
    
    def test_mint_key_request(self):
        """Test MintKeyRequest model."""
        request = MintKeyRequest(
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            expires_at=None
        )
        
        assert request.project_id == "test_project"
        assert request.owner == "Test User"
        assert request.server_name == "test-server"
        assert request.expires_at is None
    
    def test_mint_key_request_with_expiry(self):
        """Test MintKeyRequest model with expiry."""
        future_time = datetime.now().timestamp() + 3600
        
        request = MintKeyRequest(
            project_id="test_project",
            owner="Test User",
            server_name="test-server",
            expires_at=future_time
        )
        
        assert request.expires_at == future_time
    
    def test_revoke_key_request(self):
        """Test RevokeKeyRequest model."""
        request = RevokeKeyRequest(
            project_id="test_project",
            key_id="k_abc123"
        )
        
        assert request.project_id == "test_project"
        assert request.key_id == "k_abc123"
