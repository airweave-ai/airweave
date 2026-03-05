"""Shopify-specific generation adapter.

Generates realistic test content for all Shopify entity types using LLM.
"""

from typing import Dict, Any

from monke.generation.schemas.shopify import (
    ShopifyProductArtifact,
    ShopifyCustomerArtifact,
    ShopifyCollectionArtifact,
    ShopifyOrderArtifact,
    ShopifyDiscountArtifact,
    ShopifyGiftCardArtifact,
)
from monke.client.llm import LLMClient


async def generate_shopify_product(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify product via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with title, body_html, vendor, product_type
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated e-commerce product for testing. "
            "Create an updated product description for an online store. "
            f"You MUST include the literal token '{token}' in the body_html description. "
            "Keep it realistic and professional."
        )
    else:
        instruction = (
            "You are generating an e-commerce product for testing. "
            "Create a realistic product with title, description, vendor, and type. "
            f"You MUST include the literal token '{token}' in the body_html description. "
            "Think of products like clothing, electronics, home goods, etc. "
            "Keep it realistic and professional."
        )

    artifact = await llm.generate_structured(ShopifyProductArtifact, instruction)

    # Ensure token is in body_html
    body_html = artifact.body_html
    if token not in body_html:
        body_html = f"{body_html}<p>Product ID: {token}</p>"

    return {
        "title": artifact.title,
        "body_html": body_html,
        "vendor": artifact.vendor,
        "product_type": artifact.product_type,
    }


async def generate_shopify_customer(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify customer via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with first_name, last_name, email, note
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating updated customer information for testing. "
            "Create an updated note/description for a customer profile. "
            f"You MUST include the literal token '{token}' in the note field. "
            "Keep it realistic."
        )
    else:
        instruction = (
            "You are generating a customer profile for an e-commerce store test. "
            "Create a realistic customer with first name, last name, email, and notes. "
            f"You MUST include the literal token '{token}' in the note field. "
            "Use a professional, realistic format."
        )

    artifact = await llm.generate_structured(ShopifyCustomerArtifact, instruction)

    # Ensure token is in note
    note = artifact.note
    if token not in note:
        note = f"{note} (Customer ID: {token})"

    return {
        "first_name": artifact.first_name,
        "last_name": artifact.last_name,
        "email": artifact.email,
        "note": note,
    }


async def generate_shopify_collection(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify collection via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with title, body_html
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated product collection for testing. "
            "Create an updated collection title and description. "
            f"You MUST include the literal token '{token}' in the body_html. "
            "Keep it realistic for an e-commerce store."
        )
    else:
        instruction = (
            "You are generating a product collection for an e-commerce store test. "
            "Create a collection with a catchy title and HTML description. "
            f"You MUST include the literal token '{token}' in the body_html. "
            "Think of collections like 'Summer Sale', 'New Arrivals', 'Best Sellers', etc."
        )

    artifact = await llm.generate_structured(ShopifyCollectionArtifact, instruction)

    # Ensure token is in body_html
    body_html = artifact.body_html
    if token not in body_html:
        body_html = f"{body_html}<p>Collection ID: {token}</p>"

    return {
        "title": artifact.title,
        "body_html": body_html,
    }


async def generate_shopify_order(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify order note via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with note
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating updated order notes for testing. "
            "Create updated order notes for a customer order. "
            f"You MUST include the literal token '{token}' in the note. "
            "Keep it realistic."
        )
    else:
        instruction = (
            "You are generating order notes for an e-commerce order test. "
            "Create realistic order notes (shipping instructions, preferences, etc.). "
            f"You MUST include the literal token '{token}' in the note. "
            "Keep it professional and realistic."
        )

    artifact = await llm.generate_structured(ShopifyOrderArtifact, instruction)

    # Ensure token is in note
    note = artifact.note
    if token not in note:
        note = f"{note} (Order ID: {token})"

    return {
        "note": note,
    }


async def generate_shopify_discount(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify discount/price rule via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with title, value, value_type
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an updated discount/promotion for testing. "
            "Create an updated discount with a catchy title. "
            f"You MUST include the literal token '{token}' in the title. "
            "Keep it realistic for an e-commerce store."
        )
    else:
        instruction = (
            "You are generating a discount/promotion for an e-commerce store test. "
            "Create a discount with a catchy title and reasonable value. "
            f"You MUST include the literal token '{token}' in the title. "
            "Think of discounts like '10% off', '$5 off orders over $50', etc. "
            "Use value_type 'percentage' or 'fixed_amount'."
        )

    artifact = await llm.generate_structured(ShopifyDiscountArtifact, instruction)

    # Ensure token is in title
    title = artifact.title
    if token not in title:
        title = f"{title} [{token}]"

    return {
        "title": title,
        "value": artifact.value,
        "value_type": artifact.value_type,
    }


async def generate_shopify_gift_card(
    model: str, token: str, is_update: bool = False
) -> Dict[str, Any]:
    """Generate a Shopify gift card via LLM.

    Args:
        model: LLM model to use
        token: Unique token to embed in content for verification
        is_update: Whether this is for an update operation

    Returns:
        Dict with initial_value, note
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating updated gift card notes for testing. "
            "Create updated notes for a gift card. "
            f"You MUST include the literal token '{token}' in the note. "
            "Keep it realistic."
        )
    else:
        instruction = (
            "You are generating a gift card for an e-commerce store test. "
            "Create a gift card with a reasonable initial value (e.g., '25.00', '50.00', '100.00') "
            "and a nice note. "
            f"You MUST include the literal token '{token}' in the note field. "
            "Keep it professional and realistic."
        )

    artifact = await llm.generate_structured(ShopifyGiftCardArtifact, instruction)

    # Ensure token is in note
    note = artifact.note
    if token not in note:
        note = f"{note} (Gift Card ID: {token})"

    return {
        "initial_value": artifact.initial_value,
        "note": note,
    }
