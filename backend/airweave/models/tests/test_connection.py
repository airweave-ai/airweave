"""Tests for Connection ORM event listeners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from sqlalchemy import create_engine, text

from airweave.models.connection import delete_integration_credential

_CREATE_INTEGRATION_CREDENTIAL = text(
    "CREATE TABLE integration_credential (id TEXT PRIMARY KEY)"
)


@dataclass(frozen=True)
class _Target:
    integration_credential_id: Optional[str]


def test_delete_integration_credential_removes_row():
    """Row is deleted when integration_credential_id is present."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    cred_id = str(uuid4())

    with engine.begin() as conn:
        conn.execute(_CREATE_INTEGRATION_CREDENTIAL)
        conn.execute(
            text("INSERT INTO integration_credential (id) VALUES (:id)"),
            {"id": cred_id},
        )

        target = _Target(integration_credential_id=cred_id)
        delete_integration_credential(mapper=None, connection=conn, target=target)

        count = conn.execute(
            text("SELECT count(*) FROM integration_credential")
        ).scalar_one()
        assert count == 0


def test_delete_integration_credential_noop_when_none():
    """No DELETE executed when integration_credential_id is None."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    cred_id = str(uuid4())

    with engine.begin() as conn:
        conn.execute(_CREATE_INTEGRATION_CREDENTIAL)
        conn.execute(
            text("INSERT INTO integration_credential (id) VALUES (:id)"),
            {"id": cred_id},
        )

        target = _Target(integration_credential_id=None)
        delete_integration_credential(mapper=None, connection=conn, target=target)

        count = conn.execute(
            text("SELECT count(*) FROM integration_credential")
        ).scalar_one()
        assert count == 1
