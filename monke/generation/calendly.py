"""Calendly-specific generation adapter: event type and scheduled event generator."""

from typing import Tuple

from monke.generation.schemas.calendly import (
    CalendlyEventType,
    CalendlyScheduledEvent,
)
from monke.client.llm import LLMClient


async def generate_calendly_event_type(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, int]:
    """Generate a Calendly event type via LLM.

    Returns (name, description, duration_minutes). The token must be embedded in the output.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated Calendly event type for testing. "
            "Create a rescheduled version of a synthetic consultation or meeting event type. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional but synthetic. "
            "Return a name like 'Updated 30 Minute Consultation' and a description with the token."
        )
    else:
        instruction = (
            "You are generating a Calendly event type for testing. "
            "Create a synthetic consultation or meeting event type. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional but synthetic. "
            "Return a name like '30 Minute Consultation' and a description with the token."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(CalendlyEventType, instruction)

    # Add token to description if not already present
    description = artifact.content.description
    if token not in description:
        description += f"\n\nEvent Type ID: {token}"

    # Embed token in name for better searchability (name field is embeddable and is_name=True)
    # Use multiple strategies to ensure token is preserved even if API modifies the name
    name = artifact.spec.name
    if token not in name:
        # Strategy 1: Prefix token (most visible for search)
        # Format: "TOKEN Event Name"
        name = f"{token} {name}"

    # CRITICAL: Double-check token is in name before returning
    if token not in name:
        # Fallback: Append token if prefix didn't work
        name = f"{name} [{token}]"

    # Final verification - if token still not in name, this is a critical error
    if token not in name:
        raise ValueError(
            f"CRITICAL: Failed to embed token {token} in event type name '{name}'. "
            f"This will cause verification to fail!"
        )

    return name, description, artifact.spec.duration_minutes


async def generate_calendly_scheduled_event_notes(
    model: str, token: str, event_type_name: str, is_update: bool = False
) -> str:
    """Generate meeting notes for a Calendly scheduled event via LLM.

    Returns meeting notes string with the token embedded.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating updated meeting notes for a Calendly scheduled event. "
            f"The event type is '{event_type_name}'. "
            "Create updated meeting notes for a synthetic consultation or meeting. "
            "Include the literal token '{token}' somewhere in the notes. "
            "Keep it professional but synthetic."
        )
    else:
        instruction = (
            "You are generating meeting notes for a Calendly scheduled event. "
            f"The event type is '{event_type_name}'. "
            "Create meeting notes for a synthetic consultation or meeting. "
            "Include the literal token '{token}' somewhere in the notes. "
            "Keep it professional but synthetic."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(CalendlyScheduledEvent, instruction)

    # Add token to notes if not already present
    notes = artifact.content.meeting_notes
    if token not in notes:
        notes += f"\n\nEvent ID: {token}"

    return notes
