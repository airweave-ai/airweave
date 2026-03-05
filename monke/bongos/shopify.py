"""Shopify-specific bongo implementation using Client Credentials Grant.

Creates, updates, and deletes test entities via the Shopify Admin API.
Uses OAuth 2.0 client credentials grant to exchange client_id/client_secret
for an access token.

Covers entity types: Products, Variants, Customers, Orders, Collections,
Discounts (Price Rules), and Gift Cards.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


# Shopify API version
SHOPIFY_API_VERSION = "2024-01"


class ShopifyBongo(BaseBongo):
    """Shopify-specific bongo implementation.

    Creates, updates, and deletes test entities via the Shopify Admin API.
    Uses client credentials grant for authentication.

    Tests the following entity types:
    - Products (with auto-generated Variants)
    - Customers
    - Draft Orders
    - Custom Collections
    - Discounts (Price Rules)
    - Gift Cards

    Note: Locations, Inventory, Fulfillments, Metaobjects, Files, and Themes
    are read-only or dependent entities that don't need bongo creation.
    """

    connector_type = "shopify"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Shopify bongo.

        Args:
            credentials: Shopify credentials with client_id and client_secret
            **kwargs: Configuration from config file (shop_domain, entity_count, etc.)
        """
        super().__init__(credentials)
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("client_secret", "")
        self.shop_domain = kwargs.get("shop_domain", "")
        self.access_token: Optional[str] = None

        # Configuration from config file
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking - ALL entity types
        self._products: List[Dict[str, Any]] = []
        self._variants: List[Dict[str, Any]] = []
        self._customers: List[Dict[str, Any]] = []
        self._orders: List[Dict[str, Any]] = []
        self._collections: List[Dict[str, Any]] = []
        self._discounts: List[Dict[str, Any]] = []
        self._gift_cards: List[Dict[str, Any]] = []

        # Rate limiting (Shopify: 2 requests per second for REST API)
        self.last_request_time = 0.0
        self.rate_limit_delay = 0.5  # 500ms between requests

        # Logger
        self.logger = get_logger("shopify_bongo")

    async def _get_access_token(self) -> str:
        """Exchange client credentials for an access token.

        Returns:
            Access token string
        """
        if self.access_token:
            return self.access_token

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
            self.access_token = data["access_token"]
            self.logger.info("✅ Obtained Shopify access token via client credentials")
            return self.access_token

    def _build_api_url(self, endpoint: str) -> str:
        """Build Shopify Admin API URL."""
        endpoint = endpoint.lstrip("/")
        return f"https://{self.shop_domain}/admin/api/{SHOPIFY_API_VERSION}/{endpoint}"

    async def _headers(self) -> Dict[str, str]:
        """Return headers for Shopify API requests with access token."""
        token = await self._get_access_token()
        return {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": token,
        }

    async def _rate_limit(self):
        """Implement rate limiting for Shopify API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create ALL types of test entities in Shopify.

        Creates:
        - Products (with variants auto-generated)
        - Customers
        - Draft Orders (linked to customers/products)
        - Custom Collections

        Returns:
            List of entity descriptors with verification tokens
        """
        self.logger.info(
            f"🥁 Creating {self.entity_count} of each entity type in Shopify"
        )
        all_entities: List[Dict[str, Any]] = []

        from monke.generation.shopify import (
            generate_shopify_product,
            generate_shopify_customer,
            generate_shopify_collection,
            generate_shopify_order,
            generate_shopify_discount,
            generate_shopify_gift_card,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # 1. Create Products (with variants)
            self.logger.info(f"📦 Creating {self.entity_count} products...")
            for i in range(self.entity_count):
                product_token = str(uuid.uuid4())[:8]
                variant_token = str(uuid.uuid4())[:8]

                product_data = await generate_shopify_product(
                    self.openai_model, product_token
                )

                await self._rate_limit()
                product = await self._create_product(
                    client, headers, product_data, product_token, variant_token
                )

                if product:
                    # Track product entity
                    product_desc = {
                        "type": "product",
                        "id": f"product_{product['id']}",
                        "shopify_id": str(product["id"]),
                        "name": product["title"],
                        "token": product_token,
                        "expected_content": product_token,
                    }
                    self._products.append(product_desc)
                    all_entities.append(product_desc)

                    # Track variant entities (auto-created with product)
                    for variant in product.get("variants", []):
                        variant_desc = {
                            "type": "variant",
                            "id": f"variant_{variant['id']}",
                            "shopify_id": str(variant["id"]),
                            "parent_id": f"product_{product['id']}",
                            "name": variant.get("title", "Default"),
                            "token": variant_token,
                            "expected_content": variant_token,
                        }
                        self._variants.append(variant_desc)
                        all_entities.append(variant_desc)

                    self.logger.info(
                        f"📦 Created product: {product['id']} with "
                        f"{len(product.get('variants', []))} variant(s)"
                    )

            # 2. Create Customers
            self.logger.info(f"👤 Creating {self.entity_count} customers...")
            for i in range(self.entity_count):
                customer_token = str(uuid.uuid4())[:8]

                customer_data = await generate_shopify_customer(
                    self.openai_model, customer_token
                )

                await self._rate_limit()
                customer = await self._create_customer(client, headers, customer_data, customer_token)

                if customer:
                    customer_desc = {
                        "type": "customer",
                        "id": f"customer_{customer['id']}",
                        "shopify_id": str(customer["id"]),
                        "name": f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                        "token": customer_token,
                        "expected_content": customer_token,
                    }
                    self._customers.append(customer_desc)
                    all_entities.append(customer_desc)
                    self.logger.info(f"👤 Created customer: {customer['id']}")

            # 3. Create Custom Collections
            self.logger.info(f"📁 Creating {self.entity_count} collections...")
            for i in range(self.entity_count):
                collection_token = str(uuid.uuid4())[:8]

                collection_data = await generate_shopify_collection(
                    self.openai_model, collection_token
                )

                await self._rate_limit()
                collection = await self._create_collection(
                    client, headers, collection_data, collection_token
                )

                if collection:
                    collection_desc = {
                        "type": "collection",
                        "id": f"collection_{collection['id']}",
                        "shopify_id": str(collection["id"]),
                        "name": collection["title"],
                        "token": collection_token,
                        "expected_content": collection_token,
                    }
                    self._collections.append(collection_desc)
                    all_entities.append(collection_desc)
                    self.logger.info(f"📁 Created collection: {collection['id']}")

            # 4. Create Draft Orders (require customer only - NO product links)
            # IMPORTANT: We intentionally do NOT link draft orders to products/variants
            # to avoid token leakage. If a draft order contains a product variant,
            # the product's token appears in the draft order's line items, causing
            # false positives in deletion verification.
            if self._customers:
                self.logger.info(f"🛒 Creating {self.entity_count} draft orders...")
                for i in range(min(self.entity_count, len(self._customers))):
                    order_token = str(uuid.uuid4())[:8]

                    order_data = await generate_shopify_order(
                        self.openai_model, order_token
                    )

                    await self._rate_limit()
                    # Always use custom line items (no variant_id) to keep tokens isolated
                    order = await self._create_draft_order(
                        client,
                        headers,
                        order_data,
                        order_token,
                        customer_id=self._customers[i]["shopify_id"],
                        variant_id=None,  # No product link to avoid token leakage
                    )

                    if order:
                        order_desc = {
                            "type": "draft_order",
                            "id": f"draft_order_{order['id']}",
                            "shopify_id": str(order["id"]),
                            "name": order.get("name", f"Draft Order {order['id']}"),
                            "token": order_token,
                            "expected_content": order_token,
                        }
                        self._orders.append(order_desc)
                        all_entities.append(order_desc)
                        self.logger.info(f"🛒 Created draft order: {order['id']}")

            # 5. Create Discounts (Price Rules)
            self.logger.info(f"🏷️ Creating {self.entity_count} discounts...")
            for i in range(self.entity_count):
                discount_token = str(uuid.uuid4())[:8]

                discount_data = await generate_shopify_discount(
                    self.openai_model, discount_token
                )

                await self._rate_limit()
                discount = await self._create_discount(
                    client, headers, discount_data, discount_token
                )

                if discount:
                    discount_desc = {
                        "type": "discount",
                        "id": f"discount_{discount['id']}",
                        "shopify_id": str(discount["id"]),
                        "name": discount["title"],
                        "token": discount_token,
                        "expected_content": discount_token,
                    }
                    self._discounts.append(discount_desc)
                    all_entities.append(discount_desc)
                    self.logger.info(f"🏷️ Created discount: {discount['id']}")

            # 6. Create Gift Cards
            self.logger.info(f"🎁 Creating {self.entity_count} gift cards...")
            for i in range(self.entity_count):
                gift_card_token = str(uuid.uuid4())[:8]

                gift_card_data = await generate_shopify_gift_card(
                    self.openai_model, gift_card_token
                )

                await self._rate_limit()
                gift_card = await self._create_gift_card(
                    client, headers, gift_card_data, gift_card_token
                )

                if gift_card:
                    gift_card_desc = {
                        "type": "gift_card",
                        "id": f"gift_card_{gift_card['id']}",
                        "shopify_id": str(gift_card["id"]),
                        "name": f"Gift Card ****{gift_card.get('last_characters', '')}",
                        "token": gift_card_token,
                        "expected_content": gift_card_token,
                    }
                    self._gift_cards.append(gift_card_desc)
                    all_entities.append(gift_card_desc)
                    self.logger.info(f"🎁 Created gift card: {gift_card['id']}")

        self.logger.info(
            f"✅ Created {len(self._products)} products, "
            f"{len(self._variants)} variants, "
            f"{len(self._customers)} customers, "
            f"{len(self._collections)} collections, "
            f"{len(self._orders)} orders, "
            f"{len(self._discounts)} discounts, "
            f"{len(self._gift_cards)} gift cards"
        )

        self.created_entities = all_entities
        return all_entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update a subset of entities to test incremental sync."""
        self.logger.info("🥁 Updating test entities in Shopify")
        updated_entities: List[Dict[str, Any]] = []

        from monke.generation.shopify import (
            generate_shopify_product,
            generate_shopify_customer,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # Update first 2 products
            products_to_update = min(2, len(self._products))
            for i in range(products_to_update):
                product = self._products[i]
                token = product["token"]

                product_data = await generate_shopify_product(
                    self.openai_model, token, is_update=True
                )

                await self._rate_limit()
                updated = await self._update_product(
                    client, headers, product["shopify_id"], product_data
                )

                if updated:
                    updated_entities.append({
                        **product,
                        "name": updated["title"],
                        "updated": True,
                    })
                    self.logger.info(f"📝 Updated product: {product['shopify_id']}")

            # Update first 2 customers
            customers_to_update = min(2, len(self._customers))
            for i in range(customers_to_update):
                customer = self._customers[i]
                token = customer["token"]

                customer_data = await generate_shopify_customer(
                    self.openai_model, token, is_update=True
                )

                await self._rate_limit()
                updated = await self._update_customer(
                    client, headers, customer["shopify_id"], customer_data
                )

                if updated:
                    updated_entities.append({
                        **customer,
                        "updated": True,
                    })
                    self.logger.info(f"📝 Updated customer: {customer['shopify_id']}")

        self.logger.info(f"✅ Updated {len(updated_entities)} entities")
        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete ALL test entities from Shopify."""
        self.logger.info("🥁 Deleting ALL test entities from Shopify")
        deleted_ids: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # Delete in dependency order: orders -> collections -> products -> customers
            # 1. Delete draft orders first
            for order in self._orders:
                try:
                    await self._rate_limit()
                    await self._delete_draft_order(client, headers, order["shopify_id"])
                    deleted_ids.append(order["id"])
                    self.logger.info(f"🗑️ Deleted draft order: {order['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete order {order['id']}: {e}")

            # 2. Delete collections
            for collection in self._collections:
                try:
                    await self._rate_limit()
                    await self._delete_collection(client, headers, collection["shopify_id"])
                    deleted_ids.append(collection["id"])
                    self.logger.info(f"🗑️ Deleted collection: {collection['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete collection {collection['id']}: {e}")

            # 3. Delete products (variants auto-deleted)
            for product in self._products:
                try:
                    await self._rate_limit()
                    await self._delete_product(client, headers, product["shopify_id"])
                    deleted_ids.append(product["id"])
                    # Also mark variants as deleted
                    for variant in self._variants:
                        if variant["parent_id"] == product["id"]:
                            deleted_ids.append(variant["id"])
                    self.logger.info(f"🗑️ Deleted product: {product['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete product {product['id']}: {e}")

            # 4. Delete customers
            for customer in self._customers:
                try:
                    await self._rate_limit()
                    await self._delete_customer(client, headers, customer["shopify_id"])
                    deleted_ids.append(customer["id"])
                    self.logger.info(f"🗑️ Deleted customer: {customer['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete customer {customer['id']}: {e}")

            # 5. Delete discounts (price rules)
            for discount in self._discounts:
                try:
                    await self._rate_limit()
                    await self._delete_discount(client, headers, discount["shopify_id"])
                    deleted_ids.append(discount["id"])
                    self.logger.info(f"🗑️ Deleted discount: {discount['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete discount {discount['id']}: {e}")

            # 6. Disable gift cards (can't delete, only disable)
            for gift_card in self._gift_cards:
                try:
                    await self._rate_limit()
                    await self._disable_gift_card(client, headers, gift_card["shopify_id"])
                    deleted_ids.append(gift_card["id"])
                    self.logger.info(f"🗑️ Disabled gift card: {gift_card['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not disable gift card {gift_card['id']}: {e}")

        # Clear tracking
        self._orders = []
        self._collections = []
        self._products = []
        self._variants = []
        self._customers = []
        self._discounts = []
        self._gift_cards = []

        self.logger.info(f"✅ Deleted {len(deleted_ids)} entities")
        return deleted_ids

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities from Shopify."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific entities from Shopify")
        deleted_ids: List[str] = []

        # Categorize by type for proper deletion order
        draft_orders = [e for e in entities if e.get("type") == "draft_order"]
        collections = [e for e in entities if e.get("type") == "collection"]
        products = [e for e in entities if e.get("type") == "product"]
        customers = [e for e in entities if e.get("type") == "customer"]
        discounts = [e for e in entities if e.get("type") == "discount"]
        gift_cards = [e for e in entities if e.get("type") == "gift_card"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            # Delete in dependency order
            for draft_order in draft_orders:
                try:
                    await self._rate_limit()
                    await self._delete_draft_order(client, headers, draft_order["shopify_id"])
                    deleted_ids.append(draft_order["id"])
                    self._orders = [o for o in self._orders if o["id"] != draft_order["id"]]
                    self.logger.info(f"🗑️ Deleted draft order: {draft_order['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete draft order {draft_order['id']}: {e}")

            for collection in collections:
                try:
                    await self._rate_limit()
                    await self._delete_collection(client, headers, collection["shopify_id"])
                    deleted_ids.append(collection["id"])
                    self._collections = [c for c in self._collections if c["id"] != collection["id"]]
                    self.logger.info(f"🗑️ Deleted collection: {collection['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete collection {collection['id']}: {e}")

            for product in products:
                try:
                    await self._rate_limit()
                    await self._delete_product(client, headers, product["shopify_id"])
                    deleted_ids.append(product["id"])
                    # Mark variants as deleted
                    for variant in self._variants:
                        if variant["parent_id"] == product["id"]:
                            deleted_ids.append(variant["id"])
                    self._products = [p for p in self._products if p["id"] != product["id"]]
                    self._variants = [v for v in self._variants if v["parent_id"] != product["id"]]
                    self.logger.info(f"🗑️ Deleted product: {product['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete product {product['id']}: {e}")

            for customer in customers:
                try:
                    await self._rate_limit()
                    await self._delete_customer(client, headers, customer["shopify_id"])
                    deleted_ids.append(customer["id"])
                    self._customers = [c for c in self._customers if c["id"] != customer["id"]]
                    self.logger.info(f"🗑️ Deleted customer: {customer['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete customer {customer['id']}: {e}")

            for discount in discounts:
                try:
                    await self._rate_limit()
                    await self._delete_discount(client, headers, discount["shopify_id"])
                    deleted_ids.append(discount["id"])
                    self._discounts = [d for d in self._discounts if d["id"] != discount["id"]]
                    self.logger.info(f"🗑️ Deleted discount: {discount['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not delete discount {discount['id']}: {e}")

            for gift_card in gift_cards:
                try:
                    await self._rate_limit()
                    await self._disable_gift_card(client, headers, gift_card["shopify_id"])
                    deleted_ids.append(gift_card["id"])
                    self._gift_cards = [g for g in self._gift_cards if g["id"] != gift_card["id"]]
                    self.logger.info(f"🗑️ Disabled gift card: {gift_card['shopify_id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not disable gift card {gift_card['id']}: {e}")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test entities in Shopify")

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = await self._headers()

            for order in self._orders:
                try:
                    await self._rate_limit()
                    await self._delete_draft_order(client, headers, order["shopify_id"])
                except Exception:
                    pass

            for collection in self._collections:
                try:
                    await self._rate_limit()
                    await self._delete_collection(client, headers, collection["shopify_id"])
                except Exception:
                    pass

            for product in self._products:
                try:
                    await self._rate_limit()
                    await self._delete_product(client, headers, product["shopify_id"])
                except Exception:
                    pass

            for customer in self._customers:
                try:
                    await self._rate_limit()
                    await self._delete_customer(client, headers, customer["shopify_id"])
                except Exception:
                    pass

            for discount in self._discounts:
                try:
                    await self._rate_limit()
                    await self._delete_discount(client, headers, discount["shopify_id"])
                except Exception:
                    pass

            for gift_card in self._gift_cards:
                try:
                    await self._rate_limit()
                    await self._disable_gift_card(client, headers, gift_card["shopify_id"])
                except Exception:
                    pass

        self._orders = []
        self._collections = []
        self._products = []
        self._variants = []
        self._customers = []
        self._discounts = []
        self._gift_cards = []
        self.logger.info("🧹 Cleanup completed")

    # ==================== API Helper Methods ====================

    async def _create_product(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        product_data: Dict[str, Any],
        product_token: str,
        variant_token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a product via Shopify Admin API."""
        title = product_data.get("title", "Test Product")
        if product_token not in title:
            title = f"{title} [{product_token}]"

        body_html = product_data.get("body_html", "")
        if product_token not in body_html:
            body_html = f"{body_html}<p>Token: {product_token}</p>"

        payload = {
            "product": {
                "title": title,
                "body_html": body_html,
                "vendor": product_data.get("vendor", "Monke Test"),
                "product_type": product_data.get("product_type", "Test"),
                "status": "active",
                "tags": "monke-test",
                "variants": [
                    {
                        "price": "19.99",
                        "sku": f"MONKE-{variant_token}",
                        "inventory_management": None,
                    }
                ],
            }
        }

        response = await client.post(
            self._build_api_url("products.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("product")
        else:
            self.logger.error(f"Failed to create product: {response.status_code} - {response.text}")
            return None

    async def _update_product(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        product_id: str,
        product_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update a product via Shopify Admin API."""
        payload = {
            "product": {
                "id": product_id,
                "body_html": product_data.get("body_html", "Updated description"),
            }
        }

        response = await client.put(
            self._build_api_url(f"products/{product_id}.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code == 200:
            return response.json().get("product")
        else:
            self.logger.error(f"Failed to update product: {response.status_code} - {response.text}")
            return None

    async def _delete_product(self, client: httpx.AsyncClient, headers: Dict[str, str], product_id: str):
        """Delete a product via Shopify Admin API."""
        response = await client.delete(
            self._build_api_url(f"products/{product_id}.json"),
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Failed to delete product: {response.status_code} - {response.text}")

    async def _create_customer(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        customer_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a customer via Shopify Admin API."""
        note = customer_data.get("note", "")
        if token not in note:
            note = f"{note} Token: {token}"

        # Always use a unique email based on token to avoid duplicates
        # Use example.com (IANA reserved domain) - Shopify rejects subdomains like test.example.com
        unique_email = f"monke-{token}@example.com"

        payload = {
            "customer": {
                "first_name": customer_data.get("first_name", "Test"),
                "last_name": customer_data.get("last_name", "Customer"),
                "email": unique_email,
                "note": note,
                "tags": "monke-test",
            }
        }

        response = await client.post(
            self._build_api_url("customers.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("customer")
        else:
            self.logger.error(f"Failed to create customer: {response.status_code} - {response.text}")
            return None

    async def _update_customer(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        customer_id: str,
        customer_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Update a customer via Shopify Admin API."""
        payload = {
            "customer": {
                "id": customer_id,
                "note": customer_data.get("note", "Updated note"),
            }
        }

        response = await client.put(
            self._build_api_url(f"customers/{customer_id}.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code == 200:
            return response.json().get("customer")
        else:
            self.logger.error(f"Failed to update customer: {response.status_code} - {response.text}")
            return None

    async def _delete_customer(self, client: httpx.AsyncClient, headers: Dict[str, str], customer_id: str):
        """Delete a customer via Shopify Admin API."""
        response = await client.delete(
            self._build_api_url(f"customers/{customer_id}.json"),
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Failed to delete customer: {response.status_code} - {response.text}")

    async def _create_collection(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        collection_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a custom collection via Shopify Admin API."""
        title = collection_data.get("title", "Test Collection")
        if token not in title:
            title = f"{title} [{token}]"

        body_html = collection_data.get("body_html", "")
        if token not in body_html:
            body_html = f"{body_html}<p>Token: {token}</p>"

        payload = {
            "custom_collection": {
                "title": title,
                "body_html": body_html,
                "published": True,
            }
        }

        response = await client.post(
            self._build_api_url("custom_collections.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("custom_collection")
        else:
            self.logger.error(f"Failed to create collection: {response.status_code} - {response.text}")
            return None

    async def _delete_collection(self, client: httpx.AsyncClient, headers: Dict[str, str], collection_id: str):
        """Delete a custom collection via Shopify Admin API."""
        response = await client.delete(
            self._build_api_url(f"custom_collections/{collection_id}.json"),
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Failed to delete collection: {response.status_code} - {response.text}")

    async def _create_draft_order(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        order_data: Dict[str, Any],
        token: str,
        customer_id: str,
        variant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a draft order via Shopify Admin API.

        Note: We intentionally use custom line items instead of linking to product
        variants. If a draft order contains a variant, the product's name/token
        appears in the draft order data, causing token leakage and false positives
        during deletion verification tests.
        """
        note = order_data.get("note", "")
        if token not in note:
            note = f"{note} Token: {token}"

        payload: Dict[str, Any] = {
            "draft_order": {
                "customer": {"id": int(customer_id)},
                "note": note,
                "tags": "monke-test",
            }
        }

        # Always use custom line items to avoid token leakage from products
        # Even if variant_id is passed, we ignore it to keep tokens isolated
        payload["draft_order"]["line_items"] = [
            {"title": f"Test Item [{token}]", "price": "10.00", "quantity": 1}
        ]

        response = await client.post(
            self._build_api_url("draft_orders.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("draft_order")
        else:
            self.logger.error(f"Failed to create draft order: {response.status_code} - {response.text}")
            return None

    async def _delete_draft_order(self, client: httpx.AsyncClient, headers: Dict[str, str], order_id: str):
        """Delete a draft order via Shopify Admin API."""
        response = await client.delete(
            self._build_api_url(f"draft_orders/{order_id}.json"),
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Failed to delete draft order: {response.status_code} - {response.text}")

    async def _create_discount(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        discount_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a price rule (discount) via Shopify Admin API."""
        title = discount_data.get("title", "Test Discount")
        if token not in title:
            title = f"{title} [{token}]"

        # Determine value type
        value_type = discount_data.get("value_type", "percentage")
        if value_type not in ["percentage", "fixed_amount"]:
            value_type = "percentage"

        # Get value and ensure it's negative for discounts
        value = discount_data.get("value", "-10")
        if not value.startswith("-"):
            value = f"-{value}"

        payload = {
            "price_rule": {
                "title": title,
                "target_type": "line_item",
                "target_selection": "all",
                "allocation_method": "across",
                "value_type": value_type,
                "value": value,
                "customer_selection": "all",
                "starts_at": "2024-01-01T00:00:00Z",
            }
        }

        response = await client.post(
            self._build_api_url("price_rules.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("price_rule")
        else:
            self.logger.error(f"Failed to create discount: {response.status_code} - {response.text}")
            return None

    async def _delete_discount(self, client: httpx.AsyncClient, headers: Dict[str, str], discount_id: str):
        """Delete a price rule (discount) via Shopify Admin API."""
        response = await client.delete(
            self._build_api_url(f"price_rules/{discount_id}.json"),
            headers=headers,
        )
        if response.status_code not in (200, 204):
            raise Exception(f"Failed to delete discount: {response.status_code} - {response.text}")

    async def _create_gift_card(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        gift_card_data: Dict[str, Any],
        token: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a gift card via Shopify Admin API."""
        note = gift_card_data.get("note", "")
        if token not in note:
            note = f"{note} Token: {token}"

        initial_value = gift_card_data.get("initial_value", "25.00")

        payload = {
            "gift_card": {
                "initial_value": initial_value,
                "note": note,
            }
        }

        response = await client.post(
            self._build_api_url("gift_cards.json"),
            headers=headers,
            json=payload,
        )

        if response.status_code in (200, 201):
            return response.json().get("gift_card")
        else:
            self.logger.error(f"Failed to create gift card: {response.status_code} - {response.text}")
            return None

    async def _disable_gift_card(self, client: httpx.AsyncClient, headers: Dict[str, str], gift_card_id: str):
        """Disable a gift card via Shopify Admin API.

        Note: Gift cards cannot be deleted, only disabled.
        """
        payload = {
            "gift_card": {
                "id": gift_card_id,
            }
        }

        response = await client.post(
            self._build_api_url(f"gift_cards/{gift_card_id}/disable.json"),
            headers=headers,
            json=payload,
        )
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to disable gift card: {response.status_code} - {response.text}")
