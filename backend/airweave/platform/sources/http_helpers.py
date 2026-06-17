"""HTTP response → domain exception translation for source connectors.

Translates raw ``httpx`` responses into the typed exception hierarchy
from ``domains.sources.exceptions``:

- **401** → ``SourceAuthError`` (credentials dead, abort sync)
- **403** → ``SourceEntityForbiddenError`` (skip — source decides severity)
- **404** → ``SourceEntityNotFoundError`` (skip — source decides severity)
- **429** → ``SourceRateLimitError`` (retry with backoff)
- **5xx** → ``SourceServerError`` (retry with backoff)
- **3xx** → ``SourceError`` (unexpected redirect)
- **400 disguised rate limit** → ``SourceRateLimitError`` (Zoho quirk)

Usage::

    resp = await self.http_client.get(url, headers=headers)
    raise_for_status(resp, source_short_name=self.short_name)
    data = resp.json()
"""

from __future__ import annotations

import httpx

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceCursorInvalidError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceError,
    SourceRateLimitError,
    SourceServerError,
)
from airweave.domains.sources.token_providers.protocol import AuthProviderKind


def raise_for_status(
    response: httpx.Response,
    *,
    source_short_name: str,
    token_provider_kind: AuthProviderKind,
    entity_id: str = "",
    context: str = "",
) -> None:
    """Raise a domain exception if the response indicates an error.

    Args:
        response: The httpx response to check.
        source_short_name: Source identifier for the exception.
        token_provider_kind: Auth provider kind for SourceAuthError.
        entity_id: Optional entity ID for richer error messages.
        context: Optional string appended to the error message.
    """
    if response.is_success:
        return

    status = response.status_code
    detail = _extract_detail(response)
    ctx = f" while {context}" if context else ""
    eid_ctx = f" (entity {entity_id})" if entity_id else ""

    _STATUS_HANDLERS.get(status, _handle_fallback)(
        response, status, detail, ctx + eid_ctx, source_short_name, token_provider_kind
    )


def _handle_401(
    _r: httpx.Response, _s: int, detail: str, ctx: str, sn: str, tpk: AuthProviderKind
) -> None:
    raise SourceAuthError(
        f"Unauthorized (401){ctx} — credentials invalid or revoked. {detail}",
        source_short_name=sn,
        status_code=401,
        token_provider_kind=tpk,
    )


def _handle_403(
    _r: httpx.Response, _s: int, detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    raise SourceEntityForbiddenError(f"Forbidden (403){ctx}: {detail}", source_short_name=sn)


def _handle_404(
    _r: httpx.Response, _s: int, detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    raise SourceEntityNotFoundError(f"Not found (404){ctx}: {detail}", source_short_name=sn)


def _handle_410(
    _r: httpx.Response, _s: int, detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    raise SourceCursorInvalidError(
        f"Cursor invalid (410){ctx}: {detail}",
        source_short_name=sn,
        status_code=410,
    )


def _handle_429(
    resp: httpx.Response, _s: int, _detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    retry_after = _parse_retry_after(resp)
    raise SourceRateLimitError(
        retry_after=retry_after,
        source_short_name=sn,
        message=f"Rate limited (429){ctx}. Retry after {retry_after:.1f}s",
    )


def _handle_redirect(
    resp: httpx.Response, status: int, _detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    location = resp.headers.get("Location", "<unknown>")
    raise SourceError(f"Unexpected redirect ({status}){ctx} → {location}", source_short_name=sn)


def _handle_fallback(
    resp: httpx.Response, status: int, detail: str, ctx: str, sn: str, _tpk: AuthProviderKind
) -> None:
    if status >= 500:
        raise SourceServerError(
            f"Server error ({status}){ctx}: {detail}",
            source_short_name=sn,
            status_code=status,
        )
    if status == 400 and _is_rate_limit_disguised_as_400(resp):
        retry_after = _parse_retry_after(resp, default=30.0)
        raise SourceRateLimitError(
            retry_after=retry_after,
            source_short_name=sn,
            message=f"Rate limited (400 disguised){ctx}. Retry after {retry_after:.1f}s",
        )
    raise SourceError(f"HTTP {status}{ctx}: {detail}", source_short_name=sn)


_STATUS_HANDLERS = {
    401: _handle_401,
    403: _handle_403,
    404: _handle_404,
    410: _handle_410,
    429: _handle_429,
    301: _handle_redirect,
    302: _handle_redirect,
    307: _handle_redirect,
    308: _handle_redirect,
}


def translate_httpx_error(
    exc: httpx.HTTPStatusError,
    *,
    source_short_name: str,
    token_provider_kind: AuthProviderKind,
    context: str = "",
) -> None:
    """Re-raise an ``httpx.HTTPStatusError`` as the correct domain exception."""
    raise_for_status(
        exc.response,
        source_short_name=source_short_name,
        token_provider_kind=token_provider_kind,
        context=context,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_detail(response: httpx.Response, max_length: int = 200) -> str:
    """Pull a human-readable snippet from the response body."""
    try:
        data = response.json()
        for key in ("message", "error_description", "error", "detail", "errors"):
            val = data.get(key)
            if val:
                return str(val)[:max_length]
        return str(data)[:max_length]
    except Exception:
        text = response.text[:max_length] if response.text else ""
        return text or f"(no body, status {response.status_code})"


def _parse_retry_after(
    response: httpx.Response,
    default: float = 30.0,
) -> float:
    """Parse Retry-After header, fall back to *default*."""
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return max(float(raw), 1.0)
        except (ValueError, TypeError):
            pass
    return default


def _is_rate_limit_disguised_as_400(response: httpx.Response) -> bool:
    """Detect APIs that return 400 instead of 429 for rate limits (e.g. Zoho)."""
    try:
        data = response.json()
        error_desc = str(data.get("error_description", "")).lower()
        error_type = str(data.get("error", "")).lower()
        if "too many requests" in error_desc and error_type == "access denied":
            return True
        if "rate limit" in error_desc:
            return True
    except Exception:
        pass
    return False
