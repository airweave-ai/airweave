"""Gmail-specific generation adapter: email generator using JSON mode."""

from typing import Tuple

from monke.generation.schemas.gmail import GmailArtifact
from monke.client.llm import LLMClient


async def generate_gmail_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str]:
    """
    Returns (subject, body). The literal token must appear in the body.
    Uses JSON mode (response_format: json_object) under the hood.
    """
    llm = LLMClient(model_override=model if model else None)

    if is_update:
        instruction = (
            "Create a concise follow-up email about a (synthetic) tech product update. "
            f"Include the EXACT literal token '{token}' somewhere in the body text. "
            "Return JSON with fields: subject (string), body (string)."
        )
    else:
        instruction = (
            "Create a concise (synthetic) email announcing a new tech product. "
            f"Include the EXACT literal token '{token}' somewhere in the body text. "
            "Return JSON with fields: subject (string), body (string)."
        )

    artifact = await llm.generate_structured(GmailArtifact, instruction)

    body = artifact.body
    if token not in body:
        body += f"\n\nReference: {token}"

    return artifact.subject, body
