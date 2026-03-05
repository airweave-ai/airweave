"""Apollo content generation adapter.

Generates realistic CRM content for testing Apollo integration using LLM.
"""

from typing import Dict

from monke.client.llm import LLMClient
from monke.generation.schemas.apollo import ApolloAccount, ApolloContact


async def generate_apollo_account(model: str, token: str) -> Dict:
    """Generate account (company) content for Apollo testing.

    Args:
        model: LLM model to use
        token: Unique token to embed for verification

    Returns:
        Dict with name, domain for Apollo POST /accounts
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic B2B company for a sales CRM. "
        f"You MUST include the literal token '{token}' in the company name. "
        "Use a believable company name and domain (e.g. acme.io, not www.acme.io)."
    )

    account = await llm.generate_structured(ApolloAccount, instruction)
    account.spec.token = token

    name = account.spec.name
    if token not in name:
        name = f"{name} [{token}]"

    return {
        "name": name,
        "domain": account.spec.domain,
        "token": token,
    }


async def generate_apollo_contact(model: str, token: str) -> Dict:
    """Generate contact (person) content for Apollo testing.

    Args:
        model: LLM model to use
        token: Unique token to embed for verification

    Returns:
        Dict with first_name, last_name, email, title, organization_name for Apollo POST /contacts
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic professional contact for a sales CRM. "
        f"You MUST include the literal token '{token}' in the job title. "
        "Use a believable first name, last name, email, and company."
    )

    contact = await llm.generate_structured(ApolloContact, instruction)
    contact.spec.token = token

    title = contact.spec.title
    if token not in title:
        title = f"{title} [{token}]"

    return {
        "first_name": contact.spec.first_name,
        "last_name": contact.spec.last_name,
        "email": contact.spec.email,
        "title": title,
        "organization_name": contact.spec.organization_name,
        "token": token,
    }
