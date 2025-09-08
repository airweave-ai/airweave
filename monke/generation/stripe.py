"""Stripe-specific generation adapter: customer generator."""

from typing import Tuple

from monke.generation.schemas.stripe import StripeArtifact
from monke.client.llm import LLMClient


async def generate_stripe_artifact(
    model: str, token: str, is_update: bool = False
) -> Tuple[str, str, str]:
    """Generate a Stripe customer via LLM.

    Returns (name, email, description). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated Stripe customer for testing. "
            "Create an update to a synthetic business customer profile. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional and realistic. Note: email cannot be changed."
        )
    else:
        instruction = (
            "You are generating a Stripe customer for testing. "
            "Create a synthetic business customer profile with name, email, and description. "
            "Include the literal token '{token}' somewhere in the description. "
            "Keep it professional and realistic."
        )

    instruction = instruction.format(token=token)
    artifact = await llm.generate_structured(StripeArtifact, instruction)

    # Add token to description if not already present
    description = artifact.description
    if token not in description:
        description += f" (Customer ID: {token})"

    return artifact.name, artifact.email, description
