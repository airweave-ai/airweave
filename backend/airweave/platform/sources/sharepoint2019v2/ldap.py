"""Active Directory LDAP client for SharePoint 2019 V2.

This module provides LDAP connectivity to Active Directory for:
- Expanding AD group memberships (group → users, group → nested groups)
- Resolving AD principals to canonical identifiers
- Resolving SIDs to sAMAccountNames for entity access control

Performance optimizations:
- DN resolution caching: Avoids redundant LDAP lookups for the same Distinguished Names
- Group expansion memoization: Caches fully-expanded group membership results
- Automatic reconnection: Recovers from LDAP session timeouts
"""

import ssl
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from ldap3 import BASE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPSessionTerminatedByServerError, LDAPSocketOpenError

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sources.sharepoint2019v2.acl import extract_canonical_id


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
