"""Cal.com content generation adapter.

Generates realistic event type and booking content for testing Cal.com integration using LLM.
"""

from typing import List, Optional, Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.cal_com import CalComBooking, CalComEventType


async def generate_cal_com_event_type(
    model: str, token: str
) -> Tuple[str, str, int, str, Optional[str]]:
    """Generate event type content for Cal.com testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (title, description, duration_minutes, location_type, location_details)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic Cal.com event type for a professional meeting or consultation. "
        "The event type should be believable, like something a consultant, coach, or professional would offer. "
        f"You MUST include the literal token '{token}' in the event type description. "
        "Create a meaningful title and description. "
        "The event should have a clear purpose and value proposition. "
        "Suggest a reasonable duration (15, 30, 45, or 60 minutes). "
        "Choose an appropriate location type from the valid options: 'integration' (for video calls - recommended), 'link' (for custom video links), 'address' (for in-person), or 'phone' (for phone calls)."
    )

    # Generate structured event type data
    event_type = await llm.generate_structured(CalComEventType, instruction)

    # Ensure token is in the event type
    event_type.spec.token = token

    # Also ensure the token appears in the description if it's not already there
    if token not in event_type.content.description:
        event_type.content.description += f"\n\n**Verification Token**: {token}"

    return (
        event_type.spec.title,
        event_type.content.description,
        event_type.spec.duration_minutes,
        event_type.content.location_type,
        event_type.content.location_details,
    )


async def generate_cal_com_booking(
    model: str, token: str, attendee_name: str, attendee_email: str
) -> Tuple[str, List[str]]:
    """Generate booking content for Cal.com testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification
        attendee_name: Name of the attendee
        attendee_email: Email of the attendee

    Returns:
        Tuple of (notes, questions)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic booking notes for a Cal.com meeting. "
        f"The attendee is {attendee_name} ({attendee_email}). "
        f"You MUST include the literal token '{token}' in the booking notes. "
        "Create meaningful notes that explain what the attendee wants to discuss or achieve. "
        "Include 1-2 relevant questions they might have."
    )

    # Generate structured booking data
    booking = await llm.generate_structured(CalComBooking, instruction)

    # Ensure token is in the booking
    booking.spec.token = token
    booking.spec.attendee_name = attendee_name
    booking.spec.attendee_email = attendee_email

    # Also ensure the token appears in the notes if it's not already there
    if token not in booking.content.notes:
        booking.content.notes += f"\n\n**Verification Token**: {token}"

    return booking.content.notes, booking.content.questions
