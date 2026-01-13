# Connect API Code Review Fixes - Task Notes

## Current Status
Fix 6 (sanitize SSE errors) is complete. Next tasks: Fix 7 or Fix 8.

## Next Priority: Fix 7 (Add Audit Logging for Failed Authorization)
Location: `backend/airweave/api/v1/endpoints/connect.py`

Add `ctx.logger.warning()` calls at 6 locations where authorization fails due to restricted integrations:
1. `get_source` (~line 251) - "Access denied: attempted to access restricted source"
2. `create_source_connection` (~line 551) - same pattern
3. `get_source_connection` (~line 442) - same pattern
4. `delete_source_connection` (~line 485) - same pattern
5. `get_connection_jobs` (~line 644) - same pattern
6. `subscribe_to_connection_sync` (~line 700) - same pattern

Pattern to add before each HTTPException raise:
```python
ctx.logger.warning(
    f"Access denied: attempted to access restricted source '{short_name}'"
)
```

See SPEC.md Fix 7 for exact details.

## Remaining Tasks (in order)
- Fix 7: Add audit logging for failed authorization (MEDIUM) - ~6 locations
- Fix 8: Extract heartbeat constant (MINOR) - line ~733

## Testing Note
E2E tests require environment variables not available in local dev. Use `python3 -m py_compile <file>` to verify syntax.
