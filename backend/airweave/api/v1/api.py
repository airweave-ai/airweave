"""API routes for the FastAPI application."""

from airweave.api.router import TrailingSlashRouter
from airweave.api.v1.endpoints import (
    api_keys,
    chat,
    connections,
    cursor_dev,
    dag,
    destinations,
    embedding_models,
    entities,
    health,
    search,
    sources,
    sync,
    transformers,
    users,
    white_label,
)
from airweave.core.config import settings

# Use our custom router that handles trailing slashes
api_router = TrailingSlashRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api_keys"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(destinations.router, prefix="/destinations", tags=["destinations"])
api_router.include_router(
    embedding_models.router, prefix="/embedding_models", tags=["embedding_models"]
)
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(white_label.router, prefix="/white_labels", tags=["white_labels"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(dag.router, prefix="/dag", tags=["dag"])
api_router.include_router(entities.router, prefix="/entities", tags=["entities"])
api_router.include_router(transformers.router, prefix="/transformers", tags=["transformers"])

# Only include cursor development endpoints if LOCAL_CURSOR_DEVELOPMENT is enabled
if settings.LOCAL_CURSOR_DEVELOPMENT:
    api_router.include_router(cursor_dev.router, prefix="/cursor-dev", tags=["Cursor Development"])
