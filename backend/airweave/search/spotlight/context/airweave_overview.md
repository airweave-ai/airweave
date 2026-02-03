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
| `source_name` | Source type (e.g., "notion", "slack") |
| `entity_type` | Entity class (e.g., "NotionPageEntity") |
| `original_entity_id` | ID before chunking (shared by all chunks from the same item) |
| `chunk_index` | Position if content was split into chunks |

**Source-Specific Fields:** Each source has unique entity types with different fields
(e.g., `status`, `labels`, `assignee`). See the Collection Info section for available fields.

### How Data Becomes Searchable

1. **Entity extraction**: Source connector generates raw entities with all fields
2. **Textual representation**: A markdown `textual_representation` is built from high-signal fields
3. **Chunking**: Long content is split into smaller chunks sharing the same `original_entity_id`
4. **Embedding**: Each chunk gets a dense embedding (semantic) and sparse embedding (keyword)
5. **Indexing**: Entities are stored and become searchable

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

- **Keyword Search**: Matches against ALL entity fields (full JSON payload). Best for exact terms,
  specific field values, technical terms, IDs, proper nouns.
- **Semantic Search**: Matches against `textual_representation` only. Best for meaning-based
  queries, conceptually related content, natural language questions.
- **Hybrid Search**: Combines keyword filtering with semantic relevance.

### Filter Operators

For each filter condition, specify:
- `field`: The field name to filter on
- `operator`: One of `equals`, `not_equals`, `contains`, `greater_than`, `less_than`,
  `greater_than_or_equal`, `less_than_or_equal`, `in`, `not_in`
- `value`: The value to compare against (string, number, or list for `in`/`not_in`)

### Important Fields for Deep Exploration

- `breadcrumbs`: Filter by location hierarchy (e.g., "Engineering" workspace)
- `original_entity_id`: Get ALL chunks from the same original entity for full context
- `chunk_index`: Navigate within a document (get surrounding chunks)
