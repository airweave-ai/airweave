# Airweave Analytics Module

This module provides PostHog analytics integration for Airweave, enabling comprehensive tracking of user behavior, business metrics, and system performance.

## 🏗️ Architecture

The analytics module is organized into several components:

- **`service.py`**: Core PostHog integration service
- **`decorators/`**: Decorators for automatic tracking of API endpoints and operations
- **`events/`**: Business event tracking classes for high-level metrics
- **`search_analytics.py`**: Shared utilities for unified search analytics tracking
- **`config.py`**: Analytics configuration (integrated into core config)

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

# Track a custom event
analytics.track_event(
    event_name="custom_event",
    distinct_id="user_123",
    properties={"key": "value"}
)

# Track business events
business_events.track_organization_created(
    organization_id=org_id,
    user_id=user_id,
    properties={"plan": "trial"}
)
```

### 3. Using Decorators

```python
from airweave.analytics import track_api_endpoint, track_search_operation, track_streaming_search_initiation

@track_api_endpoint("create_collection")
async def create_collection(ctx: ApiContext, ...):
    # Your endpoint logic
    pass

@track_search_operation()
async def search_collection(ctx: ApiContext, query: str, ...):
    # Your search logic
    pass

# For streaming search endpoints, use manual tracking after permission checks
@router.post("/{readable_id}/search/stream")
async def stream_search_collection_advanced(...):
    # Ensure permissions first
    await guard_rail.is_allowed(ActionType.QUERIES)

    # Track stream initiation after permission check
    from airweave.analytics.search_analytics import build_search_properties, track_search_event
    if ctx and search_request.query:
        properties = build_search_properties(
            ctx=ctx,
            query=search_request.query,
            collection_slug=readable_id,
            duration_ms=0,
            search_type="streaming",
        )
        track_search_event(ctx, properties, "search_stream_start")
```

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
- **`organization_created`**: New organization signup
- **`collection_created`**: New collection creation
- **`source_connection_created`**: New source integration

### Sync Events
- **`sync_completed`**: Successful sync job completion with entity counts

**Key Properties for PostHog Dashboards:**
- `entities_synced` ✅ **USE FOR BILLING** - Only INSERT + UPDATE (actual work done)
- `entities_processed` - Total operations including KEPT/SKIPPED (operational metric)
- `entities_inserted` - New entities added
- `entities_updated` - Existing entities modified
- `entities_deleted` - Entities removed
- `entities_kept` - Unchanged entities (hash match, no work done)
- `entities_skipped` - Failed/errored entities

**Important:** For billing dashboards and usage tracking, always use `entities_synced` which accurately reflects resource consumption (embeddings computed, vector writes performed, storage used). The `entities_processed` metric includes entities that were checked but required no work (KEPT) or failed (SKIPPED).

- **`entities_synced_by_type`**: Granular entity tracking per sync and entity type

## 🎯 Dashboard Strategy

### Dashboard 1: Airweave Overview
**Purpose:** High-level business metrics and system health
**Key Metrics:**
- Query volume over time (weekly/monthly)
- Query response times
- Popular data sources
- Error rates by endpoint
- Total entities in sync
- Query volume per organization

### Dashboard 2: User Journey
**Purpose:** Track user progression and identify drop-off points
**Key Metrics:**
- User funnel: org created → collection created → source added → first search
- Time to first search ("time to wow")
- Feature adoption rates
- User retention metrics

### Dashboard 3: Syncing & Storage
**Purpose:** Monitor sync performance and storage usage
**Key Metrics:**
- Sync success/error rates
- Entities synced per sync configuration
- Storage usage by organization
- Sync performance trends
- Entity type distribution

### Dashboard 4: Performance & Errors
**Purpose:** System reliability and performance monitoring
**Key Metrics:**
- API error rates by endpoint
- Search error rates
- Sync error rates
- Performance trends
- Error patterns and troubleshooting

### Dashboard 5: Advanced Analytics
**Purpose:** Deep insights and custom analysis
**Key Metrics:**
- Query patterns and complexity
- User behavior analysis
- Integration health scores
- Custom business metrics

## 📈 PostHog Widget Configurations

### Overview Dashboard Widgets
1. **Query Volume Over Time**
   - Event: `search_query`
   - Type: Line Chart
   - Property: Count
   - Time Range: Last 30 days

2. **Query Response Times**
   - Event: `search_query`
   - Type: Line Chart
   - Property: `duration_ms` (Average)
   - Time Range: Last 7 days

3. **Error Rate by Endpoint**
   - Event: `api_call_error`
   - Type: Bar Chart
   - Property: Count
   - Breakdown: `endpoint`
   - Time Range: Last 7 days

### User Journey Dashboard Widgets
1. **User Funnel**
   - Events: `organization_created` → `collection_created` → `source_connection_created` → `search_query`
   - Type: Funnel
   - Time Range: Last 30 days

2. **Time to First Search**
   - Event: `search_query`
   - Type: Histogram (if supported) or Line Chart
   - Property: Event timestamp (PostHog default)
   - Time Range: Last 30 days

### Syncing Dashboard Widgets
1. **Sync Success Rate**
   - Event: `sync_completed`
   - Type: Line Chart
   - Property: Count
   - Time Range: Last 30 days

2. **Entities Synced per Sync**
   - Event: `sync_completed`
   - Type: Bar Chart
   - Property: `entities_synced` (Sum) - **Use this for billing metrics**
   - Breakdown: `sync_id`
   - Time Range: Last 7 days
   - Alternative: Use `entities_processed` for operational metrics (includes kept/skipped)

3. **Storage Usage by Organization**
   - Event: `entities_synced_by_type`
   - Type: Bar Chart
   - Property: `entity_count` (Sum)
   - Breakdown: `organization_name`
   - Time Range: Last 7 days

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

# Development environment (.env.dev)
ANALYTICS_ENABLED=true
ENVIRONMENT=dev

# Local development (.env.local)
ANALYTICS_ENABLED=false
ENVIRONMENT=local

# Testing (.env.test)
ANALYTICS_ENABLED=false
ENVIRONMENT=test
```

### PostHog Dashboard Filtering

- **Production Only**: `environment = "prd"`
- **All Environments**: No filter
- **Exclude Local**: `environment != "local"`
- **Development Only**: `environment = "dev"`

## 💡 Best Practices

### 1. Use Decorators for Automatic Tracking
```python
@track_api_endpoint("endpoint_name")
async def my_endpoint(ctx: ApiContext, ...):
    # Automatically tracks timing, errors, and context
    pass

@track_search_operation()
async def search_endpoint(ctx: ApiContext, query: str, ...):
    # Automatically tracks search analytics with unified properties
    pass
```

### 2. Use Shared Search Analytics Utilities
```python
from airweave.analytics.search_analytics import build_search_properties, track_search_event

# Build unified search properties
properties = build_search_properties(
    ctx=ctx,
    query=query,
    collection_slug=collection_slug,
    duration_ms=duration_ms,
    search_type="streaming",  # or "regular"
    results=search_results,  # optional
    response_type="raw",  # optional
    status="success",
)

# Track the event
track_search_event(ctx, properties, "search_query")
```

### 3. Track Business Events at Key Milestones
```python
# Track when user completes onboarding
business_events.track_first_sync_completed(ctx, sync_id, entities_count)
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

- **Regular search endpoints**: Use `@track_search_operation()` decorator
- **Streaming search endpoints**: Use manual tracking after permission checks
- **Search completion**: Automatically tracked by SearchExecutor for both types
- **Unified events**: `search_stream_start` and `search_query` with consistent properties
- **Shared utilities**: Use `search_analytics.py` for consistent property building

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
