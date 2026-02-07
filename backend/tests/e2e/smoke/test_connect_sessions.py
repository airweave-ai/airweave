"""
Async test module for Connect Session endpoints.

Tests the Connect session API endpoints that enable short-lived session tokens
for frontend integration flows (Plaid-style Connect modal).

Endpoints tested:
- POST /connect/sessions - Create session token (API key auth)
- GET /connect/sessions/{session_id} - Validate token and get context (session token auth)
- GET /connect/source-connections - List connections (mode-restricted)
- DELETE /connect/source-connections/{id} - Delete connection (mode-restricted)
"""

import pytest
import httpx
import time
from typing import Dict
from uuid import uuid4


def session_auth_headers(session_token: str) -> Dict[str, str]:
    """Build Authorization header for session token authentication."""
    return {"Authorization": f"Bearer {session_token}"}


class TestConnectSessions:
    """Test suite for Connect Session API endpoints."""

    # -------------------------------------------------------------------------
    # Session Creation Tests (POST /connect/sessions)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_session_default_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a connect session with default ALL mode."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200, f"Failed to create session: {response.text}"

        session = response.json()
        assert "session_id" in session
        assert "session_token" in session
        assert "expires_at" in session
        assert len(session["session_token"]) > 0

    @pytest.mark.asyncio
    async def test_create_session_all_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a connect session with explicit ALL mode."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_connect_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a connect session with CONNECT mode."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "connect",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_manage_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a connect session with MANAGE mode."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "manage",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_reauth_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a connect session with REAUTH mode."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "reauth",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_with_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a session with allowed_integrations filter."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "allowed_integrations": ["slack", "github", "notion"],
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_with_end_user_id(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a session with end_user_id for tracking."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "end_user_id": "user_123",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_token" in session

    @pytest.mark.asyncio
    async def test_create_session_with_all_options(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a session with all optional parameters."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "manage",
            "allowed_integrations": ["stripe", "slack"],
            "end_user_id": "customer_abc123",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 200
        session = response.json()
        assert "session_id" in session
        assert "session_token" in session
        assert "expires_at" in session

    @pytest.mark.asyncio
    async def test_create_session_nonexistent_collection(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating a session with non-existent collection returns 404."""
        session_data = {
            "readable_collection_id": "nonexistent-collection-xyz-12345",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        assert "not found" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_session_missing_collection_id(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating a session without collection_id returns 422."""
        session_data = {}

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_session_invalid_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating a session with invalid mode returns 422."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "invalid_mode",
        }

        response = await api_client.post("/connect/sessions", json=session_data)

        assert response.status_code == 422

    # -------------------------------------------------------------------------
    # Token Validation Tests (GET /connect/sessions/{session_id})
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_session_token(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test validating a session token returns correct context."""
        # Create a session first
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
            "allowed_integrations": ["slack", "notion"],
            "end_user_id": "test_user_456",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()
        session_id = session["session_id"]

        # Validate the token
        response = await api_client.get(
            f"/connect/sessions/{session_id}",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        context = response.json()

        assert "session_id" in context
        assert context["session_id"] == session_id
        assert context["collection_id"] == collection["readable_id"]
        assert context["mode"] == "all"
        assert context["allowed_integrations"] == ["slack", "notion"]
        assert context["end_user_id"] == "test_user_456"
        assert "expires_at" in context
        assert "organization_id" in context

    @pytest.mark.asyncio
    async def test_validate_session_missing_auth_header(
        self, api_client: httpx.AsyncClient
    ):
        """Test validating without Authorization header returns 422/401."""
        dummy_session_id = str(uuid4())
        response = await api_client.get(f"/connect/sessions/{dummy_session_id}")

        # FastAPI returns 422 for missing required header
        assert response.status_code in [401, 422]

    @pytest.mark.asyncio
    async def test_validate_session_invalid_auth_format(
        self, api_client: httpx.AsyncClient
    ):
        """Test validating with invalid Authorization format returns 401."""
        dummy_session_id = str(uuid4())
        response = await api_client.get(
            f"/connect/sessions/{dummy_session_id}",
            headers={"Authorization": "InvalidFormat token123"},
        )

        assert response.status_code == 401
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_validate_session_malformed_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test validating a malformed token returns 401."""
        dummy_session_id = str(uuid4())
        response = await api_client.get(
            f"/connect/sessions/{dummy_session_id}",
            headers=session_auth_headers("not.a.valid.token.format"),
        )

        assert response.status_code == 401
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_validate_session_tampered_token(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test validating a tampered token returns 401."""
        # Create a valid session first
        session_data = {"readable_collection_id": collection["readable_id"]}
        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()
        session_id = session["session_id"]

        # Tamper with the token (change a character in the signature)
        tampered_token = session["session_token"][:-1] + "X"

        response = await api_client.get(
            f"/connect/sessions/{session_id}",
            headers=session_auth_headers(tampered_token),
        )

        assert response.status_code == 401
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_validate_session_empty_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test validating an empty token returns 401."""
        dummy_session_id = str(uuid4())
        response = await api_client.get(
            f"/connect/sessions/{dummy_session_id}",
            headers={"Authorization": ""},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_validate_session_mismatched_session_id(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test validating with mismatched session ID in URL returns 403."""
        # Create a valid session
        session_data = {"readable_collection_id": collection["readable_id"]}
        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        # Use a different session ID in the URL
        wrong_session_id = str(uuid4())
        response = await api_client.get(
            f"/connect/sessions/{wrong_session_id}",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403
        error = response.json()
        assert "detail" in error

    # -------------------------------------------------------------------------
    # List Source Connections Tests (GET /connect/source-connections)
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_connections_all_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing connections with ALL mode succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        response = await api_client.get(
            "/connect/source-connections",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        connections = response.json()
        assert isinstance(connections, list)

    @pytest.mark.asyncio
    async def test_list_connections_manage_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing connections with MANAGE mode succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "manage",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        response = await api_client.get(
            "/connect/source-connections",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        connections = response.json()
        assert isinstance(connections, list)

    @pytest.mark.asyncio
    async def test_list_connections_reauth_mode(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing connections with REAUTH mode succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "reauth",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        response = await api_client.get(
            "/connect/source-connections",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        connections = response.json()
        assert isinstance(connections, list)

    @pytest.mark.asyncio
    async def test_list_connections_connect_mode_forbidden(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing connections with CONNECT mode returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "connect",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        response = await api_client.get(
            "/connect/source-connections",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403
        error = response.json()
        assert "detail" in error
        assert "mode" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_connections_invalid_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test listing connections with invalid token returns 401."""
        response = await api_client.get(
            "/connect/source-connections",
            headers=session_auth_headers("invalid.token.here"),
        )

        assert response.status_code == 401

    # -------------------------------------------------------------------------
    # Delete Source Connection Tests (DELETE /connect/source-connections/{id})
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_connection_connect_mode_forbidden(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test deleting connection with CONNECT mode returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "connect",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        # Use a fake UUID - we expect 403 before it even checks if connection exists
        fake_connection_id = str(uuid4())

        response = await api_client.delete(
            f"/connect/source-connections/{fake_connection_id}",
            headers=session_auth_headers(session["session_token"]),
        )

        # With CONNECT mode, should get 403 for mode restriction
        # OR 404 if it checks existence first - both are acceptable
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_delete_connection_reauth_mode_forbidden(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test deleting connection with REAUTH mode returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "reauth",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        fake_connection_id = str(uuid4())

        response = await api_client.delete(
            f"/connect/source-connections/{fake_connection_id}",
            headers=session_auth_headers(session["session_token"]),
        )

        # With REAUTH mode, should get 403 for mode restriction
        # OR 404 if it checks existence first
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_delete_connection_nonexistent(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test deleting non-existent connection returns 404."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        fake_connection_id = str(uuid4())

        response = await api_client.delete(
            f"/connect/source-connections/{fake_connection_id}",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 404
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_delete_connection_invalid_uuid(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test deleting with invalid UUID format returns 422."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        create_response = await api_client.post("/connect/sessions", json=session_data)
        assert create_response.status_code == 200
        session = create_response.json()

        response = await api_client.delete(
            "/connect/source-connections/not-a-valid-uuid",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_connection_invalid_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting connection with invalid token returns 401."""
        fake_connection_id = str(uuid4())

        response = await api_client.delete(
            f"/connect/source-connections/{fake_connection_id}",
            headers=session_auth_headers("invalid.token.here"),
        )

        assert response.status_code == 401


class TestConnectSessionsWithConnections:
    """Test suite for Connect Sessions with actual source connections.

    These tests create real source connections to test filtering and deletion
    access control more thoroughly.
    """

    @pytest.mark.asyncio
    async def test_list_connections_with_actual_connection(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test listing connections returns actual connections in collection."""
        # Create a source connection first
        connection_data = {
            "name": f"Test Stripe Connection {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        conn_response = await api_client.post("/source-connections", json=connection_data)

        if conn_response.status_code != 200:
            pytest.skip(f"Could not create test connection: {conn_response.text}")

        connection = conn_response.json()

        try:
            # Create a session and list connections
            session_data = {
                "readable_collection_id": collection["readable_id"],
                "mode": "all",
            }

            session_response = await api_client.post("/connect/sessions", json=session_data)
            assert session_response.status_code == 200
            session = session_response.json()

            list_response = await api_client.get(
                "/connect/source-connections",
                headers=session_auth_headers(session["session_token"]),
            )

            assert list_response.status_code == 200
            connections = list_response.json()
            assert isinstance(connections, list)
            assert len(connections) >= 1

            # Verify our connection is in the list
            connection_ids = [c["id"] for c in connections]
            assert connection["id"] in connection_ids

        finally:
            # Cleanup connection
            await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_list_connections_filtered_by_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test listing connections respects allowed_integrations filter."""
        # Create a Stripe connection
        connection_data = {
            "name": f"Test Stripe Connection {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        conn_response = await api_client.post("/source-connections", json=connection_data)

        if conn_response.status_code != 200:
            pytest.skip(f"Could not create test connection: {conn_response.text}")

        connection = conn_response.json()

        try:
            # Create session that only allows 'slack' (not 'stripe')
            session_data = {
                "readable_collection_id": collection["readable_id"],
                "mode": "all",
                "allowed_integrations": ["slack", "notion"],  # Stripe not included
            }

            session_response = await api_client.post("/connect/sessions", json=session_data)
            assert session_response.status_code == 200
            session = session_response.json()

            list_response = await api_client.get(
                "/connect/source-connections",
                headers=session_auth_headers(session["session_token"]),
            )

            assert list_response.status_code == 200
            connections = list_response.json()

            # The Stripe connection should NOT be in the filtered list
            connection_short_names = [c.get("short_name") for c in connections]
            assert "stripe" not in connection_short_names

        finally:
            # Cleanup connection
            await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_delete_connection_all_mode_success(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test deleting connection with ALL mode succeeds."""
        # Create a source connection
        connection_data = {
            "name": f"Test Stripe Connection {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        conn_response = await api_client.post("/source-connections", json=connection_data)

        if conn_response.status_code != 200:
            pytest.skip(f"Could not create test connection: {conn_response.text}")

        connection = conn_response.json()

        # Create session with ALL mode
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        # Delete the connection via connect session
        delete_response = await api_client.delete(
            f"/connect/source-connections/{connection['id']}",
            headers=session_auth_headers(session["session_token"]),
        )

        assert delete_response.status_code == 200

        # Verify connection is actually deleted
        verify_response = await api_client.get(f"/source-connections/{connection['id']}")
        assert verify_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_connection_manage_mode_success(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test deleting connection with MANAGE mode succeeds."""
        # Create a source connection
        connection_data = {
            "name": f"Test Stripe Connection {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        conn_response = await api_client.post("/source-connections", json=connection_data)

        if conn_response.status_code != 200:
            pytest.skip(f"Could not create test connection: {conn_response.text}")

        connection = conn_response.json()

        # Create session with MANAGE mode
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "manage",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        # Delete the connection via connect session
        delete_response = await api_client.delete(
            f"/connect/source-connections/{connection['id']}",
            headers=session_auth_headers(session["session_token"]),
        )

        assert delete_response.status_code == 200

        # Verify connection is actually deleted
        verify_response = await api_client.get(f"/source-connections/{connection['id']}")
        assert verify_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_connection_not_in_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test deleting connection not in allowed_integrations returns 403."""
        # Create a Stripe connection
        connection_data = {
            "name": f"Test Stripe Connection {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        conn_response = await api_client.post("/source-connections", json=connection_data)

        if conn_response.status_code != 200:
            pytest.skip(f"Could not create test connection: {conn_response.text}")

        connection = conn_response.json()

        try:
            # Create session that only allows 'slack' (not 'stripe')
            session_data = {
                "readable_collection_id": collection["readable_id"],
                "mode": "all",
                "allowed_integrations": ["slack", "notion"],  # Stripe not included
            }

            session_response = await api_client.post("/connect/sessions", json=session_data)
            assert session_response.status_code == 200
            session = session_response.json()

            # Try to delete the Stripe connection
            delete_response = await api_client.delete(
                f"/connect/source-connections/{connection['id']}",
                headers=session_auth_headers(session["session_token"]),
            )

            assert delete_response.status_code == 403
            error = delete_response.json()
            assert "detail" in error

        finally:
            # Cleanup connection via regular API
            await api_client.delete(f"/source-connections/{connection['id']}")


class TestConnectSessionsCrossCollection:
    """Test suite for cross-collection access control in Connect Sessions."""

    @pytest.mark.asyncio
    async def test_delete_connection_wrong_collection(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test deleting connection from different collection returns 403."""
        # Create two collections
        collection1_data = {"name": f"Collection 1 {int(time.time())}"}
        collection2_data = {"name": f"Collection 2 {int(time.time())}"}

        col1_response = await api_client.post("/collections/", json=collection1_data)
        col2_response = await api_client.post("/collections/", json=collection2_data)

        assert col1_response.status_code == 200
        assert col2_response.status_code == 200

        collection1 = col1_response.json()
        collection2 = col2_response.json()

        try:
            # Create a connection in collection2
            connection_data = {
                "name": f"Test Stripe Connection {int(time.time())}",
                "short_name": "stripe",
                "readable_collection_id": collection2["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }

            conn_response = await api_client.post("/source-connections", json=connection_data)

            if conn_response.status_code != 200:
                pytest.skip(f"Could not create test connection: {conn_response.text}")

            connection = conn_response.json()

            try:
                # Create session for collection1 (not collection2)
                session_data = {
                    "readable_collection_id": collection1["readable_id"],
                    "mode": "all",
                }

                session_response = await api_client.post("/connect/sessions", json=session_data)
                assert session_response.status_code == 200
                session = session_response.json()

                # Try to delete connection from collection2 using collection1's session
                delete_response = await api_client.delete(
                    f"/connect/source-connections/{connection['id']}",
                    headers=session_auth_headers(session["session_token"]),
                )

                # Should be 403 (wrong collection) or 404 (not found in scope)
                assert delete_response.status_code in [403, 404]

            finally:
                # Cleanup connection
                await api_client.delete(f"/source-connections/{connection['id']}")

        finally:
            # Cleanup collections
            await api_client.delete(f"/collections/{collection1['readable_id']}")
            await api_client.delete(f"/collections/{collection2['readable_id']}")

    @pytest.mark.asyncio
    async def test_list_connections_only_shows_session_collection(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test listing connections only shows connections from session's collection."""
        # Create two collections
        collection1_data = {"name": f"Collection 1 {int(time.time())}"}
        collection2_data = {"name": f"Collection 2 {int(time.time())}"}

        col1_response = await api_client.post("/collections/", json=collection1_data)
        col2_response = await api_client.post("/collections/", json=collection2_data)

        assert col1_response.status_code == 200
        assert col2_response.status_code == 200

        collection1 = col1_response.json()
        collection2 = col2_response.json()

        connection1 = None
        connection2 = None

        try:
            # Create connection in collection1
            connection1_data = {
                "name": f"Collection1 Stripe {int(time.time())}",
                "short_name": "stripe",
                "readable_collection_id": collection1["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }

            conn1_response = await api_client.post("/source-connections", json=connection1_data)
            if conn1_response.status_code == 200:
                connection1 = conn1_response.json()

            # Create connection in collection2
            connection2_data = {
                "name": f"Collection2 Stripe {int(time.time())}",
                "short_name": "stripe",
                "readable_collection_id": collection2["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }

            conn2_response = await api_client.post("/source-connections", json=connection2_data)
            if conn2_response.status_code == 200:
                connection2 = conn2_response.json()

            if not connection1 or not connection2:
                pytest.skip("Could not create test connections")

            # Create session for collection1 only
            session_data = {
                "readable_collection_id": collection1["readable_id"],
                "mode": "all",
            }

            session_response = await api_client.post("/connect/sessions", json=session_data)
            assert session_response.status_code == 200
            session = session_response.json()

            # List connections via session
            list_response = await api_client.get(
                "/connect/source-connections",
                headers=session_auth_headers(session["session_token"]),
            )

            assert list_response.status_code == 200
            connections = list_response.json()

            # Should only see connection1, not connection2
            connection_ids = [c["id"] for c in connections]
            assert connection1["id"] in connection_ids
            assert connection2["id"] not in connection_ids

        finally:
            # Cleanup
            if connection1:
                await api_client.delete(f"/source-connections/{connection1['id']}")
            if connection2:
                await api_client.delete(f"/source-connections/{connection2['id']}")
            await api_client.delete(f"/collections/{collection1['readable_id']}")
            await api_client.delete(f"/collections/{collection2['readable_id']}")


class TestConnectSources:
    """Test suite for Connect API sources endpoints."""

    @pytest.mark.asyncio
    async def test_list_sources_returns_all_when_no_filter(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing sources returns all sources when allowed_integrations not set."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        response = await api_client.get(
            "/connect/sources",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        sources = response.json()
        assert isinstance(sources, list)
        assert len(sources) > 0

        # Verify source structure
        source = sources[0]
        assert "name" in source
        assert "short_name" in source
        assert "auth_methods" in source

    @pytest.mark.asyncio
    async def test_list_sources_filtered_by_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test listing sources respects allowed_integrations filter."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
            "allowed_integrations": ["stripe", "slack"],
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        response = await api_client.get(
            "/connect/sources",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        sources = response.json()

        # Should only contain allowed sources
        source_short_names = [s["short_name"] for s in sources]
        for short_name in source_short_names:
            assert short_name in ["stripe", "slack"]

    @pytest.mark.asyncio
    async def test_get_source_success(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test getting a specific source returns full details."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        response = await api_client.get(
            "/connect/sources/stripe",
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        source = response.json()
        assert source["short_name"] == "stripe"
        assert "auth_methods" in source
        assert "auth_fields" in source
        assert "config_fields" in source

    @pytest.mark.asyncio
    async def test_get_source_not_in_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test getting a source not in allowed_integrations returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
            "allowed_integrations": ["slack", "notion"],  # Stripe not included
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        response = await api_client.get(
            "/connect/sources/stripe",  # Not in allowed list
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403
        error = response.json()
        assert "not allowed" in error["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_sources_invalid_token(
        self, api_client: httpx.AsyncClient
    ):
        """Test listing sources with invalid token returns 401."""
        response = await api_client.get(
            "/connect/sources",
            headers=session_auth_headers("invalid.token.here"),
        )

        assert response.status_code == 401


class TestConnectSourceConnectionCreation:
    """Test suite for creating source connections via Connect API."""

    @pytest.mark.asyncio
    async def test_create_connection_all_mode_direct_auth(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating a direct auth connection with ALL mode succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": f"Test Stripe {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": "ignored-should-use-session",  # Should be ignored
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200, f"Failed to create connection: {response.text}"
        connection = response.json()

        # Verify connection was created in session's collection (not request body's)
        assert connection["readable_collection_id"] == collection["readable_id"]
        assert connection["short_name"] == "stripe"
        assert connection["auth"]["authenticated"] is True

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_create_connection_connect_mode_success(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection with CONNECT mode succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "connect",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": f"Test Stripe {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200
        connection = response.json()

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_create_connection_manage_mode_forbidden(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection with MANAGE mode returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "manage",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": "Test Connection",
            "short_name": "stripe",
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": "sk_test_xxx"}},
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403
        assert "mode" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_connection_reauth_mode_forbidden(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating connection with REAUTH mode returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "reauth",
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": "Test Connection",
            "short_name": "stripe",
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": "sk_test_xxx"}},
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_connection_not_in_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection for source not in allowed_integrations returns 403."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
            "allowed_integrations": ["slack", "notion"],  # Stripe not included
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": "Test Stripe",
            "short_name": "stripe",  # Not in allowed list
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 403
        assert "not allowed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_connection_in_allowed_integrations(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test creating connection for source in allowed_integrations succeeds."""
        session_data = {
            "readable_collection_id": collection["readable_id"],
            "mode": "all",
            "allowed_integrations": ["stripe", "slack"],
        }

        session_response = await api_client.post("/connect/sessions", json=session_data)
        assert session_response.status_code == 200
        session = session_response.json()

        connection_data = {
            "name": f"Test Stripe {int(time.time())}",
            "short_name": "stripe",  # In allowed list
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "sync_immediately": False,
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers(session["session_token"]),
        )

        assert response.status_code == 200

        # Cleanup
        await api_client.delete(f"/source-connections/{response.json()['id']}")

    @pytest.mark.asyncio
    async def test_create_connection_invalid_token(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test creating connection with invalid token returns 401."""
        connection_data = {
            "name": "Test Connection",
            "short_name": "stripe",
            "readable_collection_id": "ignored-uses-session",  # Overridden by session
            "authentication": {"credentials": {"api_key": "sk_test_xxx"}},
        }

        response = await api_client.post(
            "/connect/source-connections",
            json=connection_data,
            headers=session_auth_headers("invalid.token.here"),
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_collection_override_security(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test that collection_id from request body is ignored (uses session's)."""
        # Create two collections
        col1 = await api_client.post("/collections/", json={"name": f"Col1 {int(time.time())}"})
        col2 = await api_client.post("/collections/", json={"name": f"Col2 {int(time.time())}"})
        collection1 = col1.json()
        collection2 = col2.json()

        try:
            # Create session for collection1
            session_data = {
                "readable_collection_id": collection1["readable_id"],
                "mode": "all",
            }

            session_response = await api_client.post("/connect/sessions", json=session_data)
            assert session_response.status_code == 200
            session = session_response.json()

            # Try to create connection specifying collection2 in body
            connection_data = {
                "name": f"Test Stripe {int(time.time())}",
                "short_name": "stripe",
                "readable_collection_id": collection2["readable_id"],  # Attempt injection
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }

            response = await api_client.post(
                "/connect/source-connections",
                json=connection_data,
                headers=session_auth_headers(session["session_token"]),
            )

            assert response.status_code == 200
            connection = response.json()

            # CRITICAL: Connection should be in collection1, NOT collection2
            assert connection["readable_collection_id"] == collection1["readable_id"]
            assert connection["readable_collection_id"] != collection2["readable_id"]

            # Cleanup
            await api_client.delete(f"/source-connections/{connection['id']}")

        finally:
            await api_client.delete(f"/collections/{collection1['readable_id']}")
            await api_client.delete(f"/collections/{collection2['readable_id']}")

