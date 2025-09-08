from monke.client.llm import LLMClient
from monke.generation.schemas.linear import LinearIssue


async def generate_linear_issue(model: str, token: str) -> LinearIssue:
    """
    Generate a realistic software/dev work item.
    Token MUST appear at the start of the title and inside the description/comments.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Create a realistic engineering issue for a modern web service. "
        f"Start the title with the literal token '{token}' and include it in the description and at least one comment. "
        "Include reproduction steps and expected vs. actual behavior."
    )
    issue = await llm.generate_structured(LinearIssue, instruction)
    issue.spec.token = token
    if not issue.spec.title.startswith(token):
        issue.spec.title = f"{token} {issue.spec.title}"
    if token not in issue.content.description:
        issue.content.description += f"\n\nToken: {token}"
    if issue.content.comments and token not in issue.content.comments[0]:
        issue.content.comments[0] = f"{token} — " + issue.content.comments[0]
    return issue
