"""Finish tool: definition for the agentic search agent.

Allows the agent to explicitly signal it is done searching.
"""

from typing import Any

# ── Tool definition (sent to the LLM) ────────────────────────────────

FINISH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": (
            "Call this tool when you are done searching. "
            "This ends the search loop and returns marked results to the user. "
            "You can call this together with mark_as_relevant in the same response."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}
