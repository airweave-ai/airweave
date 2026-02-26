"""Slite content generation adapter.

Generates realistic doc/note content for testing Slite integration using LLM.
"""

from typing import Dict

from monke.client.llm import LLMClient
from monke.generation.schemas.slite import SliteNote


async def generate_slite_note(model: str, token: str) -> Dict:
    """Generate note content for Slite testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Dict with title and markdown ready for Slite API (POST /v1/notes)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a short internal knowledge-base document (e.g., process, FAQ, or how-to). "
        "Use markdown: headings, bullet points, maybe a short paragraph. "
        f"You MUST include the literal token '{token}' in the document body. "
        "Create a clear title and 2–4 paragraphs or bullet sections."
    )

    note = await llm.generate_structured(SliteNote, instruction)

    note.spec.token = token
    if token not in note.content.markdown:
        note.content.markdown += f"\n\nVerification token: {token}"

    return {
        "title": f"{note.spec.title} [{token}]",
        "markdown": note.content.markdown,
        "token": token,
    }
