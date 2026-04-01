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

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncGenerator, Dict

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
    _parse_shopify_ts,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod

SHOPIFY_API_VERSION = "2024-01"


_parse_datetime = _parse_shopify_ts


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

    SHOPIFY_PAGE_LIMIT = 250

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ShopifyConfig,
    ) -> ShopifySource:
        """Create a new Shopify source instance.

        Exchanges client credentials for an access token and stores the
        normalized shop_domain for all subsequent API calls.
        """
        instance = cls(auth=auth, logger=logger, http_client=http_client)

        creds: ShopifyAuthConfig = auth.credentials
        instance._client_id = creds.client_id
        instance._client_secret = creds.client_secret
        instance._shop_domain = cls._normalize_shop_domain(config.shop_domain)
        instance._access_token = await instance._exchange_credentials()

        return instance

    def _prepare_entity(self, entity: BaseEntity) -> BaseEntity:
        """Set original_entity_id for orphan cleanup."""
        from airweave.platform.entities._base import AirweaveSystemMetadata

        if entity.airweave_system_metadata is None:
            entity.airweave_system_metadata = AirweaveSystemMetadata()
        entity.airweave_system_metadata.original_entity_id = entity.entity_id
        return entity

    async def _exchange_credentials(self) -> str:
        """Exchange client credentials for an access token.

        Uses OAuth 2.0 client credentials grant flow.
        POST https://{shop}.myshopify.com/admin/oauth/access_token
        """
        url = f"https://{self._shop_domain}/admin/oauth/access_token"

        response = await self.http_client.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )

        if response.status_code != 200:
            raise SourceAuthError(
                message=(
                    f"Failed to get access token: {response.status_code} {response.reason_phrase}"
                ),
                status_code=response.status_code,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )

        data = response.json()
        return data["access_token"]

    @staticmethod
    def _normalize_shop_domain(domain: str) -> str:
        """Normalize Shopify shop domain — strip protocol prefix and trailing slash."""
        domain = domain.replace("https://", "").replace("http://", "")
        domain = domain.rstrip("/")
        return domain.lower()

    def _build_api_url(self, endpoint: str) -> str:
        """Build a Shopify Admin API URL."""
        endpoint = endpoint.lstrip("/")
        return f"https://{self._shop_domain}/admin/api/{SHOPIFY_API_VERSION}/{endpoint}"

    def _build_admin_url(self, resource: str, resource_id: str) -> str:
        """Build a Shopify Admin UI URL for a resource."""
        return f"https://{self._shop_domain}/admin/{resource}/{resource_id}"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> Dict:
        """Make an authenticated GET request to the Shopify Admin API."""
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self._access_token,
        }
        response = await self.http_client.get(url, headers=headers, timeout=30.0)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_response(self, url: str) -> httpx.Response:
        """Make an authenticated GET request, returning the full response.

        Used by _get_paginated which needs access to response headers for
        Link-based pagination.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self._access_token,
        }
        response = await self.http_client.get(url, headers=headers, timeout=30.0)
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def _get_paginated(self, endpoint: str, resource_key: str) -> AsyncGenerator[Dict, None]:
        """Fetch paginated results using Shopify Link-header pagination."""
        url = f"{self._build_api_url(endpoint)}?limit={self.SHOPIFY_PAGE_LIMIT}"

        while url:
            response = await self._get_response(url)
            data = response.json()

            for item in data.get(resource_key, []):
                yield item

            link_header = response.headers.get("link", "")
            url = None
            if link_header:
                for link in link_header.split(","):
                    if 'rel="next"' in link:
                        url = link.split(";")[0].strip().strip("<>")
                        break

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_product_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Product and ProductVariant entities from Shopify.

        GET /admin/api/{version}/products.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching products...")

        async for product in self._get_paginated("products.json", "products"):
            product_id = str(product["id"])
            created_time = _parse_datetime(product.get("created_at")) or datetime.utcnow()
            updated_time = _parse_datetime(product.get("updated_at")) or created_time

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

            for variant in product.get("variants", []):
                yield self._prepare_entity(
                    ShopifyProductVariantEntity.from_api(
                        variant,
                        product_id=product_id,
                        product_title=product.get("title", f"Product {product_id}"),
                        web_url=self._build_admin_url("products", product_id),
                        parent_created_time=created_time,
                    )
                )

    async def _generate_customer_entities(self) -> AsyncGenerator[ShopifyCustomerEntity, None]:
        """Generate Customer entities from Shopify.

        GET /admin/api/{version}/customers.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching customers...")

        async for customer in self._get_paginated("customers.json", "customers"):
            customer_id = str(customer["id"])
            yield self._prepare_entity(
                ShopifyCustomerEntity.from_api(
                    customer,
                    web_url=self._build_admin_url("customers", customer_id),
                )
            )

    async def _generate_order_entities(self) -> AsyncGenerator[ShopifyOrderEntity, None]:
        """Generate Order entities from Shopify.

        GET /admin/api/{version}/orders.json?status=any
        """
        self.logger.info("🔍 [SHOPIFY] Fetching orders...")

        async for order in self._get_paginated("orders.json?status=any", "orders"):
            order_id = str(order["id"])
            yield self._prepare_entity(
                ShopifyOrderEntity.from_api(
                    order,
                    web_url=self._build_admin_url("orders", order_id),
                )
            )

    async def _generate_draft_order_entities(
        self,
    ) -> AsyncGenerator[ShopifyDraftOrderEntity, None]:
        """Generate Draft Order entities from Shopify.

        GET /admin/api/{version}/draft_orders.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching draft orders...")

        async for draft_order in self._get_paginated("draft_orders.json", "draft_orders"):
            draft_order_id = str(draft_order["id"])
            yield self._prepare_entity(
                ShopifyDraftOrderEntity.from_api(
                    draft_order,
                    web_url=self._build_admin_url("draft_orders", draft_order_id),
                )
            )

    async def _generate_collection_entities(
        self,
    ) -> AsyncGenerator[ShopifyCollectionEntity, None]:
        """Generate Collection entities from Shopify (both Custom and Smart).

        GET /admin/api/{version}/custom_collections.json
        GET /admin/api/{version}/smart_collections.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching collections...")

        async for collection in self._get_paginated(
            "custom_collections.json", "custom_collections"
        ):
            collection_id = str(collection["id"])
            yield self._prepare_entity(
                ShopifyCollectionEntity.from_api(
                    collection,
                    collection_type="custom",
                    web_url=self._build_admin_url("collections", collection_id),
                )
            )

        async for collection in self._get_paginated("smart_collections.json", "smart_collections"):
            collection_id = str(collection["id"])
            yield self._prepare_entity(
                ShopifyCollectionEntity.from_api(
                    collection,
                    collection_type="smart",
                    web_url=self._build_admin_url("collections", collection_id),
                )
            )

    async def _generate_location_entities(self) -> AsyncGenerator[ShopifyLocationEntity, None]:
        """Generate Location entities from Shopify.

        GET /admin/api/{version}/locations.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching locations...")

        async for location in self._get_paginated("locations.json", "locations"):
            location_id = str(location["id"])
            created_time = _parse_datetime(location.get("created_at")) or datetime.utcnow()
            updated_time = _parse_datetime(location.get("updated_at")) or created_time

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

    async def _generate_inventory_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate Inventory Item and Level entities from Shopify.

        GET /admin/api/{version}/inventory_items.json
        GET /admin/api/{version}/inventory_levels.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching inventory...")

        locations: Dict[str, str] = {}
        async for location in self._get_paginated("locations.json", "locations"):
            locations[str(location["id"])] = location.get("name", f"Location {location['id']}")

        inventory_items_seen: set = set()

        async for product in self._get_paginated("products.json", "products"):
            for variant in product.get("variants", []):
                inventory_item_id = str(variant.get("inventory_item_id", ""))
                if inventory_item_id and inventory_item_id not in inventory_items_seen:
                    inventory_items_seen.add(inventory_item_id)

                    try:
                        url = self._build_api_url(f"inventory_items/{inventory_item_id}.json")
                        data = await self._get(url)
                        item = data.get("inventory_item", {})

                        created_time = _parse_datetime(item.get("created_at")) or datetime.utcnow()
                        updated_time = _parse_datetime(item.get("updated_at")) or created_time

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

                        levels_url = self._build_api_url(
                            f"inventory_levels.json?inventory_item_ids={inventory_item_id}"
                        )
                        levels_data = await self._get(levels_url)

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
                    except SourceAuthError:
                        raise
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to fetch inventory item {inventory_item_id}: {e}"
                        )

    async def _generate_fulfillment_entities(
        self,
    ) -> AsyncGenerator[ShopifyFulfillmentEntity, None]:
        """Generate Fulfillment entities from Shopify (nested under orders).

        GET /admin/api/{version}/orders/{order_id}/fulfillments.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching fulfillments...")

        async for order in self._get_paginated("orders.json?status=any", "orders"):
            order_id = str(order["id"])
            order_name = order.get("name", f"Order {order_id}")

            for fulfillment in order.get("fulfillments", []):
                yield self._prepare_entity(
                    ShopifyFulfillmentEntity.from_api(
                        fulfillment,
                        order_id=order_id,
                        order_name=order_name,
                        web_url=self._build_admin_url("orders", order_id),
                    )
                )

    async def _generate_gift_card_entities(
        self,
    ) -> AsyncGenerator[ShopifyGiftCardEntity, None]:
        """Generate Gift Card entities from Shopify.

        GET /admin/api/{version}/gift_cards.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching gift cards...")

        async for gift_card in self._get_paginated("gift_cards.json", "gift_cards"):
            if gift_card.get("disabled_at"):
                continue

            gift_card_id = str(gift_card["id"])
            yield self._prepare_entity(
                ShopifyGiftCardEntity.from_api(
                    gift_card,
                    web_url=self._build_admin_url("gift_cards", gift_card_id),
                )
            )

    async def _generate_discount_entities(self) -> AsyncGenerator[ShopifyDiscountEntity, None]:
        """Generate Discount (Price Rule) entities from Shopify.

        GET /admin/api/{version}/price_rules.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching discounts/price rules...")

        async for price_rule in self._get_paginated("price_rules.json", "price_rules"):
            discount_id = str(price_rule["id"])
            created_time = _parse_datetime(price_rule.get("created_at")) or datetime.utcnow()
            updated_time = _parse_datetime(price_rule.get("updated_at")) or created_time

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
                    starts_at=_parse_datetime(price_rule.get("starts_at")),
                    ends_at=_parse_datetime(price_rule.get("ends_at")),
                    prerequisite_subtotal_range=price_rule.get("prerequisite_subtotal_range"),
                    prerequisite_quantity_range=price_rule.get("prerequisite_quantity_range"),
                )
            )

    async def _generate_metaobject_entities(  # noqa: C901
        self,
    ) -> AsyncGenerator[ShopifyMetaobjectEntity, None]:
        """Generate Metaobject entities from Shopify.

        GET /admin/api/{version}/metaobjects.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching metaobjects...")

        try:
            definitions_url = self._build_api_url("metaobject_definitions.json")
            definitions_data = await self._get(definitions_url)

            for definition in definitions_data.get("metaobject_definitions", []):
                def_type = definition.get("type", "")
                if not def_type:
                    continue

                metaobjects_url = self._build_api_url(f"metaobjects.json?type={def_type}")
                try:
                    metaobjects_data = await self._get(metaobjects_url)

                    for metaobject in metaobjects_data.get("metaobjects", []):
                        metaobject_id = str(metaobject["id"])
                        created_time = (
                            _parse_datetime(metaobject.get("created_at")) or datetime.utcnow()
                        )
                        updated_time = _parse_datetime(metaobject.get("updated_at")) or created_time

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
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Failed to fetch metaobjects of type {def_type}: {e}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to fetch metaobject definitions: {e}")

    async def _generate_file_entities(self) -> AsyncGenerator[ShopifyFileEntity, None]:
        """Generate File entities from Shopify using GraphQL.

        The Files API requires GraphQL, not REST.
        """
        self.logger.info("🔍 [SHOPIFY] Fetching files via GraphQL...")

        graphql_url = f"https://{self._shop_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"

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
        gql_cursor = None

        while has_next_page:
            variables: Dict[str, Any] = {"first": 50}
            if gql_cursor:
                variables["after"] = gql_cursor

            try:
                headers = {
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": self._access_token,
                }
                response = await self.http_client.post(
                    graphql_url,
                    headers=headers,
                    json={"query": query, "variables": variables},
                    timeout=30.0,
                )
                raise_for_status(
                    response,
                    source_short_name=self.short_name,
                    token_provider_kind=self.auth.provider_kind,
                )
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

                    yield self._prepare_entity(
                        ShopifyFileEntity.from_api(
                            file_node,
                            web_url=self._build_admin_url("content/files", file_id),
                        )
                    )

                has_next_page = page_info.get("hasNextPage", False)
                gql_cursor = page_info.get("endCursor")

            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to fetch files via GraphQL: {e}")
                break

    async def _generate_theme_entities(self) -> AsyncGenerator[ShopifyThemeEntity, None]:
        """Generate Theme entities from Shopify.

        GET /admin/api/{version}/themes.json
        """
        self.logger.info("🔍 [SHOPIFY] Fetching themes...")

        async for theme in self._get_paginated("themes.json", "themes"):
            theme_id = str(theme["id"])
            created_time = _parse_datetime(theme.get("created_at")) or datetime.utcnow()
            updated_time = _parse_datetime(theme.get("updated_at")) or created_time

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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Shopify entities."""
        async for entity in self._generate_product_entities():
            yield entity

        async for entity in self._generate_customer_entities():
            yield entity

        async for entity in self._generate_order_entities():
            yield entity

        async for entity in self._generate_draft_order_entities():
            yield entity

        async for entity in self._generate_collection_entities():
            yield entity

        async for entity in self._generate_location_entities():
            yield entity

        async for entity in self._generate_inventory_entities():
            yield entity

        async for entity in self._generate_fulfillment_entities():
            yield entity

        async for entity in self._generate_gift_card_entities():
            yield entity

        async for entity in self._generate_discount_entities():
            yield entity

        async for entity in self._generate_metaobject_entities():
            yield entity

        async for entity in self._generate_file_entities():
            yield entity

        async for entity in self._generate_theme_entities():
            yield entity

    async def validate(self) -> None:
        """Verify Shopify API access by pinging the shop endpoint."""
        await self._get(self._build_api_url("shop.json"))
