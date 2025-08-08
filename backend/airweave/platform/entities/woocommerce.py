"""WooCommerce entity definitions.

This module contains the entity classes for WooCommerce data types:
- Products
- Orders
- Customers
- Categories
- Coupons
- Refunds
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class WooCommerceProductEntity(ChunkEntity):
    """WooCommerce product entity."""

    name: str
    slug: str
    type: str
    status: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    price: Optional[str] = None
    regular_price: Optional[str] = None
    sale_price: Optional[str] = None
    stock_status: Optional[str] = None
    categories: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    images: List[Dict[str, Any]] = Field(default_factory=list)
    attributes: List[Dict[str, Any]] = Field(default_factory=list)
    variations: List[int] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WooCommerceOrderEntity(ChunkEntity):
    """WooCommerce order entity."""

    number: str
    status: str
    currency: str
    total: str
    customer_id: Optional[int] = None
    customer_note: Optional[str] = None
    billing: Dict[str, Any] = Field(default_factory=dict)
    shipping: Dict[str, Any] = Field(default_factory=dict)
    payment_method: Optional[str] = None
    payment_method_title: Optional[str] = None
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    shipping_lines: List[Dict[str, Any]] = Field(default_factory=list)
    fee_lines: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WooCommerceCustomerEntity(ChunkEntity):
    """WooCommerce customer entity."""

    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    billing: Dict[str, Any] = Field(default_factory=dict)
    shipping: Dict[str, Any] = Field(default_factory=dict)
    is_paying_customer: bool = False
    orders_count: int = 0
    total_spent: str = "0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WooCommerceCategoryEntity(ChunkEntity):
    """WooCommerce product category entity."""

    name: str
    slug: str
    description: Optional[str] = None
    parent: Optional[int] = None
    count: int = 0
    image: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WooCommerceCouponEntity(ChunkEntity):
    """WooCommerce coupon entity."""

    code: str
    amount: str
    discount_type: str
    description: Optional[str] = None
    date_expires: Optional[str] = None
    usage_count: int = 0
    individual_use: bool = False
    product_ids: List[int] = Field(default_factory=list)
    excluded_product_ids: List[int] = Field(default_factory=list)
    usage_limit: Optional[int] = None
    usage_limit_per_user: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WooCommerceRefundEntity(ChunkEntity):
    """WooCommerce refund entity."""

    order_id: str
    amount: str
    reason: Optional[str] = None
    refunded_by: Optional[int] = None
    refunded_payment: bool = False
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
