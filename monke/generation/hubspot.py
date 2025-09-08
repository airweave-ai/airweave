from monke.client.llm import LLMClient
from monke.generation.schemas.hubspot import HubSpotContact


async def generate_hubspot_contact(model: str, token: str) -> HubSpotContact:
    """
    Generate a realistic CRM contact. The email MUST contain the token (e.g., token@monke.test)
    so we can reliably verify later via search.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic CRM contact for a B2B SaaS context. "
        f"The literal token '{token}' MUST be embedded in the email local-part (e.g., '{token}@example.test') "
        "and may appear in notes. Include plausible fields."
    )
    contact = await llm.generate_structured(HubSpotContact, instruction)

    # Ensure invariants
    contact.token = token
    if token not in contact.email:
        # Force tokenized email (stable id)
        local = f"{token}.contact"
        contact.email = f"{local}@example.test"

    return contact
