"""Active Directory LDAP client for SharePoint 2019 V2.

This module provides LDAP connectivity to Active Directory for:
- Expanding AD group memberships (group → users, group → nested groups)
- Resolving AD principals to canonical identifiers
- Resolving SIDs to sAMAccountNames for entity access control
- Incremental membership sync via DirSync control

Performance optimizations:
- DN resolution caching: Avoids redundant LDAP lookups for the same Distinguished Names
- Group expansion memoization: Caches fully-expanded group membership results
- Automatic reconnection: Recovers from LDAP session timeouts

DirSync support:
- Uses LDAP_SERVER_DIRSYNC_OID (1.2.840.113556.1.4.841) for incremental sync
- Tracks group membership changes with LDAP_DIRSYNC_INCREMENTAL_VALUES flag
- Returns only added/removed members since last cookie
"""

import base64
import re
import ssl
import time
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

# DirSync control constants
LDAP_SERVER_DIRSYNC_OID = "1.2.840.113556.1.4.841"
LDAP_SERVER_SHOW_DELETED_OID = "1.2.840.113556.1.4.417"

# DirSync flags (can be combined with OR)
LDAP_DIRSYNC_OBJECT_SECURITY = 0x00000001  # Return security info
LDAP_DIRSYNC_ANCESTORS_FIRST_ORDER = 0x00000800  # Parents before children
LDAP_DIRSYNC_PUBLIC_DATA_ONLY = 0x00002000  # Skip confidential attributes
LDAP_DIRSYNC_INCREMENTAL_VALUES = 0x80000000  # Return only changed values (key for ACL!)

# Flag combinations for different sync modes:
# - INCREMENTAL_VALUES (0x80000000) returns only delta (added/removed members)
#   This is preferred for ACL sync as it gives us true deltas
# - flags=0 (default, same as .NET) returns full membership of changed groups
# We use INCREMENTAL_VALUES as primary since it gives us true deltas for ACL sync
DIRSYNC_FLAGS_FULL = LDAP_DIRSYNC_INCREMENTAL_VALUES  # Returns delta only (added/removed)
DIRSYNC_FLAGS_BASIC = 0  # Fallback: returns full membership of changed groups


class DirSyncPermissionError(Exception):
    """Raised when DirSync control is rejected due to insufficient permissions."""

    pass


class DirSyncResult:
    """Result of a DirSync query containing changes and new cookie.

    Attributes:
        changes: List of membership changes (ADDs for members, DELETE_GROUP for deleted)
        new_cookie: Updated DirSync cookie for next incremental sync
        modified_group_ids: Set of group IDs that were modified (for computing removals)
        more_results: Whether more results are available (pagination)
    """

    def __init__(
        self,
        changes: List[MembershipChange],
        new_cookie: bytes,
        modified_group_ids: Optional[Set[str]] = None,
        more_results: bool = False,
    ):
        """Initialize DirSync result with changes and cookie."""
        self.changes = changes
        self.new_cookie = new_cookie
        self.modified_group_ids = modified_group_ids or set()
        self.more_results = more_results

    @property
    def cookie_b64(self) -> str:
        """Return cookie as base64 string for storage."""
        return base64.b64encode(self.new_cookie).decode("ascii") if self.new_cookie else ""

    @classmethod
    def cookie_from_b64(cls, cookie_b64: str) -> bytes:
        """Decode base64 cookie string to bytes."""
        return base64.b64decode(cookie_b64) if cookie_b64 else b""


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

    async def _query_members_batch(
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

    async def expand_group_recursive(
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

    # =========================================================================
    # DirSync Support for Incremental ACL Sync
    # =========================================================================

    def _build_dirsync_control(
        self,
        cookie: bytes = b"",
        flags: int = LDAP_DIRSYNC_INCREMENTAL_VALUES,
        max_bytes: int = 1000000,
    ) -> Tuple[str, bool, bytes]:
        """Build a DirSync request control with correct BER encoding.

        NOTE: We use manual BER encoding because both ldap3 and pyasn1 have bugs
        that cause INCREMENTAL_VALUES (0x80000000) to be encoded incorrectly:

        1. ldap3's dir_sync_control uses ctypes.c_long which is 8 bytes on 64-bit
           systems (macOS, most Linux), so the signed conversion fails.

        2. pyasn1 encodes large negative integers with unnecessary padding bytes
           (e.g., -2147483648 becomes 5 bytes instead of 4).

        AD expects the flags as a minimal 4-byte signed integer:
        - 0x80000000 should be encoded as: 02 04 80 00 00 00
        - NOT as 02 05 00 80 00 00 00 (unsigned, 5 bytes)
        - NOT as 02 05 ff 80 00 00 00 (signed with padding, 5 bytes)

        Args:
            cookie: Previous sync cookie (empty for first sync)
            flags: DirSync flags (default: INCREMENTAL_VALUES for ACL tracking)
            max_bytes: Maximum bytes to return (server may limit further)

        Returns:
            Tuple of (OID, criticality, control_value_bytes) for ldap3
        """
        # Manually build the BER-encoded DirSync control value
        # DirSyncRequestValue ::= SEQUENCE {
        #     Flags      INTEGER,
        #     MaxBytes   INTEGER,
        #     Cookie     OCTET STRING
        # }

        def encode_ber_integer(value: int) -> bytes:
            """Encode an integer using minimal BER encoding (signed)."""
            if value == 0:
                return bytes([0x02, 0x01, 0x00])

            # Convert to signed 32-bit representation
            if value < 0:
                # For negative numbers, use 2's complement
                value = value & 0xFFFFFFFF

            # Convert to bytes (big-endian)
            result = []
            while value > 0 or (result and result[-1] & 0x80):
                result.append(value & 0xFF)
                value >>= 8
            result.reverse()

            # Handle sign: if high bit is set and we want negative, no padding needed
            # If high bit is set and we want positive, add 0x00 padding
            if flags & LDAP_DIRSYNC_INCREMENTAL_VALUES and len(result) == 4 and result[0] & 0x80:
                # This is the INCREMENTAL_VALUES flag - keep as 4 bytes (minimal encoding)
                pass
            elif result and result[0] & 0x80 and value >= 0:
                # Positive number with high bit set - add padding
                result.insert(0, 0x00)

            return bytes([0x02, len(result)]) + bytes(result)

        # Encode flags (handle INCREMENTAL_VALUES specially for minimal encoding)
        if flags & LDAP_DIRSYNC_INCREMENTAL_VALUES:
            # Use exact 4-byte encoding: 02 04 80 00 00 00
            flags_bytes = bytes([0x02, 0x04, 0x80, 0x00, 0x00, 0x00])
        else:
            flags_bytes = encode_ber_integer(flags)

        # Encode max_bytes
        maxbytes_bytes = encode_ber_integer(max_bytes)

        # Encode cookie as OCTET STRING
        cookie_len = len(cookie)
        if cookie_len < 128:
            cookie_bytes = bytes([0x04, cookie_len]) + cookie
        else:
            # Long form length encoding
            len_bytes = []
            temp = cookie_len
            while temp > 0:
                len_bytes.insert(0, temp & 0xFF)
                temp >>= 8
            cookie_bytes = bytes([0x04, 0x80 | len(len_bytes)]) + bytes(len_bytes) + cookie

        # Wrap in SEQUENCE
        content = flags_bytes + maxbytes_bytes + cookie_bytes
        content_len = len(content)
        if content_len < 128:
            control_value = bytes([0x30, content_len]) + content
        else:
            len_bytes = []
            temp = content_len
            while temp > 0:
                len_bytes.insert(0, temp & 0xFF)
                temp >>= 8
            control_value = bytes([0x30, 0x80 | len(len_bytes)]) + bytes(len_bytes) + content

        return (LDAP_SERVER_DIRSYNC_OID, True, control_value)

    def _parse_dirsync_response_control(self, controls) -> Tuple[bytes, bool]:
        """Parse DirSync response control to extract new cookie.

        Handles both formats returned by ldap3:
        1. Dictionary format (when ldap3 can parse the control):
           {'OID': {'value': {'more_results': bool, 'cookie': bytes}}}
        2. List of tuples format (raw):
           [(oid, criticality, value), ...]

        Args:
            controls: Response controls from LDAP operation (dict or list)

        Returns:
            Tuple of (new_cookie, more_results)
        """
        if not controls:
            self.logger.warning("[DirSync] No response controls received from AD server")
            return b"", False

        # Handle dictionary format (ldap3 auto-parsed)
        if isinstance(controls, dict):
            self.logger.debug(f"[DirSync] Response controls (dict): {list(controls.keys())}")
            if LDAP_SERVER_DIRSYNC_OID in controls:
                ctrl_data = controls[LDAP_SERVER_DIRSYNC_OID]
                if isinstance(ctrl_data, dict) and "value" in ctrl_data:
                    value = ctrl_data["value"]
                    if isinstance(value, dict):
                        # ldap3 parsed it for us
                        cookie = value.get("cookie", b"")
                        more_results = value.get("more_results", False)
                        self.logger.debug(
                            f"[DirSync] Cookie extracted (auto-parsed): {len(cookie)} bytes, "
                            f"more_results={more_results}"
                        )
                        return cookie, more_results

        # Handle list of tuples format (raw controls)
        if isinstance(controls, (list, tuple)):
            self.logger.debug(f"[DirSync] Response controls (list): {len(controls)} controls")
            for ctrl in controls:
                if isinstance(ctrl, tuple) and len(ctrl) >= 3:
                    oid, _criticality, value = ctrl[0], ctrl[1], ctrl[2]
                    if oid == LDAP_SERVER_DIRSYNC_OID:
                        # Decode the response value manually
                        decoded, _ = ber_decoder.decode(value, asn1Spec=Sequence())
                        more_results = int(decoded.getComponentByPosition(0)) != 0
                        new_cookie = bytes(decoded.getComponentByPosition(2))
                        self.logger.debug(
                            f"[DirSync] Cookie extracted (raw): {len(new_cookie)} bytes, "
                            f"more_results={more_results}"
                        )
                        return new_cookie, more_results

        # No DirSync control found
        self.logger.warning(
            f"[DirSync] DirSync control OID ({LDAP_SERVER_DIRSYNC_OID}) not in response. "
            "The AD user likely needs 'Replicating Directory Changes' permission on the domain NC."
        )
        return b"", False

    async def get_membership_changes(
        self,
        cookie_b64: str = "",
    ) -> DirSyncResult:
        """Get group membership changes since last sync using DirSync.

        Uses the LDAP_SERVER_DIRSYNC_OID control to efficiently retrieve
        only the changes since the last sync (identified by cookie).

        With LDAP_DIRSYNC_INCREMENTAL_VALUES flag, returns only:
        - Added values: members added to groups
        - Removed values: members removed from groups
        - Deleted objects: groups/users deleted from AD

        IMPORTANT: The sync account needs "Replicating Directory Changes"
        permission on the domain NC root.

        Args:
            cookie_b64: Base64-encoded cookie from previous sync (empty for first sync)

        Returns:
            DirSyncResult with list of MembershipChange objects and new cookie
        """
        cookie = DirSyncResult.cookie_from_b64(cookie_b64)
        is_initial = not cookie

        self.logger.info(
            f"🔄 DirSync ACL query: {'INITIAL (full)' if is_initial else 'INCREMENTAL'}"
        )

        changes: List[MembershipChange] = []
        all_modified_group_ids: Set[str] = set()
        new_cookie = cookie
        more_results = True

        # Keep querying until no more results (DirSync may paginate)
        while more_results:
            result = await self._execute_dirsync_query(new_cookie, is_initial)
            changes.extend(result.changes)
            all_modified_group_ids.update(result.modified_group_ids)
            new_cookie = result.new_cookie
            more_results = result.more_results

            if more_results:
                self.logger.debug(
                    f"DirSync has more results, continuing (got {len(changes)} so far)"
                )

        self.logger.info(
            f"✅ DirSync complete: {len(changes)} membership changes detected, "
            f"{len(all_modified_group_ids)} groups modified"
        )

        return DirSyncResult(
            changes=changes,
            new_cookie=new_cookie,
            modified_group_ids=all_modified_group_ids,
            more_results=False,
        )

    async def _execute_dirsync_query(
        self,
        cookie: bytes,
        is_initial: bool,
        flags: Optional[int] = None,
    ) -> DirSyncResult:
        """Execute a single DirSync query with automatic flag fallback.

        Tries INCREMENTAL_VALUES first (requires "Replicating Directory Changes All").
        If that fails, falls back to PUBLIC_DATA_ONLY (only requires basic permission).

        Args:
            cookie: Current sync cookie
            is_initial: Whether this is the initial (full) sync
            flags: Optional specific flags to use (for retry with fallback)

        Returns:
            DirSyncResult with changes from this query page
        """
        # Track which flags to try
        # INCREMENTAL_VALUES (FULL) gives us just the delta (added/removed members) - preferred
        # flags=0 (BASIC) gives us all current members of changed groups - fallback
        # We try INCREMENTAL_VALUES first since it's more efficient for ACL sync
        flags_to_try = [DIRSYNC_FLAGS_FULL, DIRSYNC_FLAGS_BASIC] if flags is None else [flags]

        # If we've already discovered which flags work, use those
        if hasattr(self, "_dirsync_working_flags") and self._dirsync_working_flags is not None:
            flags_to_try = [self._dirsync_working_flags]

        last_error = None
        for try_flags in flags_to_try:
            try:
                result = await self._execute_dirsync_query_with_flags(cookie, is_initial, try_flags)

                # If successful, remember these flags for future queries
                if not hasattr(self, "_dirsync_working_flags"):
                    self._dirsync_working_flags = None
                if self._dirsync_working_flags != try_flags:
                    flag_name = (
                        "INCREMENTAL_VALUES"
                        if try_flags == DIRSYNC_FLAGS_FULL
                        else "PUBLIC_DATA_ONLY"
                    )
                    self.logger.info(f"[DirSync] Using flags: {flag_name} (0x{try_flags:08x})")
                    self._dirsync_working_flags = try_flags

                return result

            except DirSyncPermissionError as e:
                last_error = e
                flag_name = (
                    "INCREMENTAL_VALUES" if try_flags == DIRSYNC_FLAGS_FULL else "PUBLIC_DATA_ONLY"
                )
                self.logger.warning(
                    f"[DirSync] Flags {flag_name} not permitted, trying fallback..."
                )
                # Need to reconnect after failed critical control
                await self.connect(force_reconnect=True)
                continue

        # All flag combinations failed
        raise Exception(f"DirSync failed with all flag combinations: {last_error}")

    async def _execute_dirsync_query_with_flags(
        self,
        cookie: bytes,
        is_initial: bool,
        flags: int,
    ) -> DirSyncResult:
        """Execute DirSync query with specific flags.

        Args:
            cookie: Current sync cookie
            is_initial: Whether this is the initial (full) sync
            flags: DirSync flags to use

        Returns:
            DirSyncResult with changes from this query page

        Raises:
            DirSyncPermissionError: If server rejects the control (permission issue)
        """

        async def query_func(conn: Connection) -> DirSyncResult:
            self._stats["ldap_queries"] += 1

            # Build DirSync control with specified flags
            dirsync_control = self._build_dirsync_control(cookie=cookie, flags=flags)

            # Also include show-deleted control to see tombstones
            show_deleted_control = (LDAP_SERVER_SHOW_DELETED_OID, True, None)

            # Query for group objects (where member attribute may have changed)
            conn.search(
                search_base=self.search_base,
                search_filter="(objectClass=group)",
                search_scope=SUBTREE,
                attributes=[
                    "sAMAccountName",
                    "member",
                    "isDeleted",
                    "distinguishedName",
                ],
                controls=[dirsync_control, show_deleted_control],
            )

            # Debug: Log the full result structure to diagnose control issues
            self.logger.debug(
                f"[DirSync] LDAP result keys: {list(conn.result.keys()) if conn.result else 'None'}"
            )
            self.logger.debug(
                f"[DirSync] LDAP result type: {conn.result.get('result', 'N/A')}, "
                f"description: {conn.result.get('description', 'N/A')}"
            )
            self.logger.debug(f"[DirSync] Entries returned: {len(conn.entries)}")

            # Check for permission error (unavailableCriticalExtension = 12)
            result_code = conn.result.get("result", 0)
            if result_code == 12:  # unavailableCriticalExtension
                raise DirSyncPermissionError(
                    f"DirSync control rejected (flags=0x{flags:08x}). "
                    "This usually means missing 'Replicating Directory Changes All' permission."
                )

            # Get controls from the result
            response_controls = conn.result.get("controls", [])

            # Parse response control to get new cookie
            new_cookie, more_results = self._parse_dirsync_response_control(response_controls)

            # Process entries to extract membership changes
            # Note: With PUBLIC_DATA_ONLY (no INCREMENTAL_VALUES), we get all current
            # members of changed groups, not just the delta. We handle this the same
            # way for now - the pipeline will deduplicate.
            use_incremental_logic = flags == DIRSYNC_FLAGS_FULL
            changes, modified_group_ids = self._process_dirsync_entries(
                conn.entries, is_initial, incremental_mode=use_incremental_logic
            )

            return DirSyncResult(
                changes=changes,
                new_cookie=new_cookie,
                modified_group_ids=modified_group_ids,
                more_results=more_results,
            )

        return await self._execute_with_retry("dirsync_query", query_func)

    def _process_dirsync_entries(
        self,
        entries: List[Any],
        is_initial: bool,
        incremental_mode: bool = True,
    ) -> Tuple[List[MembershipChange], Set[str]]:
        """Process DirSync entries to extract membership changes.

        For initial sync: All members are treated as "add" operations
        For incremental: Uses DirSync's incremental values (member;range=X-Y)

        Args:
            entries: LDAP entries from DirSync query
            is_initial: Whether this is the initial (full) sync
            incremental_mode: If True, we're using INCREMENTAL_VALUES flag (delta only).
                            If False, we're using PUBLIC_DATA_ONLY (full membership).

        Returns:
            Tuple of (List of MembershipChange objects, Set of modified group IDs)
            The modified_group_ids set is used by the pipeline to compute membership
            removals by comparing against the database state.
        """
        changes: List[MembershipChange] = []
        modified_group_ids: Set[str] = set()

        mode_desc = "INCREMENTAL" if incremental_mode else "FULL_MEMBERSHIP"
        self.logger.debug(
            f"[DirSync] Processing {len(entries)} entries "
            f"(is_initial={is_initial}, mode={mode_desc})"
        )

        for entry in entries:
            # DEBUG: Log all available attributes on the entry
            entry_attrs = []
            if hasattr(entry, "entry_attributes"):
                entry_attrs = list(entry.entry_attributes)
            elif hasattr(entry, "__dict__"):
                entry_attrs = [k for k in entry.__dict__.keys() if not k.startswith("_")]
            self.logger.info(f"[DirSync DEBUG] Entry attributes available: {entry_attrs}")

            # DEBUG: Log the raw entry for inspection
            if hasattr(entry, "entry_dn"):
                self.logger.info(f"[DirSync DEBUG] Entry DN: {entry.entry_dn}")
            if hasattr(entry, "distinguishedName"):
                self.logger.info(f"[DirSync DEBUG] distinguishedName: {entry.distinguishedName}")

            # Get group identity
            # In incremental DirSync mode, sAMAccountName may not be returned if it hasn't changed
            # In that case, extract the CN (Common Name) from the DN as a fallback
            group_name = self._get_entry_attr(entry, "sAMAccountName")
            self.logger.info(
                f"[DirSync DEBUG] sAMAccountName extracted: '{group_name}' "
                f"(raw attr exists: {hasattr(entry, 'sAMAccountName')})"
            )
            if not group_name:
                # Try to extract CN from the DN
                dn = getattr(entry, "entry_dn", None)
                if dn:
                    # Parse DN to extract CN
                    # e.g., "CN=group_name,CN=Users,DC=..." -> "group_name"
                    cn_match = re.match(r"^CN=([^,]+)", dn, re.IGNORECASE)
                    if cn_match:
                        group_name = cn_match.group(1)
                        # For deleted objects, AD appends "\0ADEL:<objectGUID>" to CN
                        # The \0 is a null byte (or escaped as \0 in string repr)
                        # Strip this suffix to get the original group name
                        group_name = re.sub(
                            r"(\x00|\\0)ADEL:[0-9a-f-]+$",
                            "",
                            group_name,
                            flags=re.IGNORECASE,
                        )
                        self.logger.info(
                            f"[DirSync DEBUG] Extracted group name from DN: '{group_name}'"
                        )
            if not group_name:
                self.logger.warning(
                    f"[DirSync DEBUG] Skipping entry - no sAMAccountName and "
                    f"couldn't extract from DN! Entry type: {type(entry)}, "
                    f"attrs: {entry_attrs}"
                )
                continue

            group_name_lower = group_name.lower()
            group_id = f"ad:{group_name_lower}"

            # Check if group was deleted
            is_deleted = self._get_entry_attr(entry, "isDeleted")
            if is_deleted:
                self.logger.debug(f"Group deleted: {group_name}")
                changes.append(
                    MembershipChange(
                        change_type=ACLChangeType.DELETE_GROUP,
                        member_id=group_id,
                        member_type="group",
                    )
                )
                continue

            # Track this group as modified (for computing removals in pipeline)
            # Only for non-deleted groups - deleted groups are handled by DELETE_GROUP
            modified_group_ids.add(group_id)

            # Get member attribute
            # - With INCREMENTAL_VALUES: Only changed members (delta)
            # - Without INCREMENTAL_VALUES: All current members of changed groups

            # DEBUG: Log raw member attribute info
            has_member_attr = hasattr(entry, "member")
            self.logger.info(f"[DirSync DEBUG] Entry has 'member' attr: {has_member_attr}")
            if has_member_attr:
                raw_member = getattr(entry, "member", None)
                self.logger.info(
                    f"[DirSync DEBUG] Raw member attr type: {type(raw_member)}, value: {raw_member}"
                )
                if raw_member:
                    if hasattr(raw_member, "values"):
                        self.logger.info(
                            f"[DirSync DEBUG] member.values: {list(raw_member.values)}"
                        )
                    if hasattr(raw_member, "value"):
                        self.logger.info(f"[DirSync DEBUG] member.value: {raw_member.value}")

            # Get added and removed members (separated by ranged attribute parsing)
            # With INCREMENTAL_VALUES: range=0-X is REMOVED, range=(X+1)-* is ADDED
            added_members, removed_members = self._get_entry_members(
                entry, incremental_mode=(incremental_mode and not is_initial)
            )
            self.logger.info(
                f"[DirSync DEBUG] _get_entry_members returned "
                f"{len(added_members)} added, {len(removed_members)} removed"
            )

            total_members = len(added_members) + len(removed_members)
            if total_members:
                self.logger.debug(
                    f"[DirSync] Group '{group_name}' has {total_members} member changes "
                    f"({len(added_members)} added, {len(removed_members)} removed)"
                )

            # Process ADDED members
            for member_dn in added_members:
                member_info = self._resolve_member_dn_sync(member_dn)
                if member_info:
                    member_type, member_id = member_info
                    changes.append(
                        MembershipChange(
                            change_type=ACLChangeType.ADD,
                            member_id=member_id,
                            member_type=member_type,
                            group_id=group_id,
                            group_name=group_name,
                        )
                    )

            # Process REMOVED members (only in incremental mode)
            for member_dn in removed_members:
                member_info = self._resolve_member_dn_sync(member_dn)
                if member_info:
                    member_type, member_id = member_info
                    changes.append(
                        MembershipChange(
                            change_type=ACLChangeType.REMOVE,
                            member_id=member_id,
                            member_type=member_type,
                            group_id=group_id,
                            group_name=group_name,
                        )
                    )

        # DEBUG: Summary log
        self.logger.info(
            f"[DirSync DEBUG] Processing complete: {len(entries)} entries → "
            f"{len(changes)} membership changes, {len(modified_group_ids)} modified groups"
        )
        if changes:
            for i, c in enumerate(changes[:5]):  # Show first 5
                self.logger.info(
                    f"[DirSync DEBUG] Change {i + 1}: {c.change_type.name} "
                    f"member={c.member_id} ({c.member_type}) → group={c.group_id}"
                )
            if len(changes) > 5:
                self.logger.info(f"[DirSync DEBUG] ... and {len(changes) - 5} more changes")

        return changes, modified_group_ids

    def _get_entry_attr(self, entry: Any, attr_name: str) -> Optional[str]:
        """Safely get an attribute value from an LDAP entry."""
        if hasattr(entry, attr_name):
            val = getattr(entry, attr_name)
            if val:
                return str(val.value) if hasattr(val, "value") else str(val)
        return None

    def _get_entry_members(
        self, entry: Any, incremental_mode: bool = False
    ) -> Tuple[List[str], List[str]]:
        """Get member DNs from an LDAP entry (handles various attribute formats).

        Handles both standard 'member' attribute and ranged 'member;range=X-Y' attributes
        that AD returns for incremental DirSync operations.

        IMPORTANT: With INCREMENTAL_VALUES flag in DirSync:
        - member;range=0-X contains REMOVED members (delta since last cookie)
        - member;range=(X+1)-* contains ADDED members (delta since last cookie)

        Args:
            entry: LDAP entry object
            incremental_mode: If True, properly parse ranged attributes to separate
                            added vs removed members. If False, treat all as current.

        Returns:
            Tuple of (added_members, removed_members) DNs
        """
        added_members = []
        removed_members = []

        def extract_values_from_attr(attr: Any, attr_name: str) -> List[str]:
            """Extract string values from an LDAP attribute."""
            extracted = []
            self.logger.debug(
                f"[_get_entry_members] {attr_name} type: {type(attr)}, "
                f"bool: {bool(attr) if attr is not None else 'None'}"
            )
            if attr:
                if hasattr(attr, "values"):
                    vals = list(attr.values)
                    self.logger.debug(
                        f"[_get_entry_members] {attr_name} Using .values: {len(vals)} items"
                    )
                    extracted.extend([str(m) for m in vals])
                elif hasattr(attr, "value"):
                    # Single value case
                    self.logger.debug(
                        f"[_get_entry_members] {attr_name} Using .value: {attr.value}"
                    )
                    if attr.value:
                        extracted.append(str(attr.value))
                elif hasattr(attr, "__iter__") and not isinstance(attr, str):
                    self.logger.debug(f"[_get_entry_members] {attr_name} Using __iter__")
                    extracted.extend([str(m) for m in attr])
                else:
                    self.logger.debug(
                        f"[_get_entry_members] {attr_name} Unknown format, trying str: {attr}"
                    )
            else:
                self.logger.debug(f"[_get_entry_members] {attr_name} is falsy/empty")
            return extracted

        def parse_range_start(attr_name: str) -> Optional[int]:
            """Parse the start index from a ranged attribute name like 'member;range=0-5'."""
            # Format: member;range=START-END
            match = re.match(r"member;range=(\d+)-", attr_name)
            if match:
                return int(match.group(1))
            return None

        # Standard member attribute (non-ranged) - these are current members
        if hasattr(entry, "member"):
            added_members.extend(extract_values_from_attr(entry.member, "member"))
        else:
            self.logger.debug("[_get_entry_members] No 'member' attribute on entry")

        # Check for ranged member attributes (e.g., 'member;range=0-0')
        # AD returns these in DirSync incremental mode
        if hasattr(entry, "entry_attributes"):
            for attr_name in entry.entry_attributes:
                if attr_name.startswith("member;range="):
                    self.logger.debug(f"[_get_entry_members] Found ranged attribute: {attr_name}")
                    attr_value = getattr(
                        entry, attr_name.replace(";", "_").replace("=", "_").replace("-", "_"), None
                    )
                    # ldap3 converts attribute names like "member;range=0-0" to "member_range_0_0"
                    if attr_value is None:
                        # Try accessing via entry's raw attributes
                        attr_value = entry.entry_attributes_as_dict.get(attr_name)
                    if attr_value:
                        members_in_range = extract_values_from_attr(attr_value, attr_name)

                        if incremental_mode:
                            # With INCREMENTAL_VALUES, range starting at 0 = REMOVED
                            range_start = parse_range_start(attr_name)
                            if range_start == 0:
                                self.logger.debug(
                                    f"[_get_entry_members] {attr_name} is REMOVED range "
                                    f"({len(members_in_range)} members)"
                                )
                                removed_members.extend(members_in_range)
                            else:
                                self.logger.debug(
                                    f"[_get_entry_members] {attr_name} is ADDED range "
                                    f"({len(members_in_range)} members)"
                                )
                                added_members.extend(members_in_range)
                        else:
                            # Not incremental - treat all as current members
                            added_members.extend(members_in_range)

        self.logger.debug(
            f"[_get_entry_members] Returning {len(added_members)} added, "
            f"{len(removed_members)} removed members"
        )
        return added_members, removed_members

    def _resolve_member_dn_sync(self, member_dn: str) -> Optional[Tuple[str, str]]:
        """Synchronously resolve a member DN to (type, id) tuple.

        Uses the DN cache first (O(1) lookup), falls back to AD query if needed.
        The cache is populated during initial sync and previous incremental syncs,
        so most lookups will be cache hits.

        Args:
            member_dn: Distinguished Name of the member

        Returns:
            Tuple of (member_type, member_id) or None
        """
        # Check cache first - O(1), no AD query
        if member_dn in self._dn_cache:
            cached = self._dn_cache[member_dn]
            if cached:
                object_classes, sam_account_name = cached
                if "user" in object_classes:
                    return ("user", sam_account_name.lower())
                elif "group" in object_classes:
                    return ("group", f"ad:{sam_account_name.lower()}")
            return None

        # Cache miss - query AD for accurate type info
        # This only happens for members we haven't seen before
        if self._connection and self._connection.bound:
            result = self._query_member_cached(self._connection, member_dn)
            if result:
                object_classes, sam_account_name = result
                if "user" in object_classes:
                    return ("user", sam_account_name.lower())
                elif "group" in object_classes:
                    return ("group", f"ad:{sam_account_name.lower()}")

        return None
