# API Key Manager - Architecture

## Overview

This document describes the architecture and implementation of the API Key Manager, a minimal and auditable key validation service.

## Design Principles

1. **Minimal & Auditable**: Clean, simple code that's easy to review and understand
2. **O(1) Performance**: Single Redis JSON.GET operations for key validation
3. **Security First**: Argon2id hashing, ACL restrictions, rate limiting
4. **Production Ready**: Docker deployment, comprehensive testing, monitoring
5. **Type Safe**: Pydantic v2 models with strict validation

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Service                         │
│                        (out of scope)                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │ mTLS / HTTP
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  API Key Manager                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  FastAPI    │  │   Pydantic  │  │    Security Utils       │  │
│  │  Endpoints  │  │   Models    │  │  - Argon2id hashing    │  │
│  │             │  │             │  │  - Key generation      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                Redis Client Manager                         │  │
│  │  - JSON document operations                                 │  │
│  │  - Stream audit logging                                     │  │
│  │  - Rate limiting                                            │  │
│  │  - Key validation workflow                                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Redis protocol
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Redis Stack                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ JSON Docs   │  │   Streams   │  │    Core Data Types      │  │
│  │ - Projects  │  │ - Audit log │  │  - Sets (key lists)    │  │
│  │ - API Keys  │  │             │  │  - Hashes (metadata)   │  │
│  │             │  │             │  │  - Counters (limits)   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Key Validation Flow

```
1. Gateway receives client request with Authorization header
2. Gateway extracts API key: sk-proj.{project}.{key}.{secret}
3. Gateway calls POST /v1/validate-key with api_key
4. Key Manager:
   a. Parses API key format
   b. JSON.GET apikey:{project}:{key} from Redis
   c. Checks disabled/expired status
   d. Verifies secret against Argon2id hash
   e. Checks rate limit (INCR + TTL)
   f. Logs audit event (XADD to stream)
   g. Updates usage metadata
5. Returns {project_id, key_id, owner, server_name}
6. Gateway routes session to server_name
```

### Key Minting Flow

```
1. Admin calls POST /v1/mint-key
2. Key Manager:
   a. Generates random key_id (k_XXXXXXX)
   b. Generates random secret (32 chars)
   c. Hashes secret with Argon2id
   d. Creates APIKeyDocument
   e. Stores JSON document in Redis
   f. Adds key_id to project's key set
   g. Initializes usage metadata
3. Returns formatted API key string
```

## Security Architecture

### Multi-Client Isolation

The system supports secure multi-client deployments using Redis ACL for database-level isolation:

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Client Architecture                │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Gateway A   │    │ Gateway B   │    │   Admin     │      │
│  │ (client_a)  │    │ (client_b)  │    │  Console    │      │
│  └─────┬───────┘    └─────┬───────┘    └─────┬───────┘      │
│        │                  │                  │              │
│  ┌─────▼───────┐    ┌─────▼───────┐    ┌─────▼───────┐      │
│  │ KeyMgr A    │    │ KeyMgr B    │    │ KeyMgr Admin│      │
│  │ (client_a)  │    │ (client_b)  │    │ (admin)     │      │
│  └─────┬───────┘    └─────┬───────┘    └─────┬───────┘      │
│        │                  │                  │              │
│        └──────────────────┼──────────────────┘              │
│                           │                                 │
│  ┌─────────────────────────▼─────────────────────────────┐  │
│  │                    Redis ACL                         │  │
│  │  client_a: ~apikey:alpha:* ~apikey:beta:*           │  │
│  │  client_b: ~apikey:gamma:*                          │  │
│  │  admin:    ~* +@all                                 │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**Security Benefits:**
- Database-level isolation prevents cross-project access
- Stolen Redis credentials only expose authorized projects
- No application-level authentication complexity
- Clear audit trails per client

### Password Hashing
- **Algorithm**: Argon2id (OWASP recommended)
- **Parameters**: 
  - time_cost=3 (iterations)
  - memory_cost=65536 (64MB)
  - parallelism=1 (single thread)
  - hash_len=32, salt_len=16
- **Verification**: Constant-time comparison

### Redis ACL
```
ACL SETUSER manager on >{password} reset -@all \
  +json.get +json.set +json.del +json.type +json.resp \
  +xadd +xlen +xread +xrange +xdel \
  +set +get +del +exists +expire +ttl \
  +incr +incrby +decr +decrby \
  +sadd +srem +smembers +scard \
  +hset +hget +hgetall +hincrby +hdel +hlen \
  +ping +echo +auth +hello +info +memory +client \
  ~apikey:* ~apiprojectkeys:* ~apimeta:* ~project:* ~audit:* ~ratelimit:*
```

### Rate Limiting
- **Algorithm**: Token bucket using Redis INCR + TTL
- **Window**: Per-minute sliding window
- **Key Pattern**: `ratelimit:key:{project}:{key}:{minute}`
- **Default Limit**: 100 requests/minute per key
- **Atomicity**: Pipelined operations for consistency

## Database Schema

### Redis Key Patterns

| Pattern | Type | Purpose | Example |
|---------|------|---------|---------|
| `project:{id}` | JSON | Project metadata | `project:merlin` |
| `apikey:{proj}:{key}` | JSON | API key document | `apikey:merlin:k_abc123` |
| `apiprojectkeys:{proj}` | SET | Key IDs for project | `apiprojectkeys:merlin` |
| `apimeta:{proj}:{key}` | HASH | Usage statistics | `apimeta:merlin:k_abc123` |
| `audit:keylookup` | STREAM | Validation events | - |
| `ratelimit:key:{proj}:{key}:{min}` | STRING | Rate limit counter | `ratelimit:key:merlin:k_abc123:27847920` |

### JSON Document Schemas

#### Project Document
```json
{
  "project_id": "merlin",
  "label": "Merlin Research",
  "owner": "rfx",
  "created_at": 1732579200.0
}
```

#### API Key Document
```json
{
  "key_id": "k_2J6Hqk3",
  "project_id": "merlin", 
  "owner": "rfx",
  "server_name": "research-west",
  "secret_hash": "argon2id$v=19$m=65536,t=3,p=1$...",
  "disabled": false,
  "created_at": 1732579200.0,
  "expires_at": null
}
```

#### Audit Event (Stream)
```
ts: 1732579301.1
project_id: merlin
key_id: k_2J6Hqk3
result: ok|denied|rate_limited
client: keymanager
```

## API Design

### REST Principles
- **Resource-based URLs**: `/v1/validate-key`, `/v1/mint-key`
- **HTTP Methods**: POST for operations, GET for queries
- **Status Codes**: 200 (success), 401 (unauthorized), 404 (not found), 422 (validation)
- **Content-Type**: `application/json`
- **Error Format**: `{"error": {"code": "...", "message": "..."}}`

### Request/Response Models
All API models use Pydantic v2 with:
- Strict validation (`extra="forbid"`)
- Type hints for all fields
- Clear field descriptions
- Serialization aliases where needed

### Admin vs Public Endpoints
- **Public**: `/v1/validate-key` (called by gateway)
- **Admin**: `/v1/mint-key`, `/v1/revoke-key`, `/v1/list-keys`
- **Utility**: `/v1/admin/*` (project management)

## Performance Characteristics

### Latency Targets
- **Key Validation**: < 10ms p50, < 20ms p95 (intra-VPC)
- **Key Operations**: < 100ms for mint/revoke/list
- **Audit Logging**: Asynchronous, < 5ms overhead

### Throughput Capacity
- **Single Instance**: > 1000 validations/second
- **Bottleneck**: Redis connection pool
- **Scaling**: Horizontal (stateless service)

### Memory Usage
- **Application**: < 100MB resident set
- **Redis**: ~1KB per API key document
- **Connection Pool**: 10 connections by default

## Deployment Architecture

### Container Strategy
```dockerfile
FROM python:3.12-slim
# Install uv for fast dependency management
# Non-root user for security
# Health checks for monitoring
# Minimal attack surface
```

### Service Dependencies
```yaml
services:
  redis:
    image: redis/redis-stack:7.2.0-v10
    # AOF persistence enabled
    # ACL configuration
    # RedisInsight for debugging
  
  keymanager:
    build: .
    # Health checks
    # Environment configuration
    # Restart policies
```

### Configuration Management
- **Environment Variables**: 12-factor app compliance
- **Secrets**: External secret management (not in env vars)
- **Health Checks**: Redis connectivity, memory usage
- **Graceful Shutdown**: Connection cleanup

## Testing Strategy

### Test Categories
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: End-to-end API workflows
3. **Performance Tests**: Latency and throughput validation
4. **Security Tests**: ACL restrictions, hash verification
5. **Acceptance Tests**: All design criteria validation

### Test Coverage
- **Models**: Validation, serialization, edge cases
- **Security**: Password hashing, key generation, timing attacks
- **Redis Client**: All CRUD operations, error handling
- **API Endpoints**: Success/failure paths, validation
- **Integration**: Complete workflows, rate limiting

### Acceptance Criteria Validation
Each test maps to specific acceptance criteria:
- ✅ Happy path < 20ms with audit logging
- ✅ Bad secret returns 401 + audit denied
- ✅ Disabled/expired returns 401 + audit denied  
- ✅ Rate limiting returns 429 + audit rate_limited
- ✅ Mint/revoke operations work correctly
- ✅ List keys excludes secrets with pagination
- ✅ Gateway integration workflow
- ✅ Redis ACL restrictions enforced

## Monitoring & Observability

### Application Metrics
- Request rate and latency by endpoint
- Error rates by error type
- Redis operation timing
- Rate limit hit rates
- Memory and CPU usage

### Redis Metrics
- Connection pool utilization
- Command latency (JSON.GET, XADD)
- Memory usage and fragmentation
- Stream depth (audit:keylookup)
- Key count by pattern

### Health Checks
- `/health` endpoint for load balancers
- Redis connectivity verification
- Memory usage thresholds
- Stream processing lag

### Alerting Scenarios
- High error rates (>5% for 5 minutes)
- Slow validation times (>20ms p95)
- Redis connection failures
- Memory usage >80%
- Stream depth growing unbounded

## Future Enhancements

### Scalability Improvements
1. **Lua Scripts**: Atomic validation + rate limiting
2. **Read Replicas**: Separate read/write Redis instances
3. **Connection Pooling**: Optimize Redis connection management
4. **Caching**: In-memory LRU cache for hot keys

### Feature Additions
1. **Admin UI**: Web interface for key management
2. **JSON Search**: Index-based key filtering
3. **Server Registry**: Metadata for target servers
4. **Webhook Events**: Real-time notifications
5. **Multi-tenancy**: Namespace isolation

### Security Enhancements
1. **mTLS**: Client certificate authentication
2. **JWT Tokens**: Stateless session tokens
3. **IP Whitelisting**: Network-level restrictions
4. **Audit Encryption**: Encrypted audit streams
5. **Key Rotation**: Automatic key lifecycle management

