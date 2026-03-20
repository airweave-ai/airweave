"""Shared fixtures for sync model tests."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

import airweave.models.sync as sync_model

_CREATE_SYNC_JOB = text(
    """
    CREATE TABLE sync_job (
        id TEXT PRIMARY KEY,
        sync_id TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        modified_at DATETIME NULL
    )
    """
)


@pytest.fixture()
def sync_job_db():
    """In-memory SQLite with a ``sync_job`` table, inside a transaction."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(_CREATE_SYNC_JOB)
        yield connection


class LogCollector:
    """Drop-in replacement for the module logger that captures messages."""

    def __init__(self):
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.debugs: list[str] = []

    def warning(self, message: str):
        self.warnings.append(message)

    def info(self, message: str):
        self.infos.append(message)

    def debug(self, message: str):
        self.debugs.append(message)


@pytest.fixture()
def quiet_logger(monkeypatch: pytest.MonkeyPatch) -> LogCollector:
    """Replace ``sync_model.logger`` with a :class:`LogCollector`."""
    collector = LogCollector()
    monkeypatch.setattr(sync_model, "logger", collector)
    return collector
