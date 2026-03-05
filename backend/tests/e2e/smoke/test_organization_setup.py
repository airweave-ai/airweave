"""E2E smoke tests for organization setup flow."""

import asyncio
import time
import uuid

import httpx
import pytest


class TestOrganizationSetupSmoke:
    @pytest.mark.asyncio
    @pytest.mark.critical
    @pytest.mark.local_only
    async def test_complete_setup_creates_organization_and_is_listed(
        self,
        api_client: httpx.AsyncClient,
    ):
        org_name = f"Smoke Org {int(time.time())}-{uuid.uuid4().hex[:6]}"
        created_org_id = None

        try:
            create_resp = await api_client.post(
                "/organizations",
                json={
                    "name": org_name,
                    "description": "e2e smoke organization setup",
                },
            )
            assert create_resp.status_code == 200, (
                f"Organization creation failed: {create_resp.status_code} {create_resp.text}"
            )
            created = create_resp.json()
            created_org_id = created["id"]
            assert created["name"] == org_name

            # Verify immediate visibility after setup (cache invalidation path)
            deadline = time.time() + 10
            seen = False
            while time.time() < deadline:
                list_resp = await api_client.get("/users/me/organizations")
                assert list_resp.status_code == 200, (
                    f"Failed listing user orgs: {list_resp.status_code} {list_resp.text}"
                )
                orgs = list_resp.json()
                if any(org["id"] == created_org_id for org in orgs):
                    seen = True
                    break
                await asyncio.sleep(0.5)

            assert seen, "Created organization not visible via /users/me/organizations"
        finally:
            if created_org_id:
                # Best-effort cleanup; don't fail test if cleanup fails.
                try:
                    await api_client.delete(f"/organizations/{created_org_id}")
                except Exception:
                    pass
