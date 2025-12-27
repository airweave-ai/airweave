"""Infrastructure management for test execution."""

import os
import time
from typing import Dict, Any

from monke.core.config import TestConfig
from monke.core.context import TestContext
from monke.core import http_utils
from monke.utils.logging import get_logger

logger = get_logger("infrastructure")


def setup_test_infrastructure(config: TestConfig, context: TestContext) -> None:
    """Set up test infrastructure (collection and source connection).

    Args:
        config: Test configuration
        context: Test context to populate with infrastructure IDs
    """
    # Create collection using HTTP API
    collection_name = f"monke-{config.connector.type}-test-{int(time.time())}"
    collection = _create_collection(collection_name)
    context.collection_id = collection["id"]
    context.collection_readable_id = collection["readable_id"]
    logger.info(f"✅ Created test collection: {collection_name}")

    # Create source connection
    connection_payload = _build_connection_payload(config, context)
    source_connection = _create_source_connection(connection_payload)
    context.source_connection_id = source_connection["id"]

    # Capture sync_id for raw data verification
    sync_id = source_connection.get("sync_id")
    if sync_id:
        context.sync_id = str(sync_id)
        logger.info(f"📦 Captured sync_id for raw data verification: {context.sync_id}")

    logger.info(f"✅ Created source connection: {context.source_connection_id}")


def teardown_test_infrastructure(context: TestContext) -> None:
    """Clean up test infrastructure.

    Args:
        context: Test context with infrastructure IDs
    """
    logger.info("🧹 Cleaning up test infrastructure")

    # Delete source connection if exists
    if context.source_connection_id:
        try:
            response = http_utils.http_delete(f"/source-connections/{context.source_connection_id}")
            if response.status_code in [200, 204]:
                logger.info("✅ Deleted source connection")
            elif response.status_code == 404:
                logger.info("ℹ️  Source connection already deleted")
            else:
                logger.error(f"❌ Failed to delete source connection: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Failed to delete source connection: {e}")

    # Delete collection if exists
    if context.collection_readable_id:
        try:
            response = http_utils.http_delete(f"/collections/{context.collection_readable_id}")
            if response.status_code in [200, 204]:
                logger.info("✅ Deleted test collection")
            elif response.status_code == 404:
                logger.info("ℹ️  Collection already deleted")
            else:
                logger.error(f"❌ Failed to delete collection: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Failed to delete collection: {e}")


def _build_connection_payload(config: TestConfig, context: TestContext) -> Dict[str, Any]:
    """Build the payload for creating a source connection.

    Args:
        config: Test configuration
        context: Test context with bongo and collection info

    Returns:
        Dictionary payload for source connection creation
    """
    base_payload = {
        "name": f"{config.connector.type.title()} Test {int(time.time())}",
        "short_name": config.connector.type,
        "readable_collection_id": context.collection_readable_id,
        "config": config.connector.config_fields,
        "schedule": {"cron": None},  # Disable automatic schedules for tests
    }

    # Handle authentication based on mode
    if config.connector.auth_mode == "direct":
        logger.info(f"🔑 Using direct auth for {config.connector.type}")

        # Get credentials from bongo or config
        credentials = {}
        if hasattr(context.bongo, "credentials"):
            credentials = context.bongo.credentials
        elif config.connector.auth_fields:
            credentials = config.connector.resolve_auth_fields()

        base_payload["authentication"] = {"credentials": credentials}

    elif config.connector.auth_mode == "composio":
        logger.info("🔐 Using Composio auth provider")

        composio_provider_id = os.getenv("MONKE_COMPOSIO_PROVIDER_ID")
        if not composio_provider_id:
            raise RuntimeError(
                "Composio auth mode configured but MONKE_COMPOSIO_PROVIDER_ID not set"
            )

        if not config.connector.composio_config:
            raise RuntimeError(
                f"Composio auth mode configured for {config.connector.type} "
                "but composio_config not provided"
            )

        base_payload["authentication"] = {
            "provider_readable_id": composio_provider_id,
            "provider_config": {
                "auth_config_id": config.connector.composio_config.auth_config_id,
                "account_id": config.connector.composio_config.account_id,
            },
        }
    else:
        # Fallback - try to get whatever credentials are available
        logger.warning(f"⚠️ No auth mode specified for {config.connector.type}")
        credentials = {}
        if hasattr(context.bongo, "credentials"):
            credentials = context.bongo.credentials
        base_payload["authentication"] = {"credentials": credentials}

    return base_payload


def _create_collection(name: str) -> Dict[str, Any]:
    """Create a collection via HTTP.

    Args:
        name: Collection name

    Returns:
        Created collection data
    """
    try:
        return http_utils.http_post("/collections", json={"name": name})
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        raise


def _create_source_connection(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a source connection via HTTP.

    Args:
        payload: Source connection creation payload

    Returns:
        Created source connection data
    """
    try:
        return http_utils.http_post("/source-connections", json=payload)
    except Exception as e:
        logger.error(f"Failed to create source connection: {e}")
        raise
