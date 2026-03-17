"""Clear all airweave_system_metadata_annotations from Vespa documents."""

import asyncio
from uuid import UUID

from airweave.platform.destinations.vespa.destination import VespaDestination
from airweave.platform.destinations._base import VectorDBUpdate


async def main():
    collection_id = UUID("cd761929-5c5b-4ba8-af89-c7302579bee3")
    sync_id = UUID("dcedf738-d3ee-440f-a2bc-4c85f450f51a")

    vespa = await VespaDestination.create()

    offset = 0
    total_cleared = 0
    while True:
        docs = await vespa.query_documents(
            collection_id, sync_id, limit=1000, offset=offset
        )
        if not docs:
            break

        updates = []
        for doc in docs:
            entity_type = doc.system_metadata.entity_type
            updates.append(VectorDBUpdate(
                id=f"{entity_type}_{doc.entity_id}",
                entity_schema=doc.system_metadata.entity_schema,
                fields={"airweave_system_metadata_annotations": []},
            ))

        await vespa.bulk_update(updates)
        total_cleared += len(updates)
        print(f"Cleared {len(updates)} docs (total: {total_cleared})")

        if len(docs) < 1000:
            break
        offset += 1000

    print(f"Done. Cleared annotations on {total_cleared} documents.")


asyncio.run(main())
