"""Fake organization service for testing."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.domains.organizations.protocols import OrganizationServiceProtocol
from airweave.models.user import User


class FakeOrganizationService(OrganizationServiceProtocol):
    """In-memory fake that records calls and returns canned responses."""

    def __init__(self) -> None:
        self._calls: list[tuple[str, ...]] = []

    async def create_organization(
        self,
        db: AsyncSession,
        org_data: schemas.OrganizationCreate,
        owner_user: User,
    ) -> schemas.Organization:
        """Return a canned Organization schema."""
        self._calls.append(("create_organization",))
        now = datetime.utcnow()
        return schemas.Organization(
            id=uuid4(),
            name=org_data.name,
            description=getattr(org_data, "description", ""),
            created_at=now,
            modified_at=now,
            role="owner",
        )

    async def delete_organization(
        self, db: AsyncSession, organization_id: UUID, deleting_user: User
    ) -> bool:
        """Record and return success."""
        self._calls.append(("delete_organization", str(organization_id)))
        return True

    async def invite_user(
        self,
        db: AsyncSession,
        organization_id: UUID,
        email: str,
        role: str,
        inviter_user: schemas.User,
    ) -> dict:
        """Record and return canned invitation."""
        self._calls.append(("invite_user", email))
        return {"id": f"inv_{uuid4().hex[:8]}", "email": email, "role": role}

    async def remove_member(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, remover_user: User
    ) -> bool:
        """Record and return success."""
        self._calls.append(("remove_member", str(user_id)))
        return True

    async def change_member_role(
        self, db: AsyncSession, organization_id: UUID, user_id: UUID, new_role: str
    ) -> bool:
        """Record and return success."""
        self._calls.append(("change_member_role", str(user_id), new_role))
        return True

    async def leave_organization(
        self, db: AsyncSession, organization_id: UUID, leaving_user: User
    ) -> bool:
        """Record and return success."""
        self._calls.append(("leave_organization", str(organization_id)))
        return True

    async def get_members(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return empty member list."""
        self._calls.append(("get_members",))
        return []

    async def get_pending_invitations(self, db: AsyncSession, organization_id: UUID) -> list[dict]:
        """Return empty invitation list."""
        self._calls.append(("get_pending_invitations",))
        return []

    async def remove_invitation(
        self, db: AsyncSession, organization_id: UUID, invitation_id: str
    ) -> bool:
        """Record and return success."""
        self._calls.append(("remove_invitation", invitation_id))
        return True

    async def provision_new_user(
        self, db: AsyncSession, user_data: dict, *, create_org: bool = False
    ) -> schemas.User:
        """Record and return a canned User schema."""
        self._calls.append(("provision_new_user",))
        return schemas.User(
            id=uuid4(),
            email=user_data.get("email", "fake@test.com"),
            full_name=user_data.get("full_name", "Fake User"),
            auth0_id=user_data.get("auth0_id"),
            user_organizations=[],
        )

    async def sync_user_organizations(self, db: AsyncSession, user: schemas.User) -> schemas.User:
        """Return user unchanged."""
        self._calls.append(("sync_user_organizations",))
        return user
