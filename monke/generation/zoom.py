"""Zoom content generation adapter.

Generates realistic meeting content for testing Zoom integration using LLM.
"""

from typing import Dict

from monke.client.llm import LLMClient
from monke.generation.schemas.zoom import ZoomMeeting


async def generate_zoom_meeting(model: str, token: str) -> Dict[str, str]:
    """Generate meeting content for Zoom testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Dict with topic, agenda, and duration
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic Zoom meeting for a software development team. "
        "The meeting should be for a project discussion, standup, or planning session. "
        f"You MUST include the literal token '{token}' in the meeting topic. "
        "Make it professional and believable, like a real team meeting."
    )

    meeting = await llm.generate_structured(ZoomMeeting, instruction)
    meeting.spec.token = token

    # Ensure token is in the topic
    if token not in meeting.content.topic:
        meeting.content.topic = f"{meeting.content.topic} [{token}]"

    # Ensure token is in the agenda too
    if token not in meeting.content.agenda:
        meeting.content.agenda += f"\n\nReference: {token}"

    return {
        "topic": meeting.content.topic,
        "agenda": meeting.content.agenda,
        "duration": meeting.content.duration,
    }
