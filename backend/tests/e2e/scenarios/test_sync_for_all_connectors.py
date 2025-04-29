"""
GIVEN A CONNECTION TEST RUNNING A SYNC FOR ALL CONNECTORS

How this test works (step-by-step):
- For each source listed in the @pytest.mark.parametrize("service_name", [...]) decorator:
    - Retrieve the credentials for the source from environment variables (set via GitHub secrets or your local .env file).
    - Open a database session to the test Postgres instance (spun up by the test fixture).
    - Look up the source definition in the database using its short_name.
    - Based on the authentication type of the source create a credentials dictionary to be encrypted
    - Create an IntegrationCredential row in the database for the source.
    - Create a Connection row in the database, linked to the new IntegrationCredential.
    - Send a POST request to the /sync/ API endpoint to create a new sync configuration using the connection.
    - Send a POST request to the /sync/{sync_id}/run API endpoint to start a sync job for the configuration.
    - Wait for the sync job to complete by polling the job status (using wait_for_sync_completion).
    - Assert that the sync job status is "completed" (fail if not).

How to add a new OAuth source to this test:
- Add the new source's short_name to the @pytest.mark.parametrize("service_name", [...]) decorator.
- Obtain valid credentials for the new source (run the debugger or follow the source's auth flow).
- Add the corresponding environment variable for the credentials to the creds fixture.
- Add the credentials to GitHub secrets for CI, and/or to your local .env file for local runs.
    - Ensure the credentials of a config class auth type are in a string over a dict of the auth.py config class
- Ensure the backend supports the new source and its short_name matches the one used in the test.
- Pass the secrets to the environment variable in tests.yml.
"""

import os
import uuid
import pytest
import requests
import asyncio
import ast

from airweave import crud, schemas

from airweave.models.integration_credential import IntegrationType

from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.shared_models import ConnectionStatus
from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID

from airweave.db.unit_of_work import UnitOfWork

from airweave.platform.auth.schemas import AuthType
from airweave.platform.locator import resource_locator


from tests.e2e.smoke.test_user_onboarding import wait_for_sync_completion

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
def creds():
    """
    Fixture providing credentials for all test connectors.
    """
    return {
        "dropbox": os.getenv("DROPBOX_REFRESH_TOKEN"),
        "google_drive": os.getenv("GDRIVE_REFRESH_TOKEN"),
        "asana": os.getenv("ASANA_REFRESH_TOKEN"),
        "notion": os.getenv("NOTION_ACCESS_TOKEN"),
        "github": os.getenv("GITHUB_CONFIG_CREDS")
    }


@pytest.mark.parametrize("service_name", ["asana", "dropbox", "github", "google_drive", "notion"])
def test_oauth_sync(e2e_environment, e2e_api_url, creds, service_name):
    """
    End-to-end test for integration connectors with various auth types.
    """
    cred = creds.get(service_name)
    if not cred:
        pytest.fail(f"No token available for {service_name}")

    # 1. Create connection
    connection = asyncio.run(create_connection(e2e_api_url, service_name, cred))
    print(f"\nCreated connection: {connection.id} for {service_name}\n")

    # 2. Create a sync
    sync_data = {
        "name": f"Test {service_name.capitalize()} Sync {uuid.uuid4()}",
        "description": f"Test sync for {service_name} using OAuth refresh token",
        "source_connection_id": str(connection.id),
        "destination_connection_ids": [str(NATIVE_QDRANT_UUID)],
        "embedding_model_connection_id": str(NATIVE_TEXT2VEC_UUID),
        "run_immediately": False,
        "schedule": None,
    }

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

    print(f"✅ Successfully completed sync test for connector: {service_name}")


async def create_connection(e2e_api_url, service_name, cred):
    """
    Creates a connection for the given service using appropriate credentials.
    """
    db, user, original_uri = await connect_test_db(e2e_api_url, service_name)
    try:
        source = await crud.source.get_by_short_name(db, service_name)
        if not source:
            raise ValueError(f"Source {service_name} not found")


        settings.ENCRYPTION_KEY = "SpgLrrEEgJ/7QdhSMSvagL1juEY5eoyCG0tZN7OSQV0="

        if source.auth_type == AuthType.oauth2:
            cred_dict = {"access_token": cred}
        elif source.auth_type in [AuthType.oauth2_with_refresh, AuthType.oauth2_with_refresh_rotating]:
            cred_dict = {"refresh_token": cred}
        elif source.auth_type == AuthType.config_class:
            # Parse the string representation of dictionary to a Python dict
            cred_dict = ast.literal_eval(cred)
        else:
            raise ValueError(f"Unsupported auth_type '{source.auth_type}'.")

        encrypted_credentials = credentials.encrypt(cred_dict)

        async with UnitOfWork(db) as uow:
            credential_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"Test {source.name} - {user.email}",
                description=f"Test credentials for {source.name}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=source.auth_type,
                encrypted_credentials=encrypted_credentials,
                auth_config_class=source.auth_config_class
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

    finally:
        await db.close()
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = original_uri


async def connect_test_db(e2e_api_url, service_name):
    """
    Sets up a test database connection for integration tests.
    """
    # Save original URI
    original_uri = settings.SQLALCHEMY_ASYNC_DATABASE_URI

    # Override with URI for test Docker container
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

    # Change this line - don't await the constructor
    db = AsyncSessionLocal()

    try:
        # Get user by email
        user_db = await crud.user.get_by_email(db, email=settings.FIRST_SUPERUSER)
        if user_db is None:
            raise ValueError(f"User with email {settings.FIRST_SUPERUSER} not found")

        user = schemas.User.model_validate(user_db)

        # Return resources without closing the db session
        return db, user, original_uri
    except Exception:
        # Close db only on exception
        await db.close()
        settings.SQLALCHEMY_ASYNC_DATABASE_URI = original_uri
        raise
