"""
Pydantic models for the API Key Manager.

Defines data models for API requests/responses and Redis JSON documents
for managing API keys and their associated metadata.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str
    message: str


# Request/Response Models for API endpoints

class ValidateKeyRequest(BaseModel):
    """Request model for POST /v1/validate-key"""
    api_key: str = Field(..., description="API key in format sk-proj.{project_id}.{key_id}.{secret}")


class ValidateKeyResponse(BaseModel):
    """Response model for successful key validation"""
    project_id: str
    key_id: str
    owner: str
    metadata: str


class MintKeyRequest(BaseModel):
    """Request model for POST /v1/mint-key (admin)"""
    project_id: str = Field(..., description="Project identifier")
    owner: str = Field(..., description="Key owner name")
    metadata: str = Field(..., description="Flexible metadata (can be server name, JSON, or any string)")
    expires_at: Optional[float] = Field(None, description="Unix timestamp when key expires")


class MintKeyResponse(BaseModel):
    """Response model for successful key minting"""
    api_key: str = Field(..., description="Generated API key")


class RevokeKeyRequest(BaseModel):
    """Request model for POST /v1/revoke-key (admin)"""
    project_id: str = Field(..., description="Project identifier")
    key_id: str = Field(..., description="Key identifier to revoke")


class RevokeKeyResponse(BaseModel):
    """Response model for successful key revocation"""
    revoked: bool


class KeyMetadata(BaseModel):
    """Key metadata for listing"""
    key_id: str
    owner: str
    metadata: str
    created_at: float
    disabled: bool
    expires_at: Optional[float] = None


class ListKeysResponse(BaseModel):
    """Response model for GET /v1/list-keys"""
    items: List[KeyMetadata]
    next: Optional[str] = None  # For pagination


# Redis JSON Document Models

class ProjectDocument(BaseModel):
    """Redis JSON document model for project:{project_id}"""
    model_config = ConfigDict(extra="forbid")
    
    project_id: str
    label: str
    owner: str
    created_at: float


class APIKeyDocument(BaseModel):
    """Redis JSON document model for apikey:{project_id}:{key_id}"""
    model_config = ConfigDict(extra="forbid")
    
    key_id: str
    project_id: str
    owner: str
    metadata: str
    secret_hash: str
    disabled: bool = False
    created_at: float
    expires_at: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if the key is expired."""
        if self.expires_at is None:
            return False
        return datetime.now().timestamp() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the key is valid (not disabled and not expired)."""
        return not self.disabled and not self.is_expired()


# Audit event for Redis Streams

class AuditEvent(BaseModel):
    """Audit event model for Redis Stream audit:keylookup"""
    ts: float = Field(default_factory=lambda: datetime.now().timestamp())
    project_id: str
    key_id: str
    result: str  # "ok", "denied", "rate_limited"
    client: str = "keymanager"
    
    def to_stream_fields(self) -> dict:
        """Convert to Redis Stream field format."""
        return {
            "ts": str(self.ts),
            "project_id": self.project_id,
            "key_id": self.key_id,
            "result": self.result,
            "client": self.client
        }


# Internal models

class ParsedAPIKey(BaseModel):
    """Parsed API key components"""
    project_id: str
    key_id: str
    secret: str
    
    @classmethod
    def parse(cls, api_key: str) -> "ParsedAPIKey":
        """Parse API key format: sk-proj.{project_id}.{key_id}.{secret}"""
        if not api_key.startswith("sk-proj."):
            raise ValueError("Invalid API key format")
        
        parts = api_key.split(".", 3)
        if len(parts) != 4:
            raise ValueError("Invalid API key format")
        
        return cls(
            project_id=parts[1],
            key_id=parts[2],
            secret=parts[3]
        )
    
    def format_key(self) -> str:
        """Format back to API key string"""
        return f"sk-proj.{self.project_id}.{self.key_id}.{self.secret}"
