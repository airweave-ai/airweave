"""Slab content generation for Monke E2E tests."""

import json
from typing import Dict

from monke.client.llm import LLMClient
from monke.generation.schemas.slab import SlabPostContent, SlabTopicContent


async def generate_slab_topic(model: str, token: str) -> Dict:
    """Generate topic name and description with embedded token.

    Returns:
        Dict with name, description for createTopic mutation.
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a short, realistic name and optional description for a team wiki topic "
        "(e.g. Engineering, Onboarding, API Docs). "
        f"You MUST include the literal token '{token}' in the name or description. "
        "Return a concise topic name and one sentence description."
    )
    topic = await llm.generate_structured(SlabTopicContent, instruction)
    if token not in topic.name and token not in topic.description:
        topic.description = (topic.description or "").strip() + f" Verification: {token}"
    return {"name": topic.name, "description": topic.description or None}


async def generate_slab_post(model: str, token: str) -> Dict:
    """Generate post title and body with embedded token.

    Returns:
        Dict with title, body_plain (for converting to Quill delta).
    """
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a short wiki post: a title and a 1–2 sentence body. "
        f"You MUST include the literal token '{token}' in the title or body. "
        "Keep it professional and documentation-style."
    )
    post = await llm.generate_structured(SlabPostContent, instruction)
    if token not in post.title and token not in post.body_plain:
        post.body_plain = (post.body_plain or "").strip() + f" Token: {token}."
    return {"title": post.title, "body_plain": post.body_plain or ""}


def plain_text_to_quill_delta(text: str):
    """Convert plain text to Quill delta for Slab updatePostContent.

    Returns object with "ops" nesting: {"ops": [{"insert": "..."}]}.
    Pass to GraphQL as JSON string (e.g. json.dumps(result)).
    """
    if not text:
        return {"ops": [{"insert": "\n"}]}
    return {"ops": [{"insert": text + "\n"}]}
