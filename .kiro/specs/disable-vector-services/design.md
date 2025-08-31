# Design Document

## Overview

This design outlines the configuration changes needed to disable vector-based services and modify default billing settings in the Airweave platform. The changes involve:

1. Disabling vector RAG-based destinations (primarily Qdrant)
2. Removing Redis-based sync monitoring dependencies
3. Preventing Qdrant vector database operations
4. Changing the default billing plan from "TRIAL" to "ENTERPRISE"

## Architecture

### Current State Analysis

Based on the codebase analysis:

- **Vector Destinations**: Qdrant is the primary vector destination (`backend/airweave/platform/destinations/qdrant.py`)
- **Redis Usage**: Used for pub/sub operations and connection pooling (`backend/airweave/core/redis_client.py`)
- **Sync Monitoring**: Currently uses database-based sync job tracking, with Redis for pub/sub notifications
- **Billing Plans**: Default billing plan is "TRIAL" in `OrganizationBilling` model

### Target Architecture

The system will operate in a "non-vector" mode where:

1. **Vector operations are disabled**: All vector-related destinations and operations return appropriate errors
2. **Redis dependencies are optional**: Sync monitoring falls back to database-only operations
3. **Qdrant connections are prevented**: Configuration prevents Qdrant client initialization
4. **Enterprise billing default**: New organizations get "ENTERPRISE" plan by default

## Components and Interfaces

### 1. Configuration Management

**Component**: `Settings` class in `backend/airweave/core/config.py`

**Changes**:
- Add new configuration flags:
  - `VECTOR_SERVICES_ENABLED: bool = False`
  - `REDIS_MONITORING_ENABLED: bool = False`
  - `QDRANT_ENABLED: bool = False`
  - `DEFAULT_BILLING_PLAN: str = "ENTERPRISE"`

**Interface**:
```python
class Settings(BaseSettings):
    # Existing fields...
    
    # New vector service control flags
    VECTOR_SERVICES_ENABLED: bool = False
    REDIS_MONITORING_ENABLED: bool = False
    QDRANT_ENABLED: bool = False
    DEFAULT_BILLING_PLAN: str = "ENTERPRISE"
```

### 2. Vector Destination Control

**Component**: `QdrantDestination` class in `backend/airweave/platform/destinations/qdrant.py`

**Changes**:
- Add initialization checks for `QDRANT_ENABLED` flag
- Modify `connect_to_qdrant()` method to fail fast when disabled
- Add error responses for all vector operations when disabled

**Interface**:
```python
class QdrantDestination(VectorDBDestination):
    async def connect_to_qdrant(self) -> None:
        if not settings.QDRANT_ENABLED:
            raise ConnectionError("Qdrant services are disabled in this deployment")
        # Existing connection logic...
```

### 3. Redis Monitoring Control

**Component**: `RedisClient` class in `backend/airweave/core/redis_client.py`

**Changes**:
- Add conditional initialization based on `REDIS_MONITORING_ENABLED`
- Provide no-op implementations when Redis is disabled
- Ensure sync operations work without Redis dependencies

**Interface**:
```python
class RedisClient:
    def __init__(self):
        if settings.REDIS_MONITORING_ENABLED:
            # Initialize Redis clients
        else:
            # Set clients to None, use no-op implementations
```

### 4. Billing Plan Default

**Component**: `OrganizationBilling` model in `backend/airweave/models/organization_billing.py`

**Changes**:
- Modify default billing plan from "TRIAL" to use configuration
- Update organization creation logic to use new default

**Interface**:
```python
class OrganizationBilling(Base):
    billing_plan: Mapped[str] = mapped_column(
        String(50), 
        default=lambda: settings.DEFAULT_BILLING_PLAN, 
        nullable=False
    )
```

### 5. Destination Factory Control

**Component**: Destination registration and factory systems

**Changes**:
- Add checks in destination factory to prevent vector destination creation
- Modify destination listing to exclude vector destinations when disabled

## Data Models

### Configuration Schema

```python
# New configuration fields in Settings
VECTOR_SERVICES_ENABLED: bool = False
REDIS_MONITORING_ENABLED: bool = False  
QDRANT_ENABLED: bool = False
DEFAULT_BILLING_PLAN: str = "ENTERPRISE"
```

### Billing Model Updates

```python
# Modified default in OrganizationBilling
billing_plan: Mapped[str] = mapped_column(
    String(50), 
    default=lambda: settings.DEFAULT_BILLING_PLAN,
    nullable=False
)
```

## Error Handling

### Vector Service Errors

When vector services are disabled:

1. **Qdrant Connection Attempts**: Return `ConnectionError` with clear message
2. **Vector Destination Creation**: Return `ServiceUnavailableError`
3. **Search Operations**: Return `FeatureDisabledError` with alternative suggestions

### Redis Fallback Behavior

When Redis monitoring is disabled:

1. **Pub/Sub Operations**: Use no-op implementations that log but don't fail
2. **Sync Status Updates**: Fall back to database-only storage
3. **Real-time Notifications**: Disable gracefully with appropriate user messaging

### Graceful Degradation

- **Search Functionality**: Disable vector search, keep text-based search if available
- **Sync Operations**: Continue working with database-only monitoring
- **API Endpoints**: Return appropriate HTTP status codes (503 for disabled services)

## Testing Strategy

### Unit Tests

1. **Configuration Tests**:
   - Test flag behavior in different combinations
   - Verify default billing plan application
   - Test environment variable parsing

2. **Service Disable Tests**:
   - Test Qdrant connection failures when disabled
   - Test Redis client no-op behavior
   - Test destination factory filtering

3. **Billing Tests**:
   - Test organization creation with new default plan
   - Test existing organization behavior unchanged

### Integration Tests

1. **End-to-End Disable Tests**:
   - Test full application startup with services disabled
   - Test sync operations without Redis
   - Test API responses for disabled vector endpoints

2. **Fallback Behavior Tests**:
   - Test sync monitoring without Redis
   - Test search functionality without vector services
   - Test error handling and user messaging

### Configuration Tests

1. **Environment Variable Tests**:
   - Test different flag combinations
   - Test configuration validation
   - Test default value behavior

2. **Deployment Tests**:
   - Test Docker container startup with new flags
   - Test configuration file parsing
   - Test runtime configuration changes