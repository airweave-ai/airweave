"""ServiceNow content generation adapter.

Generates realistic incident short_description and description for Monke E2E tests.
"""

from typing import Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.servicenow import ServiceNowIncident


async def generate_servicenow_incident(
    model: str, token: str
) -> Tuple[str, str]:
    """Generate incident short_description and description with embedded token.

    Args:
        model: LLM model to use
        token: Unique token to embed for verification

    Returns:
        (short_description, description)
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic IT support incident for a service desk. "
        "Provide a short one-line summary and a detailed description. "
        f"You MUST include the literal token '{token}' in the description. "
        "Make it sound like a real user-reported issue (e.g. login, email, access)."
    )
    incident = await llm.generate_structured(ServiceNowIncident, instruction)
    incident.spec.token = token
    if token not in incident.content.description:
        incident.content.description += f"\n\nVerification token: {token}"
    desc = (
        f"{incident.content.description}\n\n"
        f"Steps to reproduce:\n{incident.content.steps_to_reproduce}"
    )
    return incident.spec.short_description, desc
