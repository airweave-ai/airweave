"""Exception stub source for testing error handling in the sync pipeline.

Generates a configurable number of entities, then raises a chosen exception type
so you can verify how the UI and pipeline respond to different error scenarios.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from typing import AsyncGenerator, Callable

from pydantic import BaseModel

from airweave.core.logging import ContextualLogger
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceRateLimitError,
    SourceServerError,
    SourceTokenRefreshError,
)
from airweave.domains.sources.token_providers.exceptions import (
    TokenCredentialsInvalidError,
    TokenExpiredError,
    TokenProviderConfigError,
    TokenProviderServerError,
)
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    SourceAuthProvider,
)
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import StubAuthConfig
from airweave.platform.configs.config import ExceptionStubConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.stub import SmallStubEntity, StubContainerEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod

SHORT_NAME = "exception_stub"

NOUNS = ["project", "task", "document", "report", "meeting", "analysis", "review", "plan"]
ADJECTIVES = ["important", "urgent", "critical", "minor", "quick", "detailed", "final", "draft"]
AUTHORS = ["Alice Smith", "Bob Johnson", "Charlie Brown", "Diana Prince", "Eve Wilson"]


def _build_exception_factories(
    error_message: str,
    auth_provider_kind: AuthProviderKind,
) -> dict[str, Callable[[], BaseException]]:
    """Build a map of exception_type string -> factory callable."""
    kind_str = auth_provider_kind.value

    return {
        "runtime_error": lambda: RuntimeError(error_message),
        "source_auth_error": lambda: SourceAuthError(
            error_message,
            source_short_name=SHORT_NAME,
            status_code=401,
            token_provider_kind=auth_provider_kind,
        ),
        "source_token_refresh_error": lambda: SourceTokenRefreshError(
            error_message,
            source_short_name=SHORT_NAME,
            token_provider_kind=auth_provider_kind,
        ),
        "source_server_error": lambda: SourceServerError(
            error_message,
            source_short_name=SHORT_NAME,
            status_code=500,
        ),
        "source_rate_limit_error": lambda: SourceRateLimitError(
            retry_after=30.0,
            source_short_name=SHORT_NAME,
            message=error_message,
        ),
        "source_entity_not_found": lambda: SourceEntityNotFoundError(
            error_message,
            source_short_name=SHORT_NAME,
            entity_id="exception-stub-entity",
        ),
        "source_entity_forbidden": lambda: SourceEntityForbiddenError(
            error_message,
            source_short_name=SHORT_NAME,
            entity_id="exception-stub-entity",
        ),
        "token_expired": lambda: TokenExpiredError(
            error_message,
            source_short_name=SHORT_NAME,
            provider_kind=kind_str,
        ),
        "token_credentials_invalid": lambda: TokenCredentialsInvalidError(
            error_message,
            source_short_name=SHORT_NAME,
            provider_kind=kind_str,
        ),
        "token_provider_config_error": lambda: TokenProviderConfigError(
            error_message,
            source_short_name=SHORT_NAME,
            provider_kind=kind_str,
        ),
        "token_provider_server_error": lambda: TokenProviderServerError(
            error_message,
            source_short_name=SHORT_NAME,
            provider_kind=kind_str,
            status_code=500,
        ),
        "timeout": lambda: asyncio.TimeoutError(error_message),
        "cancelled": lambda: asyncio.CancelledError(error_message),
    }


@source(
    name="Exception Stub",
    short_name=SHORT_NAME,
    auth_methods=[AuthenticationMethod.DIRECT],
    oauth_type=None,
    auth_config_class=StubAuthConfig,
    config_class=ExceptionStubConfig,
    labels=["Internal", "Testing"],
    supports_continuous=False,
    internal=True,
)
class ExceptionStubSource(BaseSource):
    """Source that raises configurable exceptions for testing error handling.

    Generates deterministic test entities up to a trigger point, then raises
    the configured exception. Useful for verifying UI error states and
    pipeline error propagation.
    """

    _config: ExceptionStubConfig
    _resolved_trigger: int
    _exception_factories: dict[str, Callable[[], BaseException]]
    _error_message: str

    @classmethod
    async def create(
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: BaseModel,
    ) -> ExceptionStubSource:
        """Create a new exception stub source instance."""
        assert isinstance(config, ExceptionStubConfig)
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance._config = config

        # Resolve trigger_after=-1 to mean "after last entity"
        trigger = config.trigger_after
        if trigger == -1:
            trigger = config.entity_count - 1  # -1 because container is entity 0
        instance._resolved_trigger = trigger

        # Build error message
        msg = config.error_message or (
            f"[ExceptionStub] {config.exception_type} triggered after "
            f"{trigger} entities (simulated failure)"
        )
        provider_kind = AuthProviderKind(config.auth_provider_kind)
        instance._exception_factories = _build_exception_factories(msg, provider_kind)
        instance._error_message = msg

        return instance

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities and raise configured exception at trigger point."""
        config = self._config
        rng = random.Random(config.seed)  # noqa: S311

        self.logger.info(
            f"ExceptionStub: generating up to {config.entity_count} entities, "
            f"will raise {config.exception_type} after {self._resolved_trigger}"
        )

        # Always yield the container first
        container_id = f"exception-stub-container-{config.seed}"
        yield StubContainerEntity(
            container_id=container_id,
            container_name=f"Exception Stub Container (seed={config.seed})",
            description=(
                f"Exception test container: {config.exception_type} after {self._resolved_trigger}"
            ),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            seed=config.seed,
            entity_count=config.entity_count,
            breadcrumbs=[],
        )

        breadcrumbs = [
            Breadcrumb(
                entity_id=container_id,
                name=f"Exception Stub Container (seed={config.seed})",
                entity_type="StubContainerEntity",
            )
        ]

        entities_yielded = 0
        for i in range(config.entity_count - 1):
            # Check if we should trigger the exception
            if entities_yielded >= self._resolved_trigger:
                self.logger.info(
                    f"ExceptionStub: raising {config.exception_type} "
                    f"after {entities_yielded} entities"
                )
                raise self._exception_factories[config.exception_type]()

            # Generate a simple entity
            base_time = datetime(2024, 1, 1) + timedelta(days=i)
            yield SmallStubEntity(
                stub_id=f"exception-stub-{config.seed}-{i}",
                title=f"{rng.choice(ADJECTIVES).capitalize()} {rng.choice(NOUNS)}",
                content=f"Test entity {i} for exception stub (seed={config.seed})",
                author=rng.choice(AUTHORS),
                tags=[rng.choice(NOUNS) for _ in range(2)],
                created_at=base_time,
                modified_at=base_time + timedelta(hours=rng.randint(1, 23)),
                sequence_number=i,
                breadcrumbs=breadcrumbs,
            )
            entities_yielded += 1

        # If we get here, check if we still need to raise (trigger at end of stream)
        if self._resolved_trigger >= config.entity_count:
            # trigger_after >= entity_count — no exception (baseline)
            self.logger.info(
                f"ExceptionStub: completed all {entities_yielded} entities without error (baseline)"
            )
        elif entities_yielded >= self._resolved_trigger:
            self.logger.info(
                f"ExceptionStub: raising {config.exception_type} after {entities_yielded} entities"
            )
            raise self._exception_factories[config.exception_type]()

    async def validate(self) -> None:
        """Validate the source — raises the configured exception type if fail_on_validate is set."""
        if self._config.fail_on_validate:
            raise self._exception_factories[self._config.exception_type]()
