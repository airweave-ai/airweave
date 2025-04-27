"""WooCommerce source implementation"""

import logging
from typing import AsyncGenerator, Dict, Any, Optional
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities.woocommerce import WooCommerceProductEntity, WooCommerceOrderEntity
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source("WooCommerce", "woocommerce", AuthType.api_key)
class WooCommerceSource(BaseSource):
    """WooCommerce source integration for fetching products and orders."""

    BASE_URL: Optional[str] = None

    @classmethod
    async def create(cls, access_token: str, base_url: str) -> "WooCommerceSource":
        instance = cls()
        instance.access_token = access_token
        instance.base_url = base_url.rstrip("/") + "/"
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _make_request(self, endpoint: str, page: int = 1) -> Dict[str, Any]:
        """Make an authenticated GET request to the WooCommerce API with retries."""
        url = f"{self.base_url}{endpoint}"
        params = {
            "consumer_key": self.access_token,
            "consumer_secret": self.access_token,
            "per_page": 100,
            "page": page,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            logger.debug(f"Requesting {url} with params {params}")
            response.raise_for_status()
            return response.json()

    async def _fetch_all_pages(self, endpoint: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Helper to paginate through all pages of results."""
        page = 1
        while True:
            items = await self._make_request(endpoint, page=page)
            if not items:
                break

            for item in items:
                yield item

            page += 1

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate WooCommerce entities."""

        # Fetch Products
        async for product in self._fetch_all_pages("products"):
            yield WooCommerceProductEntity(
                entity_id=str(product["id"]),
                name=product.get("name", ""),
                price=product.get("price"),
                description=product.get("description"),
                sku=product.get("sku"),
                categories=[cat.get("name") for cat in product.get("categories", [])],
                images=[img.get("src") for img in product.get("images", [])],
            )

        # Fetch Orders
        async for order in self._fetch_all_pages("orders"):
            yield WooCommerceOrderEntity(
                entity_id=str(order["id"]),
                status=order.get("status", ""),
                total=order.get("total", ""),
                currency=order.get("currency", ""),
                customer_id=str(order.get("customer_id")),
                line_items=order.get("line_items", []),
            )