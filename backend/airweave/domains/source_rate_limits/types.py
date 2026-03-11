"""Value types and constants for source rate limit domain."""

# Pipedream proxy defaults (from Pipedream docs).
# Shared by both the config service and the runtime Redis limiter.
PIPEDREAM_PROXY_LIMIT = 1000
PIPEDREAM_PROXY_WINDOW = 300  # 5 minutes
