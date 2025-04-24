"""
1. Create IntegrationCredentialCreateEncrypted with encrypted refresh token
2.

To reproduce locally:
1. set dropbox, stripe, openai keys
2. start test containers
3. you encryption key should be the same as in the test backend
"""

from airweave import crud, schemas
from airweave.core import credentials
from airweave.models.integration_credential import IntegrationType
from airweave.core.shared_models import ConnectionStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave import schemas
from airweave import crud
from airweave.core.config import settings

import os
import uuid
import pytest
import requests
import asyncio
import subprocess
import time
import atexit

from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from tests.e2e.smoke.test_user_onboarding import wait_for_sync_completion

async def setup_connection_with_refresh_token(db, service_name, refresh_token, user):
    """Create a connection directly with a refresh token."""

    # Get the source definition
    source = await crud.source.get_by_short_name(db, service_name)
    if not source:
        raise ValueError(f"Source {service_name} not found")

    # Encrypt the refresh token
    encrypted_credentials = credentials.encrypt({"refresh_token": refresh_token})

    async with UnitOfWork(db) as uow:
        # Create the integration credential
        credential_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"Test {source.name} - {user.email}",
            description=f"Test OAuth2 credentials for {source.name}",
            integration_short_name=source.short_name,
            integration_type=IntegrationType.SOURCE,
            auth_type=source.auth_type,
            encrypted_credentials=encrypted_credentials,
        )

        credential = await crud.integration_credential.create(
            uow.session, obj_in=credential_in, current_user=user, uow=uow
        )
        await uow.session.flush()

        # Create the connection with this credential
        connection_in = schemas.ConnectionCreate(
            name=f"Test Connection to {source.name}",
            integration_type=IntegrationType.SOURCE,
            status=ConnectionStatus.ACTIVE,
            integration_credential_id=credential.id,
            short_name=source.short_name,
        )

        connection = await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )
        await uow.commit()
        await uow.session.refresh(connection)

    return connection

@pytest.fixture
def oauth_refresh_tokens():
    """Fixture to provide refresh tokens for OAuth services."""
    return {
        "dropbox": os.getenv("DROPBOX_REFRESH_TOKEN"),
        "google_drive": os.getenv("GDRIVE_REFRESH_TOKEN"),
        "asana": os.getenv("ASANA_REFRESH_TOKEN"),
    }

@pytest.fixture(scope="session")
def docker_services():
    """Start and stop Docker services for testing."""
    # Path to docker-compose file
    compose_file = os.path.join(os.path.dirname(__file__), "../../docker/docker-compose.test.yml")

    # Print current directory and file path for debugging
    print(f"Current directory: {os.getcwd()}")
    print(f"Docker compose file path: {compose_file}")

    # Stop any running containers - fixed command format
    print("Stopping any existing Docker containers...")
    subprocess.run(["docker", "compose", "down", "-v"], check=False)

    # Check if ports are already in use
    test_ports = [9432, 9379, 9080, 9333, 9001]
    for port in test_ports:
        # macOS specific check
        result = subprocess.run(["lsof", "-i", f":{port}"], capture_output=True, text=True)
        if result.stdout:
            print(f"Warning: Port {port} already in use by:\n{result.stdout}")

    # Start test containers - fixed command format
    print("Starting Docker containers...")
    try:
        subprocess.run(["docker", "compose", "-f", compose_file, "up", "-d"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to start containers: {e}")
        # Show what's running
        subprocess.run(["docker", "ps"], check=False)
        raise

    # Register cleanup function
    def cleanup():
        print("Cleaning up test containers...")
        subprocess.run(["docker", "compose", "-f", compose_file, "down", "-v"], check=False)

    atexit.register(cleanup)

    # Wait for services to be healthy
    print("Waiting for services to become healthy...")
    time.sleep(20)

    # Show running containers
    subprocess.run(["docker", "ps"], check=False)

    yield

    # Cleanup after tests
    cleanup()
    atexit.unregister(cleanup)

@pytest.mark.parametrize("service_name", ["dropbox"]) # , "google_drive", "asana"
def test_oauth_refresh_sync(docker_services, e2e_api_url, oauth_refresh_tokens, service_name):
    """Test end-to-end flow with OAuth services using refresh tokens.

    This test:
    1. Creates a connection using a refresh token
    2. Creates a sync configuration
    3. Runs the sync job and verifies completion
    4. Tests the data is searchable/usable
    """
    # Skip test if token is not available
    refresh_token = oauth_refresh_tokens.get(service_name)
    if not refresh_token:
        pytest.fail(f"No refresh token available for {service_name}")

    # 1. Create connection using refresh token
    connection = asyncio.run(_create_connection(e2e_api_url, service_name, refresh_token))
    print(f"\nCreated connection: {connection.id} for {service_name}\n")

    # 2. Create a sync configuration
    sync_data = {
        "name": f"Test {service_name.capitalize()} Sync {uuid.uuid4()}",
        "description": f"Test sync for {service_name} using OAuth refresh token",
        "source_connection_id": str(connection.id),
        "destination_connection_ids": [str(NATIVE_QDRANT_UUID)],
        "embedding_model_connection_id": str(NATIVE_TEXT2VEC_UUID),
        "run_immediately": False,
        "schedule": None,
    }
    print(f"\nSync data: {sync_data}\n")

    create_sync_response = requests.post(f"{e2e_api_url}/sync/", json=sync_data)
    assert create_sync_response.status_code == 200, f"Failed to create sync: {create_sync_response.text}"

    sync_id = create_sync_response.json()["id"]
    print(f"Created sync: {sync_id}")

    # 3. Run the sync job
    run_sync_response = requests.post(f"{e2e_api_url}/sync/{sync_id}/run")
    assert run_sync_response.status_code == 200, f"Failed to run sync: {run_sync_response.text}"
    job_id = run_sync_response.json()["id"]
    print(f"Started sync job: {job_id}")

    # 4. Wait for sync to complete (using the existing helper function)
    wait_for_sync_completion(e2e_api_url, sync_id, job_id)

    # 5. Verify the job completed successfully
    job_status_response = requests.get(
        f"{e2e_api_url}/sync/{sync_id}/job/{job_id}",
        params={"sync_id": sync_id}
    )
    assert job_status_response.status_code == 200

    job_data = job_status_response.json()
    assert job_data["status"] == "completed", f"Job failed or timed out: {job_data['status']}"

    print(f"✅ Successfully completed OAuth refresh token sync test for {service_name}")


async def _create_connection(e2e_api_url, service_name, refresh_token):
    """Helper function to create a connection with a refresh token."""

    # Save original URI
    original_uri = settings.SQLALCHEMY_ASYNC_DATABASE_URI
    try:
        # Override with test URI for Docker container
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = "postgresql+asyncpg://airweave:airweave1234!@localhost:9432/airweave"

        # NOTE: Import location is important since it create the engine on import using the URI
        from airweave.db.session import get_db_context

        # Use regular get_db_context which will now use the modified URI
        async with get_db_context() as db:
            user_db = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
            user = schemas.User.model_validate(user_db)
            return await setup_connection_with_refresh_token(db, service_name, refresh_token, user)
    finally:
        # Restore original URI
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = original_uri
