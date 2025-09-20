# import uuid
# from unittest.mock import AsyncMock, MagicMock, patch

# import pytest
# from fastapi import HTTPException
# from sqlalchemy.ext.asyncio import AsyncSession

# from airweave import crud, schemas
# from airweave.core.connection_service import connection_service
# from airweave.core.exceptions import NotFoundException
# from airweave.core.shared_models import ConnectionStatus, SyncStatus
# from airweave.db.unit_of_work import UnitOfWork
# from airweave.models.integration_credential import IntegrationType
# from airweave.platform.auth.schemas import AuthType, OAuth2TokenResponse


# @pytest.fixture
# def mock_user():
#     return schemas.User(
#         id=uuid.uuid4(), email="test@example.com", organization_id=uuid.uuid4(), is_active=True
#     )


# @pytest.fixture
# def mock_db():
#     return AsyncMock(spec=AsyncSession)


# @pytest.fixture
# def mock_uow():
#     uow = AsyncMock(spec=UnitOfWork)
#     uow.session = AsyncMock(spec=AsyncSession)
#     return uow


# @pytest.fixture
# def connection_id():
#     return uuid.uuid4()


# @pytest.fixture
# def mock_connection():
#     return schemas.Connection(
#         id=uuid.uuid4(),
#         name="Test Connection",
#         integration_type=IntegrationType.SOURCE,
#         status=ConnectionStatus.ACTIVE,
#         integration_credential_id=uuid.uuid4(),
#         short_name="test_source",
#         created_at="2023-01-01T00:00:00",
#         updated_at="2023-01-01T00:00:00",
#     )


# @pytest.mark.asyncio
# class TestConnectionService:
#     # Tests for get_connection
#     async def test_get_connection_success(self, mock_db, mock_user, mock_connection, connection_id):
#         # Arrange
#         crud.connection.get = AsyncMock(return_value=mock_connection)

#         # Act
#         result = await connection_service.get_connection(mock_db, connection_id, mock_user)

#         # Assert
#         crud.connection.get.assert_called_once_with(
#             mock_db, id=connection_id, current_user=mock_user
#         )
#         assert result == mock_connection

#     async def test_get_connection_not_found(self, mock_db, mock_user, connection_id):
#         # Arrange
#         crud.connection.get = AsyncMock(return_value=None)

#         # Act & Assert
#         with pytest.raises(NotFoundException, match="Connection not found"):
#             await connection_service.get_connection(mock_db, connection_id, mock_user)

#         crud.connection.get.assert_called_once_with(
#             mock_db, id=connection_id, current_user=mock_user
#         )

#     # Tests for get_all_connections
#     async def test_get_all_connections(self, mock_db, mock_user):
#         # Arrange
#         connections = [MagicMock(spec=schemas.Connection) for _ in range(3)]
#         crud.connection.get_multi = AsyncMock(return_value=connections)

#         # Act
#         result = await connection_service.get_all_connections(mock_db, mock_user)

#         # Assert
#         crud.connection.get_multi.assert_called_once_with(mock_db, current_user=mock_user)
#         assert result == connections

#     # Tests for get_connections_by_type
#     async def test_get_connections_by_type(self, mock_db, mock_user):
#         # Arrange
#         integration_type = IntegrationType.SOURCE
#         connections = [MagicMock(spec=schemas.Connection) for _ in range(2)]
#         crud.connection.get_by_integration_type = AsyncMock(return_value=connections)

#         # Act
#         result = await connection_service.get_connections_by_type(
#             mock_db, integration_type, mock_user
#         )

#         # Assert
#         crud.connection.get_by_integration_type.assert_called_once_with(
#             mock_db, integration_type=integration_type, organization_id=mock_user.organization_id
#         )
#         assert result == connections

#     # Tests for connect_with_config
#     @patch("airweave.core.connection_service.UnitOfWork")
#     @patch("airweave.core.connection_service.resource_locator")
#     async def test_connect_with_config_auth_none(
#         self, mock_locator, MockUnitOfWork, mock_db, mock_user
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         integration_type = IntegrationType.SOURCE
#         short_name = "test_source"
#         name = "Test Connection"
#         auth_fields = {}

#         mock_integration = MagicMock()
#         mock_integration.auth_type = AuthType.none
#         mock_integration.name = "Test Integration"

#         mock_connection = MagicMock(spec=schemas.Connection)

#         connection_service._get_integration_by_type = AsyncMock(return_value=mock_integration)
#         connection_service._create_connection_without_credential = AsyncMock(
#             return_value=mock_connection
#         )

#         # Act
#         result = await connection_service.connect_with_config(
#             mock_db, integration_type, short_name, name, auth_fields, mock_user
#         )

#         # Assert
#         connection_service._get_integration_by_type.assert_called_once_with(
#             mock_uow.session, integration_type, short_name
#         )
#         connection_service._create_connection_without_credential.assert_called_once_with(
#             uow=mock_uow,
#             integration_type=integration_type,
#             short_name=short_name,
#             name=name,
#             integration_name=mock_integration.name,
#             user=mock_user,
#         )
#         mock_uow.commit.assert_called_once()
#         mock_uow.session.refresh.assert_called_once_with(mock_connection)
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.UnitOfWork")
#     @patch("airweave.core.connection_service.resource_locator")
#     @patch("airweave.core.connection_service.credentials")
#     async def test_connect_with_config_config_class(
#         self, mock_credentials, mock_locator, MockUnitOfWork, mock_db, mock_user
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         integration_type = IntegrationType.SOURCE
#         short_name = "test_source"
#         name = "Test Connection"
#         auth_fields = {"api_key": "test_key"}

#         mock_integration = MagicMock()
#         mock_integration.auth_type = AuthType.config_class
#         mock_integration.auth_config_class = "TestAuthConfig"
#         mock_integration.name = "Test Integration"

#         mock_auth_config = MagicMock()
#         mock_auth_config.model_dump.return_value = {"api_key": "test_key"}

#         mock_auth_config_class = MagicMock(return_value=mock_auth_config)
#         mock_locator.get_auth_config.return_value = mock_auth_config_class

#         encrypted_creds = "encrypted_data"
#         mock_credentials.encrypt.return_value = encrypted_creds

#         mock_connection = MagicMock(spec=schemas.Connection)

#         connection_service._get_integration_by_type = AsyncMock(return_value=mock_integration)
#         connection_service._create_connection_with_credential = AsyncMock(
#             return_value=mock_connection
#         )

#         # Act
#         result = await connection_service.connect_with_config(
#             mock_db, integration_type, short_name, name, auth_fields, mock_user
#         )

#         # Assert
#         connection_service._get_integration_by_type.assert_called_once_with(
#             mock_uow.session, integration_type, short_name
#         )
#         mock_locator.get_auth_config.assert_called_once_with("TestAuthConfig")
#         mock_auth_config_class.assert_called_once_with(**auth_fields)
#         mock_credentials.encrypt.assert_called_once_with(mock_auth_config.model_dump())

#         connection_service._create_connection_with_credential.assert_called_once_with(
#             uow=mock_uow,
#             integration_type=integration_type,
#             short_name=short_name,
#             name=name,
#             integration_name=mock_integration.name,
#             auth_type=mock_integration.auth_type,
#             encrypted_credentials=encrypted_creds,
#             auth_config_class=mock_integration.auth_config_class,
#             user=mock_user,
#         )
#         mock_uow.commit.assert_called_once()
#         mock_uow.session.refresh.assert_called_once_with(mock_connection)
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.UnitOfWork")
#     async def test_connect_with_config_integration_not_found(
#         self, MockUnitOfWork, mock_db, mock_user
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         integration_type = IntegrationType.SOURCE
#         short_name = "non_existent"
#         name = "Test Connection"
#         auth_fields = {}

#         connection_service._get_integration_by_type = AsyncMock(return_value=None)

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service.connect_with_config(
#                 mock_db, integration_type, short_name, name, auth_fields, mock_user
#             )

#         assert excinfo.value.status_code == 400
#         assert f"{integration_type} with short_name '{short_name}' does not exist" in str(
#             excinfo.value.detail
#         )

#     # Tests for get_oauth2_auth_url
#     @patch("airweave.core.connection_service.integration_settings")
#     @patch("airweave.core.connection_service.oauth2_service")
#     async def test_get_oauth2_auth_url(self, mock_oauth2_service, mock_integration_settings):
#         # Arrange
#         short_name = "test_source"
#         mock_settings = MagicMock()
#         mock_settings.auth_type = AuthType.oauth2
#         mock_await integration_settings.get_by_short_name.return_value = mock_settings

#         expected_url = "https://example.com/oauth2/authorize"
#         mock_oauth2_service.generate_auth_url.return_value = expected_url

#         # Act
#         result = await connection_service.get_oauth2_auth_url(short_name)

#         # Assert
#         mock_await integration_settings.get_by_short_name.assert_called_once_with(short_name)
#         mock_oauth2_service.generate_auth_url.assert_called_once_with(mock_settings, None)
#         assert result == expected_url

#     @patch("airweave.core.connection_service.integration_settings")
#     async def test_get_oauth2_auth_url_integration_not_found(self, mock_integration_settings):
#         # Arrange
#         short_name = "non_existent"
#         mock_await integration_settings.get_by_short_name.return_value = None

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service.get_oauth2_auth_url(short_name)

#         assert excinfo.value.status_code == 404
#         assert "Integration not found" in str(excinfo.value.detail)

#     # Tests for connect_with_oauth2_code
#     @patch("airweave.core.connection_service.oauth2_service")
#     @patch("airweave.core.connection_service.integration_settings")
#     async def test_connect_with_oauth2_code(
#         self, mock_integration_settings, mock_oauth2_service, mock_db, mock_user
#     ):
#         # Arrange
#         short_name = "test_source"
#         code = "test_code"

#         oauth2_response = OAuth2TokenResponse(
#             access_token="test_access_token", token_type="bearer", expires_in=3600
#         )
#         mock_oauth2_service.exchange_autorization_code_for_token = AsyncMock(
#             return_value=oauth2_response
#         )

#         mock_source = MagicMock(spec=schemas.Source)
#         mock_source.short_name = short_name
#         crud.source.get_by_short_name = AsyncMock(return_value=mock_source)

#         mock_settings = MagicMock()
#         mock_await integration_settings.get_by_short_name.return_value = mock_settings

#         mock_connection = MagicMock(spec=schemas.Connection)
#         connection_service._create_oauth2_connection = AsyncMock(return_value=mock_connection)

#         # Act
#         result = await connection_service.connect_with_oauth2_code(
#             mock_db, short_name, code, mock_user
#         )

#         # Assert
#         mock_oauth2_service.exchange_autorization_code_for_token.assert_called_once_with(
#             short_name, code, None
#         )
#         crud.source.get_by_short_name.assert_called_once_with(mock_db, short_name)
#         mock_await integration_settings.get_by_short_name.assert_called_once_with(short_name)
#         connection_service._create_oauth2_connection.assert_called_once_with(
#             db=mock_db,
#             source=mock_source,
#             settings=mock_settings,
#             oauth2_response=oauth2_response,
#             user=mock_user,
#             connection_name=None,
#             auth_fields=None
#         )
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.oauth2_service")
#     async def test_connect_with_oauth2_code_exchange_fails(
#         self, mock_oauth2_service, mock_db, mock_user
#     ):
#         # Arrange
#         short_name = "test_source"
#         code = "invalid_code"

#         mock_oauth2_service.exchange_autorization_code_for_token.side_effect = Exception(
#             "Token exchange failed"
#         )

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service.connect_with_oauth2_code(mock_db, short_name, code, mock_user)

#         assert excinfo.value.status_code == 400
#         assert "Failed to exchange OAuth2 code" in str(excinfo.value.detail)


#     # Tests for connect_with_direct_token
#     @patch("airweave.core.connection_service.settings")
#     @patch("airweave.core.connection_service.UnitOfWork")
#     @patch("airweave.core.connection_service.credentials")
#     async def test_connect_with_direct_token(
#         self, mock_credentials, MockUnitOfWork, mock_settings, mock_db, mock_user
#     ):
#         # Arrange
#         mock_settings.LOCAL_DEVELOPMENT = True
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         short_name = "test_source"
#         token = "test_token"
#         name = "Test Connection"
#         validate_token = False

#         mock_source = MagicMock(spec=schemas.Source)
#         mock_source.name = "Test Source"
#         crud.source.get_by_short_name = AsyncMock(return_value=mock_source)

#         encrypted_creds = "encrypted_data"
#         mock_credentials.encrypt.return_value = encrypted_creds

#         mock_connection = MagicMock(spec=schemas.Connection)
#         connection_service._create_connection_with_credential = AsyncMock(
#             return_value=mock_connection
#         )

#         # Act
#         result = await connection_service.connect_with_direct_token(
#             mock_db, short_name, token, name, mock_user, validate_token
#         )

#         # Assert
#         crud.source.get_by_short_name.assert_called_once_with(mock_uow.session, short_name)
#         mock_credentials.encrypt.assert_called_once_with({"access_token": token})
#         connection_service._create_connection_with_credential.assert_called_once_with(
#             uow=mock_uow,
#             integration_type=IntegrationType.SOURCE,
#             short_name=short_name,
#             name=name,
#             integration_name=mock_source.name,
#             auth_type=AuthType.oauth2,
#             encrypted_credentials=encrypted_creds,
#             auth_config_class=None,
#             user=mock_user,
#         )
#         mock_uow.commit.assert_called_once()
#         mock_uow.session.refresh.assert_called_once_with(mock_connection)
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.settings")
#     async def test_connect_with_direct_token_not_local_dev(self, mock_settings, mock_db, mock_user):
#         # Arrange
#         mock_settings.LOCAL_DEVELOPMENT = False

#         short_name = "test_source"
#         token = "test_token"
#         name = "Test Connection"

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service.connect_with_direct_token(
#                 mock_db, short_name, token, name, mock_user
#             )

#         assert excinfo.value.status_code == 403
#         assert "Direct token connection is only allowed in local development mode" in str(
#             excinfo.value.detail
#         )

#     # Tests for delete_connection
#     @patch("airweave.core.connection_service.UnitOfWork")
#     async def test_delete_connection(self, MockUnitOfWork, mock_db, mock_user, connection_id):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         mock_connection = MagicMock(spec=schemas.Connection)
#         mock_connection.integration_credential_id = uuid.uuid4()
#         crud.connection.get = AsyncMock(return_value=mock_connection)
#         crud.connection.remove = AsyncMock(return_value=mock_connection)
#         crud.integration_credential.remove = AsyncMock()
#         crud.sync.remove_all_for_connection = AsyncMock()

#         # Act
#         result = await connection_service.delete_connection(mock_db, connection_id, mock_user)

#         # Assert
#         crud.connection.get.assert_called_once_with(
#             mock_uow.session, id=connection_id, current_user=mock_user
#         )
#         crud.sync.remove_all_for_connection.assert_called_once_with(
#             mock_uow.session, connection_id, current_user=mock_user, uow=mock_uow
#         )
#         crud.connection.remove.assert_called_once_with(
#             mock_uow.session, id=connection_id, current_user=mock_user, uow=mock_uow
#         )
#         crud.integration_credential.remove.assert_called_once_with(
#             mock_uow.session,
#             id=mock_connection.integration_credential_id,
#             current_user=mock_user,
#             uow=mock_uow,
#         )
#         mock_uow.commit.assert_called_once()
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.UnitOfWork")
#     async def test_delete_connection_not_found(
#         self, MockUnitOfWork, mock_db, mock_user, connection_id
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         crud.connection.get = AsyncMock(return_value=None)

#         # Act & Assert
#         with pytest.raises(NotFoundException) as excinfo:
#             await connection_service.delete_connection(mock_db, connection_id, mock_user)

#         assert f"No active connection found for '{connection_id}'" in str(excinfo.value)

#     # Tests for disconnect_source
#     @patch("airweave.core.connection_service.UnitOfWork")
#     @patch("airweave.schemas.ConnectionUpdate.model_validate")
#     @patch("airweave.schemas.SyncUpdate.model_validate")
#     @patch("airweave.schemas.Connection.model_validate")
#     async def test_disconnect_source(
#         self,
#         mock_conn_model_validate,
#         mock_sync_update_validate,
#         mock_conn_update_validate,
#         MockUnitOfWork,
#         mock_db,
#         mock_user,
#         connection_id,
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         # Create a mock connection that will be returned by the get method
#         mock_connection = MagicMock()
#         mock_connection.integration_type = IntegrationType.SOURCE
#         mock_connection.status = ConnectionStatus.ACTIVE
#         crud.connection.get = AsyncMock(return_value=mock_connection)

#         # Setup connection update mocking
#         mock_connection_update = MagicMock()
#         mock_conn_update_validate.return_value = mock_connection_update
#         crud.connection.update = AsyncMock()

#         # Mock the Connection.model_validate call that happens at the end
#         mock_conn_model_validate.return_value = mock_connection

#         # Setup sync mocks
#         mock_sync1 = MagicMock()
#         mock_sync1.status = SyncStatus.ACTIVE
#         mock_sync2 = MagicMock()
#         mock_sync2.status = SyncStatus.ACTIVE
#         crud.sync.get_all_for_source_connection = AsyncMock(return_value=[mock_sync1, mock_sync2])

#         # Setup sync update mocking
#         mock_sync_update = MagicMock()
#         mock_sync_update_validate.return_value = mock_sync_update
#         crud.sync.update = AsyncMock()

#         # Act
#         result = await connection_service.disconnect_source(mock_db, connection_id, mock_user)

#         # Assert
#         crud.connection.get.assert_called_once_with(
#             mock_uow.session, id=connection_id, current_user=mock_user
#         )
#         assert mock_connection.status == ConnectionStatus.INACTIVE
#         assert mock_sync1.status == SyncStatus.INACTIVE
#         assert mock_sync2.status == SyncStatus.INACTIVE
#         assert crud.sync.update.call_count == 2
#         mock_uow.commit.assert_called_once()
#         assert result == mock_connection

#     @patch("airweave.core.connection_service.UnitOfWork")
#     async def test_disconnect_source_not_source(
#         self, MockUnitOfWork, mock_db, mock_user, connection_id
#     ):
#         # Arrange
#         mock_uow = AsyncMock()
#         mock_uow.session = mock_db
#         MockUnitOfWork.return_value.__aenter__.return_value = mock_uow

#         mock_connection = MagicMock()
#         mock_connection.integration_type = IntegrationType.DESTINATION  # Not a source
#         crud.connection.get = AsyncMock(return_value=mock_connection)

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service.disconnect_source(mock_db, connection_id, mock_user)

#         assert excinfo.value.status_code == 400
#         assert "Connection is not a source" in str(excinfo.value.detail)

#     # Tests for get_connection_credentials
#     @patch("airweave.core.connection_service.credentials")
#     async def test_get_connection_credentials(
#         self, mock_credentials, mock_db, mock_user, connection_id
#     ):
#         # Arrange
#         credential_id = uuid.uuid4()
#         mock_connection = MagicMock(spec=schemas.Connection)
#         mock_connection.integration_credential_id = credential_id
#         crud.connection.get = AsyncMock(return_value=mock_connection)

#         mock_credential = MagicMock()
#         mock_credential.encrypted_credentials = "encrypted_data"
#         crud.integration_credential.get = AsyncMock(return_value=mock_credential)

#         decrypted_data = {"access_token": "test_token"}
#         mock_credentials.decrypt.return_value = decrypted_data

#         # Act
#         result = await connection_service.get_connection_credentials(
#             mock_db, connection_id, mock_user
#         )

#         # Assert
#         crud.connection.get.assert_called_once_with(
#             mock_db, id=connection_id, current_user=mock_user
#         )
#         crud.integration_credential.get.assert_called_once_with(
#             mock_db, id=credential_id, current_user=mock_user
#         )
#         mock_credentials.decrypt.assert_called_once_with(mock_credential.encrypted_credentials)
#         assert result == decrypted_data

#     async def test_get_connection_credentials_connection_not_found(
#         self, mock_db, mock_user, connection_id
#     ):
#         # Arrange
#         crud.connection.get = AsyncMock(return_value=None)

#         # Act & Assert
#         with pytest.raises(NotFoundException, match="Connection not found"):
#             await connection_service.get_connection_credentials(mock_db, connection_id, mock_user)

#     async def test_get_connection_credentials_no_credential_id(
#         self, mock_db, mock_user, connection_id
#     ):
#         # Arrange
#         mock_connection = MagicMock(spec=schemas.Connection)
#         mock_connection.integration_credential_id = None
#         crud.connection.get = AsyncMock(return_value=mock_connection)

#         # Act & Assert
#         with pytest.raises(NotFoundException, match="Connection has no integration credential"):
#             await connection_service.get_connection_credentials(mock_db, connection_id, mock_user)

#     # Tests for private helper methods
#     async def test_get_integration_by_type_source(self, mock_db):
#         # Arrange
#         integration_type = IntegrationType.SOURCE
#         short_name = "test_source"
#         mock_source = MagicMock(spec=schemas.Source)

#         # Directly monkey patch the method
#         original_func = connection_service._get_integration_by_type

#         # Define a replacement function
#         async def mock_get_integration_by_type(db, i_type, s_name):
#             assert db == mock_db
#             assert i_type == integration_type
#             assert s_name == short_name
#             return mock_source

#         connection_service._get_integration_by_type = mock_get_integration_by_type

#         try:
#             # Act
#             result = await connection_service._get_integration_by_type(
#                 mock_db, integration_type, short_name
#             )

#             # Assert
#             assert result == mock_source
#         finally:
#             # Restore original method
#             connection_service._get_integration_by_type = original_func

#     @patch("airweave.crud.destination.get_by_short_name")
#     async def test_get_integration_by_type_destination(self, mock_get_by_short_name, mock_db):
#         # Arrange
#         integration_type = IntegrationType.DESTINATION
#         short_name = "test_destination"
#         mock_destination = MagicMock(spec=schemas.Destination)

#         # Directly monkey patch the method
#         original_func = connection_service._get_integration_by_type

#         # Define a replacement function
#         async def mock_get_integration_by_type(db, i_type, s_name):
#             assert db == mock_db
#             assert i_type == integration_type
#             assert s_name == short_name
#             return mock_destination

#         connection_service._get_integration_by_type = mock_get_integration_by_type

#         try:
#             # Act
#             result = await connection_service._get_integration_by_type(
#                 mock_db, integration_type, short_name
#             )

#             # Assert
#             assert result == mock_destination
#         finally:
#             # Restore original method
#             connection_service._get_integration_by_type = original_func

#     @patch("airweave.crud.embedding_model.get_by_short_name")
#     async def test_get_integration_by_type_embedding_model(self, mock_db):
#         # Arrange
#         integration_type = IntegrationType.EMBEDDING_MODEL
#         short_name = "test_model"
#         mock_model = MagicMock(spec=schemas.EmbeddingModel)

#         # Directly monkey patch the method
#         original_func = connection_service._get_integration_by_type

#         # Define a replacement function
#         async def mock_get_integration_by_type(db, i_type, s_name):
#             assert db == mock_db
#             assert i_type == integration_type
#             assert s_name == short_name
#             return mock_model

#         connection_service._get_integration_by_type = mock_get_integration_by_type

#         try:
#             # Act
#             result = await connection_service._get_integration_by_type(
#                 mock_db, integration_type, short_name
#             )

#             # Assert
#             assert result == mock_model
#         finally:
#             # Restore original method
#             connection_service._get_integration_by_type = original_func

#     async def test_create_connection_without_credential(self, mock_uow, mock_user):
#         # Arrange
#         integration_type = IntegrationType.SOURCE
#         short_name = "test_source"
#         name = None  # Test default name generation
#         integration_name = "Test Integration"
#         expected_name = f"Connection to {integration_name}"
#         mock_connection = MagicMock(spec=schemas.Connection)

#         # Directly monkey patch the method
#         original_func = connection_service._create_connection_without_credential

#         # Define a replacement function
#         async def mock_create_connection_without_credential(uow, i_type, s_name, n, i_name, user):
#             assert uow == mock_uow
#             assert i_type == integration_type
#             assert s_name == short_name
#             assert n == name
#             assert i_name == integration_name
#             assert user == mock_user
#             return mock_connection

#         connection_service._create_connection_without_credential = (
#             mock_create_connection_without_credential
#         )

#         try:
#             # Act
#             result = await connection_service._create_connection_without_credential(
#                 mock_uow, integration_type, short_name, name, integration_name, mock_user
#             )

#             # Assert
#             assert result == mock_connection
#         finally:
#             # Restore original method
#             connection_service._create_connection_without_credential = original_func

#     @patch("airweave.core.connection_service.httpx")
#     @patch("airweave.core.connection_service.settings")
#     async def test_validate_slack_token_success(self, mock_settings, mock_httpx):
#         # Arrange
#         token = "xoxb-test-token"
#         name = None  # Test default name generation

#         mock_client = AsyncMock()
#         mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

#         mock_response = MagicMock()
#         mock_response.raise_for_status = MagicMock()
#         mock_response.json.return_value = {"ok": True, "team": "Awesome Team"}
#         mock_client.get.return_value = mock_response

#         # Act
#         result = await connection_service._validate_slack_token(token, name)

#         # Assert
#         mock_client.get.assert_called_once_with(
#             "https://slack.com/api/auth.test",
#             headers={
#                 "Authorization": f"Bearer {token}",
#                 "Content-Type": "application/json",
#             },
#         )
#         assert result == "Awesome Team Direct Token"

#     @patch("airweave.core.connection_service.httpx")
#     async def test_validate_slack_token_api_error(self, mock_httpx):
#         # Arrange
#         token = "invalid-token"
#         name = None

#         mock_client = AsyncMock()
#         mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

#         mock_response = MagicMock()
#         mock_response.raise_for_status = MagicMock()
#         mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
#         mock_client.get.return_value = mock_response

#         # Act & Assert
#         with pytest.raises(HTTPException) as excinfo:
#             await connection_service._validate_slack_token(token, name)

#         assert excinfo.value.status_code == 400
#         assert "Invalid Slack token: invalid_auth" in str(excinfo.value.detail)

#     # Test OAuth2 support check
#     @pytest.mark.skip(reason="This is not an async test")
#     def test_supports_oauth2(self):
#         # Test supported auth types
#         assert connection_service._supports_oauth2(AuthType.oauth2) is True
#         assert connection_service._supports_oauth2(AuthType.oauth2_with_refresh) is True
#         assert connection_service._supports_oauth2(AuthType.oauth2_with_refresh_rotating) is True

#         # Test unsupported auth types
#         assert connection_service._supports_oauth2(AuthType.none) is False
#         assert connection_service._supports_oauth2(AuthType.config_class) is False
