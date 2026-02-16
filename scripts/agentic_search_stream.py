"""Visualize agentic_search streaming search events.

Usage:
    python scripts/agentic_search_stream.py <collection_id> <query> [--host HOST] [--filter FILTER_JSON] [--mode MODE]

Examples:
    python scripts/agentic_search_stream.py test-04ic3f "what does julius schutten really want?"
    python scripts/agentic_search_stream.py my-collection "find deployment docs" --mode direct
    python scripts/agentic_search_stream.py my-collection "slack messages" --filter '[{"conditions":[{"field":"airweave_system_metadata.source_name","operator":"equals","value":"slack"}]}]'
"""

import argparse
import json
import sys
import time

import httpx


def dim(text: str) -> str:
    return f"\033[2m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


def green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def magenta(text: str) -> str:
    return f"\033[35m{text}\033[0m"


def wrap_text(text: str, width: int = 90, indent: str = "  ") -> str:
    """Wrap text to width with indent on continuation lines."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return f"\n{indent}".join(lines)


def render_planning(event: dict) -> None:
    iteration = event["iteration"]
    plan = event["plan"]
    print(f"\n{cyan(bold(f'  Planning (iteration {iteration})'))}  ")
    print(f"  {dim('Query:')} {plan['query']['primary']}")
    if plan["query"].get("variations"):
        print(f"  {dim('Variations:')} {', '.join(plan['query']['variations'])}")
    print(f"  {dim('Strategy:')} {plan['retrieval_strategy']}")
    filter_groups = plan.get("filter_groups") or []
    if filter_groups:
        for i, group in enumerate(filter_groups):
            conditions = group.get("conditions", [])
            parts = [f"{c['field']} {c['operator']} {c['value']}" for c in conditions]
            prefix = "  " if i == 0 else "  OR "
            print(
                f"  {dim('Filters:' if i == 0 else '        ')} {prefix}({', '.join(parts)})"
            )
    else:
        print(f"  {dim('Filters:')} None")
    print(f"  {dim('Limit:')} {plan.get('limit', '?')}")
    print(f"  {dim('Reasoning:')}")
    print(f"  {wrap_text(plan['reasoning'])}")


def render_searching(event: dict) -> None:
    count = event["result_count"]
    ms = event["duration_ms"]
    print(f"\n{yellow(bold('  Searching'))}  ")
    print(f"  Found {bold(str(count))} results in {bold(f'{ms}ms')}")


def render_evaluating(event: dict) -> None:
    ev = event["evaluation"]
    cont = ev["should_continue"]
    verdict = "Continue" if cont else "Done"
    color = yellow if cont else green
    print(f"\n{magenta(bold('  Evaluating'))}  {dim('→')} {color(verdict)}")
    print(f"  {dim('Results summarized:')} {len(ev.get('result_summaries', []))}")
    print(f"  {dim('Reasoning:')}")
    print(f"  {wrap_text(ev['reasoning'])}")
    if ev.get("advice"):
        print(f"  {dim('Advice:')}")
        print(f"  {wrap_text(ev['advice'])}")


def render_done(event: dict) -> None:
    response = event["response"]
    answer = response["answer"]
    results = response["results"]
    citations = answer.get("citations", [])

    print(f"\n{'─' * 60}")
    print(f"{green(bold('  Answer'))}\n")
    print(f"  {wrap_text(answer['text'])}")

    if citations:
        print(f"\n  {dim('Citations:')}")
        cited_ids = {c["entity_id"] for c in citations}
        for result in results:
            if result["entity_id"] in cited_ids:
                name = result.get("name", "?")
                entity_type = result.get("airweave_system_metadata", {}).get(
                    "entity_type", "?"
                )
                source = result.get("airweave_system_metadata", {}).get(
                    "source_name", "?"
                )
                print(
                    f"    {dim('•')} {bold(name)} {dim(f'({entity_type} from {source})')}"
                )

    print(f"\n  {dim(f'{len(results)} results returned, {len(citations)} cited')}")


def render_error(event: dict) -> None:
    print(f"\n{red(bold('  Error'))}")
    print(f"  {red(event['message'])}")


RENDERERS = {
    "planning": render_planning,
    "searching": render_searching,
    "evaluating": render_evaluating,
    "done": render_done,
    "error": render_error,
}


def main():
    parser = argparse.ArgumentParser(description="AgenticSearch streaming search viewer")
    parser.add_argument("collection_id", help="Collection readable ID")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--host", default="http://localhost:8001", help="API host")
    parser.add_argument("--filter", default=None, help="Filter JSON string")
    parser.add_argument("--mode", default="agentic", choices=["agentic", "direct"])
    args = parser.parse_args()

    url = f"{args.host}/collections/{args.collection_id}/agentic-search/stream"
    body = {"query": args.query, "mode": args.mode}
    if args.filter:
        body["filter"] = json.loads(args.filter)

    print(f"{'─' * 60}")
    print(f"  {bold('Agentic Search')}")
    print(f"  {dim('Collection:')} {args.collection_id}")
    print(f"  {dim('Query:')} {args.query}")
    if args.filter:
        print(f"  {dim('Filter:')} {args.filter}")
    print(f"  {dim('Mode:')} {args.mode}")
    print(f"{'─' * 60}")

    start = time.monotonic()

    with httpx.stream(
        "POST",
        url,
        json=body,
        headers={"Content-Type": "application/json"},
        timeout=120.0,
    ) as response:
        if response.status_code != 200:
            print(red(f"\nHTTP {response.status_code}"))
            print(response.read().decode())
            sys.exit(1)

        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                message, buffer = buffer.split("\n\n", 1)
                message = message.strip()
                if not message:
                    continue

                # Parse SSE data line
                if message.startswith("data: "):
                    data_str = message[6:]
                elif message.startswith("data:"):
                    data_str = message[5:]
                else:
                    continue

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    print(dim(f"  [raw] {data_str}"))
                    continue

                event_type = event.get("type", "unknown")
                renderer = RENDERERS.get(event_type)
                if renderer:
                    renderer(event)
                else:
                    print(dim(f"  [unknown event] {json.dumps(event, indent=2)}"))

    elapsed = time.monotonic() - start
    print(f"\n{'─' * 60}")
    print(f"  {dim(f'Total time: {elapsed:.1f}s')}")
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()
