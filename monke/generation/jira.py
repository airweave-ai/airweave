"""Jira-specific generation adapter: issue and comment generator."""

from typing import List, Tuple

from monke.generation.schemas.jira import (
    JiraIssueArtifact,
    JiraCommentArtifact,
    JiraEpicArtifact
)
from monke.client.llm import LLMClient


async def generate_jira_issue(
    model: str,
    token: str,
    is_update: bool = False,
    issue_type: str = "Task"
) -> Tuple[str, str, str, List[str], bool, int]:
    """Generate a Jira issue via LLM with rich metadata.

    Returns:
        (summary, description, issue_type, labels, should_have_comments, num_comments)
        The token must be embedded in the description.
    """
    llm = LLMClient(model_override=model)

    if is_update:
        instruction = (
            "You are generating an UPDATED Jira issue for testing. "
            "Create an update to a synthetic software development task with realistic changes. "
            f"Include the literal token '{token}' somewhere in the description. "
            "Add 2-4 relevant labels (e.g., 'backend', 'api', 'bug-fix', 'enhancement'). "
            "Indicate if this issue should have comments (e.g., for bugs or complex tasks). "
            "Keep it professional and realistic."
        )
    else:
        instruction = (
            "You are generating a Jira issue for testing. "
            "Create a synthetic software development task, bug report, or story. "
            f"Include the literal token '{token}' somewhere in the description. "
            "Add 2-4 relevant labels (e.g., 'frontend', 'database', 'performance', 'security'). "
            "Indicate if this issue should have comments (typically for bugs or complex tasks). "
            "Set assignee_needed=true for ~50% of issues. "
            "Keep it professional and realistic."
        )

    artifact = await llm.generate_structured(JiraIssueArtifact, instruction)

    # Add token to description if not already present
    description = artifact.description
    if token not in description:
        description += f"\n\nReference: {token}"

    return (
        artifact.summary,
        description,
        artifact.issue_type,
        artifact.labels or [],
        artifact.should_have_comments,
        artifact.num_comments if artifact.should_have_comments else 0
    )


async def generate_jira_comments(
    model: str,
    token: str,
    issue_summary: str,
    num_comments: int = 2
) -> List[str]:
    """Generate comments for a Jira issue.

    Args:
        model: LLM model to use
        token: Unique token to embed in at least one comment
        issue_summary: The issue summary for context
        num_comments: Number of comments to generate

    Returns:
        List of comment body texts
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate {num_comments} realistic comments for a Jira issue titled '{issue_summary}'. "
        f"Include the token '{token}' in at least ONE comment. "
        "Comments should be professional developer discussions about the issue: "
        "questions, clarifications, status updates, or technical details. "
        "Each comment should be 1-3 sentences."
    )

    comments = []
    for i in range(num_comments):
        comment_instruction = f"{instruction}\n\nComment {i+1} of {num_comments}:"
        artifact = await llm.generate_structured(JiraCommentArtifact, comment_instruction)
        comments.append(artifact.body)

    # Ensure token appears in at least one comment
    if not any(token in comment for comment in comments):
        comments[0] += f"\n\nRef: {token}"

    return comments


async def generate_jira_epic(
    model: str,
    token: str
) -> Tuple[str, str, List[str]]:
    """Generate a Jira epic.

    Returns:
        (summary, description, labels)
    """
    llm = LLMClient(model_override=model)

    instruction = (
        "Generate a Jira Epic for testing. "
        "Create a high-level feature or initiative for a software project. "
        f"Include the token '{token}' in the description. "
        "Add 2-3 relevant labels. "
        "Keep it professional and realistic."
    )

    artifact = await llm.generate_structured(JiraEpicArtifact, instruction)

    # Add token to description if not present
    description = artifact.description
    if token not in description:
        description += f"\n\nEpic Reference: {token}"

    return artifact.summary, description, artifact.labels or []


# Backwards compatibility
async def generate_jira_artifact(
    model: str,
    token: str,
    is_update: bool = False
) -> Tuple[str, str, str]:
    """Legacy function for backwards compatibility.

    Returns (summary, description, issue_type).
    """
    summary, description, issue_type, _, _, _ = await generate_jira_issue(
        model, token, is_update
    )
    return summary, description, issue_type
