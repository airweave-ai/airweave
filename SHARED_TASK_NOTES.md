# Connect API Code Review Fixes - Task Notes

## Current Status
Fix 5 (exception handling in _build_source_schema) is complete. Next tasks: Fix 6, 7, or 8.

## Next Priority: Fix 6 (Sanitize SSE Error Messages)
Location: `backend/airweave/api/v1/endpoints/connect.py:~741`

The SSE event_stream exception handler currently sends raw exception messages to the client, which may leak internal details. The fix:
1. Add a `_sanitize_sse_error` helper function at module level
2. Update the exception handler in `event_stream()` to use it
3. HTTPException details can be returned as-is; other exceptions get a generic message

See SPEC.md Fix 6 for the exact implementation.

## Remaining Tasks (in order)
- Fix 6: Sanitize SSE error messages (MEDIUM) - security improvement
- Fix 7: Add audit logging for failed authorization (MEDIUM) - ~6 locations
- Fix 8: Extract heartbeat constant (MINOR) - line ~722

## Testing Note
E2E tests require environment variables (TEST_STRIPE_API_KEY, etc.) not available in local dev. Use `python3 -m py_compile <file>` to verify syntax.
