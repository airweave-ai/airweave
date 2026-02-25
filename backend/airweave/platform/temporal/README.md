# Temporal Integration

This directory contains the Temporal workflow integration for Airweave.

## Overview

Temporal is used for orchestrating long-running sync jobs with reliability and observability.

## Components

- `worker.py` - The Temporal worker that processes sync jobs
- `workflows.py` - Workflow definitions for sync operations
- `activities.py` - Individual activities that workflows orchestrate
- `client.py` - Client utilities for interacting with Temporal

## Local Development

1. Ensure Temporal is running (included in docker-compose):
```bash
docker-compose -f docker/docker-compose.dev.yml up -d
```

2. The worker will start automatically with the backend.

3. Access Temporal UI at http://localhost:8233

## Configuration

Temporal settings are configured via environment variables:
- `TEMPORAL_HOST` - Temporal server host (default: localhost)
- `TEMPORAL_PORT` - Temporal server port (default: 7233)
- `TEMPORAL_NAMESPACE` - Namespace to use (default: default)
- `TEMPORAL_TASK_QUEUE` - Task queue name (default: airweave-sync-queue)

## Running

The Temporal server and worker are automatically started with `docker-compose up`:

```bash
# From project root
docker-compose -f docker/docker-compose.yml up -d

# Or for development
docker-compose -f docker/docker-compose.dev.yml up -d
```

## Testing

Temporal workflows can be tested using the Temporal testing framework. See the test files for examples.

## Fallback Behavior

If Temporal is not available, the system automatically falls back to using FastAPI's `BackgroundTasks` for backward compatibility.

## Integration Points

The Temporal integration is used in:
- `POST /source-connections/{id}/run` - Run individual source connection

Both endpoints check if Temporal is available and fall back to background tasks if needed.

## Monitoring

- **Temporal UI**: http://localhost:8233 - View workflows, activities, and task queues
- **Worker Logs**: `docker logs -f airweave-temporal-worker`
- **Server Logs**: `docker logs -f airweave-temporal`

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │    │  Temporal Server │    │ Temporal Worker │
│   (Local/Debug) │───▶│   (Docker)       │───▶│   (Docker)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   PostgreSQL     │    │  sync_service   │
                       │   (Docker)       │    │  .run()         │
                       └──────────────────┘    └─────────────────┘
```
