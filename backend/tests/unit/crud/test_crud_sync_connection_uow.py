"""Tests for CRUD sync_connection UnitOfWork handling."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.crud.crud_sync_connection import CRUDSyncConnection
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.sync_connection import DestinationRole


class TestCRUDSyncConnectionUnitOfWork:
    """Test that CRUD operations properly handle UnitOfWork."""

    @pytest.fixture
    def crud(self):
        """Create CRUD instance."""
        return CRUDSyncConnection()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()
        return db

    @pytest.fixture
    def mock_uow(self):
        """Create mock UnitOfWork."""
        uow = MagicMock(spec=UnitOfWork)
        # Important: UoW does NOT have flush() method
        assert not hasattr(uow, "flush")
        return uow

    @pytest.mark.asyncio
    async def test_create_without_uow_commits(self, crud, mock_db):
        """Test create() without UoW commits immediately."""
        sync_id = uuid4()
        connection_id = uuid4()
        
        await crud.create(
            db=mock_db,
            sync_id=sync_id,
            connection_id=connection_id,
            role=DestinationRole.ACTIVE,
            uow=None,
        )
        
        # Should commit and refresh
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_uow_no_commit(self, crud, mock_db, mock_uow):
        """Test create() with UoW does NOT commit (UoW handles it)."""
        sync_id = uuid4()
        connection_id = uuid4()
        
        await crud.create(
            db=mock_db,
            sync_id=sync_id,
            connection_id=connection_id,
            role=DestinationRole.ACTIVE,
            uow=mock_uow,
        )
        
        # Should NOT commit or refresh (UoW handles on __aexit__)
        mock_db.commit.assert_not_called()
        mock_db.refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_role_without_uow_commits(self, crud, mock_db):
        """Test update_role() without UoW commits immediately."""
        slot_id = uuid4()
        
        # Mock get() to return None (simplified)
        crud.get = AsyncMock(return_value=None)
        
        await crud.update_role(
            db=mock_db,
            id=slot_id,
            role=DestinationRole.SHADOW,
            uow=None,
        )
        
        # Should commit
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_role_with_uow_no_commit(self, crud, mock_db, mock_uow):
        """Test update_role() with UoW does NOT commit."""
        slot_id = uuid4()
        
        crud.get = AsyncMock(return_value=None)
        
        await crud.update_role(
            db=mock_db,
            id=slot_id,
            role=DestinationRole.SHADOW,
            uow=mock_uow,
        )
        
        # Should NOT commit
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_update_role_without_uow_commits(self, crud, mock_db):
        """Test bulk_update_role() without UoW commits immediately."""
        sync_id = uuid4()
        mock_result = MagicMock(rowcount=5)
        mock_db.execute.return_value = mock_result
        
        rowcount = await crud.bulk_update_role(
            db=mock_db,
            sync_id=sync_id,
            from_role=DestinationRole.ACTIVE,
            to_role=DestinationRole.DEPRECATED,
            uow=None,
        )
        
        # Should commit
        mock_db.commit.assert_called_once()
        assert rowcount == 5

    @pytest.mark.asyncio
    async def test_bulk_update_role_with_uow_no_commit(self, crud, mock_db, mock_uow):
        """Test bulk_update_role() with UoW does NOT commit."""
        sync_id = uuid4()
        mock_result = MagicMock(rowcount=5)
        mock_db.execute.return_value = mock_result
        
        rowcount = await crud.bulk_update_role(
            db=mock_db,
            sync_id=sync_id,
            from_role=DestinationRole.ACTIVE,
            to_role=DestinationRole.DEPRECATED,
            uow=mock_uow,
        )
        
        # Should NOT commit
        mock_db.commit.assert_not_called()
        assert rowcount == 5

    @pytest.mark.asyncio
    async def test_remove_without_uow_commits(self, crud, mock_db):
        """Test remove() without UoW commits immediately."""
        slot_id = uuid4()
        mock_obj = MagicMock()
        crud.get = AsyncMock(return_value=mock_obj)
        
        result = await crud.remove(
            db=mock_db,
            id=slot_id,
            uow=None,
        )
        
        # Should commit
        mock_db.commit.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_with_uow_no_commit(self, crud, mock_db, mock_uow):
        """Test remove() with UoW does NOT commit."""
        slot_id = uuid4()
        mock_obj = MagicMock()
        crud.get = AsyncMock(return_value=mock_obj)
        
        result = await crud.remove(
            db=mock_db,
            id=slot_id,
            uow=mock_uow,
        )
        
        # Should NOT commit
        mock_db.commit.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_uow_does_not_have_flush_method(self, mock_uow):
        """Test that UnitOfWork does NOT have flush() method (regression test)."""
        # This test documents the bug we fixed: code was calling uow.flush()
        # which doesn't exist on UnitOfWork
        assert not hasattr(mock_uow, "flush")
        
        # Attempting to call flush() would raise AttributeError
        with pytest.raises(AttributeError):
            mock_uow.flush()


class TestCRUDSyncConnectionTransactionBehavior:
    """Integration-style tests for transaction behavior."""

    @pytest.fixture
    def crud(self):
        return CRUDSyncConnection()

    @pytest.mark.asyncio
    async def test_multiple_operations_with_uow_single_transaction(self, crud):
        """Test that multiple operations with same UoW use single transaction."""
        mock_db = AsyncMock()
        mock_uow = MagicMock(spec=UnitOfWork)
        
        sync_id = uuid4()
        conn_id1 = uuid4()
        conn_id2 = uuid4()
        
        # Create multiple connections in same UoW
        await crud.create(mock_db, sync_id=sync_id, connection_id=conn_id1, uow=mock_uow)
        await crud.create(mock_db, sync_id=sync_id, connection_id=conn_id2, uow=mock_uow)
        
        # Neither should commit (UoW commits once at end)
        assert mock_db.commit.call_count == 0

    @pytest.mark.asyncio
    async def test_operations_without_uow_multiple_commits(self, crud):
        """Test that operations without UoW commit individually."""
        mock_db = AsyncMock()
        
        sync_id = uuid4()
        conn_id1 = uuid4()
        conn_id2 = uuid4()
        
        # Create multiple connections without UoW
        await crud.create(mock_db, sync_id=sync_id, connection_id=conn_id1, uow=None)
        await crud.create(mock_db, sync_id=sync_id, connection_id=conn_id2, uow=None)
        
        # Each should commit separately
        assert mock_db.commit.call_count == 2

