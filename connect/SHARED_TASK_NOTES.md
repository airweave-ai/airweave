# Connect API Code Review Fixes - Progress Notes

## Completed This Iteration (Jan 13, 2026)

Implemented Fixes 1, 2, and 3:

1. **Fix 2**: Added `extract_bearer_token()` utility function to `backend/airweave/api/deps.py:583-597`
2. **Fix 1**: Added KeyError/ValueError handling around ConnectSessionContext creation in `deps.py:637-648`
3. **Fix 3**: Updated `connect.py:561-574` to use the new utility and explicit `setattr()` for Pydantic attributes

## Next Up

Continue with Fix 4 (mode checking centralization) - this is the next item in the implementation order.

Key locations:
- Mode check helper should go near top of `connect.py` after imports
- Update these endpoints to use the new helper:
  - `list_source_connections`
  - `get_source_connection`
  - `delete_source_connection`
  - `create_source_connection`

## Testing

Could not run pytest directly (missing virtual environment setup). Verified Python syntax is valid for both modified files. Full testing should be done when the project environment is properly set up:

```bash
pytest backend/tests/e2e/smoke/test_connect_sessions.py -v
```
