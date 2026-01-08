"""Active Directory LDAP client for SharePoint 2019 V2.

This module provides LDAP connectivity to Active Directory for:
- Expanding AD group memberships (group → users, group → nested groups)
- Resolving AD principals to canonical identifiers
- Resolving SIDs to sAMAccountNames for entity access control
"""

import ssl
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from ldap3 import BASE, SUBTREE, Connection, Server, Tls

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sources.sharepoint2019v2.acl import extract_canonical_id


class LDAPClient:
    """Client for Active Directory LDAP operations.

    Handles LDAP connectivity with automatic protocol negotiation:
    1. Tries LDAPS (port 636) first
    2. Falls back to STARTTLS on port 389

    Args:
        server: AD server hostname or IP
        username: AD username for authentication
        password: AD password
        domain: AD domain (e.g., 'CONTOSO')
        search_base: LDAP search base DN (e.g., 'DC=contoso,DC=local')
        logger: Logger instance
    """

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

    async def connect(self) -> Connection:
        """Establish LDAP connection to Active Directory.

        Tries LDAPS first, then falls back to STARTTLS.

        Returns:
            Bound LDAP Connection

        Raises:
            Exception: If both connection methods fail
        """
        if self._connection and self._connection.bound:
            return self._connection

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

        # Prevent infinite recursion
        if group_name.lower() in visited_groups:
            self.logger.debug(f"Skipping already-visited group: {group_name}")
            return
        visited_groups.add(group_name.lower())

        # Connect to AD
        conn = await self.connect()

        # Query AD for this group
        search_filter = f"(&(objectClass=group)(sAMAccountName={group_name}))"
        conn.search(
            search_base=self.search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["cn", "distinguishedName", "member"],
            size_limit=1000,
        )

        if not conn.entries:
            self.logger.warning(f"AD group not found: {group_name}")
            return

        group_entry = conn.entries[0]
        members = self._get_members(group_entry)
        self.logger.info(f"AD group '{group_name}' has {len(members)} members")

        # Canonical group_id format: "ad:groupname"
        # This matches entity access format: "group:ad:groupname"
        membership_group_id = f"ad:{group_name.lower()}"

        for member_dn in members:
            # Query member to determine type (user or group)
            member_info = self._query_member(conn, member_dn)
            if not member_info:
                continue

            object_classes, sam_account_name = member_info

            if "user" in object_classes:
                # AD Group → User
                # member_id is raw sAMAccountName (lowercase)
                self.logger.debug(f"  → User member: {sam_account_name}")
                yield MembershipTuple(
                    member_id=sam_account_name.lower(),
                    member_type="user",
                    group_id=membership_group_id,
                    group_name=group_name,
                )

            elif "group" in object_classes:
                # AD Group → AD Group (nested)
                # member_id uses "ad:groupname" format
                nested_group_id = f"ad:{sam_account_name.lower()}"
                self.logger.info(f"  → Nested group member: {sam_account_name} (will recurse)")
                yield MembershipTuple(
                    member_id=nested_group_id,
                    member_type="group",
                    group_id=membership_group_id,
                    group_name=group_name,
                )

                # Recurse into nested group
                nested_login = f"{self.domain}\\{sam_account_name}"
                async for nested_membership in self.expand_group_recursive(
                    nested_login, visited_groups
                ):
                    yield nested_membership

    def _get_members(self, group_entry: Any) -> List[str]:
        """Extract member DNs from LDAP group entry."""
        if hasattr(group_entry, "member"):
            return [str(m) for m in group_entry.member]
        return []

    def _query_member(self, conn: Connection, member_dn: str) -> Optional[tuple]:
        """Query a member DN to determine its type and sAMAccountName.

        Args:
            conn: LDAP connection
            member_dn: Distinguished Name of the member

        Returns:
            Tuple of (object_classes_list, sAMAccountName) or None
        """
        try:
            conn.search(
                search_base=member_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=["objectClass", "sAMAccountName"],
            )
        except Exception as e:
            self.logger.warning(f"LDAP query failed for member DN '{member_dn}': {e}")
            return None

        if not conn.entries:
            self.logger.debug(f"No LDAP entry found for member DN: {member_dn}")
            return None

        member_entry = conn.entries[0]

        # Extract object classes
        object_classes = []
        if hasattr(member_entry, "objectClass"):
            object_classes = [str(oc).lower() for oc in member_entry.objectClass]

        # Extract sAMAccountName
        sam_account_name = None
        if hasattr(member_entry, "sAMAccountName"):
            sam_account_name = str(member_entry.sAMAccountName)

        if not sam_account_name:
            self.logger.debug(f"No sAMAccountName for member DN: {member_dn}")
            return None

        self.logger.debug(
            f"Resolved member DN '{member_dn}' → {sam_account_name} (classes: {object_classes})"
        )
        return object_classes, sam_account_name
