"""Test flow execution engine with structured events (unique per-step metrics)."""

import time
import os
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
                self.logger.error(
                    f"❌ Cleanup failed after test failure: {cleanup_error}"
                )
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

        try:
            resolved_creds = await resolve_credentials(
                self.config.connector.type, self.config.connector.auth_fields
            )
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
        collection_name = f"monke-{self.config.connector.type}-test-{int(time.time())}"
        collection = airweave_client.collections.create(name=collection_name)
        self.config._collection_id = collection.id
        self.config._collection_readable_id = collection.readable_id

        has_explicit_auth = bool(self.config.connector.auth_fields)
        use_provider = (
            os.getenv("DM_AUTH_PROVIDER") is not None and not has_explicit_auth
        )

        if has_explicit_auth:
            self.logger.info(
                f"🔑 Using explicit auth fields from config for {self.config.connector.type}"
            )
        elif use_provider:
            self.logger.info(f"🔐 Using auth provider: {os.getenv('DM_AUTH_PROVIDER')}")
        else:
            self.logger.info(
                "⚠️  No auth configured - will attempt with empty auth_fields"
            )

        if use_provider:
            auth_provider_id = os.getenv("DM_AUTH_PROVIDER_ID")
            if not auth_provider_id:
                self.logger.warning(
                    "Auth provider requested but DM_AUTH_PROVIDER_ID not set; falling back to explicit auth_fields if provided"
                )
                source_connection = airweave_client.source_connections.create(
                    name=f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                    short_name=self.config.connector.type,
                    collection=self.config._collection_readable_id,
                    auth_fields=(
                        bongo.credentials
                        if hasattr(bongo, "credentials")
                        else self.config.connector.auth_fields
                    ),
                    config_fields=self.config.connector.config_fields,
                )
            else:
                src_upper = self.config.connector.type.upper()
                auth_config_id = os.getenv(f"{src_upper}_AUTH_PROVIDER_AUTH_CONFIG_ID")
                account_id = os.getenv(f"{src_upper}_AUTH_PROVIDER_ACCOUNT_ID")

                # Fallback to global identifiers if source-specific ones are not provided
                if not auth_config_id:
                    auth_config_id = os.getenv("DM_AUTH_PROVIDER_AUTH_CONFIG_ID")
                if not account_id:
                    account_id = os.getenv("DM_AUTH_PROVIDER_ACCOUNT_ID")

                auth_provider_config = None
                if auth_config_id and account_id:
                    auth_provider_config = {
                        "auth_config_id": auth_config_id,
                        "account_id": account_id,
                    }

                if not auth_provider_config:
                    missing = []
                    if not os.getenv(
                        f"{src_upper}_AUTH_PROVIDER_AUTH_CONFIG_ID"
                    ) and not os.getenv("DM_AUTH_PROVIDER_AUTH_CONFIG_ID"):
                        missing.append(
                            f"{src_upper}_AUTH_PROVIDER_AUTH_CONFIG_ID or DM_AUTH_PROVIDER_AUTH_CONFIG_ID"
                        )
                    if not os.getenv(
                        f"{src_upper}_AUTH_PROVIDER_ACCOUNT_ID"
                    ) and not os.getenv("DM_AUTH_PROVIDER_ACCOUNT_ID"):
                        missing.append(
                            f"{src_upper}_AUTH_PROVIDER_ACCOUNT_ID or DM_AUTH_PROVIDER_ACCOUNT_ID"
                        )
                    msg = (
                        "Auth provider is configured but required auth_provider_config is missing. "
                        "Please set: " + ", ".join(missing)
                    )
                    self.logger.error(msg)
                    raise RuntimeError(msg)

                kwargs = dict(
                    name=f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                    short_name=self.config.connector.type,
                    collection=self.config._collection_readable_id,
                    auth_provider=auth_provider_id,
                    # Always pass through any connector config fields
                    config_fields=self.config.connector.config_fields,
                )
                if auth_provider_config:
                    kwargs["auth_provider_config"] = auth_provider_config

                try:
                    source_connection = airweave_client.source_connections.create(
                        **kwargs
                    )
                except Exception as create_err:
                    hint = (
                        "Failed to create source connection via auth provider. "
                        "Verify auth_provider is valid and auth_provider_config contains both "
                        "auth_config_id and account_id."
                    )
                    self.logger.error(f"{hint} Raw error: {create_err}")
                    raise
        else:
            source_connection = airweave_client.source_connections.create(
                name=f"{self.config.connector.type.title()} Test Connection {int(time.time())}",
                short_name=self.config.connector.type,
                collection=self.config._collection_readable_id,
                auth_fields=self.config.connector.auth_fields,
                config_fields=self.config.connector.config_fields,
            )

        self.config._source_connection_id = source_connection.id

    async def cleanup(self) -> bool:
        """Clean up the test environment."""
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

    async def _emit_event(
        self, event_type: str, extra: Optional[Dict[str, Any]] = None
    ) -> None:
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
