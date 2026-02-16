"""Active Directory LDAP client for SharePoint 2019 V2.

This module provides LDAP connectivity to Active Directory for:
- Expanding AD group memberships (group → users, group → nested groups)
- Resolving AD principals to canonical identifiers
- Resolving SIDs to sAMAccountNames for entity access control
- Incremental membership tracking via DirSync control

Performance optimizations:
- DN resolution caching: Avoids redundant LDAP lookups for the same Distinguished Names
- Group expansion memoization: Caches fully-expanded group membership results
- Automatic reconnection: Recovers from LDAP session timeouts
"""

import base64
import re
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from ldap3 import BASE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPSessionTerminatedByServerError, LDAPSocketOpenError
from pyasn1.codec.ber import decoder as ber_decoder
from pyasn1.type.univ import Sequence

from airweave.platform.access_control.schemas import (
    ACLChangeType,
    MembershipChange,
    MembershipTuple,
)
from airweave.platform.sources.sharepoint2019v2.acl import extract_canonical_id

# -------------------------------------------------------------------------
# DirSync Constants
# -------------------------------------------------------------------------

# LDAP control OID for DirSync
LDAP_SERVER_DIRSYNC_OID = "1.2.840.113556.1.4.841"
# LDAP control OID for showing deleted/tombstone objects
LDAP_SERVER_SHOW_DELETED_OID = "1.2.840.113556.1.4.417"

# DirSync flags (bitfield)
LDAP_DIRSYNC_OBJECT_SECURITY = 0x00000001  # Respect ACLs
LDAP_DIRSYNC_ANCESTORS_FIRST_ORDER = 0x00000800  # Parents before children
LDAP_DIRSYNC_PUBLIC_DATA_ONLY = 0x00002000  # No secret attributes
LDAP_DIRSYNC_INCREMENTAL_VALUES = 0x80000000  # Only changed members, not full list

# Composite flag sets
# FULL: INCREMENTAL_VALUES returns only changed members (not the full list).
# Does NOT include OBJECT_SECURITY (requires "Replicating Directory Changes All").
DIRSYNC_FLAGS_FULL = LDAP_DIRSYNC_INCREMENTAL_VALUES
# BASIC: no flags at all (same as .NET default), used as fallback
DIRSYNC_FLAGS_BASIC = 0


class DirSyncPermissionError(Exception):
    """Raised when the account lacks DirSync privileges."""

    pass


@dataclass
class DirSyncResult:
    """Result from a DirSync query.

    Attributes:
        changes: List of membership changes (add/remove).
        new_cookie: Opaque cookie for the next DirSync query.
        modified_group_ids: Set of group IDs whose membership changed.
        deleted_group_ids: Set of group IDs that were deleted from AD.
        more_results: True if more pages are available.
    """

    changes: List[MembershipChange] = field(default_factory=list)
    new_cookie: bytes = b""
    modified_group_ids: Set[str] = field(default_factory=set)
    deleted_group_ids: Set[str] = field(default_factory=set)
    more_results: bool = False

    @property
    def cookie_b64(self) -> str:
        """Return the cookie as a base64-encoded string for storage."""
        if not self.new_cookie:
            return ""
        return base64.b64encode(self.new_cookie).decode("ascii")

    @classmethod
    def cookie_from_b64(cls, b64_str: str) -> bytes:
        """Decode a base64 cookie string back to bytes."""
        if not b64_str:
            return b""
        return base64.b64decode(b64_str)


class LDAPClient:
    """Client for Active Directory LDAP operations.

    Handles LDAP connectivity with automatic protocol negotiation:
    1. Tries LDAPS (port 636) first
    2. Falls back to STARTTLS on port 389

    Performance optimizations:
    - DN cache: Stores results of _query_member() to avoid redundant lookups
    - Group expansion cache: Memoizes expand_group_recursive() results
    - Auto-reconnect: Recovers from LDAP session timeouts with exponential backoff

    Args:
        server: AD server hostname or IP
        username: AD username for authentication
        password: AD password
        domain: AD domain (e.g., 'CONTOSO')
        search_base: LDAP search base DN (e.g., 'DC=contoso,DC=local')
        logger: Logger instance
    """

    # Retry configuration for LDAP operations
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2  # Exponential backoff: 2^attempt seconds

    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        domain: str,
        search_base: str,
        logger: Any,
    ):
        """Initialize LDAP client."""
        self.server_address = server
        self.username = username
        self.password = password
        self.domain = domain
        self.search_base = search_base
        self.logger = logger
        self._connection: Optional[Connection] = None
        self._sid_cache: Dict[str, Optional[str]] = {}

        # DN resolution cache: member_dn → (object_classes, sam_account_name) or None
        self._dn_cache: Dict[str, Optional[Tuple[List[str], str]]] = {}
        # Group expansion cache: group_name_lower → List[MembershipTuple]
        self._group_expansion_cache: Dict[str, List[MembershipTuple]] = {}

        # Batch LDAP query configuration
        self.LDAP_BATCH_SIZE = 50  # Number of DNs to resolve in a single LDAP query

        # Statistics for monitoring
        self._stats = {
            "dn_cache_hits": 0,
            "dn_cache_misses": 0,
            "group_cache_hits": 0,
            "group_cache_misses": 0,
            "reconnects": 0,
            "ldap_queries": 0,
            "batch_queries": 0,
            "dns_resolved_via_batch": 0,
        }

    async def connect(self, force_reconnect: bool = False) -> Connection:
        """Establish LDAP connection to Active Directory.

        Tries LDAPS first, then falls back to STARTTLS.

        Args:
            force_reconnect: If True, close existing connection and create new one

        Returns:
            Bound LDAP Connection

        Raises:
            Exception: If both connection methods fail
        """
        if not force_reconnect and self._connection and self._connection.bound:
            return self._connection

        # Close existing connection if forcing reconnect
        if force_reconnect and self._connection:
            self.close()
            self._stats["reconnects"] += 1
            self.logger.info("Forcing LDAP reconnection")

        # Strip protocol prefix if present
        server_clean = self.server_address.replace("ldap://", "").replace("ldaps://", "")

        # TLS config for both methods
        tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        user_dn = f"{self.domain}\\{self.username}"

        # Try LDAPS first (port 636)
        try:
            server_url = server_clean if ":" in server_clean else f"{server_clean}:636"
            server = Server(server_url, get_info="ALL", use_ssl=True, tls=tls_config)
            conn = Connection(server, user=user_dn, password=self.password, auto_bind=True)
            self._connection = conn
            self.logger.info(f"Connected to AD via LDAPS: {server_url}")
            return conn
        except Exception as ldaps_error:
            self.logger.debug(f"LDAPS failed, trying STARTTLS: {ldaps_error}")

        # Fallback to STARTTLS (port 389)
        try:
            server_url_starttls = server_clean if ":" in server_clean else server_clean
            server = Server(server_url_starttls, get_info="ALL", tls=tls_config)
            conn = Connection(server, user=user_dn, password=self.password, auto_bind=False)
            conn.open()
            conn.start_tls()
            conn.bind()
            self._connection = conn
            self.logger.info(f"Connected to AD via STARTTLS: {server_url_starttls}")
            return conn
        except Exception as starttls_error:
            self.logger.error(f"Both LDAPS and STARTTLS failed: {starttls_error}")
            raise Exception(f"Could not connect to AD: {starttls_error}") from starttls_error

    def close(self) -> None:
        """Close the LDAP connection."""
        if self._connection:
            try:
                self._connection.unbind()
            except Exception:
                pass
            self._connection = None

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dict with cache hit/miss counts and other metrics
        """
        return {
            **self._stats,
            "dn_cache_size": len(self._dn_cache),
            "group_cache_size": len(self._group_expansion_cache),
            "dn_cache_hit_rate": (
                self._stats["dn_cache_hits"]
                / max(1, self._stats["dn_cache_hits"] + self._stats["dn_cache_misses"])
            ),
            "group_cache_hit_rate": (
                self._stats["group_cache_hits"]
                / max(1, self._stats["group_cache_hits"] + self._stats["group_cache_misses"])
            ),
        }

    def log_cache_stats(self) -> None:
        """Log cache statistics for performance monitoring."""
        stats = self.get_cache_stats()
        dn_total = stats["dn_cache_hits"] + stats["dn_cache_misses"]
        grp_total = stats["group_cache_hits"] + stats["group_cache_misses"]
        self.logger.info(
            f"LDAP stats: DN cache {stats['dn_cache_hits']}/{dn_total} hits "
            f"({stats['dn_cache_hit_rate']:.1%}), "
            f"Group cache {stats['group_cache_hits']}/{grp_total} hits "
            f"({stats['group_cache_hit_rate']:.1%}), "
            f"LDAP queries: {stats['ldap_queries']}, "
            f"Batch queries: {stats['batch_queries']} ({stats['dns_resolved_via_batch']} DNs), "
            f"Reconnects: {stats['reconnects']}"
        )

    async def _execute_with_retry(self, operation_name: str, operation_func):
        """Execute an LDAP operation with automatic retry on connection errors.

        Args:
            operation_name: Name of operation for logging
            operation_func: Async function to execute (receives connection as arg)

        Returns:
            Result of operation_func

        Raises:
            Exception: If all retries fail
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                conn = await self.connect(force_reconnect=(attempt > 0))
                return await operation_func(conn)

            except (LDAPSessionTerminatedByServerError, LDAPSocketOpenError) as e:
                last_error = e
                wait_time = self.RETRY_BACKOFF_BASE**attempt
                self.logger.warning(
                    f"LDAP connection error during {operation_name} "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                    f"Reconnecting in {wait_time}s..."
                )
                time.sleep(wait_time)
                # Force close the dead connection
                self._connection = None

            except Exception:
                # Non-recoverable error, don't retry
                raise

        raise Exception(
            f"LDAP operation '{operation_name}' failed after "
            f"{self.MAX_RETRIES} attempts: {last_error}"
        )

    async def _query_members_batch(  # noqa: C901
        self, member_dns: List[str]
    ) -> Dict[str, Optional[Tuple[List[str], str]]]:
        """Resolve multiple member DNs in a single batched LDAP query.

        This is the key optimization: instead of making N LDAP queries for N members,
        we batch them into ceil(N/BATCH_SIZE) queries using OR filters.

        Args:
            member_dns: List of Distinguished Names to resolve

        Returns:
            Dict mapping DN → (object_classes, sam_account_name) or DN → None
        """
        results: Dict[str, Optional[Tuple[List[str], str]]] = {}

        # First, check cache and separate cached vs uncached DNs
        uncached_dns: List[str] = []
        for dn in member_dns:
            if dn in self._dn_cache:
                self._stats["dn_cache_hits"] += 1
                results[dn] = self._dn_cache[dn]
            else:
                self._stats["dn_cache_misses"] += 1
                uncached_dns.append(dn)

        if not uncached_dns:
            return results

        # Process uncached DNs in batches
        conn = await self.connect()

        for i in range(0, len(uncached_dns), self.LDAP_BATCH_SIZE):
            batch = uncached_dns[i : i + self.LDAP_BATCH_SIZE]
            self._stats["batch_queries"] += 1
            self._stats["ldap_queries"] += 1

            # Build OR filter for batch: (|(distinguishedName=dn1)(distinguishedName=dn2)...)
            # Escape special LDAP characters in DNs
            dn_filters = []
            for dn in batch:
                # Escape special chars: * ( ) \ NUL
                escaped_dn = dn.replace("\\", "\\5c").replace("*", "\\2a")
                escaped_dn = escaped_dn.replace("(", "\\28").replace(")", "\\29")
                dn_filters.append(f"(distinguishedName={escaped_dn})")

            search_filter = f"(|{''.join(dn_filters)})"

            try:
                conn.search(
                    search_base=self.search_base,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=["distinguishedName", "objectClass", "sAMAccountName"],
                    size_limit=len(batch) + 10,  # Allow some buffer
                )

                # Map results back to DNs
                dn_to_entry: Dict[str, Any] = {}
                for entry in conn.entries:
                    if hasattr(entry, "distinguishedName"):
                        entry_dn = str(entry.distinguishedName)
                        dn_to_entry[entry_dn] = entry

                # Process each DN in the batch
                for dn in batch:
                    entry = dn_to_entry.get(dn)
                    if entry is None:
                        # DN not found
                        self._dn_cache[dn] = None
                        results[dn] = None
                        continue

                    # Extract object classes
                    object_classes: List[str] = []
                    if hasattr(entry, "objectClass"):
                        object_classes = [str(oc).lower() for oc in entry.objectClass]

                    # Extract sAMAccountName
                    sam_account_name = None
                    if hasattr(entry, "sAMAccountName"):
                        sam_account_name = str(entry.sAMAccountName)

                    if not sam_account_name:
                        self._dn_cache[dn] = None
                        results[dn] = None
                    else:
                        result = (object_classes, sam_account_name)
                        self._dn_cache[dn] = result
                        results[dn] = result
                        self._stats["dns_resolved_via_batch"] += 1

            except Exception as e:
                self.logger.warning(f"Batch LDAP query failed: {e}")
                # Fall back to marking all as None (will be retried individually if needed)
                for dn in batch:
                    if dn not in results:
                        self._dn_cache[dn] = None
                        results[dn] = None

        return results

    async def resolve_sid(self, sid: str) -> Optional[str]:
        """Resolve a Windows SID to its sAMAccountName.

        Uses an in-memory cache to avoid repeated LDAP lookups for the same SID.

        Args:
            sid: Windows Security Identifier (e.g., "s-1-5-21-...")

        Returns:
            The sAMAccountName (lowercase) if found, None otherwise
        """
        # Check cache first
        if sid in self._sid_cache:
            cached = self._sid_cache[sid]
            if cached:
                self.logger.debug(f"SID cache hit: {sid} → {cached}")
            return cached

        # Connect to AD
        conn = await self.connect()

        # Query AD for the object with this SID
        # The objectSid attribute requires special escaping for LDAP search
        search_filter = f"(objectSid={sid})"
        conn.search(
            search_base=self.search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["sAMAccountName", "objectClass"],
            size_limit=1,
        )

        if not conn.entries:
            self.logger.debug(f"SID not found in AD: {sid}")
            self._sid_cache[sid] = None
            return None

        entry = conn.entries[0]
        sam_account_name = None
        if hasattr(entry, "sAMAccountName"):
            sam_account_name = str(entry.sAMAccountName).lower()

        # Cache the result
        self._sid_cache[sid] = sam_account_name
        if sam_account_name:
            self.logger.debug(f"SID resolved: {sid} → {sam_account_name}")

        return sam_account_name

    async def expand_group_recursive(  # noqa: C901
        self,
        group_login_name: str,
        visited_groups: Optional[Set[str]] = None,
    ) -> AsyncGenerator[MembershipTuple, None]:
        r"""Recursively expand an AD group to find all nested memberships.

        Queries Active Directory using the "member" attribute to find:
        - Direct user members → yields AD Group → User membership
        - Nested group members → yields AD Group → AD Group membership and recurses

        The member_id format for users is the raw sAMAccountName (lowercase).
        The group_id format is "ad:{groupname}" to match entity access control.

        Performance optimizations:
        - Memoizes fully-expanded groups to avoid redundant work
        - Uses DN caching for member resolution
        - Auto-reconnects on LDAP session timeout

        Args:
            group_login_name: LoginName of the AD group.
                Claims format: "c:0+.w|DOMAIN\\groupname"
                Non-claims format: "DOMAIN\\groupname"
            visited_groups: Set of already-visited group names to prevent cycles

        Yields:
            MembershipTuple for AD Group → User and AD Group → AD Group
        """
        if visited_groups is None:
            visited_groups = set()

        # Extract group name from LoginName
        group_name = extract_canonical_id(group_login_name)
        group_name_lower = group_name.lower()

        # Prevent infinite recursion
        if group_name_lower in visited_groups:
            self.logger.debug(f"Skipping already-visited group: {group_name}")
            return
        visited_groups.add(group_name_lower)

        # Check group expansion cache (only if this is a fresh expansion, not recursive)
        # We cache at the top level but not during recursion to handle visited correctly
        if len(visited_groups) == 1 and group_name_lower in self._group_expansion_cache:
            self._stats["group_cache_hits"] += 1
            cached = self._group_expansion_cache[group_name_lower]
            self.logger.debug(f"Group cache hit: {group_name} ({len(cached)} memberships)")
            for membership in cached:
                yield membership
            return

        if len(visited_groups) == 1:
            self._stats["group_cache_misses"] += 1

        # Collect memberships for caching (only at top level)
        collected_memberships: List[MembershipTuple] = [] if len(visited_groups) == 1 else None

        # Use retry wrapper for LDAP operations
        async def query_group(conn: Connection):
            self._stats["ldap_queries"] += 1
            search_filter = f"(&(objectClass=group)(sAMAccountName={group_name}))"
            conn.search(
                search_base=self.search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=["cn", "distinguishedName", "member"],
                size_limit=1000,
            )
            return conn.entries[0] if conn.entries else None

        group_entry = await self._execute_with_retry(f"expand_group({group_name})", query_group)

        if not group_entry:
            self.logger.warning(f"AD group not found: {group_name}")
            return

        members = self._get_members(group_entry)
        self.logger.info(f"AD group '{group_name}' has {len(members)} members")

        # Canonical group_id format: "ad:groupname"
        # This matches entity access format: "group:ad:groupname"
        membership_group_id = f"ad:{group_name_lower}"

        # BATCH OPTIMIZATION: Resolve all member DNs in batched LDAP queries
        # Instead of N queries for N members, we do ceil(N/50) queries
        member_infos = await self._query_members_batch(members)

        # Track nested groups to recurse into after processing all members
        nested_groups_to_expand: List[str] = []

        for member_dn in members:
            member_info = member_infos.get(member_dn)
            if not member_info:
                continue

            object_classes, sam_account_name = member_info

            if "user" in object_classes:
                # AD Group → User
                # member_id is raw sAMAccountName (lowercase)
                self.logger.debug(f"  → User member: {sam_account_name}")
                membership = MembershipTuple(
                    member_id=sam_account_name.lower(),
                    member_type="user",
                    group_id=membership_group_id,
                    group_name=group_name,
                )
                if collected_memberships is not None:
                    collected_memberships.append(membership)
                yield membership

            elif "group" in object_classes:
                # AD Group → AD Group (nested)
                # member_id uses "ad:groupname" format
                nested_group_id = f"ad:{sam_account_name.lower()}"
                self.logger.info(f"  → Nested group member: {sam_account_name}")
                membership = MembershipTuple(
                    member_id=nested_group_id,
                    member_type="group",
                    group_id=membership_group_id,
                    group_name=group_name,
                )
                # Track for recursion
                nested_groups_to_expand.append(sam_account_name)
                if collected_memberships is not None:
                    collected_memberships.append(membership)
                yield membership

        # Now recursively expand nested groups
        for nested_group_name in nested_groups_to_expand:
            nested_login = f"{self.domain}\\{nested_group_name}"
            async for nested_membership in self.expand_group_recursive(
                nested_login, visited_groups
            ):
                if collected_memberships is not None:
                    collected_memberships.append(nested_membership)
                yield nested_membership

        # Cache the fully expanded group (only at top level)
        if collected_memberships is not None:
            self._group_expansion_cache[group_name_lower] = collected_memberships
            self.logger.debug(
                f"Cached group expansion: {group_name} ({len(collected_memberships)} memberships)"
            )

    def _get_members(self, group_entry: Any) -> List[str]:
        """Extract member DNs from LDAP group entry."""
        if hasattr(group_entry, "member"):
            return [str(m) for m in group_entry.member]
        return []

    def _query_member_cached(
        self, conn: Connection, member_dn: str
    ) -> Optional[Tuple[List[str], str]]:
        """Query a member DN with caching to avoid redundant lookups.

        This is a key optimization: the same users appear in multiple groups,
        so caching DN resolutions significantly reduces LDAP queries.

        Args:
            conn: LDAP connection
            member_dn: Distinguished Name of the member

        Returns:
            Tuple of (object_classes_list, sAMAccountName) or None
        """
        # Check cache first
        if member_dn in self._dn_cache:
            self._stats["dn_cache_hits"] += 1
            cached = self._dn_cache[member_dn]
            if cached:
                self.logger.debug(f"DN cache hit: {member_dn} → {cached[1]}")
            return cached

        self._stats["dn_cache_misses"] += 1
        self._stats["ldap_queries"] += 1

        try:
            conn.search(
                search_base=member_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=["objectClass", "sAMAccountName"],
            )
        except Exception as e:
            self.logger.warning(f"LDAP query failed for member DN '{member_dn}': {e}")
            self._dn_cache[member_dn] = None
            return None

        if not conn.entries:
            self.logger.debug(f"No LDAP entry found for member DN: {member_dn}")
            self._dn_cache[member_dn] = None
            return None

        member_entry = conn.entries[0]

        # Extract object classes
        object_classes: List[str] = []
        if hasattr(member_entry, "objectClass"):
            object_classes = [str(oc).lower() for oc in member_entry.objectClass]

        # Extract sAMAccountName
        sam_account_name = None
        if hasattr(member_entry, "sAMAccountName"):
            sam_account_name = str(member_entry.sAMAccountName)

        if not sam_account_name:
            self.logger.debug(f"No sAMAccountName for member DN: {member_dn}")
            self._dn_cache[member_dn] = None
            return None

        result = (object_classes, sam_account_name)
        self._dn_cache[member_dn] = result
        self.logger.debug(
            f"Resolved member DN '{member_dn}' → {sam_account_name} (classes: {object_classes})"
        )
        return result

    def _query_member(self, conn: Connection, member_dn: str) -> Optional[tuple]:
        """Query a member DN to determine its type and sAMAccountName.

        Wrapper for backwards compatibility - uses cached version internally.

        Args:
            conn: LDAP connection
            member_dn: Distinguished Name of the member

        Returns:
            Tuple of (object_classes_list, sAMAccountName) or None
        """
        return self._query_member_cached(conn, member_dn)

    # -------------------------------------------------------------------------
    # DirSync — Incremental Group Membership Tracking
    # -------------------------------------------------------------------------

    def _build_dirsync_control(
        self,
        cookie: bytes = b"",
        flags: int = DIRSYNC_FLAGS_FULL,
        max_bytes: int = 1048576,
    ) -> Tuple[str, bool, bytes]:
        """Build a DirSync LDAP control for the search request.

        The DirSync control is a BER-encoded SEQUENCE of:
            flags (INTEGER), max_bytes (INTEGER), cookie (OCTET STRING)

        We manually encode because both ldap3 and pyasn1 have quirks
        with large flag values (INCREMENTAL_VALUES = 0x80000000).

        Args:
            cookie: Opaque cookie from a previous DirSync response (empty = initial).
            flags: DirSync flags bitmask.
            max_bytes: Maximum attribute value bytes to return.

        Returns:
            Tuple of (OID, criticality, BER-encoded-value) for ldap3 controls.
        """

        def _ber_encode_int(value: int) -> bytes:
            """BER-encode a signed integer."""
            if value == 0:
                return b"\x02\x01\x00"
            # Determine byte length needed
            if value > 0:
                length = (value.bit_length() + 8) // 8  # +1 for sign, round up
            else:
                length = (value.bit_length() + 9) // 8
            int_bytes = value.to_bytes(length, byteorder="big", signed=True)
            return b"\x02" + bytes([len(int_bytes)]) + int_bytes

        def _ber_encode_octet_string(data: bytes) -> bytes:
            """BER-encode an OCTET STRING."""
            length = len(data)
            if length < 128:
                return b"\x04" + bytes([length]) + data
            # Long form
            len_bytes = length.to_bytes((length.bit_length() + 7) // 8, "big")
            return b"\x04" + bytes([0x80 | len(len_bytes)]) + len_bytes + data

        def _ber_encode_sequence(items: bytes) -> bytes:
            """BER-encode a SEQUENCE wrapper."""
            length = len(items)
            if length < 128:
                return b"\x30" + bytes([length]) + items
            len_bytes = length.to_bytes((length.bit_length() + 7) // 8, "big")
            return b"\x30" + bytes([0x80 | len(len_bytes)]) + len_bytes + items

        # Encode: SEQUENCE { flags INTEGER, max_bytes INTEGER, cookie OCTET STRING }
        payload = (
            _ber_encode_int(flags) + _ber_encode_int(max_bytes) + _ber_encode_octet_string(cookie)
        )
        value = _ber_encode_sequence(payload)

        return (LDAP_SERVER_DIRSYNC_OID, True, value)

    def _parse_dirsync_response_control(
        self,
        controls: Any,
    ) -> Tuple[bytes, bool]:
        """Parse the DirSync response control to extract cookie and more_results flag.

        Args:
            controls: Response controls dict from the LDAP search result.

        Returns:
            Tuple of (new_cookie_bytes, more_results_bool).

        Raises:
            ValueError: If the DirSync control is not in the response.
        """
        if not controls or LDAP_SERVER_DIRSYNC_OID not in controls:
            self.logger.warning(
                "DirSync response control not found in response. "
                "Ensure the account has 'Replicating Directory Changes' permission."
            )
            return b"", False

        ctrl_data = controls[LDAP_SERVER_DIRSYNC_OID]

        # ldap3 returns controls as {"value": {"cookie": ..., "more_results": ...}}
        if isinstance(ctrl_data, dict):
            # Drill into the "value" key if present (ldap3 wrapping)
            value = ctrl_data.get("value", ctrl_data)
            if isinstance(value, dict):
                cookie = value.get("cookie", b"")
                more = value.get("more_results", False)
                if isinstance(cookie, str):
                    cookie = cookie.encode("latin-1")
                return cookie, bool(more)

        # Some ldap3 versions may return raw BER bytes
        if isinstance(ctrl_data, bytes):
            decoded, _ = ber_decoder.decode(ctrl_data, asn1Spec=Sequence())
            # SEQUENCE { more_results INTEGER, unused INTEGER, cookie OCTET STRING }
            more = int(decoded[0]) != 0
            cookie = bytes(decoded[2])
            return cookie, more

        # Fallback: return empty cookie (triggers full sync next time)
        self.logger.warning(f"Unexpected DirSync control format: {type(ctrl_data)}")
        return b"", False

    async def get_membership_changes(
        self,
        cookie_b64: str = "",
    ) -> DirSyncResult:
        """Get incremental group membership changes via AD DirSync.

        DirSync is an LDAP extended control (OID 1.2.840.113556.1.4.841)
        that returns only objects changed since the cookie was issued.

        On first call (empty cookie), returns ALL group memberships.
        On subsequent calls, returns only groups whose membership changed.

        Automatically paginates when AD returns more_results=True.

        Args:
            cookie_b64: Base64-encoded cookie from a previous call (empty = initial).

        Returns:
            DirSyncResult with changes, new cookie, and modified group IDs.
        """
        cookie = DirSyncResult.cookie_from_b64(cookie_b64)
        is_initial = len(cookie) == 0

        self.logger.info(
            f"DirSync query: {'initial (full)' if is_initial else 'incremental'}, "
            f"cookie_len={len(cookie)}"
        )

        # Paginate: DirSync may return partial results with more_results=True
        all_changes: List[MembershipChange] = []
        all_modified_ids: Set[str] = set()
        all_deleted_ids: Set[str] = set()
        page = 0

        while True:
            page += 1
            result = await self._execute_dirsync_query_with_flags(
                cookie=cookie,
                is_initial=is_initial,
                flags=DIRSYNC_FLAGS_FULL,
            )

            all_changes.extend(result.changes)
            all_modified_ids.update(result.modified_group_ids)
            all_deleted_ids.update(result.deleted_group_ids)
            cookie = result.new_cookie

            self.logger.debug(
                f"DirSync page {page}: {len(result.changes)} changes, "
                f"more_results={result.more_results}"
            )

            if not result.more_results:
                break

        self.logger.info(
            f"DirSync complete: {len(all_changes)} changes across {page} page(s), "
            f"{len(all_modified_ids)} groups modified, "
            f"{len(all_deleted_ids)} groups deleted, "
            f"new_cookie_len={len(cookie)}"
        )

        return DirSyncResult(
            changes=all_changes,
            new_cookie=cookie,
            modified_group_ids=all_modified_ids,
            deleted_group_ids=all_deleted_ids,
            more_results=False,
        )

    async def _execute_dirsync_query_with_flags(
        self,
        cookie: bytes,
        is_initial: bool,
        flags: int,
    ) -> DirSyncResult:
        """Execute DirSync with given flags, falling back to basic on permission error.

        Reconnects the LDAP connection before retrying with reduced flags,
        since AD may leave the connection in an unusable state after rejecting
        a critical extension.

        Args:
            cookie: DirSync cookie bytes.
            is_initial: Whether this is the first sync (no prior cookie).
            flags: DirSync flags bitmask.

        Returns:
            DirSyncResult with changes.
        """
        try:
            return await self._execute_dirsync_query(cookie, is_initial, flags)
        except DirSyncPermissionError:
            if flags != DIRSYNC_FLAGS_BASIC:
                self.logger.warning(
                    "DirSync with full flags failed, reconnecting and retrying with basic flags"
                )
                await self.connect(force_reconnect=True)
                return await self._execute_dirsync_query(cookie, is_initial, DIRSYNC_FLAGS_BASIC)
            raise

    async def _execute_dirsync_query(
        self,
        cookie: bytes,
        is_initial: bool,
        flags: int,
    ) -> DirSyncResult:
        """Execute a single DirSync LDAP search with automatic retry.

        Retries on transient LDAP failures (session terminated, socket errors)
        by reconnecting and re-executing, matching the pattern used by
        _execute_with_retry for regular LDAP operations.

        Args:
            cookie: DirSync cookie bytes.
            is_initial: Whether this is the first sync.
            flags: DirSync flags bitmask.

        Returns:
            DirSyncResult with parsed changes.

        Raises:
            DirSyncPermissionError: If the account lacks DirSync rights.
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            # Ensure we have a live connection
            if not self._connection or not self._connection.bound:
                await self.connect(force_reconnect=(attempt > 0))
            conn = self._connection

            try:
                return self._execute_dirsync_search(conn, cookie, is_initial, flags)
            except (LDAPSessionTerminatedByServerError, LDAPSocketOpenError) as e:
                last_error = e
                self.logger.warning(
                    f"DirSync LDAP connection error (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )
                self._connection = None
                continue
            except DirSyncPermissionError:
                raise
            except Exception:
                raise

        raise Exception(f"DirSync query failed after {self.MAX_RETRIES} attempts: {last_error}")

    def _execute_dirsync_search(
        self,
        conn: Connection,
        cookie: bytes,
        is_initial: bool,
        flags: int,
    ) -> DirSyncResult:
        """Execute the actual DirSync LDAP search on a given connection.

        Separated from _execute_dirsync_query to allow retry logic to wrap it.

        Args:
            conn: Active LDAP Connection.
            cookie: DirSync cookie bytes.
            is_initial: Whether this is the first sync.
            flags: DirSync flags bitmask.

        Returns:
            DirSyncResult with parsed changes.

        Raises:
            DirSyncPermissionError: If the account lacks DirSync rights.
        """
        dirsync_ctrl = self._build_dirsync_control(cookie=cookie, flags=flags)
        show_deleted_ctrl = (LDAP_SERVER_SHOW_DELETED_OID, True, None)

        # Search for group objects with member attribute
        search_filter = "(&(objectClass=group)(objectCategory=group))"
        attributes = ["sAMAccountName", "member", "distinguishedName", "objectGUID", "isDeleted"]

        try:
            success = conn.search(
                search_base=self.search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                controls=[dirsync_ctrl, show_deleted_ctrl],
            )
        except Exception as e:
            error_str = str(e).lower()
            if "insufficient" in error_str or "rights" in error_str or "8514" in error_str:
                raise DirSyncPermissionError(
                    f"Account lacks 'Replicating Directory Changes' permission: {e}"
                ) from e
            raise

        if not success:
            result_code = conn.result.get("result", -1)
            description = conn.result.get("description", "unknown")
            if result_code == 8:  # LDAP_STRONG_AUTH_REQUIRED
                raise DirSyncPermissionError(
                    f"DirSync requires stronger auth or privileges: {description}"
                )
            self.logger.warning(f"DirSync search failed: {result_code} {description}")
            # Return empty result with same cookie (retry next time)
            return DirSyncResult(new_cookie=cookie)

        # Parse response control for new cookie
        resp_controls = conn.result.get("controls", {})
        new_cookie, more_results = self._parse_dirsync_response_control(resp_controls)

        # Process entries into membership changes
        incremental_mode = bool(flags & LDAP_DIRSYNC_INCREMENTAL_VALUES) and not is_initial
        changes, modified_ids, deleted_ids = self._process_dirsync_entries(
            conn.entries, is_initial, incremental_mode
        )

        return DirSyncResult(
            changes=changes,
            new_cookie=new_cookie,
            modified_group_ids=modified_ids,
            deleted_group_ids=deleted_ids,
            more_results=more_results,
        )

    def _process_dirsync_entries(  # noqa: C901
        self,
        entries: List,
        is_initial: bool,
        incremental_mode: bool,
    ) -> Tuple[List[MembershipChange], Set[str], Set[str]]:
        """Parse DirSync LDAP entries into MembershipChange objects.

        Args:
            entries: LDAP search result entries.
            is_initial: Whether this is the first sync.
            incremental_mode: If True, member attribute contains only deltas.

        Returns:
            Tuple of (changes_list, modified_group_ids_set, deleted_group_ids_set).
        """
        changes: List[MembershipChange] = []
        modified_group_ids: Set[str] = set()
        deleted_group_ids: Set[str] = set()

        for entry in entries:
            group_name = self._get_entry_attr(entry, "sAMAccountName")

            # In incremental DirSync, sAMAccountName may not be returned for
            # entries where only the member attribute changed. Fall back to
            # extracting CN from the distinguishedName.
            if not group_name:
                dn = self._get_entry_attr(entry, "distinguishedName")
                if dn:
                    cn_match = re.match(r"CN=([^,]+)", dn, re.IGNORECASE)
                    if cn_match:
                        group_name = cn_match.group(1)
                        self.logger.debug(
                            f"DirSync: sAMAccountName missing, extracted CN from DN: {group_name}"
                        )
            if not group_name:
                self.logger.debug("DirSync: skipping entry with no sAMAccountName or DN")
                continue

            group_id = f"ad:{group_name.lower()}"
            is_deleted = self._get_entry_attr(entry, "isDeleted")

            if is_deleted and str(is_deleted).upper() == "TRUE":
                # Group was deleted from AD -- all its memberships must be removed
                # immediately by the pipeline to prevent stale access
                deleted_group_ids.add(group_id)
                self.logger.info(f"DirSync: group deleted from AD: {group_id}")
                continue

            added_dns, removed_dns = self._get_entry_members(entry, incremental_mode)
            if not added_dns and not removed_dns:
                continue

            modified_group_ids.add(group_id)

            for member_dn in added_dns:
                resolved = self._resolve_member_dn_sync(member_dn)
                if resolved:
                    member_id, member_type = resolved
                    changes.append(
                        MembershipChange(
                            change_type=ACLChangeType.ADD,
                            member_id=member_id,
                            member_type=member_type,
                            group_id=group_id,
                            group_name=group_name,
                        )
                    )

            for member_dn in removed_dns:
                resolved = self._resolve_member_dn_sync(member_dn)
                if resolved:
                    member_id, member_type = resolved
                    changes.append(
                        MembershipChange(
                            change_type=ACLChangeType.REMOVE,
                            member_id=member_id,
                            member_type=member_type,
                            group_id=group_id,
                            group_name=group_name,
                        )
                    )

        return changes, modified_group_ids, deleted_group_ids

    def _get_entry_attr(self, entry: Any, attr_name: str) -> Optional[str]:
        """Safely get a string attribute from an LDAP entry.

        Handles both ldap3 Entry objects (with .value property) and plain dicts.

        Args:
            entry: An ldap3 search result entry.
            attr_name: Attribute name to retrieve.

        Returns:
            String value or None.
        """
        try:
            # ldap3 Entry objects use attribute access with .value
            attr = getattr(entry, attr_name, None)
            if attr is not None:
                val = getattr(attr, "value", attr)
                if val is None:
                    return None
                if isinstance(val, (list, tuple)):
                    return str(val[0]) if val else None
                return str(val) if val else None

            # Fallback to dict-style access
            val = entry[attr_name]
            if val is None:
                return None
            if isinstance(val, (list, tuple)):
                return str(val[0]) if val else None
            return str(val) if val else None
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    def _get_entry_members(  # noqa: C901
        self,
        entry: Any,
        incremental_mode: bool,
    ) -> Tuple[List[str], List[str]]:
        """Extract added and removed member DNs from a DirSync entry.

        In incremental mode with INCREMENTAL_VALUES flag:
        - The "member" attribute contains ADDED members
        - Removed members appear in ranged attributes like "member;range=0-0"
          accessible via entry.entry_attributes

        In full mode, all members are treated as "added".

        Args:
            entry: LDAP search result entry.
            incremental_mode: Whether only deltas are returned.

        Returns:
            Tuple of (added_dns, removed_dns).
        """
        added: List[str] = []
        removed: List[str] = []

        # Get the "member" attribute (added members in incremental mode, all in full)
        try:
            member_attr = getattr(entry, "member", None)
            if member_attr is not None:
                vals = getattr(member_attr, "values", None) or getattr(member_attr, "value", None)
                if vals is None:
                    vals = []
                elif isinstance(vals, str):
                    vals = [vals]
                else:
                    vals = list(vals)
                members_raw = vals
            else:
                members_raw = entry.get("member", []) if hasattr(entry, "get") else []
                if isinstance(members_raw, str):
                    members_raw = [members_raw]
        except (KeyError, TypeError, AttributeError):
            members_raw = []

        if not incremental_mode:
            # Full mode -- all members are "adds"
            added = [str(dn) for dn in members_raw if dn]
            return added, removed

        # Incremental mode -- "member" attribute has added DNs
        added = [str(dn) for dn in members_raw if dn]

        # Look for removed members in ranged attributes.
        # AD DirSync with INCREMENTAL_VALUES encodes removals as ranged attributes
        # like "member;range=0-0" in the entry's attribute list.
        try:
            entry_attrs = getattr(entry, "entry_attributes", [])
            for attr_name in entry_attrs:
                attr_str = str(attr_name)
                if attr_str.startswith("member;range="):
                    # This is a removal range -- get its values
                    try:
                        range_attr = getattr(entry, attr_str, None)
                        if range_attr is not None:
                            range_vals = getattr(range_attr, "values", None) or getattr(
                                range_attr, "value", None
                            )
                            if range_vals is None:
                                continue
                            if isinstance(range_vals, str):
                                range_vals = [range_vals]
                            removed.extend(str(dn) for dn in range_vals if dn)
                    except (AttributeError, TypeError):
                        pass
        except (AttributeError, TypeError):
            pass

        return added, removed

    def _resolve_member_dn_sync(
        self,
        member_dn: str,
    ) -> Optional[Tuple[str, str]]:
        """Resolve a member DN to (member_id, member_type) synchronously.

        Uses the existing DN cache and the cached LDAP connection.

        Args:
            member_dn: Distinguished Name of the member.

        Returns:
            Tuple of (canonical_id, "user"|"group") or None if unresolvable.
        """
        # Check DN cache first
        if member_dn in self._dn_cache:
            cached = self._dn_cache[member_dn]
            if cached is None:
                return None
            object_classes, sam_account_name = cached
        else:
            # Query via cached connection
            if not self._connection or not self._connection.bound:
                self.logger.warning(f"No LDAP connection for resolving DN: {member_dn}")
                return None
            result = self._query_member_cached(self._connection, member_dn)
            if not result:
                return None
            object_classes, sam_account_name = result

        classes_lower = [c.lower() for c in object_classes]

        if "group" in classes_lower:
            return (f"ad:{sam_account_name.lower()}", "group")
        elif "user" in classes_lower or "person" in classes_lower:
            return (sam_account_name.lower(), "user")

        return None
