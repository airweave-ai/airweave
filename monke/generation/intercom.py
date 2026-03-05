"""Intercom content generation adapter.

Generates realistic ticket content for testing Intercom integration using LLM.
"""

from typing import Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.intercom import IntercomTicket


def render_ticket_description(ticket: IntercomTicket) -> str:
    """Render the ticket content as default_description for Intercom."""
    content = ticket.content
    spec = ticket.spec
    parts = [
        f"Verification Token: {spec.token}",
        f"\n## Issue Description\n\n{content.description}",
        f"\n## Customer Information\n\n{content.customer_info}",
        "\n## Steps to Reproduce:",
    ]
    for i, step in enumerate(content.steps_to_reproduce, 1):
        parts.append(f"{i}. {step}")
    parts.extend([
        f"\n## Expected Behavior\n\n{content.expected_behavior}",
        f"\n## Actual Behavior\n\n{content.actual_behavior}",
    ])
    return "\n".join(parts)


async def generate_intercom_ticket(model: str, token: str) -> Tuple[str, str]:
    """Generate ticket content for Intercom testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (default_title, default_description)
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic Intercom support ticket for a software application. "
        "The ticket should be from a customer reporting a technical issue or asking for help. "
        f"You MUST include the literal token '{token}' in the ticket description and in the title. "
        "Create a believable customer scenario with clear steps to reproduce, expected vs actual behavior. "
        "The ticket should feel like it's from a real customer experiencing a genuine issue."
    )
    ticket = await llm.generate_structured(IntercomTicket, instruction)
    ticket.spec.token = token
    if token not in ticket.content.description:
        ticket.content.description += f"\n\nDebug Token: {token}"
    description = render_ticket_description(ticket)
    title = ticket.spec.default_title
    if token not in title:
        title = f"{title} [{token}]"
    return title, description
