"""Asana content generation adapter.

Generates realistic task content for testing Asana integration using LLM.
"""

from typing import List, Tuple

from monke.generation.schemas.asana import AsanaTask
from monke.client.llm import LLMClient


def render_notes(task: AsanaTask) -> str:
    """Render the task content as markdown notes for Asana."""
    content = task.content
    spec = task.spec

    # Build the notes in markdown format
    parts = [
        f"## Task Description\n\n{content.description}",
        f"\n**Verification Token**: {spec.token}",
        "\n### Objectives:",
    ]

    # Add objectives as bullet points
    for obj in content.objectives:
        parts.append(f"- {obj}")

    parts.extend([
        f"\n### Technical Details\n\n{content.technical_details}",
        "\n### Acceptance Criteria:",
    ])

    # Add acceptance criteria as checklist
    for criteria in content.acceptance_criteria:
        parts.append(f"- [ ] {criteria}")

    # Add priority and tags
    parts.extend([
        f"\n### Priority: {spec.priority.title()}",
        f"### Tags: {', '.join(spec.tags) if spec.tags else 'None'}",
    ])

    return "\n".join(parts)


async def generate_asana_task(model: str, token: str) -> Tuple[str, str, List[str]]:
    """Generate task content for Asana testing using LLM.

    Args:
        model: The LLM model to use
        token: A unique token to embed in the content for verification

    Returns:
        Tuple of (title, notes, comments)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a realistic Asana task for a software development project. "
        "The task should be technical but believable, like something from a real sprint. "
        f"You MUST include the literal token '{token}' in the task description and at the beginning of the title and in the comments. "
        "Create meaningful objectives, technical details, and acceptance criteria. "
        "The task should feel like it's part of an ongoing project. "
        "Generate 2-3 helpful comments that a project manager or teammate might add."
    )

    # Generate structured task data
    task = await llm.generate_structured(AsanaTask, instruction)

    # Ensure token is in the task (update if needed)
    task.spec.token = token

    # Also ensure the token appears in the description if it's not already there
    if token not in task.content.description:
        task.content.description += f"\n\n**Debug Token**: {token}"

    # Render the notes
    notes = render_notes(task)

    # Return title, notes, and comments
    return task.spec.title, notes, task.content.comments
