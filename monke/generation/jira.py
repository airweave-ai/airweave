"""Jira-specific generation adapter: issue generator."""

from typing import Tuple

from monke.generation.schemas.jira import JiraArtifact
from monke.client.llm import LLMClient


async def generate_jira_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, str]:
    """Generate a Jira issue via LLM.

    Returns (summary, description, issue_type). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated Jira issue for testing. "
            "Create an update to a synthetic software development task. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional and realistic."
        )
    else:
        instruction = (
            "You are generating a Jira issue for testing. "
            "Create a synthetic software development task or bug report. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional and realistic."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(JiraArtifact, instruction)

    # Add token to description if not already present
    description = artifact.description
    if token not in description:
        description += f"\n\nReference: {token}"

    return artifact.summary, description, artifact.issue_type
