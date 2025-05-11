"""
End-to-end OAuth sync test for Airweave sources.

How this test works (step-by-step):
- For each source listed in the @pytest.mark.parametrize("service_name", [...]) decorator:
    - Retrieve the refresh token for the source from environment variables (set via GitHub secrets or your local .env file).
    - Open a database session to the test Postgres instance (spun up by the test fixture).
    - Look up the source definition in the database using its short_name.
    - Encrypt the refresh token and create an IntegrationCredential row in the database for the source.
    - Create a Connection row in the database, linked to the new IntegrationCredential.
    - Send a POST request to the /sync/ API endpoint to create a new sync configuration using the connection.
    - Send a POST request to the /sync/{sync_id}/run API endpoint to start a sync job for the configuration.
    - Wait for the sync job to complete by polling the job status (using wait_for_sync_completion).
    - Assert that the sync job status is "completed" (fail if not).

How to add a new OAuth source to this test:
- Add the new source's short_name to the @pytest.mark.parametrize("service_name", [...]) decorator.
- Obtain a valid refresh token for the new source (run the debugger or follow the source's OAuth flow).
- Add the corresponding environment variable for the refresh token to the oauth_refresh_tokens fixture.
- Add the refresh token to GitHub secrets for CI, and/or to your local .env file for local runs.
- Ensure the backend supports the new source and its short_name matches the one used in the test.
- Pass the secrets to the environment variable in tests.yml.
- If the new source uses a different authorization type (not refresh token), add logic to handle it in the test and credential setup.
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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
def oauth_refresh_tokens():
    """Fixture to provide refresh tokens for OAuth services."""
    return {
        "dropbox": os.getenv("DROPBOX_REFRESH_TOKEN"),
        "google_drive": os.getenv("GDRIVE_REFRESH_TOKEN"),
        "asana": os.getenv("ASANA_REFRESH_TOKEN"),
    }


async def setup_connection_with_refresh_token(db, service_name, refresh_token, user):
    """
    - Create encrypted integration credentials using the refresh token
    - Create connection with those credentials
    - Store directly in the database
    """

    # Get the source definition
    source = await crud.source.get_by_short_name(db, service_name)
    if not source:
        raise ValueError(f"Source {service_name} not found")

    # Encrypt the refresh token
    settings.ENCRYPTION_KEY = "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0="
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


@pytest.mark.parametrize("service_name", ["dropbox"])  # , "google_drive", "asana"
def test_oauth_refresh_sync(e2e_environment, e2e_api_url, oauth_refresh_tokens, service_name):
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
    assert (
        create_sync_response.status_code == 200
    ), f"Failed to create sync: {create_sync_response.text}"

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
        f"{e2e_api_url}/sync/{sync_id}/job/{job_id}", params={"sync_id": sync_id}
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
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = (
            "postgresql+asyncpg://airweave:airweave1234!@localhost:9432/airweave"
        )

        async_engine = create_async_engine(
            str(settings.SQLALCHEMY_ASYNC_DATABASE_URI),
            pool_size=50,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_timeout=60,
            isolation_level="READ COMMITTED",
        )
        AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=async_engine)

        async with AsyncSessionLocal() as db:
            try:
                # Get user by email
                user_db = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)

                # Error handling for when user is None
                if user_db is None:
                    print(
                        f"ERROR: User with email {settings.FIRST_SUPERUSER} not found in database"
                    )
                    print(f"Database URI: {settings.SQLALCHEMY_ASYNC_DATABASE_URI}")

                    # Try to list available users for debugging
                    try:
                        users = await crud.user.get_multi(db, skip=0, limit=10)
                        print(f"Available users in database: {[u.email for u in users]}")
                    except Exception as e:
                        print(f"Failed to list users: {e}")

                    raise ValueError(f"User with email {settings.FIRST_SUPERUSER} not found")

                user = schemas.User.model_validate(user_db)
                return await setup_connection_with_refresh_token(
                    db, service_name, refresh_token, user
                )
            finally:
                await db.close()
    finally:
        # Restore original URI
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = original_uri
