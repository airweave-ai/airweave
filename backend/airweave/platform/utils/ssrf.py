"""SSRF protection utilities.

Validates URLs and hostnames against known-dangerous targets before they
reach HTTP clients or database drivers.  Two public entry points:

    validate_url(url)   – for full URLs (scheme + host checked)
    validate_host(host) – for bare hostnames / IP addresses

Both raise ``SSRFViolation`` (a ValueError subclass) on blocked input
and return the input unchanged on success, making them usable as
Pydantic field validators.

Design notes
------------
* No DNS resolution — avoids TOCTOU races.  DNS rebinding is
  expected to be caught at the network layer (egress controls).
* ``socket.inet_aton`` is used as a fallback to catch octal / hex / short
  IP notation that ``ipaddress.ip_address`` rejects.
* IPv4-mapped IPv6 addresses (``::ffff:x.x.x.x``) are unpacked and
  re-checked against the IPv4 blocklist.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class SSRFViolation(ValueError):
    """Raised when a URL or hostname targets a blocked destination."""


# ---------------------------------------------------------------------------
# Configuration import (deferred to avoid circular imports at module level)
# ---------------------------------------------------------------------------


def _get_allow_private_default() -> bool:
    """Return the global default for ``allow_private`` from settings."""
    try:
        from airweave.core.config import settings

        return getattr(settings, "SSRF_ALLOW_PRIVATE_NETWORKS", False)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Blocklists
# ---------------------------------------------------------------------------

_BLOCKED_METADATA_IPS: frozenset[str] = frozenset(
    {
        "169.254.169.254",
        "fd00:ec2::254",
        "100.100.100.200",
    }
)

_BLOCKED_HOSTNAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.goog",
    }
)

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Private / loopback / link-local networks (blocked when allow_private=False)
_PRIVATE_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
)

# Unspecified addresses
_UNSPECIFIED_ADDRS: frozenset[str] = frozenset({"0.0.0.0", "::"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Try to parse *host* as an IP address.

    Falls back to ``socket.inet_aton`` to catch octal (``0177.0.0.1``),
    hex (``0x7f000001``), and shorthand (``127.1``) notation.
    """
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    # Fallback: socket.inet_aton handles non-standard notation.
    try:
        packed = socket.inet_aton(host)
        return ipaddress.IPv4Address(packed)
    except (OSError, OverflowError):
        pass

    return None


def _check_ip(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    allow_private: bool,
) -> None:
    """Raise ``SSRFViolation`` if *addr* is blocked."""
    canonical = str(addr)

    # Always block metadata IPs
    if canonical in _BLOCKED_METADATA_IPS:
        raise SSRFViolation(f"blocked metadata IP: {canonical}")

    # Unpack IPv4-mapped IPv6 and re-check
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        _check_ip(addr.ipv4_mapped, allow_private)
        return

    # Always block unspecified
    if canonical in _UNSPECIFIED_ADDRS:
        raise SSRFViolation(f"blocked unspecified address: {canonical}")

    if not allow_private:
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                raise SSRFViolation(f"blocked private/loopback IP: {canonical}")


def _check_host_string(host: str, allow_private: bool) -> None:
    """Validate a hostname or IP string."""
    if not host:
        return

    lower = host.lower()

    # Strip IPv6 brackets if present
    if lower.startswith("[") and lower.endswith("]"):
        lower = lower[1:-1]

    ip = _parse_ip(lower)
    if ip is not None:
        _check_ip(ip, allow_private)
        return

    # It's a hostname — check against blocklist
    if lower in _BLOCKED_HOSTNAMES:
        raise SSRFViolation(f"blocked hostname: {lower}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_url(url: str, *, allow_private: bool | None = None) -> str:
    """Validate a URL for SSRF safety.

    Checks the scheme and hostname.  Relative URLs (no scheme *and* no
    host) are passed through without checks — the base URL was already
    validated at config time.  Protocol-relative URLs (``//host/path``)
    *are* checked.

    Returns *url* unchanged on success.

    Raises:
        SSRFViolation: If the URL targets a blocked destination.
    """
    if allow_private is None:
        allow_private = _get_allow_private_default()

    if not url:
        return url

    parsed = urlparse(url)

    # Relative URL: no scheme AND no hostname → skip
    if not parsed.scheme and not parsed.hostname:
        return url

    # Scheme check (only when present)
    if parsed.scheme and parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SSRFViolation(f"blocked scheme: {parsed.scheme}")

    hostname = parsed.hostname or ""
    _check_host_string(hostname, allow_private)

    return url


def validate_host(host: str, *, allow_private: bool | None = None) -> str:
    """Validate a bare hostname or IP address for SSRF safety.

    Returns *host* unchanged on success.

    Raises:
        SSRFViolation: If the host is a blocked destination.
    """
    if allow_private is None:
        allow_private = _get_allow_private_default()

    if not host:
        return host

    _check_host_string(host.strip(), allow_private)
    return host
