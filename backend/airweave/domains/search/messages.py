"""Shared prompt loading for the search domain.

Used by both classic and agentic tiers to build system prompts
from the shared airweave_overview.md + tier-specific task prompts.
"""

from __future__ import annotations

import functools
from pathlib import Path

from airweave.domains.search.types.metadata import CollectionMetadata


@functools.cache
def _load_overview() -> str:
    """Load and cache the shared airweave overview prompt."""
    return (Path(__file__).parent / "context" / "airweave_overview.md").read_text()


def build_system_prompt(
    overview: str,
    task: str,
    metadata: CollectionMetadata,
    **replacements: object,
) -> str:
    """Assemble system prompt from overview + task + metadata.

    Applies any template replacements (e.g., {max_iterations}) to the task text.
    """
    for key, value in replacements.items():
        task = task.replace(f"{{{key}}}", str(value))
    return (
        f"# Airweave Overview\n\n{overview}\n\n"
        f"---\n\n{task}\n\n"
        f"---\n\n## Collection Metadata\n\n{metadata.to_md()}"
    )
