"""PowerPoint-specific generation adapter: presentation content generator."""

from typing import List, Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.powerpoint import PowerPointPresentationContent


async def generate_powerpoint_presentation(
    model: str, token: str, presentation_type: str
) -> PowerPointPresentationContent:
    """Generate realistic PowerPoint presentation content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        presentation_type: Type of presentation (e.g., 'Business Review', 'Product Launch')

    Returns:
        PowerPointPresentationContent with title, subtitle, and slides
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic content for a PowerPoint presentation of type '{presentation_type}'. "
        f"Create a professional presentation with a title, subtitle, and 4-6 slides. "
        f"Each slide should have a title and 3-5 bullet points or content blocks. "
        f"You MUST include the literal token '{token}' naturally within one of the slide contents. "
        "The presentation should look professional and realistic (e.g., business review, product launch, quarterly update). "
        "Return JSON with: title (string), subtitle (string), "
        "slides (list of objects with title and content fields)."
    )

    pres_content = await llm.generate_structured(
        PowerPointPresentationContent, instruction
    )

    # Ensure token appears somewhere in the presentation
    token_found = False
    for slide in pres_content.slides:
        if token in slide.title or any(token in content for content in slide.content):
            token_found = True
            break

    if not token_found and pres_content.slides:
        # Add token to the last slide's content
        last_slide = pres_content.slides[-1]
        if last_slide.content:
            last_slide.content[-1] = f"{last_slide.content[-1]} (ID: {token})"
        else:
            last_slide.content.append(f"Reference ID: {token}")

    return pres_content


async def generate_presentations_content(
    model: str, tokens: List[str], base_name: str = "Test Presentation"
) -> Tuple[List[str], List[PowerPointPresentationContent]]:
    """Generate content for multiple PowerPoint presentations.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per presentation)
        base_name: Base name for the presentations

    Returns:
        Tuple of (list of filenames, list of presentation content)
    """
    presentations = []
    filenames = []

    presentation_types = [
        "Quarterly Business Review",
        "Product Launch Strategy",
        "Team Performance Update",
        "Market Analysis Report",
        "Project Roadmap",
    ]

    for i, token in enumerate(tokens):
        pres_type = (
            presentation_types[i]
            if i < len(presentation_types)
            else f"Presentation {i + 1}"
        )
        pres_content = await generate_powerpoint_presentation(model, token, pres_type)
        presentations.append(pres_content)

        # Generate filename incorporating base_name for uniqueness
        safe_base = base_name.replace(" ", "_")
        safe_title = pres_content.title.replace(" ", "_")[:40]
        filename = f"Monke_{safe_base}_{safe_title}.pptx"
        filenames.append(filename)

    return filenames, presentations
