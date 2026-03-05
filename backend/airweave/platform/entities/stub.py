"""Stub entity schemas for testing purposes.

Provides deterministic, reproducible test entities with various content sizes
and types to simulate real-world data sources.
"""

from datetime import datetime
from typing import Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity


class StubContainerEntity(BaseEntity):
    """Container entity for organizing stub entities.

    Acts as a parent breadcrumb for all generated stub entities,
    similar to how projects/workspaces work in real sources.
    """

    container_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub container",
        is_entity_id=True,
    )
    container_name: str = AirweaveField(
        ...,
        description="Name of the stub container",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of the stub container",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the container was created",
        is_created_at=True,
    )
    seed: int = AirweaveField(
        default=42,
        description="Random seed used for content generation",
        embeddable=False,
    )
    entity_count: int = AirweaveField(
        default=10,
        description="Total number of entities in this container",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the container."""
        return f"stub://container/{self.container_id}"


class SmallStubEntity(BaseEntity):
    """Small stub entity (~100-200 chars).

    Represents: Comments, notes, short messages.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub entity",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Title of the stub entity",
        is_name=True,
        embeddable=True,
    )
    content: str = AirweaveField(
        ...,
        description="Short content text (~100-200 chars)",
        embeddable=True,
    )
    author: str = AirweaveField(
        default="",
        description="Author of the content",
        embeddable=True,
    )
    tags: list[str] = AirweaveField(
        default_factory=list,
        description="Tags associated with this entity",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the entity."""
        return f"stub://entity/small/{self.stub_id}"


class MediumStubEntity(BaseEntity):
    """Medium stub entity (~500-1000 chars).

    Represents: Tasks, pages, documents.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub entity",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Title of the stub entity",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        ...,
        description="Detailed description (~500-1000 chars)",
        embeddable=True,
    )
    status: str = AirweaveField(
        default="active",
        description="Status of the entity",
        embeddable=True,
    )
    priority: str = AirweaveField(
        default="normal",
        description="Priority level",
        embeddable=True,
    )
    assignee: str = AirweaveField(
        default="",
        description="Person assigned to this entity",
        embeddable=True,
    )
    tags: list[str] = AirweaveField(
        default_factory=list,
        description="Tags associated with this entity",
        embeddable=True,
    )
    notes: str = AirweaveField(
        default="",
        description="Additional notes",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was last modified",
        is_updated_at=True,
    )
    due_date: Optional[datetime] = AirweaveField(
        None,
        description="Due date for the entity",
        embeddable=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the entity."""
        return f"stub://entity/medium/{self.stub_id}"


class LargeStubEntity(BaseEntity):
    """Large stub entity (~3000-5000 chars).

    Represents: Long articles, wikis, rich content.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub entity",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Title of the stub entity",
        is_name=True,
        embeddable=True,
    )
    summary: str = AirweaveField(
        ...,
        description="Brief summary of the content",
        embeddable=True,
    )
    content: str = AirweaveField(
        ...,
        description="Full content text (~3000-5000 chars)",
        embeddable=True,
    )
    author: str = AirweaveField(
        default="",
        description="Author of the content",
        embeddable=True,
    )
    category: str = AirweaveField(
        default="general",
        description="Category of the content",
        embeddable=True,
    )
    tags: list[str] = AirweaveField(
        default_factory=list,
        description="Tags associated with this entity",
        embeddable=True,
    )
    sections: list[str] = AirweaveField(
        default_factory=list,
        description="Section headings in the content",
        embeddable=True,
    )
    references: list[str] = AirweaveField(
        default_factory=list,
        description="References cited in the content",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the entity was last modified",
        is_updated_at=True,
    )
    published_at: Optional[datetime] = AirweaveField(
        None,
        description="When the content was published",
        embeddable=True,
    )
    word_count: int = AirweaveField(
        default=0,
        description="Word count of the content",
        embeddable=False,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the entity."""
        return f"stub://entity/large/{self.stub_id}"


class SmallStubFileEntity(FileEntity):
    """Small stub file entity (~1-5 KB).

    Represents: Small text files, config files.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub file",
        is_entity_id=True,
    )
    file_name: str = AirweaveField(
        ...,
        description="Name of the file",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of the file contents",
        embeddable=True,
    )
    file_extension: str = AirweaveField(
        default=".txt",
        description="File extension",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the file."""
        return f"stub://file/small/{self.stub_id}"


class LargeStubFileEntity(FileEntity):
    """Large stub file entity (~50-100 KB).

    Represents: PDFs, larger documents, reports.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub file",
        is_entity_id=True,
    )
    file_name: str = AirweaveField(
        ...,
        description="Name of the file",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of the file contents",
        embeddable=True,
    )
    file_extension: str = AirweaveField(
        default=".txt",
        description="File extension",
        embeddable=True,
    )
    summary: str = AirweaveField(
        default="",
        description="Summary of the document",
        embeddable=True,
    )
    author: str = AirweaveField(
        default="",
        description="Author of the document",
        embeddable=True,
    )
    category: str = AirweaveField(
        default="document",
        description="Category of the document",
        embeddable=True,
    )
    page_count: int = AirweaveField(
        default=1,
        description="Estimated page count",
        embeddable=False,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the file."""
        return f"stub://file/large/{self.stub_id}"


class PdfStubFileEntity(FileEntity):
    """PDF stub file entity (~5-20 KB).

    Represents: PDF documents with extractable text content.
    Generated as real binary PDF files using fpdf2.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub PDF file",
        is_entity_id=True,
    )
    file_name: str = AirweaveField(
        ...,
        description="Name of the PDF file",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of the PDF contents",
        embeddable=True,
    )
    file_extension: str = AirweaveField(
        default=".pdf",
        description="File extension",
        embeddable=True,
    )
    summary: str = AirweaveField(
        default="",
        description="Summary of the document",
        embeddable=True,
    )
    author: str = AirweaveField(
        default="",
        description="Author of the document",
        embeddable=True,
    )
    page_count: int = AirweaveField(
        default=1,
        description="Number of pages in the PDF",
        embeddable=False,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the PDF file."""
        return f"stub://file/pdf/{self.stub_id}"


class PptxStubFileEntity(FileEntity):
    """PPTX stub file entity (~10-30 KB).

    Represents: PowerPoint presentations with extractable text content.
    Generated as real binary PPTX files using python-pptx.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub PPTX file",
        is_entity_id=True,
    )
    file_name: str = AirweaveField(
        ...,
        description="Name of the PPTX file",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of the presentation contents",
        embeddable=True,
    )
    file_extension: str = AirweaveField(
        default=".pptx",
        description="File extension",
        embeddable=True,
    )
    summary: str = AirweaveField(
        default="",
        description="Summary of the presentation",
        embeddable=True,
    )
    author: str = AirweaveField(
        default="",
        description="Author of the presentation",
        embeddable=True,
    )
    slide_count: int = AirweaveField(
        default=1,
        description="Number of slides in the presentation",
        embeddable=False,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the PPTX file."""
        return f"stub://file/pptx/{self.stub_id}"


class CodeStubFileEntity(CodeFileEntity):
    """Code stub file entity (~2-10 KB).

    Represents: Python, JavaScript, and other source code files.
    """

    stub_id: str = AirweaveField(
        ...,
        description="Unique identifier for the stub code file",
        is_entity_id=True,
    )
    file_name: str = AirweaveField(
        ...,
        description="Name of the code file",
        is_name=True,
        embeddable=True,
    )
    description: str = AirweaveField(
        default="",
        description="Description of what the code does",
        embeddable=True,
    )
    functions: list[str] = AirweaveField(
        default_factory=list,
        description="Function names defined in the file",
        embeddable=True,
    )
    classes: list[str] = AirweaveField(
        default_factory=list,
        description="Class names defined in the file",
        embeddable=True,
    )
    imports: list[str] = AirweaveField(
        default_factory=list,
        description="Import statements in the file",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was created",
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the file was last modified",
        is_updated_at=True,
    )
    sequence_number: int = AirweaveField(
        default=0,
        description="Sequence number for ordering",
        embeddable=False,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Placeholder URL for the code file."""
        return f"stub://file/code/{self.stub_id}"
