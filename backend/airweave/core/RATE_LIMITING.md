# Rate Limiting Implementation

## Overview

Airweave implements distributed rate limiting using Redis with a sliding window algorithm. Rate limits are applied per organization and automatically adjust based on the billing plan tier.

## Features

- **Distributed**: Works across multiple horizontally scaled pods using shared Redis
- **Plan-aware**: Automatically adjusts limits based on billing plan (Developer, Pro, Team, Enterprise)
- **Accurate**: Sliding window prevents burst issues at window boundaries
- **Informative**: Returns standard RFC 6585 rate limit headers
- **Performant**: Single Redis call per request using pipeline
- **Fail-safe**: Allows requests through on Redis failures (fail-open)
- **Configurable**: Can be disabled or bypassed in development

## Architecture

### Components

1. **RateLimiterService** (`core/rate_limiter_service.py`)
   - Redis-backed sliding window implementation
   - Plan-based limit resolution
   - Automatic caching of organization limits

2. **Middleware** (`api/middleware.py`)
   - `rate_limit_middleware`: Enforces rate limits before request processing
   - `request_timeout_middleware`: Prevents long-running requests (60s timeout)

3. **Exception Handling**
   - `RateLimitExceededException`: Raised when limit is exceeded
   - `rate_limit_exception_handler`: Returns 429 with proper headers

## Rate Limits by Plan

| Plan       | Requests/Second | Cost         |
|------------|-----------------|--------------|
| Developer  | 10              | Free tier    |
| Pro        | 25              | $29/month    |
| Team       | 50              | $99/month    |
| Enterprise | Unlimited       | Custom       |

**Note**: Legacy organizations without billing receive Pro tier limits (25 req/s).

## Configuration

### Environment Variables

```bash
# Rate limiting configuration
RATE_LIMIT_ENABLED=true           # Enable/disable rate limiting
REQUEST_TIMEOUT_SECONDS=60        # Request timeout in seconds
REQUEST_BODY_SIZE_LIMIT=10485760  # Max request body size (10MB)

# Redis configuration (required for rate limiting)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=optional_password
REDIS_DB=0
```

### Disabling Rate Limiting

Rate limiting is automatically disabled in local development mode (`LOCAL_DEVELOPMENT=true`) or can be explicitly disabled:

```python
# In config.py
RATE_LIMIT_ENABLED = False
```

## API Response Headers

### Successful Requests

```http
HTTP/1.1 200 OK
RateLimit-Limit: 25
RateLimit-Remaining: 24
RateLimit-Reset: 1234567890
```

### Rate Limited Requests

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 1
RateLimit-Limit: 25
RateLimit-Remaining: 0
RateLimit-Reset: 1234567890
Content-Type: application/json

{
  "detail": "Rate limit exceeded. Please retry after 0.85 seconds. Limit: 25 requests per second."
}
```

## Usage

### Automatic Middleware Protection

Rate limiting is automatically applied to all API endpoints except:
- `/` (root)
- `/openapi.json`
- `/health`
- `/docs`
- `/redoc`

No additional code is needed in endpoints - the middleware handles everything.

### Manual Rate Limit Checks (Optional)

For custom rate limiting logic in specific endpoints:

```python
from fastapi import Depends
from airweave.api.deps import get_rate_limiter_service
from airweave.core.rate_limiter_service import RateLimiterService

@router.post("/expensive-operation")
async def expensive_operation(
    rate_limiter: RateLimiterService = Depends(get_rate_limiter_service),
):
    # Check rate limit before processing
    allowed, retry_after, limit, remaining = await rate_limiter.check_rate_limit()

    if not allowed:
        # Will automatically raise RateLimitExceededException
        pass

    # Process request
    return {"status": "success"}
```

## Redis Data Structure

Rate limits use Redis sorted sets (ZSET) for the sliding window:

```
Key: rate_limit:org:<organization_id>
Type: ZSET
Score: Unix timestamp (float)
Value: Unix timestamp (string)
TTL: 2 seconds (auto-cleanup)
```

### Example Redis Data

```redis
# Add request at current timestamp
ZADD rate_limit:org:123e4567-e89b-12d3-a456-426614174000 1234567890.123 "1234567890.123"

# Count requests in last second
ZCOUNT rate_limit:org:123e4567-e89b-12d3-a456-426614174000 1234567889.123 1234567890.123

# Remove old entries
ZREMRANGEBYSCORE rate_limit:org:123e4567-e89b-12d3-a456-426614174000 0 1234567889.123
```

## Algorithm: Sliding Window

The sliding window algorithm provides accurate rate limiting without edge cases:

1. **Record Request**: Add current timestamp to ZSET
2. **Count Active**: Count entries within the 1-second window
3. **Check Limit**: Compare count to organization's limit
4. **Clean Up**: Remove timestamps older than window
5. **Set TTL**: Auto-expire key after 2 seconds

### Why Sliding Window?

- **No burst at boundaries**: Fixed windows allow bursts at window edges
- **Accurate counting**: Counts exact requests in rolling window
- **Memory efficient**: Old entries automatically expire
- **Distributed safe**: Works correctly across multiple pods

## Testing

### Unit Tests

```bash
cd backend
pytest tests/test_rate_limiter_service.py -v
```

### Load Testing

Test rate limiting under load:

```python
import asyncio
import aiohttp

async def test_rate_limit():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(100):  # Send 100 requests
            tasks.append(
                session.get(
                    "http://localhost:8001/api/v1/collections",
                    headers={"X-Organization-ID": "your-org-id"}
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful vs rate limited
        success = sum(1 for r in responses if r.status == 200)
        rate_limited = sum(1 for r in responses if r.status == 429)

        print(f"Successful: {success}, Rate Limited: {rate_limited}")

asyncio.run(test_rate_limit())
```

## Monitoring

### Key Metrics to Monitor

1. **Rate Limit Hits**: Count of 429 responses
2. **Redis Performance**: Latency of rate limit checks
3. **Organization Usage**: Requests per second by org
4. **False Positives**: Legitimate requests blocked

### Logging

Rate limit events are logged at different levels:

```python
# Allowed requests (DEBUG)
logger.debug("Rate limit check passed for organization X: 11/25 requests")

# Blocked requests (WARNING)
logger.warning("Rate limit exceeded for organization X: 25/25 requests, retry after 0.5s")

# Redis errors (ERROR)
logger.error("Redis error during rate limit check: Connection refused. Allowing request.")
```

## Troubleshooting

### Rate Limiting Not Working

1. **Check Redis connection**:
   ```bash
   redis-cli -h localhost -p 6379 ping
   ```

2. **Verify configuration**:
   ```python
   from airweave.core.config import settings
   print(f"Rate limiting enabled: {settings.RATE_LIMIT_ENABLED}")
   print(f"Local development: {settings.LOCAL_DEVELOPMENT}")
   ```

3. **Check logs** for rate limit events

### Requests Incorrectly Blocked

1. **Verify organization plan**:
   ```sql
   SELECT plan FROM billing_periods WHERE organization_id = 'X' AND status = 'active';
   ```

2. **Check Redis keys**:
   ```bash
   redis-cli KEYS "rate_limit:org:*"
   redis-cli ZRANGE rate_limit:org:123... 0 -1 WITHSCORES
   ```

3. **Temporarily disable** for testing:
   ```bash
   RATE_LIMIT_ENABLED=false
   ```

### Redis Memory Issues

Rate limit keys auto-expire, but if memory is an issue:

```bash
# Check memory usage
redis-cli INFO memory

# Clear all rate limit keys (emergency only)
redis-cli KEYS "rate_limit:org:*" | xargs redis-cli DEL
```

## Security Considerations

1. **Organization ID Validation**: Rate limiting uses the `X-Organization-ID` header, which is validated by `get_context` dependency

2. **Fail-Open Design**: Redis failures allow requests through to prevent service disruption

3. **No PII in Redis**: Only timestamps and organization IDs are stored

4. **Automatic Cleanup**: Keys expire automatically to prevent data accumulation

## Future Enhancements

Potential improvements for future versions:

- [ ] Per-endpoint rate limits (e.g., search = 10/s, other = 25/s)
- [ ] Burst allowance (e.g., 100 requests in 10 seconds)
- [ ] IP-based rate limiting for unauthenticated endpoints
- [ ] Rate limit analytics dashboard
- [ ] Dynamic limit adjustment based on system load
- [ ] Rate limit exemptions for specific organizations
