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

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL to view customer in Shopify admin."""
        return self.web_url_value or ""


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
