"""Asana permission-aware vector search components."""

from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from airweave.core.logging import logger
from airweave.crud import integration_credential, user
from airweave.db.session import get_db_context
from airweave.models.integration_credential import IntegrationCredential


class AsanaUserPermission(BaseModel):
    """Represents a user's permissions in Asana.

    This class represents a user's identity and permissions in Asana.
    It contains the necessary context to evaluate Asana permissions
    at query time.
    """

    user_email: str
    user_gid: str
    workspaces: List[Dict[str, str]] = Field(default_factory=list)  # [{gid, name}]
    teams: List[Dict[str, str]] = Field(default_factory=list)  # [{gid, name}]

    @classmethod
    async def from_email(cls, email: str) -> "AsanaUserPermission":
        """Create an Asana permission object for a user based on their email.

        Args:
            email: The user's email address

        Returns:
            An AsanaUserPermission object with the user's Asana permissions

        Raises:
            ValueError: If no user or valid credentials found
        """
        # Get the user's Asana credentials
        async with get_db_context() as db:
            # Get the user record first
            user_obj = await user.get_by_email(db, email=email)
            if not user_obj:
                raise ValueError(f"User with email {email} not found")

            # Find Asana credentials for this user
            credentials = await integration_credential.get_all_for_source(
                db, user=user_obj, source_short_name="asana"
            )

            if not credentials or len(credentials) == 0:
                logger.warning(f"No Asana credentials found for user {email}")
                # Return minimal permissions object
                return cls(user_email=email, user_gid="", workspaces=[], teams=[])

            # Use the first valid credential
            cred: IntegrationCredential = credentials[0]
            access_token = cred.credentials.get("access_token")

            if not access_token:
                raise ValueError("Invalid Asana credentials: missing access_token")

            base_url = "https://app.asana.com/api/1.0"

            # Fetch user data from Asana API
            async with httpx.AsyncClient() as client:
                # Get user profile
                user_response = await client.get(
                    f"{base_url}/users/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_response.raise_for_status()
                user_data = user_response.json().get("data", {})

                # Get workspaces
                workspaces_response = await client.get(
                    f"{base_url}/workspaces",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                workspaces_response.raise_for_status()
                workspaces_data = workspaces_response.json().get("data", [])

                # Get teams (can only get teams per workspace)
                teams = []
                for workspace in workspaces_data:
                    teams_response = await client.get(
                        f"{base_url}/workspaces/{workspace['gid']}/teams",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if teams_response.status_code == 200:
                        teams_data = teams_response.json().get("data", [])
                        teams.extend(teams_data)
                    else:
                        logger.warning(
                            f"Failed to get teams for workspace {workspace['gid']}: "
                            f"{teams_response.status_code} {teams_response.text}"
                        )

            # Create and return the permission object
            return cls(
                user_email=email,
                user_gid=user_data.get("gid", ""),
                workspaces=[{"gid": w["gid"], "name": w["name"]} for w in workspaces_data],
                teams=[{"gid": t["gid"], "name": t["name"]} for t in teams],
            )


class AsanaPermissionMetadata(BaseModel):
    """Asana-specific permission metadata for entities.

    This class represents the permission data stored with each Asana entity
    during ingestion.
    """

    source_name: str = "asana"
    created_by_gid: Optional[str] = None
    assigned_to_gid: Optional[str] = None
    workspace_gid: Optional[str] = None
    team_gid: Optional[str] = None
    is_public: bool = False
    # For projects
    members: List[Dict[str, str]] = Field(default_factory=list)  # [{gid, name}]
    # For tasks
    followers: List[Dict[str, str]] = Field(default_factory=list)  # [{gid, name}]
    # Project memberships for tasks
    memberships: List[Dict[str, Any]] = Field(default_factory=list)


class AsanaPermissionFilters:
    """Builds Qdrant filters for Asana permissions."""

    @staticmethod
    async def build_filters(user_email: str) -> Dict[str, Any]:  # TODO: make pydantic
        """Build Qdrant filters for a specific user's Asana permissions.

        Args:
            user_email: The user's email address

        Returns:
            A Qdrant-compatible filter dictionary
        """
        try:
            # Get the user's Asana permissions
            auth = await AsanaUserPermission.from_email(user_email)

            # Filter building logic
            filter_dict = {
                "must": [
                    {"key": "sync_metadata.permissions.source_name", "match": {"value": "asana"}},
                ],
                "should": [
                    # User created the item
                    {
                        "key": "sync_metadata.permissions.created_by_gid",
                        "match": {"value": auth.user_gid},
                    },
                    # User is assigned to the item
                    {
                        "key": "sync_metadata.permissions.assigned_to_gid",
                        "match": {"value": auth.user_gid},
                    },
                    # Item is public
                    {"key": "sync_metadata.permissions.is_public", "match": {"value": True}},
                ],
            }

            # Add workspace-level access if user has workspaces
            if auth.workspaces:
                workspace_filters = []
                for workspace in auth.workspaces:
                    workspace_filters.append(
                        {
                            "key": "sync_metadata.permissions.workspace_gid",
                            "match": {"value": workspace["gid"]},
                        }
                    )
                filter_dict["should"].extend(workspace_filters)

            # Add team-level access if user has teams
            if auth.teams:
                team_filters = []
                for team in auth.teams:
                    team_filters.append(
                        {
                            "key": "sync_metadata.permissions.team_gid",
                            "match": {"value": team["gid"]},
                        }
                    )
                filter_dict["should"].extend(team_filters)

            # Add membership checks for projects - check if user is in the members list
            # This requires array matching in Qdrant, which is more complex
            member_filter = {
                "key": "sync_metadata.permissions.members",
                "match": {"any": {"key": "gid", "match": {"value": auth.user_gid}}},
            }
            filter_dict["should"].append(member_filter)

            # Add follower checks for tasks
            follower_filter = {
                "key": "sync_metadata.permissions.followers",
                "match": {"any": {"key": "gid", "match": {"value": auth.user_gid}}},
            }
            filter_dict["should"].append(follower_filter)

            # Add project membership checks for tasks
            # This is the most complex case where we need to check if the user
            # is a member of any of the projects in the task's memberships
            project_membership_filter = {
                "key": "sync_metadata.permissions.memberships",
                "match": {
                    "any": {
                        "key": "project",
                        "match": {
                            "any": {
                                "key": "members",
                                "match": {"any": {"key": "gid", "match": {"value": auth.user_gid}}},
                            }
                        },
                    }
                },
            }
            filter_dict["should"].append(project_membership_filter)

            logger.info(f"Built Asana permission filters for user {user_email}")
            return filter_dict

        except Exception as e:
            logger.error(f"Error building Asana filters: {e}")
            # Return default filter that won't match anything if there's an error
            return {
                "must": [
                    {"key": "sync_metadata.permissions.source_name", "match": {"value": "asana"}},
                    {
                        "key": "sync_metadata.permissions.created_by_gid",
                        "match": {"value": "INVALID-USER-GID"},
                    },
                ]
            }
