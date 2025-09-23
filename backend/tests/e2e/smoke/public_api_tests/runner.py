"""
Main test runner for the Public API Test Suite.

This runner orchestrates the sequential execution of all test modules,
maintaining the dependencies between tests and passing data between them.

Usage:
    # Set environment variables first:
    export STRIPE_API_KEY=sk_test_...
    export OPENAI_API_KEY=...  # Optional for local
    export AIRWEAVE_API_KEY=... # Required for dev/prod

    # Required test environment variables:
    export TEST_NOTION_TOKEN=...
    export TEST_GOOGLE_CLIENT_ID=...
    export TEST_GOOGLE_CLIENT_SECRET=...
    export TEST_AUTH_PROVIDER_NAME=composio
    export TEST_COMPOSIO_API_KEY=...
    export TEST_COMPOSIO_AUTH_CONFIG_ID=...  # From Composio for Asana
    export TEST_COMPOSIO_ACCOUNT_ID=...      # From Composio for Asana

    # Then run:
    python runner.py --env local
    python runner.py --env dev
    python runner.py --env prod
"""

import argparse
import os
import sys
from typing import Optional

from .utils import setup_environment
from .test_environment import validate_environment
from .test_sources import test_sources
from .test_collections import test_collections
from .test_source_connections import test_source_connections
from .test_search import test_search_functionality
from .test_cleanup import test_cleanup


def parse_arguments():
    """Parse command line arguments and environment variables."""
    parser = argparse.ArgumentParser(
        description="Test Airweave Public API",
        epilog="""
Environment variables:
  STRIPE_API_KEY              Stripe API key (required)
  OPENAI_API_KEY              OpenAI API key (optional for local)
  AIRWEAVE_API_KEY            API key for dev/prod environments
  SKIP_STARTUP                Skip running start.sh (default: false)

Required test variables:
  TEST_NOTION_TOKEN           Notion OAuth access token
  TEST_GOOGLE_CLIENT_ID       Google OAuth client ID for BYOC
  TEST_GOOGLE_CLIENT_SECRET   Google OAuth client secret for BYOC
  TEST_AUTH_PROVIDER_NAME     Auth provider name (must be 'composio')
  TEST_COMPOSIO_API_KEY       Composio API key
  TEST_COMPOSIO_AUTH_CONFIG_ID Composio auth config ID for Asana connection
  TEST_COMPOSIO_ACCOUNT_ID    Composio account ID for Asana connection
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        default="local",
        help="Environment to test against (default: local)",
    )

    parser.add_argument(
        "--skip-startup",
        action="store_true",
        help="Skip running start.sh and container health checks (assumes services are already running)",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require all optional environment variables to be set (fail if any are missing)",
    )

    args = parser.parse_args()

    # Get API keys from environment variables
    args.stripe_api_key = os.environ.get("STRIPE_API_KEY")
    args.openai_api_key = os.environ.get("OPENAI_API_KEY")
    args.api_key = os.environ.get("AIRWEAVE_API_KEY")

    # Check SKIP_STARTUP environment variable if not set via command line
    if not args.skip_startup:
        args.skip_startup = os.environ.get("SKIP_STARTUP", "false").lower() in ["true", "1", "yes"]

    # Validate Stripe API key (always required)
    if not args.stripe_api_key:
        print("❌ Error: STRIPE_API_KEY environment variable is required")
        print("   Set it with: export STRIPE_API_KEY=sk_test_...")
        sys.exit(1)

    # Validate Stripe API key format
    if not args.stripe_api_key.startswith("sk_"):
        print("❌ Error: STRIPE_API_KEY must start with 'sk_' (e.g., sk_test_... or sk_live_...)")
        sys.exit(1)

    # Validate API key for dev/prod environments
    if args.env in ["dev", "prod"] and not args.api_key:
        print(
            f"❌ Error: AIRWEAVE_API_KEY environment variable is required for {args.env} environment"
        )
        print("   Set it with: export AIRWEAVE_API_KEY=your_api_key")
        sys.exit(1)

    # Optional warning for local environment without OpenAI key
    if args.env == "local" and not args.openai_api_key:
        print("⚠️  Warning: OPENAI_API_KEY not set. Some features may be limited.")
        print("   Set it with: export OPENAI_API_KEY=your_key")

    # Check for required test environment variables
    required_test_vars = [
        ("TEST_NOTION_TOKEN", "Notion OAuth token injection"),
        ("TEST_GOOGLE_CLIENT_ID", "Google OAuth BYOC flow"),
        ("TEST_GOOGLE_CLIENT_SECRET", "Google OAuth BYOC flow"),
        ("TEST_AUTH_PROVIDER_NAME", "Auth provider testing (must be 'composio')"),
        ("TEST_COMPOSIO_API_KEY", "Composio auth provider API key"),
        ("TEST_COMPOSIO_AUTH_CONFIG_ID", "Composio auth config ID for Asana"),
        ("TEST_COMPOSIO_ACCOUNT_ID", "Composio account ID for Asana"),
    ]

    missing_required_vars = []
    for var_name, feature in required_test_vars:
        if not os.environ.get(var_name):
            missing_required_vars.append((var_name, feature))

    if missing_required_vars:
        print("\n❌ Required test environment variables not set:")
        for var_name, feature in missing_required_vars:
            print(f"   - {var_name}: Required for {feature}")
        print("\n   All these variables MUST be set for the test suite to run.")
        sys.exit(1)

    # Validate TEST_AUTH_PROVIDER_NAME is set to 'composio'
    if (
        os.environ.get("TEST_AUTH_PROVIDER_NAME")
        and os.environ.get("TEST_AUTH_PROVIDER_NAME") != "composio"
    ):
        print(
            f"\n❌ Error: TEST_AUTH_PROVIDER_NAME must be 'composio', got '{os.environ.get('TEST_AUTH_PROVIDER_NAME')}'"
        )
        sys.exit(1)

    return args


def main():
    """Main test execution orchestrator."""
    args = parse_arguments()

    # Validate environment first
    if not validate_environment(args.env, require_all_optional=args.strict):
        print("\n❌ Environment validation failed. Please fix the issues above and try again.")
        sys.exit(1)

    # Show skip-startup status if enabled
    if args.skip_startup:
        print("\n⚡ Skip-startup mode enabled - assuming services are already running")
        print("   (Use --skip-startup flag or set SKIP_STARTUP=true to enable)")

    # Setup environment
    api_url = setup_environment(args.env, args.openai_api_key, skip_startup=args.skip_startup)
    if not api_url:
        print("❌ Failed to setup environment")
        sys.exit(1)

    # Configure headers with correct x-api-key format
    headers = {"Content-Type": "application/json", "accept": "application/json"}
    if args.api_key:
        headers["x-api-key"] = args.api_key

    print(f"\n🚀 Ready to test {args.env} environment at {api_url}")

    # Track created resources for summary
    created_resources = {}

    try:
        # Run tests in sequence (order matters due to dependencies)

        # 1. Test sources endpoints (independent)
        test_sources(api_url, headers)

        # 2. Test collections CRUD (returns readable_id for next tests)
        readable_id = test_collections(api_url, headers)
        created_resources["collection"] = readable_id

        # 3. Test source connections (uses collection from step 2)
        source_conn_id1, source_conn_id2 = test_source_connections(
            api_url, headers, readable_id, args.stripe_api_key
        )
        created_resources["source_conn_1"] = source_conn_id1
        created_resources["source_conn_2"] = source_conn_id2

        # 4. Test search functionality (searches in synced data)
        test_search_functionality(api_url, headers, readable_id)

        # 5. Test cleanup (deletes all created resources)
        test_cleanup(api_url, headers, readable_id, source_conn_id1, source_conn_id2)

        print("\n✅ All tests completed successfully!")

        # Print summary
        print(f"\n📋 Test artifacts created and cleaned up:")
        print(f"  - Collection: {created_resources.get('collection', 'N/A')}")
        print(
            f"  - Source connections: {created_resources.get('source_conn_1', 'N/A')}, {created_resources.get('source_conn_2', 'N/A')}"
        )
        print("\n💡 Note: All test data was cleaned up successfully")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        print("\n🔍 Test failure details:")
        print(f"   Error type: AssertionError")
        print(f"   Error message: {str(e)}")

        # Attempt cleanup on failure
        print("\n🧹 Attempting to clean up created resources...")
        try:
            if "collection" in created_resources:
                # Try to clean up whatever was created
                test_cleanup(
                    api_url,
                    headers,
                    created_resources.get("collection", ""),
                    created_resources.get("source_conn_1", ""),
                    created_resources.get("source_conn_2", ""),
                )
                print("✓ Cleanup successful")
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup failed: {cleanup_error}")
            print("  Please manually delete test resources:")
            print(f"  Collection: {created_resources.get('collection', 'N/A')}")
            print(
                f"  Source connections: {created_resources.get('source_conn_1', 'N/A')}, {created_resources.get('source_conn_2', 'N/A')}"
            )

        print("\n❌ TEST SUITE FAILED - Exiting with error code 1")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("\n🔍 Error details:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")

        import traceback

        print("\n📝 Stack trace:")
        traceback.print_exc()

        # Attempt cleanup on unexpected error
        if created_resources:
            print("\n🧹 Attempting to clean up created resources...")
            try:
                if "collection" in created_resources:
                    test_cleanup(
                        api_url,
                        headers,
                        created_resources.get("collection", ""),
                        created_resources.get("source_conn_1", ""),
                        created_resources.get("source_conn_2", ""),
                    )
                    print("✓ Cleanup successful")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup failed: {cleanup_error}")
                print("  Please manually delete test resources")

        print("\n❌ TEST SUITE FAILED - Exiting with error code 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
