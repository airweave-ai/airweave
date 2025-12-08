#!/usr/bin/env python3
"""Transform Airweave docs.jsonl into Vespa feed format.

Handles:
- ISO timestamp → epoch seconds conversion
- Extracting extra source fields into `payload` JSON
- Vespa document feed format (put operations)
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Fields that belong to the base_entity schema (not payload)
BASE_FIELDS = {
    "entity_id",
    "breadcrumbs",
    "name",
    "created_at",
    "updated_at",
    "textual_representation",
    "airweave_system_metadata",  # skipped for now since not in schema
}


def iso_to_epoch(iso_string: Optional[str]) -> Optional[int]:
    """Convert ISO 8601 timestamp to Unix epoch seconds."""
    if iso_string is None:
        return None
    try:
        # Handle ISO format with Z or +00:00 timezone
        if iso_string.endswith("Z"):
            iso_string = iso_string[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_string)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def transform_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a single document to Vespa feed format."""
    # Start with base fields
    vespa_fields = {}

    # entity_id (string, as-is)
    vespa_fields["entity_id"] = doc.get("entity_id")

    # name (string, as-is)
    vespa_fields["name"] = doc.get("name")

    # breadcrumbs (array of struct)
    breadcrumbs = doc.get("breadcrumbs", [])
    if breadcrumbs:
        vespa_fields["breadcrumbs"] = breadcrumbs

    # Timestamps → epoch seconds
    vespa_fields["created_at"] = iso_to_epoch(doc.get("created_at"))
    vespa_fields["updated_at"] = iso_to_epoch(doc.get("updated_at"))

    # textual_representation (string, as-is)
    vespa_fields["textual_representation"] = doc.get("textual_representation")

    # Extract extra fields into payload
    payload = {}
    for key, value in doc.items():
        if key not in BASE_FIELDS:
            payload[key] = value

    if payload:
        vespa_fields["payload"] = json.dumps(payload)

    # Remove None values for cleaner output
    vespa_fields = {k: v for k, v in vespa_fields.items() if v is not None}

    # Vespa feed format
    entity_id = doc.get("entity_id", "unknown")
    return {
        "put": f"id:airweave:base_entity::{entity_id}",
        "fields": vespa_fields,
    }


def main():
    input_path = Path(__file__).parent.parent / "dataset" / "docs.jsonl"
    output_path = Path(__file__).parent.parent / "dataset" / "vespa_feed.json"

    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])

    print(f"Reading from: {input_path}")
    print(f"Writing to: {output_path}")

    documents = []
    with open(input_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                vespa_doc = transform_document(doc)
                documents.append(vespa_doc)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping line {line_num} due to JSON error: {e}", file=sys.stderr)

    # Write as JSON array (Vespa feed format)
    with open(output_path, "w") as f:
        json.dump(documents, f, indent=2)

    print(f"Transformed {len(documents)} documents")
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
