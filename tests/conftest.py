"""
Pytest configuration and fixtures for API Key Manager tests.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Generator, AsyncGenerator

import redis.asyncio as redis
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.main import app
from src.redis_client import RedisKeyManager
from src.models import APIKeyDocument, ProjectDocument
from src.security import password_manager


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def redis_client() -> AsyncGenerator[RedisKeyManager, None]:
    """Create a Redis client for testing."""
    # Use a test database
    client = RedisKeyManager(
        host="localhost",
        port=6379,
        password="defaultpass",
        db=15  # Use database 15 for testing
    )
    
    # Test connection
    if not client.ping():
        pytest.skip("Redis is not available for testing")
    
    yield client
    
    # Cleanup - flush test database
    client.client.flushdb()


@pytest.fixture
async def clean_redis(redis_client: RedisKeyManager) -> AsyncGenerator[RedisKeyManager, None]:
    """Provide a clean Redis database for each test."""
    # Clean before test
    redis_client.client.flushdb()
    
    yield redis_client
    
    # Clean after test
    redis_client.client.flushdb()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_project(clean_redis: RedisKeyManager) -> ProjectDocument:
    """Create a sample project for testing."""
    project_doc = ProjectDocument(
        project_id="test_project",
        label="Test Project",
        owner="Test Owner",
        created_at=datetime.now().timestamp()
    )
    
    await clean_redis.store_project(project_doc)
    return project_doc


@pytest.fixture
async def sample_api_key(clean_redis: RedisKeyManager, sample_project: ProjectDocument) -> APIKeyDocument:
    """Create a sample API key for testing."""
    secret = "test_secret_123"
    secret_hash = password_manager.hash_password(secret)
    
    api_key_doc = APIKeyDocument(
        key_id="k_test123",
        project_id=sample_project.project_id,
        owner="Test User",
        metadata="test-server",
        secret_hash=secret_hash,
        disabled=False,
        created_at=datetime.now().timestamp(),
        expires_at=None
    )
    
    await clean_redis.store_api_key(api_key_doc)
    
    # Store the plain secret for testing
    api_key_doc.plain_secret = secret
    
    return api_key_doc


@pytest.fixture
async def expired_api_key(clean_redis: RedisKeyManager, sample_project: ProjectDocument) -> APIKeyDocument:
    """Create an expired API key for testing."""
    secret = "expired_secret_123"
    secret_hash = password_manager.hash_password(secret)
    
    # Set expiry to 1 hour ago
    expired_time = datetime.now().timestamp() - 3600
    
    api_key_doc = APIKeyDocument(
        key_id="k_expired",
        project_id=sample_project.project_id,
        owner="Test User",
        metadata="test-server",
        secret_hash=secret_hash,
        disabled=False,
        created_at=datetime.now().timestamp() - 7200,  # Created 2 hours ago
        expires_at=expired_time
    )
    
    await clean_redis.store_api_key(api_key_doc)
    
    # Store the plain secret for testing
    api_key_doc.plain_secret = secret
    
    return api_key_doc


@pytest.fixture
async def disabled_api_key(clean_redis: RedisKeyManager, sample_project: ProjectDocument) -> APIKeyDocument:
    """Create a disabled API key for testing."""
    secret = "disabled_secret_123"
    secret_hash = password_manager.hash_password(secret)
    
    api_key_doc = APIKeyDocument(
        key_id="k_disabled",
        project_id=sample_project.project_id,
        owner="Test User",
        metadata="test-server",
        secret_hash=secret_hash,
        disabled=True,  # Disabled
        created_at=datetime.now().timestamp(),
        expires_at=None
    )
    
    await clean_redis.store_api_key(api_key_doc)
    
    # Store the plain secret for testing
    api_key_doc.plain_secret = secret
    
    return api_key_doc
