"""
API Key Manager - FastAPI Application

Provides key validation, minting, revocation, and listing endpoints
for managing API keys with flexible metadata.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import (
    ValidateKeyRequest, ValidateKeyResponse,
    MintKeyRequest, MintKeyResponse,
    RevokeKeyRequest, RevokeKeyResponse,
    ListKeysResponse, KeyMetadata,
    ErrorResponse, ErrorDetail,
    APIKeyDocument, ProjectDocument,
    ParsedAPIKey
)
from .redis_client import RedisKeyManager
from .security import generate_key_id, generate_secret, password_manager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global Redis clients - separate for validation vs admin operations
redis_validator: Optional[RedisKeyManager] = None  # Read-only for /v1/validate-key
redis_admin: Optional[RedisKeyManager] = None     # Read-write for admin operations

# Admin authentication
ADMIN_SECRET = os.getenv("ADMIN_SECRET")
security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global redis_validator, redis_admin
    
    # Startup
    logger.info("Starting API Key Manager")
    
    # Initialize Redis clients with different permissions
    redis_validator = RedisKeyManager(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_VALIDATOR_PASSWORD"),
        username=os.getenv("REDIS_VALIDATOR_USERNAME", "validator"),
        db=int(os.getenv("REDIS_DB", "0"))
    )
    
    redis_admin = RedisKeyManager(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_MANAGER_PASSWORD"),
        username=os.getenv("REDIS_MANAGER_USERNAME", "manager"),
        db=int(os.getenv("REDIS_DB", "0"))
    )
    
    # Test Redis connections
    if not redis_validator.ping():
        logger.error("Failed to connect to Redis with validator credentials")
        raise RuntimeError("Redis validator connection failed")
    
    if not redis_admin.ping():
        logger.error("Failed to connect to Redis with admin credentials")
        raise RuntimeError("Redis admin connection failed")
    
    logger.info("Successfully connected to Redis with both validator and admin credentials")
    
    # Check admin secret configuration
    if not ADMIN_SECRET:
        logger.warning("ADMIN_SECRET not set - admin endpoints will be disabled")
    else:
        logger.info("Admin authentication configured")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Key Manager")


# Create FastAPI application
app = FastAPI(
    title="API Key Manager",
    description="API key validation and management service with flexible metadata",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Create standardized error response."""
    error_response = ErrorResponse(
        error=ErrorDetail(code=code, message=message)
    )
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )


async def verify_admin_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Verify admin authentication using Bearer token.
    
    The token should match the ADMIN_SECRET environment variable.
    """
    if not ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are disabled (ADMIN_SECRET not configured)"
        )
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if credentials.credentials != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True



@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not redis_validator or not redis_validator.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection failed"
        )
    
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/v1/validate-key", response_model=ValidateKeyResponse)
async def validate_key(request: ValidateKeyRequest):
    """
    Validate an API key and return associated metadata.
    
    This is the primary endpoint for validating client API keys 
    and retrieving the associated metadata for routing or other purposes.
    """
    try:
        # Validate the API key (using read-only client)
        api_key_doc = await redis_validator.validate_api_key(request.api_key)
        
        if api_key_doc is None:
            return create_error_response(
                code="invalid_key",
                message="Invalid or expired API key",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Return success response
        return ValidateKeyResponse(
            project_id=api_key_doc.project_id,
            key_id=api_key_doc.key_id,
            owner=api_key_doc.owner,
            metadata=api_key_doc.metadata
        )
        
    except Exception as e:
        logger.error(f"Error in validate_key: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post("/v1/mint-key", response_model=MintKeyResponse)
async def mint_key(request: MintKeyRequest, _: bool = Depends(verify_admin_auth)):
    """
    Mint a new API key (admin operation).
    
    Creates a new API key for the specified project with the given parameters.
    """
    try:
        # Generate new key components
        key_id = generate_key_id()
        secret = generate_secret()
        secret_hash = password_manager.hash_password(secret)
        
        # Create API key document
        current_time = datetime.now().timestamp()
        api_key_doc = APIKeyDocument(
            key_id=key_id,
            project_id=request.project_id,
            owner=request.owner,
            metadata=request.metadata,
            secret_hash=secret_hash,
            disabled=False,
            created_at=current_time,
            expires_at=request.expires_at
        )
        
        # Store in Redis (using admin client)
        if not await redis_admin.store_api_key(api_key_doc):
            return create_error_response(
                code="storage_error",
                message="Failed to store API key",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Format the API key for return
        parsed_key = ParsedAPIKey(
            project_id=request.project_id,
            key_id=key_id,
            secret=secret
        )
        api_key = parsed_key.format_key()
        
        logger.info(f"Minted new API key for project {request.project_id}, key {key_id}")
        
        return MintKeyResponse(api_key=api_key)
        
    except Exception as e:
        logger.error(f"Error in mint_key: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.post("/v1/revoke-key", response_model=RevokeKeyResponse)
async def revoke_key(request: RevokeKeyRequest, _: bool = Depends(verify_admin_auth)):
    """
    Revoke an API key (admin operation).
    
    Disables the specified API key to prevent future use.
    """
    try:
        # Check if key exists
        api_key_doc = await redis_admin.get_api_key(request.project_id, request.key_id)
        if api_key_doc is None:
            return create_error_response(
                code="key_not_found",
                message="API key not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Revoke the key (using admin client)
        if not await redis_admin.revoke_api_key(request.project_id, request.key_id):
            return create_error_response(
                code="revocation_error",
                message="Failed to revoke API key",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"Revoked API key for project {request.project_id}, key {request.key_id}")
        
        return RevokeKeyResponse(revoked=True)
        
    except Exception as e:
        logger.error(f"Error in revoke_key: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/v1/list-keys", response_model=ListKeysResponse)
async def list_keys(
    project_id: str = Query(..., description="Project ID to list keys for"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of keys to return"),
    _: bool = Depends(verify_admin_auth)
):
    """
    List API keys for a project (admin operation).
    
    Returns metadata for all API keys belonging to the specified project.
    """
    try:
        # Retrieve API keys for the project
        api_key_docs = await redis_admin.list_project_keys(project_id, offset, limit)
        
        # Convert to metadata format (without secrets)
        items = []
        for doc in api_key_docs:
            key_metadata = KeyMetadata(
                key_id=doc.key_id,
                owner=doc.owner,
                metadata=doc.metadata,
                created_at=doc.created_at,
                disabled=doc.disabled,
                expires_at=doc.expires_at
            )
            items.append(key_metadata)
        
        # Determine if there are more results for pagination
        next_token = None
        if len(items) == limit:
            # There might be more results
            next_offset = offset + limit
            next_token = str(next_offset)
        
        return ListKeysResponse(items=items, next=next_token)
        
    except Exception as e:
        logger.error(f"Error in list_keys: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Additional utility endpoints for admin

@app.post("/v1/admin/create-project")
async def create_project(
    project_id: str = Query(..., description="Project identifier"),
    label: str = Query(..., description="Human-readable project label"),
    owner: str = Query(..., description="Project owner"),
    _: bool = Depends(verify_admin_auth)
):
    """
    Create a new project (admin operation).
    
    Creates a new project that can contain API keys.
    """
    try:
        # Check if project already exists (using admin client)
        existing_project = await redis_admin.get_project(project_id)
        if existing_project:
            return create_error_response(
                code="project_exists",
                message="Project already exists",
                status_code=status.HTTP_409_CONFLICT
            )
        
        # Create project document
        current_time = datetime.now().timestamp()
        project_doc = ProjectDocument(
            project_id=project_id,
            label=label,
            owner=owner,
            created_at=current_time
        )
        
        # Store in Redis (using admin client)
        if not await redis_admin.store_project(project_doc):
            return create_error_response(
                code="storage_error",
                message="Failed to create project",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"Created project {project_id}")
        
        return {"project_id": project_id, "created": True}
        
    except Exception as e:
        logger.error(f"Error in create_project: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@app.get("/v1/admin/project/{project_id}")
async def get_project(project_id: str, _: bool = Depends(verify_admin_auth)):
    """
    Get project information (admin operation).
    """
    try:
        project_doc = await redis_admin.get_project(project_id)
        if project_doc is None:
            return create_error_response(
                code="project_not_found",
                message="Project not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        return project_doc.model_dump()
        
    except Exception as e:
        logger.error(f"Error in get_project: {e}")
        return create_error_response(
            code="internal_error",
            message="Internal server error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
