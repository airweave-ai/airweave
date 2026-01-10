"""Pipeline components for entity and ACL processing.

This module contains the event-driven pipeline architecture:

Core Components:
- EntityTracker: Central entity state tracking (dedup + counts + pubsub)
- ACLMembershipTracker: ACL membership tracking (dedup + orphan detection)
- ProcessingRequirement: What processing a destination expects from the pipeline

Processing Helpers:
- HashComputer: Computes content hashes
- TextualRepresentationBuilder: Builds textual representations
- CleanupService: Handles orphan and temp file cleanup
"""

# Core components
# Processing helpers
from airweave.platform.sync.pipeline.acl_membership_tracker import (
    ACLMembershipTracker,
    ACLSyncStats,
)
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
    "ACLMembershipTracker",
    "ACLSyncStats",
    "ProcessingRequirement",
    # Processing helpers
    "cleanup_service",
    "hash_computer",
    "TextualRepresentationBuilder",
    "text_builder",
]
