"""Pipeline components for entity processing.

This module contains the event-driven entity pipeline architecture:

Core Components:
- EntityTracker: Central entity state tracking (dedup + counts + pubsub)
- ProcessingRequirement: What processing a destination expects from the pipeline

Processing Helpers:
- HashComputer: Computes content hashes
- TextualRepresentationBuilder: Builds textual representations
- CleanupService: Handles orphan and temp file cleanup
"""

# Core components
# Processing helpers
from airweave.platform.sync.pipeline.cleanup_service import cleanup_service
from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
from airweave.platform.sync.pipeline.enums import ProcessingRequirement
from airweave.platform.sync.pipeline.hash_computer import hash_computer
from airweave.platform.sync.pipeline.text_builder import (
    TextualRepresentationBuilder,
    text_builder,
)

__all__ = [
    # Core components
    "EntityTracker",
    "ProcessingRequirement",
    # Processing helpers
    "cleanup_service",
    "hash_computer",
    "TextualRepresentationBuilder",
    "text_builder",
]
