# Connect API Code Review Fixes - Task Notes

## Current Status
Fix 7 (audit logging) is complete. Only Fix 8 remains.

## Next Priority: Fix 8 (Extract Heartbeat Constant)
Location: `backend/airweave/api/v1/endpoints/connect.py`

This is a minor cleanup:
1. Add module-level constant at top of file (after other constants like MODES_*):
   ```python
   SSE_HEARTBEAT_INTERVAL_SECONDS = 30
   ```
2. Update line ~747 (in `event_stream()` function) to use the constant:
   ```python
   heartbeat_interval = SSE_HEARTBEAT_INTERVAL_SECONDS
   ```

See SPEC.md Fix 8 for exact details.

## Remaining Tasks
- Fix 8: Extract heartbeat constant (MINOR) - 2 small changes

## Testing Note
E2E tests require environment variables not available in local dev. Use `python3 -m py_compile <file>` to verify syntax.
