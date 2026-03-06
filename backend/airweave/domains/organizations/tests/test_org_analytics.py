"""Tests for organization event handling in the AnalyticsEventSubscriber.

Wires the real subscriber with a FakeAnalyticsTracker and drives org events
through it. Verifies that the correct PostHog calls (track + group_identify)
are produced with the right properties.
"""

from uuid import uuid4

import pytest

from airweave.adapters.analytics.fake import FakeAnalyticsTracker
from airweave.adapters.analytics.subscriber import AnalyticsEventSubscriber
from airweave.core.events.organization import OrganizationLifecycleEvent

ORG_ID = uuid4()
OWNER_EMAIL = "owner@example.com"


def _make_subscriber():
    tracker = FakeAnalyticsTracker()
    subscriber = AnalyticsEventSubscriber(tracker)
    return subscriber, tracker


# ---------------------------------------------------------------------------
# organization.created
# ---------------------------------------------------------------------------


class TestOrgCreatedAnalytics:
    @pytest.mark.asyncio
    async def test_group_identify_called(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID,
            organization_name="Test Org",
            owner_email=OWNER_EMAIL,
            plan="pro",
        )

        await subscriber.handle(event)

        group_event = tracker.get("$group_identify:organization")
        assert group_event.distinct_id == str(ORG_ID)
        assert group_event.properties["organization_name"] == "Test Org"
        assert group_event.properties["organization_plan"] == "pro"

    @pytest.mark.asyncio
    async def test_track_event_fired(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID,
            organization_name="Test Org",
            owner_email=OWNER_EMAIL,
            plan="team",
        )

        await subscriber.handle(event)

        track_event = tracker.get("organization_created")
        assert track_event.distinct_id == OWNER_EMAIL
        assert track_event.properties["plan"] == "team"
        assert track_event.properties["organization_id"] == str(ORG_ID)
        assert track_event.groups == {"organization": str(ORG_ID)}

    @pytest.mark.asyncio
    async def test_missing_plan_defaults_to_developer(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID,
            organization_name="Test",
            owner_email=OWNER_EMAIL,
        )

        await subscriber.handle(event)

        track_event = tracker.get("organization_created")
        assert track_event.properties["plan"] == "developer"

    @pytest.mark.asyncio
    async def test_missing_owner_email_uses_org_id(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID,
            organization_name="Test",
            owner_email="",
        )

        await subscriber.handle(event)

        track_event = tracker.get("organization_created")
        assert track_event.distinct_id == str(ORG_ID)


# ---------------------------------------------------------------------------
# organization.deleted
# ---------------------------------------------------------------------------


class TestOrgDeletedAnalytics:
    @pytest.mark.asyncio
    async def test_track_event_fired(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID,
            organization_name="Doomed Org",
            affected_user_emails=["a@x.com", "b@x.com"],
        )

        await subscriber.handle(event)

        track_event = tracker.get("organization_deleted")
        assert track_event.properties["affected_users"] == 2
        assert track_event.properties["organization_name"] == "Doomed Org"

    @pytest.mark.asyncio
    async def test_no_affected_users(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID,
            organization_name="Empty Org",
        )

        await subscriber.handle(event)

        track_event = tracker.get("organization_deleted")
        assert track_event.properties["affected_users"] == 0


# ---------------------------------------------------------------------------
# Unhandled org events (member_added, member_removed) — should not crash
# ---------------------------------------------------------------------------


class TestUnhandledOrgEvents:
    @pytest.mark.asyncio
    async def test_member_added_does_not_crash(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.member_added(
            organization_id=ORG_ID,
            organization_name="Test",
            affected_user_emails=["new@x.com"],
        )

        await subscriber.handle(event)
        assert len(tracker.events) == 0

    @pytest.mark.asyncio
    async def test_member_removed_does_not_crash(self):
        subscriber, tracker = _make_subscriber()
        event = OrganizationLifecycleEvent.member_removed(
            organization_id=ORG_ID,
            organization_name="Test",
            affected_user_emails=["gone@x.com"],
        )

        await subscriber.handle(event)
        assert len(tracker.events) == 0
