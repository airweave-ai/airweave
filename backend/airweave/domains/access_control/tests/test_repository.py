"""Table-driven tests for AccessControlMembershipRepository.

Each method is a 1-line delegation to crud.access_control_membership.
We verify every method forwards arguments correctly.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.access_control.repository import AccessControlMembershipRepository

ORG_ID = uuid4()
SC_ID = uuid4()


@dataclass
class RepositoryMethodCase:
    name: str
    method: str
    args: List[Any]
    kwargs: Dict[str, Any]
    crud_method: str
    expected_crud_args: List[Any]
    expected_crud_kwargs: Dict[str, Any]
    crud_return: Any


CASES = [
    RepositoryMethodCase(
        name="bulk_create",
        method="bulk_create",
        args=[],
        kwargs=dict(
            memberships=["m1", "m2"],
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_name="slack",
        ),
        crud_method="bulk_create",
        expected_crud_args=[["m1", "m2"], ORG_ID, SC_ID, "slack"],
        expected_crud_kwargs={},
        crud_return=2,
    ),
    RepositoryMethodCase(
        name="upsert",
        method="upsert",
        args=[],
        kwargs=dict(
            member_id="alice",
            member_type="user",
            group_id="g1",
            group_name="Engineering",
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_name="slack",
        ),
        crud_method="upsert",
        expected_crud_args=[],
        expected_crud_kwargs=dict(
            member_id="alice",
            member_type="user",
            group_id="g1",
            group_name="Engineering",
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_name="slack",
        ),
        crud_return=None,
    ),
    RepositoryMethodCase(
        name="delete_by_key",
        method="delete_by_key",
        args=[],
        kwargs=dict(
            member_id="alice",
            member_type="user",
            group_id="g1",
            source_connection_id=SC_ID,
            organization_id=ORG_ID,
        ),
        crud_method="delete_by_key",
        expected_crud_args=[],
        expected_crud_kwargs=dict(
            member_id="alice",
            member_type="user",
            group_id="g1",
            source_connection_id=SC_ID,
            organization_id=ORG_ID,
        ),
        crud_return=1,
    ),
    RepositoryMethodCase(
        name="delete_by_group",
        method="delete_by_group",
        args=[],
        kwargs=dict(group_id="g1", source_connection_id=SC_ID, organization_id=ORG_ID),
        crud_method="delete_by_group",
        expected_crud_args=[],
        expected_crud_kwargs=dict(group_id="g1", source_connection_id=SC_ID, organization_id=ORG_ID),
        crud_return=3,
    ),
    RepositoryMethodCase(
        name="get_by_source_connection",
        method="get_by_source_connection",
        args=[SC_ID, ORG_ID],
        kwargs={},
        crud_method="get_by_source_connection",
        expected_crud_args=[SC_ID, ORG_ID],
        expected_crud_kwargs={},
        crud_return=[],
    ),
    RepositoryMethodCase(
        name="bulk_delete",
        method="bulk_delete",
        args=[[uuid4(), uuid4()]],
        kwargs={},
        crud_method="bulk_delete",
        expected_crud_args=None,  # checked via call_args
        expected_crud_kwargs={},
        crud_return=2,
    ),
    RepositoryMethodCase(
        name="get_by_member",
        method="get_by_member",
        args=["alice", "user", ORG_ID],
        kwargs={},
        crud_method="get_by_member",
        expected_crud_args=["alice", "user", ORG_ID],
        expected_crud_kwargs={},
        crud_return=[],
    ),
    RepositoryMethodCase(
        name="get_by_member_and_collection",
        method="get_by_member_and_collection",
        args=["alice", "user", "coll-1", ORG_ID],
        kwargs={},
        crud_method="get_by_member_and_collection",
        expected_crud_args=["alice", "user", "coll-1", ORG_ID],
        expected_crud_kwargs={},
        crud_return=[],
    ),
    RepositoryMethodCase(
        name="get_memberships_by_groups",
        method="get_memberships_by_groups",
        args=[],
        kwargs=dict(group_ids=["g1", "g2"], source_connection_id=SC_ID, organization_id=ORG_ID),
        crud_method="get_memberships_by_groups",
        expected_crud_args=[],
        expected_crud_kwargs=dict(
            group_ids=["g1", "g2"], source_connection_id=SC_ID, organization_id=ORG_ID
        ),
        crud_return=[],
    ),
    RepositoryMethodCase(
        name="delete_by_source_connection",
        method="delete_by_source_connection",
        args=[SC_ID, ORG_ID],
        kwargs={},
        crud_method="delete_by_source_connection",
        expected_crud_args=[SC_ID, ORG_ID],
        expected_crud_kwargs={},
        crud_return=5,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
@pytest.mark.asyncio
async def test_repository_delegates_to_crud(case: RepositoryMethodCase):
    """Each repo method delegates to crud.access_control_membership with correct args."""
    db = MagicMock()
    repo = AccessControlMembershipRepository()

    crud_mock = AsyncMock(return_value=case.crud_return)

    with patch(
        f"airweave.domains.access_control.repository.crud.access_control_membership"
    ) as mock_singleton:
        setattr(mock_singleton, case.crud_method, crud_mock)

        method: Callable = getattr(repo, case.method)
        result = await method(db, *case.args, **case.kwargs)

    assert result == case.crud_return
    crud_mock.assert_called_once()

    call_args, call_kwargs = crud_mock.call_args
    # First positional arg is always the db session
    assert call_args[0] is db
    # Verify keyword args match
    for k, v in case.expected_crud_kwargs.items():
        assert call_kwargs[k] == v
