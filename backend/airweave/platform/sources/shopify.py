"""Shopify Admin GraphQL API source implementation.

This source connects to Shopify stores via the Admin GraphQL API and syncs
core business data including products, orders, customers, collections, and inventory.
"""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import ShopifyAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.shopify import (
    ShopifyCollectionEntity,
    ShopifyCustomerEntity,
    ShopifyDraftOrderEntity,
    ShopifyFulfillmentOrderEntity,
    ShopifyInventoryItemEntity,
    ShopifyLocationEntity,
    ShopifyOrderEntity,
    ShopifyProductEntity,
    ShopifyShopEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

# Resource configurations with query patterns
RESOURCE_CONFIGS = {
    "Product": {
        "query_name": "products",
        "entity_class": ShopifyProductEntity,
        "fields": """
            id
            title
            description
            descriptionHtml
            handle
            status
            createdAt
            updatedAt
            publishedAt
            vendor
            productType
            tags
            totalInventory
            tracksInventory
            onlineStoreUrl
            featuredImage {
                url
                altText
            }
            priceRangeV2 {
                minVariantPrice {
                    amount
                    currencyCode
                }
                maxVariantPrice {
                    amount
                    currencyCode
                }
            }
        """,
        "name_field": "title",
    },
    "Order": {
        "query_name": "orders",
        "entity_class": ShopifyOrderEntity,
        "fields": """
            id
            name
            email
            phone
            createdAt
            updatedAt
            cancelledAt
            closedAt
            processedAt
            displayFulfillmentStatus
            displayFinancialStatus
            fullyPaid
            confirmed
            cancelled
            test
            tags
            note
            customAttributes {
                key
                value
            }
            totalPriceSet {
                shopMoney {
                    amount
                    currencyCode
                }
            }
            subtotalPriceSet {
                shopMoney {
                    amount
                    currencyCode
                }
            }
            totalTaxSet {
                shopMoney {
                    amount
                    currencyCode
                }
            }
            totalShippingPriceSet {
                shopMoney {
                    amount
                    currencyCode
                }
            }
            customer {
                id
                email
                displayName
            }
        """,
        "name_field": "name",
    },
    "Customer": {
        "query_name": "customers",
        "entity_class": ShopifyCustomerEntity,
        "fields": """
            id
            firstName
            lastName
            displayName
            email
            phone
            createdAt
            updatedAt
            state
            verifiedEmail
            taxExempt
            tags
            note
            ordersCount
            totalSpentV2 {
                amount
                currencyCode
            }
            averageOrderAmountV2 {
                amount
                currencyCode
            }
            lifetimeDuration
            addresses {
                id
                address1
                address2
                city
                province
                country
                zip
                phone
                company
            }
        """,
        "name_field": "displayName",
    },
    "Collection": {
        "query_name": "collections",
        "entity_class": ShopifyCollectionEntity,
        "fields": """
            id
            title
            description
            descriptionHtml
            handle
            sortOrder
            templateSuffix
            updatedAt
            productsCount
            image {
                url
                altText
            }
            ruleSet {
                appliedDisjunctively
                rules {
                    column
                    relation
                    condition
                }
            }
        """,
        "name_field": "title",
    },
    "DraftOrder": {
        "query_name": "draftOrders",
        "entity_class": ShopifyDraftOrderEntity,
        "fields": """
            id
            name
            email
            phone
            createdAt
            updatedAt
            completedAt
            status
            tags
            note
            invoiceUrl
            totalPrice
            subtotalPrice
            totalTax
            totalShippingPrice
            currencyCode
            customer {
                id
                email
                displayName
            }
        """,
        "name_field": "name",
    },
    "InventoryItem": {
        "query_name": "inventoryItems",
        "entity_class": ShopifyInventoryItemEntity,
        "fields": """
            id
            createdAt
            updatedAt
            sku
            tracked
            requiresShipping
            duplicateSkuCount
            countryCodeOfOrigin
            provinceCodeOfOrigin
            harmonizedSystemCode
            unitCost {
                amount
                currencyCode
            }
        """,
        "name_field": "sku",
    },
    "Location": {
        "query_name": "locations",
        "entity_class": ShopifyLocationEntity,
        "fields": """
            id
            name
            address {
                address1
                address2
                city
                province
                country
                zip
                phone
            }
            isActive
            fulfillsOnlineOrders
            hasActiveInventory
            shipsInventory
            createdAt
            updatedAt
        """,
        "name_field": "name",
    },
    "FulfillmentOrder": {
        "query_name": "fulfillmentOrders",
        "entity_class": ShopifyFulfillmentOrderEntity,
        "fields": """
            id
            createdAt
            updatedAt
            status
            requestStatus
            destination {
                firstName
                lastName
                address1
                address2
                city
                province
                country
                zip
                phone
            }
            deliveryMethod {
                methodType
            }
            assignedLocation {
                name
                address1
            }
        """,
        "name_field": "id",
    },
}


@source(
    name="Shopify",
    short_name="shopify",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class="ShopifyAuthConfig",
    config_class="ShopifyConfig",
    labels=["E-commerce", "Sales"],
    rate_limit_level=RateLimitLevel.ORG,
)
class ShopifySource(BaseSource):
    """Shopify Admin GraphQL API connector.

    Syncs core business data from Shopify stores including products, orders,
    customers, collections, inventory, and fulfillment information.
    """

    def __init__(self):
        """Initialize the Shopify source."""
        super().__init__()
        self.shop_breadcrumb: Optional[Breadcrumb] = None
        self.shop_name: Optional[str] = None
        self.api_version: str = "2025-01"
        self.resources: List[str] = list(RESOURCE_CONFIGS.keys())

    @classmethod
    async def create(
        cls, credentials: ShopifyAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "ShopifySource":
        """Create a new Shopify source instance.

        Args:
            credentials: ShopifyAuthConfig instance containing the access token
            config: Optional configuration dict containing:
                - shop_name: The Shopify store name (required)
                - api_version: API version (default: "2025-01")
                - resources: List of resources to sync
        """
        instance = cls()
        instance.access_token = credentials.access_token

        if config:
            # shop_name should be passed in config from source config
            instance.shop_name = config.get("shop_name")
            instance.api_version = config.get("api_version", "2025-01")
            instance.resources = config.get("resources") or list(RESOURCE_CONFIGS.keys())

        if not instance.shop_name:
            raise ValueError("shop_name is required in config")

        return instance

    def _get_api_url(self) -> str:
        """Construct the GraphQL API URL."""
        shop_name = self.shop_name

        # Handle both formats: 'my-store' or 'my-store.myshopify.com'
        if ".myshopify.com" not in shop_name:
            shop_name = f"{shop_name}.myshopify.com"

        return f"https://{shop_name}/admin/api/{self.api_version}/graphql.json"

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _execute_graphql(
        self, client: httpx.AsyncClient, query: str, variables: Optional[Dict] = None
    ) -> Dict:
        """Execute a GraphQL query against the Shopify API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.

        Args:
            client: HTTP client to use for the request
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Response data dictionary
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        url = self._get_api_url()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token,
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                raise ValueError(f"GraphQL errors: {data['errors']}")

            return data.get("data", {})

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Shopify API: {e.response.status_code}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Shopify API: {str(e)}")
            raise

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _extract_nested_value(self, obj: Dict, path: str) -> Any:
        """Extract a nested value from a dictionary using dot notation."""
        parts = path.split(".")
        current = obj
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    async def _get_shop_info(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Get shop information."""
        query = """
        query {
          shop {
            id
            name
            email
            myshopifyDomain
            currencyCode
            ianaTimezone
            contactEmail
            shopOwnerName
            billingAddress {
              country
            }
          }
        }
        """
        result = await self._execute_graphql(client, query)
        return result.get("shop", {})

    async def _fetch_resource_page(
        self,
        client: httpx.AsyncClient,
        resource_type: str,
        cursor: Optional[str] = None,
        page_size: int = 50,
    ) -> Dict:
        """Fetch a page of resources using cursor-based pagination.

        Args:
            client: HTTP client to use for the request
            resource_type: Name of the resource to fetch
            cursor: Cursor for pagination (None for first page)
            page_size: Number of items per page

        Returns:
            Query result with edges and pageInfo
        """
        config = RESOURCE_CONFIGS[resource_type]
        query_name = config["query_name"]
        fields = config["fields"]

        cursor_arg = f', after: "{cursor}"' if cursor else ""

        query = f"""
        query {{
          {query_name}(first: {page_size}{cursor_arg}) {{
            edges {{
              cursor
              node {{
                {fields}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """

        result = await self._execute_graphql(client, query)
        return result.get(query_name, {})

    def _generate_entity_id(self, resource_type: str, node_data: Dict) -> str:
        """Generate a unique entity ID."""
        shopify_id = node_data.get("id", "")
        return f"shopify:{resource_type.lower()}:{shopify_id}"

    async def _process_node_to_entity(
        self,
        node_data: Dict,
        resource_type: str,
    ) -> BaseEntity:
        """Convert a GraphQL node to an entity."""
        config = RESOURCE_CONFIGS[resource_type]
        entity_class = config["entity_class"]
        name_field = config.get("name_field", "id")

        # Generate entity ID
        entity_id = self._generate_entity_id(resource_type, node_data)

        # Determine entity name
        entity_name = str(node_data.get(name_field) or node_data.get("id", "unknown"))

        # Extract timestamps
        created_at = self._parse_datetime(node_data.get("createdAt"))
        updated_at = self._parse_datetime(node_data.get("updatedAt"))

        # Build entity-specific fields based on resource type
        kwargs = {}

        if resource_type == "Product":
            kwargs = {
                "description": node_data.get("description"),
                "description_html": node_data.get("descriptionHtml"),
                "handle": node_data.get("handle"),
                "status": node_data.get("status"),
                "published_at": self._parse_datetime(node_data.get("publishedAt")),
                "vendor": node_data.get("vendor"),
                "product_type": node_data.get("productType"),
                "tags": json.dumps(node_data.get("tags", [])),
                "total_inventory": node_data.get("totalInventory"),
                "tracks_inventory": node_data.get("tracksInventory"),
                "online_store_url": node_data.get("onlineStoreUrl"),
                "featured_image_url": self._extract_nested_value(node_data, "featuredImage.url"),
                "price_range_min": self._extract_nested_value(
                    node_data, "priceRangeV2.minVariantPrice.amount"
                ),
                "price_range_max": self._extract_nested_value(
                    node_data, "priceRangeV2.maxVariantPrice.amount"
                ),
                "currency_code": self._extract_nested_value(
                    node_data, "priceRangeV2.minVariantPrice.currencyCode"
                ),
            }

        elif resource_type == "Order":
            kwargs = {
                "email": node_data.get("email"),
                "phone": node_data.get("phone"),
                "cancelled_at": self._parse_datetime(node_data.get("cancelledAt")),
                "closed_at": self._parse_datetime(node_data.get("closedAt")),
                "processed_at": self._parse_datetime(node_data.get("processedAt")),
                "fulfillment_status": node_data.get("displayFulfillmentStatus"),
                "financial_status": node_data.get("displayFinancialStatus"),
                "fully_paid": node_data.get("fullyPaid"),
                "confirmed": node_data.get("confirmed"),
                "cancelled": node_data.get("cancelled"),
                "test": node_data.get("test"),
                "tags": json.dumps(node_data.get("tags", [])),
                "note": node_data.get("note"),
                "total_price": self._extract_nested_value(
                    node_data, "totalPriceSet.shopMoney.amount"
                ),
                "subtotal_price": self._extract_nested_value(
                    node_data, "subtotalPriceSet.shopMoney.amount"
                ),
                "total_tax": self._extract_nested_value(node_data, "totalTaxSet.shopMoney.amount"),
                "total_shipping_price": self._extract_nested_value(
                    node_data, "totalShippingPriceSet.shopMoney.amount"
                ),
                "currency_code": self._extract_nested_value(
                    node_data, "totalPriceSet.shopMoney.currencyCode"
                ),
                "customer_id": self._extract_nested_value(node_data, "customer.id"),
                "customer_email": self._extract_nested_value(node_data, "customer.email"),
                "customer_name": self._extract_nested_value(node_data, "customer.displayName"),
            }

        elif resource_type == "Customer":
            kwargs = {
                "first_name": node_data.get("firstName"),
                "last_name": node_data.get("lastName"),
                "email": node_data.get("email"),
                "phone": node_data.get("phone"),
                "state": node_data.get("state"),
                "verified_email": node_data.get("verifiedEmail"),
                "tax_exempt": node_data.get("taxExempt"),
                "tags": json.dumps(node_data.get("tags", [])),
                "note": node_data.get("note"),
                "orders_count": node_data.get("ordersCount"),
                "total_spent": self._extract_nested_value(node_data, "totalSpentV2.amount"),
                "average_order_amount": self._extract_nested_value(
                    node_data, "averageOrderAmountV2.amount"
                ),
                "currency_code": self._extract_nested_value(node_data, "totalSpentV2.currencyCode"),
                "lifetime_duration": node_data.get("lifetimeDuration"),
                "addresses": json.dumps(node_data.get("addresses", [])),
            }

        elif resource_type == "Collection":
            kwargs = {
                "description": node_data.get("description"),
                "description_html": node_data.get("descriptionHtml"),
                "handle": node_data.get("handle"),
                "sort_order": node_data.get("sortOrder"),
                "template_suffix": node_data.get("templateSuffix"),
                "products_count": node_data.get("productsCount"),
                "image_url": self._extract_nested_value(node_data, "image.url"),
                "rule_set": json.dumps(node_data.get("ruleSet"))
                if node_data.get("ruleSet")
                else None,
            }

        elif resource_type == "DraftOrder":
            kwargs = {
                "email": node_data.get("email"),
                "phone": node_data.get("phone"),
                "completed_at": self._parse_datetime(node_data.get("completedAt")),
                "status": node_data.get("status"),
                "tags": json.dumps(node_data.get("tags", [])),
                "note": node_data.get("note"),
                "invoice_url": node_data.get("invoiceUrl"),
                "total_price": node_data.get("totalPrice"),
                "subtotal_price": node_data.get("subtotalPrice"),
                "total_tax": node_data.get("totalTax"),
                "total_shipping_price": node_data.get("totalShippingPrice"),
                "currency_code": node_data.get("currencyCode"),
                "customer_id": self._extract_nested_value(node_data, "customer.id"),
                "customer_email": self._extract_nested_value(node_data, "customer.email"),
                "customer_name": self._extract_nested_value(node_data, "customer.displayName"),
            }

        elif resource_type == "InventoryItem":
            kwargs = {
                "sku": node_data.get("sku"),
                "tracked": node_data.get("tracked"),
                "requires_shipping": node_data.get("requiresShipping"),
                "duplicate_sku_count": node_data.get("duplicateSkuCount"),
                "country_code_of_origin": node_data.get("countryCodeOfOrigin"),
                "province_code_of_origin": node_data.get("provinceCodeOfOrigin"),
                "harmonized_system_code": node_data.get("harmonizedSystemCode"),
                "unit_cost": self._extract_nested_value(node_data, "unitCost.amount"),
                "currency_code": self._extract_nested_value(node_data, "unitCost.currencyCode"),
            }

        elif resource_type == "Location":
            kwargs = {
                "address": json.dumps(node_data.get("address"))
                if node_data.get("address")
                else None,
                "is_active": node_data.get("isActive"),
                "fulfills_online_orders": node_data.get("fulfillsOnlineOrders"),
                "has_active_inventory": node_data.get("hasActiveInventory"),
                "ships_inventory": node_data.get("shipsInventory"),
            }

        elif resource_type == "FulfillmentOrder":
            kwargs = {
                "status": node_data.get("status"),
                "request_status": node_data.get("requestStatus"),
                "destination": json.dumps(node_data.get("destination"))
                if node_data.get("destination")
                else None,
                "delivery_method_type": self._extract_nested_value(
                    node_data, "deliveryMethod.methodType"
                ),
                "assigned_location_name": self._extract_nested_value(
                    node_data, "assignedLocation.name"
                ),
                "assigned_location_address": self._extract_nested_value(
                    node_data, "assignedLocation.address1"
                ),
            }

        return entity_class(
            entity_id=entity_id,
            breadcrumbs=[self.shop_breadcrumb] if self.shop_breadcrumb else [],
            name=entity_name,
            created_at=created_at,
            updated_at=updated_at,
            **kwargs,
        )

    async def _sync_resource_type(
        self, client: httpx.AsyncClient, resource_type: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Sync all items for a specific resource type."""
        cursor = None
        page_count = 0
        total_items = 0

        while True:
            page_count += 1
            self.logger.info(
                f"Fetching {resource_type} page {page_count} "
                f"(cursor: {cursor[:20] if cursor else 'start'}...)"
            )

            try:
                result = await self._fetch_resource_page(client, resource_type, cursor)
            except Exception as e:
                self.logger.error(f"Error fetching {resource_type} page: {e}")
                break

            edges = result.get("edges", [])
            page_info = result.get("pageInfo", {})

            if not edges:
                break

            # Process nodes
            for edge in edges:
                node = edge.get("node", {})
                try:
                    entity = await self._process_node_to_entity(node, resource_type)
                    total_items += 1
                    yield entity
                except Exception as e:
                    self.logger.error(f"Error processing {resource_type} node: {e}")
                    continue

            # Check for next page
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        self.logger.info(
            f"Completed {resource_type} sync: {total_items} items across {page_count} pages"
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities by syncing all configured resource types."""
        async with self.http_client() as client:
            # Get shop info and create shop entity
            shop_info = await self._get_shop_info(client)
            shop_id = shop_info.get("id", "unknown")
            shop_name = shop_info.get("name", "Unknown Shop")

            shop_entity = ShopifyShopEntity(
                entity_id=shop_id,
                breadcrumbs=[],
                name=shop_name,
                created_at=None,
                updated_at=None,
                email=shop_info.get("email") or shop_info.get("contactEmail"),
                domain=shop_info.get("myshopifyDomain"),
                currency_code=shop_info.get("currencyCode"),
                timezone=shop_info.get("ianaTimezone"),
                shop_owner=shop_info.get("shopOwnerName"),
                country_name=self._extract_nested_value(shop_info, "billingAddress.country"),
            )

            self.shop_breadcrumb = Breadcrumb(entity_id=shop_id)
            yield shop_entity

            # Get list of resources to sync
            resources_to_sync = self.resources

            self.logger.info(
                f"Starting Shopify sync for {len(resources_to_sync)} resource types: "
                f"{', '.join(resources_to_sync)}"
            )

            # Sync each resource type
            for i, resource_type in enumerate(resources_to_sync, 1):
                if resource_type not in RESOURCE_CONFIGS:
                    self.logger.warning(f"Unknown resource type: {resource_type}, skipping")
                    continue

                self.logger.info(f"Syncing {i}/{len(resources_to_sync)}: {resource_type}")

                async for entity in self._sync_resource_type(client, resource_type):
                    yield entity

            self.logger.info(
                f"Successfully completed sync for all {len(resources_to_sync)} resource types"
            )

    async def validate(self) -> bool:
        """Verify Shopify credentials and API access."""
        try:
            async with self.http_client() as client:
                # Test with a simple shop query
                test_query = """
                query {
                  shop {
                    name
                    email
                    currencyCode
                  }
                }
                """

                result = await self._execute_graphql(client, test_query)

                if "shop" in result:
                    shop_name = result["shop"].get("name", "Unknown")
                    self.logger.info(f"Successfully connected to shop: {shop_name}")
                    return True
                else:
                    self.logger.error("Validation failed: No shop data returned")
                    return False

        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False
