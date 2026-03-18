"""Tests for AgentState."""

from airweave.domains.search.agentic.tests.conftest import make_result, make_state


class TestAddToCollected:
    """Tests for AgentState.add_to_collected."""

    def test_adds_known_entity(self) -> None:
        """Entity in results pool → added to collected."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r})

        newly, already, not_found = state.add_to_collected(["ent-1"])

        assert newly == ["ent-1"]
        assert already == []
        assert not_found == []
        assert "ent-1" in state.collected_ids

    def test_already_collected(self) -> None:
        """Entity already in collected → returned in already list."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r}, collected_ids={"ent-1"})

        newly, already, not_found = state.add_to_collected(["ent-1"])

        assert newly == []
        assert already == ["ent-1"]
        assert not_found == []

    def test_unknown_entity(self) -> None:
        """Entity not in results pool → returned in not_found."""
        state = make_state()

        newly, already, not_found = state.add_to_collected(["unknown"])

        assert newly == []
        assert already == []
        assert not_found == ["unknown"]

    def test_mixed_input(self) -> None:
        """Mix of new, already collected, and unknown."""
        r1 = make_result(entity_id="ent-1")
        r2 = make_result(entity_id="ent-2")
        state = make_state(
            results={"ent-1": r1, "ent-2": r2},
            collected_ids={"ent-2"},
        )

        newly, already, not_found = state.add_to_collected(["ent-1", "ent-2", "ent-3"])

        assert newly == ["ent-1"]
        assert already == ["ent-2"]
        assert not_found == ["ent-3"]
        assert state.collected_ids == {"ent-1", "ent-2"}


class TestRemoveFromCollected:
    """Tests for AgentState.remove_from_collected."""

    def test_removes_collected_entity(self) -> None:
        """Entity in collected → removed."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r}, collected_ids={"ent-1"})

        removed, not_in = state.remove_from_collected(["ent-1"])

        assert removed == ["ent-1"]
        assert not_in == []
        assert "ent-1" not in state.collected_ids

    def test_not_in_collected(self) -> None:
        """Entity not in collected → returned in not_in_collected."""
        state = make_state()

        removed, not_in = state.remove_from_collected(["ent-1"])

        assert removed == []
        assert not_in == ["ent-1"]
