"""Collection info utilities for agentic search."""

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.models.entity_count import EntityCount
from airweave.models.entity_definition import EntityDefinition


class CollectionInfoError(Exception):
    """Error raised when collection info is missing or incomplete."""

    pass


class CollectionInfoBuilder:
    """Builds collection info for LLM context in agentic search.

    This class gathers information about a collection's sources, entity definitions,
    and entity counts, then formats it as markdown for LLM consumption.

    Usage:
        builder = CollectionInfoBuilder(db, ctx)
        markdown = await builder.build_markdown(readable_collection_id)
    """

    _SOURCE_DESCRIPTIONS: Dict[str, str] = {
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
        "snapshot": ("Snapshot source that generates data from ARF, simulating the source."),
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
    }

    def __init__(self, db: AsyncSession, ctx: ApiContext) -> None:
        """Initialize the collection info builder.

        Args:
            db: Database session
            ctx: API context for organization scoping
        """
        self._db = db
        self._ctx = ctx

    async def build_markdown(self, readable_collection_id: str) -> str:
        """Build a markdown string with collection info for LLM context.

        This is the main public method that orchestrates gathering all collection
        information and formatting it as markdown.

        Args:
            readable_collection_id: The collection's readable ID

        Returns:
            Markdown-formatted string with sources, entity definitions, and counts.

        Raises:
            CollectionInfoError: If any required info is missing.
        """
        source_short_names = await self._get_source_short_names(readable_collection_id)
        entity_counts = await self._get_entity_counts(readable_collection_id)

        # Note: This markdown is embedded inside "### Collection Info" in the prompt,
        # so we use #### and ##### for proper nesting
        lines = [f"**Collection:** `{readable_collection_id}`", ""]

        for short_name in sorted(source_short_names):
            description = self._get_source_description(short_name)
            lines.append(f"#### {short_name}")
            lines.append(f"{description}")
            lines.append("")

            entity_defs = await self._get_entity_definitions(short_name)

            for entity_def in entity_defs:
                entity_name = entity_def["name"]
                count = entity_counts.get(entity_name, 0)

                lines.append(f"##### {entity_name} ({count} entities)")
                lines.append("")
                lines.append("| Field | Description |")
                lines.append("|-------|-------------|")

                for field_name, field_desc in sorted(entity_def["fields"].items()):
                    escaped_desc = field_desc.replace("|", "\\|")
                    lines.append(f"| {field_name} | {escaped_desc} |")

                lines.append("")

        return "\n".join(lines)

    async def _get_source_short_names(self, readable_collection_id: str) -> List[str]:
        """Get all unique source short names for a collection.

        Args:
            readable_collection_id: The collection's readable ID

        Returns:
            List of unique source short names (e.g., ["notion", "slack", "github"])

        Raises:
            CollectionInfoError: If no source connections found for the collection
        """
        source_connections = await crud.source_connection.get_for_collection(
            self._db,
            readable_collection_id=readable_collection_id,
            ctx=self._ctx,
        )

        if not source_connections:
            raise CollectionInfoError(
                f"No source connections found for collection: {readable_collection_id}"
            )

        short_names = list({sc.short_name for sc in source_connections})

        if not short_names:
            raise CollectionInfoError(
                f"No source short names found for collection: {readable_collection_id}"
            )

        return short_names

    def _get_source_description(self, short_name: str) -> str:
        """Get a human-readable description for a source.

        Args:
            short_name: The source's short name (e.g., "notion", "slack")

        Returns:
            Description of the source.

        Raises:
            CollectionInfoError: If no description found for the source
        """
        if short_name not in self._SOURCE_DESCRIPTIONS:
            raise CollectionInfoError(f"No description found for source: {short_name}")

        return self._SOURCE_DESCRIPTIONS[short_name]

    async def _get_entity_definitions(self, source_short_name: str) -> List[Dict[str, Any]]:
        """Get entity definitions for a source with field info.

        Args:
            source_short_name: The source's short name (e.g., "notion", "slack")

        Returns:
            List of entity definitions, each containing:
            - name: Entity class name (e.g., "NotionPageEntity")
            - fields: Dict of field_name -> field_description

        Raises:
            CollectionInfoError: If no entity definitions found, or if schema is missing
        """
        entity_defs = await crud.entity_definition.get_multi_by_source_short_name(
            self._db, source_short_name=source_short_name
        )

        if not entity_defs:
            raise CollectionInfoError(
                f"No entity definitions found for source: {source_short_name}"
            )

        result = []
        for entity_def in entity_defs:
            if not entity_def.entity_schema:
                raise CollectionInfoError(f"Entity definition '{entity_def.name}' has no schema")

            if "properties" not in entity_def.entity_schema:
                raise CollectionInfoError(
                    f"Entity definition '{entity_def.name}' schema has no properties"
                )

            fields = {}
            for field_name, field_info in entity_def.entity_schema["properties"].items():
                if not isinstance(field_info, dict):
                    raise CollectionInfoError(
                        f"Entity '{entity_def.name}' field '{field_name}' has invalid schema"
                    )

                description = field_info.get("description")
                if not description:
                    raise CollectionInfoError(
                        f"Entity '{entity_def.name}' field '{field_name}' has no description"
                    )

                fields[field_name] = description

            if not fields:
                raise CollectionInfoError(f"Entity definition '{entity_def.name}' has no fields")

            result.append(
                {
                    "name": entity_def.name,
                    "fields": fields,
                }
            )

        return result

    async def _get_entity_counts(self, readable_collection_id: str) -> Dict[str, int]:
        """Get entity counts per entity definition for a collection.

        Args:
            readable_collection_id: The collection's readable ID

        Returns:
            Dict mapping entity_definition_name -> count
            (e.g., {"NotionPageEntity": 150, "NotionDatabaseEntity": 10})

        Raises:
            CollectionInfoError: If no source connections, sync_ids, or entity counts found
        """
        source_connections = await crud.source_connection.get_for_collection(
            self._db,
            readable_collection_id=readable_collection_id,
            ctx=self._ctx,
        )

        if not source_connections:
            raise CollectionInfoError(
                f"No source connections found for collection: {readable_collection_id}"
            )

        sync_ids: List[UUID] = [sc.sync_id for sc in source_connections if sc.sync_id]

        if not sync_ids:
            raise CollectionInfoError(
                f"No sync_ids found for collection: {readable_collection_id}. "
                "Source connections may not have been synced yet."
            )

        query = (
            select(
                EntityDefinition.name,
                func.sum(EntityCount.count).label("total"),
            )
            .join(EntityDefinition, EntityCount.entity_definition_id == EntityDefinition.id)
            .where(EntityCount.sync_id.in_(sync_ids))
            .group_by(EntityDefinition.name)
        )

        result = await self._db.execute(query)
        counts = {row.name: row.total for row in result.all()}

        if not counts:
            raise CollectionInfoError(
                f"No entity counts found for collection: {readable_collection_id}. "
                "The collection may not have been synced yet."
            )

        return counts
