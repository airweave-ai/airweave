"""Coda content generation for Monke tests."""

from typing import Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.coda import CodaDocSpec


async def generate_coda_doc(model: str, token: str, update: bool = False) -> Tuple[str, str]:
    """Generate doc title and intro text for Coda testing.

    Returns:
        (title, intro_html) - title and a short HTML snippet for initial page content.
    """
    llm = LLMClient(model_override=model)
    update_ctx = " (Updated)" if update else ""
    instruction = (
        f"Generate a minimal Coda doc spec for testing{update_ctx}. "
        f"You MUST include the literal token '{token}' in both the title and the intro. "
        "Title: one short phrase (e.g. 'Q4 Goals'). "
        "Intro: one sentence in plain language (will be wrapped in <p>). Keep it brief."
    )
    doc = await llm.generate_structured(CodaDocSpec, instruction)
    doc.token = token
    if token not in doc.title:
        doc.title = f"{token} {doc.title}"
    if token not in doc.intro:
        doc.intro = f"{doc.intro} Monke verification token {token}."
    intro_html = f"<p>{doc.intro}</p>"
    return doc.title, intro_html
