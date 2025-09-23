"""GitHub-specific generation adapter: artifact generator + renderer + slug."""

import re
import json
from typing import Tuple

from monke.generation.schemas.github import GitHubArtifact
from monke.client.llm import LLMClient


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\-\s]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def render_body(artifact: GitHubArtifact) -> str:
    common = artifact.common
    if artifact.type == "markdown":
        parts = [f"# {common.title}", common.summary, f"Token: {common.token}"]
        parts += [
            f"## {s.heading}\n\n{s.body}"
            for s in artifact.content.sections  # type: ignore[attr-defined]
        ]
        return "\n\n".join(parts)
    if artifact.type == "python":
        fns = "\n\n".join(s.body for s in artifact.content.functions)  # type: ignore[attr-defined]
        classes = "\n\n".join(s.body for s in artifact.content.classes)  # type: ignore[attr-defined]
        return f'"""{common.summary} | token={common.token}"""\n\n{fns}\n\n{classes}\n'
    c = artifact.content  # type: ignore[assignment]
    # Convert KVPair lists to dicts
    metadata = {kv.key: kv.value for kv in getattr(c, "metadata", [])}
    metadata.update({"token": common.token, "created_at": common.created_at})
    body = {
        "title": common.title,
        "summary": common.summary,
        "attributes": {kv.key: kv.value for kv in getattr(c, "attributes", [])},
        "metadata": metadata,
    }
    return json.dumps(body, indent=2)


async def generate_github_artifact(
    file_type: str, model: str, token: str
) -> Tuple[str, str]:
    """Generate a GitHub artifact via LLM and render to text.

    Returns (title, body). The token must be embedded in the output by instruction.
    """
    llm = LLMClient(model_override=model)

    instructions = {
        "markdown": (
            "You are generating a markdown document for a test GitHub repo. "
            "Create a playful, synthetic summary of today's world news. "
            "Include the literal token '{token}' somewhere in the body. "
            "Avoid factual claims; keep it synthetic."
        ),
        "python": (
            "Generate a small Python module with one simple function and one simple class. "
            "Include the literal token '{token}' in a docstring or string constant."
        ),
        "json": (
            "Generate a compact JSON changelog-like entry with title, summary, attributes, and metadata. "
            "Ensure metadata includes the literal token '{token}'."
        ),
    }

    instruction = f"Type: {file_type}\n" + instructions[file_type].format(token=token)
    artifact = await llm.generate_structured(GitHubArtifact, instruction)
    body = render_body(artifact)
    title = artifact.common.title
    return title, body
