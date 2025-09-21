"""Stripe-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class StripeBongo(BaseBongo):
    """Stripe-specific bongo implementation.

    Creates, updates, and deletes test customers via the real Stripe API.
    """

    connector_type = "stripe"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Stripe bongo.

        Args:
            credentials: Stripe credentials with api_key
            **kwargs: Additional configuration (e.g., entity_count)
        """
        super().__init__(credentials)
        self.api_key = credentials["api_key"]

        # Configuration from kwargs
        self.entity_count = kwargs.get('entity_count', 10)
        self.llm_model = kwargs.get("llm_model", None)

        # Test data tracking
        self.test_customers = []

        # Rate limiting (Stripe: 100 requests per second in test mode)
        self.last_request_time = 0
        self.rate_limit_delay = 0.1  # 0.1 second between requests

        # Logger
        self.logger = get_logger("stripe_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test customers in Stripe."""
        self.logger.info(f"🥁 Creating {self.entity_count} test customers in Stripe")
        entities = []

        # Create customers based on configuration
        from monke.generation.stripe import generate_stripe_artifact

        for i in range(self.entity_count):
            # Short unique token used in name and metadata for verification
            token = str(uuid.uuid4())[:8]

            name, email, description = await generate_stripe_artifact(self.llm_model, token)

            # Create customer
            customer_data = await self._create_test_customer(
                name,
                email,
                description,
                token
            )

            entities.append({
                "type": "customer",
                "id": customer_data["id"],
                "name": name,
                "email": email,
                "token": token,
                "expected_content": token,
            })

            self.logger.info(f"💳 Created test customer: {customer_data['id']}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.1)

        self.test_customers = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Stripe."""
        self.logger.info("🥁 Updating test customers in Stripe")
        updated_entities = []

        # Update a subset of customers based on configuration
        from monke.generation.stripe import generate_stripe_artifact
        customers_to_update = min(3, self.entity_count)  # Update max 3 customers for any test size

        for i in range(customers_to_update):
            if i < len(self.test_customers):
                customer_info = self.test_customers[i]
                token = customer_info.get("token") or str(uuid.uuid4())[:8]

                # Generate new content with same token
                name, email, description = await generate_stripe_artifact(
                    self.llm_model, token, is_update=True
                )

                # Update customer
                await self._update_test_customer(
                    customer_info["id"],
                    name,
                    description
                )

                updated_entities.append({
                    "type": "customer",
                    "id": customer_info["id"],
                    "name": name,
                    "email": customer_info["email"],  # Email can't be changed
                    "token": token,
                    "expected_content": token,
                    "updated": True,
                })

                self.logger.info(f"📝 Updated test customer: {customer_info['id']}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.1)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Stripe."""
        self.logger.info("🥁 Deleting all test customers from Stripe")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Stripe."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific customers from Stripe")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test customer
                test_customer = next((tc for tc in self.test_customers if tc["id"] == entity["id"]), None)

                if test_customer:
                    await self._delete_test_customer(test_customer["id"])
                    deleted_ids.append(test_customer["id"])
                    self.logger.info(f"🗑️ Deleted test customer: {test_customer['id']}")
                else:
                    self.logger.warning(f"⚠️ Could not find test customer for entity: {entity.get('id')}")

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if customers are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if customers are actually deleted from Stripe")
        for entity in entities:
            if entity["id"] in deleted_ids:
                is_deleted = await self._verify_customer_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(f"✅ Customer {entity['id']} confirmed deleted from Stripe")
                else:
                    self.logger.warning(f"⚠️ Customer {entity['id']} still exists in Stripe!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test customers in Stripe")

        # Force delete any remaining test customers
        for test_customer in self.test_customers:
            try:
                await self._force_delete_customer(test_customer["id"])
                self.logger.info(f"🧹 Force deleted customer: {test_customer['id']}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not force delete customer {test_customer['id']}: {e}")

    # Helper methods for Stripe API calls
    async def _create_test_customer(
        self,
        name: str,
        email: str,
        description: str,
        token: str
    ) -> Dict[str, Any]:
        """Create a test customer via Stripe API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.stripe.com/v1/customers",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "name": name,
                    "email": email,
                    "description": description,
                    "metadata[monke_token]": token,
                    "metadata[test]": "true"
                }
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create customer: {response.status_code} - {response.text}")

            result = response.json()

            # Track created customer
            self.created_entities.append({
                "id": result["id"],
                "email": result["email"]
            })

            return result

    async def _update_test_customer(
        self,
        customer_id: str,
        name: str,
        description: str
    ):
        """Update a test customer via Stripe API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.stripe.com/v1/customers/{customer_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "name": name,
                    "description": description
                }
            )

            if response.status_code != 200:
                raise Exception(f"Failed to update customer: {response.status_code} - {response.text}")

    async def _delete_test_customer(self, customer_id: str):
        """Delete a test customer via Stripe API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.stripe.com/v1/customers/{customer_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}"
                }
            )

            if response.status_code != 200:
                raise Exception(f"Failed to delete customer: {response.status_code} - {response.text}")

    async def _verify_customer_deleted(self, customer_id: str) -> bool:
        """Verify if a customer is actually deleted from Stripe."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.stripe.com/v1/customers/{customer_id}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )

                if response.status_code == 404:
                    # Customer not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Check if customer is deleted
                    data = response.json()
                    return data.get("deleted", False)
                else:
                    # Unexpected response
                    self.logger.warning(f"⚠️ Unexpected response checking {customer_id}: {response.status_code}")
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying customer deletion for {customer_id}: {e}")
            return False

    async def _force_delete_customer(self, customer_id: str):
        """Force delete a customer."""
        try:
            await self._delete_test_customer(customer_id)
        except Exception as e:
            self.logger.warning(f"Could not force delete {customer_id}: {e}")

    async def _rate_limit(self):
        """Implement rate limiting for Stripe API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
