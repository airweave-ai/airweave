"""Notion content generation."""

from typing import List, Tuple, Dict, Any

from monke.generation.schemas.notion import NotionPage
from monke.client.llm import LLMClient


def render_content_blocks(page: NotionPage) -> List[Dict[str, Any]]:
    """Convert page content into Notion block format."""
    blocks = []

    # Introduction paragraph
    if page.content.introduction:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": page.content.introduction}}]
            }
        })

    # Token callout
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": f"Token: {page.spec.token}"}}],
            "icon": {"emoji": "🔑"}
        }
    })

    # Sections
    for section in page.content.sections:
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": section.title}}]
            }
        })

        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": section.content}}]
            }
        })

    # Checklist
    if page.content.checklist_items:
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "Checklist"}}]
            }
        })

        for item in page.content.checklist_items:
            blocks.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": item}}],
                    "checked": False
                }
            })

    return blocks


async def generate_notion_page(
    model: str,
    token: str,
    update: bool = False
) -> Tuple[str, List[Dict[str, Any]]]:
    """Generate page content for Notion testing using LLM."""
    llm = LLMClient(model_override=model if model else None)

    update_context = " (updated version)" if update else ""

    instruction = (
        f"Generate a realistic Notion page for a knowledge base{update_context}. "
        f"You MUST include the literal token '{token}' prominently. "
        "Create meaningful sections and checklist items."
    )

    page = await llm.generate_structured(NotionPage, instruction)
    page.spec.token = token

    if token not in page.content.introduction:
        page.content.introduction = f"{page.content.introduction}\n\nReference Token: {token}"

    content_blocks = render_content_blocks(page)

    return page.spec.title, content_blocks
