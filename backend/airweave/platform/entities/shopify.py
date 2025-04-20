"""Shopify entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class ShopifyShopEntity(ChunkEntity):
    """Schema for Shopify shop entities."""

    name: str = Field(..., description="The name of the shop")
    shop_id: int = Field(..., description="Unique identifier of the shop")
    domain: str = Field(..., description="The shop's primary domain (e.g., example.myshopify.com)")
    email: Optional[str] = Field(None, description="The contact email for the shop")
    currency: str = Field(..., description="The shop's primary currency (e.g., USD, EUR)")
    country: Optional[str] = Field(None, description="The shop's country")
    created_at: Optional[datetime] = Field(None, description="The time at which the shop was created")
    updated_at: Optional[datetime] = Field(None, description="The time at which the shop was last updated")
    plan_name: Optional[str] = Field(None, description="The shop's Shopify plan (e.g., basic, shopify, advanced)")
    timezone: Optional[str] = Field(None, description="The shop's timezone (e.g., America/New_York)")
    enabled_features: List[str] = Field(
        default_factory=list, description="List of enabled features for the shop"
    )


class ShopifyProductEntity(ChunkEntity):
    """Schema for Shopify product entities."""

    title: str = Field(..., description="The title of the product")
    product_id: int = Field(..., description="Unique identifier of the product")
    shop_id: int = Field(..., description="Unique identifier of the shop the product belongs to")
    shop_domain: str = Field(..., description="The shop's domain (e.g., example.myshopify.com)")
    body_html: Optional[str] = Field(None, description="HTML description of the product")
    vendor: Optional[str] = Field(None, description="The vendor of the product")
    product_type: Optional[str] = Field(None, description="The type of product (e.g., Clothing, Electronics)")
    created_at: Optional[datetime] = Field(None, description="The time at which the product was created")
    updated_at: Optional[datetime] = Field(None, description="The time at which the product was last updated")
    published_at: Optional[datetime] = Field(None, description="The time at which the product was published")
    status: str = Field("draft", description="The status of the product (active, draft, archived)")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the product")
    variants: List[Dict] = Field(
        default_factory=list, description="List of product variants (e.g., size, color)")
    images: List[Dict] = Field(default_factory=list, description="List of images associated with the product")
    options: List[Dict] = Field(
        default_factory=list, description="List of product options (e.g., Size, Color)")
    handle: Optional[str] = Field(None, description="SEO-friendly handle for the product URL")
    metafields: List[Dict] = Field(
        default_factory=list, description="List of metafields associated with the product")


class ShopifyOrderEntity(ChunkEntity):
    """Schema for Shopify order entities."""

    order_id: int = Field(..., description="Unique identifier of the order")
    shop_id: int = Field(..., description="Unique identifier of the shop the order belongs to")
    shop_domain: str = Field(..., description="The shop's domain (e.g., example.myshopify.com)")
    email: Optional[str] = Field(None, description="The customer's email address")
    created_at: Optional[datetime] = Field(None, description="The time at which the order was created")
    updated_at: Optional[datetime] = Field(None, description="The time at which the order was last updated")
    total_price: Optional[str] = Field(None, description="The total price of the order")
    currency: Optional[str] = Field(None, description="The currency of the order")
    financial_status: Optional[str] = Field(
        None, description="The financial status of the order (e.g., paid, pending, refunded)")
    fulfillment_status: Optional[str] = Field(
        None, description="The fulfillment status of the order (e.g., fulfilled, partial, unfulfilled)")
    customer: Optional[Dict] = Field(None, description="The customer associated with the order")
    line_items: List[Dict] = Field(default_factory=list, description="List of line items in the order")
    billing_address: Optional[Dict] = Field(None, description="The billing address for the order")
    shipping_address: Optional[Dict] = Field(None, description="The shipping address for the order")
    note: Optional[str] = Field(None, description="Free-form note associated with the order")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the order")
    metafields: List[Dict] = Field(
        default_factory=list, description="List of metafields associated with the order")


class ShopifyCustomerEntity(ChunkEntity):
    """Schema for Shopify customer entities."""

    customer_id: int = Field(..., description="Unique identifier of the customer")
    shop_id: int = Field(..., description="Unique identifier of the shop the customer belongs to")
    shop_domain: str = Field(..., description="The shop's domain (e.g., example.myshopify.com)")
    first_name: Optional[str] = Field(None, description="The customer's first name")
    last_name: Optional[str] = Field(None, description="The customer's last name")
    email: Optional[str] = Field(None, description="The customer's email address")
    phone: Optional[str] = Field(None, description="The customer's phone number")
    created_at: Optional[datetime] = Field(None, description="The time at which the customer was created")
    updated_at: Optional[datetime] = Field(None, description="The time at which the customer was last updated")
    state: Optional[str] = Field(None, description="The state of the customer (e.g., enabled, disabled)")
    verified_email: bool = Field(False, description="Whether the customer's email is verified")
    addresses: List[Dict] = Field(default_factory=list, description="List of customer addresses")
    tags: List[str] = Field(default_factory=list, description="List of tags associated with the customer")
    metafields: List[Dict] = Field(
        default_factory=list, description="List of metafields associated with the customer")


class ShopifyFileEntity(FileEntity):
    """Schema for Shopify file entities (e.g., product images, generic files).

    Reference:
        https://shopify.dev/docs/api/admin-rest/2024-04/resources/product-image
        https://shopify.dev/docs/api/admin-rest/2024-04/resources/file
    """

    file_id: int = Field(..., description="Unique identifier of the file")
    shop_id: int = Field(..., description="Unique identifier of the shop the file belongs to")
    shop_domain: str = Field(..., description="The shop's domain (e.g., example.myshopify.com)")
    resource_type: str = Field(..., description="Type of the file resource (e.g., image, file)")
    src: Optional[str] = Field(None, description="URL to access the file")
    created_at: Optional[datetime] = Field(None, description="The time at which the file was created")
    updated_at: Optional[datetime] = Field(None, description="The time at which the file was last updated")
    alt: Optional[str] = Field(None, description="Alt text for the file (e.g., for images)")
    parent: Optional[Dict[str, Any]] = Field(
        None, description="Parent resource the file is associated with (e.g., product, order)")
    metafields: List[Dict] = Field(
        default_factory=list, description="List of metafields associated with the file")