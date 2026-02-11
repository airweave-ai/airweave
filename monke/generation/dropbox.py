"""Dropbox-specific generation adapter: file content generator."""

from typing import Tuple

from monke.generation.schemas.dropbox import DropboxArtifact
from monke.client.llm import LLMClient


def render_body(artifact: DropboxArtifact, file_type: str) -> str:
    """Render the artifact body based on file type."""
    if file_type == "json":
        import json
        data = {
            "title": artifact.title,
            "description": artifact.description,
            "token": artifact.token,
            "created_at": artifact.created_at.isoformat(),
            "metadata": getattr(artifact, "metadata", {})
        }
        return json.dumps(data, indent=2)
    elif file_type == "yaml":
        # Create YAML content
        lines = [
            f"title: {artifact.title}",
            f"description: {artifact.description}",
            f"token: {artifact.token}",
            f"created_at: {artifact.created_at.isoformat()}",
        ]
        if hasattr(artifact, 'metadata') and artifact.metadata:
            lines.append("metadata:")
            for key, value in artifact.metadata.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)
    else:
        # For markdown and text files
        parts = [f"# {artifact.title}", artifact.description, f"Token: {artifact.token}"]
        if hasattr(artifact, 'sections') and artifact.sections:
            parts.extend([f"\n## {s.get('heading', '')}\n{s.get('body', '')}" for s in artifact.sections])
        return "\n\n".join(parts)


async def generate_dropbox_artifact(
    file_type: str, model: str, token: str, is_update: bool = False
) -> Tuple[str, str]:
    """Generate a Dropbox file via LLM.

    Returns (title, content). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model)

    instructions = {
        "markdown": (
            "Generate a markdown document about a synthetic cloud storage best practices guide. "
            "Include the literal token '{token}' somewhere in the content. "
            "Use proper markdown formatting with sections."
        ),
        "text": (
            "Generate a plain text file with notes from a synthetic product planning meeting. "
            "Include the literal token '{token}' somewhere in the content."
        ),
        "json": (
            "Generate a JSON configuration file for a synthetic application. "
            "Include the literal token '{token}' in the metadata. "
            "Include relevant configuration options."
        ),
        "yaml": (
            "Generate a YAML configuration for a synthetic deployment pipeline. "
            "Include the literal token '{token}' somewhere in the configuration. "
            "Use proper YAML formatting."
        )
    }

    if is_update:
        instruction = f"Type: {file_type} (UPDATED VERSION)\n" + instructions.get(file_type, instructions["text"]).format(token=token)
    else:
        instruction = f"Type: {file_type}\n" + instructions.get(file_type, instructions["text"]).format(token=token)

    artifact = await llm.generate_structured(DropboxArtifact, instruction)

    # Ensure token is in artifact
    if token not in str(artifact.dict()):
        artifact.token = token

    content = render_body(artifact, file_type)

    return artifact.title, content
