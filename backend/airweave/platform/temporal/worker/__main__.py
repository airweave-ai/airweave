"""Entry point for running the worker as a module: python -m airweave.platform.temporal.worker."""

import asyncio

from . import main

if __name__ == "__main__":
    asyncio.run(main())
