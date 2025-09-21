"""Bitbucket-specific generation adapter: code file generator."""

from typing import Tuple

from monke.generation.schemas.bitbucket import BitbucketArtifact
from monke.client.llm import LLMClient


async def generate_bitbucket_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, str]:
    """Generate a Bitbucket code file via LLM.

    Returns (filename, content, file_type). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model if model else None)

    if is_update:
        instruction = (
            "You are generating an updated code file for a test Bitbucket repository. "
            "Create an update to a synthetic Python module with functions and classes. "
            "Include the literal token '{token}' in a comment or docstring. "
            "Keep it clean and well-documented."
        )
    else:
        instruction = (
            "You are generating a code file for a test Bitbucket repository. "
            "Create a synthetic Python module with functions and classes. "
            "Include the literal token '{token}' in a comment or docstring. "
            "Keep it clean and well-documented."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(BitbucketArtifact, instruction)

    # Add token to content if not already present
    content = artifact.content
    if token not in content:
        content = f"# Token: {token}\n\n{content}"

    return artifact.filename, content, artifact.file_type
