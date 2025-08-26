#!/usr/bin/env python3
"""
Minimal client example for KeyMaster API.

This script demonstrates how to validate an API key using the /v1/validate-key endpoint
and parse the response using the Pydantic models from models.py.
"""

import os
import json
import sys
from typing import Dict, Any, Union
import requests

from pydantic import BaseModel, Field

# ------------------------------------------------------------
# Request/Response Models for API endpoints
# ------------------------------------------------------------

class ValidateKeyRequest(BaseModel):
    """Request model for POST /v1/validate-key"""
    api_key: str = Field(..., description="API key in format sk-proj.{project_id}.{key_id}.{secret}")


class ValidateKeyResponse(BaseModel):
    """Response model for successful key validation"""
    project_id: str
    key_id: str
    owner: str
    metadata: str

class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str
    message: str



def validate_api_key(base_url: str, api_key: str) -> Union[ValidateKeyResponse, ErrorResponse]:
    """
    Validate an API key against the KeyMaster service.
    
    Args:
        base_url: Base URL of the KeyMaster service (e.g., "http://localhost:8000")
        api_key: API key to validate
        
    Returns:
        ValidateKeyResponse on success, ErrorResponse on error
    """
    url = f"{base_url}/v1/validate-key"
    
    # Create request payload
    request_data = ValidateKeyRequest(api_key=api_key)
    
    try:
        response = requests.post(
            url,
            json=request_data.model_dump(),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            # Success - parse as ValidateKeyResponse
            return ValidateKeyResponse(**response.json())
        else:
            # Error - parse as ErrorResponse
            return ErrorResponse(**response.json())
            
    except requests.exceptions.RequestException as e:
        # Network or connection error
        return ErrorResponse(
            error={
                "code": "CONNECTION_ERROR",
                "message": f"Failed to connect to service: {str(e)}"
            }
        )
    except json.JSONDecodeError as e:
        # Invalid JSON response
        return ErrorResponse(
            error={
                "code": "INVALID_RESPONSE",
                "message": f"Invalid JSON response: {str(e)}"
            }
        )


def parse_metadata(metadata: str) -> Union[str, Dict[str, Any]]:
    """
    Parse metadata string. If it's valid JSON, return as dict; otherwise return as string.
    
    Args:
        metadata: Metadata string from the API response
        
    Returns:
        Dict if metadata is valid JSON, str otherwise
    """
    try:
        return json.loads(metadata)
    except (json.JSONDecodeError, TypeError):
        return metadata



if __name__ == "__main__":
    BASE_URL = "http://localhost:12818"
    TEST_KEY = "sk-proj.test-project.k_Aa0sSqD.-jUVLTdvZchjHk6dE0nlvYwx14ti_lu6"
    TEST_BAD_KEY = "sk-proj.fff-project.k_7xFAxjD.Wa2B8c5mvgcEkiDx1G8gSHUjjZBHCTyE"

    print(f"Validating test key: {validate_api_key(BASE_URL, TEST_KEY)}")
    print(f"Validating test bad key: {validate_api_key(BASE_URL, TEST_BAD_KEY)}")
