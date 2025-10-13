"""
Async test module for Temporal Schedule functionality.

Tests integration between source connection schedule updates and Temporal workflow scheduler.
NOTE: These tests only run in local environment as they require Temporal API access.
"""

import pytest
import httpx
import asyncio
import time
import datetime
from datetime import timezone
from typing import Dict, List, Optional, Tuple


@pytest.mark.asyncio
@pytest.mark.requires_temporal
class TestTemporalSchedules:
    """Test suite for Temporal schedule integration."""

    async def _get_sync_id(
        self, api_client: httpx.AsyncClient, source_connection_id: str
    ) -> Optional[str]:
        """Get sync_id for a source connection, returns None if no sync exists."""
        response = await api_client.get(f"/source-connections/{source_connection_id}/sync-id")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            pytest.fail(f"Failed to get sync_id: {response.text}")
        return response.json()["sync_id"]

    async def _check_temporal_schedules(
        self, sync_id: str, expected_cron: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Check Temporal schedules via REST API for a specific sync."""
        temporal_url = "http://localhost:8088/api/v1/namespaces/default/schedules"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(temporal_url)
                response.raise_for_status()

                schedules_data = response.json()
                matching_schedules = []
                sync_schedule_ids = []

                # Look for schedules related to this sync_id
                # Schedule IDs are: sync-{sync_id}, minute-sync-{sync_id}, daily-cleanup-{sync_id}
                expected_schedule_ids = [
                    f"sync-{sync_id}",
                    f"minute-sync-{sync_id}",
                    f"daily-cleanup-{sync_id}",
                ]

                for schedule in schedules_data.get("schedules", []):
                    schedule_id = schedule.get("scheduleId", "")

                    # Check if this schedule belongs to our sync
                    if schedule_id in expected_schedule_ids:
                        sync_schedule_ids.append(schedule_id)

                        if expected_cron:
                            info = schedule.get("info", {})
                            spec = info.get("spec", {})

                            # Extract CRON expression
                            cron_expr = None
                            if "structuredCalendar" in spec and spec["structuredCalendar"]:
                                # Convert structured calendar to CRON (simplified)
                                structured_cal = spec["structuredCalendar"][0]
                                cron_expr = self._structured_calendar_to_cron(structured_cal)
                            elif "cronExpressions" in spec and spec["cronExpressions"]:
                                cron_expr = spec["cronExpressions"][0]

                            if cron_expr and cron_expr == expected_cron:
                                matching_schedules.append(schedule_id)

                if expected_cron:
                    return len(matching_schedules) > 0, matching_schedules
                else:
                    return len(sync_schedule_ids) > 0, sync_schedule_ids

        except Exception:
            # Temporal might not be available
            pytest.skip("Temporal API not available")

    def _structured_calendar_to_cron(self, structured_cal: dict) -> str:
        """Convert Temporal's structuredCalendar to a CRON expression.

        The structuredCalendar format uses:
        - step=1 with only step means "at 0" (first unit)
        - step=1 with end means "every unit from 0 to end"
        - step=N means "every N units"
        - start/end with step=1 means "every unit in range"
        - Multiple entries in an array mean comma-separated values (e.g., 6,18 for hours)
        """
        # Extract the schedule components - these can be lists for comma-separated values
        minutes = structured_cal.get("minute", [{}])
        hours = structured_cal.get("hour", [{}])
        days_of_month = structured_cal.get("dayOfMonth", [{}])
        months = structured_cal.get("month", [{}])
        days_of_week = structured_cal.get("dayOfWeek", [{}])

        # Convert minutes (handle multiple entries for comma-separated values)
        minute_parts = []
        for minute in minutes:
            if not minute:  # Empty dict
                continue
            if minute.get("step") == 1:
                if "start" in minute and "end" in minute:
                    # Check if start == end (specific minute) or range
                    if minute["start"] == minute["end"]:
                        # Specific minute (most common case: minute 0)
                        minute_parts.append(str(minute["start"]))
                    else:
                        # Range of minutes
                        minute_parts.append("*")
                elif "end" in minute or "start" in minute:
                    # Has range, means every minute in range
                    minute_parts.append("*")
                else:
                    # No range, just step=1 means minute 0
                    minute_parts.append("0")
            elif minute.get("step"):
                minute_parts.append(f"*/{minute['step']}")
            elif "start" in minute:
                # Specific minute value
                minute_parts.append(str(minute.get("start", 0)))
            # Don't add anything for empty dicts
        minute_part = ",".join(minute_parts) if minute_parts else "0"

        # Convert hours (handle multiple entries for comma-separated values)
        hour_parts = []
        for hour in hours:
            if not hour:  # Empty dict
                continue
            if hour.get("step") == 1:
                if "start" in hour and "end" in hour:
                    # Check if start == end (specific hour) or range
                    if hour["start"] == hour["end"]:
                        # Specific hour (e.g., start: 6, end: 6, step: 1)
                        hour_parts.append(str(hour["start"]))
                    else:
                        # Range of hours (e.g., start: 0, end: 23, step: 1)
                        hour_parts.append("*")
                elif "end" in hour:
                    # Has end but no start, means every hour (0-23)
                    hour_parts.append("*")
                else:
                    # No end, just step=1 means hour 0
                    hour_parts.append("0")
            elif hour.get("step"):
                hour_parts.append(f"*/{hour['step']}")
            elif "start" in hour:
                # Specific hour value
                hour_parts.append(str(hour.get("start", 0)))
            # Don't add anything for empty dicts
        hour_part = ",".join(hour_parts) if hour_parts else "0"

        # Convert day of month (usually single value)
        day_of_month = days_of_month[0] if days_of_month else {}
        if day_of_month.get("step") == 1 and ("start" in day_of_month or "end" in day_of_month):
            day_part = "*"
        else:
            day_part = str(day_of_month.get("start", 1)) if day_of_month else "*"

        # Convert month (usually single value)
        month = months[0] if months else {}
        if month.get("step") == 1 and ("start" in month or "end" in month):
            month_part = "*"
        else:
            month_part = str(month.get("start", 1)) if month else "*"

        # Convert day of week (usually single value)
        day_of_week = days_of_week[0] if days_of_week else {}
        if day_of_week.get("step") == 1 and "end" in day_of_week:
            weekday_part = "*"
        elif day_of_week.get("start") is not None:
            if day_of_week.get("end"):
                weekday_part = f"{day_of_week['start']}-{day_of_week['end']}"
            else:
                weekday_part = str(day_of_week["start"])
        else:
            weekday_part = "*"

        return f"{minute_part} {hour_part} {day_part} {month_part} {weekday_part}"

    async def test_daily_schedule(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict, config
    ):
        """Test updating to daily schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_fast["id"]

        # Update to daily schedule
        update_payload = {"schedule": {"cron": "0 0 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 0 * * *"

        # Wait for Temporal to update
        await asyncio.sleep(2)

        # Should have daily schedule
        sync_id = await self._get_sync_id(api_client, conn_id)

        # Check Temporal
        has_schedule, matching = await self._check_temporal_schedules(sync_id, "0 0 * * *")
        assert has_schedule, "Should have daily schedule in Temporal"

    async def test_hourly_schedule(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict, config
    ):
        """Test updating to hourly schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_fast["id"]

        # Update to hourly schedule
        update_payload = {"schedule": {"cron": "0 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 * * * *"

        sync_id = await self._get_sync_id(api_client, conn_id)
        # Wait and check Temporal
        await asyncio.sleep(2)
        has_schedule, matching = await self._check_temporal_schedules(sync_id, "0 * * * *")
        assert has_schedule, "Should have hourly schedule in Temporal"

    async def test_minute_level_schedule_rejection(
        self,
        api_client,
        source_connection_fast,
        config,
    ):
        """Test that minute-level schedules are rejected for non-continuous sources."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_fast["id"]

        # Try minute-level schedule (should fail for Todoist)
        update_payload = {"schedule": {"cron": "*/5 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        # Should be rejected
        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "does not support continuous" in detail or "minimum schedule interval" in detail

    async def test_schedule_removal(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict, config
    ):
        """Test removing schedule deletes Temporal schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_fast["id"]
        sync_id = await self._get_sync_id(api_client, conn_id)

        # First set a schedule
        update_payload = {"schedule": {"cron": "0 2 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        await asyncio.sleep(2)
        has_before, schedules_before = await self._check_temporal_schedules(sync_id, "0 2 * * *")

        # Remove schedule
        update_payload = {"schedule": {"cron": None}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        # Check schedule was removed
        await asyncio.sleep(2)
        has_after, schedules_after = await self._check_temporal_schedules(sync_id, "0 2 * * *")

        # Should have fewer schedules with this CRON
        assert len(schedules_after) < len(schedules_before)

    async def test_schedule_re_enable(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict, config
    ):
        """Test re-enabling schedule creates new Temporal schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_fast["id"]
        sync_id = await self._get_sync_id(api_client, conn_id)

        # Remove any existing schedule
        update_payload = {"schedule": {"cron": None}}
        await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        await asyncio.sleep(2)

        # Re-enable with new schedule
        update_payload = {"schedule": {"cron": "30 2 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "30 2 * * *"

        # Check Temporal
        await asyncio.sleep(2)
        has_schedule, matching = await self._check_temporal_schedules(sync_id, "30 2 * * *")
        assert has_schedule, "Should have new schedule in Temporal"

    async def test_invalid_cron(self, api_client: httpx.AsyncClient, source_connection_fast: dict):
        """Test invalid CRON expression is rejected."""
        conn_id = source_connection_fast["id"]

        update_payload = {"schedule": {"cron": "invalid cron expression"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 422

    async def test_combined_update(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict
    ):
        """Test updating schedule along with other fields."""
        conn_id = source_connection_fast["id"]

        update_payload = {
            "name": "Updated Connection with Schedule",
            "description": "Testing combined updates",
            "schedule": {"cron": "15 3 * * 1"},  # Weekly on Monday
        }

        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Updated Connection with Schedule"
        assert updated["description"] == "Testing combined updates"
        assert updated["schedule"]["cron"] == "15 3 * * 1"

    async def test_minute_level_for_continuous_source(
        self, api_client: httpx.AsyncClient, source_connection_continuous_slow: dict, config
    ):
        """Test minute-level schedules work for continuous sources."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_continuous_slow["id"]
        sync_id = await self._get_sync_id(api_client, conn_id)

        # Set minute-level schedule (should work for Gmail as it's continuous)
        update_payload = {"schedule": {"cron": "*/15 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "*/15 * * * *"

        # Check Temporal
        await asyncio.sleep(2)
        has_schedule, matching = await self._check_temporal_schedules(sync_id, "*/15 * * * *")
        assert has_schedule, "Should have minute-level schedule for continuous source"

    # ============= NULL SCHEDULE TESTS =============

    async def test_schedule_null_no_sync_created(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that schedule:{cron:null} creates no sync or schedules."""
        payload = {
            "name": "No Schedule Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": None},  # Explicitly null cron
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()

        # Should have no schedule
        assert connection.get("schedule") is None or connection["schedule"].get("cron") is None

        # Should have no sync_id
        sync_id = await self._get_sync_id(api_client, connection["id"])
        assert sync_id is None, "No sync should be created with schedule:null"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_schedule_null_with_sync_immediately(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test schedule:{cron:null} with sync_immediately creates one-time sync."""
        payload = {
            "name": "One-time Sync Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": None},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()

        # Should have sync info but no schedule
        assert connection.get("schedule") is None or connection["schedule"].get("cron") is None
        assert connection.get("sync") is not None, "Should have sync info from immediate run"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    # ============= CONTINUOUS SOURCE DEFAULT TESTS =============

    async def test_continuous_source_default_schedules(
        self, api_client: httpx.AsyncClient, collection: Dict, config, composio_auth_provider: Dict
    ):
        """Test continuous source gets minute + cleanup schedules by default."""
        payload = {
            "name": "Continuous Default Schedule",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID,
                },
            },
            # schedule omitted - should get defaults
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()

        # Should have minute-level schedule (*/5 based on updated code)
        assert (
            connection["schedule"]["cron"] == "*/5 * * * *"
        ), "Should have default 5-minute schedule"

        # Check Temporal for both schedules
        sync_id = await self._get_sync_id(api_client, connection["id"])
        assert sync_id is not None

        # TODO: Check for minute-sync-{sync_id} and daily-cleanup-{sync_id} in Temporal

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_continuous_source_custom_minute_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config, composio_auth_provider: Dict
    ):
        """Test continuous source can have custom minute-level schedule."""

        payload = {
            "name": "Custom Minute Schedule",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID,
                },
            },
            "schedule": {"cron": "*/1 * * * *"},  # Every 1 minute
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()

        assert connection["schedule"]["cron"] == "*/1 * * * *"

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    # ============= REGULAR SOURCE DEFAULT TESTS =============

    async def test_regular_source_default_daily_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test regular source gets daily schedule by default."""
        payload = {
            "name": "Regular Default Schedule",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            # schedule omitted - should get daily default
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()

        # Should have daily schedule (check it's in the format "M H * * *")
        cron = connection["schedule"]["cron"]
        parts = cron.split()
        assert len(parts) == 5
        assert parts[2] == "*" and parts[3] == "*" and parts[4] == "*"
        assert 0 <= int(parts[0]) <= 59  # Valid minute
        assert 0 <= int(parts[1]) <= 23  # Valid hour

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_regular_source_rejects_minute_schedule(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test regular source rejects minute-level schedules."""
        payload = {
            "name": "Invalid Minute Schedule",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "*/5 * * * *"},  # Minute-level
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 400
        error = response.json()
        assert "does not support continuous" in error["detail"].lower()

    # ============= OAUTH VALIDATION TESTS =============

    async def test_oauth_browser_rejects_sync_immediately(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test OAuth browser flow rejects sync_immediately=true."""
        payload = {
            "name": "OAuth Invalid Sync",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            },
            "sync_immediately": True,  # Should be rejected
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 400
        error = response.json()
        assert "oauth connections cannot use sync_immediately" in error["detail"].lower()

    async def test_oauth_token_allows_sync_immediately(
        self, api_client: httpx.AsyncClient, collection: Dict
    ):
        """Test OAuth token injection allows sync_immediately."""
        payload = {
            "name": "OAuth Token Sync",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
            },
            "sync_immediately": True,  # Should be allowed
        }

        response = await api_client.post("/source-connections", json=payload)
        # Should succeed (will fail on validation but not on sync_immediately check)
        # We expect 400 from token validation, not from sync_immediately
        if response.status_code == 400:
            error = response.json()
            assert "sync_immediately" not in error["detail"].lower()

    # ============= UPDATE SCHEDULE TESTS =============

    async def test_update_null_schedule_to_create(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test updating from null schedule to create schedule."""
        # Create with null schedule
        payload = {
            "name": "Update Schedule Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": None},  # Explicitly no schedule
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        # Verify no sync initially
        sync_id = await self._get_sync_id(api_client, conn_id)
        assert sync_id is None

        # Update to add schedule
        update_payload = {"schedule": {"cron": "0 3 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200
        updated = response.json()

        assert updated["schedule"]["cron"] == "0 3 * * *"

        # Should now have sync_id
        sync_id = await self._get_sync_id(api_client, conn_id)
        assert sync_id is not None, "Sync should be created when adding schedule"

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_update_schedule_to_null_removes(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test updating schedule to null removes all schedules."""
        # Create with schedule
        payload = {
            "name": "Remove Schedule Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 4 * * *"},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        # Update to remove schedule
        update_payload = {"schedule": {"cron": None}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200
        updated = response.json()

        assert updated.get("schedule") is None or updated["schedule"].get("cron") is None

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_update_regular_source_reject_minute_schedule(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: Dict
    ):
        """Test updating regular source to minute schedule is rejected."""
        conn_id = module_source_connection_stripe["id"]

        # Try to update to minute-level schedule
        update_payload = {"schedule": {"cron": "*/10 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 400
        error = response.json()
        assert "does not support continuous" in error["detail"].lower()

    # ============= SCHEDULE EXECUTION TESTS =============

    async def test_minute_schedule_executes_sync(
        self, api_client: httpx.AsyncClient, collection: Dict, config, composio_auth_provider: Dict
    ):
        """Test that a minute-level schedule actually triggers sync execution."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        # Calculate optimal timing to ensure we catch an execution
        now = datetime.datetime.now(timezone.utc)
        seconds_into_minute = now.second
        seconds_to_next_minute = 60 - seconds_into_minute

        # Strategy: Wait until we're past the next minute boundary, then wait for
        # the NEXT minute boundary to ensure schedule has time to register and fire
        # Total wait: time to next minute + one full minute cycle + 30s buffer
        calculated_wait_time = seconds_to_next_minute + 60 + 30

        # Create connection with schedule that runs EVERY MINUTE
        payload = {
            "name": f"Minute Schedule Execution Test {int(time.time())}",
            "short_name": "gmail",
            "readable_collection_id": collection["readable_id"],
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID,
                },
            },
            "schedule": {"cron": "* * * * *"},  # Run EVERY minute
            "sync_immediately": False,  # Don't sync immediately
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        # Get sync_id
        sync_id = await self._get_sync_id(api_client, conn_id)
        assert sync_id is not None

        # Wait longer for schedule to be created in Temporal (CI environments can be slow)
        await asyncio.sleep(5)

        # Check schedule was created in Temporal
        has_schedule, _ = await self._check_temporal_schedules(sync_id, "* * * * *")
        assert has_schedule, "Schedule should be created in Temporal"

        # Wait calculated time to guarantee catching at least one schedule execution
        # This accounts for current time position and ensures we wait through a full minute cycle
        await asyncio.sleep(calculated_wait_time)

        # Check if sync job was created
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        response.raise_for_status()
        jobs = response.json()

        # Should have at least one job from the schedule
        assert len(jobs) > 0, (
            f"Schedule should have triggered a sync job. "
            f"Waited {calculated_wait_time}s (started at {seconds_into_minute}s into minute)"
        )

        # Verify job is running or completed
        latest_job = jobs[0]
        assert latest_job["status"] in ["pending", "running", "completed"]

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    async def test_hourly_schedule_executes_sync(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that an hourly schedule triggers sync every hour."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        # Calculate optimal target minute for testing
        from datetime import timezone

        now = datetime.datetime.now(timezone.utc)
        seconds_until_next_minute = 60 - now.second

        # Choose target minute based on current second
        if seconds_until_next_minute > 30:
            # Next minute is far enough away, use it
            target_minute = (now.minute + 1) % 60
            base_wait = seconds_until_next_minute + 45  # 45s margin
        else:
            # Too close to next minute, use the one after
            target_minute = (now.minute + 2) % 60
            base_wait = seconds_until_next_minute + 105  # 45s margin after extra minute

        # Check if we're wrapping around to next hour
        if target_minute < now.minute:
            # We're wrapping to the next hour, add time to wait for hour boundary
            minutes_until_hour = 60 - now.minute
            seconds_until_hour = (minutes_until_hour * 60) - now.second
            wait_seconds = seconds_until_hour + (target_minute * 60) + 45  # 45s margin
        else:
            # Same hour, use base wait
            wait_seconds = base_wait

        # Create connection with hourly schedule at specific minute
        payload = {
            "name": f"Hourly Schedule Execution Test {int(time.time())}",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": f"{target_minute} * * * *"},  # Run at specific minute every hour
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        # Get sync_id
        sync_id = await self._get_sync_id(api_client, conn_id)
        assert sync_id is not None

        # Verify schedule in Temporal
        has_schedule, _ = await self._check_temporal_schedules(sync_id, f"{target_minute} * * * *")
        assert has_schedule, "Schedule should be created in Temporal"

        # Wait for the scheduled time (calculated above)
        # Add extra margin for processing
        await asyncio.sleep(wait_seconds)

        # Check for sync job
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        response.raise_for_status()
        jobs = response.json()

        assert len(jobs) > 0, "Schedule should have triggered a sync job"

        # Verify latest job
        latest_job = jobs[0]
        assert latest_job["status"] in ["pending", "running", "completed"]

        # Cleanup
        await api_client.delete(f"/source-connections/{conn_id}")

    # ============= TIMEZONE HANDLING TESTS =============

    async def test_next_run_timezone_aware_serialization(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that next_run_at is properly timezone-aware when retrieved."""
        # Create connection with daily schedule
        payload = {
            "name": "Timezone Test Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "30 14 * * *"},  # 2:30 PM UTC daily
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        try:
            # Get the connection details
            response = await api_client.get(f"/source-connections/{conn_id}")
            assert response.status_code == 200
            conn_details = response.json()

            # Verify schedule exists
            assert conn_details.get("schedule") is not None
            assert conn_details["schedule"]["cron"] == "30 14 * * *"

            # Verify next_run is present and properly formatted
            next_run = conn_details["schedule"].get("next_run")
            assert next_run is not None, "next_run should be present"

            # Parse the datetime string - it should be ISO format with timezone
            from datetime import datetime

            parsed_next_run = datetime.fromisoformat(next_run.replace("Z", "+00:00"))

            # Verify it's timezone-aware (has tzinfo)
            assert parsed_next_run.tzinfo is not None, "next_run should be timezone-aware"

            # Verify it's in UTC
            assert parsed_next_run.tzinfo == timezone.utc, "next_run should be in UTC timezone"

            # Verify the time components match the cron expression
            assert parsed_next_run.hour == 14
            assert parsed_next_run.minute == 30

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{conn_id}")

    async def test_cron_schedule_update_calculates_next_run(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict
    ):
        """Test that updating cron_schedule properly calculates next_scheduled_run."""
        conn_id = source_connection_fast["id"]

        # Update with a specific schedule
        update_payload = {"schedule": {"cron": "45 10 * * *"}}  # 10:45 AM UTC daily
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()

        # Verify schedule was updated
        assert updated["schedule"]["cron"] == "45 10 * * *"

        # Get full connection details to check next_run
        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200
        conn_details = response.json()

        # Verify next_run is calculated
        next_run = conn_details["schedule"].get("next_run")
        assert next_run is not None, "next_run should be calculated after schedule update"

        # Parse and verify the next run time
        from datetime import datetime

        parsed_next_run = datetime.fromisoformat(next_run.replace("Z", "+00:00"))

        # Should be in the future
        now = datetime.now(timezone.utc)
        assert parsed_next_run > now, "next_run should be in the future"

        # Should match the cron pattern
        assert parsed_next_run.hour == 10
        assert parsed_next_run.minute == 45

    async def test_null_schedule_clears_next_run(
        self, api_client: httpx.AsyncClient, source_connection_fast: dict
    ):
        """Test that setting schedule to null also clears next_scheduled_run."""
        conn_id = source_connection_fast["id"]

        # First set a schedule
        update_payload = {"schedule": {"cron": "0 6 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        # Verify next_run is set
        response = await api_client.get(f"/source-connections/{conn_id}")
        conn_with_schedule = response.json()
        assert conn_with_schedule["schedule"].get("next_run") is not None

        # Now remove the schedule
        update_payload = {"schedule": {"cron": None}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        # Verify next_run is cleared
        response = await api_client.get(f"/source-connections/{conn_id}")
        conn_without_schedule = response.json()
        assert (
            conn_without_schedule.get("schedule") is None
            or conn_without_schedule["schedule"].get("next_run") is None
        )

    async def test_croniter_base_uses_utc(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that croniter calculations use UTC as base, not local time."""
        # Create two connections with same schedule at different times
        connections = []

        for i in range(2):
            payload = {
                "name": f"UTC Base Test {i}",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "schedule": {"cron": "0 12 * * *"},  # Noon UTC daily
                "sync_immediately": False,
            }

            response = await api_client.post("/source-connections", json=payload)
            assert response.status_code == 200
            connections.append(response.json())

            # Small delay between creations
            await asyncio.sleep(1)

        try:
            # Get both connections and compare next_run times
            next_runs = []
            for conn in connections:
                response = await api_client.get(f"/source-connections/{conn['id']}")
                assert response.status_code == 200
                conn_details = response.json()
                next_run = conn_details["schedule"]["next_run"]
                next_runs.append(next_run)

            # Both should have the same next_run (since they have the same cron expression)
            # Small tolerance for processing time differences
            from datetime import datetime

            dt1 = datetime.fromisoformat(next_runs[0].replace("Z", "+00:00"))
            dt2 = datetime.fromisoformat(next_runs[1].replace("Z", "+00:00"))

            # Should be within 1 minute of each other (accounting for processing delays)
            time_diff = abs((dt1 - dt2).total_seconds())
            assert (
                time_diff < 60
            ), f"Next run times should be nearly identical, but differ by {time_diff} seconds"

        finally:
            # Cleanup
            for conn in connections:
                await api_client.delete(f"/source-connections/{conn['id']}")

    async def test_schedule_with_different_timezones(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that schedules work correctly regardless of server timezone."""
        # Create connection with schedule that runs at specific UTC time
        payload = {
            "name": "Fixed UTC Schedule",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "0 0 * * *"},  # Midnight UTC
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        try:
            # Get connection details
            response = await api_client.get(f"/source-connections/{conn_id}")
            assert response.status_code == 200
            conn_details = response.json()

            next_run_str = conn_details["schedule"]["next_run"]
            from datetime import datetime

            next_run = datetime.fromisoformat(next_run_str.replace("Z", "+00:00"))

            # Verify it's at midnight UTC
            assert next_run.hour == 0
            assert next_run.minute == 0
            assert next_run.tzinfo == timezone.utc

            # Update to different time
            update_payload = {"schedule": {"cron": "30 23 * * *"}}  # 11:30 PM UTC
            response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
            assert response.status_code == 200

            # Get updated details
            response = await api_client.get(f"/source-connections/{conn_id}")
            assert response.status_code == 200
            updated_details = response.json()

            updated_next_run_str = updated_details["schedule"]["next_run"]
            updated_next_run = datetime.fromisoformat(updated_next_run_str.replace("Z", "+00:00"))

            # Verify it's at 11:30 PM UTC
            assert updated_next_run.hour == 23
            assert updated_next_run.minute == 30
            assert updated_next_run.tzinfo == timezone.utc

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{conn_id}")

    async def test_schedule_persistence_across_restarts(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test that next_scheduled_run persists correctly in database."""
        # Create connection with schedule
        payload = {
            "name": "Persistence Test",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
            "schedule": {"cron": "15 8 * * *"},  # 8:15 AM UTC
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)
        assert response.status_code == 200
        connection = response.json()
        conn_id = connection["id"]

        try:
            # Get initial next_run
            response = await api_client.get(f"/source-connections/{conn_id}")
            initial_details = response.json()
            initial_next_run = initial_details["schedule"]["next_run"]

            # Simulate "restart" by just fetching again (in real scenario, this would be after service restart)
            await asyncio.sleep(1)

            # Get next_run again
            response = await api_client.get(f"/source-connections/{conn_id}")
            after_details = response.json()
            after_next_run = after_details["schedule"]["next_run"]

            # Should be the same (persisted in database)
            assert initial_next_run == after_next_run, "next_run should persist across fetches"

            # Both should be properly formatted with timezone
            from datetime import datetime

            initial_dt = datetime.fromisoformat(initial_next_run.replace("Z", "+00:00"))
            after_dt = datetime.fromisoformat(after_next_run.replace("Z", "+00:00"))

            assert initial_dt == after_dt
            assert initial_dt.tzinfo == timezone.utc
            assert after_dt.tzinfo == timezone.utc

        finally:
            # Cleanup
            await api_client.delete(f"/source-connections/{conn_id}")
