"""Usage domain factories — backwards compatibility shim.

The factory pattern is no longer used for the checker (it's a singleton).
This file exists only to avoid breaking imports elsewhere.
"""

# Re-export for any old import paths
from airweave.domains.usage.limit_checker import (  # noqa: F401
    AlwaysAllowLimitChecker,
    UsageLimitCheckService,
)
