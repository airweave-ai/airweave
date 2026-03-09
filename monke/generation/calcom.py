"""Cal.com content generation adapter.

Generates realistic booking content with embedded verification tokens for Monke.
"""

from monke.client.llm import LLMClient
from monke.generation.schemas.calcom import CalBookingArtifact


async def generate_cal_booking(model: str, token: str) -> dict:
    """Generate Cal.com booking content with an embedded verification token.

    Args:
        model: LLM model name to use.
        token: Unique verification token to embed in the description.

    Returns:
        Dict with `title`, `description`, and attendee metadata.
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a synthetic but realistic meeting for a scheduling platform like Cal.com. "
        f"You MUST include the literal token '{token}' in the summary or description so "
        "it can be used for search verification. The meeting should be technical, "
        "for example a product integration review or API design session."
    )

    # Ask the model to fill out the CalBookingArtifact schema directly.
    # It must:
    # - Set spec.token to the exact token string provided above
    # - Provide a technical meeting title and attendee metadata
    # - Populate content.summary/agenda/expected_outcomes realistically
    artifact = await llm.generate_structured(CalBookingArtifact, instruction)

    # Ensure token appears in summary/description
    summary = artifact.content.summary
    if token not in summary:
        summary = f"{summary}\n\nVerification Token: {token}"

    description_lines = [
        summary,
        "",
        "Agenda:",
        *(f"- {item}" for item in artifact.content.agenda),
        "",
        "Expected outcomes:",
        *(f"- {item}" for item in artifact.content.expected_outcomes),
    ]
    description = "\n".join(description_lines)

    return {
        "title": artifact.spec.title or "Cal.com integration review",
        "description": description,
        "attendee_name": artifact.spec.attendee_name,
        "attendee_email": artifact.spec.attendee_email,
        "attendee_time_zone": artifact.spec.attendee_time_zone,
        "token": token,
    }
