"""Test flow execution engine with structured events (unique per-step metrics)."""

import time
from typing import Any, Dict, List, Optional

from monke.core.config import TestConfig
from monke.core.context import TestContext
from monke.core.steps import TestStepFactory
from monke.core import services, infrastructure
from monke.utils.logging import get_logger
from monke.core import events


class TestFlow:
    """Executes a test flow based on configuration."""

    def __init__(self, config: TestConfig, run_id: Optional[str] = None):
        """Initialize the test flow."""
        self.config = config
        self.context = TestContext()  # Clean separation of runtime state
        self.logger = get_logger(f"test_flow.{config.name}")
        self.step_factory = TestStepFactory()
        self.run_id = run_id or f"run-{int(time.time() * 1000)}"
        self._step_idx = 0  # ensure unique metric keys

    @classmethod
    def create(cls, config: TestConfig, run_id: Optional[str] = None) -> "TestFlow":
        return cls(config, run_id=run_id)

    async def execute(self):
        """Execute the test flow."""
        # Print narrative test flow summary
        self.logger.info("=" * 80)
        self.logger.info(f"🚀 TEST FLOW: {self.config.name}")
        self.logger.info("=" * 80)
        self.logger.info(f"📡 Connector: {self.config.connector.type}")
        self.logger.info(f"📦 Test Entities: {self.config.entity_count}")
        self.logger.info(f"🔄 Total Steps: {len(self.config.test_flow.steps)}")
        self.logger.info("")
        self.logger.info("📋 Test Flow Roadmap:")

        # Show step-by-step roadmap
        step_descriptions = {
            "cleanup": "Clean up any leftover test data",
            "create": "Create test entities in source system",
            "sync": "Sync data from source to vector database",
            "force_full_sync": "Force full sync (ignore cursor, fetch all entities)",
            "verify": "Verify entities appear in vector database",
            "verify_raw_data": "Verify raw data captured to local storage",
            "update": "Update existing test entities",
            "partial_delete": "Delete subset of test entities",
            "verify_partial_deletion": "Verify deleted entities are removed",
            "verify_remaining_entities": "Verify non-deleted entities still exist",
            "complete_delete": "Delete all remaining test entities",
            "verify_complete_deletion": "Verify all entities are removed",
        }

        for i, step in enumerate(self.config.test_flow.steps, 1):
            description = step_descriptions.get(step, "Execute step")
            self.logger.info(f"   {i}. {step:<25} → {description}")

        self.logger.info("=" * 80)
        self.logger.info("")

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
            for step_idx, step_name in enumerate(self.config.test_flow.steps, 1):
                await self._execute_step(step_name, step_idx, len(self.config.test_flow.steps))

            total_duration = time.time() - flow_start
            self.context.metrics["total_duration_wall_clock"] = total_duration

            # Final summary
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info(f"✅ TEST FLOW COMPLETED: {self.config.name}")
            self.logger.info("=" * 80)
            self.logger.info(f"⏱️  Total Duration: {total_duration:.2f}s")
            self.logger.info(f"📊 Steps Executed: {len(self.config.test_flow.steps)}")
            self.logger.info("🎯 Test Status: PASSED")
            self.logger.info("=" * 80)

            await self._emit_event("flow_completed")
        except Exception as e:
            self.logger.error(f"❌ Test flow execution failed: {e}")
            self.context.metrics["total_duration_wall_clock"] = time.time() - flow_start
            try:
                await self.cleanup()
            except Exception as cleanup_error:
                self.logger.error(
                    f"❌ Cleanup failed after test failure: {cleanup_error}"
                )
            raise

    async def _execute_step(self, step_name: str, step_idx: int = 0, total_steps: int = 0):
        """Execute a single test step."""
        self._step_idx += 1
        idx = self._step_idx

        # Show progress
        if step_idx > 0 and total_steps > 0:
            self.logger.info("")
            self.logger.info(f"📍 PROGRESS: Step {step_idx}/{total_steps} - {step_name.upper()}")
            self.logger.info("")
        else:
            self.logger.info(f"🔄 Executing step: {step_name}")

        await self._emit_event("step_started", extra={"step": step_name, "index": idx})

        # Pass both config and context to steps
        step = self.step_factory.create_step(step_name, self.config, self.context)
        start_time = time.time()

        try:
            await step.execute()
            duration = time.time() - start_time

            self.context.metrics[f"{idx:02d}_{step_name}_duration"] = duration
            self.logger.info(f"✅ Step {step_name} completed in {duration:.2f}s")
            await self._emit_event(
                "step_completed",
                extra={"step": step_name, "index": idx, "duration": duration},
            )

        except Exception as e:
            duration = time.time() - start_time
            self.context.metrics[f"{idx:02d}_{step_name}_duration"] = duration
            self.context.metrics[f"{idx:02d}_{step_name}_failed"] = True
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
        return self.context.metrics.copy()

    def get_warnings(self) -> List[str]:
        """Get test execution warnings."""
        return self.context.warnings.copy()

    async def setup(self) -> bool:
        """Set up the test environment."""
        self.logger.info("🔧 Setting up test environment")
        await self._emit_event("setup_started")

        try:
            # Initialize services (bongo and airweave client)
            await services.initialize_services(self.config, self.context)

            # Set up infrastructure (collection and source connection)
            infrastructure.setup_test_infrastructure(self.config, self.context)

            self.logger.info("✅ Test environment setup completed")
            await self._emit_event("setup_completed")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to setup test environment: {e}")
            await self._emit_event("setup_failed", extra={"error": str(e)})
            return False

    async def cleanup(self) -> bool:
        """Clean up the test environment."""
        try:
            self.logger.info("🧹 Cleaning up test environment")
            await self._emit_event("cleanup_started")

            # Use the infrastructure module for cleanup
            infrastructure.teardown_test_infrastructure(self.context)

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
