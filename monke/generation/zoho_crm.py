"""LLM-powered content generators for Zoho CRM."""

from monke.client.llm import LLMClient
from monke.generation.schemas.zoho_crm import (
    ZohoCRMAccount,
    ZohoCRMContact,
    ZohoCRMDeal,
    ZohoCRMLead,
)


async def generate_zoho_crm_contact(model: str, token: str) -> ZohoCRMContact:
    """Generate a realistic Zoho CRM contact.

    The email MUST contain the token (e.g., token@monke.test) so we can reliably
    verify later via search.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic B2B contact for Zoho CRM. "
        f"The literal token '{token}' MUST be embedded in the email local-part "
        f"(e.g., '{token}@example.test') and may appear in description. "
        "Include plausible contact details."
    )
    contact = await llm.generate_structured(ZohoCRMContact, instruction)

    # Ensure invariants - ALWAYS force proper token separation for BM25 tokenization
    # The token must be a separate "word" to be found by keyword search
    contact.token = token
    contact.email = f"{token}.contact@example.test"

    return contact


async def generate_zoho_crm_account(model: str, token: str) -> ZohoCRMAccount:
    """Generate a realistic Zoho CRM account.

    The token MUST be embedded in account_name or description for verification.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic B2B company/account for Zoho CRM. "
        f"The literal token '{token}' MUST be embedded in the account_name "
        f"(e.g., 'Acme Corp [{token}]'). "
        "Include plausible company details like industry, website, address."
    )
    account = await llm.generate_structured(ZohoCRMAccount, instruction)

    # Ensure invariants
    account.token = token
    if token not in account.account_name:
        account.account_name = f"{account.account_name} [{token}]"

    return account


async def generate_zoho_crm_deal(model: str, token: str) -> ZohoCRMDeal:
    """Generate a realistic Zoho CRM deal.

    The token MUST be embedded in deal_name or description for verification.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic B2B sales deal for Zoho CRM. "
        f"The literal token '{token}' MUST be embedded in the deal_name "
        f"(e.g., 'Enterprise License Deal [{token}]'). "
        "Include plausible deal details like amount, stage, next step."
    )
    deal = await llm.generate_structured(ZohoCRMDeal, instruction)

    # Ensure invariants
    deal.token = token
    if token not in deal.deal_name:
        deal.deal_name = f"{deal.deal_name} [{token}]"

    return deal


async def generate_zoho_crm_lead(model: str, token: str) -> ZohoCRMLead:
    """Generate a realistic Zoho CRM lead.

    The email MUST contain the token (e.g., token@monke.test) for verification.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic B2B sales lead for Zoho CRM. "
        f"The literal token '{token}' MUST be embedded in the email local-part "
        f"(e.g., '{token}@example.test'). "
        "Include plausible lead details like company, title, industry."
    )
    lead = await llm.generate_structured(ZohoCRMLead, instruction)

    # Ensure invariants - ALWAYS force proper token separation for BM25 tokenization
    # The token must be a separate "word" to be found by keyword search
    lead.token = token
    lead.email = f"{token}.lead@example.test"

    return lead
