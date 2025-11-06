"""Access control membership model."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.source_connection import SourceConnection


class AccessControlMembership(OrganizationBase):
    """Membership tuple for access control (source-agnostic).

    Clean tuple design: (member_id, member_type) → group_id

    Examples:
    - User-to-group: ("john@acme.com", "user", "group-frontend")
    - Group-to-group: ("group-frontend", "group", "group-engineering")

    Used at search time to expand group principals into user principals.
    """

    # when expanded: {
    #     "john@acme.com" : [user:john@acme.com, group:group-frontend, group:group-engineering],
    # }

    __tablename__ = "access_control_membership"

    # Member (the principal joining the group)
    member_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # Email for users, ID for groups
    member_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" or "group"

    # Parent group (the group being joined)
    group_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Source info (generic - works for any source)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    source_connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_connection.id", ondelete="CASCADE"), nullable=False
    )

    # Relationship
    source_connection: Mapped["SourceConnection"] = relationship("SourceConnection", lazy="noload")

    __table_args__ = (
        # Composite lookup: member identity
        Index("idx_acl_membership_member", "organization_id", "member_id", "member_type"),
        # Lookup by parent group
        Index("idx_acl_membership_group", "organization_id", "group_id"),
        # Lookup by source for cleanup
        Index("idx_acl_membership_source", "source_connection_id"),
        # Unique constraint: one membership per (org, member, group, source_connection)
        Index(
            "uq_acl_membership",
            "organization_id",
            "member_id",
            "member_type",
            "group_id",
            "source_connection_id",
            unique=True,
        ),
    )
