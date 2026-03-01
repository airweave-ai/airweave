"""Tests for OrganizationLifecycleEvent factory methods.

Verifies each factory method produces the correct event_type, carries
the right fields, and handles defaults/edge cases. These events flow
through the entire bus → subscriber chain, so correctness here is critical.
"""

from uuid import uuid4

import pytest

from airweave.core.events.enums import OrganizationEventType
from airweave.core.events.organization import OrganizationLifecycleEvent

ORG_ID = uuid4()


class TestCreatedEvent:
    def test_event_type(self):
        e = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="Acme", owner_email="a@b.com",
        )
        assert e.event_type == OrganizationEventType.CREATED
        assert e.event_type.value == "organization.created"

    def test_carries_all_fields(self):
        e = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="Acme",
            owner_email="a@b.com", plan="team",
        )
        assert e.organization_id == ORG_ID
        assert e.organization_name == "Acme"
        assert e.owner_email == "a@b.com"
        assert e.plan == "team"

    def test_plan_defaults_to_developer(self):
        e = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )
        assert e.plan == "developer"

    def test_timestamp_auto_populated(self):
        e = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )
        assert e.timestamp is not None

    def test_frozen_immutability(self):
        e = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )
        with pytest.raises(Exception):
            e.organization_name = "changed"


class TestDeletedEvent:
    def test_event_type(self):
        e = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID, organization_name="Doomed",
        )
        assert e.event_type == OrganizationEventType.DELETED

    def test_affected_emails_carried(self):
        emails = ["a@x.com", "b@x.com"]
        e = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID, organization_name="X",
            affected_user_emails=emails,
        )
        assert e.affected_user_emails == emails

    def test_none_affected_emails_becomes_empty_list(self):
        e = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID, organization_name="X",
            affected_user_emails=None,
        )
        assert e.affected_user_emails == []

    def test_owner_email_empty_by_default(self):
        e = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID, organization_name="X",
        )
        assert e.owner_email == ""


class TestMemberAddedEvent:
    def test_event_type(self):
        e = OrganizationLifecycleEvent.member_added(organization_id=ORG_ID)
        assert e.event_type == OrganizationEventType.MEMBER_ADDED

    def test_affected_emails(self):
        e = OrganizationLifecycleEvent.member_added(
            organization_id=ORG_ID, affected_user_emails=["new@x.com"],
        )
        assert e.affected_user_emails == ["new@x.com"]


class TestMemberRemovedEvent:
    def test_event_type(self):
        e = OrganizationLifecycleEvent.member_removed(organization_id=ORG_ID)
        assert e.event_type == OrganizationEventType.MEMBER_REMOVED

    def test_defaults(self):
        e = OrganizationLifecycleEvent.member_removed(organization_id=ORG_ID)
        assert e.organization_name == ""
        assert e.affected_user_emails == []
