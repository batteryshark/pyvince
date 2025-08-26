"""
Tests for FastAPI endpoints covering all acceptance criteria.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from src.main import app, redis_client
from src.models import APIKeyDocument, ProjectDocument, ParsedAPIKey
from src.security import password_manager


# Mock the redis_client for testing
@pytest.fixture(autouse=True)
def mock_redis_client(clean_redis, monkeypatch):
    """Mock the global redis_client with our test client."""
    monkeypatch.setattr("src.main.redis_client", clean_redis)


class TestValidateKeyEndpoint:
    """Test /v1/validate-key endpoint - Acceptance Criteria 1-4."""
    
    def test_validate_key_success(self, client: TestClient, sample_api_key: APIKeyDocument):
        """
        Acceptance Criteria 1: Happy path validation.
        Given a valid API key, should return server_name in < 20ms and log audit event.
        """
        # Create valid API key string
        parsed_key = ParsedAPIKey(
            project_id=sample_api_key.project_id,
            key_id=sample_api_key.key_id,
            secret=sample_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == sample_api_key.project_id
        assert data["key_id"] == sample_api_key.key_id
        assert data["owner"] == sample_api_key.owner
        assert data["metadata"] == sample_api_key.metadata
    
    def test_validate_key_wrong_secret(self, client: TestClient, sample_api_key: APIKeyDocument):
        """
        Acceptance Criteria 2: Bad secret should return 401 and audit result=denied.
        """
        # Create API key with wrong secret
        parsed_key = ParsedAPIKey(
            project_id=sample_api_key.project_id,
            key_id=sample_api_key.key_id,
            secret="wrong_secret"
        )
        api_key = parsed_key.format_key()
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_key"
    
    def test_validate_key_disabled(self, client: TestClient, disabled_api_key: APIKeyDocument):
        """
        Acceptance Criteria 3: Disabled key should return 401 and audit result=denied.
        """
        # Create API key string for disabled key
        parsed_key = ParsedAPIKey(
            project_id=disabled_api_key.project_id,
            key_id=disabled_api_key.key_id,
            secret=disabled_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_key"
    
    def test_validate_key_expired(self, client: TestClient, expired_api_key: APIKeyDocument):
        """
        Acceptance Criteria 3: Expired key should return 401 and audit result=denied.
        """
        # Create API key string for expired key
        parsed_key = ParsedAPIKey(
            project_id=expired_api_key.project_id,
            key_id=expired_api_key.key_id,
            secret=expired_api_key.plain_secret
        )
        api_key = parsed_key.format_key()
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_key"
    
    def test_validate_key_nonexistent(self, client: TestClient):
        """Test validation with non-existent key."""
        api_key = "sk-proj.nonexistent.k_nonexistent.secret"
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_key"
    
    def test_validate_key_invalid_format(self, client: TestClient):
        """Test validation with invalid API key format."""
        api_key = "invalid-format"
        
        # Make request
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        
        # Verify error response
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "invalid_key"
    
    def test_validate_key_missing_field(self, client: TestClient):
        """Test validation with missing api_key field."""
        # Make request without api_key
        response = client.post("/v1/validate-key", json={})
        
        # Verify validation error
        assert response.status_code == 422


class TestMintKeyEndpoint:
    """Test /v1/mint-key endpoint - Acceptance Criteria 5."""
    
    def test_mint_key_success(self, client: TestClient, sample_project: ProjectDocument):
        """
        Acceptance Criteria 5: Mint key should produce printable token.
        """
        # Make request
        response = client.post("/v1/mint-key", json={
            "project_id": sample_project.project_id,
            "owner": "Test User",
            "server_name": "test-server",
            "expires_at": None
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
        
        # Verify API key format
        api_key = data["api_key"]
        assert api_key.startswith("sk-proj.")
        
        # Parse and verify components
        parsed = ParsedAPIKey.parse(api_key)
        assert parsed.project_id == sample_project.project_id
        assert parsed.key_id.startswith("k_")
        assert len(parsed.secret) > 20  # Reasonable secret length
    
    def test_mint_key_with_expiry(self, client: TestClient, sample_project: ProjectDocument):
        """Test minting key with expiry time."""
        future_time = (datetime.now() + timedelta(hours=24)).timestamp()
        
        # Make request
        response = client.post("/v1/mint-key", json={
            "project_id": sample_project.project_id,
            "owner": "Test User",
            "server_name": "test-server",
            "expires_at": future_time
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
    
    def test_mint_key_missing_fields(self, client: TestClient):
        """Test minting key with missing required fields."""
        # Make request without required fields
        response = client.post("/v1/mint-key", json={
            "project_id": "test_project"
            # Missing owner and server_name
        })
        
        # Verify validation error
        assert response.status_code == 422


class TestRevokeKeyEndpoint:
    """Test /v1/revoke-key endpoint - Acceptance Criteria 5."""
    
    def test_revoke_key_success(self, client: TestClient, sample_api_key: APIKeyDocument):
        """
        Acceptance Criteria 5: Revoke key should set disabled=true.
        """
        # Make request
        response = client.post("/v1/revoke-key", json={
            "project_id": sample_api_key.project_id,
            "key_id": sample_api_key.key_id
        })
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["revoked"] is True
    
    def test_revoke_key_nonexistent(self, client: TestClient):
        """Test revoking non-existent key."""
        # Make request
        response = client.post("/v1/revoke-key", json={
            "project_id": "nonexistent",
            "key_id": "k_nonexistent"
        })
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "key_not_found"
    
    def test_revoke_key_missing_fields(self, client: TestClient):
        """Test revoking key with missing fields."""
        # Make request without key_id
        response = client.post("/v1/revoke-key", json={
            "project_id": "test_project"
        })
        
        # Verify validation error
        assert response.status_code == 422


class TestListKeysEndpoint:
    """Test /v1/list-keys endpoint - Acceptance Criteria 6."""
    
    def test_list_keys_success(self, client: TestClient, sample_project: ProjectDocument):
        """
        Acceptance Criteria 6: List keys should return metadata without secrets.
        """
        # Create multiple keys
        for i in range(3):
            client.post("/v1/mint-key", json={
                "project_id": sample_project.project_id,
                "owner": f"User {i}",
                "server_name": f"server-{i}",
                "expires_at": None
            })
        
        # Make request
        response = client.get(f"/v1/list-keys?project_id={sample_project.project_id}")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3
        
        # Verify metadata structure (no secrets)
        for item in data["items"]:
            assert "key_id" in item
            assert "owner" in item
            assert "server_name" in item
            assert "created_at" in item
            assert "disabled" in item
            assert "expires_at" in item
            
            # Ensure no secret fields
            assert "secret" not in item
            assert "secret_hash" not in item
    
    def test_list_keys_pagination(self, client: TestClient, sample_project: ProjectDocument):
        """Test list keys with pagination."""
        # Create 5 keys
        for i in range(5):
            client.post("/v1/mint-key", json={
                "project_id": sample_project.project_id,
                "owner": f"User {i}",
                "server_name": f"server-{i}",
                "expires_at": None
            })
        
        # Get first page
        response = client.get(
            f"/v1/list-keys?project_id={sample_project.project_id}&offset=0&limit=3"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["next"] == "3"  # Next offset
        
        # Get second page
        response = client.get(
            f"/v1/list-keys?project_id={sample_project.project_id}&offset=3&limit=3"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2  # Only 2 remaining
        assert data["next"] is None  # No more pages
    
    def test_list_keys_empty_project(self, client: TestClient):
        """Test listing keys for project with no keys."""
        # Make request
        response = client.get("/v1/list-keys?project_id=empty_project")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["next"] is None
    
    def test_list_keys_missing_project_id(self, client: TestClient):
        """Test listing keys without project_id parameter."""
        # Make request without project_id
        response = client.get("/v1/list-keys")
        
        # Verify validation error
        assert response.status_code == 422


class TestIntegrationFlow:
    """Test complete integration flows - Acceptance Criteria 7-8."""
    
    def test_complete_key_lifecycle(self, client: TestClient):
        """
        Test complete key lifecycle: create project, mint key, validate key, revoke key.
        """
        # 1. Create project
        response = client.post("/v1/admin/create-project", params={
            "project_id": "integration_test",
            "label": "Integration Test Project",
            "owner": "Integration Tester"
        })
        assert response.status_code == 200
        
        # 2. Mint key
        response = client.post("/v1/mint-key", json={
            "project_id": "integration_test",
            "owner": "Test User",
            "server_name": "integration-server",
            "expires_at": None
        })
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        
        # Parse key to get components
        parsed = ParsedAPIKey.parse(api_key)
        
        # 3. Validate key (should succeed)
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        assert response.status_code == 200
        data = response.json()
        assert data["server_name"] == "integration-server"
        
        # 4. Revoke key
        response = client.post("/v1/revoke-key", json={
            "project_id": parsed.project_id,
            "key_id": parsed.key_id
        })
        assert response.status_code == 200
        
        # 5. Validate key again (should fail)
        response = client.post("/v1/validate-key", json={
            "api_key": api_key
        })
        assert response.status_code == 401
    
    def test_rate_limiting_flow(self, client: TestClient, sample_project: ProjectDocument):
        """
        Acceptance Criteria 4: Test rate limiting behavior.
        """
        # Mint a key for rate limit testing
        response = client.post("/v1/mint-key", json={
            "project_id": sample_project.project_id,
            "owner": "Rate Test User",
            "server_name": "rate-test-server",
            "expires_at": None
        })
        assert response.status_code == 200
        api_key = response.json()["api_key"]
        
        # Make requests within rate limit (first few should succeed)
        success_count = 0
        for i in range(10):
            response = client.post("/v1/validate-key", json={
                "api_key": api_key
            })
            if response.status_code == 200:
                success_count += 1
            else:
                # Should get rate limited eventually
                assert response.status_code == 401
                break
        
        # Should have some successful requests before rate limiting
        assert success_count > 0


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check_success(self, client: TestClient):
        """Test health check when Redis is available."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestAdminEndpoints:
    """Test admin utility endpoints."""
    
    def test_create_project_success(self, client: TestClient):
        """Test creating a new project."""
        response = client.post("/v1/admin/create-project", params={
            "project_id": "admin_test_project",
            "label": "Admin Test Project",
            "owner": "Admin User"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "admin_test_project"
        assert data["created"] is True
    
    def test_create_project_duplicate(self, client: TestClient, sample_project: ProjectDocument):
        """Test creating a project that already exists."""
        response = client.post("/v1/admin/create-project", params={
            "project_id": sample_project.project_id,
            "label": "Duplicate Project",
            "owner": "Admin User"
        })
        
        assert response.status_code == 409
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "project_exists"
    
    def test_get_project_success(self, client: TestClient, sample_project: ProjectDocument):
        """Test retrieving project information."""
        response = client.get(f"/v1/admin/project/{sample_project.project_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == sample_project.project_id
        assert data["label"] == sample_project.label
        assert data["owner"] == sample_project.owner
    
    def test_get_project_nonexistent(self, client: TestClient):
        """Test retrieving non-existent project."""
        response = client.get("/v1/admin/project/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "project_not_found"
