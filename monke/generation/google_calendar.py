"""Google Calendar-specific generation adapter: event generator."""

from typing import Tuple

from monke.generation.schemas.google_calendar import GoogleCalendarArtifact
from monke.client.llm import LLMClient


async def generate_google_calendar_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, float]:
    """Generate a Google Calendar event via LLM.

    Returns (title, description, duration_hours). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model if model else None)

    if is_update:
        instruction = (
            "You are generating an updated calendar event for a test Google Calendar. "
            "Create a rescheduled version of a synthetic tech conference event. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional but synthetic."
        )
    else:
        instruction = (
            "You are generating a calendar event for a test Google Calendar. "
            "Create a synthetic tech conference or meeting event. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional but synthetic."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(GoogleCalendarArtifact, instruction)

    # Add token to description if not already present
    description = artifact.description
    if token not in description:
        description += f"\n\nEvent ID: {token}"

    return artifact.title, description, artifact.duration_hours
