# API Key Manager

A minimal, auditable key-validation service for managing API keys with flexible metadata. This service validates API keys, manages key lifecycle, and provides associated metadata for routing, configuration, or any other purposes.

## Features

- **Fast Key Validation**: O(1) validation with < 10ms p50 latency
- **Secure Storage**: Argon2id password hashing with Redis JSON documents
- **Audit Trail**: Complete audit logging via Redis Streams
- **Rate Limiting**: Per-key rate limiting with configurable thresholds
- **Admin Operations**: Key minting, revocation, and listing
- **Production Ready**: Docker deployment with Redis Stack

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   Client        │    │  API Key Manager     │    │   Redis Stack   │
│   Application   │───▶│  (this service)      │───▶│   + RedisJSON   │
│                 │    │                      │    │   + Streams     │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
         │                        │
         │                        ▼
         ▼                 ┌─────────────────┐
┌─────────────────┐        │   Audit Logs   │
│   Backend       │        │   Rate Limits   │
│   Services      │        │   Metadata      │
└─────────────────┘        └─────────────────┘
```

## API Key Format

API keys follow the format: `sk-proj.{project_id}.{key_id}.{secret}`

Example: `sk-proj.merlin.k_2J6Hqk3.XyZ123abc...`

## Flexible Metadata

The `metadata` field is a flexible string that can contain:
- **Server names**: `"api-server-west"` for routing
- **JSON configuration**: `'{"server": "west", "region": "us", "version": "v2"}'`
- **Simple flags**: `"production"` or `"development"`
- **Any string data**: Whatever your application needs for routing, configuration, or logic

This design keeps the service generic and adaptable to any use case while maintaining type safety and validation.

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and setup**:
   ```bash
   git clone <repo-url>
   cd keymaster
   ```

2. **Initialize with secure secrets** (Recommended):
   ```bash
   ./scripts/init_project.sh
   ```
   
   Or manually:
   ```bash
   cp env.example .env
   ./scripts/setup_secrets.sh
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **Setup Redis ACL** (production):
   ```bash
   ./setup_redis_acl.sh
   ```

4. **Test the API**:
   ```bash
   curl http://localhost:8000/health
   ```

### Manual Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Redis Stack**:
   ```bash
   docker run -d -p 6379:6379 -p 8001:8001 redis/redis-stack:7.2.0-v10
   ```

3. **Run the application**:
   ```bash
   python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

## Authentication

### Public Endpoints
- `POST /v1/validate-key` - No authentication required (security via Redis ACL isolation)
- `GET /health` - No authentication required

### Admin Endpoints
Admin endpoints require authentication using a Bearer token that matches the `ADMIN_SECRET` environment variable.

**Headers required for admin endpoints:**
```
Authorization: Bearer your_super_secret_admin_token
```

**Admin endpoints:**
- `POST /v1/mint-key`
- `POST /v1/revoke-key` 
- `GET /v1/list-keys`
- `POST /v1/admin/create-project`
- `GET /v1/admin/project/{project_id}`

### Setting Up Admin Authentication

1. **Generate a secure admin secret:**
   ```bash
   # Generate a random 32-character secret
   export ADMIN_SECRET=$(openssl rand -base64 32)
   echo "ADMIN_SECRET=$ADMIN_SECRET"
   ```

2. **Set the environment variable:**
   ```bash
   export ADMIN_SECRET=your_generated_secret
   ```

3. **Use in API calls:**
   ```bash
   curl -H "Authorization: Bearer $ADMIN_SECRET" \
        -X POST http://localhost:8000/v1/mint-key \
        -H "Content-Type: application/json" \
        -d '{"project_id":"test","owner":"admin","metadata":"server-1"}'
   ```

## API Endpoints

### Core Operations

#### POST /v1/validate-key
Validate an API key and get associated metadata.

**Request**:
```json
{
  "api_key": "sk-proj.merlin.k_2J6Hqk3.XyZ123abc..."
}
```

**Response** (200 OK):
```json
{
  "project_id": "merlin",
  "key_id": "k_2J6Hqk3",
  "owner": "Mario",
  "metadata": "research-west"
}
```

#### POST /v1/mint-key (Admin)
Create a new API key.

**Request**:
```json
{
  "project_id": "merlin",
  "owner": "Mario",
  "metadata": "research-west",
  "expires_at": null
}
```

**Response** (201 Created):
```json
{
  "api_key": "sk-proj.merlin.k_AbCdEf.....<secret>"
}
```

#### POST /v1/revoke-key (Admin)
Revoke an API key.

**Request**:
```json
{
  "project_id": "merlin",
  "key_id": "k_2J6Hqk3"
}
```

**Response** (200 OK):
```json
{
  "revoked": true
}
```

#### GET /v1/list-keys (Admin)
List API keys for a project.

**Query Parameters**:
- `project_id`: Project identifier (required)
- `offset`: Pagination offset (default: 0)
- `limit`: Maximum results (default: 50)

**Response** (200 OK):
```json
{
  "items": [
    {
      "key_id": "k_2J6Hqk3",
      "owner": "Mario",
      "metadata": "research-west",
      "created_at": 1732579200.0,
      "disabled": false,
      "expires_at": null
    }
  ],
  "next": null
}
```

### Admin Operations

#### POST /v1/admin/create-project
Create a new project.

#### GET /v1/admin/project/{project_id}
Get project information.

#### GET /health
Health check endpoint.

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_secure_password
REDIS_USERNAME=manager
REDIS_DB=0

# Admin Authentication
ADMIN_SECRET=your_super_secret_admin_token

# Application
LOG_LEVEL=info
HOST=0.0.0.0
PORT=8000
```

### Redis ACL Setup

For production, create a restricted Redis user:

```bash
./setup_redis_acl.sh
```

This creates a `manager` user with limited permissions:
- JSON operations on key patterns
- Stream operations for audit logs
- Basic operations for rate limiting
- No access to dangerous commands

### Multi-Client Deployment with Redis ACL

For secure multi-client deployments, create separate Redis users for each client/environment with project-specific access patterns. This provides database-level security isolation.

#### Creating Client-Specific Users

Add users to your `redis_users.acl.example` file (or modify the generated `redis_users.acl` file):

```bash
# Client A - can access projects "alpha" and "beta"
user client_a on >secure_password_a ~apikey:alpha:* ~apikey:beta:* ~apiprojectkeys:alpha ~apiprojectkeys:beta ~project:alpha ~project:beta ~audit:* ~ratelimit:* +@read +@write +@keyspace +@stream +@hash +@set +@string +@connection +@transaction +json.set +json.get +json.del +json.type +json.resp

# Client B - can only access project "gamma"
user client_b on >secure_password_b ~apikey:gamma:* ~apiprojectkeys:gamma ~project:gamma ~audit:* ~ratelimit:* +@read +@write +@keyspace +@stream +@hash +@set +@string +@connection +@transaction +json.set +json.get +json.del +json.type +json.resp

# Admin user - full access for management operations
user admin on >admin_password ~* +@all
```

#### Deployment Pattern

Deploy separate keymaster instances for each client:

```bash
# Client A instance
docker run -e REDIS_USERNAME=client_a -e REDIS_PASSWORD=secure_password_a keymaster

# Client B instance  
docker run -e REDIS_USERNAME=client_b -e REDIS_PASSWORD=secure_password_b keymaster
```

#### Benefits of Redis ACL Isolation

- **Database-level security**: Clients physically cannot access unauthorized projects
- **No application-level authentication needed**: Security handled by Redis
- **Complete isolation**: Stolen credentials only expose authorized projects
- **Simple deployment**: Each client just needs different Redis credentials
- **Audit separation**: Each client creates separate audit streams

## Data Model

### Redis Keys

- `project:{project_id}` → Project document
- `apikey:{project_id}:{key_id}` → API key document  
- `apiprojectkeys:{project_id}` → SET of key IDs
- `apimeta:{project_id}:{key_id}` → Usage metadata
- `audit:keylookup` → Audit event stream
- `ratelimit:key:{project_id}:{key_id}:{minute}` → Rate limit counters

### API Key Document

```json
{
  "key_id": "k_2J6Hqk3",
  "project_id": "merlin",
  "owner": "Mario",
  "metadata": "research-west",
  "secret_hash": "argon2id$...",
  "disabled": false,
  "created_at": 1732579200.0,
  "expires_at": null
}
```

### Audit Events

Stored in Redis Stream `audit:keylookup`:

```
ts: 1732579301.1
project_id: merlin
key_id: k_2J6Hqk3
result: ok|denied|rate_limited
client: keymanager
```

## Security

### Admin Authentication
- **Method**: Bearer token authentication
- **Token**: Matches `ADMIN_SECRET` environment variable
- **Scope**: All admin endpoints (mint, revoke, list, project management)
- **Generation**: Use `./scripts/generate_admin_secret.sh` for secure random tokens

### Password Hashing
- **Algorithm**: Argon2id (OWASP recommended)
- **Parameters**: time_cost=3, memory_cost=64MB, parallelism=1
- **Salt**: 16 bytes random salt per password

### Rate Limiting
- **Default**: 100 requests per minute per key
- **Implementation**: Redis INCR with TTL
- **Window**: Per-minute sliding window

### Access Control
- **Redis ACL**: Restricted user with minimal permissions
- **Key Patterns**: Limited to specific prefixes
- **Commands**: Only necessary Redis commands allowed
- **API Endpoints**: Public validation vs authenticated admin operations

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

Test coverage includes:
- ✅ API key validation (happy path < 20ms)
- ✅ Invalid/expired/disabled key handling
- ✅ Rate limiting behavior
- ✅ Key minting and revocation
- ✅ Audit logging
- ✅ Error handling
- ✅ Security verification

## Performance

### Benchmarks

- **Key Validation**: < 10ms p50, < 20ms p95 (intra-VPC)
- **Throughput**: > 1000 validations/second
- **Memory**: < 100MB resident set
- **Storage**: O(1) Redis operations

### Optimization

- Connection pooling with Redis
- Pipelined operations where possible
- Minimal JSON document sizes
- Efficient rate limiting with TTL

## Deployment

## Scripts

The project includes several utility scripts in the `scripts/` directory:

### `scripts/init_project.sh`
Complete project initialization - copies `env.example` to `.env` and generates all secrets:
```bash
./scripts/init_project.sh
```

### `scripts/setup_secrets.sh`
Generates secure passwords and updates configuration files:
```bash
./scripts/setup_secrets.sh
```
- Generates Redis manager password (no special characters)
- Generates admin secret for API authentication
- Creates `.env` and `redis_users.acl` files from templates if they don't exist
- Updates existing files with new secure passwords
- Creates backups with timestamps

### `scripts/reset_for_github.sh`
Resets the project to a clean state for GitHub deployment:
```bash
./scripts/reset_for_github.sh
```
- Removes all backup files
- Resets `.env` and `redis_users.acl` to template values (copies from `.example` files)
- Stops Docker containers
- Optionally removes Docker volumes

### Environment Variables

After running the setup scripts, your `.env` file will contain:

- `REDIS_PASSWORD`: Manager user password for Redis ACL
- `ADMIN_SECRET`: Bearer token for admin API endpoints
- `REDIS_HOST`, `REDIS_PORT`, etc.: Connection parameters

**Important**: The `.env` file contains secrets and should not be committed to version control.

### Production Checklist

- [ ] Run `./scripts/setup_secrets.sh` to generate secure secrets
- [ ] Secure the `.env` file with appropriate permissions
- [ ] Configure Redis with AOF/RDB persistence
- [ ] Set up Redis ACL with restricted user
- [ ] Enable TLS for Redis connections
- [ ] Configure log aggregation
- [ ] Set up monitoring and alerting
- [ ] Review rate limiting thresholds
- [ ] Backup strategy for Redis data
- [ ] Rotate admin secrets periodically

### Monitoring

Key metrics to monitor:
- Validation request rate and latency
- Error rates by type (denied, rate_limited, internal)
- Redis connection health
- Stream depth for audit logs
- Memory usage patterns

### Scaling

- **Horizontal**: Multiple Key Manager instances (stateless)
- **Redis**: Redis Cluster for high availability
- **Caching**: Connection pooling and keep-alive
- **Rate Limits**: Lua scripts for atomic operations

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting guide
- Review test examples
- Open an issue with detailed information
