"""Access control schemas (Pydantic models)."""

from enum import Enum
from typing import List, Optional, Set

from pydantic import BaseModel, Field


class ACLChangeType(str, Enum):
    """Type of ACL membership change for incremental sync."""

    ADD = "add"
    REMOVE = "remove"


class MembershipChange(BaseModel):
    """A single ACL membership change (add or remove).

    Used for incremental ACL sync -- sources return a list of these
    instead of the full membership set when doing delta updates.
    """

    change_type: ACLChangeType
    member_id: str = Field(description="Email for users, ID for groups")
    member_type: str = Field(description="'user' or 'group'")
    group_id: str = Field(description="The group this member belongs to")
    group_name: Optional[str] = None


class MembershipTuple(BaseModel):
    """Lightweight membership tuple yielded by sources during access control sync.

    This is the internal representation used during sync processing. Sources yield
    these tuples, which are then persisted via the CRUD layer (which adds DB fields
    like id, organization_id, timestamps).

    Clean tuple design: (member_id, member_type) → group_id

    Examples:
    - User-to-group: MembershipTuple(
        member_id="john@acme.com",
        member_type="user",
        group_id="group-engineering"
      )
    - Group-to-group: MembershipTuple(
        member_id="group-frontend",
        member_type="group",
        group_id="group-engineering"
      )

    Note: SharePoint uses /transitivemembers to flatten nested groups,
    so only user-type tuples are created. Other sources may create group-type tuples.

    See also: airweave.schemas.access_control.AccessControlMembership for full DB schema.
    """

    member_id: str = Field(description="Email for users, ID for groups")
    member_type: str = Field(description="'user' or 'group'")
    group_id: str = Field(description="The group this member belongs to")
    group_name: Optional[str] = None


class AccessContext(BaseModel):
    """User's access context for permission checking (source-agnostic).

    Contains expanded principals: user + all groups they belong to (including transitive).
    """

    user_principal: str = Field(description="User principal (username or identifier)")
    user_principals: List[str] = Field(description="User principals, e.g., ['user:sp_admin']")
    group_principals: List[str] = Field(
        description="Group principals, e.g., ['group:engineering', 'group:design']"
    )

    @property
    def all_principals(self) -> Set[str]:
        """All principals (user + groups) for filtering."""
        return set(self.user_principals + self.group_principals)

    model_config = {"frozen": True}  # Immutable context
