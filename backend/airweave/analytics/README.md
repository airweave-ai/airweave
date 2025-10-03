# Airweave Analytics Module

This module provides PostHog analytics integration for Airweave, enabling comprehensive tracking of user behavior, business metrics, and system performance.

## 🏗️ Architecture

The analytics module uses a **dual-pattern approach** for maximum flexibility:

### **API Layer (Dependency Injection)**
- **`contextual_service.py`**: Context-aware analytics service with automatic header capture
- **`deps.py`**: FastAPI dependency resolver for analytics service
- **Usage**: API endpoints with request context and headers

### **Service Layer (Global Singleton)**  
- **`service.py`**: Core PostHog integration service (global singleton)
- **`events/business_events.py`**: Business event tracking for service layers
- **Usage**: Background jobs, sync operations, service layers without request context

### **Key Features**
- **Automatic Header Capture**: SDK, client, framework, and session headers
- **User Identification**: Complete PostHog user journey tracking
- **Group Properties**: Organization-level segmentation and targeting
- **Context Injection**: Automatic user/org context in all events

## 🚀 Quick Start

### 1. Environment Setup

Add these variables to your `.env` file:

```bash
# PostHog Configuration
POSTHOG_API_KEY=phc_your_api_key_here
POSTHOG_HOST=https://app.posthog.com
ANALYTICS_ENABLED=true
```

### 2. Basic Usage

```python
from airweave.analytics import analytics, business_events

# Track a custom event using global analytics service
analytics.track_event(
    event_name="custom_event",
    distinct_id="user_123",
    properties={"key": "value"}
)

# Track business events (used in service layers)
business_events.track_source_connection_created(
    ctx=api_context,
    connection_id=conn_id,
    source_short_name="slack"
)

# Set organization group properties
business_events.set_organization_properties(
    organization_id=org_id,
    properties={"plan": "trial", "industry": "technology"}
)
```

### 3. Using Dependency Injection

```python
from airweave.analytics import ContextualAnalyticsService
from airweave.api import deps

@router.post("/", response_model=schemas.Collection)
async def create_collection(
    collection: schemas.CollectionCreate,
    ctx: ApiContext = Depends(deps.get_context),
    analytics: ContextualAnalyticsService = Depends(deps.get_analytics_service),
):
    # Your endpoint logic
    collection_obj = await collection_service.create(db, collection_in=collection, ctx=ctx)
    
    # Track with dependency injection - automatic context and headers
    analytics.track_api_call("create_collection")
    analytics.track_event("collection_created", {
        "collection_id": str(collection_obj.id),
        "collection_name": collection_obj.name,
    })
    
    return collection_obj

@router.post("/", response_model=schemas.Organization)
async def create_organization(
    organization_data: schemas.OrganizationCreate,
    analytics: ContextualAnalyticsService = Depends(deps.get_analytics_service),
):
    # Your endpoint logic
    organization = await organization_service.create_organization_with_integrations(...)
    
    # Identify user for complete PostHog user journey tracking
    analytics.identify_user({
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "organization_plan": "trial",
        "user_role": "owner",
    })
    
    # Track API call and business event
    analytics.track_api_call("create_organization")
    analytics.track_event("organization_created", {...})
    
    return organization

@router.post("/{readable_id}/search")
async def search_collection(
    readable_id: str,
    search_request: SearchRequest,
    ctx: ApiContext = Depends(deps.get_context),
    analytics: ContextualAnalyticsService = Depends(deps.get_analytics_service),
):
    # Your search logic
    result = await search_service.search_with_request(...)
    
    # Track search with dependency injection
    analytics.track_search_query(
        query=search_request.query,
        collection_slug=readable_id,
        duration_ms=duration_ms,
        search_type="advanced",
        results_count=len(result.results) if result.results else 0,
        status="success"
    )
    
    return result
```

## 🔍 Automatic Header Capture & User Identification

### **Request Headers Automatically Captured**

The `ContextualAnalyticsService` automatically extracts and includes these headers in all events:

```python
# SDK Headers
X-SDK-Name: airweave-python
X-SDK-Version: 1.2.3

# Client Headers  
X-Client-Name: airweave-frontend
X-Client-Version: 2.1.0

# Framework Headers (future)
X-Framework-Name: langchain
X-Framework-Version: 0.1.0

# Session Headers
X-Session-ID: session_123
X-Request-ID: req_456
User-Agent: CustomAgent/1.0
```

### **User Identification**

```python
# Automatically called during user registration and organization creation
analytics.identify_user({
    "email": "user@example.com",
    "full_name": "John Doe", 
    "auth0_id": "auth0|507f1f77bcf86cd799439011",
    "created_at": "2025-01-01T00:00:00Z",
    "plan": "trial",
    "signup_source": "auth0"
})
```

### **Group Properties (Organization-Level)**

```python
# Sets organization properties for PostHog segmentation
business_events.set_organization_properties(
    organization_id=org_id,
    properties={
        "organization_name": "Acme Corp",
        "organization_plan": "enterprise", 
        "organization_created_at": "2025-01-01T00:00:00Z",
        "organization_source": "signup",
        "organization_industry": "technology"
    }
)
```

### **Benefits**
- **Complete User Journey**: Link all events to identified user profiles
- **SDK Tracking**: Identify which SDKs/clients are being used
- **Organization Segmentation**: Filter analytics by organization properties
- **Feature Flag Targeting**: Enable features based on organization type/plan

## 📊 Complete Analytics Events Overview

### API Events
- **`api_call`**: Successful API calls with timing and context
- **`api_call_error`**: Failed API calls with error details and status codes

**Covered Endpoints:**
- `create_organization` - Organization creation
- `list_collections` - Collection listing  
- `create_collection` - Collection creation
- `create_source_connection` - Source connection setup
- `run_sync` - Sync execution
- `search` - Basic search queries
- `search_advanced` - Advanced search queries

### Search Events
- **`search_stream_start`**: Streaming search initiation (after permission check)
- **`search_query`**: Successful search operations with unified analytics (regular and streaming)
- **`search_query_error`**: Failed search operations with error details

**Search Event Properties:**
- `query_length`: Length of search query
- `collection_slug`: Collection identifier
- `duration_ms`: Search execution time
- `search_type`: "regular" or "streaming"
- `results_count`: Number of results returned
- `organization_name`: Organization name
- `status`: "success" or error status
- `response_type`: Response type (for regular searches)

### Business Events
- **`source_connection_created`**: New source integration
- **`sync_started`**: Sync operation initiation
- **`sync_completed`**: Successful sync job completion with entity counts
- **`sync_failed`**: Failed sync operations with error details
- **`sync_cancelled`**: Cancelled sync operations

### User Identification
- **`identify_user`**: Links all future events to identified user profiles
- **User Properties**: email, full_name, auth0_id, created_at, plan, signup_source
- **Organization Properties**: organization_id, organization_name, organization_plan, user_role

### Group Properties (PostHog Organizations)
- **`set_organization_properties`**: Sets organization-level properties for segmentation
- **Organization Properties**: organization_name, organization_plan, organization_created_at, organization_source
- **Benefits**: Organization segmentation, feature flag targeting, cohort analysis


## 🔧 Configuration

The analytics module respects these configuration options:

- `POSTHOG_API_KEY`: Your PostHog API key (required)
- `POSTHOG_HOST`: PostHog host URL (default: https://app.posthog.com)
- `ANALYTICS_ENABLED`: Enable/disable analytics (default: true)
- `ENVIRONMENT`: Deployment environment - added as property to all events

**Important**: Analytics events are emitted when `ANALYTICS_ENABLED=true`. Each event includes an `environment` property allowing you to filter by environment in PostHog dashboards. Control which environments emit events via their respective environment files.

### Environment Configuration Examples

```bash
# Production environment (.env.prod)
ANALYTICS_ENABLED=true
ENVIRONMENT=prd
```

### PostHog Dashboard Filtering

- **Production Only**: `environment = "prd"`
- **All Environments**: No filter
- **Exclude Local**: `environment != "local"`
- **Development Only**: `environment = "dev"`

## 💡 Best Practices

### 1. Use Dependency Injection for API Endpoints
```python
async def my_endpoint(
    ctx: ApiContext = Depends(deps.get_context),
    analytics: ContextualAnalyticsService = Depends(deps.get_analytics_service),
):
    # Track API call with automatic context and headers
    analytics.track_api_call("endpoint_name")
    
    # Track custom events
    analytics.track_event("custom_event", {"key": "value"})
```

### 2. Use Global Analytics for Service Layers
```python
from airweave.analytics import business_events

# In sync operations, service layers, etc.
business_events.track_sync_completed(ctx, sync_id, entities_processed, duration_ms)
```

### 3. Track Business Events at Key Milestones
```python
# Track sync operations
business_events.track_sync_started(ctx, sync_id, source_type, collection_id)
business_events.track_sync_completed(ctx, sync_id, entities_processed, duration_ms)

# Set organization properties
business_events.set_organization_properties(org_id, {"plan": "enterprise"})
```

### 4. Include Rich Context
```python
analytics.track_event(
    event_name="custom_event",
    distinct_id=user_id,
    properties={
        "organization_name": ctx.organization.name,
        "plan": ctx.organization.plan,
        "feature": "advanced_search"
    },
    groups={"organization": str(ctx.organization.id)}
)
```

### 5. Handle Errors Gracefully
The analytics service automatically handles PostHog errors and logs them without affecting your application.

### 6. Unified Search Analytics
All search operations (regular and streaming) now use unified analytics tracking:

- **API endpoints**: Use `analytics.track_search_query()` with dependency injection
- **Streaming search endpoints**: Use manual tracking after permission checks
- **Search completion**: Automatically tracked by SearchExecutor for both types
- **Unified events**: `search_stream_start` and `search_query` with consistent properties
- **Consistent properties**: All search events include query_length, collection_slug, duration_ms, etc.

**Important**: For streaming endpoints, always track analytics AFTER permission checks to avoid counting blocked requests.

## 🔒 Privacy & Compliance

- All user data is sent to PostHog (ensure compliance with your privacy policy)
- Distinct IDs are not hashed by default; ensure compliance when sending user identifiers.
- Sensitive data should not be included in event properties
- Consider data retention policies in PostHog

## 🚨 Troubleshooting

### Common Issues

1. **Events not appearing in PostHog**
   - Check `POSTHOG_API_KEY` is set correctly
   - Verify `ANALYTICS_ENABLED=true`
   - Check logs for PostHog errors

2. **High event volume**
   - PostHog free tier: 1M events/month
   - Consider sampling for high-volume events
   - Use `ANALYTICS_ENABLED=false` to disable

3. **Performance impact**
   - Analytics calls are async and non-blocking
   - Errors are logged but don't affect application flow
   - Consider batching for high-frequency events

## 📚 Additional Resources

- [PostHog Documentation](https://posthog.com/docs)
- [PostHog Python SDK](https://posthog.com/docs/libraries/python)
