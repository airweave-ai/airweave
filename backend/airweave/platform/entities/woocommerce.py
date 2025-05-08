"""WooCommerce entity definitions for Airweave."""

from typing import List, Dict, Optional
from pydantic import Field
from airweave.platform.entities._base import ChunkEntity


class WooCommerceProductEntity(ChunkEntity):
    """WooCommerce Product Entity."""

    entity_id: str = Field(..., description="Unique product ID")
    name: str = Field(..., description="Product name")
    price: Optional[str] = Field(None, description="Product price")
    description: Optional[str] = Field(None, description="Product description")
    sku: Optional[str] = Field(None, description="Product SKU")
    categories: List[str] = Field(default_factory=list, description="List of category names")
    images: List[str] = Field(default_factory=list, description="List of product image URLs")


class WooCommerceOrderEntity(ChunkEntity):
    """WooCommerce Order Entity."""

    entity_id: str = Field(..., description="Unique order ID")
    status: str = Field(..., description="Order status")
    total: str = Field(..., description="Order total amount")
    currency: str = Field(..., description="Currency used")
    customer_id: Optional[str] = Field(None, description="Customer ID")
    line_items: List[Dict] = Field(default_factory=list, description="List of line items")