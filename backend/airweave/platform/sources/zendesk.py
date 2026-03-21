"""Zendesk source implementation for syncing tickets, comments, users, orgs, and attachments."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import ZendeskConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.zendesk import (
    ZendeskAttachmentEntity,
    ZendeskCommentEntity,
    ZendeskOrganizationEntity,
    ZendeskTicketEntity,
    ZendeskUserEntity,
    _parse_dt,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Zendesk",
    short_name="zendesk",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=ZendeskConfig,
    labels=["Customer Support", "CRM"],
    rate_limit_level=RateLimitLevel.ORG,
)
class ZendeskSource(BaseSource):
    """Zendesk source connector integrates with the Zendesk API to extract and synchronize data.

    Connects to your Zendesk instance to sync tickets, comments, users, orgs, and attachments.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ZendeskConfig,
    ) -> ZendeskSource:
        """Create a new Zendesk source."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.subdomain = config.subdomain
        instance.exclude_closed_tickets = config.exclude_closed_tickets
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make an authenticated GET request to the Zendesk API."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Zendesk — attempting token refresh")
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}", "Accept": "application/json"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _generate_organization_entities(
        self,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate organization entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/organizations.json"

        while url:
            response = await self._get(url)

            for org in response.get("organizations", []):
                yield ZendeskOrganizationEntity.from_api(org, subdomain=self.subdomain)

            url = response.get("next_page")

    async def _generate_user_entities(
        self,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate user entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/users.json"

        while url:
            response = await self._get(url)

            for user in response.get("users", []):
                if not user.get("email"):
                    continue

                yield ZendeskUserEntity.from_api(user, subdomain=self.subdomain)

            url = response.get("next_page")

    async def _generate_ticket_entities(
        self,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ticket entities."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"

        while url:
            response = await self._get(url)

            for ticket in response.get("tickets", []):
                if self.exclude_closed_tickets and ticket.get("status") == "closed":
                    continue

                yield ZendeskTicketEntity.from_api(ticket, subdomain=self.subdomain)

            url = response.get("next_page")

    async def _generate_comment_entities(
        self, ticket_id: int, ticket_subject: str, ticket_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a ticket."""
        url = (
            f"https://{self.subdomain}.zendesk.com/api/v2/tickets/"
            f"{ticket_id}/comments.json?include=users"
        )

        try:
            response = await self._get(url)

            users_map: Dict[int, Dict[str, Any]] = {}
            for user in response.get("users", []):
                users_map[user["id"]] = user

            for comment in response.get("comments", []):
                yield ZendeskCommentEntity.from_api(
                    comment,
                    ticket_id=ticket_id,
                    ticket_subject=ticket_subject,
                    ticket_breadcrumb=ticket_breadcrumb,
                    users_map=users_map,
                    subdomain=self.subdomain,
                )
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to fetch comments for ticket {ticket_id}: {e}")

    async def _generate_attachment_entities(  # noqa: C901
        self,
        ticket_id: int,
        ticket_subject: str,
        ticket_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate attachment entities for a ticket."""
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json"

        try:
            response = await self._get(url)

            for comment in response.get("comments", []):
                comment_created_at = _parse_dt(comment.get("created_at"))
                comment_breadcrumb = Breadcrumb(
                    entity_id=str(comment["id"]),
                    name=f"Comment {comment['id']}",
                    entity_type=ZendeskCommentEntity.__name__,
                )

                for attachment in comment.get("attachments", []):
                    if not all(
                        attachment.get(field) for field in ["id", "file_name", "content_url"]
                    ):
                        continue

                    attachment_entity = ZendeskAttachmentEntity.from_api(
                        attachment,
                        ticket_id=ticket_id,
                        ticket_subject=ticket_subject,
                        ticket_breadcrumb=ticket_breadcrumb,
                        comment_breadcrumb=comment_breadcrumb,
                        comment_created_at=comment_created_at,
                        subdomain=self.subdomain,
                    )

                    if files:
                        try:
                            await files.download_from_url(
                                entity=attachment_entity,
                                client=self.http_client,
                                auth=self.auth,
                                logger=self.logger,
                            )

                            if not attachment_entity.local_path:
                                raise ValueError(
                                    f"Download failed - no local path set for "
                                    f"{attachment_entity.name}"
                                )

                            self.logger.debug(
                                f"Successfully downloaded attachment: {attachment_entity.name}"
                            )
                            yield attachment_entity

                        except FileSkippedException as e:
                            self.logger.debug(
                                f"Skipping attachment {attachment_entity.name}: {e.reason}"
                            )
                            continue

                        except SourceAuthError:
                            raise

                        except Exception as e:
                            self.logger.warning(
                                f"Failed to download attachment {attachment_entity.name}: {e}"
                            )
                            continue
                    else:
                        yield attachment_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to fetch attachments for ticket {ticket_id}: {e}")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Zendesk."""
        async for org_entity in self._generate_organization_entities():
            yield org_entity

        async for user_entity in self._generate_user_entities():
            yield user_entity

        async for ticket_entity in self._generate_ticket_entities():
            yield ticket_entity

            ticket_breadcrumb = Breadcrumb(
                entity_id=str(ticket_entity.ticket_id),
                name=ticket_entity.subject,
                entity_type=ZendeskTicketEntity.__name__,
            )

            async for comment_entity in self._generate_comment_entities(
                ticket_id=ticket_entity.ticket_id,
                ticket_subject=ticket_entity.subject,
                ticket_breadcrumb=ticket_breadcrumb,
            ):
                yield comment_entity

            async for attachment_entity in self._generate_attachment_entities(
                ticket_id=ticket_entity.ticket_id,
                ticket_subject=ticket_entity.subject,
                ticket_breadcrumb=ticket_breadcrumb,
                files=files,
            ):
                yield attachment_entity

    async def validate(self) -> None:
        """Validate credentials by pinging Zendesk's /users/me endpoint."""
        await self._get(f"https://{self.subdomain}.zendesk.com/api/v2/users/me.json")
