"""Access control schemas (Pydantic models)."""

from enum import Enum
from typing import List, Optional, Set

from pydantic import BaseModel, Field


class ACLChangeType(str, Enum):
    """Type of ACL change for incremental sync."""

    ADD = "add"  # Membership added
    REMOVE = "remove"  # Membership removed
    DELETE_USER = "delete_user"  # User deleted from AD
    DELETE_GROUP = "delete_group"  # Group deleted from AD


class MembershipChange(BaseModel):
    """Represents a single membership change for incremental ACL sync.

    Used by sources that support continuous ACL sync (e.g., AD DirSync).
    Unlike MembershipTuple which represents state, this represents a change event.

    Examples:
    - User added to group: MembershipChange(
        change_type=ACLChangeType.ADD,
        member_id="john",
        member_type="user",
        group_id="ad:engineering",
        group_name="Engineering"
      )
    - User removed from group: MembershipChange(
        change_type=ACLChangeType.REMOVE,
        member_id="john",
        member_type="user",
        group_id="ad:engineering"
      )
    - User deleted from AD: MembershipChange(
        change_type=ACLChangeType.DELETE_USER,
        member_id="john",
        member_type="user"
      )
    """

    change_type: ACLChangeType = Field(description="Type of change (add/remove/delete)")
    member_id: str = Field(description="ID of the member affected")
    member_type: str = Field(default="user", description="'user' or 'group'")
    group_id: Optional[str] = Field(
        default=None, description="Group ID (not set for delete_user/delete_group)"
    )
    group_name: Optional[str] = Field(default=None, description="Human-readable group name")


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
