"""WooCommerce source implementation.

We retrieve data from the WooCommerce API for the following core resources:
- Products
- Orders
- Customers
- Categories
- Coupons
- Refunds

Then, we yield them as entities using the respective entity schemas
defined in entities/woocommerce.py.
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import WooCommerceAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.woocommerce import (
    WooCommerceCategoryEntity,
    WooCommerceCouponEntity,
    WooCommerceCustomerEntity,
    WooCommerceOrderEntity,
    WooCommerceProductEntity,
    WooCommerceRefundEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="WooCommerce",
    short_name="woocommerce",
    auth_type=AuthType.config_class,
    auth_config_class="WooCommerceAuthConfig",
    config_class="WooCommerceConfig",
    labels=["E-commerce"],
)
class WooCommerceSource(BaseSource):
    """WooCommerce source implementation.

    This connector retrieves data from various WooCommerce objects, yielding them as entities
    through their respective schemas. The following resource endpoints are used:

      - /wp-json/wc/v3/products
      - /wp-json/wc/v3/orders
      - /wp-json/wc/v3/customers
      - /wp-json/wc/v3/products/categories
      - /wp-json/wc/v3/coupons
      - /wp-json/wc/v3/orders/{id}/refunds

    Each resource endpoint uses WooCommerce's pagination to retrieve all objects.
    Fields are mapped to the entity schemas defined in entities/woocommerce.py.
    """

    @classmethod
    async def create(
        cls, woocommerce_auth_config: WooCommerceAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "WooCommerceSource":
        """Create a new WooCommerce source instance."""
        instance = cls()
        instance.consumer_key = woocommerce_auth_config.consumer_key
        instance.consumer_secret = woocommerce_auth_config.consumer_secret
        instance.store_url = woocommerce_auth_config.store_url
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_with_auth(self, client: httpx.AsyncClient, endpoint: str) -> dict:
        """Make an authenticated GET request to the WooCommerce API.

        Args:
            client: The HTTP client to use
            endpoint: The API endpoint to call (e.g., 'products', 'orders')

        Returns:
            The JSON response from the API
        """
        url = f"{self.store_url}/wp-json/wc/v3/{endpoint}"
        params = {
            "consumer_key": self.consumer_key,
            "consumer_secret": self.consumer_secret,
        }
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _generate_product_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve products from WooCommerce.

        GET /wp-json/wc/v3/products
        Yields WooCommerceProductEntity objects.
        """
        page = 1
        while True:
            data = await self._get_with_auth(client, f"products?page={page}&per_page=100")
            if not data:
                break

            for product in data:
                yield WooCommerceProductEntity(
                    entity_id=str(product["id"]),
                    name=product.get("name"),
                    slug=product.get("slug"),
                    type=product.get("type"),
                    status=product.get("status"),
                    description=product.get("description"),
                    short_description=product.get("short_description"),
                    price=product.get("price"),
                    regular_price=product.get("regular_price"),
                    sale_price=product.get("sale_price"),
                    stock_status=product.get("stock_status"),
                    categories=product.get("categories", []),
                    tags=product.get("tags", []),
                    images=product.get("images", []),
                    attributes=product.get("attributes", []),
                    variations=product.get("variations", []),
                    created_at=product.get("date_created"),
                    updated_at=product.get("date_modified"),
                )

            page += 1

    async def _generate_order_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve orders from WooCommerce.

        GET /wp-json/wc/v3/orders
        Yields WooCommerceOrderEntity objects.
        """
        page = 1
        while True:
            data = await self._get_with_auth(client, f"orders?page={page}&per_page=100")
            if not data:
                break

            for order in data:
                yield WooCommerceOrderEntity(
                    entity_id=str(order["id"]),
                    number=order.get("number"),
                    status=order.get("status"),
                    currency=order.get("currency"),
                    total=order.get("total"),
                    customer_id=order.get("customer_id"),
                    customer_note=order.get("customer_note"),
                    billing=order.get("billing", {}),
                    shipping=order.get("shipping", {}),
                    payment_method=order.get("payment_method"),
                    payment_method_title=order.get("payment_method_title"),
                    line_items=order.get("line_items", []),
                    shipping_lines=order.get("shipping_lines", []),
                    fee_lines=order.get("fee_lines", []),
                    created_at=order.get("date_created"),
                    updated_at=order.get("date_modified"),
                )

            page += 1

    async def _generate_customer_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve customers from WooCommerce.

        GET /wp-json/wc/v3/customers
        Yields WooCommerceCustomerEntity objects.
        """
        page = 1
        while True:
            data = await self._get_with_auth(client, f"customers?page={page}&per_page=100")
            if not data:
                break

            for customer in data:
                yield WooCommerceCustomerEntity(
                    entity_id=str(customer["id"]),
                    email=customer.get("email"),
                    first_name=customer.get("first_name"),
                    last_name=customer.get("last_name"),
                    username=customer.get("username"),
                    billing=customer.get("billing", {}),
                    shipping=customer.get("shipping", {}),
                    is_paying_customer=customer.get("is_paying_customer", False),
                    orders_count=customer.get("orders_count", 0),
                    total_spent=customer.get("total_spent", "0"),
                    created_at=customer.get("date_created"),
                    updated_at=customer.get("date_modified"),
                )

            page += 1

    async def _generate_category_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve product categories from WooCommerce.

        GET /wp-json/wc/v3/products/categories
        Yields WooCommerceCategoryEntity objects.
        """
        page = 1
        while True:
            data = await self._get_with_auth(
                client, f"products/categories?page={page}&per_page=100"
            )
            if not data:
                break

            for category in data:
                yield WooCommerceCategoryEntity(
                    entity_id=str(category["id"]),
                    name=category.get("name"),
                    slug=category.get("slug"),
                    description=category.get("description"),
                    parent=category.get("parent"),
                    count=category.get("count", 0),
                    image=category.get("image", {}),
                    created_at=category.get("date_created"),
                    updated_at=category.get("date_modified"),
                )

            page += 1

    async def _generate_coupon_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve coupons from WooCommerce.

        GET /wp-json/wc/v3/coupons
        Yields WooCommerceCouponEntity objects.
        """
        page = 1
        while True:
            data = await self._get_with_auth(client, f"coupons?page={page}&per_page=100")
            if not data:
                break

            for coupon in data:
                yield WooCommerceCouponEntity(
                    entity_id=str(coupon["id"]),
                    code=coupon.get("code"),
                    amount=coupon.get("amount"),
                    discount_type=coupon.get("discount_type"),
                    description=coupon.get("description"),
                    date_expires=coupon.get("date_expires"),
                    usage_count=coupon.get("usage_count", 0),
                    individual_use=coupon.get("individual_use", False),
                    product_ids=coupon.get("product_ids", []),
                    excluded_product_ids=coupon.get("excluded_product_ids", []),
                    usage_limit=coupon.get("usage_limit"),
                    usage_limit_per_user=coupon.get("usage_limit_per_user"),
                    created_at=coupon.get("date_created"),
                    updated_at=coupon.get("date_modified"),
                )

            page += 1

    async def _generate_refund_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Retrieve refunds from WooCommerce.

        GET /wp-json/wc/v3/orders/{id}/refunds
        Yields WooCommerceRefundEntity objects.
        """
        # First get all orders
        page = 1
        while True:
            orders = await self._get_with_auth(client, f"orders?page={page}&per_page=100")
            if not orders:
                break

            for order in orders:
                order_id = order["id"]
                refunds = await self._get_with_auth(client, f"orders/{order_id}/refunds")

                for refund in refunds:
                    yield WooCommerceRefundEntity(
                        entity_id=str(refund["id"]),
                        order_id=str(order_id),
                        amount=refund.get("amount"),
                        reason=refund.get("reason"),
                        refunded_by=refund.get("refunded_by"),
                        refunded_payment=refund.get("refunded_payment", False),
                        line_items=refund.get("line_items", []),
                        created_at=refund.get("date_created"),
                        updated_at=refund.get("date_modified"),
                    )

            page += 1

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all WooCommerce entities.

        This method yields entities from all WooCommerce resources in sequence.
        """
        async with httpx.AsyncClient() as client:
            # Generate products
            async for entity in self._generate_product_entities(client):
                yield entity

            # Generate orders
            async for entity in self._generate_order_entities(client):
                yield entity

            # Generate customers
            async for entity in self._generate_customer_entities(client):
                yield entity

            # Generate categories
            async for entity in self._generate_category_entities(client):
                yield entity

            # Generate coupons
            async for entity in self._generate_coupon_entities(client):
                yield entity

            # Generate refunds
            async for entity in self._generate_refund_entities(client):
                yield entity
