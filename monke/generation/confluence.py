"""Confluence-specific generation adapter: page generator."""

from typing import Tuple

from monke.generation.schemas.confluence import ConfluenceArtifact
from monke.client.llm import LLMClient


async def generate_confluence_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str]:
    """Generate a Confluence page via LLM.

    Returns (title, content). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model if model else None)

    if is_update:
        instruction = (
            "You are generating an updated Confluence page for testing. "
            "Create an update to a synthetic technical documentation page. "
            "Include the literal token '{token}' somewhere in the content. "
            "Keep it professional and informative."
        )
    else:
        instruction = (
            "You are generating a Confluence page for testing. "
            "Create a synthetic technical documentation or knowledge base article. "
            "Include the literal token '{token}' somewhere in the content. "
            "Keep it professional and informative."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(ConfluenceArtifact, instruction)

    # Add token to content if not already present
    content = artifact.content
    if token not in content:
        content += f"\n\nDocument ID: {token}"

    return artifact.title, content
