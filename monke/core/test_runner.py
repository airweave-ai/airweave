"""Core test runner that orchestrates the entire testing process (fixed duration calc)."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from monke.core.test_config import TestConfig
from monke.core.test_flow import TestFlow
from monke.utils.logging import get_logger


@dataclass
class TestResult:
    """Result of a test execution."""

    success: bool
    duration: float
    metrics: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


def _compute_duration(metrics: Dict[str, Any]) -> float:
    """
    Prefer a single wall-clock measurement if present; otherwise sum only per-step durations.
    Avoid double counting and ignore non-numeric / boolean values.
    """
    wall = metrics.get("total_duration_wall_clock")
    if isinstance(wall, (int, float)):
        return float(wall)

    # Fallback: sum per-step durations only (keys ending with "_duration")
    total = 0.0
    for k, v in metrics.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if k.endswith("_duration"):
            total += float(v)
    return total


class TestRunner:
    """Main test runner that orchestrates the entire testing process."""

    def __init__(self, config_path: str, run_id: Optional[str] = None):
        """Initialize the test runner.

        Args:
            config_path: Path to the test configuration file
        """
        self.config = TestConfig.from_file(config_path)
        self.logger = get_logger("test_runner")
        self.run_id = run_id

    async def run_tests(self) -> List[TestResult]:
        """Run all configured tests."""
        self.logger.info(f"🚀 Starting test run: {self.config.name}")
        self.logger.info(f"📝 Description: {self.config.description}")
        self.logger.info(f"🔗 Connector: {self.config.connector.type}")

        test_flow: Optional[TestFlow] = None
        try:
            # Create and set up the flow
            test_flow = TestFlow.create(self.config, run_id=self.run_id)
            if not await test_flow.setup():
                raise Exception("Failed to setup test environment")

            # Execute flow
            await test_flow.execute()

            # Clean up
            await test_flow.cleanup()

            # Build result with corrected duration
            metrics = test_flow.get_metrics()
            duration = _compute_duration(metrics)

            result = TestResult(
                success=True,
                duration=duration,
                metrics=metrics,
                errors=[],
                warnings=test_flow.get_warnings(),
            )
            return [result]

        except Exception as e:
            raise e
            self.logger.error(f"❌ Test execution failed: {e}")

            # Ensure cleanup happens even on failure
            if test_flow:
                try:
                    self.logger.info("🧹 Attempting emergency cleanup after test failure...")
                    await test_flow.cleanup()
                    self.logger.info("✅ Emergency cleanup completed")
                except Exception as cleanup_error:
                    self.logger.error(f"❌ Emergency cleanup failed: {cleanup_error}")

            result = TestResult(
                success=False,
                duration=0.0,
                metrics={},
                errors=[str(e)],
                warnings=[],
            )
            return [result]
