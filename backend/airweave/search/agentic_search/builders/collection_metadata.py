"""Builder for AgenticSearchCollectionMetadata."""

from airweave.search.agentic_search.external.database import AgenticSearchDatabaseInterface
from airweave.search.agentic_search.schemas import (
    AgenticSearchCollectionMetadata,
    AgenticSearchEntityTypeMetadata,
    AgenticSearchSourceMetadata,
)
from airweave.search.agentic_search.schemas.database import AgenticSearchEntityDefinition


class AgenticSearchCollectionMetadataBuilder:
    """Builds AgenticSearchCollectionMetadata from database.

    Orchestrates calls to the database interface to gather all data needed
    to construct the AgenticSearchCollectionMetadata schema.
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
        # Internal sources (used for testing and development)
        "stub": (
            "An internal test data source that generates deterministic synthetic entities "
            "for testing and development purposes."
        ),
    }

    def __init__(self, db: AgenticSearchDatabaseInterface):
        """Initialize with a database interface."""
        self.db = db

    def _get_source_description(self, short_name: str) -> str:
        """Get description for a source by short_name.

        Raises:
            ValueError: If no description found for the source.
        """
        if short_name not in self._SOURCE_DESCRIPTIONS:
            raise ValueError(f"No description found for source: {short_name}")
        return self._SOURCE_DESCRIPTIONS[short_name]

    async def build(self, collection_readable_id: str) -> AgenticSearchCollectionMetadata:
        """Build collection metadata.

        Args:
            collection_readable_id: The readable ID of the collection.

        Returns:
            AgenticSearchCollectionMetadata with all source metadata populated.
        """
        # 1. Get collection
        collection = await self.db.get_collection_by_readable_id(collection_readable_id)

        # 2. Get source connections in collection
        source_connections = await self.db.get_source_connections_in_collection(collection)

        # 3. Build metadata for each source connection
        sources: list[AgenticSearchSourceMetadata] = []
        for source_connection in source_connections:
            # Get source definition
            source = await self.db.get_source_by_short_name(source_connection.short_name)

            # Get entity definitions this source can produce
            entity_definitions = await self.db.get_entity_definitions_of_source(source)

            # Build entity type metadata with fields and counts
            entity_types: list[AgenticSearchEntityTypeMetadata] = []
            for entity_definition in entity_definitions:
                entity_count = await self.db.get_entity_type_count_of_source_connection(
                    source_connection, entity_definition
                )
                fields = self._extract_fields(entity_definition)

                entity_types.append(
                    AgenticSearchEntityTypeMetadata(
                        name=entity_definition.name,
                        count=entity_count.count,
                        fields=fields,
                    )
                )

            sources.append(
                AgenticSearchSourceMetadata(
                    short_name=source_connection.short_name,
                    description=self._get_source_description(source_connection.short_name),
                    entity_types=entity_types,
                )
            )

        return AgenticSearchCollectionMetadata(
            collection_id=str(collection.id),
            collection_readable_id=collection.readable_id,
            sources=sources,
        )

    def _extract_fields(self, entity_definition: AgenticSearchEntityDefinition) -> dict[str, str]:
        """Extract field names and descriptions from entity schema.

        Args:
            entity_definition: Entity definition with schema.

        Returns:
            Dict mapping field names to their descriptions.
        """
        fields: dict[str, str] = {}
        schema = entity_definition.entity_schema

        if not schema or "properties" not in schema:
            return fields

        for field_name, field_info in schema["properties"].items():
            if isinstance(field_info, dict):
                description = field_info.get("description", "No description")
                fields[field_name] = description

        return fields
