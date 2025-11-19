"""Notion content generation."""

from typing import List, Tuple, Dict, Any

from monke.generation.schemas.notion import NotionPage
from monke.client.llm import LLMClient


def render_content_blocks(page: NotionPage) -> List[Dict[str, Any]]:
    """Convert page content into Notion block format."""
    blocks = []

    # Introduction paragraph
    if page.content.introduction:
        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": page.content.introduction}}
                    ]
                },
            }
        )

    # Token callout
    blocks.append(
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {"type": "text", "text": {"content": f"Token: {page.spec.token}"}}
                ],
                "icon": {"emoji": "🔑"},
            },
        }
    )

    # Sections
    for section in page.content.sections:
        blocks.append(
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": section.title}}]
                },
            }
        )

        blocks.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": section.content}}
                    ]
                },
            }
        )

    # Checklist
    if page.content.checklist_items:
        blocks.append(
            {
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "Checklist"}}]
                },
            }
        )

        for item in page.content.checklist_items:
            blocks.append(
                {
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": item}}],
                        "checked": False,
                    },
                }
            )

    return blocks


async def generate_notion_page(
    model: str, token: str, update: bool = False
) -> Tuple[str, List[Dict[str, Any]]]:
    """Generate page content for Notion testing using LLM."""
    llm = LLMClient(model_override=model)

    update_context = " (updated version)" if update else ""

    instruction = (
        f"Generate a concise Notion page for a knowledge base{update_context}. "
        f"You MUST include the literal token '{token}' prominently in the introduction. "
        "Keep it minimal: create exactly 2 sections with brief content (1-2 sentences each), "
        "and exactly 3 checklist items. "
        "This is for testing purposes, so brevity is essential."
    )

    page = await llm.generate_structured(NotionPage, instruction)
    page.spec.token = token

    if token not in page.content.introduction:
        page.content.introduction = (
            f"{page.content.introduction}\n\nReference Token: {token}"
        )

    # Safety: Limit sections and checklist items to avoid Notion's block depth/count limits
    # Notion allows max ~100 blocks per request, but nested structures have tighter limits
    page.content.sections = page.content.sections[:2]  # Max 2 sections
    page.content.checklist_items = page.content.checklist_items[:3]  # Max 3 items

    content_blocks = render_content_blocks(page)

    return page.spec.title, content_blocks
