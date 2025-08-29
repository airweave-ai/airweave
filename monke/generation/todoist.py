"""Todoist-specific generation adapter: task generator."""

from typing import Tuple

from monke.generation.schemas.todoist import TodoistArtifact
from monke.client.llm import LLMClient


async def generate_todoist_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, int]:
    """Generate a Todoist task via LLM.

    Returns (content, description, priority). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated Todoist task for testing. "
            "Create an update to a synthetic productivity task. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it actionable and realistic."
        )
    else:
        instruction = (
            "You are generating a Todoist task for testing. "
            "Create a synthetic productivity or project management task. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it actionable and realistic."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(TodoistArtifact, instruction)

    # Add token to description if not already present
    description = artifact.description
    if token not in description:
        description += f"\n\nTask ID: {token}"

    return artifact.content, description, artifact.priority
