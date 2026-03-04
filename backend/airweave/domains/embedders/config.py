"""Deployment-wide embedding configuration.

Reads from environment variables (.env) — no defaults.
All three must be explicitly set: DENSE_EMBEDDER, EMBEDDING_DIMENSIONS, SPARSE_EMBEDDER.

Startup validation ensures they exist in the registry, dimensions are valid,
credentials are present, and the DB deployment metadata row is consistent.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.domains.embedders.protocols import (
    DenseEmbedderRegistryProtocol,
    SparseEmbedderRegistryProtocol,
)
from airweave.domains.embedders.types import DenseEmbedderEntry, SparseEmbedderEntry
from airweave.models.vector_db_deployment_metadata import VectorDbDeploymentMetadata


class EmbeddingConfigError(Exception):
    """Hard error raised when embedding config is invalid or mismatched."""


# ---------------------------------------------------------------------------
# Read from environment — validated in validate_embedding_config() at startup
# ---------------------------------------------------------------------------

DENSE_EMBEDDER: str = settings.DENSE_EMBEDDER or ""
EMBEDDING_DIMENSIONS: int = settings.EMBEDDING_DIMENSIONS or 0
SPARSE_EMBEDDER: str = settings.SPARSE_EMBEDDER or ""


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------


def validate_embedding_config_sync(
    *,
    dense_registry: DenseEmbedderRegistryProtocol,
    sparse_registry: SparseEmbedderRegistryProtocol,
) -> None:
    """Validate env vars, registry lookups, dimensions, and credentials (no DB needed).

    Called from the DI container factory *before* embedder instances are constructed,
    so that missing/invalid config produces a clear error instead of a raw KeyError.

    Raises:
        EmbeddingConfigError on any mismatch.
    """
    dense_names = [e.short_name for e in dense_registry.list_all()]
    sparse_names = [e.short_name for e in sparse_registry.list_all()]

    # Check required settings are present
    if not DENSE_EMBEDDER:
        raise EmbeddingConfigError(
            f"Required environment variable 'DENSE_EMBEDDER' is not set. "
            f"Add it to your .env file.\n  Available options: {', '.join(dense_names)}"
        )
    if not EMBEDDING_DIMENSIONS:
        raise EmbeddingConfigError(
            "Required environment variable 'EMBEDDING_DIMENSIONS' is not set. "
            "Add it to your .env file."
        )
    if not SPARSE_EMBEDDER:
        raise EmbeddingConfigError(
            f"Required environment variable 'SPARSE_EMBEDDER' is not set. "
            f"Add it to your .env file.\n  Available options: {', '.join(sparse_names)}"
        )

    # Check embedder names exist in registry
    try:
        dense_spec = dense_registry.get(DENSE_EMBEDDER)
    except KeyError:
        raise EmbeddingConfigError(
            f"Dense embedder '{DENSE_EMBEDDER}' not found in registry. "
            f"Available options: {', '.join(dense_names)}"
        )

    try:
        sparse_spec = sparse_registry.get(SPARSE_EMBEDDER)
    except KeyError:
        raise EmbeddingConfigError(
            f"Sparse embedder '{SPARSE_EMBEDDER}' not found in registry. "
            f"Available options: {', '.join(sparse_names)}"
        )

    _validate_dimensions(dense_spec)
    _validate_credentials(dense_spec, sparse_spec)


async def validate_embedding_config(db: AsyncSession) -> None:
    """Reconcile embedding config against the DB deployment metadata table.

    The env-var / registry / dimensions / credentials checks are handled earlier
    by validate_embedding_config_sync() during container initialization.
    This async step only needs a DB session.

    Raises:
        EmbeddingConfigError on any mismatch.
    """
    await _reconcile_db(db)


def _validate_dimensions(dense_spec: DenseEmbedderEntry) -> None:
    """Validate EMBEDDING_DIMENSIONS against the dense embedder spec."""
    if dense_spec.supports_matryoshka:
        if EMBEDDING_DIMENSIONS > dense_spec.max_dimensions:
            raise EmbeddingConfigError(
                f"EMBEDDING_DIMENSIONS={EMBEDDING_DIMENSIONS} exceeds max_dimensions="
                f"{dense_spec.max_dimensions} for dense embedder '{DENSE_EMBEDDER}'."
            )
    elif EMBEDDING_DIMENSIONS != dense_spec.max_dimensions:
        raise EmbeddingConfigError(
            f"Dense embedder '{DENSE_EMBEDDER}' does not support Matryoshka dimensions — "
            f"EMBEDDING_DIMENSIONS must be exactly {dense_spec.max_dimensions}, "
            f"got {EMBEDDING_DIMENSIONS}."
        )


def _validate_credentials(
    dense_spec: DenseEmbedderEntry,
    sparse_spec: SparseEmbedderEntry,
) -> None:
    """Check that required API keys / settings are present."""
    if dense_spec.required_setting:
        value = getattr(settings, dense_spec.required_setting, None)
        if not value:
            raise EmbeddingConfigError(
                f"Dense embedder '{DENSE_EMBEDDER}' requires setting "
                f"'{dense_spec.required_setting}' but it is not set."
            )

    if sparse_spec.required_setting:
        value = getattr(settings, sparse_spec.required_setting, None)
        if not value:
            raise EmbeddingConfigError(
                f"Sparse embedder '{SPARSE_EMBEDDER}' requires setting "
                f"'{sparse_spec.required_setting}' but it is not set."
            )


async def _reconcile_db(db: AsyncSession) -> None:
    """Reconcile code config against the vector_db_deployment_metadata table."""
    result = await db.execute(select(VectorDbDeploymentMetadata).limit(1))
    row = result.scalar_one_or_none()

    if row is None:
        row = VectorDbDeploymentMetadata(
            dense_embedder=DENSE_EMBEDDER,
            embedding_dimensions=EMBEDDING_DIMENSIONS,
            sparse_embedder=SPARSE_EMBEDDER,
        )
        db.add(row)
        await db.commit()
        logger.info(
            f"[EmbeddingConfig] First deploy — created vector_db_deployment_metadata row: "
            f"dense={DENSE_EMBEDDER}, dims={EMBEDDING_DIMENSIONS}, sparse={SPARSE_EMBEDDER}"
        )
        return

    mismatches = []
    if row.dense_embedder != DENSE_EMBEDDER:
        mismatches.append(f"dense_embedder: code={DENSE_EMBEDDER}, db={row.dense_embedder}")
    if row.embedding_dimensions != EMBEDDING_DIMENSIONS:
        mismatches.append(
            f"embedding_dimensions: code={EMBEDDING_DIMENSIONS}, db={row.embedding_dimensions}"
        )
    if row.sparse_embedder != SPARSE_EMBEDDER:
        mismatches.append(f"sparse_embedder: code={SPARSE_EMBEDDER}, db={row.sparse_embedder}")

    if mismatches:
        detail = "; ".join(mismatches)
        raise EmbeddingConfigError(
            f"Embedding config mismatch: {detail}. "
            f"Changing embedding model or dimensions makes all synced data "
            f"unsearchable — you would have to delete all data and resync."
        )

    logger.info("[EmbeddingConfig] vector_db_deployment_metadata row matches code config — OK")
