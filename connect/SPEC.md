 Summary

 Fix issues identified in code review for the Connect API (all introduced in anand/ENG-1318-connect-api branch).

 Files to Modify

 1. backend/airweave/api/deps.py - Token parsing fixes
 2. backend/airweave/api/v1/endpoints/connect.py - Multiple endpoint fixes

 ---
 Fix 1: Missing KeyError Handling in Token Parsing (CRITICAL)

 File: backend/airweave/api/deps.py:623-631

 Problem: Token payload parsing crashes with 500 instead of 401 if keys are missing.

 Fix: Wrap ConnectSessionContext creation in try/except:

 try:
     return ConnectSessionContext(
         session_id=uuid.UUID(payload["sid"]),
         organization_id=uuid.UUID(payload["oid"]),
         collection_id=payload["cid"],
         allowed_integrations=payload.get("int"),
         mode=mode,
         end_user_id=payload.get("uid"),
         expires_at=datetime.fromtimestamp(payload["ts"] + 600, tz=timezone.utc),
     )
 except (KeyError, ValueError) as e:
     raise HTTPException(status_code=401, detail="Invalid session token payload") from e

 ---
 Fix 2: Extract Bearer Token Utility (Enables Fix 3)

 File: backend/airweave/api/deps.py (add before get_connect_session)

 Problem: Bearer token parsing is duplicated in deps.py:605-608 and connect.py:563.

 Fix: Add utility function:

 def extract_bearer_token(authorization: str) -> str:
     """Extract token from Bearer authorization header."""
     if not authorization.startswith("Bearer "):
         raise HTTPException(status_code=401, detail="Invalid authorization header format")
     return authorization[7:]

 Then update get_connect_session to use it:
 token = extract_bearer_token(authorization)

 ---
 Fix 3: Dynamic Pydantic Attributes (HIGH)

 File: backend/airweave/api/v1/endpoints/connect.py:561-573

 Problem: Private attributes dynamically assigned to Pydantic model.

 Fix: Use explicit setattr with documentation (minimal change):

 # Extract token using shared utility
 from airweave.api.deps import extract_bearer_token
 session_token = extract_bearer_token(authorization)

 # Attach connect session data for OAuth callback validation
 # Note: These temporary attributes are consumed by create_init_session for OAuth flows
 connect_context = {
     "session_id": str(session.session_id),
     "organization_id": str(session.organization_id),
     "collection_id": session.collection_id,
     "end_user_id": session.end_user_id,
 }
 setattr(source_connection_in, "_connect_session_token", session_token)
 setattr(source_connection_in, "_connect_session_context", connect_context)

 ---
 Fix 4: Centralize Mode Checking Logic (MEDIUM)

 File: backend/airweave/api/v1/endpoints/connect.py (add at top, after imports)

 Problem: Mode checks duplicated with slight variations across endpoints.

 Fix: Add constants and helper:

 from typing import FrozenSet

 # Mode permission sets
 MODES_VIEW: FrozenSet[schemas.ConnectSessionMode] = frozenset({
     schemas.ConnectSessionMode.ALL,
     schemas.ConnectSessionMode.MANAGE,
     schemas.ConnectSessionMode.REAUTH,
 })
 MODES_CREATE: FrozenSet[schemas.ConnectSessionMode] = frozenset({
     schemas.ConnectSessionMode.ALL,
     schemas.ConnectSessionMode.CONNECT,
 })
 MODES_DELETE: FrozenSet[schemas.ConnectSessionMode] = frozenset({
     schemas.ConnectSessionMode.ALL,
     schemas.ConnectSessionMode.MANAGE,
 })

 def _check_session_mode(
     session: ConnectSessionContext,
     allowed_modes: FrozenSet[schemas.ConnectSessionMode],
     operation: str,
 ) -> None:
     """Validate session mode allows the requested operation."""
     if session.mode not in allowed_modes:
         raise HTTPException(
             status_code=403,
             detail=f"Session mode does not allow {operation}",
         )

 Update endpoints:
 - list_source_connections: _check_session_mode(session, MODES_VIEW, "viewing source connections")
 - get_source_connection: _check_session_mode(session, MODES_VIEW, "viewing source connections")
 - delete_source_connection: _check_session_mode(session, MODES_DELETE, "deleting source connections")
 - create_source_connection: _check_session_mode(session, MODES_CREATE, "creating source connections")

 ---
 Fix 5: Improve Exception Handling in _build_source_schema (MEDIUM)

 File: backend/airweave/api/v1/endpoints/connect.py:137-183

 Problem: Silently catches ALL exceptions with except Exception: return None.

 Fix: Be specific and log unexpected errors:

 async def _build_source_schema(
     source: schemas.Source,
     ctx: ApiContext,
 ) -> Optional[schemas.Source]:
     """Build a Source schema with auth_fields and config_fields."""
     try:
         # ... existing code until line 180 ...
         return schemas.Source.model_validate(source_dict)

     except AttributeError:
         # Expected: source has invalid config_class or auth_config_class
         return None
     except Exception as e:
         # Unexpected error - log for investigation
         ctx.logger.error(f"Unexpected error building source schema for {source.short_name}: {e}")
         return None

 ---
 Fix 6: Sanitize SSE Error Messages (MEDIUM)

 File: backend/airweave/api/v1/endpoints/connect.py:739-741

 Problem: Raw exception messages may leak internal system details.

 Fix: Add sanitization:

 # At module level (after imports)
 def _sanitize_sse_error(error: Exception) -> str:
     """Return a safe error message for SSE client consumption."""
     if isinstance(error, HTTPException):
         return error.detail
     return "An unexpected error occurred"

 # In event_stream() exception handler:
 except Exception as e:
     logger.error(f"SSE error for job {job_id}: {str(e)}")
     safe_message = _sanitize_sse_error(e)
     yield f"data: {json.dumps({'type': 'error', 'message': safe_message})}\n\n"

 ---
 Fix 7: Add Audit Logging for Failed Authorization (MEDIUM)

 File: backend/airweave/api/v1/endpoints/connect.py

 Problem: No logging when users try to access denied integrations.

 Fix: Add logging at authorization failure points. Example for get_source (line ~244):

 if session.allowed_integrations and short_name not in session.allowed_integrations:
     ctx.logger.warning(
         f"Access denied: attempted to access restricted source '{short_name}'"
     )
     raise HTTPException(...)

 Apply similar pattern to:
 - create_source_connection (line ~544)
 - get_source_connection (line ~435)
 - delete_source_connection (line ~478)
 - get_connection_jobs (line ~637)
 - subscribe_to_connection_sync (line ~693)

 ---
 Fix 8: Extract Heartbeat Constant (MINOR)

 File: backend/airweave/api/v1/endpoints/connect.py:722

 Problem: Hardcoded heartbeat_interval = 30.

 Fix: Add module-level constant:

 # At top of file (after imports)
 SSE_HEARTBEAT_INTERVAL_SECONDS = 30

 # In event_stream():
 heartbeat_interval = SSE_HEARTBEAT_INTERVAL_SECONDS

 ---
 Implementation Order

- [x] Fix 2 (extract_bearer_token utility) - enables other fixes
- [x] Fix 1 (KeyError handling) - critical security fix
- [x] Fix 3 (Pydantic attributes) - uses new utility
- [x] Fix 4 (mode checking) - improves code structure
- [x] Fix 5 (exception handling) - improves debugging
- [x] Fix 6 (SSE errors) - security improvement
- [x] Fix 7 (audit logging) - uses centralized mode checks
- [ ] Fix 8 (heartbeat constant) - minor cleanup

 ---
 Verification

 1. Run existing tests: pytest backend/tests/e2e/smoke/test_connect_sessions.py -v
 2. Test KeyError handling: Create a malformed token and verify 401 response
 3. Test mode restrictions: Verify each mode only allows its permitted operations
 4. Test SSE: Connect to SSE endpoint and verify heartbeats/error handling
 5. Check logs: Verify authorization failures are logged