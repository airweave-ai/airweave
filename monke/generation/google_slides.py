"""Google Slides-specific generation adapter: presentation generator."""

from typing import List

from monke.client.llm import LLMClient
from monke.generation.schemas.google_slides import GoogleSlidesPresentation


async def generate_google_slides_presentation(
    model: str, token: str, presentation_title: str
) -> GoogleSlidesPresentation:
    """Generate realistic Google Slides presentation content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        presentation_title: Title for the presentation

    Returns:
        GoogleSlidesPresentation with title and content
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic content for a Google Slides presentation titled '{presentation_title}'. "
        f"Create 3-5 slides worth of content with bullet points, headings, and key information. "
        f"You MUST include the literal token '{token}' naturally within the content. "
        "The content should look professional and realistic for a business presentation. "
        "Format as plain text with slide separators (use '---' between slides). "
        "Return JSON with: title (string), content (string with plain text, use \\n for newlines)."
    )

    presentation = await llm.generate_structured(GoogleSlidesPresentation, instruction)
    presentation.title = presentation_title

    # Ensure token appears in the content
    if token not in presentation.content:
        # Add token to the end if not present
        presentation.content = f"{presentation.content}\n\nVerification: {token}"

    return presentation


async def generate_presentations(
    model: str, tokens: List[str], base_name: str = "Test Presentation"
) -> List[GoogleSlidesPresentation]:
    """Generate multiple Google Slides presentations.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per presentation)
        base_name: Base name for the presentations

    Returns:
        List of GoogleSlidesPresentation objects
    """
    presentations = []

    presentation_types = [
        "Quarterly Business Review",
        "Product Launch Strategy",
        "Team Meeting Agenda",
        "Project Status Update",
        "Sales Pitch Deck",
    ]

    for i, token in enumerate(tokens):
        pres_type = (
            presentation_types[i]
            if i < len(presentation_types)
            else f"Presentation {i + 1}"
        )
        pres_title = f"{base_name} - {pres_type}"
        presentation = await generate_google_slides_presentation(
            model, token, pres_title
        )
        presentations.append(presentation)

    return presentations
