"""Unit tests for the SharePoint 2019 V2 source connector."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from airweave.platform.entities.sharepoint2019v2 import (
    SharePoint2019V2FileDeletionEntity,
    SharePoint2019V2ItemDeletionEntity,
)
from airweave.platform.sources.sharepoint2019v2.ldap import (
    DIRSYNC_FLAGS_BASIC,
    DIRSYNC_FLAGS_FULL,
    DirSyncPermissionError,
    DirSyncResult,
    LDAPClient,
)
from airweave.platform.sources.sharepoint2019v2.source import SharePoint2019V2Source


@pytest.fixture
def source_with_ad():
    """Create a SharePoint2019V2Source with AD config populated."""
    source = SharePoint2019V2Source()
    source._ad_username = "admin"
    source._ad_password = "pass"
    source._ad_domain = "DOMAIN"
    source._ad_server = "ldaps://server:636"
    source._ad_search_base = "DC=DOMAIN,DC=local"
    return source


@pytest.fixture
def source_without_ad():
    """Create a SharePoint2019V2Source without AD config."""
    source = SharePoint2019V2Source()
    source._ad_username = ""
    source._ad_password = ""
    source._ad_domain = ""
    source._ad_server = ""
    source._ad_search_base = ""
    return source


class TestSupportsIncrementalAcl:
    """Tests for supports_incremental_acl().

    The method should return True only when AD config is present AND the
    class has supports_continuous=True (set by the @source decorator).
    """

    def test_returns_true_with_ad_config(self, source_with_ad):
        """With AD config and supports_continuous=True on the class, should return True."""
        assert source_with_ad.supports_incremental_acl() is True

    def test_returns_false_without_ad_config(self, source_without_ad):
        """Without AD config, should return False even though class supports continuous."""
        assert source_without_ad.supports_incremental_acl() is False

    def test_reads_class_attribute_not_instance(self, source_with_ad):
        """Should read supports_continuous from the class, not an instance attribute."""
        # The @source decorator sets supports_continuous as a class attribute.
        # Verify the method checks the class, not the instance.
        assert hasattr(SharePoint2019V2Source, "supports_continuous")
        assert SharePoint2019V2Source.supports_continuous is True


class TestDeletionEntities:
    """Tests for deletion entity construction during incremental sync.

    Deletion entities must include deletion_status and breadcrumbs
    to pass BaseEntity validation.
    """

    def test_file_deletion_entity_valid(self):
        """FileDeletionEntity should accept deletion_status and breadcrumbs."""
        entity = SharePoint2019V2FileDeletionEntity(
            list_id="87b63068-d1f6-4cef-8b80-1759e2b538fb",
            item_id=12345,
            sp_entity_id="sp2019v2:file:87b63068:12345",
            label="Deleted file 12345 from 87b63068",
            deletion_status="removed",
            breadcrumbs=[],
        )
        assert entity.deletion_status == "removed"
        assert entity.breadcrumbs == []
        assert entity.list_id == "87b63068-d1f6-4cef-8b80-1759e2b538fb"
        assert entity.item_id == 12345

    def test_item_deletion_entity_valid(self):
        """ItemDeletionEntity should accept deletion_status and breadcrumbs."""
        entity = SharePoint2019V2ItemDeletionEntity(
            list_id="87b63068-d1f6-4cef-8b80-1759e2b538fb",
            item_id=67890,
            sp_entity_id="sp2019v2:item:87b63068:67890",
            label="Deleted item 67890 from 87b63068",
            deletion_status="removed",
            breadcrumbs=[],
        )
        assert entity.deletion_status == "removed"
        assert entity.breadcrumbs == []
        assert entity.list_id == "87b63068-d1f6-4cef-8b80-1759e2b538fb"
        assert entity.item_id == 67890

    def test_file_deletion_entity_missing_deletion_status_fails(self):
        """FileDeletionEntity without deletion_status should raise ValidationError."""
        with pytest.raises(Exception):
            SharePoint2019V2FileDeletionEntity(
                list_id="87b63068",
                item_id=1,
                sp_entity_id="sp2019v2:file:87b63068:1",
                label="Deleted file",
                breadcrumbs=[],
            )

    def test_file_deletion_entity_missing_breadcrumbs_fails(self):
        """FileDeletionEntity without breadcrumbs should raise ValidationError."""
        with pytest.raises(Exception):
            SharePoint2019V2FileDeletionEntity(
                list_id="87b63068",
                item_id=1,
                sp_entity_id="sp2019v2:file:87b63068:1",
                label="Deleted file",
                deletion_status="removed",
            )


class TestDirSyncFlagFallback:
    """Tests for DirSync error 12 (unavailableCriticalExtension) handling.

    Some AD servers don't support the LDAP_DIRSYNC_INCREMENTAL_VALUES flag
    (0x80000000) and return error 12. The code should fall back to basic
    flags (0) on this error.
    """

    @pytest.fixture
    def ldap_client(self):
        """Create an LDAPClient with mocked logger."""
        client = LDAPClient(
            server="ldaps://server:636",
            username="admin",
            password="pass",
            domain="DOMAIN",
            search_base="DC=DOMAIN,DC=local",
            logger=MagicMock(),
        )
        return client

    def test_error_12_raises_dirsync_permission_error(self, ldap_client):
        """Error code 12 should raise DirSyncPermissionError to trigger fallback."""
        conn = MagicMock()
        conn.search.return_value = False
        conn.result = {"result": 12, "description": "unavailableCriticalExtension"}

        with pytest.raises(DirSyncPermissionError, match="flag not supported"):
            ldap_client._execute_dirsync_search(
                conn, cookie=b"", is_initial=True, flags=DIRSYNC_FLAGS_FULL
            )

    def test_error_8_raises_dirsync_permission_error(self, ldap_client):
        """Error code 8 (strong auth required) should also raise DirSyncPermissionError."""
        conn = MagicMock()
        conn.search.return_value = False
        conn.result = {"result": 8, "description": "strongAuthRequired"}

        with pytest.raises(DirSyncPermissionError, match="stronger auth"):
            ldap_client._execute_dirsync_search(
                conn, cookie=b"", is_initial=True, flags=DIRSYNC_FLAGS_FULL
            )

    def test_other_errors_return_empty_result(self, ldap_client):
        """Non-permission errors should return empty DirSyncResult."""
        conn = MagicMock()
        conn.search.return_value = False
        conn.result = {"result": 1, "description": "operationsError"}

        result = ldap_client._execute_dirsync_search(
            conn, cookie=b"test", is_initial=False, flags=DIRSYNC_FLAGS_BASIC
        )
        assert isinstance(result, DirSyncResult)
        assert result.new_cookie == b"test"
        assert len(result.changes) == 0

    @pytest.mark.asyncio
    async def test_permission_error_propagates_no_fallback(self, ldap_client):
        """DirSyncPermissionError propagates — no silent retry with basic flags."""

        async def mock_query(cookie, is_initial, flags):
            raise DirSyncPermissionError("flag not supported")

        ldap_client._execute_dirsync_query = mock_query

        with pytest.raises(DirSyncPermissionError):
            await ldap_client.get_membership_changes(cookie_b64="")
