"""Shopify entity schemas.

Based on the Shopify Admin API, we define entity schemas for Shopify resources:
- Products and Product Variants
- Customers
- Orders and Draft Orders
- Collections (Custom and Smart)
- Locations
- Inventory Items and Levels
- Fulfillments
- Gift Cards
- Discounts (Price Rules)
- Metaobjects
- Files
- Themes

Uses OAuth 2.0 client credentials grant for authentication.

API Reference: https://shopify.dev/docs/api/admin-rest
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _parse_shopify_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse a Shopify datetime string (ISO 8601) into a datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class ShopifyProductEntity(BaseEntity):
    """Schema for Shopify Product resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/product
    """

    product_id: str = AirweaveField(..., description="Shopify product ID.", is_entity_id=True)
    product_title: str = AirweaveField(
        ..., description="Title of the product.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the product was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the product was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this product in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    body_html: Optional[str] = AirweaveField(
        None, description="Product description in HTML format", embeddable=True
    )
    vendor: Optional[str] = AirweaveField(
        None, description="Name of the product vendor", embeddable=True
    )
    product_type: Optional[str] = AirweaveField(
        None, description="Product type/category", embeddable=True
    )
    handle: Optional[str] = AirweaveField(
        None, description="URL-friendly product handle", embeddable=False
    )
    status: Optional[str] = AirweaveField(
        None, description="Product status (active, archived, draft)", embeddable=True
    )
    tags: Optional[str] = AirweaveField(
        None, description="Comma-separated list of product tags", embeddable=True
    )
    variants: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Product variants with pricing, inventory, etc.",
        embeddable=True,
    )
    options: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Product options (size, color, etc.)",
        embeddable=True,
    )
    images: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Product images",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view product in Shopify admin."""
        return self.web_url_value or ""


class ShopifyProductVariantEntity(BaseEntity):
    """Schema for Shopify Product Variant resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/product-variant
    """

    variant_id: str = AirweaveField(..., description="Shopify variant ID.", is_entity_id=True)
    variant_title: str = AirweaveField(
        ..., description="Title of the variant.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the variant was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the variant was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this variant in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    product_id: Optional[str] = AirweaveField(
        None, description="ID of the parent product", embeddable=False
    )
    sku: Optional[str] = AirweaveField(
        None, description="Stock keeping unit (SKU)", embeddable=True
    )
    price: Optional[str] = AirweaveField(None, description="Price of the variant", embeddable=True)
    compare_at_price: Optional[str] = AirweaveField(
        None, description="Compare-at price for sale pricing", embeddable=True
    )
    inventory_quantity: Optional[int] = AirweaveField(
        None, description="Available inventory quantity", embeddable=True
    )
    weight: Optional[float] = AirweaveField(
        None, description="Weight of the variant", embeddable=True
    )
    weight_unit: Optional[str] = AirweaveField(
        None, description="Weight unit (g, kg, oz, lb)", embeddable=False
    )
    barcode: Optional[str] = AirweaveField(
        None, description="Barcode (ISBN, UPC, GTIN, etc.)", embeddable=True
    )
    option1: Optional[str] = AirweaveField(None, description="First option value", embeddable=True)
    option2: Optional[str] = AirweaveField(None, description="Second option value", embeddable=True)
    option3: Optional[str] = AirweaveField(None, description="Third option value", embeddable=True)

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        product_id: str,
        product_title: str,
        web_url: str,
        parent_created_time: datetime,
    ) -> ShopifyProductVariantEntity:
        """Build from a Shopify API product variant object."""
        variant_id = str(data["id"])
        variant_created = _parse_shopify_ts(data.get("created_at")) or parent_created_time
        variant_updated = _parse_shopify_ts(data.get("updated_at")) or variant_created

        variant_title = data.get("title", "Default")
        if variant_title == "Default Title":
            variant_title = product_title or f"Variant {variant_id}"
        else:
            variant_title = f"{product_title} - {variant_title}" if product_title else variant_title

        breadcrumbs = [
            Breadcrumb(
                entity_id=product_id,
                name=product_title or f"Product {product_id}",
                entity_type=ShopifyProductEntity.__name__,
            )
        ]

        return cls(
            entity_id=variant_id,
            breadcrumbs=breadcrumbs,
            name=variant_title,
            created_at=variant_created,
            updated_at=variant_updated,
            variant_id=variant_id,
            variant_title=variant_title,
            created_time=variant_created,
            updated_time=variant_updated,
            web_url_value=web_url,
            product_id=product_id,
            sku=data.get("sku"),
            price=data.get("price"),
            compare_at_price=data.get("compare_at_price"),
            inventory_quantity=data.get("inventory_quantity"),
            weight=data.get("weight"),
            weight_unit=data.get("weight_unit"),
            barcode=data.get("barcode"),
            option1=data.get("option1"),
            option2=data.get("option2"),
            option3=data.get("option3"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view variant in Shopify admin."""
        return self.web_url_value or ""


class ShopifyCustomerEntity(BaseEntity):
    """Schema for Shopify Customer resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/customer
    """

    customer_id: str = AirweaveField(..., description="Shopify customer ID.", is_entity_id=True)
    customer_name: str = AirweaveField(
        ..., description="Display name of the customer.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the customer was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the customer was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this customer in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    email: Optional[str] = AirweaveField(
        None, description="Customer's email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Customer's phone number", embeddable=True
    )
    first_name: Optional[str] = AirweaveField(
        None, description="Customer's first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        None, description="Customer's last name", embeddable=True
    )
    verified_email: bool = AirweaveField(
        False, description="Whether the email has been verified", embeddable=False
    )
    accepts_marketing: bool = AirweaveField(
        False, description="Whether customer accepts marketing emails", embeddable=True
    )
    orders_count: int = AirweaveField(
        0, description="Number of orders placed by customer", embeddable=True
    )
    total_spent: Optional[str] = AirweaveField(
        None, description="Total amount spent by customer", embeddable=True
    )
    state: Optional[str] = AirweaveField(
        None,
        description="Customer account state (disabled, invited, enabled, declined)",
        embeddable=True,
    )
    currency: Optional[str] = AirweaveField(
        None, description="Customer's preferred currency", embeddable=False
    )
    tags: Optional[str] = AirweaveField(
        None, description="Comma-separated list of customer tags", embeddable=True
    )
    note: Optional[str] = AirweaveField(
        None, description="Notes about the customer", embeddable=True
    )
    default_address: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Customer's default address", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> ShopifyCustomerEntity:
        """Build from a Shopify API customer object."""
        customer_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time

        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        email = data.get("email", "")

        if first_name and last_name:
            customer_name = f"{first_name} {last_name}"
        elif first_name:
            customer_name = first_name
        elif last_name:
            customer_name = last_name
        elif email:
            customer_name = email
        else:
            customer_name = f"Customer {customer_id}"

        return cls(
            entity_id=customer_id,
            breadcrumbs=[],
            name=customer_name,
            created_at=created_time,
            updated_at=updated_time,
            customer_id=customer_id,
            customer_name=customer_name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            email=email or None,
            phone=data.get("phone"),
            first_name=first_name or None,
            last_name=last_name or None,
            verified_email=data.get("verified_email", False),
            accepts_marketing=data.get("accepts_marketing", False),
            orders_count=data.get("orders_count", 0),
            total_spent=data.get("total_spent"),
            state=data.get("state"),
            currency=data.get("currency"),
            tags=data.get("tags"),
            note=data.get("note"),
            default_address=data.get("default_address"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view customer in Shopify admin."""
        return self.web_url_value or ""


def _build_customer_breadcrumb(order_data: Dict[str, Any]) -> List[Breadcrumb]:
    """Extract customer info from an order/draft-order and return breadcrumbs."""
    customer = order_data.get("customer")
    if not customer:
        return []
    customer_id = str(customer.get("id", ""))
    if not customer_id:
        return []
    customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    if not customer_name:
        customer_name = customer.get("email", f"Customer {customer_id}")
    return [
        Breadcrumb(
            entity_id=customer_id,
            name=customer_name,
            entity_type=ShopifyCustomerEntity.__name__,
        )
    ]


class ShopifyOrderEntity(BaseEntity):
    """Schema for Shopify Order resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/order
    """

    order_id: str = AirweaveField(..., description="Shopify order ID.", is_entity_id=True)
    order_name: str = AirweaveField(
        ..., description="Order number/name (e.g., #1001).", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the order was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the order was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this order in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    order_number: Optional[int] = AirweaveField(
        None, description="Sequential order number", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="Customer's email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Customer's phone number", embeddable=True
    )
    total_price: Optional[str] = AirweaveField(
        None, description="Total price of the order including taxes and shipping", embeddable=True
    )
    subtotal_price: Optional[str] = AirweaveField(
        None, description="Subtotal price before taxes and shipping", embeddable=True
    )
    total_tax: Optional[str] = AirweaveField(None, description="Total tax amount", embeddable=True)
    total_discounts: Optional[str] = AirweaveField(
        None, description="Total discount amount applied", embeddable=True
    )
    currency: Optional[str] = AirweaveField(
        None, description="Currency code (e.g., USD, EUR)", embeddable=True
    )
    financial_status: Optional[str] = AirweaveField(
        None,
        description="Payment status (pending, authorized, paid, refunded, etc.)",
        embeddable=True,
    )
    fulfillment_status: Optional[str] = AirweaveField(
        None, description="Fulfillment status (fulfilled, partial, null)", embeddable=True
    )
    customer_id: Optional[str] = AirweaveField(
        None, description="ID of the customer who placed the order", embeddable=False
    )
    line_items: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Line items in the order",
        embeddable=True,
    )
    shipping_address: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Shipping address", embeddable=True
    )
    billing_address: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Billing address", embeddable=True
    )
    tags: Optional[str] = AirweaveField(
        None, description="Comma-separated list of order tags", embeddable=True
    )
    note: Optional[str] = AirweaveField(None, description="Notes about the order", embeddable=True)
    cancelled_at: Optional[datetime] = AirweaveField(
        None, description="When the order was cancelled (if applicable)", embeddable=True
    )
    cancel_reason: Optional[str] = AirweaveField(
        None, description="Reason for cancellation", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> ShopifyOrderEntity:
        """Build from a Shopify API order object."""
        order_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time
        order_name = data.get("name", f"Order {order_id}")
        breadcrumbs = _build_customer_breadcrumb(data)
        customer = data.get("customer")

        return cls(
            entity_id=order_id,
            breadcrumbs=breadcrumbs,
            name=order_name,
            created_at=created_time,
            updated_at=updated_time,
            order_id=order_id,
            order_name=order_name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            order_number=data.get("order_number"),
            email=data.get("email"),
            phone=data.get("phone"),
            total_price=data.get("total_price"),
            subtotal_price=data.get("subtotal_price"),
            total_tax=data.get("total_tax"),
            total_discounts=data.get("total_discounts"),
            currency=data.get("currency"),
            financial_status=data.get("financial_status"),
            fulfillment_status=data.get("fulfillment_status"),
            customer_id=str(customer.get("id")) if customer else None,
            line_items=data.get("line_items", []),
            shipping_address=data.get("shipping_address"),
            billing_address=data.get("billing_address"),
            tags=data.get("tags"),
            note=data.get("note"),
            cancelled_at=_parse_shopify_ts(data.get("cancelled_at")),
            cancel_reason=data.get("cancel_reason"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view order in Shopify admin."""
        return self.web_url_value or ""


class ShopifyDraftOrderEntity(BaseEntity):
    """Schema for Shopify Draft Order resource.

    Draft orders are orders created by merchants that haven't been completed/paid yet.
    https://shopify.dev/docs/api/admin-rest/2024-01/resources/draftorder
    """

    draft_order_id: str = AirweaveField(
        ..., description="Shopify draft order ID.", is_entity_id=True
    )
    draft_order_name: str = AirweaveField(
        ..., description="Draft order name (e.g., #D1).", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the draft order was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the draft order was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this draft order in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    email: Optional[str] = AirweaveField(
        None, description="Customer's email address", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Draft order status (open, invoice_sent, completed)", embeddable=True
    )
    total_price: Optional[str] = AirweaveField(
        None, description="Total price of the draft order", embeddable=True
    )
    subtotal_price: Optional[str] = AirweaveField(
        None, description="Subtotal price before taxes and shipping", embeddable=True
    )
    total_tax: Optional[str] = AirweaveField(None, description="Total tax amount", embeddable=True)
    currency: Optional[str] = AirweaveField(
        None, description="Currency code (e.g., USD, EUR)", embeddable=True
    )
    customer_id: Optional[str] = AirweaveField(
        None, description="ID of the customer", embeddable=False
    )
    line_items: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="Line items in the draft order",
        embeddable=True,
    )
    shipping_address: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Shipping address", embeddable=True
    )
    billing_address: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Billing address", embeddable=True
    )
    tags: Optional[str] = AirweaveField(
        None, description="Comma-separated list of tags", embeddable=True
    )
    note: Optional[str] = AirweaveField(
        None, description="Notes about the draft order", embeddable=True
    )
    invoice_sent_at: Optional[datetime] = AirweaveField(
        None, description="When the invoice was sent", embeddable=True
    )
    completed_at: Optional[datetime] = AirweaveField(
        None, description="When the draft order was completed", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> ShopifyDraftOrderEntity:
        """Build from a Shopify API draft order object."""
        draft_order_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time
        draft_order_name = data.get("name", f"Draft Order {draft_order_id}")
        breadcrumbs = _build_customer_breadcrumb(data)
        customer = data.get("customer")

        return cls(
            entity_id=draft_order_id,
            breadcrumbs=breadcrumbs,
            name=draft_order_name,
            created_at=created_time,
            updated_at=updated_time,
            draft_order_id=draft_order_id,
            draft_order_name=draft_order_name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            email=data.get("email"),
            status=data.get("status"),
            total_price=data.get("total_price"),
            subtotal_price=data.get("subtotal_price"),
            total_tax=data.get("total_tax"),
            currency=data.get("currency"),
            customer_id=str(customer.get("id")) if customer else None,
            line_items=data.get("line_items", []),
            shipping_address=data.get("shipping_address"),
            billing_address=data.get("billing_address"),
            tags=data.get("tags"),
            note=data.get("note"),
            invoice_sent_at=_parse_shopify_ts(data.get("invoice_sent_at")),
            completed_at=_parse_shopify_ts(data.get("completed_at")),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view draft order in Shopify admin."""
        return self.web_url_value or ""


class ShopifyCollectionEntity(BaseEntity):
    """Schema for Shopify Collection resources (Custom and Smart Collections).

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/customcollection
    https://shopify.dev/docs/api/admin-rest/2024-01/resources/smartcollection
    """

    collection_id: str = AirweaveField(..., description="Shopify collection ID.", is_entity_id=True)
    collection_title: str = AirweaveField(
        ..., description="Title of the collection.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the collection was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the collection was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this collection in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    handle: Optional[str] = AirweaveField(
        None, description="URL-friendly collection handle", embeddable=False
    )
    body_html: Optional[str] = AirweaveField(
        None, description="Collection description in HTML format", embeddable=True
    )
    published_at: Optional[datetime] = AirweaveField(
        None, description="When the collection was published", embeddable=True
    )
    published_scope: Optional[str] = AirweaveField(
        None, description="Publication scope (web, global)", embeddable=False
    )
    sort_order: Optional[str] = AirweaveField(
        None, description="Sort order for products in collection", embeddable=False
    )
    collection_type: str = AirweaveField(
        "custom", description="Type of collection (custom or smart)", embeddable=True
    )
    disjunctive: Optional[bool] = AirweaveField(
        None,
        description="For smart collections: whether rules are OR (true) or AND (false)",
        embeddable=False,
    )
    rules: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="For smart collections: rules that define product membership",
        embeddable=True,
    )
    products_count: Optional[int] = AirweaveField(
        None, description="Number of products in the collection", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        collection_type: str,
        web_url: str,
    ) -> ShopifyCollectionEntity:
        """Build from a Shopify API custom_collection or smart_collection object."""
        collection_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("published_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time
        title = data.get("title", f"Collection {collection_id}")

        return cls(
            entity_id=collection_id,
            breadcrumbs=[],
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            collection_id=collection_id,
            collection_title=title,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            handle=data.get("handle"),
            body_html=data.get("body_html"),
            published_at=_parse_shopify_ts(data.get("published_at")),
            published_scope=data.get("published_scope"),
            sort_order=data.get("sort_order"),
            collection_type=collection_type,
            disjunctive=data.get("disjunctive") if collection_type == "smart" else None,
            rules=data.get("rules", []) if collection_type == "smart" else [],
            products_count=None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view collection in Shopify admin."""
        return self.web_url_value or ""


class ShopifyInventoryItemEntity(BaseEntity):
    """Schema for Shopify Inventory Item resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/inventoryitem
    """

    inventory_item_id: str = AirweaveField(
        ..., description="Shopify inventory item ID.", is_entity_id=True
    )
    inventory_item_name: str = AirweaveField(
        ..., description="Display name for the inventory item.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the inventory item was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the inventory item was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this inventory item in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    sku: Optional[str] = AirweaveField(
        None, description="Stock keeping unit (SKU)", embeddable=True
    )
    cost: Optional[str] = AirweaveField(
        None, description="Unit cost of the inventory item", embeddable=True
    )
    tracked: bool = AirweaveField(
        False, description="Whether inventory tracking is enabled", embeddable=True
    )
    requires_shipping: bool = AirweaveField(
        False, description="Whether the item requires shipping", embeddable=False
    )
    country_code_of_origin: Optional[str] = AirweaveField(
        None, description="Country code of origin", embeddable=True
    )
    province_code_of_origin: Optional[str] = AirweaveField(
        None, description="Province/state code of origin", embeddable=False
    )
    harmonized_system_code: Optional[str] = AirweaveField(
        None, description="Harmonized System (HS) tariff code", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view inventory item in Shopify admin."""
        return self.web_url_value or ""


class ShopifyLocationEntity(BaseEntity):
    """Schema for Shopify Location resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/location
    """

    location_id: str = AirweaveField(..., description="Shopify location ID.", is_entity_id=True)
    location_name: str = AirweaveField(
        ..., description="Name of the location.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the location was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the location was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this location in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    address1: Optional[str] = AirweaveField(
        None, description="Primary street address", embeddable=True
    )
    address2: Optional[str] = AirweaveField(
        None, description="Secondary address line", embeddable=True
    )
    city: Optional[str] = AirweaveField(None, description="City", embeddable=True)
    province: Optional[str] = AirweaveField(
        None, description="Province/state name", embeddable=True
    )
    province_code: Optional[str] = AirweaveField(
        None, description="Province/state code", embeddable=False
    )
    country: Optional[str] = AirweaveField(None, description="Country name", embeddable=True)
    country_code: Optional[str] = AirweaveField(
        None, description="Country code (ISO 3166-1 alpha-2)", embeddable=False
    )
    zip: Optional[str] = AirweaveField(None, description="Postal/ZIP code", embeddable=True)
    phone: Optional[str] = AirweaveField(None, description="Phone number", embeddable=True)
    active: bool = AirweaveField(
        True, description="Whether the location is active", embeddable=True
    )
    legacy: bool = AirweaveField(
        False, description="Whether this is a legacy location", embeddable=False
    )
    localized_country_name: Optional[str] = AirweaveField(
        None, description="Localized country name", embeddable=True
    )
    localized_province_name: Optional[str] = AirweaveField(
        None, description="Localized province/state name", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view location in Shopify admin."""
        return self.web_url_value or ""


class ShopifyInventoryLevelEntity(BaseEntity):
    """Schema for Shopify Inventory Level resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/inventorylevel
    """

    inventory_level_id: str = AirweaveField(
        ..., description="Composite ID (inventory_item_id-location_id).", is_entity_id=True
    )
    inventory_level_name: str = AirweaveField(
        ..., description="Display name for the inventory level.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the inventory level was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the inventory level was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this inventory in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    inventory_item_id: str = AirweaveField(
        ..., description="ID of the inventory item", embeddable=False
    )
    location_id: str = AirweaveField(..., description="ID of the location", embeddable=False)
    available: Optional[int] = AirweaveField(
        None, description="Available quantity at this location", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view inventory level in Shopify admin."""
        return self.web_url_value or ""


class ShopifyFulfillmentEntity(BaseEntity):
    """Schema for Shopify Fulfillment resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/fulfillment
    """

    fulfillment_id: str = AirweaveField(
        ..., description="Shopify fulfillment ID.", is_entity_id=True
    )
    fulfillment_name: str = AirweaveField(
        ..., description="Display name for the fulfillment.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the fulfillment was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the fulfillment was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this fulfillment in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    order_id: str = AirweaveField(..., description="ID of the parent order", embeddable=False)
    status: Optional[str] = AirweaveField(
        None,
        description="Status of the fulfillment (pending, open, success, cancelled, error, failure)",
        embeddable=True,
    )
    tracking_company: Optional[str] = AirweaveField(
        None, description="Name of the tracking company", embeddable=True
    )
    tracking_number: Optional[str] = AirweaveField(
        None, description="Tracking number", embeddable=True
    )
    tracking_numbers: List[str] = AirweaveField(
        default_factory=list, description="List of tracking numbers", embeddable=True
    )
    tracking_url: Optional[str] = AirweaveField(
        None, description="URL for tracking the shipment", embeddable=False
    )
    tracking_urls: List[str] = AirweaveField(
        default_factory=list, description="List of tracking URLs", embeddable=False
    )
    location_id: Optional[str] = AirweaveField(
        None, description="ID of the fulfillment location", embeddable=False
    )
    line_items: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Line items in this fulfillment", embeddable=True
    )
    shipment_status: Optional[str] = AirweaveField(
        None, description="Shipment status", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        order_id: str,
        order_name: str,
        web_url: str,
    ) -> ShopifyFulfillmentEntity:
        """Build from a Shopify API fulfillment object nested under an order."""
        fulfillment_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time
        name = f"Fulfillment {fulfillment_id} for {order_name}"

        breadcrumbs = [
            Breadcrumb(
                entity_id=order_id,
                name=order_name,
                entity_type=ShopifyOrderEntity.__name__,
            )
        ]

        return cls(
            entity_id=fulfillment_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_time,
            updated_at=updated_time,
            fulfillment_id=fulfillment_id,
            fulfillment_name=name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            order_id=order_id,
            status=data.get("status"),
            tracking_company=data.get("tracking_company"),
            tracking_number=data.get("tracking_number"),
            tracking_numbers=data.get("tracking_numbers", []),
            tracking_url=data.get("tracking_url"),
            tracking_urls=data.get("tracking_urls", []),
            location_id=str(data.get("location_id")) if data.get("location_id") else None,
            line_items=data.get("line_items", []),
            shipment_status=data.get("shipment_status"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view fulfillment in Shopify admin."""
        return self.web_url_value or ""


class ShopifyGiftCardEntity(BaseEntity):
    """Schema for Shopify Gift Card resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/gift-card
    """

    gift_card_id: str = AirweaveField(..., description="Shopify gift card ID.", is_entity_id=True)
    gift_card_name: str = AirweaveField(
        ..., description="Display name for the gift card.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the gift card was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the gift card was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this gift card in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    initial_value: Optional[str] = AirweaveField(
        None, description="Initial value of the gift card", embeddable=True
    )
    balance: Optional[str] = AirweaveField(None, description="Current balance", embeddable=True)
    currency: Optional[str] = AirweaveField(None, description="Currency code", embeddable=True)
    code: Optional[str] = AirweaveField(
        None, description="Gift card code (masked)", embeddable=True
    )
    last_characters: Optional[str] = AirweaveField(
        None, description="Last 4 characters of the code", embeddable=True
    )
    disabled_at: Optional[datetime] = AirweaveField(
        None, description="When the gift card was disabled", embeddable=True
    )
    expires_on: Optional[str] = AirweaveField(None, description="Expiration date", embeddable=True)
    note: Optional[str] = AirweaveField(
        None, description="Notes about the gift card", embeddable=True
    )
    customer_id: Optional[str] = AirweaveField(
        None, description="ID of the customer who owns this gift card", embeddable=False
    )
    order_id: Optional[str] = AirweaveField(
        None, description="ID of the order that created this gift card", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        web_url: str,
    ) -> ShopifyGiftCardEntity:
        """Build from a Shopify API gift_card object."""
        gift_card_id = str(data["id"])
        created_time = _parse_shopify_ts(data.get("created_at")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(data.get("updated_at")) or created_time

        last_chars = data.get("last_characters", "")
        gift_card_name = (
            f"Gift Card ****{last_chars}" if last_chars else f"Gift Card {gift_card_id}"
        )

        return cls(
            entity_id=gift_card_id,
            breadcrumbs=[],
            name=gift_card_name,
            created_at=created_time,
            updated_at=updated_time,
            gift_card_id=gift_card_id,
            gift_card_name=gift_card_name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            initial_value=data.get("initial_value"),
            balance=data.get("balance"),
            currency=data.get("currency"),
            code=data.get("code"),
            last_characters=last_chars,
            disabled_at=_parse_shopify_ts(data.get("disabled_at")),
            expires_on=data.get("expires_on"),
            note=data.get("note"),
            customer_id=str(data.get("customer_id")) if data.get("customer_id") else None,
            order_id=str(data.get("order_id")) if data.get("order_id") else None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view gift card in Shopify admin."""
        return self.web_url_value or ""


class ShopifyDiscountEntity(BaseEntity):
    """Schema for Shopify Price Rule / Discount resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/pricerule
    """

    discount_id: str = AirweaveField(..., description="Shopify price rule ID.", is_entity_id=True)
    discount_title: str = AirweaveField(
        ..., description="Title of the discount/price rule.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the discount was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the discount was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this discount in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    value_type: Optional[str] = AirweaveField(
        None, description="Type of discount value (fixed_amount, percentage)", embeddable=True
    )
    value: Optional[str] = AirweaveField(
        None, description="Discount value (negative for discounts)", embeddable=True
    )
    target_type: Optional[str] = AirweaveField(
        None, description="Target type (line_item, shipping_line)", embeddable=True
    )
    target_selection: Optional[str] = AirweaveField(
        None, description="Target selection (all, entitled)", embeddable=True
    )
    allocation_method: Optional[str] = AirweaveField(
        None, description="Allocation method (across, each)", embeddable=True
    )
    once_per_customer: bool = AirweaveField(
        False,
        description="Whether the discount can only be used once per customer",
        embeddable=True,
    )
    usage_limit: Optional[int] = AirweaveField(
        None, description="Maximum number of times the discount can be used", embeddable=True
    )
    starts_at: Optional[datetime] = AirweaveField(
        None, description="When the discount becomes active", embeddable=True
    )
    ends_at: Optional[datetime] = AirweaveField(
        None, description="When the discount expires", embeddable=True
    )
    prerequisite_subtotal_range: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Minimum subtotal required", embeddable=True
    )
    prerequisite_quantity_range: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Minimum quantity required", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view discount in Shopify admin."""
        return self.web_url_value or ""


class ShopifyMetaobjectEntity(BaseEntity):
    """Schema for Shopify Metaobject resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/metaobject
    """

    metaobject_id: str = AirweaveField(..., description="Shopify metaobject ID.", is_entity_id=True)
    metaobject_name: str = AirweaveField(
        ..., description="Display name/handle for the metaobject.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the metaobject was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the metaobject was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this metaobject in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    type: str = AirweaveField(..., description="Metaobject definition type", embeddable=True)
    handle: Optional[str] = AirweaveField(
        None, description="Unique handle for the metaobject", embeddable=True
    )
    fields: List[Dict[str, Any]] = AirweaveField(
        default_factory=list, description="Field values for the metaobject", embeddable=True
    )
    capabilities: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Capabilities of the metaobject", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view metaobject in Shopify admin."""
        return self.web_url_value or ""


class ShopifyFileEntity(FileEntity):
    """Schema for Shopify File resource.

    Inherits from FileEntity for consistency with other file entities in the codebase.

    https://shopify.dev/docs/api/admin-graphql/2024-01/objects/file
    """

    file_id: str = AirweaveField(..., description="Shopify file ID.", is_entity_id=True)
    file_name: str = AirweaveField(
        ..., description="Name of the file.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the file was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the file was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this file in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # Shopify-specific fields
    alt: Optional[str] = AirweaveField(
        None, description="Alt text for accessibility", embeddable=True
    )
    file_status: Optional[str] = AirweaveField(
        None,
        description="Status of the file (UPLOADED, PROCESSING, READY, FAILED)",
        embeddable=True,
    )
    preview_image_url: Optional[str] = AirweaveField(
        None, description="URL of the preview image", embeddable=False
    )

    @classmethod
    def from_api(
        cls,
        file_node: Dict[str, Any],
        *,
        web_url: str,
    ) -> ShopifyFileEntity:
        """Build from a Shopify GraphQL file node (GenericFile/MediaImage/Video)."""
        file_gid = file_node.get("id", "")
        file_id = file_gid.split("/")[-1] if "/" in file_gid else file_gid

        created_time = _parse_shopify_ts(file_node.get("createdAt")) or datetime.utcnow()
        updated_time = _parse_shopify_ts(file_node.get("updatedAt")) or created_time

        file_type = "GENERIC"
        file_url = file_node.get("url") or ""
        file_size = file_node.get("originalFileSize") or 0

        if "image" in file_node:
            file_type = "IMAGE"
            file_url = file_node.get("image", {}).get("url") or ""
        elif "originalSource" in file_node:
            file_type = "VIDEO"
            original_source = file_node.get("originalSource", {})
            file_url = original_source.get("url") or ""
            file_size = original_source.get("fileSize") or 0

        file_name = file_node.get("alt") or f"File {file_id}"

        return cls(
            entity_id=file_id,
            breadcrumbs=[],
            name=file_name,
            created_at=created_time,
            updated_at=updated_time,
            url=file_url,
            size=file_size,
            file_type=file_type,
            file_id=file_id,
            file_name=file_name,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=web_url,
            alt=file_node.get("alt"),
            file_status=file_node.get("fileStatus"),
            preview_image_url=file_url or None,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view file in Shopify admin."""
        return self.web_url_value or ""


class ShopifyThemeEntity(BaseEntity):
    """Schema for Shopify Theme resource.

    https://shopify.dev/docs/api/admin-rest/2024-01/resources/theme
    """

    theme_id: str = AirweaveField(..., description="Shopify theme ID.", is_entity_id=True)
    theme_name: str = AirweaveField(
        ..., description="Name of the theme.", embeddable=True, is_name=True
    )
    created_time: datetime = AirweaveField(
        ..., description="When the theme was created.", is_created_at=True
    )
    updated_time: datetime = AirweaveField(
        ..., description="When the theme was last updated.", is_updated_at=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this theme in Shopify admin.",
        embeddable=False,
        unhashable=True,
    )

    # API fields
    role: Optional[str] = AirweaveField(
        None, description="Role of the theme (main, unpublished, demo)", embeddable=True
    )
    theme_store_id: Optional[int] = AirweaveField(
        None, description="ID from the Shopify Theme Store", embeddable=False
    )
    previewable: bool = AirweaveField(
        True, description="Whether the theme can be previewed", embeddable=True
    )
    processing: bool = AirweaveField(
        False, description="Whether the theme is currently being processed", embeddable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view theme in Shopify admin."""
        return self.web_url_value or ""
