"""Debug script for SCE — run in PyCharm with breakpoints.

Verifies:
1. The exclusion set is built correctly
2. entity_type values from Vespa match the exclusion set
3. should_extract correctly skips code entities for NER
"""

import asyncio

from airweave.core.config import settings
from airweave.core.container import initialize_container


async def main():
    initialize_container(settings)
    import airweave.core.container as container_module
    container = container_module.container
    sce_service = container.sce_service

    # Print extractor info
    for i, ext in enumerate(sce_service.extractors):
        print(f"\nExtractor {i}: {ext.__class__.__name__}")
        print(f"  excluded_entity_types: {ext.excluded_entity_types}")

    # Grab the NER extractor (index 1)
    ner = sce_service.extractors[1]
    print(f"\nNER exclusion set ({len(ner.excluded_entity_types)} types):")
    for name in sorted(ner.excluded_entity_types):
        print(f"  - {name}")

    # Now fetch a few docs from Vespa and check entity_types
    from uuid import UUID

    from airweave.platform.destinations.vespa.destination import VespaDestination

    # Replace with your actual IDs
    collection_id = "cd761929-5c5b-4ba8-af89-c7302579bee3"
    sync_id = "dcedf738-d3ee-440f-a2bc-4c85f450f51a"

    vespa = await VespaDestination.create()
    docs = await vespa.query_documents(
        UUID(collection_id), UUID(sync_id), limit=20
    )

    print(f"\nFetched {len(docs)} docs from Vespa:")
    for doc in docs:
        entity_type = doc.system_metadata.entity_type
        ner_will_run = ner.should_extract(entity_type)
        marker = "NER SKIP" if not ner_will_run else "NER RUN"
        print(f"  [{marker}] {entity_type}: {doc.entity_id[:12]}...")


asyncio.run(main())
