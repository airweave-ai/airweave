"""Shopify-specific generation schemas.

Pydantic schemas for generating test content for all Shopify entity types.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class ShopifyProductArtifact(BaseModel):
    """Schema for Shopify product generation."""

    title: str = Field(description="Product title")
    body_html: str = Field(description="Product description in HTML format")
    vendor: str = Field(description="Product vendor/brand name")
    product_type: str = Field(description="Product category/type")
    created_at: datetime = Field(default_factory=datetime.now)


class ShopifyCustomerArtifact(BaseModel):
    """Schema for Shopify customer generation."""

    first_name: str = Field(description="Customer first name")
    last_name: str = Field(description="Customer last name")
    email: str = Field(description="Customer email address")
    note: str = Field(description="Notes about the customer (token embedded here)")
    created_at: datetime = Field(default_factory=datetime.now)


class ShopifyCollectionArtifact(BaseModel):
    """Schema for Shopify collection generation."""

    title: str = Field(description="Collection title")
    body_html: str = Field(description="Collection description in HTML format")
    created_at: datetime = Field(default_factory=datetime.now)


class ShopifyOrderArtifact(BaseModel):
    """Schema for Shopify draft order generation."""

    note: str = Field(description="Order notes (token embedded here)")
    created_at: datetime = Field(default_factory=datetime.now)


class ShopifyDiscountArtifact(BaseModel):
    """Schema for Shopify discount/price rule generation."""

    title: str = Field(description="Discount title/name")
    value: str = Field(description="Discount value (e.g., '-10' for 10 off)")
    value_type: str = Field(description="Type of discount: 'fixed_amount' or 'percentage'")
    created_at: datetime = Field(default_factory=datetime.now)


class ShopifyGiftCardArtifact(BaseModel):
    """Schema for Shopify gift card generation."""

    initial_value: str = Field(description="Initial value of the gift card (e.g., '50.00')")
    note: str = Field(description="Notes about the gift card (token embedded here)")
    created_at: datetime = Field(default_factory=datetime.now)
