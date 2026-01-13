# Connect API Code Review Fixes - Task Notes

## Current Status
Fix 4 (centralize mode checking) is complete. Next tasks: Fix 5, 6, 7, or 8.

## Next Priority: Fix 5 (Exception Handling in _build_source_schema)
Location: `backend/airweave/api/v1/endpoints/connect.py:137-183`

The `_build_source_schema` function currently has a bare `except Exception: return None` that silently swallows all errors. Change to:
- Catch `AttributeError` explicitly (expected for invalid config classes)
- Log unexpected errors with `ctx.logger.error()` before returning None

## Remaining Tasks (in order)
- Fix 5: Exception handling in _build_source_schema (MEDIUM)
- Fix 6: Sanitize SSE error messages (MEDIUM) - line ~741
- Fix 7: Add audit logging for failed authorization (MEDIUM)
- Fix 8: Extract heartbeat constant (MINOR) - line ~722

## Testing Note
E2E tests require environment variables (TEST_STRIPE_API_KEY, etc.) not available in local dev. Use `python3 -m py_compile <file>` to verify syntax.
