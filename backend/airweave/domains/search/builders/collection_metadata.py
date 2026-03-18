"""Builder for CollectionMetadata using Code Blue DI.

Takes existing Code Blue protocols via constructor injection.
No container imports. No CRUD calls.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.entities.protocols import (
    EntityCountRepositoryProtocol,
    EntityDefinitionRegistryProtocol,
)
from airweave.domains.search.types.metadata import (
    CollectionMetadata,
    EntityTypeMetadata,
    SourceMetadata,
)
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.protocols import SourceRegistryProtocol


class CollectionMetadataBuilder:
    """Builds CollectionMetadata from Code Blue repositories.

    Orchestrates calls to existing domain protocols to gather all data needed
    to construct the CollectionMetadata schema.
    """

    # Source descriptions for LLM context
    _SOURCE_DESCRIPTIONS: dict[str, str] = {
        "airtable": (
            "A cloud platform that blends the ease of a spreadsheet with the power of "
            "a database for organizing data, workflows, and custom apps."
        ),
        "asana": (
            "A work and project management tool for teams to organize, track, and "
            "manage tasks and projects collaboratively."
        ),
        "attio": (
            "A flexible, modern CRM platform that lets businesses build and customize "
            "their customer relationship data model."
        ),
        "bitbucket": (
            "A Git-based code hosting and collaboration tool for teams to manage "
            "repositories, code review, and CI/CD workflows."
        ),
        "box": (
            "A cloud content management and file sharing service that enables secure "
            "storage and collaboration."
        ),
        "clickup": (
            "An all-in-one productivity and project management platform combining "
            "tasks, docs, goals, and calendars."
        ),
        "confluence": (
            "A team collaboration and documentation platform for creating, organizing, "
            "and storing content in a shared workspace."
        ),
        "dropbox": (
            "A cloud storage and file-sync service for storing, sharing, and accessing "
            "files across devices."
        ),
        "excel": (
            "Microsoft's spreadsheet application for organizing, analyzing, and visualizing data."
        ),
        "github": (
            "A platform for hosting Git repositories and collaborating on software "
            "development with version control."
        ),
        "gitlab": (
            "A DevOps platform that offers Git repository management, CI/CD pipelines, "
            "and issue tracking in one application."
        ),
        "gmail": (
            "Google's web-based email service for sending, receiving, and organizing messages."
        ),
        "google_calendar": (
            "Google's online calendar service for scheduling events, reminders, and "
            "managing shared calendars."
        ),
        "google_docs": (
            "Google's web-based document editor for creating and collaborating on text documents."
        ),
        "google_drive": (
            "Google's cloud file storage service for uploading, sharing, and accessing "
            "files from any device."
        ),
        "google_slides": (
            "Google's cloud-based presentation app for creating and collaborating on slide decks."
        ),
        "hubspot": (
            "An integrated CRM platform that centralizes customer data, marketing, "
            "sales, and service tools."
        ),
        "jira": (
            "A project and issue tracking tool used for planning, tracking, and "
            "managing work across teams."
        ),
        "linear": (
            "A streamlined issue tracking and project management tool designed for "
            "fast workflows, especially for engineering teams."
        ),
        "monday": (
            "A visual work operating system for planning, tracking, and automating "
            "team projects and workflows."
        ),
        "notion": (
            "An all-in-one workspace for notes, docs, databases, and task management "
            "that teams can tailor to their needs."
        ),
        "onedrive": (
            "Microsoft's cloud storage service for syncing and sharing files across devices."
        ),
        "onenote": (
            "Microsoft's digital notebook app for capturing and organizing handwritten "
            "and typed notes."
        ),
        "outlook_calendar": (
            "Microsoft's calendar service integrated into Outlook for scheduling "
            "events and appointments."
        ),
        "outlook_mail": (
            "Microsoft's email service within Outlook for sending and receiving "
            "messages with calendar and contact integration."
        ),
        "pipedrive": (
            "A cloud-based sales CRM tool focused on pipeline management and "
            "automating sales processes."
        ),
        "sales_force": (
            "A leading enterprise CRM platform for managing sales, marketing, service, "
            "and customer data at scale."
        ),
        "sharepoint": (
            "Microsoft's content management and intranet platform for storing, "
            "organizing, and sharing information."
        ),
        "shopify": (
            "An e-commerce platform for building online stores and managing products, "
            "payments, and orders."
        ),
        "slack": (
            "A team communication platform featuring channels, direct messages, and "
            "integrations for real-time collaboration."
        ),
        "snapshot": "Snapshot source that generates data from ARF, simulating the source.",
        "stripe": (
            "An online payments platform for processing transactions and managing "
            "financial infrastructure."
        ),
        "teams": (
            "Microsoft Teams, a unified communication platform with chat, meetings, "
            "calls, and file collaboration."
        ),
        "todoist": (
            "A task management app for creating, organizing, and tracking personal and team to-dos."
        ),
        "trello": (
            "A visual project management tool using boards and cards to organize "
            "tasks and workflows."
        ),
        "word": (
            "Microsoft Word, a word processing application for creating and editing text documents."
        ),
        "zendesk": (
            "A customer support platform with ticketing and help desk tools to manage "
            "and respond to inquiries."
        ),
        "zoho_crm": (
            "A cloud-based CRM application for managing sales processes, marketing "
            "activities, and customer support."
        ),
        # Enron email corpus
        "enron": (
            "The Enron Email Dataset (CMU corpus) — over 500,000 real corporate emails "
            "from Enron employees, including internal communications, meeting scheduling, "
            "project discussions, and business operations."
        ),
        # HERB benchmark sources
        "herb_code_review": (
            "GitHub pull requests and code reviews from the HERB benchmark dataset, "
            "including PR summaries, review comments, and merge status."
        ),
        "herb_documents": (
            "Internal documents (PRDs, vision docs, system designs, market research reports) "
            "from the HERB benchmark dataset."
        ),
        "herb_meetings": (
            "Meeting transcripts and chat logs from the HERB benchmark dataset, "
            "including participant names and dialogue."
        ),
        "herb_messaging": (
            "Slack messages from the HERB benchmark dataset, including channel context "
            "and sender information."
        ),
        "herb_people": (
            "Employee and customer records from the HERB benchmark dataset, "
            "including roles, locations, and organizational data."
        ),
        "herb_resources": (
            "Shared URLs and bookmarks from the HERB benchmark dataset, "
            "including descriptions and links."
        ),
        # Internal sources (used for testing and development)
        "stub": (
            "An internal test data source that generates deterministic synthetic entities "
            "for testing and development purposes."
        ),
    }

    def __init__(
        self,
        collection_repo: CollectionRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        source_registry: SourceRegistryProtocol,
        entity_definition_registry: EntityDefinitionRegistryProtocol,
        entity_count_repo: EntityCountRepositoryProtocol,
    ) -> None:
        """Initialize with repository and registry dependencies."""
        self._collection_repo = collection_repo
        self._sc_repo = sc_repo
        self._source_registry = source_registry
        self._entity_definition_registry = entity_definition_registry
        self._entity_count_repo = entity_count_repo

    def _get_source_description(self, short_name: str) -> str:
        """Get description for a source by short_name."""
        if short_name not in self._SOURCE_DESCRIPTIONS:
            raise ValueError(f"No description found for source: {short_name}")
        return self._SOURCE_DESCRIPTIONS[short_name]

    async def build(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: str,
    ) -> CollectionMetadata:
        """Build collection metadata.

        Args:
            db: Database session (passed at call time, not constructor).
            ctx: API context for org scoping.
            collection_readable_id: The readable ID of the collection.

        Returns:
            CollectionMetadata with all source metadata populated.
        """
        # 1. Get collection
        collection = await self._collection_repo.get_by_readable_id(db, collection_readable_id, ctx)
        if not collection:
            raise ValueError(f"Collection not found: {collection_readable_id}")

        # 2. Get source connections in collection
        source_connections = await self._sc_repo.get_by_collection_ids(
            db,
            organization_id=ctx.organization.id,
            readable_collection_ids=[collection_readable_id],
        )

        # 3. Build metadata for each source connection
        sources: list[SourceMetadata] = []
        for sc in source_connections:
            # Get entity definitions this source can produce (in-memory, sync)
            entity_definitions = self._entity_definition_registry.list_for_source(sc.short_name)

            # Get entity counts for this source connection's sync
            counts_by_short_name: dict[str, int] = {}
            if sc.sync_id:
                entity_counts = await self._entity_count_repo.get_counts_per_sync_and_type(
                    db, sc.sync_id
                )
                for ec in entity_counts:
                    counts_by_short_name[ec.entity_definition_short_name] = ec.count

            # Build entity type metadata with fields and counts
            entity_types: list[EntityTypeMetadata] = []
            for entity_def in entity_definitions:
                count = counts_by_short_name.get(entity_def.short_name, 0)
                fields = self._extract_fields(entity_def.entity_schema)

                entity_types.append(
                    EntityTypeMetadata(
                        name=entity_def.name,
                        count=count,
                        fields=fields,
                    )
                )

            sources.append(
                SourceMetadata(
                    short_name=sc.short_name,
                    description=self._get_source_description(sc.short_name),
                    entity_types=entity_types,
                )
            )

        return CollectionMetadata(
            collection_id=str(collection.id),
            collection_readable_id=collection_readable_id,
            sources=sources,
        )

    def _extract_fields(self, entity_schema: dict) -> dict[str, str]:
        """Extract field names and descriptions from entity schema.

        Args:
            entity_schema: JSON schema with field names and descriptions.

        Returns:
            Dict mapping field names to their descriptions.
        """
        fields: dict[str, str] = {}

        if not entity_schema or "properties" not in entity_schema:
            return fields

        for field_name, field_info in entity_schema["properties"].items():
            if isinstance(field_info, dict):
                description = field_info.get("description", "No description")
                fields[field_name] = description

        return fields
