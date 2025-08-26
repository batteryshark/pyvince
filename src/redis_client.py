"""
Redis client for the API Key Manager.

Provides Redis operations with JSON support and ACL configuration.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import redis
from redis.exceptions import ConnectionError, RedisError

from .models import APIKeyDocument, ProjectDocument, AuditEvent, ParsedAPIKey
from .security import password_manager


logger = logging.getLogger(__name__)


class RedisKeyManager:
    """
    Redis client manager for key operations.
    
    Handles all Redis operations including JSON documents, Streams, and rate limiting.
    """
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        password: Optional[str] = None,
        username: Optional[str] = None,
        db: int = 0
    ):
        """
        Initialize Redis client.
        
        Args:
            host: Redis server hostname
            port: Redis server port  
            password: Redis password
            username: Redis username (for ACL)
            db: Redis database number
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password,
            username=username,
            db=db,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.client.ping()
        except ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            return False
    
    # Key naming helper methods
    
    def _project_key(self, project_id: str) -> str:
        """Generate Redis key for project document."""
        return f"project:{project_id}"
    
    def _apikey_key(self, project_id: str, key_id: str) -> str:
        """Generate Redis key for API key document."""
        return f"apikey:{project_id}:{key_id}"
    
    def _apiprojectkeys_key(self, project_id: str) -> str:
        """Generate Redis key for project's key set."""
        return f"apiprojectkeys:{project_id}"
    
    def _apimeta_key(self, project_id: str, key_id: str) -> str:
        """Generate Redis key for API key metadata."""
        return f"apimeta:{project_id}:{key_id}"
    
    def _ratelimit_key(self, project_id: str, key_id: str, minute: int) -> str:
        """Generate Redis key for rate limiting."""
        return f"ratelimit:key:{project_id}:{key_id}:{minute}"
    
    # API Key operations
    
    async def get_api_key(self, project_id: str, key_id: str) -> Optional[APIKeyDocument]:
        """
        Retrieve API key document from Redis.
        
        Args:
            project_id: Project identifier
            key_id: Key identifier
            
        Returns:
            APIKeyDocument if found, None otherwise
        """
        try:
            key = self._apikey_key(project_id, key_id)
            data = self.client.json().get(key)
            
            if data is None:
                return None
                
            return APIKeyDocument.model_validate(data)
            
        except (RedisError, ValueError) as e:
            logger.error(f"Error retrieving API key {project_id}:{key_id}: {e}")
            return None
    
    async def store_api_key(self, api_key_doc: APIKeyDocument) -> bool:
        """
        Store API key document in Redis.
        
        Args:
            api_key_doc: API key document to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Store the API key document
            key = self._apikey_key(api_key_doc.project_id, api_key_doc.key_id)
            data = api_key_doc.model_dump()
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            
            # Store API key JSON document
            pipe.json().set(key, "$", data)
            
            # Add key_id to project's key set
            project_keys = self._apiprojectkeys_key(api_key_doc.project_id)
            pipe.sadd(project_keys, api_key_doc.key_id)
            
            # Initialize metadata hash
            meta_key = self._apimeta_key(api_key_doc.project_id, api_key_doc.key_id)
            pipe.hset(meta_key, mapping={
                "usage_count": 0,
                "last_used": ""
            })
            
            pipe.execute()
            return True
            
        except RedisError as e:
            logger.error(f"Error storing API key {api_key_doc.project_id}:{api_key_doc.key_id}: {e}")
            return False
    
    async def revoke_api_key(self, project_id: str, key_id: str) -> bool:
        """
        Revoke an API key by setting disabled=true.
        
        Args:
            project_id: Project identifier
            key_id: Key identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._apikey_key(project_id, key_id)
            
            # Update only the disabled field
            result = self.client.json().set(key, "$.disabled", True)
            return result is not None
            
        except RedisError as e:
            logger.error(f"Error revoking API key {project_id}:{key_id}: {e}")
            return False
    
    async def list_project_keys(
        self, 
        project_id: str, 
        offset: int = 0, 
        limit: int = 50
    ) -> List[APIKeyDocument]:
        """
        List all API keys for a project.
        
        Args:
            project_id: Project identifier
            offset: Pagination offset
            limit: Maximum number of keys to return
            
        Returns:
            List of APIKeyDocument objects
        """
        try:
            # Get all key IDs for the project
            project_keys = self._apiprojectkeys_key(project_id)
            key_ids = list(self.client.smembers(project_keys))
            
            # Apply pagination
            paginated_key_ids = key_ids[offset:offset + limit]
            
            # Retrieve API key documents
            keys = []
            for key_id in paginated_key_ids:
                api_key_doc = await self.get_api_key(project_id, key_id)
                if api_key_doc:
                    keys.append(api_key_doc)
            
            return keys
            
        except RedisError as e:
            logger.error(f"Error listing keys for project {project_id}: {e}")
            return []
    
    # Project operations
    
    async def get_project(self, project_id: str) -> Optional[ProjectDocument]:
        """
        Retrieve project document from Redis.
        
        Args:
            project_id: Project identifier
            
        Returns:
            ProjectDocument if found, None otherwise
        """
        try:
            key = self._project_key(project_id)
            data = self.client.json().get(key)
            
            if data is None:
                return None
                
            return ProjectDocument.model_validate(data)
            
        except (RedisError, ValueError) as e:
            logger.error(f"Error retrieving project {project_id}: {e}")
            return None
    
    async def store_project(self, project_doc: ProjectDocument) -> bool:
        """
        Store project document in Redis.
        
        Args:
            project_doc: Project document to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._project_key(project_doc.project_id)
            data = project_doc.model_dump()
            
            result = self.client.json().set(key, "$", data)
            return result is not None
            
        except RedisError as e:
            logger.error(f"Error storing project {project_doc.project_id}: {e}")
            return False
    
    # Audit operations
    
    async def log_audit_event(self, event: AuditEvent) -> bool:
        """
        Log an audit event to Redis Stream.
        
        Args:
            event: Audit event to log
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stream_key = "audit:keylookup"
            fields = event.to_stream_fields()
            
            # Add event to stream
            self.client.xadd(stream_key, fields)
            return True
            
        except RedisError as e:
            logger.error(f"Error logging audit event: {e}")
            return False
    
    # Rate limiting operations
    
    async def check_rate_limit(
        self, 
        project_id: str, 
        key_id: str, 
        limit_per_minute: int = 100
    ) -> bool:
        """
        Check if a key is rate limited.
        
        Args:
            project_id: Project identifier
            key_id: Key identifier
            limit_per_minute: Maximum requests per minute
            
        Returns:
            True if request is allowed, False if rate limited
        """
        try:
            # Use current minute as rate limit window
            current_minute = int(datetime.now().timestamp() // 60)
            rate_key = self._ratelimit_key(project_id, key_id, current_minute)
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            
            # Increment counter
            pipe.incr(rate_key)
            # Set expiry to 2 minutes (to handle clock skew)
            pipe.expire(rate_key, 120)
            
            results = pipe.execute()
            current_count = results[0]
            
            return current_count <= limit_per_minute
            
        except RedisError as e:
            logger.error(f"Error checking rate limit for {project_id}:{key_id}: {e}")
            # On error, allow the request (fail open)
            return True
    
    async def update_key_usage(self, project_id: str, key_id: str) -> None:
        """
        Update key usage metadata.
        
        Args:
            project_id: Project identifier
            key_id: Key identifier
        """
        try:
            meta_key = self._apimeta_key(project_id, key_id)
            current_time = datetime.now().isoformat()
            
            # Use pipeline for atomic operations
            pipe = self.client.pipeline()
            pipe.hincrby(meta_key, "usage_count", 1)
            pipe.hset(meta_key, "last_used", current_time)
            pipe.execute()
            
        except RedisError as e:
            logger.error(f"Error updating key usage for {project_id}:{key_id}: {e}")
    
    # Key validation workflow
    
    async def validate_api_key(self, api_key: str) -> Optional[APIKeyDocument]:
        """
        Complete API key validation workflow.
        
        Args:
            api_key: API key string to validate
            
        Returns:
            APIKeyDocument if valid, None otherwise
        """
        try:
            # Parse API key
            parsed_key = ParsedAPIKey.parse(api_key)
            
            # Retrieve API key document
            api_key_doc = await self.get_api_key(parsed_key.project_id, parsed_key.key_id)
            if not api_key_doc:
                await self.log_audit_event(AuditEvent(
                    project_id=parsed_key.project_id,
                    key_id=parsed_key.key_id,
                    result="denied"
                ))
                return None
            
            # Check if key is valid (not disabled, not expired)
            if not api_key_doc.is_valid():
                await self.log_audit_event(AuditEvent(
                    project_id=parsed_key.project_id,
                    key_id=parsed_key.key_id,
                    result="denied"
                ))
                return None
            
            # Verify secret
            if not password_manager.verify_password(parsed_key.secret, api_key_doc.secret_hash):
                await self.log_audit_event(AuditEvent(
                    project_id=parsed_key.project_id,
                    key_id=parsed_key.key_id,
                    result="denied"
                ))
                return None
            
            # Check rate limit
            if not await self.check_rate_limit(parsed_key.project_id, parsed_key.key_id):
                await self.log_audit_event(AuditEvent(
                    project_id=parsed_key.project_id,
                    key_id=parsed_key.key_id,
                    result="rate_limited"
                ))
                return None
            
            # Success - log audit event and update usage
            await self.log_audit_event(AuditEvent(
                project_id=parsed_key.project_id,
                key_id=parsed_key.key_id,
                result="ok"
            ))
            
            await self.update_key_usage(parsed_key.project_id, parsed_key.key_id)
            
            return api_key_doc
            
        except ValueError as e:
            logger.warning(f"Invalid API key format: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None
