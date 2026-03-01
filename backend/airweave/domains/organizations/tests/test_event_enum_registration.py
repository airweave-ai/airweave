"""Tests for organization event enum registration.

Verifies that OrganizationEventType is properly registered in the
EventType union and ALL_EVENT_TYPE_ENUMS tuple. If these are missing,
events won't match subscriber patterns and the webhook EventType enum
(derived from ALL_EVENT_TYPE_ENUMS) won't include org events.
"""

from airweave.core.events.enums import (
    ALL_EVENT_TYPE_ENUMS,
    EventType,
    OrganizationEventType,
)


class TestOrganizationEventTypeRegistration:
    def test_all_values_are_organization_prefixed(self):
        for member in OrganizationEventType:
            assert member.value.startswith("organization."), (
                f"{member.name} has value '{member.value}' — must start with 'organization.'"
            )

    def test_registered_in_all_event_type_enums(self):
        assert OrganizationEventType in ALL_EVENT_TYPE_ENUMS, (
            "OrganizationEventType not in ALL_EVENT_TYPE_ENUMS — "
            "webhooks EventType enum won't include org events"
        )

    def test_values_accepted_by_event_type_union(self):
        """Each org event value must be assignable to the EventType union."""
        for member in OrganizationEventType:
            assert isinstance(member, EventType.__args__), (
                f"{member} is not a valid EventType"
            )

    def test_has_expected_members(self):
        expected = {"CREATED", "DELETED", "MEMBER_ADDED", "MEMBER_REMOVED"}
        actual = {m.name for m in OrganizationEventType}
        assert expected == actual, f"Missing or extra members: {expected.symmetric_difference(actual)}"
