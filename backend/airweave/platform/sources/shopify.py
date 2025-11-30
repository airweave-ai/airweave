"""Shopify Admin GraphQL API source implementation.

This source connects to Shopify stores via the Admin GraphQL API and dynamically
discovers available data types. It focuses on primary business resources like
products, orders, customers, collections, and inventory.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Type

from aiohttp import ClientSession, ClientTimeout

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, PolymorphicEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

# Resource configurations with query patterns
RESOURCE_CONFIGS = {
    "Product": {
        "query_name": "products",
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

    _RESERVED_ENTITY_FIELDS = {
        "entity_id",
        "breadcrumbs",
        "name",
        "created_at",
        "updated_at",
        "textual_representation",
        "airweave_system_metadata",
    }

    def __init__(self):
        """Initialize the Shopify source."""
        super().__init__()
        self.session: Optional[ClientSession] = None
        self.entity_classes: Dict[str, Type[PolymorphicEntity]] = {}
        self.field_mappings: Dict[str, Dict[str, str]] = {}

    @classmethod
    async def create(
        cls, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> "ShopifySource":
        """Create a new Shopify source instance.

        Args:
            credentials: Dictionary containing:
                - shop_name: Shopify store name (e.g., 'my-store' for my-store.myshopify.com)
                - access_token: Admin API access token
                - api_version: API version (e.g., '2025-01', defaults to '2025-01')
                - resources: Optional list of resources to sync (defaults to all)
            config: Optional configuration parameters
        """
        instance = cls()
        instance.config = (
            credentials.model_dump() if hasattr(credentials, "model_dump") else dict(credentials)
        )

        # Set defaults
        if "api_version" not in instance.config:
            instance.config["api_version"] = "2025-01"
        if "resources" not in instance.config:
            instance.config["resources"] = list(RESOURCE_CONFIGS.keys())

        return instance

    def _get_api_url(self) -> str:
        """Construct the GraphQL API URL."""
        shop_name = self.config["shop_name"]
        api_version = self.config["api_version"]

        # Handle both formats: 'my-store' or 'my-store.myshopify.com'
        if ".myshopify.com" not in shop_name:
            shop_name = f"{shop_name}.myshopify.com"

        return f"https://{shop_name}/admin/api/{api_version}/graphql.json"

    async def _create_session(self) -> ClientSession:
        """Create an aiohttp session with proper headers."""
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.config["access_token"],
        }
        timeout = ClientTimeout(total=60)
        return ClientSession(headers=headers, timeout=timeout)

    async def _execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query against the Shopify API.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Response data dictionary
        """
        if not self.session:
            self.session = await self._create_session()

        url = self._get_api_url()
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with self.session.post(url, json=payload) as response:
            if response.status == 429:
                # Handle rate limiting
                retry_after = int(response.headers.get("Retry-After", 2))
                self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                return await self._execute_graphql(query, variables)

            response.raise_for_status()
            data = await response.json()

            if "errors" in data:
                raise ValueError(f"GraphQL errors: {data['errors']}")

            return data.get("data", {})

    def _flatten_nested_object(self, obj: Any, prefix: str = "") -> Dict[str, Any]:
        """Flatten nested objects into dot-notation fields."""
        result = {}

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, (dict, list)) and value:
                    # Serialize complex objects as JSON strings
                    result[new_key] = json.dumps(value)
                else:
                    result[new_key] = value
        elif isinstance(obj, list):
            result[prefix] = json.dumps(obj)
        else:
            result[prefix] = obj

        return result

    def _extract_fields_from_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and flatten fields from a GraphQL node."""
        flattened = {}

        for key, value in node.items():
            if value is None:
                flattened[key] = None
            elif isinstance(value, dict):
                # Flatten nested objects
                nested = self._flatten_nested_object(value, key)
                flattened.update(nested)
            elif isinstance(value, list):
                # Serialize lists as JSON
                flattened[key] = json.dumps(value)
            else:
                flattened[key] = value

        return flattened

    def _infer_type_from_value(self, value: Any) -> Type:
        """Infer Python type from a value."""
        if value is None:
            return str
        elif isinstance(value, bool):
            return bool
        elif isinstance(value, int):
            return int
        elif isinstance(value, float):
            return float
        elif isinstance(value, str):
            # Check if it's a datetime string
            if "T" in value and ("Z" in value or "+" in value or "-" in value):
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return datetime
                except (ValueError, AttributeError):
                    pass
            return str
        elif isinstance(value, (dict, list)):
            return str  # Will be serialized as JSON
        else:
            return str

    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field names to avoid collisions."""
        if field_name in self._RESERVED_ENTITY_FIELDS:
            return f"{field_name}_field"
        return field_name

    async def _create_entity_class(
        self, resource_type: str, sample_nodes: List[Dict]
    ) -> Type[PolymorphicEntity]:
        """Create a polymorphic entity class from sample data.

        Args:
            resource_type: Name of the resource
            sample_nodes: Sample nodes to infer schema

        Returns:
            Dynamically created entity class
        """
        # Collect all fields from sample nodes
        all_fields = {}
        for node in sample_nodes:
            flattened = self._extract_fields_from_node(node)
            for field_name, value in flattened.items():
                if field_name not in all_fields:
                    python_type = self._infer_type_from_value(value)
                    all_fields[field_name] = python_type

        # Create columns
        columns = {}
        field_mapping = {}

        for field_name, python_type in all_fields.items():
            normalized_name = self._normalize_field_name(field_name)

            columns[field_name] = {
                "name": field_name,
                "python_type": python_type,
                "normalized_name": normalized_name,
            }

            field_mapping[field_name] = normalized_name

        self.field_mappings[resource_type] = field_mapping

        # Create entity class
        entity_class = PolymorphicEntity.create_table_entity_class(
            table_name=resource_type,
            schema_name="shopify",
            columns=columns,
            primary_keys=["id"],
        )

        return entity_class

    async def _fetch_resource_page(
        self, resource_type: str, cursor: Optional[str] = None, page_size: int = 50
    ) -> Dict:
        """Fetch a page of resources using cursor-based pagination.

        Args:
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

        result = await self._execute_graphql(query)
        return result.get(query_name, {})

    def _generate_entity_id(self, resource_type: str, node_data: Dict) -> str:
        """Generate a unique entity ID."""
        shopify_id = node_data.get("id", "")
        return f"shopify:{resource_type.lower()}:{shopify_id}"

    async def _process_node_to_entity(
        self,
        node_data: Dict,
        resource_type: str,
        entity_class: Type[PolymorphicEntity],
    ) -> BaseEntity:
        """Convert a GraphQL node to an entity."""
        # Flatten nested objects
        flattened = self._extract_fields_from_node(node_data)

        # Generate entity ID
        entity_id = self._generate_entity_id(resource_type, node_data)

        # Map fields
        field_mapping = self.field_mappings.get(resource_type, {})
        processed_data = {}

        for field_name, value in flattened.items():
            normalized_name = field_mapping.get(field_name, field_name)

            if normalized_name not in entity_class.model_fields:
                continue

            processed_data[normalized_name] = value

        # Determine entity name
        config = RESOURCE_CONFIGS[resource_type]
        name_field = config.get("name_field", "id")
        entity_name = str(node_data.get(name_field) or node_data.get("id", "unknown"))

        # Extract timestamps
        created_at = node_data.get("createdAt")
        updated_at = node_data.get("updatedAt")

        return entity_class(
            entity_id=entity_id,
            breadcrumbs=[],
            name=entity_name,
            created_at=created_at,
            updated_at=updated_at,
            **processed_data,
        )

    async def _sync_resource_type(self, resource_type: str) -> AsyncGenerator[BaseEntity, None]:
        """Sync all items for a specific resource type."""
        cursor = None
        page_count = 0
        total_items = 0
        sample_nodes = []

        # First pass: collect samples to infer schema
        self.logger.info(f"Collecting schema samples for {resource_type}...")
        sample_result = await self._fetch_resource_page(resource_type, None, 10)
        sample_edges = sample_result.get("edges", [])

        for edge in sample_edges:
            sample_nodes.append(edge.get("node", {}))

        if not sample_nodes:
            self.logger.warning(f"No data found for {resource_type}")
            return

        # Create entity class from samples
        entity_class = await self._create_entity_class(resource_type, sample_nodes)
        self.entity_classes[resource_type] = entity_class

        # Second pass: sync all data
        while True:
            page_count += 1
            self.logger.info(
                f"Fetching {resource_type} page {page_count} "
                f"(cursor: {cursor[:20] if cursor else 'start'}...)"
            )

            try:
                result = await self._fetch_resource_page(resource_type, cursor)
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
                    entity = await self._process_node_to_entity(node, resource_type, entity_class)
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
        try:
            # Create session
            self.session = await self._create_session()

            # Get list of resources to sync
            resources_to_sync = self.config.get("resources", list(RESOURCE_CONFIGS.keys()))

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

                async for entity in self._sync_resource_type(resource_type):
                    yield entity

            self.logger.info(
                f"Successfully completed sync for all {len(resources_to_sync)} resource types"
            )

        finally:
            if self.session:
                await self.session.close()
                self.session = None

    async def validate(self) -> bool:
        """Verify Shopify credentials and API access."""
        try:
            self.session = await self._create_session()

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

            result = await self._execute_graphql(test_query)

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

        finally:
            if self.session:
                await self.session.close()
                self.session = None
