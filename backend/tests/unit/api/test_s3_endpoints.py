"""Unit tests for S3 destination endpoints.

Mocks external dependencies to test endpoint logic in isolation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel

from airweave.api.v1.endpoints.s3 import (
    S3ConfigRequest,
    configure_s3_destination,
    validate_s3_connection,
    delete_s3_configuration,
    get_s3_status,
)
from airweave.core.shared_models import ConnectionStatus, FeatureFlag


@pytest.fixture
def mock_db():
    """Mock AsyncSession."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_ctx():
    """Mock ApiContext with S3_DESTINATION feature enabled."""
    ctx = MagicMock()
    ctx.organization.id = uuid4()
    ctx.user.email = "test@example.com"
    ctx.logger = MagicMock()
    ctx.has_feature = MagicMock(return_value=True)
    return ctx


@pytest.fixture
def valid_s3_config():
    """Valid S3 configuration request."""
    return S3ConfigRequest(
        role_arn="arn:aws:iam::123456789012:role/airweave-writer",
        external_id="airweave-test-external-id-12345",
        bucket_name="test-bucket",
        bucket_prefix="airweave/",
        aws_region="us-east-1",
    )


class TestConfigureS3Destination:
    """Test suite for POST /s3/configure endpoint."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, mock_db, mock_ctx, valid_s3_config):
        """Test that endpoint rejects requests when feature flag is disabled."""
        mock_ctx.has_feature.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await configure_s3_destination(valid_s3_config, mock_db, mock_ctx)

        assert exc_info.value.status_code == 403
        assert "S3_DESTINATION feature not enabled" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, mock_db, mock_ctx, valid_s3_config):
        """Test that endpoint validates credentials by testing connection."""
        with patch(
            "airweave.api.v1.endpoints.s3.S3Destination.create",
            side_effect=Exception("AssumeRole failed"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await configure_s3_destination(valid_s3_config, mock_db, mock_ctx)

            assert exc_info.value.status_code == 400
            assert "S3 connection test failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_new_connection(self, mock_db, mock_ctx, valid_s3_config):
        """Test creating a new S3 connection."""
        # Mock S3Destination.create to succeed
        with patch("airweave.api.v1.endpoints.s3.S3Destination.create"):
            # Mock no existing connection
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            # Mock encryption
            with patch("airweave.api.v1.endpoints.s3.encrypt", return_value=b"encrypted"):
                response = await configure_s3_destination(
                    valid_s3_config, mock_db, mock_ctx
                )

                assert response.status == "created"
                assert "created successfully" in response.message
                assert mock_db.commit.called
                assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_update_existing_connection(self, mock_db, mock_ctx, valid_s3_config):
        """Test updating an existing S3 connection."""
        # Mock S3Destination.create to succeed
        with patch("airweave.api.v1.endpoints.s3.S3Destination.create"):
            # Mock existing connection
            existing_conn = MagicMock()
            existing_conn.id = uuid4()
            existing_conn.integration_credential_id = uuid4()

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing_conn
            mock_db.execute.return_value = mock_result

            # Mock credential retrieval (must be AsyncMock for async function)
            mock_cred = MagicMock()
            with patch("airweave.api.v1.endpoints.s3.crud") as mock_crud:
                mock_crud.integration_credential.get = AsyncMock(return_value=mock_cred)

                with patch("airweave.api.v1.endpoints.s3.encrypt", return_value=b"encrypted"):
                    response = await configure_s3_destination(
                        valid_s3_config, mock_db, mock_ctx
                    )

                    assert response.status == "updated"
                    assert "updated successfully" in response.message
                    assert mock_db.commit.called
                    # Check that ctx was passed to get()
                    mock_crud.integration_credential.get.assert_called_once()
                    call_args = mock_crud.integration_credential.get.call_args
                    assert call_args.kwargs.get("ctx") == mock_ctx


class TestValidateS3Connection:
    """Test suite for POST /s3/test endpoint."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, mock_ctx, valid_s3_config):
        """Test that validate endpoint rejects requests when feature flag is disabled."""
        mock_ctx.has_feature.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await validate_s3_connection(valid_s3_config, mock_ctx)

        assert exc_info.value.status_code == 403
        assert "S3_DESTINATION feature not enabled" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_successful_connection(self, mock_ctx, valid_s3_config):
        """Test successful S3 connection validation."""
        with patch("airweave.api.v1.endpoints.s3.S3Destination.create"):
            response = await validate_s3_connection(valid_s3_config, mock_ctx)

            assert response["status"] == "success"
            assert valid_s3_config.bucket_name in response["message"]
            assert response["role_arn"] == valid_s3_config.role_arn

    @pytest.mark.asyncio
    async def test_connection_failure(self, mock_ctx, valid_s3_config):
        """Test failed S3 connection validation."""
        error_msg = "Access Denied: Invalid external ID"
        with patch(
            "airweave.api.v1.endpoints.s3.S3Destination.create",
            side_effect=Exception(error_msg),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_s3_connection(valid_s3_config, mock_ctx)

            assert exc_info.value.status_code == 400
            assert "Connection test failed" in exc_info.value.detail
            assert error_msg in exc_info.value.detail


class TestDeleteS3Configuration:
    """Test suite for DELETE /s3/configure endpoint."""

    @pytest.mark.asyncio
    async def test_connection_not_found(self, mock_db, mock_ctx):
        """Test deleting non-existent S3 connection."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await delete_s3_configuration(mock_db, mock_ctx)

        assert exc_info.value.status_code == 404
        assert "S3 connection not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_connection_with_credentials(self, mock_db, mock_ctx):
        """Test deleting S3 connection with credentials."""
        # Mock existing connection with credentials
        connection = MagicMock()
        connection.integration_credential_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connection
        mock_db.execute.return_value = mock_result

        # Mock credential retrieval (must be AsyncMock for async function)
        mock_cred = MagicMock()
        with patch("airweave.api.v1.endpoints.s3.crud") as mock_crud:
            mock_crud.integration_credential.get = AsyncMock(return_value=mock_cred)

            response = await delete_s3_configuration(mock_db, mock_ctx)

            assert response["status"] == "success"
            assert "removed" in response["message"]
            assert mock_db.delete.call_count == 2  # Both cred and connection
            assert mock_db.commit.called
            # Check that ctx was passed to get()
            mock_crud.integration_credential.get.assert_called_once()
            call_args = mock_crud.integration_credential.get.call_args
            assert call_args.kwargs.get("ctx") == mock_ctx

    @pytest.mark.asyncio
    async def test_delete_connection_without_credentials(self, mock_db, mock_ctx):
        """Test deleting S3 connection without credentials."""
        # Mock existing connection without credentials
        connection = MagicMock()
        connection.integration_credential_id = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connection
        mock_db.execute.return_value = mock_result

        response = await delete_s3_configuration(mock_db, mock_ctx)

        assert response["status"] == "success"
        assert mock_db.delete.call_count == 1  # Only connection
        assert mock_db.commit.called


class TestGetS3Status:
    """Test suite for GET /s3/status endpoint."""

    @pytest.mark.asyncio
    async def test_feature_disabled(self, mock_db, mock_ctx):
        """Test status endpoint when feature flag is disabled."""
        mock_ctx.has_feature.return_value = False

        response = await get_s3_status(mock_db, mock_ctx)

        assert response["feature_enabled"] is False
        assert response["configured"] is False
        assert "not enabled" in response["message"]

    @pytest.mark.asyncio
    async def test_not_configured(self, mock_db, mock_ctx):
        """Test status when S3 is not configured."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await get_s3_status(mock_db, mock_ctx)

        assert response["feature_enabled"] is True
        assert response["configured"] is False
        assert "not configured" in response["message"]

    @pytest.mark.asyncio
    async def test_configured_with_details(self, mock_db, mock_ctx):
        """Test status when S3 is configured."""
        # Mock configured connection
        connection = MagicMock()
        connection.id = uuid4()
        connection.integration_credential_id = uuid4()
        connection.status = ConnectionStatus.ACTIVE
        connection.created_at = MagicMock()
        connection.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connection
        mock_db.execute.return_value = mock_result

        # Mock credential with decrypted data
        mock_cred = MagicMock()
        mock_cred.encrypted_credentials = b"encrypted"

        with patch("airweave.api.v1.endpoints.s3.crud") as mock_crud:
            mock_crud.integration_credential.get = AsyncMock(return_value=mock_cred)

            with patch(
                "airweave.core.credentials.decrypt",
                return_value={
                    "bucket_name": "test-bucket",
                    "role_arn": "arn:aws:iam::123456789012:role/airweave-writer",
                },
            ):
                response = await get_s3_status(mock_db, mock_ctx)

                assert response["feature_enabled"] is True
                assert response["configured"] is True
                assert response["bucket_name"] == "test-bucket"
                assert "arn:aws:iam" in response["role_arn"]
                assert response["status"] == ConnectionStatus.ACTIVE
                # Check that ctx was passed to get()
                mock_crud.integration_credential.get.assert_called_once()
                call_args = mock_crud.integration_credential.get.call_args
                assert call_args.kwargs.get("ctx") == mock_ctx

    @pytest.mark.asyncio
    async def test_configured_with_decryption_error(self, mock_db, mock_ctx):
        """Test status when credentials exist but decryption fails."""
        # Mock configured connection
        connection = MagicMock()
        connection.id = uuid4()
        connection.integration_credential_id = uuid4()
        connection.status = ConnectionStatus.ACTIVE
        connection.created_at = MagicMock()
        connection.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = connection
        mock_db.execute.return_value = mock_result

        # Mock credential with decryption error
        mock_cred = MagicMock()
        with patch("airweave.api.v1.endpoints.s3.crud") as mock_crud:
            mock_crud.integration_credential.get = AsyncMock(return_value=mock_cred)

            with patch(
                "airweave.core.credentials.decrypt", side_effect=Exception("Decryption failed")
            ):
                response = await get_s3_status(mock_db, mock_ctx)

                # Should still return configured=True, but no sensitive details
                assert response["feature_enabled"] is True
                assert response["configured"] is True
                assert response["bucket_name"] is None
                assert response["role_arn"] is None
