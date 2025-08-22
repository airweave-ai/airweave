"""
Test module for Sources endpoints.

This module tests the sources listing and detail endpoints including:
- Listing all available sources
- Getting specific source details
- Validating source structure (auth_fields, config_fields)
- Error handling for non-existent sources
"""

import requests


def test_sources(api_url: str, headers: dict) -> None:
    """Test sources endpoints - list and detail."""
    print("\n🔄 Testing Sources Endpoints")

    # LIST: Get all available sources
    print("  Listing all sources...")
    response = requests.get(f"{api_url}/sources/list", headers=headers)
    assert response.status_code == 200, f"Failed to list sources: {response.text}"

    sources = response.json()
    assert isinstance(sources, list), "Sources response should be an array"
    assert len(sources) > 0, "No sources available"

    # Verify first source has required structure
    first_source = sources[0]
    required_fields = [
        "id",
        "name",
        "short_name",
        "auth_config_class",
        "config_class",
        "class_name",
        "auth_fields",
        "created_at",
        "modified_at",
    ]
    for field in required_fields:
        assert field in first_source, f"Source missing required field: {field}"

    # Find Stripe source
    stripe_source = next((s for s in sources if s["short_name"] == "stripe"), None)
    assert stripe_source is not None, "Stripe source not found in sources list"

    print(f"  ✓ Found {len(sources)} sources, including Stripe")

    # Validate Stripe source structure
    assert stripe_source["auth_config_class"] == "StripeAuthConfig", "Unexpected auth config class"
    assert stripe_source["config_class"] == "StripeConfig", "Unexpected config class"

    # Validate auth_fields (required and must have fields)
    assert stripe_source["auth_fields"] is not None, "auth_fields is required"
    assert "fields" in stripe_source["auth_fields"], "auth_fields must have 'fields'"
    assert len(stripe_source["auth_fields"]["fields"]) > 0, "auth_fields cannot be empty"

    # Find and validate api_key field
    auth_fields = stripe_source["auth_fields"]["fields"]
    api_key_field = next((f for f in auth_fields if f["name"] == "api_key"), None)
    assert api_key_field is not None, "Stripe must have 'api_key' auth field"

    # Validate api_key field properties
    assert api_key_field["type"] == "string", "api_key must be string type"
    assert "title" in api_key_field, "api_key must have title"
    assert "description" in api_key_field, "api_key must have description"
    assert api_key_field["name"] == "api_key", "Field name should be 'api_key'"

    # Validate config_fields (can be None or empty for Stripe)
    if stripe_source.get("config_fields"):
        assert (
            "fields" in stripe_source["config_fields"]
        ), "config_fields must have 'fields' if present"

    print("  ✓ Stripe source structure validated")

    # DETAIL: Get specific source details
    print("  Getting Stripe source details...")
    response = requests.get(f"{api_url}/sources/detail/stripe", headers=headers)
    assert response.status_code == 200, f"Failed to get Stripe source details: {response.text}"

    stripe_detail = response.json()

    # Verify detail has all required fields
    for field in required_fields:
        assert field in stripe_detail, f"Detail response missing field: {field}"

    # Verify consistency between list and detail
    assert stripe_detail["id"] == stripe_source["id"], "ID mismatch between list and detail"
    assert stripe_detail["name"] == stripe_source["name"], "Name mismatch"
    assert stripe_detail["short_name"] == "stripe", "Short name mismatch"
    assert (
        stripe_detail["auth_config_class"] == stripe_source["auth_config_class"]
    ), "Auth config class mismatch"
    assert stripe_detail["config_class"] == stripe_source["config_class"], "Config class mismatch"

    # Verify auth_fields match
    detail_api_key = next(
        (f for f in stripe_detail["auth_fields"]["fields"] if f["name"] == "api_key"), None
    )
    assert detail_api_key is not None, "Detail response missing api_key field"
    assert detail_api_key == api_key_field, "api_key field mismatch between list and detail"

    print("  ✓ Stripe source details match list response")

    # ERROR HANDLING: Test non-existent source
    print("  Testing error handling...")
    response = requests.get(f"{api_url}/sources/detail/nonexistent", headers=headers)
    assert (
        response.status_code == 404
    ), f"Expected 404 for non-existent source, got {response.status_code}"

    # Verify error response structure
    error_response = response.json()
    assert "detail" in error_response, "Error response should have 'detail' field"
    assert (
        "nonexistent" in error_response["detail"].lower()
    ), "Error message should mention the source name"

    print("  ✓ Error handling works correctly")

    print("✅ Sources endpoints test completed successfully")
