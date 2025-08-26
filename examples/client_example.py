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
from src.models import ValidateKeyRequest, ValidateKeyResponse, ErrorResponse

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


def main():
    """Main function demonstrating the client usage."""
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Configuration
    BASE_URL = os.getenv("BASE_URL", "http://localhost:12828")  # Change this to your KeyMaster service URL
    
    # Example API key - replace with a real one
    API_KEY = "sk-proj.example-project.example-key.example-secret"
    
    # You can also pass the API key as a command line argument
    if len(sys.argv) > 1:
        API_KEY = sys.argv[1]
    
    print(f"Validating API key: {API_KEY[:20]}...")
    print(f"Service URL: {BASE_URL}")
    print("-" * 50)
    
    # Validate the API key
    result = validate_api_key(BASE_URL, API_KEY)
    
    if isinstance(result, ValidateKeyResponse):
        print("✅ API Key is valid!")
        print(f"Project ID: {result.project_id}")
        print(f"Key ID: {result.key_id}")
        print(f"Owner: {result.owner}")
        print(f"Raw Metadata: {result.metadata}")
        
        # Parse metadata
        parsed_metadata = parse_metadata(result.metadata)
        print(f"Parsed Metadata Type: {type(parsed_metadata).__name__}")
        
        if isinstance(parsed_metadata, dict):
            print("📋 Metadata (JSON):")
            for key, value in parsed_metadata.items():
                print(f"  {key}: {value}")
        else:
            print(f"📋 Metadata (String): {parsed_metadata}")
            
    elif isinstance(result, ErrorResponse):
        print("❌ API Key validation failed!")
        print(f"Error Code: {result.error.code}")
        print(f"Error Message: {result.error.message}")
        sys.exit(1)
    else:
        print("❌ Unexpected response type")
        sys.exit(1)


if __name__ == "__main__":
    main()
