#!/usr/bin/env python3
"""
Minimal KeyMaster Admin Client

Simple admin client with core functions for managing projects and API keys.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
import requests
from src.models import (
    MintKeyRequest, MintKeyResponse,
    RevokeKeyRequest, RevokeKeyResponse,
    ListKeysResponse, KeyMetadata,
    ErrorResponse
)


class KeyMasterAdminClient:
    """Admin client for KeyMaster API operations."""
    
    def __init__(self, base_url: str, admin_token: str):
        """
        Initialize the admin client.
        
        Args:
            base_url: Base URL of the KeyMaster service
            admin_token: Admin authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
        self.timeout = 30
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the API."""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('headers', self.headers)
        kwargs.setdefault('timeout', self.timeout)
        
        return requests.request(method, url, **kwargs)
    
    def _handle_response(self, response: requests.Response, success_model=None):
        """Handle API response and return parsed result or error."""
        try:
            if response.status_code >= 200 and response.status_code < 300:
                json_data = response.json()
                if success_model:
                    return success_model(**json_data)
                return json_data
            else:
                # Try to parse as ErrorResponse
                try:
                    error_data = response.json()
                    return ErrorResponse(**error_data)
                except:
                    # Fallback error
                    return ErrorResponse(
                        error={
                            "code": f"HTTP_{response.status_code}",
                            "message": f"Request failed with status {response.status_code}: {response.text}"
                        }
                    )
        except requests.exceptions.RequestException as e:
            return ErrorResponse(
                error={
                    "code": "REQUEST_ERROR",
                    "message": f"Request failed: {str(e)}"
                }
            )
        except json.JSONDecodeError as e:
            return ErrorResponse(
                error={
                    "code": "INVALID_JSON",
                    "message": f"Invalid JSON response: {str(e)}"
                }
            )
    
    def health_check(self) -> Union[Dict[str, Any], ErrorResponse]:
        """Check service health."""
        response = self._make_request("GET", "/health")
        return self._handle_response(response)
    
    def create_project(self, project_id: str, label: str, owner: str) -> Union[Dict[str, Any], ErrorResponse]:
        """Create a new project."""
        params = {
            "project_id": project_id,
            "label": label,
            "owner": owner
        }
        response = self._make_request("POST", "/v1/admin/create-project", params=params)
        return self._handle_response(response)
    
    def get_project(self, project_id: str) -> Union[Dict[str, Any], ErrorResponse]:
        """Get project information."""
        response = self._make_request("GET", f"/v1/admin/project/{project_id}")
        return self._handle_response(response)
    
    def mint_key(self, project_id: str, owner: str, metadata: str, expires_in_days: Optional[int] = None) -> Union[MintKeyResponse, ErrorResponse]:
        """Mint a new API key."""
        expires_at = None
        if expires_in_days is not None:
            expires_at = (datetime.now() + timedelta(days=expires_in_days)).timestamp()
        
        request_data = MintKeyRequest(
            project_id=project_id,
            owner=owner,
            metadata=metadata,
            expires_at=expires_at
        )
        
        response = self._make_request("POST", "/v1/mint-key", json=request_data.model_dump())
        return self._handle_response(response, MintKeyResponse)
    
    def revoke_key(self, project_id: str, key_id: str) -> Union[RevokeKeyResponse, ErrorResponse]:
        """Revoke an API key."""
        request_data = RevokeKeyRequest(project_id=project_id, key_id=key_id)
        response = self._make_request("POST", "/v1/revoke-key", json=request_data.model_dump())
        return self._handle_response(response, RevokeKeyResponse)
    
    def list_keys(self, project_id: str, offset: int = 0, limit: int = 50) -> Union[ListKeysResponse, ErrorResponse]:
        """List API keys for a project."""
        params = {
            "project_id": project_id,
            "offset": offset,
            "limit": limit
        }
        response = self._make_request("GET", "/v1/list-keys", params=params)
        return self._handle_response(response, ListKeysResponse)
    
    def list_all_keys(self, project_id: str) -> Union[List[KeyMetadata], ErrorResponse]:
        """List all keys for a project (handles pagination automatically)."""
        all_keys = []
        offset = 0
        limit = 50
        
        while True:
            result = self.list_keys(project_id, offset, limit)
            
            if isinstance(result, ErrorResponse):
                return result
            
            all_keys.extend(result.items)
            
            # Check if there are more results
            if result.next is None or len(result.items) < limit:
                break
            
            offset += limit
        
        return all_keys


def parse_metadata(metadata_str: str) -> Union[str, Dict[str, Any]]:
    """Parse metadata string as JSON if possible."""
    try:
        return json.loads(metadata_str)
    except:
        return metadata_str


# Example usage
if __name__ == "__main__":
    # Configuration
    BASE_URL = "http://localhost:8000"
    ADMIN_TOKEN = "your-admin-token-here"
    
    # Create client
    client = KeyMasterAdminClient(BASE_URL, ADMIN_TOKEN)
    
    # Example: Create a project
    result = client.create_project("test-project", "Test Project", "admin@example.com")
    print("Create project:", result)
    
    # Example: Mint a key
    result = client.mint_key("test-project", "user1", '{"env": "development"}', expires_in_days=30)
    print("Mint key:", result)
    
    # Example: List keys
    result = client.list_all_keys("test-project")
    print("List keys:", result)
