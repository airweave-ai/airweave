#!/usr/bin/env python3
"""Backfill manifest.json files for existing local ARF data.

This is a standalone script that works directly with the filesystem,
without needing the full Airweave environment.

Usage:
    cd backend
    python3 scripts/backfill_arf_manifests.py

The script will:
1. Scan local_storage/raw/ for ARF folders
2. Try to infer the source type from entity data
3. Create manifest.json with entity/file counts
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def infer_source_type(sync_path: Path) -> str:
    """Try to infer source type from entity data."""
    entities_dir = sync_path / "entities"
    if not entities_dir.exists():
        return "unknown"

    # Check first few entity files
    entity_files = list(entities_dir.glob("*.json"))[:5]

    for entity_file in entity_files:
        try:
            with open(entity_file) as f:
                entity = json.load(f)
        except Exception:
            continue

        # Check module name
        module = entity.get("__entity_module__", "")
        if "notion" in module.lower():
            return "notion"
        if "github" in module.lower():
            return "github"
        if "google_drive" in module.lower():
            return "google_drive"
        if "slack" in module.lower():
            return "slack"

        # Check entity class
        entity_class = entity.get("__entity_class__", "")
        if "Notion" in entity_class:
            return "notion"
        if "GitHub" in entity_class or "Commit" in entity_class or "Issue" in entity_class:
            return "github"

    return "unknown"


def count_entities_and_files(sync_path: Path) -> tuple[int, int]:
    """Count entities and files in an ARF store."""
    entities_dir = sync_path / "entities"
    files_dir = sync_path / "files"

    entity_count = len(list(entities_dir.glob("*.json"))) if entities_dir.exists() else 0
    file_count = len(list(files_dir.iterdir())) if files_dir.exists() else 0

    return entity_count, file_count


def create_manifest(sync_path: Path, source_short_name: str) -> dict:
    """Create a manifest for an ARF store."""
    entity_count, file_count = count_entities_and_files(sync_path)
    now = datetime.now(timezone.utc).isoformat()

    manifest = {
        "sync_id": sync_path.name,
        "source_short_name": source_short_name,
        "collection_id": "",  # Unknown for backfilled data
        "collection_readable_id": "",
        "organization_id": "",
        "created_at": now,
        "updated_at": now,
        "sync_jobs": [],  # No jobs for backfilled data
        "entity_count": entity_count,
        "file_count": file_count,
        "vector_size": None,
        "embedding_model_name": None,
    }

    return manifest


def main() -> None:
    """CLI entry point for ARF manifest backfill."""
    print("=" * 60)
    print("ARF Manifest Backfill Script")
    print("=" * 60)

    # Find the local_storage/raw directory
    script_dir = Path(__file__).resolve().parent
    raw_dir = script_dir.parent / "local_storage" / "raw"

    if not raw_dir.exists():
        print(f"\n❌ No local_storage/raw directory found at: {raw_dir}")
        return

    # List all sync directories
    sync_dirs = [d for d in raw_dir.iterdir() if d.is_dir()]

    if not sync_dirs:
        print(f"\nNo ARF stores found in {raw_dir}")
        return

    print(f"\nFound {len(sync_dirs)} ARF store(s):\n")

    to_create = []
    for sync_path in sync_dirs:
        manifest_path = sync_path / "manifest.json"
        sync_id = sync_path.name

        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            source = manifest.get("source_short_name", "unknown")
            print(f"  ✓ {sync_id}: manifest exists ({source})")
        else:
            source_type = infer_source_type(sync_path)
            entity_count, file_count = count_entities_and_files(sync_path)
            print(
                f"  ✗ {sync_id}: needs manifest "
                f"(inferred: {source_type}, {entity_count} entities, {file_count} files)"
            )
            to_create.append((sync_path, source_type))

    if not to_create:
        print("\n✅ All ARF stores already have manifests!")
        return

    # Confirm
    print(f"\nWill create {len(to_create)} manifest(s).")
    response = input("Continue? [y/N]: ").strip().lower()
    if response != "y":
        print("Aborted.")
        return

    # Create manifests
    print("\nCreating manifests...")
    created = []
    for sync_path, source_type in to_create:
        manifest = create_manifest(sync_path, source_type)
        manifest_path = sync_path / "manifest.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        created.append(sync_path.name)
        print(f"   ✓ Created: {sync_path.name} ({source_type})")

    print(f"\n✅ Created {len(created)} manifest(s)!")
    print("\nDone!")


if __name__ == "__main__":
    main()
