"""Schemas for the agentic search builder."""

from dataclasses import dataclass
from typing import Any


@dataclass
class VespaQuery:
    """Complete Vespa query ready for execution.

    Combines the YQL query string with all necessary parameters.
    This is the output of AgenticQueryBuilder and input to Executor.
    """

    yql: str
    params: dict[str, Any]

    def to_query_params(self) -> dict[str, Any]:
        """Merge YQL into params dict for VespaClient.execute_query().

        Returns:
            Combined dict with 'yql' key plus all other params
        """
        return {"yql": self.yql, **self.params}

    def format_params_for_logging(self) -> str:
        """Format params for readable logging, summarizing embedding vectors.

        Returns:
            Multi-line string with params, vectors shown as summaries
        """
        lines = []
        for key, value in self.params.items():
            if isinstance(value, dict) and "values" in value:
                # This is an embedding vector - summarize it
                vec = value["values"]
                dim = len(vec) if isinstance(vec, list) else "?"
                lines.append(f"  {key}: <vector dim={dim}>")
            elif key == "input.query(q_sparse)" and isinstance(value, dict):
                # Sparse vector - show token count
                cells = value.get("cells", {})
                lines.append(f"  {key}: <sparse tokens={len(cells)}>")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)
