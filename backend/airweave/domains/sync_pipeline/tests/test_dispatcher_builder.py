"""Table-driven tests for EntityDispatcherBuilder handler flag combinations."""

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from airweave.domains.sync_pipeline.config.base import HandlerConfig, SyncConfig
from airweave.domains.sync_pipeline.entity.dispatcher import EntityActionDispatcher
from airweave.domains.sync_pipeline.entity.dispatcher_builder import (
    EntityDispatcherBuilder,
)
from airweave.domains.sync_pipeline.entity.handlers.arf import ArfHandler
from airweave.domains.sync_pipeline.entity.handlers.destination import DestinationHandler
from airweave.domains.sync_pipeline.entity.handlers.postgres import EntityPostgresHandler


def _make_builder(*, arf_service=MagicMock()):
    return EntityDispatcherBuilder(
        processor=MagicMock(),
        entity_repo=MagicMock(),
        arf_service=arf_service,
    )


def _make_config(*, vector=True, arf=True, postgres=True) -> SyncConfig:
    return SyncConfig(
        handlers=HandlerConfig(
            enable_vector_handlers=vector,
            enable_raw_data_handler=arf,
            enable_postgres_handler=postgres,
        )
    )


@dataclass
class BuilderCase:
    name: str
    enable_vector: bool = True
    enable_arf: bool = True
    enable_postgres: bool = True
    has_destinations: bool = True
    arf_service_none: bool = False
    expected_dest_handler_types: List[type] = field(default_factory=list)
    expected_metadata_handler_type: Optional[type] = None


CASES = [
    BuilderCase(
        name="all_enabled",
        expected_dest_handler_types=[DestinationHandler, ArfHandler],
        expected_metadata_handler_type=EntityPostgresHandler,
    ),
    BuilderCase(
        name="vector_disabled",
        enable_vector=False,
        expected_dest_handler_types=[ArfHandler],
        expected_metadata_handler_type=EntityPostgresHandler,
    ),
    BuilderCase(
        name="arf_disabled",
        enable_arf=False,
        expected_dest_handler_types=[DestinationHandler],
        expected_metadata_handler_type=EntityPostgresHandler,
    ),
    BuilderCase(
        name="postgres_disabled",
        enable_postgres=False,
        expected_dest_handler_types=[DestinationHandler, ArfHandler],
        expected_metadata_handler_type=None,
    ),
    BuilderCase(
        name="all_disabled",
        enable_vector=False,
        enable_arf=False,
        enable_postgres=False,
        expected_dest_handler_types=[],
        expected_metadata_handler_type=None,
    ),
    BuilderCase(
        name="arf_service_none",
        arf_service_none=True,
        expected_dest_handler_types=[DestinationHandler],
        expected_metadata_handler_type=EntityPostgresHandler,
    ),
    BuilderCase(
        name="no_destinations",
        has_destinations=False,
        expected_dest_handler_types=[ArfHandler],
        expected_metadata_handler_type=EntityPostgresHandler,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_build_produces_expected_handlers(case: BuilderCase):
    arf_svc = None if case.arf_service_none else MagicMock()
    builder = _make_builder(arf_service=arf_svc)

    destinations = [MagicMock()] if case.has_destinations else []
    config = _make_config(
        vector=case.enable_vector,
        arf=case.enable_arf,
        postgres=case.enable_postgres,
    )
    logger = MagicMock()

    dispatcher = builder.build(destinations=destinations, execution_config=config, logger=logger)

    assert isinstance(dispatcher, EntityActionDispatcher)

    dest_types = [type(h) for h in dispatcher._destination_handlers]
    assert dest_types == case.expected_dest_handler_types

    if case.expected_metadata_handler_type is None:
        assert dispatcher._postgres_handler is None
    else:
        assert isinstance(dispatcher._postgres_handler, case.expected_metadata_handler_type)


def test_build_without_config_enables_all():
    """No execution_config → all handlers enabled (defaults)."""
    builder = _make_builder()
    dispatcher = builder.build(
        destinations=[MagicMock()],
        execution_config=None,
        logger=MagicMock(),
    )
    assert len(dispatcher._destination_handlers) == 2
    assert dispatcher._postgres_handler is not None


def test_build_for_cleanup_uses_no_config():
    """build_for_cleanup delegates to build(execution_config=None)."""
    builder = _make_builder()
    dispatcher = builder.build_for_cleanup(
        destinations=[MagicMock()],
        logger=MagicMock(),
    )
    assert len(dispatcher._destination_handlers) == 2
    assert dispatcher._postgres_handler is not None


def test_all_disabled_logs_warning():
    """When all handlers are disabled, a warning is logged."""
    builder = _make_builder(arf_service=None)
    logger = MagicMock()
    config = _make_config(vector=False, arf=False, postgres=False)

    builder.build(destinations=[], execution_config=config, logger=logger)

    logger.warning.assert_called_once()
    assert "No handlers created" in logger.warning.call_args[0][0]
