"""Unit tests for AccessBroker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from airweave.platform.access_control.broker import AccessBroker
from airweave.platform.access_control.schemas import AccessContext
from airweave.platform.entities._base import AccessControl


@pytest.fixture
def broker():
    """Create AccessBroker instance."""
    return AccessBroker()


@pytest.fixture
def organization_id():
    """Sample organization ID."""
    return uuid4()


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


class TestAccessBrokerBasicResolution:
    """Test basic access context resolution."""

    @pytest.mark.asyncio
    async def test_resolve_access_context_for_user_with_no_memberships(
        self, broker, mock_db, organization_id
    ):
        """Test resolution for user with no group memberships."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:
            mock_crud.access_control_membership.get_by_member = AsyncMock(return_value=[])

            result = await broker.resolve_access_context(
                db=mock_db, user_principal="john@acme.com", organization_id=organization_id
            )

            assert isinstance(result, AccessContext)
            assert result.user_principal == "john@acme.com"
            assert result.user_principals == ["user:john@acme.com"]
            assert result.group_principals == []
            assert len(result.all_principals) == 1

    @pytest.mark.asyncio
    async def test_resolve_access_context_for_user_with_direct_groups(
        self, broker, mock_db, organization_id
    ):
        """Test resolution for user with direct group memberships."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:
            # Mock membership data
            membership1 = MagicMock()
            membership1.group_id = "sp:engineering"
            membership1.group_name = "Engineering"

            membership2 = MagicMock()
            membership2.group_id = "ad:frontend"
            membership2.group_name = "Frontend Team"

            mock_crud.access_control_membership.get_by_member = AsyncMock(return_value=[membership1, membership2])

            result = await broker.resolve_access_context(
                db=mock_db, user_principal="john@acme.com", organization_id=organization_id
            )

            assert result.user_principal == "john@acme.com"
            assert result.user_principals == ["user:john@acme.com"]
            assert len(result.group_principals) == 2
            assert "group:sp:engineering" in result.group_principals
            assert "group:ad:frontend" in result.group_principals
            assert len(result.all_principals) == 3

    @pytest.mark.asyncio
    async def test_resolve_access_context_returns_user_and_group_principals(
        self, broker, mock_db, organization_id
    ):
        """Test that all_principals property combines user and group principals."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:
            membership = MagicMock()
            membership.group_id = "sp:site_owners"
            mock_crud.access_control_membership.get_by_member = AsyncMock(return_value=[membership])

            result = await broker.resolve_access_context(
                db=mock_db, user_principal="admin@acme.com", organization_id=organization_id
            )

            all_principals = result.all_principals
            assert "user:admin@acme.com" in all_principals
            assert "group:sp:site_owners" in all_principals
            assert len(all_principals) == 2


class TestAccessBrokerCollectionScoping:
    """Test collection-scoped access resolution."""

    @pytest.mark.asyncio
    async def test_resolve_for_collection_filters_by_readable_collection_id(
        self, broker, mock_db, organization_id
    ):
        """Test that collection resolution filters by readable_collection_id."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:
            membership = MagicMock()
            membership.group_id = "sp:engineering"
            mock_crud.access_control_membership.get_by_member_and_collection = AsyncMock(return_value=[membership])
            
            # Mock get_by_member for group expansion (returns empty for simplicity)
            mock_crud.access_control_membership.get_by_member = AsyncMock(return_value=[])

            # Mock _collection_has_ac_sources to return True
            with patch.object(broker, "_collection_has_ac_sources", new=AsyncMock(return_value=True)):
                result = await broker.resolve_access_context_for_collection(
                    db=mock_db,
                    user_principal="john@acme.com",
                    readable_collection_id="my-collection",
                    organization_id=organization_id,
                )

                # Verify CRUD was called with collection filter
                mock_crud.access_control_membership.get_by_member_and_collection.assert_called_once_with(
                    db=mock_db,
                    member_id="john@acme.com",
                    member_type="user",
                    readable_collection_id="my-collection",
                    organization_id=organization_id,
                )

                assert isinstance(result, AccessContext)
                assert "group:sp:engineering" in result.group_principals

    @pytest.mark.asyncio
    async def test_resolve_for_collection_returns_none_when_no_ac_sources(
        self, broker, mock_db, organization_id
    ):
        """Test that resolution returns None if collection has no AC sources."""
        # Mock _collection_has_ac_sources to return False
        with patch.object(broker, "_collection_has_ac_sources", new=AsyncMock(return_value=False)):
            result = await broker.resolve_access_context_for_collection(
                db=mock_db,
                user_principal="john@acme.com",
                readable_collection_id="my-collection",
                organization_id=organization_id,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_collection_has_ac_sources_returns_false_for_empty_collection(
        self, broker, mock_db, organization_id
    ):
        """Test _collection_has_ac_sources returns False when no memberships exist."""
        # Mock database query to return False
        mock_result = MagicMock()
        mock_result.scalar.return_value = False
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await broker._collection_has_ac_sources(
            db=mock_db,
            readable_collection_id="empty-collection",
            organization_id=organization_id,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_collection_has_ac_sources_returns_true_when_memberships_exist(
        self, broker, mock_db, organization_id
    ):
        """Test _collection_has_ac_sources returns True when memberships exist."""
        # Mock database query to return True
        mock_result = MagicMock()
        mock_result.scalar.return_value = True
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await broker._collection_has_ac_sources(
            db=mock_db,
            readable_collection_id="collection-with-acl",
            organization_id=organization_id,
        )

        assert result is True


class TestAccessBrokerGroupExpansion:
    """Test recursive group membership expansion."""

    @pytest.mark.asyncio
    async def test_expand_group_memberships_handles_nested_groups(
        self, broker, mock_db, organization_id
    ):
        """Test expansion of nested group-to-group relationships."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:
            # Mock nested groups: frontend -> engineering -> all-staff
            async def mock_get_by_member(db, member_id, member_type, organization_id):
                if member_id == "frontend" and member_type == "group":
                    parent = MagicMock()
                    parent.group_id = "engineering"
                    return [parent]
                elif member_id == "engineering" and member_type == "group":
                    parent = MagicMock()
                    parent.group_id = "all-staff"
                    return [parent]
                return []

            mock_crud.access_control_membership.get_by_member = AsyncMock(side_effect=mock_get_by_member)

            result = await broker._expand_group_memberships(
                db=mock_db, group_ids=["frontend"], organization_id=organization_id
            )

            # Should include all levels: frontend, engineering, all-staff
            assert "frontend" in result
            assert "engineering" in result
            assert "all-staff" in result
            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_expand_group_memberships_handles_circular_references(
        self, broker, mock_db, organization_id
    ):
        """Test that circular group references don't cause infinite loops."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:

            async def mock_get_by_member(db, member_id, member_type, organization_id):
                # Create circular reference: group-a -> group-b -> group-a
                if member_id == "group-a" and member_type == "group":
                    parent = MagicMock()
                    parent.group_id = "group-b"
                    return [parent]
                elif member_id == "group-b" and member_type == "group":
                    parent = MagicMock()
                    parent.group_id = "group-a"
                    return [parent]
                return []

            mock_crud.access_control_membership.get_by_member = AsyncMock(side_effect=mock_get_by_member)

            result = await broker._expand_group_memberships(
                db=mock_db, group_ids=["group-a"], organization_id=organization_id
            )

            # Should handle circular reference gracefully
            assert "group-a" in result
            assert "group-b" in result
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_expand_group_memberships_respects_max_depth(
        self, broker, mock_db, organization_id
    ):
        """Test that expansion stops at max depth to prevent abuse."""
        with patch("airweave.platform.access_control.broker.crud") as mock_crud:

            call_count = 0

            async def mock_get_by_member(db, member_id, member_type, organization_id):
                nonlocal call_count
                call_count += 1
                # Always return a new parent group (infinite nesting)
                parent = MagicMock()
                parent.group_id = f"level-{call_count}"
                return [parent]

            mock_crud.access_control_membership.get_by_member = AsyncMock(side_effect=mock_get_by_member)

            result = await broker._expand_group_memberships(
                db=mock_db, group_ids=["level-0"], organization_id=organization_id
            )

            # Should stop at max depth (10 in implementation)
            assert len(result) <= 12  # initial + 10 levels + some tolerance


class TestAccessBrokerEntityAccess:
    """Test entity-level access checking."""

    def test_check_entity_access_returns_true_for_public_entities(self, broker):
        """Test that public entities are accessible to everyone."""
        entity_access = AccessControl(viewers=["group:sp:owners"], is_public=True)
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=[],
        )

        result = broker.check_entity_access(entity_access, access_context)

        assert result is True

    def test_check_entity_access_returns_true_for_null_access_control(self, broker):
        """Test that entities without access control are accessible to everyone."""
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=[],
        )

        result = broker.check_entity_access(None, access_context)

        assert result is True

    def test_check_entity_access_returns_true_when_principal_matches(self, broker):
        """Test that entities are accessible when user's principal matches viewers."""
        entity_access = AccessControl(
            viewers=["group:sp:engineering", "user:jane@acme.com"], is_public=False
        )
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering"],
        )

        result = broker.check_entity_access(entity_access, access_context)

        assert result is True

    def test_check_entity_access_returns_false_when_no_match(self, broker):
        """Test that entities are not accessible when no principals match."""
        entity_access = AccessControl(
            viewers=["group:sp:owners", "user:admin@acme.com"], is_public=False
        )
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering"],
        )

        result = broker.check_entity_access(entity_access, access_context)

        assert result is False

    def test_check_entity_access_returns_true_when_no_access_context(self, broker):
        """Test that entities are accessible when no access context (no AC sources)."""
        entity_access = AccessControl(viewers=["group:sp:owners"], is_public=False)

        result = broker.check_entity_access(entity_access, None)

        assert result is True

    def test_check_entity_access_returns_true_when_empty_viewers(self, broker):
        """Test that entities with empty viewers list are accessible (legacy behavior)."""
        entity_access = AccessControl(viewers=[], is_public=False)
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=[],
        )

        result = broker.check_entity_access(entity_access, access_context)

        assert result is True

