# Airweave Analytics Module

This module provides PostHog analytics integration for Airweave, enabling comprehensive tracking of user behavior, business metrics, and system performance.

## 🏗️ Architecture

The analytics module is organized into several components:

- **`service.py`**: Core PostHog integration service
- **`contextual_service.py`**: Context-aware analytics service with dependency injection
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

# Track events with context (recommended for API endpoints)
async def my_endpoint(ctx: ApiContext, ...):
    analytics.track_event("custom_event", {"key": "value"})
```

### 3. Dependency Injection Architecture

```python
# Analytics service is automatically injected via ApiContext
async def my_endpoint(ctx: ApiContext, ...):
    # Track custom events with automatic context
    analytics.track_event("custom_event", {"key": "value"})

    # Search operations are automatically tracked
    # No manual tracking needed in endpoints
```

### 4. Search Analytics

```python
# Search operations are automatically tracked via SearchService
# No manual tracking required in endpoints

# For custom search analytics, use the utilities:
from airweave.analytics.search_analytics import track_search_completion

# This is already done automatically in SearchService.search()
track_search_completion(
    ctx=ctx,
    query="search query",
    collection_slug="my-collection",
    duration_ms=150.0,
    results=search_results,
    completion=ai_response,  # Optional AI completion
    search_type="regular",   # or "streaming"
)
```

## 📊 Complete Analytics Events Overview

### API Events
- **Custom Events**: Tracked via `analytics.track_event()` in API endpoints
- **Business Events**: Tracked via `business_events.track_*()` methods

**Covered Endpoints:**
- All API endpoints can track custom events using `analytics.track_event()`
- Business events tracked for key milestones (organization creation, sync completion, etc.)

### Search Events
- **`search_query`**: Automatically tracked for all search operations (regular and streaming)
- **Search completion**: Tracked via `SearchService.search()` with comprehensive analytics

**Search Event Properties:**
- `query_length`: Length of search query
- `collection_slug`: Collection identifier
- `duration_ms`: Search execution time
- `search_type`: "regular" or "streaming"
- `results_count`: Number of results returned
- `has_completion`: Whether AI generated a response
- `completion_length`: Length of AI-generated completion
- `retrieval_strategy`: "hybrid", "neural", or "keyword"
- `temporal_relevance`: Recency weight (0-1)
- `expand_query`, `interpret_filters`, `rerank`, `generate_answer`: Feature flags
- `organization_name`: Organization name (auto-included)
- `auth_method`: Authentication method (auto-included)

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

### 1. Use Dependency Injection for Analytics
```python
async def my_endpoint(ctx: ApiContext, ...):
    # Analytics service is pre-configured with user/org context
    analytics.track_event("custom_event", {"key": "value"})

    # Search operations are automatically tracked - no manual work needed
    pass
```

### 2. Search Analytics (Automatic)
```python
# Search analytics are automatically handled by SearchService
# No manual tracking required in endpoints

# The service automatically tracks:
# - Query details and performance metrics
# - AI completion data (if generated)
# - Search configuration and feature usage
# - User and organization context
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
All search operations (regular and streaming) use unified analytics tracking:

- **All search endpoints**: Analytics automatically handled by `SearchService.search()`
- **No manual tracking**: No decorators or manual tracking needed in endpoints
- **Comprehensive data**: Tracks query details, performance, AI completion, and configuration
- **Unified events**: Single `search_query` event with consistent properties across all search types
- **Dependency injection**: Analytics service pre-configured with user/org context

**Important**: Search analytics are completely automatic - no manual tracking required in endpoints.

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
