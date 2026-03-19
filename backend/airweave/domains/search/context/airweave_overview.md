Airweave is a platform that connects to apps, databases, and documents and turns them into
searchable knowledge. Data from various sources is extracted, chunked, embedded, and stored
in a vector database.

## How Airweave Works

### Core Concepts

- **Source**: An external application, database, or document store
  (e.g., Notion, Slack, GitHub, Google Drive, Salesforce).
- **Source Connection**: A configured, authenticated instance linking to a specific account
  or workspace.
- **Entity**: A single indexed item extracted from a source
  (e.g., a Slack message, Notion page, GitHub issue).
- **Collection**: A searchable knowledge base composed of entities from one or more source
  connections. Search is always performed against exactly one collection.

### Entity Structure

**Base Fields (present on all entities):**

| Field | Description |
|-------|-------------|
| `entity_id` | Unique ID of this item (for chunks: `original_entity_id__chunk_{{chunk_index}}`) |
| `name` | Display name of the entity |
| `breadcrumbs` | Location hierarchy (e.g., "Workspace > Project > Page") |
| `created_at` | When created in source (if available) |
| `updated_at` | When last modified in source (if available) |

**System Metadata (set by Airweave):**

| Field | Description |
|-------|-------------|
| `airweave_system_metadata.source_name` | Source type (e.g., "notion", "slack") |
| `airweave_system_metadata.entity_type` | Entity class (e.g., "NotionPageEntity") |
| `airweave_system_metadata.original_entity_id` | ID before chunking (shared by all chunks from the same item) |
| `airweave_system_metadata.chunk_index` | Position if content was split into chunks |

**Source-Specific Fields:** Each source has unique entity types with different fields
(e.g., `status`, `labels`, `assignee`). See the Collection Info section for available fields.

**Important:** Source-specific fields are stored in the entity payload and are **searchable via
keyword search** but **NOT filterable**. To find entities with specific field values, include
those terms in your search query rather than using filters.

### How Data Becomes Searchable

1. **Entity extraction**: Source connector generates raw entities with all fields
2. **Textual representation**: A markdown `textual_representation` is built from high-signal fields
3. **Chunking**: Long content is split into smaller chunks sharing the same `original_entity_id`
4. **Embedding**: Each chunk gets a dense embedding (semantic) and sparse embedding (keyword)
5. **Indexing**: Entities are stored and become searchable

### What Chunking Means for Search

Each chunk is a **separate search result**. A long document (e.g., a 10-page PDF) is split
into multiple chunks that share the same `original_entity_id`. A search result showing
chunk 2 of a document means you're seeing one section — other sections exist in sibling
chunks.

### Textual Representation

The `textual_representation` field is purpose-built for semantic search. Not all entity fields
are equally useful for meaning-based matching—IDs, timestamps, and system metadata add noise.

Airweave marks source fields as "embeddable" when they carry semantic value (e.g., title,
description, content). The textual representation is a markdown document containing:
- Entity metadata (name, breadcrumbs)
- Embeddable source fields (title, description, labels, etc.)
- File content (for document entities)

This focused representation ensures semantic search matches on high-signal content, not polluted
by system IDs or JSON structure. For exact matching, keyword search uses the full entity payload.

### How Search Works

- **Keyword search** matches against ALL entity fields (full JSON payload), including
  source-specific fields. Use for exact terms, IDs, proper nouns.
- **Semantic search** matches against `textual_representation` only. Use for meaning-based
  queries and conceptually related content.
- **Hybrid search** combines both.

### Federated Sources

Some sources (marked as "federated" in the collection metadata) cannot be synced and
indexed due to API limitations. Instead, they are searched in real-time via their native
search API at query time using the primary query as a keyword search.

Federated results are automatically merged with vector database results. Filters, limit,
and offset all work normally on federated results. The only difference is that retrieval
strategy and query variations don't affect federated sources — they are always searched
via keyword matching.

Since federated data is not synced, fields like `sync_id` and `chunk_index` will be empty
on federated results.
