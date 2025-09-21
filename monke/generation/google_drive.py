"""Google Drive-specific generation adapter: file content generator."""

from typing import Tuple

from monke.generation.schemas.google_drive import GoogleDriveArtifact
from monke.client.llm import LLMClient


def get_mime_type(file_type: str) -> str:
    """Get MIME type for a given file type."""
    mime_types = {
        "document": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "pdf": "application/pdf",
        "text": "text/plain",
        "markdown": "text/markdown",
    }
    return mime_types.get(file_type, "text/plain")


def get_media_content_type(file_type: str, target_mime: str) -> str:
    """
    Content-Type of the *media bytes* you upload.
    For Google-native targets we must upload something importable.
    """
    if target_mime == "application/vnd.google-apps.document":
        # Upload text (or HTML) that Docs can import.
        return "text/plain"  # or "text/html"
    if target_mime == "application/vnd.google-apps.spreadsheet":
        # Upload CSV so Sheets can import to a Sheet.
        return "text/csv"

    # Non-Google-native: just use the file's own content type.
    # (If you don't know, text/plain is fine for your generated strings.)
    fallback_by_type = {
        "pdf": "application/pdf",
        "text": "text/plain",
        "markdown": "text/markdown",
    }
    return fallback_by_type.get(file_type, target_mime or "application/octet-stream")


def render_body(artifact: GoogleDriveArtifact, file_type: str) -> str:
    """Render the artifact body based on file type."""
    if file_type == "spreadsheet":
        # For spreadsheets, create CSV-like content
        rows = [
            "Title,Description,Token,Created",
            f'"{artifact.title}","{artifact.description}","{artifact.token}","{artifact.created_at}"',
        ]
        if hasattr(artifact, "rows") and artifact.rows:
            rows.extend(artifact.rows)
        return "\n".join(rows)
    elif file_type == "pdf":
        # For PDFs, we'll just use plain text (the API will handle conversion)
        return f"{artifact.title}\n\n{artifact.description}\n\nToken: {artifact.token}"
    else:
        # For documents and text files
        parts = [f"# {artifact.title}", artifact.description, f"Token: {artifact.token}"]
        if hasattr(artifact, "sections") and artifact.sections:
            parts.extend(
                [f"\n## {s.get('heading', '')}\n{s.get('body', '')}" for s in artifact.sections]
            )
        return "\n\n".join(parts)


async def generate_google_drive_artifact(
    file_type: str, model: str, token: str, is_update: bool = False
) -> Tuple[str, str, str]:
    """Generate a Google Drive file via LLM.

    Returns (title, content, mime_type). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model if model else None)

    instructions = {
        "document": (
            "Generate a Google Docs document about a synthetic tech product review. "
            "Include the literal token '{token}' somewhere in the content. "
            "Keep it informative but synthetic."
        ),
        "spreadsheet": (
            "Generate data for a Google Sheets spreadsheet tracking synthetic project milestones. "
            "Include the literal token '{token}' in one of the data rows. "
            "Create CSV-formatted data with headers and at least 3 data rows."
        ),
        "pdf": (
            "Generate content for a PDF report about synthetic quarterly results. "
            "Include the literal token '{token}' somewhere in the content. "
            "Keep it professional but synthetic."
        ),
        "text": (
            "Generate a plain text file with meeting notes from a synthetic tech planning session. "
            "Include the literal token '{token}' somewhere in the content."
        ),
        "markdown": (
            "Generate a markdown file documenting a synthetic API specification. "
            "Include the literal token '{token}' somewhere in the content. "
            "Use proper markdown formatting."
        ),
    }

    if is_update:
        instruction = f"Type: {file_type} (UPDATED VERSION)\n" + instructions.get(
            file_type, instructions["text"]
        ).format(token=token)
    else:
        instruction = f"Type: {file_type}\n" + instructions.get(
            file_type, instructions["text"]
        ).format(token=token)

    artifact = await llm.generate_structured(GoogleDriveArtifact, instruction)

    # Ensure token is in artifact
    if token not in artifact.description:
        artifact.description += f"\n\nReference: {token}"

    content = render_body(artifact, file_type)
    mime_type = get_mime_type(file_type)

    return artifact.title, content, mime_type
