"""Content generators for Pipedrive test entities."""

from monke.client.llm import LLMClient
from monke.generation.schemas.pipedrive import (
    PipedriveDeal,
    PipedriveOrganization,
    PipedrivePerson,
)


async def generate_pipedrive_person(model: str, token: str) -> PipedrivePerson:
    """Generate a realistic CRM person/contact with embedded token for verification.

    Token will be added to the organization name field for reliable vector search.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic CRM contact for a B2B sales context. "
        f"The email should be '{token}@monke-test.com'. "
        "Include realistic name, phone, and organization name. "
        "Make it look like a real business contact."
    )
    person = await llm.generate_structured(PipedrivePerson, instruction)

    # Ensure invariants
    person.token = token
    if token not in person.email:
        person.email = f"{token}@monke-test.com"

    # Embed token in org_name for vector search
    if person.org_name:
        person.org_name = f"{person.org_name} [{token}]"
    else:
        person.org_name = f"Monke Test Corp [{token}]"

    return person


async def generate_pipedrive_organization(model: str, token: str) -> PipedriveOrganization:
    """Generate a realistic organization with embedded token for verification."""
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic company/organization for a B2B CRM context. "
        "Include a company name and business address. "
        "Make it look like a real business."
    )
    org = await llm.generate_structured(PipedriveOrganization, instruction)

    # Ensure invariants - embed token in name
    org.token = token
    org.name = f"{org.name} [{token}]"

    return org


async def generate_pipedrive_deal(model: str, token: str) -> PipedriveDeal:
    """Generate a realistic deal with embedded token for verification."""
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic sales deal/opportunity for a B2B CRM context. "
        "Include a deal title and value. "
        "Make it look like a real sales opportunity."
    )
    deal = await llm.generate_structured(PipedriveDeal, instruction)

    # Ensure invariants - embed token in title
    deal.token = token
    deal.title = f"{deal.title} [{token}]"

    return deal

