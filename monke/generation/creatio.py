"""Creatio-specific generation adapter.

Generates realistic test content for all Creatio entity types using LLM.
"""

from typing import Any, Dict

from monke.generation.schemas.creatio import (
    CreatioAccountArtifact,
    CreatioContactArtifact,
    CreatioCampaignArtifact,
    CreatioOpportunityArtifact,
    CreatioOrderArtifact,
)
from monke.client.llm import LLMClient


async def generate_creatio_account(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Creatio account via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with Name, Phone, Web, Address
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated CRM account for testing. "
            "Create an updated company name and details. "
            f"You MUST include the literal token '{token}' in the name field. "
            "Keep it realistic and professional."
        )
    else:
        instruction = (
            "You are generating a CRM account/company for testing. "
            "Create a realistic company with name, phone, website, and address. "
            f"You MUST include the literal token '{token}' in the name field. "
            "Think of real-world companies. Keep it realistic and professional."
        )

    artifact = await llm.generate_structured(CreatioAccountArtifact, instruction)

    name = artifact.name
    if token not in name:
        name = f"{name} [{token}]"

    return {
        "Name": name,
        "Phone": artifact.phone,
        "Web": artifact.web,
        "Address": artifact.address,
    }


async def generate_creatio_contact(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Creatio contact via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with Name, Email, Phone, JobTitle
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated CRM contact for testing. "
            "Create an updated job title for a contact. "
            f"You MUST include the literal token '{token}' in the job_title field. "
            "Keep it realistic."
        )
    else:
        instruction = (
            "You are generating a CRM contact for testing. "
            "Create a realistic person with full name, email, phone, and job title. "
            f"You MUST include the literal token '{token}' in the job_title field. "
            "Keep it professional and realistic."
        )

    artifact = await llm.generate_structured(CreatioContactArtifact, instruction)

    job_title = artifact.job_title
    if token not in job_title:
        job_title = f"{job_title} [{token}]"

    return {
        "Name": artifact.name,
        "Email": artifact.email,
        "Phone": artifact.phone,
        "JobTitle": job_title,
    }


async def generate_creatio_campaign(
    model: str, token: str
) -> Dict[str, Any]:
    """Generate a Creatio campaign via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification

    Returns:
        Dict with Name, TargetDescription, StartDate, EndDate
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "You are generating a marketing campaign for CRM testing. "
        "Create a realistic campaign with a name and target description. "
        f"You MUST include the literal token '{token}' in the name field. "
        "Keep it professional and realistic."
    )

    artifact = await llm.generate_structured(CreatioCampaignArtifact, instruction)

    name = artifact.name
    if token not in name:
        name = f"{name} [{token}]"

    return {
        "Name": name,
        "TargetDescription": artifact.target_description,
        "StartDate": "2025-01-01T00:00:00Z",
        "EndDate": "2025-12-31T23:59:59Z",
    }


async def generate_creatio_opportunity(
    model: str, token: str
) -> Dict[str, Any]:
    """Generate a Creatio opportunity via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification

    Returns:
        Dict with Title, Description, Budget, Amount
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "You are generating a sales opportunity for CRM testing. "
        "Create a realistic opportunity with title, description, budget, and amount. "
        f"You MUST include the literal token '{token}' in the title field. "
        "Keep it professional and realistic."
    )

    artifact = await llm.generate_structured(CreatioOpportunityArtifact, instruction)

    title = artifact.title
    if token not in title:
        title = f"{title} [{token}]"

    return {
        "Title": title,
        "Description": artifact.description,
        "Budget": artifact.budget,
        "Amount": artifact.amount,
    }


async def generate_creatio_order(
    model: str, token: str
) -> Dict[str, Any]:
    """Generate a Creatio order via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification

    Returns:
        Dict with Notes, Comment, ReceiverName, DeliveryAddress
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "You are generating an order for CRM testing. "
        "Create realistic order notes, comment, receiver name, and delivery address. "
        f"You MUST include the literal token '{token}' in the notes field. "
        "Keep it professional and realistic."
    )

    artifact = await llm.generate_structured(CreatioOrderArtifact, instruction)

    notes = artifact.notes
    if token not in notes:
        notes = f"{notes} (Order Token: {token})"

    return {
        "Notes": notes,
        "Comment": artifact.comment,
        "ReceiverName": artifact.receiver_name,
        "DeliveryAddress": artifact.delivery_address,
    }
