"""Vespa configuration for agentic search."""

import re

from airweave.platform.entities._base import (
    BaseEntity,
    CodeFileEntity,
    EmailEntity,
    FileEntity,
    WebEntity,
)

# =============================================================================
# Search Tuning
# =============================================================================

TARGET_HITS = 5000
HNSW_EXPLORE_ADDITIONAL = 500
DEFAULT_GLOBAL_PHASE_RERANK_COUNT = 100

# =============================================================================
# Vespa Schema Names (derived from entity class hierarchy)
# =============================================================================

# Entity classes that have corresponding Vespa schemas
# NOT included: PolymorphicEntity (dynamic), DeletionEntity (special purpose)
_VESPA_SCHEMA_ENTITY_CLASSES = [
    BaseEntity,
    FileEntity,
    CodeFileEntity,
    EmailEntity,
    WebEntity,
]


def _entity_class_to_schema_name(cls: type) -> str:
    """Convert entity class to snake_case Vespa schema name."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()


ALL_VESPA_SCHEMAS = [_entity_class_to_schema_name(cls) for cls in _VESPA_SCHEMA_ENTITY_CLASSES]
