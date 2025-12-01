"""Shopify entity schemas."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class ShopifyShopEntity(BaseEntity):
    """The Shopify shop (store) metadata."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (shop ID or domain)
    # - breadcrumbs (empty - shop is top-level)
    # - name (shop name)
    # - created_at (None - shop doesn't have creation timestamp in API)
    # - updated_at (None - shop doesn't have update timestamp in API)

    # API fields
    email: Optional[str] = AirweaveField(None, description="Shop email address", embeddable=True)
    domain: Optional[str] = AirweaveField(None, description="Shop domain", embeddable=True)
    currency_code: Optional[str] = AirweaveField(
        None, description="Primary currency code", embeddable=False
    )
    timezone: Optional[str] = AirweaveField(None, description="Shop timezone", embeddable=False)
    shop_owner: Optional[str] = AirweaveField(None, description="Shop owner name", embeddable=True)
    country_name: Optional[str] = AirweaveField(None, description="Shop country", embeddable=True)


class ShopifyProductEntity(BaseEntity):
    """A Shopify product."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (product ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (product title)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    description: Optional[str] = AirweaveField(
        None, description="Product description (plain text)", embeddable=True
    )
    description_html: Optional[str] = AirweaveField(
        None, description="Product description (HTML)", embeddable=True
    )
    handle: Optional[str] = AirweaveField(
        None, description="URL-friendly product handle", embeddable=False
    )
    status: Optional[str] = AirweaveField(
        None, description="Product status (ACTIVE, DRAFT, ARCHIVED)", embeddable=False
    )
    published_at: Optional[datetime] = AirweaveField(
        None, description="When the product was published", embeddable=False
    )
    vendor: Optional[str] = AirweaveField(None, description="Product vendor", embeddable=True)
    product_type: Optional[str] = AirweaveField(
        None, description="Product type/category", embeddable=True
    )
    tags: Optional[str] = AirweaveField(
        None, description="Product tags (JSON array)", embeddable=True
    )
    total_inventory: Optional[int] = AirweaveField(
        None, description="Total inventory across all variants", embeddable=False
    )
    tracks_inventory: Optional[bool] = AirweaveField(
        None, description="Whether inventory is tracked", embeddable=False
    )
    online_store_url: Optional[str] = AirweaveField(
        None, description="URL to product in online store", embeddable=False
    )
    featured_image_url: Optional[str] = AirweaveField(
        None, description="Featured image URL", embeddable=False
    )
    price_range_min: Optional[str] = AirweaveField(
        None, description="Minimum variant price", embeddable=False
    )
    price_range_max: Optional[str] = AirweaveField(
        None, description="Maximum variant price", embeddable=False
    )
    currency_code: Optional[str] = AirweaveField(
        None, description="Price currency code", embeddable=False
    )


class ShopifyOrderEntity(BaseEntity):
    """A Shopify order."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (order ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (order name, e.g. #1001)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    email: Optional[str] = AirweaveField(
        None, description="Customer email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(None, description="Customer phone number", embeddable=True)
    cancelled_at: Optional[datetime] = AirweaveField(
        None, description="When the order was cancelled", embeddable=False
    )
    closed_at: Optional[datetime] = AirweaveField(
        None, description="When the order was closed", embeddable=False
    )
    processed_at: Optional[datetime] = AirweaveField(
        None, description="When the order was processed", embeddable=False
    )
    fulfillment_status: Optional[str] = AirweaveField(
        None, description="Fulfillment status display", embeddable=False
    )
    financial_status: Optional[str] = AirweaveField(
        None, description="Financial status display", embeddable=False
    )
    fully_paid: Optional[bool] = AirweaveField(
        None, description="Whether the order is fully paid", embeddable=False
    )
    confirmed: Optional[bool] = AirweaveField(
        None, description="Whether the order is confirmed", embeddable=False
    )
    cancelled: Optional[bool] = AirweaveField(
        None, description="Whether the order is cancelled", embeddable=False
    )
    test: Optional[bool] = AirweaveField(
        None, description="Whether this is a test order", embeddable=False
    )
    tags: Optional[str] = AirweaveField(
        None, description="Order tags (JSON array)", embeddable=True
    )
    note: Optional[str] = AirweaveField(None, description="Order notes", embeddable=True)
    total_price: Optional[str] = AirweaveField(
        None, description="Total price amount", embeddable=False
    )
    subtotal_price: Optional[str] = AirweaveField(
        None, description="Subtotal price amount", embeddable=False
    )
    total_tax: Optional[str] = AirweaveField(None, description="Total tax amount", embeddable=False)
    total_shipping_price: Optional[str] = AirweaveField(
        None, description="Total shipping amount", embeddable=False
    )
    currency_code: Optional[str] = AirweaveField(
        None, description="Order currency code", embeddable=False
    )
    customer_id: Optional[str] = AirweaveField(None, description="Customer ID", embeddable=False)
    customer_email: Optional[str] = AirweaveField(
        None, description="Customer email from order", embeddable=True
    )
    customer_name: Optional[str] = AirweaveField(
        None, description="Customer display name", embeddable=True
    )


class ShopifyCustomerEntity(BaseEntity):
    """A Shopify customer."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (customer ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (customer display name)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    first_name: Optional[str] = AirweaveField(
        None, description="Customer first name", embeddable=True
    )
    last_name: Optional[str] = AirweaveField(
        None, description="Customer last name", embeddable=True
    )
    email: Optional[str] = AirweaveField(
        None, description="Customer email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(None, description="Customer phone number", embeddable=True)
    state: Optional[str] = AirweaveField(
        None, description="Customer account state", embeddable=False
    )
    verified_email: Optional[bool] = AirweaveField(
        None, description="Whether email is verified", embeddable=False
    )
    tax_exempt: Optional[bool] = AirweaveField(
        None, description="Whether customer is tax exempt", embeddable=False
    )
    tags: Optional[str] = AirweaveField(
        None, description="Customer tags (JSON array)", embeddable=True
    )
    note: Optional[str] = AirweaveField(None, description="Customer notes", embeddable=True)
    orders_count: Optional[int] = AirweaveField(
        None, description="Total number of orders", embeddable=False
    )
    total_spent: Optional[str] = AirweaveField(
        None, description="Total amount spent", embeddable=False
    )
    average_order_amount: Optional[str] = AirweaveField(
        None, description="Average order amount", embeddable=False
    )
    currency_code: Optional[str] = AirweaveField(
        None, description="Currency code", embeddable=False
    )
    lifetime_duration: Optional[str] = AirweaveField(
        None, description="Customer lifetime duration", embeddable=False
    )
    addresses: Optional[str] = AirweaveField(
        None, description="Customer addresses (JSON array)", embeddable=True
    )


class ShopifyCollectionEntity(BaseEntity):
    """A Shopify collection."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (collection ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (collection title)
    # - created_at (None - collections don't have createdAt in GraphQL)
    # - updated_at (from updatedAt)

    # API fields
    description: Optional[str] = AirweaveField(
        None, description="Collection description (plain text)", embeddable=True
    )
    description_html: Optional[str] = AirweaveField(
        None, description="Collection description (HTML)", embeddable=True
    )
    handle: Optional[str] = AirweaveField(
        None, description="URL-friendly collection handle", embeddable=False
    )
    sort_order: Optional[str] = AirweaveField(
        None, description="Product sort order", embeddable=False
    )
    template_suffix: Optional[str] = AirweaveField(
        None, description="Template suffix for theme", embeddable=False
    )
    products_count: Optional[int] = AirweaveField(
        None, description="Number of products in collection", embeddable=False
    )
    image_url: Optional[str] = AirweaveField(
        None, description="Collection image URL", embeddable=False
    )
    rule_set: Optional[str] = AirweaveField(
        None, description="Collection rules (JSON)", embeddable=True
    )


class ShopifyDraftOrderEntity(BaseEntity):
    """A Shopify draft order."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (draft order ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (draft order name)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    email: Optional[str] = AirweaveField(
        None, description="Customer email address", embeddable=True
    )
    phone: Optional[str] = AirweaveField(None, description="Customer phone number", embeddable=True)
    completed_at: Optional[datetime] = AirweaveField(
        None, description="When the draft order was completed", embeddable=False
    )
    status: Optional[str] = AirweaveField(None, description="Draft order status", embeddable=False)
    tags: Optional[str] = AirweaveField(
        None, description="Draft order tags (JSON array)", embeddable=True
    )
    note: Optional[str] = AirweaveField(None, description="Draft order notes", embeddable=True)
    invoice_url: Optional[str] = AirweaveField(None, description="Invoice URL", embeddable=False)
    total_price: Optional[str] = AirweaveField(None, description="Total price", embeddable=False)
    subtotal_price: Optional[str] = AirweaveField(
        None, description="Subtotal price", embeddable=False
    )
    total_tax: Optional[str] = AirweaveField(None, description="Total tax", embeddable=False)
    total_shipping_price: Optional[str] = AirweaveField(
        None, description="Total shipping price", embeddable=False
    )
    currency_code: Optional[str] = AirweaveField(
        None, description="Currency code", embeddable=False
    )
    customer_id: Optional[str] = AirweaveField(None, description="Customer ID", embeddable=False)
    customer_email: Optional[str] = AirweaveField(
        None, description="Customer email from draft order", embeddable=True
    )
    customer_name: Optional[str] = AirweaveField(
        None, description="Customer display name", embeddable=True
    )


class ShopifyInventoryItemEntity(BaseEntity):
    """A Shopify inventory item."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (inventory item ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (SKU or ID)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    sku: Optional[str] = AirweaveField(None, description="Stock keeping unit", embeddable=True)
    tracked: Optional[bool] = AirweaveField(
        None, description="Whether inventory is tracked", embeddable=False
    )
    requires_shipping: Optional[bool] = AirweaveField(
        None, description="Whether item requires shipping", embeddable=False
    )
    duplicate_sku_count: Optional[int] = AirweaveField(
        None, description="Number of duplicate SKUs", embeddable=False
    )
    country_code_of_origin: Optional[str] = AirweaveField(
        None, description="Country code of origin", embeddable=False
    )
    province_code_of_origin: Optional[str] = AirweaveField(
        None, description="Province code of origin", embeddable=False
    )
    harmonized_system_code: Optional[str] = AirweaveField(
        None, description="Harmonized system code", embeddable=False
    )
    unit_cost: Optional[str] = AirweaveField(None, description="Unit cost amount", embeddable=False)
    currency_code: Optional[str] = AirweaveField(
        None, description="Currency code", embeddable=False
    )


class ShopifyLocationEntity(BaseEntity):
    """A Shopify location (warehouse, retail store, etc.)."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (location ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (location name)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    address: Optional[str] = AirweaveField(
        None, description="Location address (JSON)", embeddable=True
    )
    is_active: Optional[bool] = AirweaveField(
        None, description="Whether location is active", embeddable=False
    )
    fulfills_online_orders: Optional[bool] = AirweaveField(
        None, description="Whether location fulfills online orders", embeddable=False
    )
    has_active_inventory: Optional[bool] = AirweaveField(
        None, description="Whether location has active inventory", embeddable=False
    )
    ships_inventory: Optional[bool] = AirweaveField(
        None, description="Whether location ships inventory", embeddable=False
    )


class ShopifyFulfillmentOrderEntity(BaseEntity):
    """A Shopify fulfillment order."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (fulfillment order ID)
    # - breadcrumbs (shop breadcrumb)
    # - name (fulfillment order ID)
    # - created_at (from createdAt)
    # - updated_at (from updatedAt)

    # API fields
    status: Optional[str] = AirweaveField(
        None, description="Fulfillment order status", embeddable=False
    )
    request_status: Optional[str] = AirweaveField(
        None, description="Request status", embeddable=False
    )
    destination: Optional[str] = AirweaveField(
        None, description="Destination address (JSON)", embeddable=True
    )
    delivery_method_type: Optional[str] = AirweaveField(
        None, description="Delivery method type", embeddable=False
    )
    assigned_location_name: Optional[str] = AirweaveField(
        None, description="Assigned location name", embeddable=True
    )
    assigned_location_address: Optional[str] = AirweaveField(
        None, description="Assigned location address", embeddable=True
    )
