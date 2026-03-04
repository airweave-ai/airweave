"""Shopify source implementation using Client Credentials Grant.

We retrieve data from the Shopify Admin API for the following resources:
- Products (with variants)
- Customers
- Orders and Draft Orders
- Collections (Custom and Smart)
- Locations
- Inventory Items and Levels
- Fulfillments
- Gift Cards
- Discounts (Price Rules)
- Metaobjects
- Files (via GraphQL)
- Themes

Authentication uses OAuth 2.0 client credentials grant to exchange
client_id and client_secret for an access token.

API Reference: https://shopify.dev/docs/api/admin-rest
Auth Reference: https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import ShopifyAuthConfig
from airweave.platform.configs.config import ShopifyConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.shopify import (
    ShopifyCollectionEntity,
    ShopifyCustomerEntity,
    ShopifyDiscountEntity,
    ShopifyDraftOrderEntity,
    ShopifyFileEntity,
    ShopifyFulfillmentEntity,
    ShopifyGiftCardEntity,
    ShopifyInventoryItemEntity,
    ShopifyInventoryLevelEntity,
    ShopifyLocationEntity,
    ShopifyMetaobjectEntity,
    ShopifyOrderEntity,
    ShopifyProductEntity,
    ShopifyProductVariantEntity,
    ShopifyThemeEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

# Shopify API version - use a stable version
SHOPIFY_API_VERSION = "2024-01"


@source(
    name="Shopify",
    short_name="shopify",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=ShopifyAuthConfig,
    config_class=ShopifyConfig,
    labels=["E-commerce", "Retail"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class ShopifySource(BaseSource):
    """Shopify source connector integrates with the Shopify Admin API.

    Uses OAuth 2.0 client credentials grant to exchange client_id/client_secret
    for an access token, then syncs comprehensive data from your Shopify store:
    - Products and their variants with pricing and inventory
    - Customer profiles and purchase history
    - Orders with line items and fulfillment status
    - Custom and Smart Collections
    - Store locations and inventory levels
    - Fulfillments and shipment tracking
    - Gift cards and discounts/price rules
    - Metaobjects for custom data structures
    - Files/media via GraphQL
    - Themes and templates
    """

    # Shopify API pagination limits
    SHOPIFY_PAGE_LIMIT = 250  # Maximum results per page

    def __init__(self):
        """Initialize the Shopify source."""
        super().__init__()
        self.shop_domain: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.access_token: Optional[str] = None

    def _prepare_entity(self, entity: BaseEntity) -> BaseEntity:
        """Prepare entity for yielding - sets original_entity_id for orphan cleanup.

        This ensures the orphan cleanup process can properly delete entities
        from Qdrant when they are removed from the source.
        """
        from airweave.platform.entities._base import AirweaveSystemMetadata

        if entity.airweave_system_metadata is None:
            entity.airweave_system_metadata = AirweaveSystemMetadata()
        entity.airweave_system_metadata.original_entity_id = entity.entity_id
        return entity

    @classmethod
    async def create(
        cls, credentials: ShopifyAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "ShopifySource":
        """Create a new Shopify source instance.

        Args:
            credentials: ShopifyAuthConfig with client_id and client_secret
            config: Required configuration containing shop_domain

        Returns:
            Configured ShopifySource instance
        """
        instance = cls()

        # Extract credentials from auth config
        instance.client_id = credentials.client_id
        instance.client_secret = credentials.client_secret

        # Get shop_domain from config
        if config and config.get("shop_domain"):
            instance.shop_domain = cls._normalize_shop_domain(config["shop_domain"])
        else:
            raise ValueError("shop_domain is required in config")

        # Exchange client credentials for access token
        instance.access_token = await instance._get_access_token()

        return instance

    async def _get_access_token(self) -> str:
        """Exchange client credentials for an access token.

        Uses OAuth 2.0 client credentials grant flow.
        POST https://{shop}.myshopify.com/admin/oauth/access_token

        Returns:
            Access token string

        Raises:
            ValueError: If token exchange fails
        """
        url = f"https://{self.shop_domain}/admin/oauth/access_token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(
                    f"Failed to get access token: {response.status_code} - {response.text}"
                )

            data = response.json()
            return data["access_token"]

    @staticmethod
    def _normalize_shop_domain(domain: Optional[str]) -> Optional[str]:
        """Normalize Shopify shop domain.

        Removes protocol prefix and trailing slash if present.
        """
        if not domain:
            return domain
        # Remove https:// or http:// prefix
        domain = domain.replace("https://", "").replace("http://", "")
        # Remove trailing slash
        domain = domain.rstrip("/")
        return domain.lower()

    def _build_api_url(self, endpoint: str) -> str:
        """Build a Shopify Admin API URL.

        Args:
            endpoint: API endpoint path (e.g., 'products.json')

        Returns:
            Full API URL
        """
        # Remove any leading slashes from endpoint
        endpoint = endpoint.lstrip("/")
        return f"https://{self.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/{endpoint}"

    def _build_admin_url(self, resource: str, resource_id: str) -> str:
        """Build a Shopify Admin UI URL for a resource.

        Args:
            resource: Resource type (e.g., 'products', 'customers', 'orders')
            resource_id: Resource ID

        Returns:
            Admin UI URL
        """
        return f"https://{self.shop_domain}/admin/{resource}/{resource_id}"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for authenticated API requests."""
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.access_token,
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make an authenticated GET request to the Shopify Admin API.

        Args:
            client: HTTP client
            url: Full API URL

        Returns:
            JSON response from API
        """
        response = await client.get(url, headers=self._get_headers(), timeout=30.0)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_retry(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Make an authenticated GET request with retry, returning full response.

        Used by _get_paginated which needs access to response headers for pagination.

        Args:
            client: HTTP client
            url: Full API URL

        Returns:
            Full httpx.Response object (for header access)
        """
        response = await client.get(url, headers=self._get_headers(), timeout=30.0)
        response.raise_for_status()
        return response

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse a Shopify datetime string into a datetime object.

        Shopify uses ISO 8601 format: 2024-01-15T14:30:00-05:00

        Args:
            value: Datetime string from Shopify API

        Returns:
            Parsed datetime or None
        """
        if not value:
            return None
        try:
            # Handle ISO format with timezone
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    async def _get_paginated(
        self, client: httpx.AsyncClient, endpoint: str, resource_key: str
    ) -> AsyncGenerator[Dict, None]:
        """Fetch paginated results from a Shopify API endpoint.

        Shopify uses Link header-based pagination. Uses _get_with_retry for
        automatic retry on rate limits and timeouts.

        Args:
            client: HTTP client
            endpoint: API endpoint (e.g., 'products.json')
            resource_key: Key in response containing the data (e.g., 'products')

        Yields:
            Individual resource dictionaries
        """
        url = f"{self._build_api_url(endpoint)}?limit={self.SHOPIFY_PAGE_LIMIT}"

        while url:
            # Use retry-protected method for rate limit handling
            response = await self._get_with_retry(client, url)
            data = response.json()

            # Yield items from this page
            for item in data.get(resource_key, []):
                yield item

            # Check for next page using Link header
            link_header = response.headers.get("link", "")
            url = None
            if link_header:
                # Parse Link header for next page
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        # Extract URL from <url>; rel="next"
                        url = link.split(";")[0].strip().strip("<>")
                        break

    async def _generate_product_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Product and ProductVariant entities from Shopify.

        GET /admin/api/{version}/products.json

        Yields:
            ShopifyProductEntity and ShopifyProductVariantEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching products...")

        async for product in self._get_paginated(client, "products.json", "products"):
            product_id = str(product["id"])
            created_time = self._parse_datetime(product.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(product.get("updated_at")) or created_time

            # Yield the product entity
            yield self._prepare_entity(
                ShopifyProductEntity(
                    entity_id=product_id,
                    breadcrumbs=[],
                    name=product.get("title", f"Product {product_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    product_id=product_id,
                    product_title=product.get("title", f"Product {product_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("products", product_id),
                    body_html=product.get("body_html"),
                    vendor=product.get("vendor"),
                    product_type=product.get("product_type"),
                    handle=product.get("handle"),
                    status=product.get("status"),
                    tags=product.get("tags"),
                    variants=product.get("variants", []),
                    options=product.get("options", []),
                    images=product.get("images", []),
                )
            )

            # Yield variant entities with breadcrumbs pointing to parent product
            for variant in product.get("variants", []):
                variant_id = str(variant["id"])
                variant_created = self._parse_datetime(variant.get("created_at")) or created_time
                variant_updated = self._parse_datetime(variant.get("updated_at")) or variant_created

                # Build variant title from options
                variant_title = variant.get("title", "Default")
                if variant_title == "Default Title":
                    variant_title = product.get("title", f"Variant {variant_id}")
                else:
                    variant_title = f"{product.get('title', '')} - {variant_title}"

                yield self._prepare_entity(
                    ShopifyProductVariantEntity(
                        entity_id=variant_id,
                        breadcrumbs=[
                            Breadcrumb(
                                entity_id=product_id,
                                name=product.get("title", f"Product {product_id}"),
                                entity_type=ShopifyProductEntity.__name__,
                            )
                        ],
                        name=variant_title,
                        created_at=variant_created,
                        updated_at=variant_updated,
                        variant_id=variant_id,
                        variant_title=variant_title,
                        created_time=variant_created,
                        updated_time=variant_updated,
                        web_url_value=self._build_admin_url("products", product_id),
                        product_id=product_id,
                        sku=variant.get("sku"),
                        price=variant.get("price"),
                        compare_at_price=variant.get("compare_at_price"),
                        inventory_quantity=variant.get("inventory_quantity"),
                        weight=variant.get("weight"),
                        weight_unit=variant.get("weight_unit"),
                        barcode=variant.get("barcode"),
                        option1=variant.get("option1"),
                        option2=variant.get("option2"),
                        option3=variant.get("option3"),
                    )
                )

    async def _generate_customer_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyCustomerEntity, None]:
        """Generate Customer entities from Shopify.

        GET /admin/api/{version}/customers.json

        Yields:
            ShopifyCustomerEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching customers...")

        async for customer in self._get_paginated(client, "customers.json", "customers"):
            customer_id = str(customer["id"])
            created_time = self._parse_datetime(customer.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(customer.get("updated_at")) or created_time

            # Build customer name
            first_name = customer.get("first_name", "")
            last_name = customer.get("last_name", "")
            email = customer.get("email", "")

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

            yield self._prepare_entity(
                ShopifyCustomerEntity(
                    entity_id=customer_id,
                    breadcrumbs=[],
                    name=customer_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    customer_id=customer_id,
                    customer_name=customer_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("customers", customer_id),
                    email=email or None,
                    phone=customer.get("phone"),
                    first_name=first_name or None,
                    last_name=last_name or None,
                    verified_email=customer.get("verified_email", False),
                    accepts_marketing=customer.get("accepts_marketing", False),
                    orders_count=customer.get("orders_count", 0),
                    total_spent=customer.get("total_spent"),
                    state=customer.get("state"),
                    currency=customer.get("currency"),
                    tags=customer.get("tags"),
                    note=customer.get("note"),
                    default_address=customer.get("default_address"),
                )
            )

    async def _generate_order_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyOrderEntity, None]:
        """Generate Order entities from Shopify.

        GET /admin/api/{version}/orders.json?status=any

        Yields:
            ShopifyOrderEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching orders...")

        # Fetch all orders including closed/cancelled
        async for order in self._get_paginated(client, "orders.json?status=any", "orders"):
            order_id = str(order["id"])
            created_time = self._parse_datetime(order.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(order.get("updated_at")) or created_time

            # Order name is typically like "#1001"
            order_name = order.get("name", f"Order {order_id}")

            # Build breadcrumbs to customer if present
            breadcrumbs: List[Breadcrumb] = []
            customer = order.get("customer")
            if customer:
                customer_id = str(customer.get("id", ""))
                if customer_id:
                    customer_name = (
                        f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    )
                    if not customer_name:
                        customer_name = customer.get("email", f"Customer {customer_id}")
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=customer_name,
                            entity_type=ShopifyCustomerEntity.__name__,
                        )
                    )

            yield self._prepare_entity(
                ShopifyOrderEntity(
                    entity_id=order_id,
                    breadcrumbs=breadcrumbs,
                    name=order_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    order_id=order_id,
                    order_name=order_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("orders", order_id),
                    order_number=order.get("order_number"),
                    email=order.get("email"),
                    phone=order.get("phone"),
                    total_price=order.get("total_price"),
                    subtotal_price=order.get("subtotal_price"),
                    total_tax=order.get("total_tax"),
                    total_discounts=order.get("total_discounts"),
                    currency=order.get("currency"),
                    financial_status=order.get("financial_status"),
                    fulfillment_status=order.get("fulfillment_status"),
                    customer_id=str(customer.get("id")) if customer else None,
                    line_items=order.get("line_items", []),
                    shipping_address=order.get("shipping_address"),
                    billing_address=order.get("billing_address"),
                    tags=order.get("tags"),
                    note=order.get("note"),
                    cancelled_at=self._parse_datetime(order.get("cancelled_at")),
                    cancel_reason=order.get("cancel_reason"),
                )
            )

    async def _generate_draft_order_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyDraftOrderEntity, None]:
        """Generate Draft Order entities from Shopify.

        GET /admin/api/{version}/draft_orders.json

        Draft orders are merchant-created orders that haven't been completed yet.

        Yields:
            ShopifyDraftOrderEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching draft orders...")

        async for draft_order in self._get_paginated(client, "draft_orders.json", "draft_orders"):
            draft_order_id = str(draft_order["id"])
            created_time = self._parse_datetime(draft_order.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(draft_order.get("updated_at")) or created_time

            # Draft order name is typically like "#D1"
            draft_order_name = draft_order.get("name", f"Draft Order {draft_order_id}")

            # Build breadcrumbs to customer if present
            breadcrumbs: List[Breadcrumb] = []
            customer = draft_order.get("customer")
            if customer:
                customer_id = str(customer.get("id", ""))
                if customer_id:
                    customer_name = (
                        f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    )
                    if not customer_name:
                        customer_name = customer.get("email", f"Customer {customer_id}")
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=customer_id,
                            name=customer_name,
                            entity_type=ShopifyCustomerEntity.__name__,
                        )
                    )

            yield self._prepare_entity(
                ShopifyDraftOrderEntity(
                    entity_id=draft_order_id,
                    breadcrumbs=breadcrumbs,
                    name=draft_order_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    draft_order_id=draft_order_id,
                    draft_order_name=draft_order_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("draft_orders", draft_order_id),
                    email=draft_order.get("email"),
                    status=draft_order.get("status"),
                    total_price=draft_order.get("total_price"),
                    subtotal_price=draft_order.get("subtotal_price"),
                    total_tax=draft_order.get("total_tax"),
                    currency=draft_order.get("currency"),
                    customer_id=str(customer.get("id")) if customer else None,
                    line_items=draft_order.get("line_items", []),
                    shipping_address=draft_order.get("shipping_address"),
                    billing_address=draft_order.get("billing_address"),
                    tags=draft_order.get("tags"),
                    note=draft_order.get("note"),
                    invoice_sent_at=self._parse_datetime(draft_order.get("invoice_sent_at")),
                    completed_at=self._parse_datetime(draft_order.get("completed_at")),
                )
            )

    async def _generate_collection_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyCollectionEntity, None]:
        """Generate Collection entities from Shopify (both Custom and Smart).

        GET /admin/api/{version}/custom_collections.json
        GET /admin/api/{version}/smart_collections.json

        Yields:
            ShopifyCollectionEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching collections...")

        # Fetch custom collections
        async for collection in self._get_paginated(
            client, "custom_collections.json", "custom_collections"
        ):
            collection_id = str(collection["id"])
            created_time = self._parse_datetime(collection.get("published_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(collection.get("updated_at")) or created_time

            yield self._prepare_entity(
                ShopifyCollectionEntity(
                    entity_id=collection_id,
                    breadcrumbs=[],
                    name=collection.get("title", f"Collection {collection_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    collection_id=collection_id,
                    collection_title=collection.get("title", f"Collection {collection_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("collections", collection_id),
                    handle=collection.get("handle"),
                    body_html=collection.get("body_html"),
                    published_at=self._parse_datetime(collection.get("published_at")),
                    published_scope=collection.get("published_scope"),
                    sort_order=collection.get("sort_order"),
                    collection_type="custom",
                    disjunctive=None,
                    rules=[],
                    products_count=None,
                )
            )

        # Fetch smart collections
        async for collection in self._get_paginated(
            client, "smart_collections.json", "smart_collections"
        ):
            collection_id = str(collection["id"])
            created_time = self._parse_datetime(collection.get("published_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(collection.get("updated_at")) or created_time

            yield self._prepare_entity(
                ShopifyCollectionEntity(
                    entity_id=collection_id,
                    breadcrumbs=[],
                    name=collection.get("title", f"Collection {collection_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    collection_id=collection_id,
                    collection_title=collection.get("title", f"Collection {collection_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("collections", collection_id),
                    handle=collection.get("handle"),
                    body_html=collection.get("body_html"),
                    published_at=self._parse_datetime(collection.get("published_at")),
                    published_scope=collection.get("published_scope"),
                    sort_order=collection.get("sort_order"),
                    collection_type="smart",
                    disjunctive=collection.get("disjunctive"),
                    rules=collection.get("rules", []),
                    products_count=None,
                )
            )

    async def _generate_location_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyLocationEntity, None]:
        """Generate Location entities from Shopify.

        GET /admin/api/{version}/locations.json

        Yields:
            ShopifyLocationEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching locations...")

        async for location in self._get_paginated(client, "locations.json", "locations"):
            location_id = str(location["id"])
            created_time = self._parse_datetime(location.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(location.get("updated_at")) or created_time

            yield self._prepare_entity(
                ShopifyLocationEntity(
                    entity_id=location_id,
                    breadcrumbs=[],
                    name=location.get("name", f"Location {location_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    location_id=location_id,
                    location_name=location.get("name", f"Location {location_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("settings/locations", location_id),
                    address1=location.get("address1"),
                    address2=location.get("address2"),
                    city=location.get("city"),
                    province=location.get("province"),
                    province_code=location.get("province_code"),
                    country=location.get("country"),
                    country_code=location.get("country_code"),
                    zip=location.get("zip"),
                    phone=location.get("phone"),
                    active=location.get("active", True),
                    legacy=location.get("legacy", False),
                    localized_country_name=location.get("localized_country_name"),
                    localized_province_name=location.get("localized_province_name"),
                )
            )

    async def _generate_inventory_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Inventory Item and Level entities from Shopify.

        GET /admin/api/{version}/inventory_items.json
        GET /admin/api/{version}/inventory_levels.json

        Yields:
            ShopifyInventoryItemEntity and ShopifyInventoryLevelEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching inventory...")

        # First get all locations for inventory levels
        locations: Dict[str, str] = {}
        async for location in self._get_paginated(client, "locations.json", "locations"):
            locations[str(location["id"])] = location.get("name", f"Location {location['id']}")

        # Get inventory items (these are linked to product variants)
        # We need to get them via products since there's no direct list endpoint
        inventory_items_seen: set = set()

        async for product in self._get_paginated(client, "products.json", "products"):
            for variant in product.get("variants", []):
                inventory_item_id = str(variant.get("inventory_item_id", ""))
                if inventory_item_id and inventory_item_id not in inventory_items_seen:
                    inventory_items_seen.add(inventory_item_id)

                    # Fetch full inventory item details
                    try:
                        url = self._build_api_url(f"inventory_items/{inventory_item_id}.json")
                        data = await self._get_with_auth(client, url)
                        item = data.get("inventory_item", {})

                        created_time = (
                            self._parse_datetime(item.get("created_at")) or datetime.utcnow()
                        )
                        updated_time = self._parse_datetime(item.get("updated_at")) or created_time

                        yield self._prepare_entity(
                            ShopifyInventoryItemEntity(
                                entity_id=inventory_item_id,
                                breadcrumbs=[
                                    Breadcrumb(
                                        entity_id=str(variant["id"]),
                                        name=variant.get("title", f"Variant {variant['id']}"),
                                        entity_type=ShopifyProductVariantEntity.__name__,
                                    )
                                ],
                                name=item.get("sku") or f"Inventory Item {inventory_item_id}",
                                created_at=created_time,
                                updated_at=updated_time,
                                inventory_item_id=inventory_item_id,
                                inventory_item_name=item.get("sku")
                                or f"Inventory Item {inventory_item_id}",
                                created_time=created_time,
                                updated_time=updated_time,
                                web_url_value=self._build_admin_url(
                                    "products/inventory", inventory_item_id
                                ),
                                sku=item.get("sku"),
                                cost=item.get("cost"),
                                tracked=item.get("tracked", False),
                                requires_shipping=item.get("requires_shipping", False),
                                country_code_of_origin=item.get("country_code_of_origin"),
                                province_code_of_origin=item.get("province_code_of_origin"),
                                harmonized_system_code=item.get("harmonized_system_code"),
                            )
                        )

                        # Fetch inventory levels for this item
                        levels_url = self._build_api_url(
                            f"inventory_levels.json?inventory_item_ids={inventory_item_id}"
                        )
                        levels_data = await self._get_with_auth(client, levels_url)

                        for level in levels_data.get("inventory_levels", []):
                            level_location_id = str(level.get("location_id", ""))
                            composite_id = f"{inventory_item_id}-{level_location_id}"
                            location_name = locations.get(
                                level_location_id, f"Location {level_location_id}"
                            )

                            yield self._prepare_entity(
                                ShopifyInventoryLevelEntity(
                                    entity_id=composite_id,
                                    breadcrumbs=[
                                        Breadcrumb(
                                            entity_id=inventory_item_id,
                                            name=item.get("sku") or f"Item {inventory_item_id}",
                                            entity_type=ShopifyInventoryItemEntity.__name__,
                                        ),
                                        Breadcrumb(
                                            entity_id=level_location_id,
                                            name=location_name,
                                            entity_type=ShopifyLocationEntity.__name__,
                                        ),
                                    ],
                                    name=f"{item.get('sku', 'Item')} @ {location_name}",
                                    created_at=updated_time,
                                    updated_at=updated_time,
                                    inventory_level_id=composite_id,
                                    inventory_level_name=(
                                        f"{item.get('sku', 'Item')} @ {location_name}"
                                    ),
                                    created_time=updated_time,
                                    updated_time=updated_time,
                                    web_url_value=self._build_admin_url(
                                        "products/inventory", inventory_item_id
                                    ),
                                    inventory_item_id=inventory_item_id,
                                    location_id=level_location_id,
                                    available=level.get("available"),
                                )
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to fetch inventory item {inventory_item_id}: {e}"
                        )

    async def _generate_fulfillment_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyFulfillmentEntity, None]:
        """Generate Fulfillment entities from Shopify (nested under orders).

        GET /admin/api/{version}/orders/{order_id}/fulfillments.json

        Yields:
            ShopifyFulfillmentEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching fulfillments...")

        async for order in self._get_paginated(client, "orders.json?status=any", "orders"):
            order_id = str(order["id"])
            order_name = order.get("name", f"Order {order_id}")

            for fulfillment in order.get("fulfillments", []):
                fulfillment_id = str(fulfillment["id"])
                created_time = (
                    self._parse_datetime(fulfillment.get("created_at")) or datetime.utcnow()
                )
                updated_time = self._parse_datetime(fulfillment.get("updated_at")) or created_time

                yield self._prepare_entity(
                    ShopifyFulfillmentEntity(
                        entity_id=fulfillment_id,
                        breadcrumbs=[
                            Breadcrumb(
                                entity_id=order_id,
                                name=order_name,
                                entity_type=ShopifyOrderEntity.__name__,
                            )
                        ],
                        name=f"Fulfillment {fulfillment_id} for {order_name}",
                        created_at=created_time,
                        updated_at=updated_time,
                        fulfillment_id=fulfillment_id,
                        fulfillment_name=f"Fulfillment {fulfillment_id} for {order_name}",
                        created_time=created_time,
                        updated_time=updated_time,
                        web_url_value=self._build_admin_url("orders", order_id),
                        order_id=order_id,
                        status=fulfillment.get("status"),
                        tracking_company=fulfillment.get("tracking_company"),
                        tracking_number=fulfillment.get("tracking_number"),
                        tracking_numbers=fulfillment.get("tracking_numbers", []),
                        tracking_url=fulfillment.get("tracking_url"),
                        tracking_urls=fulfillment.get("tracking_urls", []),
                        location_id=str(fulfillment.get("location_id"))
                        if fulfillment.get("location_id")
                        else None,
                        line_items=fulfillment.get("line_items", []),
                        shipment_status=fulfillment.get("shipment_status"),
                    )
                )

    async def _generate_gift_card_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyGiftCardEntity, None]:
        """Generate Gift Card entities from Shopify.

        GET /admin/api/{version}/gift_cards.json

        Yields:
            ShopifyGiftCardEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching gift cards...")

        async for gift_card in self._get_paginated(client, "gift_cards.json", "gift_cards"):
            # IMPORTANT:Skip disabled gift cards (they can't be deleted in Shopify, only disabled)
            if gift_card.get("disabled_at"):
                continue

            gift_card_id = str(gift_card["id"])
            created_time = self._parse_datetime(gift_card.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(gift_card.get("updated_at")) or created_time

            last_chars = gift_card.get("last_characters", "")
            gift_card_name = (
                f"Gift Card ****{last_chars}" if last_chars else f"Gift Card {gift_card_id}"
            )

            yield self._prepare_entity(
                ShopifyGiftCardEntity(
                    entity_id=gift_card_id,
                    breadcrumbs=[],
                    name=gift_card_name,
                    created_at=created_time,
                    updated_at=updated_time,
                    gift_card_id=gift_card_id,
                    gift_card_name=gift_card_name,
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("gift_cards", gift_card_id),
                    initial_value=gift_card.get("initial_value"),
                    balance=gift_card.get("balance"),
                    currency=gift_card.get("currency"),
                    code=gift_card.get("code"),
                    last_characters=last_chars,
                    disabled_at=self._parse_datetime(gift_card.get("disabled_at")),
                    expires_on=gift_card.get("expires_on"),
                    note=gift_card.get("note"),
                    customer_id=str(gift_card.get("customer_id"))
                    if gift_card.get("customer_id")
                    else None,
                    order_id=str(gift_card.get("order_id")) if gift_card.get("order_id") else None,
                )
            )

    async def _generate_discount_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyDiscountEntity, None]:
        """Generate Discount (Price Rule) entities from Shopify.

        GET /admin/api/{version}/price_rules.json

        Yields:
            ShopifyDiscountEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching discounts/price rules...")

        async for price_rule in self._get_paginated(client, "price_rules.json", "price_rules"):
            discount_id = str(price_rule["id"])
            created_time = self._parse_datetime(price_rule.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(price_rule.get("updated_at")) or created_time

            yield self._prepare_entity(
                ShopifyDiscountEntity(
                    entity_id=discount_id,
                    breadcrumbs=[],
                    name=price_rule.get("title", f"Discount {discount_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    discount_id=discount_id,
                    discount_title=price_rule.get("title", f"Discount {discount_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("discounts", discount_id),
                    value_type=price_rule.get("value_type"),
                    value=price_rule.get("value"),
                    target_type=price_rule.get("target_type"),
                    target_selection=price_rule.get("target_selection"),
                    allocation_method=price_rule.get("allocation_method"),
                    once_per_customer=price_rule.get("once_per_customer", False),
                    usage_limit=price_rule.get("usage_limit"),
                    starts_at=self._parse_datetime(price_rule.get("starts_at")),
                    ends_at=self._parse_datetime(price_rule.get("ends_at")),
                    prerequisite_subtotal_range=price_rule.get("prerequisite_subtotal_range"),
                    prerequisite_quantity_range=price_rule.get("prerequisite_quantity_range"),
                )
            )

    async def _generate_metaobject_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyMetaobjectEntity, None]:
        """Generate Metaobject entities from Shopify.

        GET /admin/api/{version}/metaobjects.json

        Yields:
            ShopifyMetaobjectEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching metaobjects...")

        # First get all metaobject definitions to know what types exist
        try:
            definitions_url = self._build_api_url("metaobject_definitions.json")
            definitions_data = await self._get_with_auth(client, definitions_url)

            for definition in definitions_data.get("metaobject_definitions", []):
                def_type = definition.get("type", "")
                if not def_type:
                    continue

                # Fetch metaobjects of this type
                metaobjects_url = self._build_api_url(f"metaobjects.json?type={def_type}")
                try:
                    metaobjects_data = await self._get_with_auth(client, metaobjects_url)

                    for metaobject in metaobjects_data.get("metaobjects", []):
                        metaobject_id = str(metaobject["id"])
                        created_time = (
                            self._parse_datetime(metaobject.get("created_at")) or datetime.utcnow()
                        )
                        updated_time = (
                            self._parse_datetime(metaobject.get("updated_at")) or created_time
                        )

                        handle = metaobject.get("handle", "")
                        display_name = handle or f"Metaobject {metaobject_id}"

                        yield self._prepare_entity(
                            ShopifyMetaobjectEntity(
                                entity_id=metaobject_id,
                                breadcrumbs=[],
                                name=display_name,
                                created_at=created_time,
                                updated_at=updated_time,
                                metaobject_id=metaobject_id,
                                metaobject_name=display_name,
                                created_time=created_time,
                                updated_time=updated_time,
                                web_url_value=self._build_admin_url(
                                    "content/entries", metaobject_id
                                ),
                                type=def_type,
                                handle=handle,
                                fields=metaobject.get("fields", []),
                                capabilities=metaobject.get("capabilities"),
                            )
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to fetch metaobjects of type {def_type}: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to fetch metaobject definitions: {e}")

    async def _generate_file_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyFileEntity, None]:
        """Generate File entities from Shopify using GraphQL.

        The Files API requires GraphQL, not REST.

        Yields:
            ShopifyFileEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching files via GraphQL...")

        graphql_url = f"https://{self.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"

        query = """
        query GetFiles($first: Int!, $after: String) {
          files(first: $first, after: $after) {
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                ... on GenericFile {
                  id
                  alt
                  createdAt
                  updatedAt
                  fileStatus
                  originalFileSize
                  url
                }
                ... on MediaImage {
                  id
                  alt
                  createdAt
                  updatedAt
                  fileStatus
                  image {
                    url
                    width
                    height
                  }
                }
                ... on Video {
                  id
                  alt
                  createdAt
                  updatedAt
                  fileStatus
                  originalSource {
                    url
                    fileSize
                  }
                }
              }
            }
          }
        }
        """

        has_next_page = True
        cursor = None

        while has_next_page:
            variables = {"first": 50}
            if cursor:
                variables["after"] = cursor

            try:
                response = await client.post(
                    graphql_url,
                    headers=self._get_headers(),
                    json={"query": query, "variables": variables},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if "errors" in result:
                    self.logger.warning(f"GraphQL errors fetching files: {result['errors']}")
                    break

                files_data = result.get("data", {}).get("files", {})
                page_info = files_data.get("pageInfo", {})
                edges = files_data.get("edges", [])

                for edge in edges:
                    file_node = edge.get("node", {})
                    file_gid = file_node.get("id", "")
                    file_id = file_gid.split("/")[-1] if "/" in file_gid else file_gid

                    created_time = (
                        self._parse_datetime(file_node.get("createdAt")) or datetime.utcnow()
                    )
                    updated_time = self._parse_datetime(file_node.get("updatedAt")) or created_time

                    # Determine file type, URL, and size based on file kind
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

                    yield self._prepare_entity(
                        ShopifyFileEntity(
                            entity_id=file_id,
                            breadcrumbs=[],
                            name=file_name,
                            created_at=created_time,
                            updated_at=updated_time,
                            # FileEntity required fields
                            url=file_url,
                            size=file_size,
                            file_type=file_type,
                            # Shopify-specific fields
                            file_id=file_id,
                            file_name=file_name,
                            created_time=created_time,
                            updated_time=updated_time,
                            web_url_value=self._build_admin_url("content/files", file_id),
                            alt=file_node.get("alt"),
                            file_status=file_node.get("fileStatus"),
                            preview_image_url=file_url or None,
                        )
                    )

                has_next_page = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

            except Exception as e:
                self.logger.warning(f"Failed to fetch files via GraphQL: {e}")
                break

    async def _generate_theme_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ShopifyThemeEntity, None]:  # noqa C901
        """Generate Theme entities from Shopify.

        GET /admin/api/{version}/themes.json

        Yields:
            ShopifyThemeEntity objects
        """
        self.logger.info("🔍 [SHOPIFY] Fetching themes...")

        async for theme in self._get_paginated(client, "themes.json", "themes"):
            theme_id = str(theme["id"])
            created_time = self._parse_datetime(theme.get("created_at")) or datetime.utcnow()
            updated_time = self._parse_datetime(theme.get("updated_at")) or created_time

            yield self._prepare_entity(
                ShopifyThemeEntity(
                    entity_id=theme_id,
                    breadcrumbs=[],
                    name=theme.get("name", f"Theme {theme_id}"),
                    created_at=created_time,
                    updated_at=updated_time,
                    theme_id=theme_id,
                    theme_name=theme.get("name", f"Theme {theme_id}"),
                    created_time=created_time,
                    updated_time=updated_time,
                    web_url_value=self._build_admin_url("themes", theme_id),
                    role=theme.get("role"),
                    theme_store_id=theme.get("theme_store_id"),
                    previewable=theme.get("previewable", True),
                    processing=theme.get("processing", False),
                )
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa C901
        """Generate all Shopify entities.

        Yields:
            All Shopify entities: Products, Variants, Customers, Orders, Draft Orders,
            Collections, Locations, Inventory, Fulfillments, Gift Cards, Discounts,
            Metaobjects, Files, and Themes.
        """
        async with self.http_client(timeout=30.0) as client:
            # 1) Products and variants
            async for entity in self._generate_product_entities(client):
                yield entity

            # 2) Customers
            async for entity in self._generate_customer_entities(client):
                yield entity

            # 3) Orders
            async for entity in self._generate_order_entities(client):
                yield entity

            # 4) Draft Orders
            async for entity in self._generate_draft_order_entities(client):
                yield entity

            # 5) Collections
            async for entity in self._generate_collection_entities(client):
                yield entity

            # 6) Locations
            async for entity in self._generate_location_entities(client):
                yield entity

            # 7) Inventory Items and Levels
            async for entity in self._generate_inventory_entities(client):
                yield entity

            # 8) Fulfillments
            async for entity in self._generate_fulfillment_entities(client):
                yield entity

            # 9) Gift Cards
            async for entity in self._generate_gift_card_entities(client):
                yield entity

            # 10) Discounts (Price Rules)
            async for entity in self._generate_discount_entities(client):
                yield entity

            # 12) Metaobjects
            async for entity in self._generate_metaobject_entities(client):
                yield entity

            # 13) Files (via GraphQL)
            async for entity in self._generate_file_entities(client):
                yield entity

            # 14) Themes
            async for entity in self._generate_theme_entities(client):
                yield entity

    async def validate(self) -> bool:
        """Verify Shopify API access by pinging the shop endpoint.

        Returns:
            True if the credentials are valid and the shop is accessible
        """
        if not self.client_id or not self.client_secret or not self.shop_domain:
            self.logger.error(
                "Shopify validation failed: missing client_id, client_secret, or shop_domain"
            )
            return False

        try:
            # Get access token if not already obtained
            if not self.access_token:
                self.access_token = await self._get_access_token()

            async with self.http_client(timeout=10.0) as client:
                # Ping the shop endpoint to verify credentials
                url = self._build_api_url("shop.json")
                result = await self._get_with_auth(client, url)
                shop_name = result.get("shop", {}).get("name", "Unknown")
                self.logger.info(f"✅ [SHOPIFY] Connected to store: {shop_name}")
                return True
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Shopify validation failed: HTTP {e.response.status_code} - "
                f"{e.response.text[:200]}"
            )
            return False
        except ValueError as e:
            self.logger.error(f"Shopify validation failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Shopify validation: {e}")
            return False
