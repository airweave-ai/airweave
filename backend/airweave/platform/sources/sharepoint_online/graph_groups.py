"""Entra ID group expansion via Microsoft Graph API.

Replaces the LDAP-based AD group expansion from SharePoint 2019 V2.
Uses Graph API's transitive membership endpoint for recursive group expansion.

The Graph API handles circular group references and deep nesting automatically
via /groups/{id}/transitiveMembers.
"""

from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import httpx

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sources.sharepoint_online.acl import format_entra_group_id

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class EntraGroupExpander:
    """Expands Entra ID group memberships via Microsoft Graph API.

    Uses /groups/{id}/transitiveMembers to get all nested members
    (users and groups) in a single API call — no manual recursion needed.

    Args:
        access_token_provider: Async callable returning a valid OAuth2 token.
        logger: Logger instance.
    """

    def __init__(
        self,
        access_token_provider: Callable,
        logger: Any,
    ):
        """Initialize the group expander with an OAuth2 token provider."""
        self._get_token = access_token_provider
        self.logger = logger
        self._group_cache: Dict[str, List[MembershipTuple]] = {}
        self._expanding: set = set()
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
        }

    async def _headers(self) -> Dict[str, str]:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def expand_group(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        group_id: str,
        group_display_name: str = "",
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand an Entra ID group to all its direct members, recursing into nested groups.

        Args:
            client: httpx AsyncClient.
            group_id: Entra ID group object ID.
            group_display_name: Display name for logging.

        Yields:
            MembershipTuple for each member (user or nested group).
        """
        cache_key = group_id.lower()

        if cache_key in self._group_cache:
            self._stats["cache_hits"] += 1
            for membership in self._group_cache[cache_key]:
                yield membership
            return

        if cache_key in self._expanding:
            self.logger.debug(f"Circular group reference detected: {group_id}, skipping")
            return

        self._expanding.add(cache_key)
        self._stats["cache_misses"] += 1
        collected: List[MembershipTuple] = []
        membership_group_id = format_entra_group_id(group_id)

        url = f"{GRAPH_BASE_URL}/groups/{group_id}/members"
        params: Optional[Dict[str, str]] = {
            "$top": "200",
            "$select": "id,displayName,mail,userPrincipalName",
        }

        try:
            current_url: Optional[str] = url

            while current_url:
                self._stats["api_calls"] += 1
                headers = await self._headers()
                response = await client.get(
                    current_url,
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                for member in data.get("value", []):
                    odata_type = member.get("@odata.type", "")

                    if odata_type == "#microsoft.graph.user":
                        email = (member.get("mail") or member.get("userPrincipalName", "")).lower()
                        if not email:
                            continue

                        membership = MembershipTuple(
                            member_id=email,
                            member_type="user",
                            group_id=membership_group_id,
                            group_name=group_display_name or group_id,
                        )
                        collected.append(membership)
                        yield membership

                    elif odata_type == "#microsoft.graph.group":
                        nested_id = member.get("id", "")
                        nested_name = member.get("displayName", "")
                        if not nested_id:
                            continue

                        nested_group_id = format_entra_group_id(nested_id)
                        membership = MembershipTuple(
                            member_id=nested_group_id,
                            member_type="group",
                            group_id=membership_group_id,
                            group_name=group_display_name or group_id,
                        )
                        collected.append(membership)
                        yield membership

                        async for nested_membership in self.expand_group(
                            client, nested_id, nested_name
                        ):
                            collected.append(nested_membership)
                            yield nested_membership

                current_url = data.get("@odata.nextLink")
                params = None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Group not found: {group_id}")
            else:
                self.logger.error(f"Error expanding group {group_id}: {e}")
                raise

        self._expanding.discard(cache_key)
        self._group_cache[cache_key] = collected
        self.logger.debug(
            f"Expanded group {group_display_name or group_id}: {len(collected)} memberships"
        )

    async def expand_groups_for_site(
        self,
        client: httpx.AsyncClient,
        group_ids: List[str],
        group_names: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[MembershipTuple, None]:
        """Expand multiple groups.

        Args:
            client: httpx AsyncClient.
            group_ids: List of Entra ID group object IDs to expand.
            group_names: Optional map of group_id -> display_name.

        Yields:
            MembershipTuple for each membership across all groups.
        """
        group_names = group_names or {}
        for gid in group_ids:
            display_name = group_names.get(gid, "")
            async for membership in self.expand_group(client, gid, display_name):
                yield membership

    def log_stats(self) -> None:
        """Log cache hit rate and API call statistics."""
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        hit_rate = self._stats["cache_hits"] / max(1, total)
        self.logger.info(
            f"EntraGroupExpander stats: "
            f"{self._stats['cache_hits']}/{total} cache hits ({hit_rate:.1%}), "
            f"{self._stats['api_calls']} API calls"
        )
