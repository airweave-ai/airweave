"""Test flow execution engine with structured events (unique per-step metrics)."""

import time
import os
from types import SimpleNamespace
import httpx
from typing import Any, Dict, List, Optional

from monke.core.config import TestConfig
from monke.core.steps import TestStepFactory
from monke.utils.logging import get_logger
from monke.core import events


class TestFlow:
    """Executes a test flow based on configuration."""

    def __init__(self, config: TestConfig, run_id: Optional[str] = None):
        """Initialize the test flow."""
        self.config = config
        self.logger = get_logger(f"test_flow.{config.name}")
        self.step_factory = TestStepFactory()
        self.metrics: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.run_id = run_id or f"run-{int(time.time() * 1000)}"
        self._step_idx = 0  # ensure unique metric keys

    @classmethod
    def create(cls, config: TestConfig, run_id: Optional[str] = None) -> "TestFlow":
        return cls(config, run_id=run_id)

    async def execute(self):
        """Execute the test flow."""
        self.logger.info(f"🚀 Executing test flow: {self.config.name}")
        self.logger.info(f"🔄 Test flow steps: {self.config.test_flow.steps}")
        await self._emit_event(
            "flow_started",
            extra={
                "name": self.config.name,
                "connector": self.config.connector.type,
                "steps": self.config.test_flow.steps,
                "entity_count": self.config.entity_count,
            },
        )

        flow_start = time.time()
        try:
            for step_name in self.config.test_flow.steps:
                await self._execute_step(step_name)

            self.logger.info(f"✅ Test flow completed: {self.config.name}")
            self.metrics["total_duration_wall_clock"] = time.time() - flow_start
            await self._emit_event("flow_completed")
        except Exception as e:
            self.logger.error(f"❌ Test flow execution failed: {e}")
            self.metrics["total_duration_wall_clock"] = time.time() - flow_start
            try:
                await self.cleanup()
                pass
            except Exception as cleanup_error:
                self.logger.error(f"❌ Cleanup failed after test failure: {cleanup_error}")
            raise

    async def _execute_step(self, step_name: str):
        """Execute a single test step."""
        self._step_idx += 1
        idx = self._step_idx
        self.logger.info(f"🔄 Executing step: {step_name}")
        await self._emit_event("step_started", extra={"step": step_name, "index": idx})

        step = self.step_factory.create_step(step_name, self.config)
        start_time = time.time()

        try:
            await step.execute()
            duration = time.time() - start_time

            self.metrics[f"{idx:02d}_{step_name}_duration"] = duration
            self.logger.info(f"✅ Step {step_name} completed in {duration:.2f}s")
            await self._emit_event(
                "step_completed",
                extra={"step": step_name, "index": idx, "duration": duration},
            )

        except Exception as e:
            duration = time.time() - start_time
            self.metrics[f"{idx:02d}_{step_name}_duration"] = duration
            self.metrics[f"{idx:02d}_{step_name}_failed"] = True
            await self._emit_event(
                "step_failed",
                extra={
                    "step": step_name,
                    "index": idx,
                    "duration": duration,
                    "error": str(e),
                },
            )
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get test execution metrics."""
        return self.metrics.copy()

    def get_warnings(self) -> List[str]:
        """Get test execution warnings."""
        return self.warnings.copy()

    async def setup(self) -> bool:
        """Set up the test environment."""
        self.logger.info("🔧 Setting up test environment")
        await self._emit_event("setup_started")

        from monke.bongos.registry import BongoRegistry
        from monke.auth.credentials_resolver import resolve_credentials
        from monke.auth.broker import ComposioBroker

        try:
            # Resolve credentials based on auth mode
            if self.config.connector.auth_mode == "composio":
                broker = ComposioBroker(
                    account_id=self.config.connector.composio_config.account_id,
                    auth_config_id=self.config.connector.composio_config.auth_config_id,
                )
                resolved_creds = await broker.get_credentials(self.config.connector.type)
            else:
                # For direct mode, resolve auth fields from environment variables
                if self.config.connector.auth_fields:
                    # Resolve the environment variables to actual values
                    resolved_creds = self.config.connector.resolve_auth_fields()
                else:
                    # No auth fields provided, let resolve_credentials handle it
                    resolved_creds = await resolve_credentials(self.config.connector.type, None)

            bongo = BongoRegistry.create(
                self.config.connector.type,
                resolved_creds,
                entity_count=self.config.entity_count,
                **self.config.connector.config_fields,
            )
            self.config._bongo = bongo

            from airweave import AirweaveSDK

            airweave_client = AirweaveSDK(
                base_url=os.getenv("AIRWEAVE_API_URL", "http://localhost:8001"),
                api_key=os.getenv("AIRWEAVE_API_KEY"),
            )
            self.config._airweave_client = airweave_client

            await self._setup_infrastructure(bongo, airweave_client)

            self.logger.info("✅ Test environment setup completed")
            await self._emit_event("setup_completed")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to setup test environment: {e}")
            await self._emit_event("setup_failed", extra={"error": str(e)})
            return False

    async def _setup_infrastructure(self, bongo, airweave_client):
        def _create_source_connection_via_http(
            payload: Dict[str, Any],
        ) -> SimpleNamespace:
            base_url = os.getenv("AIRWEAVE_API_URL", "http://localhost:8001").rstrip("/")
            headers = {"Content-Type": "application/json"}
            api_key = os.getenv("AIRWEAVE_API_KEY")
            if api_key:
                headers["x-api-key"] = api_key

            try:
                response = httpx.post(
                    f"{base_url}/source-connections",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Log the error details for debugging
                self.logger.error(f"Failed to create source connection: {e}")
                self.logger.error(f"Response body: {e.response.text}")
                raise

            data = response.json()
            return SimpleNamespace(id=data.get("id"))

        collection_name = f"monke-{self.config.connector.type}-test-{int(time.time())}"
        collection = airweave_client.collections.create(name=collection_name)
        self.config._collection_id = collection.id
        self.config._collection_readable_id = collection.readable_id

        # Check auth mode from config
        if self.config.connector.auth_mode == "direct":
            self.logger.info(
                f"🔑 Using direct auth (explicit auth fields) for {self.config.connector.type}"
            )
            # Direct auth - use credentials from bongo or auth_fields
            # The schema expects just "credentials" field for DirectAuthentication
            credentials = (
                bongo.credentials
                if hasattr(bongo, "credentials")
                else self.config.connector.resolve_auth_fields()
            )

            # Log what we're sending (hide sensitive values)
            self.logger.info(f"📋 Sending auth with {len(credentials)} credential fields")
            self.logger.info(f"Credential keys: {list(credentials.keys())}")
            # Debug: Show first few chars of api_key to verify it's loaded
            if "api_key" in credentials and credentials["api_key"]:
                key_preview = (
                    credentials["api_key"][:10] + "..."
                    if len(credentials["api_key"]) > 10
                    else "SHORT_KEY"
                )
                self.logger.info(f"API key preview: {key_preview}")

            payload = {
                "name": f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                "short_name": self.config.connector.type,
                "readable_collection_id": self.config._collection_readable_id,
                "authentication": {"credentials": credentials},
                "config": self.config.connector.config_fields,
            }

            source_connection = _create_source_connection_via_http(payload)
        elif self.config.connector.auth_mode == "composio":
            self.logger.info("🔐 Using Composio auth provider")

            # Get Composio provider ID from environment
            composio_provider_id = os.getenv("COMPOSIO_PROVIDER_ID")
            if not composio_provider_id:
                raise RuntimeError(
                    "Composio auth mode configured but COMPOSIO_PROVIDER_ID not set. "
                    "Ensure COMPOSIO_API_KEY is configured."
                )

            # Get auth config from the YAML config
            if not self.config.connector.composio_config:
                raise RuntimeError(
                    f"Composio auth mode configured for {self.config.connector.type} "
                    "but composio_config not provided in YAML"
                )

            auth_provider_config = {
                "auth_config_id": self.config.connector.composio_config.auth_config_id,
                "account_id": self.config.connector.composio_config.account_id,
            }

            # New API (v0.6) via HTTP: pass auth provider via nested authentication
            payload = {
                "name": f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                "short_name": self.config.connector.type,
                "readable_collection_id": self.config._collection_readable_id,
                "authentication": {
                    "provider_readable_id": composio_provider_id,
                    "provider_config": auth_provider_config,
                },
                "config": self.config.connector.config_fields,
            }

            source_connection = _create_source_connection_via_http(payload)
        else:
            # Fallback - no auth mode specified, use empty credentials or what's available
            self.logger.info(
                f"⚠️ No auth mode specified for {self.config.connector.type}, using fallback"
            )

            # Try to get credentials from bongo or config
            credentials = {}
            if hasattr(bongo, "credentials"):
                credentials = bongo.credentials
            elif self.config.connector.auth_fields:
                try:
                    credentials = self.config.connector.resolve_auth_fields()
                except Exception:
                    credentials = {}

            source_connection = _create_source_connection_via_http(
                {
                    "name": f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                    "short_name": self.config.connector.type,
                    "readable_collection_id": self.config._collection_readable_id,
                    "authentication": {"credentials": credentials},
                    "config": self.config.connector.config_fields,
                }
            )

        self.config._source_connection_id = source_connection.id

    async def cleanup(self) -> bool:
        """Clean up the test environment."""
        self.logger.info("🧹 Cleanup skipped")
        return True
        try:
            self.logger.info("🧹 Cleaning up test environment")
            await self._emit_event("cleanup_started")

            # Try to delete source connection if it exists
            # Note: It may already be deleted if the collection was deleted first
            if hasattr(self.config, "_source_connection_id"):
                try:
                    self.config._airweave_client.source_connections.delete(
                        self.config._source_connection_id
                    )
                    self.logger.info("✅ Deleted source connection")
                except Exception as e:
                    # Check if it's a 404 error (already deleted)
                    if "404" in str(e) or "not found" in str(e).lower():
                        self.logger.info(
                            "ℹ️  Source connection already deleted (likely with collection)"
                        )
                    else:
                        # Re-raise if it's a different error
                        raise

            # Try to delete collection if it exists
            if hasattr(self.config, "_collection_readable_id"):
                try:
                    self.config._airweave_client.collections.delete(
                        self.config._collection_readable_id
                    )
                    self.logger.info("✅ Deleted test collection")
                except Exception as e:
                    # Check if it's a 404 error (already deleted)
                    if "404" in str(e) or "not found" in str(e).lower():
                        self.logger.info("ℹ️  Collection already deleted")
                    else:
                        # Re-raise if it's a different error
                        raise

            self.logger.info("✅ Test environment cleanup completed")
            await self._emit_event("cleanup_completed")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup test environment: {e}")
            await self._emit_event("cleanup_failed", extra={"error": str(e)})
            return False

    async def _emit_event(self, event_type: str, extra: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {
            "type": event_type,
            "run_id": self.run_id,
            "ts": time.time(),
            "connector": self.config.connector.type,
        }
        if extra:
            payload.update(extra)
        try:
            await events.publish(payload)
        except Exception:
            pass
