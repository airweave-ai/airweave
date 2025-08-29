#!/usr/bin/env python3
"""Simple test runner for Monke.

Usage:
    python test.py --config configs/notion.yaml
    python test.py --config configs/github.yaml
    python test.py --config configs/asana.yaml
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
except ImportError:
    print("⚠️  python-dotenv not installed. Using system environment variables only.")
    load_dotenv = None

from monke.core.test_runner import TestRunner
from monke.utils.logging import get_logger


async def run_test(config_path: str, run_id: str | None = None):
    """Run a test with the specified configuration."""
    logger = get_logger("monke_test")

    logger.info(f"🚀 Running test with config: {config_path}")

    # Create test runner
    runner = TestRunner(config_path, run_id=run_id)

    # Run tests
    results = await runner.run_tests()

    # Check results
    success = True
    for result in results:
        if result.success:
            logger.info(f"✅ Test passed | Duration: {result.duration:.2f}s")
        else:
            logger.error("❌ Test failed")
            for error in result.errors:
                logger.error(f"  • {error}")
            success = False

    return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Monke tests")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to test configuration file (e.g., configs/notion.yaml)",
    )
    parser.add_argument(
        "--run-id", required=False, help="Optional run identifier to correlate UI/metrics"
    )
    parser.add_argument(
        "--env", default="env.test", help="Path to environment file (default: env.test)"
    )

    args = parser.parse_args()

    # Load environment variables
    if load_dotenv:
        env_path = Path(__file__).parent / args.env
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ Loaded environment from {env_path}")
        else:
            print(f"⚠️  No environment file at {env_path}, using system environment")
    else:
        print("⚠️  Using system environment variables (install python-dotenv for .env support)")

    # Check if config exists
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).parent / config_path

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    # Run the test
    try:
        success = asyncio.run(run_test(str(config_path), run_id=args.run_id))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
