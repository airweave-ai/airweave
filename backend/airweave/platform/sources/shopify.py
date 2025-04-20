"""Shopify source implementation."""

from typing import AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.shopify import (
    ShopifyCustomerEntity,
    ShopifyFileEntity,
    ShopifyOrderEntity,
    ShopifyProductEntity,
    ShopifyShopEntity,
)
from airweave.platform.file_handling.file_manager import file_manager
from airweave.platform.sources._base import BaseSource


@source("Shopify", "shopify", AuthType.oauth2_with_refresh, labels=["Marketing" , "CRM" , "Customer Service"])
class ShopifySource(BaseSource):
    """Shopify source implementation."""

    @classmethod
    async def create(cls, access_token: str, shop_domain: str) -> "ShopifySource":
        """Create a new Shopify source."""
        instance = cls()
        instance.access_token = access_token
        instance.shop_domain = shop_domain  # e.g., example.myshopify.com
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_with_auth(self, client: httpx.AsyncClient, endpoint: str) -> Dict:
        """Make authenticated GET request to Shopify API."""
        url = f"https://{self.shop_domain}/admin/api/2024-04{endpoint}"
        response = await client.get(
            url,
            headers={"X-Shopify-Access-Token": self.access_token},
        )
        response.raise_for_status()
        return response.json()

    async def _generate_shop_entity(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate shop entity."""
        shop_data = await self._get_with_auth(client, "/shop.json")
        shop = shop_data.get("shop", {})

        yield ShopifyShopEntity(
            entity_id=str(shop["id"]),
            breadcrumbs=[],
            name=shop.get("name"),
            shop_id=shop["id"],
            domain=shop.get("domain"),
            email=shop.get("email"),
            currency=shop.get("currency"),
            country=shop.get("country"),
            created_at=shop.get("created_at"),
            updated_at=shop.get("updated_at"),
            plan_name=shop.get("plan_name"),
            timezone=shop.get("timezone"),
            enabled_features=shop.get("enabled_features", []),
        )

    async def _generate_product_entities(
        self, client: httpx.AsyncClient, shop: Dict, shop_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate product entities for a shop."""
        products_data = await self._get_with_auth(client, "/products.json?limit=250")

        for product in products_data.get("products", []):
            yield ShopifyProductEntity(
                entity_id=str(product["id"]),
                breadcrumbs=[shop_breadcrumb],
                title=product.get("title"),
                product_id=product["id"],
                shop_id=shop["id"],
                shop_domain=self.shop_domain,
                body_html=product.get("body_html"),
                vendor=product.get("vendor"),
                product_type=product.get("product_type"),
                created_at=product.get("created_at"),
                updated_at=product.get("updated_at"),
                published_at=product.get("published_at"),
                status=product.get("status"),
                tags=product.get("tags", "").split(", ") if product.get("tags") else [],
                variants=product.get("variants", []),
                images=product.get("images", []),
                options=product.get("options", []),
                handle=product.get("handle"),
                metafields=product.get("metafields", []),
            )

    async def _generate_order_entities(
        self, client: httpx.AsyncClient, shop: Dict, shop_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate order entities for a shop."""
        orders_data = await self._get_with_auth(client, "/orders.json?limit=250")

        for order in orders_data.get("orders", []):
            yield ShopifyOrderEntity(
                entity_id=str(order["id"]),
                breadcrumbs=[shop_breadcrumb],
                order_id=order["id"],
                shop_id=shop["id"],
                shop_domain=self.shop_domain,
                email=order.get("email"),
                created_at=order.get("created_at"),
                updated_at=order.get("updated_at"),
                total_price=order.get("total_price"),
                currency=order.get("currency"),
                financial_status=order.get("financial_status"),
                fulfillment_status=order.get("fulfillment_status"),
                customer=order.get("customer"),
                line_items=order.get("line_items", []),
                billing_address=order.get("billing_address"),
                shipping_address=order.get("shipping_address"),
                note=order.get("note"),
                tags=order.get("tags", "").split(", ") if order.get("tags") else [],
                metafields=order.get("metafields", []),
            )

    async def _generate_customer_entities(
        self, client: httpx.AsyncClient, shop: Dict, shop_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate customer entities for a shop."""
        customers_data = await self._get_with_auth(client, "/customers.json?limit=250")

        for customer in customers_data.get("customers", []):
            yield ShopifyCustomerEntity(
                entity_id=str(customer["id"]),
                breadcrumbs=[shop_breadcrumb],
                customer_id=customer["id"],
                shop_id=shop["id"],
                shop_domain=self.shop_domain,
                first_name=customer.get("first_name"),
                last_name=customer.get("last_name"),
                email=customer.get("email"),
                phone=customer.get("phone"),
                created_at=customer.get("created_at"),
                updated_at=customer.get("updated_at"),
                state=customer.get("state"),
                verified_email=customer.get("verified_email", False),
                addresses=customer.get("addresses", []),
                tags=customer.get("tags", "").split(", ") if customer.get("tags") else [],
                metafields=customer.get("metafields", []),
            )

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        product: Dict,
        product_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file entities (e.g., product images) for a product."""
        images = product.get("images", [])

        for image in images:
            if not image.get("src"):
                logger.warning(
                    f"No source URL found for image {image['id']} in product {product['id']}"
                )
                continue

            file_entity = ShopifyFileEntity(
                entity_id=str(image["id"]),
                breadcrumbs=product_breadcrumbs,
                file_id=image["id"],
                shop_id=product["id"],
                shop_domain=self.shop_domain,
                resource_type="image",
                src=image.get("src"),
                created_at=image.get("created_at"),
                updated_at=image.get("updated_at"),
                alt=image.get("alt"),
                parent={"resource_type": "product", "id": product["id"]},
                metafields=image.get("metafields", []),
            )

            # Stream the file from the image URL
            file_stream = file_manager.stream_file_from_url(file_entity.src)
            yield await file_manager.handle_file_entity(stream=file_stream, entity=file_entity)

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Shopify."""
        async with httpx.AsyncClient() as client:
            async for shop_entity in self._generate_shop_entity(client):
                yield shop_entity

                shop_breadcrumb = Breadcrumb(
                    entity_id=str(shop_entity.shop_id),
                    name=shop_entity.name,
                    type="shop",
                )

                # Generate products
                async for product_entity in self._generate_product_entities(
                    client,
                    {"id": shop_entity.shop_id},
                    shop_breadcrumb,
                ):
                    yield product_entity

                    product_breadcrumb = Breadcrumb(
                        entity_id=str(product_entity.product_id),
                        name=product_entity.title,
                        type="product",
                    )
                    product_breadcrumbs = [shop_breadcrumb, product_breadcrumb]

                    # Generate file entities (e.g., images) for the product
                    async for file_entity in self._generate_file_entities(
                        client,
                        {
                            "id": product_entity.product_id,
                            "images": product_entity.images,
                        },
                        product_breadcrumbs,
                    ):
                        yield file_entity

                # Generate orders
                async for order_entity in self._generate_order_entities(
                    client,
                    {"id": shop_entity.shop_id},
                    shop_breadcrumb,
                ):
                    yield order_entity

                # Generate customers
                async for customer_entity in self._generate_customer_entities(
                    client,
                    {"id": shop_entity.shop_id},
                    shop_breadcrumb,
                ):
                    yield customer_entity