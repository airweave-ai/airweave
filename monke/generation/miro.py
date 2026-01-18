"""Miro content generation adapter.

Generates realistic content for testing Miro integration using LLM.
"""

import io
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from monke.generation.schemas.miro import (
    MiroStickyNote,
    MiroCard,
    MiroText,
    MiroFrame,
    MiroTag,
    MiroDocument,
    MiroImage,
)
from monke.client.llm import LLMClient


async def generate_sticky_note(model: str, token: str) -> Tuple[str, str]:
    """Generate sticky note content for Miro testing.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (content, color)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic sticky note for a Miro board. "
        "Context: This could be from a sprint retrospective (what went well/needs improvement), "
        "a user research synthesis session (insight or user quote), "
        "a product brainstorming session (feature idea or problem statement), "
        "or a design thinking workshop (user pain point or opportunity). "
        f"You MUST include the literal token '{token}' in the content. "
        "Keep it concise (1-3 sentences) like a real workshop participant would write."
    )

    sticky = await llm.generate_structured(MiroStickyNote, instruction)
    sticky.spec.token = token

    # Ensure token is in content
    content = sticky.content.content
    if token not in content:
        content = f"{content}\n\n[Token: {token}]"

    return content, sticky.spec.color


async def generate_card(model: str, token: str) -> Tuple[str, str, str]:
    """Generate card content for Miro testing.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (title, description, due_date or None)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic card for a Miro board. "
        "This could be: a user story (As a [user], I want [goal] so that [benefit]), "
        "a sprint task (specific deliverable with acceptance criteria), "
        "a research synthesis card (key finding with supporting evidence), "
        "or a feature request (problem + proposed solution). "
        f"You MUST include the literal token '{token}' in both the title and description. "
        "Make it feel like a real card from an agile team's workflow."
    )

    card = await llm.generate_structured(MiroCard, instruction)
    card.spec.token = token

    # Ensure token is in title and description
    title = card.spec.title
    if token not in title:
        title = f"[{token}] {title}"

    description = card.content.description
    if token not in description:
        description = f"{description}\n\n[Verification Token: {token}]"

    return title, description, card.content.due_date


async def generate_text(model: str, token: str) -> str:
    """Generate text content for Miro testing.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        The text content
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate realistic text content for a Miro board. "
        "This could be: a workshop section header (e.g., 'User Pain Points', 'Sprint Goals'), "
        "a process step description, an instruction for participants, "
        "a strategic insight or key takeaway, or annotation explaining a diagram. "
        f"You MUST include the literal token '{token}' in the text. "
        "Make it 2-4 sentences, like real content from a facilitated workshop."
    )

    text = await llm.generate_structured(MiroText, instruction)
    text.spec.token = token

    content = text.content.content
    if token not in content:
        content = f"{content}\n\n[Token: {token}]"

    return content


async def generate_frame(model: str, token: str) -> Tuple[str, str]:
    """Generate frame content for Miro testing.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the title for verification

    Returns:
        Tuple of (title, format)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic frame title for a Miro board. "
        "Frames organize related content. Examples: 'Sprint Backlog', 'User Journey Map', "
        "'Retrospective - What Went Well', 'Research Themes', 'Ideation Space', "
        "'Personas', 'Empathy Map', 'Roadmap Q1', 'Discovery Findings'. "
        f"You MUST include the literal token '{token}' in the title. "
        "The title should clearly describe what content belongs in this section."
    )

    frame = await llm.generate_structured(MiroFrame, instruction)
    frame.spec.token = token

    title = frame.spec.title
    if token not in title:
        title = f"{title} [{token}]"

    return title, frame.content.format


async def generate_tag(model: str, token: str) -> str:
    """Generate tag content for Miro testing.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the title for verification

    Returns:
        The tag title
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic tag name for a Miro board. "
        "Tags categorize items. Examples: 'Must Have', 'Nice to Have', 'Blocked', "
        "'In Review', 'Research', 'Design', 'Engineering', 'Quick Win', "
        "'High Priority', 'User Feedback', 'Technical Debt'. "
        f"You MUST include the literal token '{token}' in the tag name. "
        "Keep it short (2-4 words including the token)."
    )

    tag = await llm.generate_structured(MiroTag, instruction)
    tag.spec.token = token

    title = tag.spec.title
    if token not in title:
        title = f"{title}-{token}"

    return title


async def generate_document_content(model: str, token: str) -> Tuple[str, str]:
    """Generate document content for Miro testing as CSV format.

    Miro supports: ods, csv, docx, pptx, pdf, xls, odt, rtf, odp, xlsx, ppt, doc, psd
    We use CSV as it's the simplest text-based format that Miro accepts.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (title/filename, csv_content)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate content for a document uploaded to a Miro board. "
        "Context: This could be workshop data (attendees, feedback scores), "
        "research synthesis (key findings, participant quotes), "
        "sprint metrics (velocity, burndown data), or process documentation. "
        f"You MUST include the literal token '{token}' in the content. "
        "Keep it concise and data-oriented."
    )

    doc = await llm.generate_structured(MiroDocument, instruction)
    doc.spec.token = token

    # Build content
    content = doc.content.text_content
    if token not in content:
        content = f"{content}\n\nVerification Token: {token}"

    # Escape quotes for CSV
    escaped_content = content.replace('"', '""')
    escaped_title = doc.spec.title.replace('"', '""')

    # Create CSV with token embedded in searchable content
    csv_content = "Title,Content,Token\n"
    csv_content += f'"{escaped_title}","{escaped_content}","{token}"\n'

    # Include token in filename for title field matching
    filename = f"doc-{token}.csv"

    return filename, csv_content


async def generate_image_metadata(model: str, token: str) -> Tuple[str, str]:
    """Generate image metadata for Miro testing.

    Creates a PNG image with text that OCR can read.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the image for verification

    Returns:
        Tuple of (filename with token, alt_text with token)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate metadata for a diagram image on a Miro board. "
        "This could be: a user flow diagram, customer journey map, "
        "system architecture sketch, process flowchart, or wireframe mockup. "
        f"You MUST include the literal token '{token}' in the alt text. "
        "The alt text should clearly describe what the visual represents."
    )

    image = await llm.generate_structured(MiroImage, instruction)
    image.spec.token = token

    # Include token in filename so it appears in the title field (which is embeddable)
    filename = f"diagram-{token}.png"

    alt_text = image.content.alt_text
    if token not in alt_text:
        alt_text = f"{alt_text} [Token: {token}]"

    return filename, alt_text


def generate_simple_png_diagram(token: str, title: str = "Test Diagram") -> bytes:
    """Generate a simple PNG diagram with embedded verification token.

    Creates an image with clear text that OCR can read and extract the token from.

    Args:
        token: The verification token to embed in the image
        title: The diagram title

    Returns:
        PNG image content as bytes
    """
    # Create image with white background
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    # Try to use a basic font, fall back to default if not available
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except (OSError, IOError):
        # Fallback to default font
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw title at top
    draw.text((width // 2, 30), title, fill="black", font=font_large, anchor="mm")

    # Draw a simple flowchart
    # Box 1 - Start
    draw.rectangle([200, 70, 400, 120], fill="#4285f4", outline="#333")
    draw.text((300, 95), "Start", fill="white", font=font_medium, anchor="mm")

    # Arrow 1
    draw.line([(300, 120), (300, 150)], fill="#333", width=2)
    draw.polygon([(295, 145), (305, 145), (300, 155)], fill="#333")

    # Box 2 - Process
    draw.rectangle([200, 160, 400, 210], fill="#34a853", outline="#333")
    draw.text((300, 185), "Process", fill="white", font=font_medium, anchor="mm")

    # Arrow 2
    draw.line([(300, 210), (300, 240)], fill="#333", width=2)
    draw.polygon([(295, 235), (305, 235), (300, 245)], fill="#333")

    # Box 3 - End
    draw.rectangle([200, 250, 400, 300], fill="#ea4335", outline="#333")
    draw.text((300, 275), "End", fill="white", font=font_medium, anchor="mm")

    # Draw verification token prominently at bottom (OCR will read this)
    draw.text((width // 2, 350), f"Verification Token: {token}", fill="#333", font=font_small, anchor="mm")

    # Also draw token in a box to make it more visible
    token_text = f"TOKEN: {token}"
    draw.rectangle([150, 365, 450, 390], outline="#666", width=1)
    draw.text((width // 2, 377), token_text, fill="#000", font=font_small, anchor="mm")

    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()
