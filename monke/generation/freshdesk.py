"""Freshdesk content generation adapter.

Generates realistic ticket content for testing Freshdesk integration using LLM.
"""

from typing import Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.freshdesk import FreshdeskTicket


def render_description(ticket: FreshdeskTicket) -> str:
    """Render the ticket content as description for Freshdesk (plain text or HTML)."""
    content = ticket.content
    spec = ticket.spec

    parts = [
        f"**Verification Token**: {spec.token}",
        f"\n## Issue Description\n\n{content.description}",
        f"\n## Customer Information\n\n{content.customer_info}",
        "\n## Steps to Reproduce:",
    ]
    for i, step in enumerate(content.steps_to_reproduce, 1):
        parts.append(f"{i}. {step}")
    parts.extend([
        f"\n## Expected Behavior\n\n{content.expected_behavior}",
        f"\n## Actual Behavior\n\n{content.actual_behavior}",
        f"\n## Additional Information\n\n{content.additional_info}",
    ])
    return "\n".join(parts)


async def generate_freshdesk_ticket(model: str, token: str) -> Tuple[str, str]:
    """Generate ticket content for Freshdesk testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (subject, description)
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic Freshdesk support ticket for a software application. "
        "The ticket should be from a customer reporting a technical issue or asking for help. "
        f"You MUST include the literal token '{token}' in the ticket description and at the beginning of the subject. "
        "Create a believable customer scenario with clear steps to reproduce, expected vs actual behavior. "
        "The ticket should feel like it's from a real customer experiencing a genuine issue. "
        "Include customer context like their environment, browser, etc."
    )
    ticket = await llm.generate_structured(FreshdeskTicket, instruction)
    ticket.spec.token = token
    if token not in ticket.content.description:
        ticket.content.description += f"\n\n**Debug Token**: {token}"
    description = render_description(ticket)
    return ticket.spec.subject, description
