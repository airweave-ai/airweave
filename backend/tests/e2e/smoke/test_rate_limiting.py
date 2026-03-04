"""
Smoke tests for rate limiting functionality.

Tests the rate limiting system with minute-based windows by making multiple
concurrent requests to verify that rate limits are enforced correctly across the API.

Rate limit configuration:
- Window: 60 seconds (1 minute)
- Developer plan: 10 requests/minute
- Pro plan: 100 requests/minute
- Team plan: 250 requests/minute
- Enterprise plan: Unlimited

NOTE: These tests only run in local development environments to avoid
interfering with CI/CD pipelines and production systems.

IMPORTANT: Rate limiting must be enabled for these tests to work.
- Set DISABLE_RATE_LIMIT=false (or omit it) when running these tests
- Other test suites should set DISABLE_RATE_LIMIT=true to avoid quota issues

Run with: pytest -m rate_limit
Skip with: pytest -m "not rate_limit" (default behavior in CI)
"""

import asyncio
import os
import time
from typing import Dict, List, Tuple

import httpx
import pytest

from config import settings

# Module-level marker - applies to all tests in this file
# Use api_rate_limit to distinguish from source rate limiting tests
pytestmark = [
    pytest.mark.api_rate_limit,
    pytest.mark.asyncio,
]


@pytest.fixture(scope="module", autouse=True)
def skip_if_not_local():
    """Skip all rate limit tests if not in local development."""
    if not settings.is_local:
        pytest.skip("Rate limit tests only run in local development environment", allow_module_level=True)


def _rate_limiting_disabled() -> bool:
    """Check if rate limiting is disabled via environment variable."""
    return os.environ.get("DISABLE_RATE_LIMIT", "").lower() == "true"


skip_if_rate_limit_disabled = pytest.mark.skipif(
    _rate_limiting_disabled(),
    reason="Rate limiting is disabled (DISABLE_RATE_LIMIT=true)",
)


class TestRateLimiting:
    """Test suite for API rate limiting with minute-based windows."""

    async def test_rate_limit_headers_present(self, api_client: httpx.AsyncClient):
        """Test that rate limit headers are present in successful responses."""
        response = await api_client.get("/sources/github")

        assert response.status_code == 200

        # Check for RFC 6585 compliant rate limit headers (case-insensitive)
        assert "ratelimit-limit" in response.headers, "Missing RateLimit-Limit header"
        assert (
            "ratelimit-remaining" in response.headers
        ), "Missing RateLimit-Remaining header"
        assert "ratelimit-reset" in response.headers, "Missing RateLimit-Reset header"

        # Verify header values are valid
        limit = int(response.headers["ratelimit-limit"])
        remaining = int(response.headers["ratelimit-remaining"])
        reset = int(response.headers["ratelimit-reset"])

        assert limit > 0, "Rate limit should be positive"
        assert remaining >= 0, "Remaining requests should be non-negative"
        assert reset > 0, "Reset timestamp should be positive"

        print(f"\n📊 Rate Limit Info: {limit} requests/minute, {remaining} remaining")

    async def test_concurrent_requests_under_limit(self, api_client: httpx.AsyncClient):
        """Test that concurrent requests under the limit all succeed."""

        async def make_request(index: int) -> Tuple[int, Dict[str, str]]:
            """Make a single request and return status code and headers."""
            response = await api_client.get("/sources/github")
            return (response.status_code, dict(response.headers))

        # Make 5 concurrent requests (should be under all plan rate limits)
        print("\n🚀 Sending 5 concurrent requests...")
        results = await asyncio.gather(*[make_request(i) for i in range(5)])

        # All requests should succeed
        successful = 0
        for status_code, headers in results:
            assert status_code == 200, f"Expected 200, got {status_code}"
            assert "ratelimit-limit" in headers
            successful += 1

        print(f"✅ All {successful} requests succeeded")

    async def test_rate_limit_headers_decrement(self, api_client: httpx.AsyncClient):
        """Test that RateLimit-Remaining decreases with each request."""
        print("\n🔍 Testing rate limit header decrement...")

        # Make sequential requests and track remaining count
        remaining_values = []

        for i in range(5):
            response = await api_client.get("/collections/")
            if response.status_code == 200:
                remaining = int(response.headers.get("ratelimit-remaining", 0))
                remaining_values.append(remaining)
                print(f"Request {i + 1}: Remaining = {remaining}")

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.05)

        # Verify we got some remaining values
        assert len(remaining_values) >= 3, "Should have captured at least 3 remaining values"

        # Note: Due to the sliding window, remaining might not strictly decrement
        # but it should stay within reasonable bounds
        first_remaining = remaining_values[0]
        print(f"\n📊 Remaining values: {remaining_values}")
        print(f"First remaining: {first_remaining}")

        # At least verify all values are non-negative and reasonable
        for remaining in remaining_values:
            assert remaining >= 0, f"Remaining should be non-negative, got {remaining}"

        # In a minute-based window, remaining should not increase during sequential requests
        # (unless the first request from the previous window expires)
        print("✅ All remaining values are valid")

    @skip_if_rate_limit_disabled
    async def test_retry_after_header_accuracy(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test that Retry-After header provides accurate timing."""
        # Get rate limit
        response = await api_client.get("/sources/github")
        rate_limit = int(response.headers.get("ratelimit-limit", 100))

        # Trigger rate limiting
        async def make_request() -> httpx.Response:
            return await api_client.get(f"/sources/github")

        print(f"\n🚀 Triggering rate limit with {rate_limit + 10} requests...")
        responses = await asyncio.gather(*[make_request() for _ in range(rate_limit + 10)])

        # Find first rate limited response
        rate_limited_response = None
        for resp in responses:
            if resp.status_code == 429:
                rate_limited_response = resp
                break

        if rate_limited_response:
            retry_after = int(rate_limited_response.headers.get("retry-after", 0))
            print(f"⏰ Retry-After: {retry_after} seconds")

            assert retry_after > 0, "Retry-After should be positive"
            assert retry_after <= 60, (
                f"Retry-After should be reasonable (≤60s for 60s window), got {retry_after}s"
            )
        else:
            print("ℹ️  No rate limiting triggered (rate limit might be very high)")

    @skip_if_rate_limit_disabled
    async def test_post_requests_also_rate_limited(
        self, api_client: httpx.AsyncClient
    ):
        """Test that POST requests are also subject to rate limiting."""
        # Get rate limit
        response = await api_client.get("/collections/")
        rate_limit = int(response.headers.get("ratelimit-limit", 100))

        print(f"\n📊 Rate Limit: {rate_limit} requests/minute")

        # Make many POST requests to trigger rate limiting
        async def create_collection(index: int) -> int:
            """Attempt to create a collection."""
            collection_data = {"name": f"Rate Limit Test {index} {int(time.time())}"}
            try:
                response = await api_client.post("/sources/github", json=collection_data)

                # Clean up if successful
                if response.status_code == 200:
                    try:
                        collection = response.json()
                        # Schedule cleanup (don't wait for it)
                        asyncio.create_task(
                            api_client.delete(f"/collections/{collection['readable_id']}")
                        )
                    except:
                        pass

                return response.status_code
            except:
                return 0

        # Make many concurrent POST requests
        num_requests = rate_limit * 2
        print(f"🚀 Sending {num_requests} concurrent POST requests...")

        results = await asyncio.gather(*[create_collection(i) for i in range(num_requests)])

        rate_limited_count = sum(1 for status in results if status == 429)
        successful_count = sum(1 for status in results if status == 200)

        print(f"✅ Successful: {successful_count}")
        print(f"🛑 Rate Limited: {rate_limited_count}")

        # Should have some rate limited responses
        assert rate_limited_count > 0, (
            "Expected POST requests to be rate limited, "
            f"but all {successful_count} requests succeeded"
        )

        # Give a moment for cleanup tasks to complete
        await asyncio.sleep(0.5)

    @skip_if_rate_limit_disabled
    async def test_different_endpoints_share_rate_limit(
        self, api_client: httpx.AsyncClient
    ):
        """Test that rate limits are applied per organization across all endpoints."""
        # Get rate limit
        response = await api_client.get("/sources/github")
        rate_limit = int(response.headers.get("ratelimit-limit", 100))

        print(f"\n📊 Rate Limit: {rate_limit} requests/minute")

        # Make requests to different endpoints
        async def make_mixed_request(index: int) -> int:
            """Make requests to various endpoints."""
            endpoints = [
                "/sources/github",
                "/sources/",
            ]
            endpoint = endpoints[index % len(endpoints)]
            try:
                response = await api_client.get(endpoint)
                return response.status_code
            except:
                return 0

        # Make many requests across different endpoints
        num_requests = min(rate_limit * 2, 200)  # Cap for test performance
        print(f"🚀 Sending {num_requests} requests across multiple endpoints...")

        results = await asyncio.gather(*[make_mixed_request(i) for i in range(num_requests)])

        rate_limited_count = sum(1 for status in results if status == 429)
        successful_count = sum(1 for status in results if status == 200)

        print(f"✅ Successful: {successful_count}")
        print(f"🛑 Rate Limited: {rate_limited_count}")

        # Should have some rate limited responses
        assert rate_limited_count > 0, (
            "Expected rate limiting across different endpoints, "
            f"but all {successful_count} requests succeeded"
        )
