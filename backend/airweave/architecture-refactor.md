# Airweave Backend Architecture Refactor v0

## Executive Summary

This document defines how we restructure the backend to make it **testable** and **reliable**. The core problem: our services are 1900-line god objects with direct imports to Stripe, Temporal, and Svix — impossible to test without hitting real infrastructure.

### The Design

**1. Domains own business logic, adapters own infrastructure**
```
domains/sync/operations.py      → "execute a sync" (business logic)
adapters/temporal/client.py     → "talk to Temporal" (infrastructure)
```

**2. Protocols are centralized by capability, not scattered by domain**
```
core/protocols/
├── messaging.py      # EventPublisher, StatePublisher
├── storage.py        # FileStorage, CredentialStore
├── sources.py        # Source
├── destinations.py   # Destination
└── embeddings.py     # Embedder
```

Domains import from `core/protocols/`. Domains may also define domain-specific protocols (e.g., `billing/protocols.py` → `PaymentGateway`). Adapters implement all protocols.

**3. Container wires dependencies, entry points inject them**
```python
# API: FastAPI Depends()
@router.post("/")
async def create(request, event_publisher: EventPublisher = Depends(get_event_publisher)):
    ...

# Temporal: Constructor injection at worker startup
activities = [RunSyncActivity(event_publisher=container.event_publisher)]
```

**4. Tests inject fakes — no monkey-patching**
```python
fake = FakeEventPublisher()
await operations.execute_sync(..., event_publisher=fake)
fake.assert_published("sync.completed")
```

### What Changes

| Before | After |
|--------|-------|
| `source_connection_service.py` (1923 lines) | `domains/source_connections/` (multiple small files) |
| `from temporal_service import temporal_service` | `workflow_runner: WorkflowRunner` (injected protocol) |
| `await stripe_client.create_customer()` | `await payment_gateway.create_customer()` (injected) |
| 275-line Temporal activities | 30-line thin wrappers calling domain ops |
| Serialized objects through Temporal | IDs only — activities fetch fresh data |

---

## Current State Analysis

### Pain Points

| Issue | Impact | Examples |
|-------|--------|----------|
| God Objects | 1900+ line services | `source_connection_service.py`, `billing/service.py` |
| Module Singletons | Tight coupling, hard to test | `sync_service`, `temporal_service`, `billing_service` |
| Transaction Boundaries | Services create own DB sessions | Scattered `get_db_context()` calls |
| Mixed Concerns | Auth, validation, orchestration intertwined | OAuth flows in `source_connection_service` |
| No Seams for Testing | Mocking requires patching imports | Direct calls to `crud.*`, `stripe_client.*` |

### Current Directory Structure (Problematic Areas)

```
backend/airweave/
├── core/                    # 🔴 God services + module singletons
│   ├── source_connection_service.py  # 1923 lines, 6+ responsibilities
│   ├── sync_service.py               # Temporal orchestration + DB ops
│   ├── temporal_service.py           # Direct Temporal client access
│   └── billing_service.py            # 900+ lines, Stripe + plans + periods
├── billing/                 # 🟡 Better, but still coupled to Stripe
├── platform/                # 🟡 Good modular structure, but no DI
│   ├── sources/             # ✅ Well-designed base class + implementations
│   ├── destinations/        # ✅ Good abstraction
│   ├── sync/                # 🟡 Complex but reasonable
│   └── temporal/            # 🟡 Direct client access
├── crud/                    # 🟡 Good, but accessed globally
├── api/                     # 🟡 Thin, but directly imports singletons
└── webhooks/                # 🟡 Coupled to Svix, no protocol boundary
```

---

## Proposed Directory Structure

```
backend/airweave/
│
├── api/                                    # HTTP layer - THIN routing only
│   ├── deps.py                             # FastAPI dependencies (DI wiring)
│   ├── middleware.py                       # Auth, logging, error handling
│   └── v1/endpoints/                       # Route definitions → delegate to domains
│
├── core/                                   # CROSS-CUTTING CONCERNS
│   ├── config.py                           # Settings (from env)
│   ├── container.py                        # DI container
│   ├── logging.py                          # Contextual logging
│   ├── context.py                          # ApiContext
│   └── protocols/                          # 🆕 CENTRALIZED PROTOCOLS
│       ├── __init__.py
│       ├── messaging.py                    # EventPublisher, StatePublisher
│       ├── storage.py                      # FileStorage, CredentialStore
│       ├── sources.py                      # Source
│       ├── destinations.py                 # Destination
│       ├── embeddings.py                   # Embedder
│       └── scheduling.py                   # WorkflowRunner
│
├── domains/                                # 🆕 CORE BUSINESS LOGIC
│   │
│   ├── source_connections/                 # Domain: Source Connection lifecycle
│   │   ├── types.py                        # Domain types (AuthMethod, AuthResult, etc.)
│   │   ├── auth/                           # Auth sub-domain
│   │   │   ├── logic.py                    # PURE: determine_auth_method, validate_credentials
│   │   │   ├── direct.py                   # I/O: Direct credential auth
│   │   │   ├── oauth2.py                   # I/O: OAuth2 browser + app-to-app flows
│   │   │   └── white_label.py              # I/O: White-label OAuth
│   │   ├── sync_management/                # Sync sub-domain
│   │   │   ├── logic.py                    # PURE: schedule validation
│   │   │   └── operations.py               # I/O: Trigger, cancel, schedule
│   │   ├── operations.py                   # Top-level operations (create, delete, update)
│   │   └── tests/                          # Colocated tests
│   │
│   ├── sync/                               # Domain: Sync execution engine
│   │   ├── types.py                        # SyncJobStatus, SyncStats, etc.
│   │   ├── logic.py                        # PURE: should_cleanup, is_incremental
│   │   ├── lifecycle.py                    # Status transitions + webhook publishing
│   │   ├── orchestration/                  # Sync orchestration (factory, orchestrator, stream)
│   │   ├── pipeline/                       # Entity processing (chunk, embed, dispatch)
│   │   ├── handlers/                       # Destination handlers
│   │   ├── operations.py                   # execute_sync(), create_job(), cancel()
│   │   └── tests/
│   │
│   ├── billing/                            # Domain: Subscription & usage billing
│   │   ├── types.py                        # BillingPlan, ChangeType, PlanLimits
│   │   ├── protocols.py                    # 🆕 PaymentGateway (domain-specific) ⭐️
│   │   ├── plans/logic.py                  # PURE: compare_plans, analyze_change
│   │   ├── subscriptions/operations.py     # Create, cancel, reactivate
│   │   ├── webhooks/handler.py             # Stripe webhook handling
│   │   └── tests/
│   │
│   ├── search/                             # Domain: Search & retrieval
│   │   ├── types.py                        # SearchConfig, RetrievalStrategy
│   │   ├── orchestrator.py                 # Pipeline execution
│   │   ├── operations/                     # Query expansion, retrieval, reranking
│   │   └── tests/
│   │
│   ├── webhooks/                           # Domain: Event publishing
│   │   ├── types.py                        # EventType, SyncEventPayload
│   │   ├── operations.py                   # publish_sync_event(), manage subscriptions
│   │   └── tests/
│   │
│   └── shared/                             # Cross-domain shared types
│       ├── types.py                        # SyncJobStatus, AuthMethod, etc.
│       └── exceptions.py                   # Domain exceptions
│
├── adapters/                               # 🆕 INFRASTRUCTURE ADAPTERS
│   │
│   ├── temporal/                           # Temporal Cloud/OSS
│   │   ├── client.py                       # Implements WorkflowRunner, ScheduleClient protocols
│   │   ├── worker.py                       # Worker setup with DI wiring
│   │   ├── workflows/                      # ORCHESTRATION ONLY (retry, timeout, routing)
│   │   │   ├── sync.py                     # SyncWorkflow — calls activities
│   │   │   └── cleanup.py                  # CleanupWorkflow
│   │   ├── activities/                     # THIN WRAPPERS (fetch → call domain op)
│   │   │   ├── sync.py                     # RunSyncActivity class
│   │   │   ├── sync_job.py                 # CreateSyncJobActivity class
│   │   │   └── cleanup.py                  # CleanupActivity class
│   │   ├── fake.py                         # FakeTemporalAdapter for testing
│   │   └── tests/
│   │
│   ├── stripe/                             # Stripe
│   │   ├── client.py                       # Implements PaymentGateway
│   │   ├── fake.py                         # FakePaymentGateway
│   │   └── tests/
│   │
│   ├── storage/                            # Implements FileStorage (core/protocols/storage.py)
│   │   ├── azure_blob.py
│   │   ├── local.py
│   │   └── fake.py
│   │
│   ├── credentials/                        # Implements CredentialStore (core/protocols/storage.py)
│   │   ├── azure_keyvault.py
│   │   └── fake.py
│   │
│   ├── analytics/                          # Implements AnalyticsTracker (core/protocols/)
│   │   ├── posthog.py
│   │   └── fake.py
│   │
│   ├── svix/                               # Implements EventPublisher (core/protocols/messaging.py)
│   │   ├── client.py
│   │   └── fake.py
│   │
│   ├── redis/                              # Implements StatePublisher (core/protocols/messaging.py)
│   │   ├── pubsub.py
│   │   └── fake.py
│   │
│   └── email/                              # Implements EmailSender (core/protocols/)
│       ├── sendgrid.py
│       └── fake.py
│
├── platform/                               # SOURCE/DESTINATION IMPLEMENTATIONS
│   ├── sources/                            # Source connectors (Slack, Notion, GitHub, ...)
│   │   ├── mixins.py                       # 🆕 Optional helpers (OAuthSourceMixin, ConcurrentEntityMixin)
│   │   ├── notion.py                       # Implements Source protocol + uses mixins
│   │   ├── slack.py
│   │   └── ...
│   ├── destinations/                       # Destination connectors (implements Destination protocol)
│   │   ├── qdrant.py
│   │   ├── vespa.py
│   │   └── ...
│   ├── entities/                           # Entity definitions
│   ├── embedders/                          # Embedding models (implements Embedder protocol)
│   ├── chunkers/                           # Text chunking
│   └── auth_providers/                     # OAuth providers (white-label)
│
├── db/                                     # DATABASE LAYER
│   ├── session.py                          # Session factory, get_db_context
│   ├── models/                             # 🆕 SQLAlchemy models (moved from models/)
│   └── repositories/                       # 🆕 Renamed from crud/
│
├── schemas/                                # PYDANTIC SCHEMAS (API contracts, mostly unchanged)
│
└── main.py                                 # FastAPI app entry point
```

### Colocated Tests

Tests live **with the code they test**:

```
domains/source_connections/
├── auth/
│   ├── logic.py
│   └── tests/
│       └── test_logic.py           # Unit: pure auth logic
├── operations.py
└── tests/
    ├── conftest.py                 # Domain-specific fixtures
    └── test_operations.py          # Integration: with fakes
```

Cross-cutting tests live in `tests/` at backend root:

```
tests/
├── conftest.py                     # Shared fixtures (db, fakes)
├── cross_domain/                   # Multi-domain flows
│   ├── test_full_sync_flow.py      # source_connections → sync → webhooks
│   └── test_billing_limits.py      # billing → guard_rails → sync
└── e2e/                            # Full API tests
    └── test_source_connection_api.py
```

**Why colocate?**
- Edit `logic.py`, `tests/test_logic.py` is right there
- Move a domain → tests move with it
- Domain teams own code + tests together

---

## Package Anatomy: Domains vs Adapters

Both `domains/` and `adapters/` are Python packages. They share structure but differ in purpose.

### What They Have in Common

| Both Have | Purpose |
|-----------|---------|
| `__init__.py` | Public API exports |
| `types.py` | Data structures (dataclasses, enums) |
| `tests/` | Colocated tests |

### What Makes Them Different

| Aspect | Domain | Adapter |
|--------|--------|---------|
| **Contains** | Business logic | Infrastructure wiring |
| **Imports** | `core/protocols/` | `core/protocols/` + SDKs |
| **Has** | `logic.py` (pure) + `operations.py` (I/O) | `client.py` (real) + `fake.py` (test) |
| **Example** | `domains/sync/` | `adapters/temporal/` |

### The Dependency Rule

```
            ┌─────────────────────┐
            │   core/protocols/   │  ← Cross-cutting contracts
            └─────────────────────┘
                 ▲           ▲
        imports  │           │  implements
                 │           │
           ┌─────┴───┐   ┌───┴─────┐
           │ domains │   │ adapters│
           └─────────┘   └─────────┘
                 │               │
                 │  may define   │  implements
                 ▼               │
        ┌────────────────┐       │
        │ domain-specific│ ◄─────┘
        │   protocols    │   (e.g., Stripe adapter implements billing's PaymentGateway)
        └────────────────┘
```

- **`core/protocols/`** defines all architectural contracts
- **Domains** import and use protocols
- **Adapters** implement protocols
- Domains **never** import adapters directly

---

## Two Entry Points, One Pattern

The backend has two main entry points. Both use the same container, injected differently.

### Entry Point 1: FastAPI (HTTP)

```python
# api/deps.py — wiring happens per-request via Depends()

def get_event_publisher() -> EventPublisher:
    return container.event_publisher

# api/v1/endpoints/sync.py

@router.post("/trigger")
async def trigger_sync(
    sync_id: UUID,
    p: ApiContext = Depends(get_context),
    workflow_runner: WorkflowRunner = Depends(get_workflow_runner),
):
    return await sync_ops.trigger(ctx.db, sync_id, ctx, workflow_runner=workflow_runner)
```

### Entry Point 2: Temporal (Background Jobs)

```python
# adapters/temporal/worker.py — wiring happens once at startup

def create_worker(client: Client, container: Container) -> Worker:
    return Worker(
        client,
        task_queue="sync-queue",
        activities=[
            RunSyncActivity(
                sync_executor=container.sync_executor,
                event_publisher=container.event_publisher,
            ),
        ],
    )
```

### Same Pattern, Different Timing

| Aspect | FastAPI | Temporal |
|--------|---------|----------|
| **When wired** | Per-request | At worker startup |
| **How injected** | `Depends()` | Constructor |
| **Lifetime** | Request-scoped | Worker-scoped |
| **Testing** | Override `app.dependency_overrides` | Pass fakes to constructor |

---

## Deep Dive: Decoupling the Sync Engine

The `platform/sync/` module is the most complex part of the codebase. It currently has direct dependencies on:

| Current | Side Effect | Protocol Needed |
|---------|-------------|-----------------|
| `arf/service.py` | File system I/O | `FileStorage` |
| `handlers/destination.py` | Qdrant/Vespa API calls | `VectorStore` |
| `handlers/entity_postgres.py` | Direct DB writes | (uses injected session) |
| `processors/chunk_embed.py` | OpenAI API calls | `Embedder` |
| `state_publisher.py` | Redis pub/sub | `StatePublisher` |
| `token_manager.py` | Credential fetch | `CredentialStore` |
| `web_fetcher.py` | HTTP requests | `HttpClient` |

### Target Architecture

```
core/protocols/
├── messaging.py                    # EventPublisher, StatePublisher
├── storage.py                      # FileStorage
├── destinations.py                 # Destination (vector store operations)
└── embeddings.py                   # Embedder

domains/sync/
├── orchestration/
│   ├── orchestrator.py            # Core sync loop (uses protocols)
│   ├── stream.py                  # Async entity stream
│   └── worker_pool.py             # Bounded concurrency
├── pipeline/
│   ├── entity_pipeline.py         # Chunk, embed, dispatch (uses protocols)
│   └── hash_computer.py           # Content hashing (pure)
├── operations.py                  # execute_sync(), cancel_sync()
└── lifecycle.py                   # Status transitions + webhooks

adapters/
├── vector_stores/
│   ├── qdrant.py                  # Implements VectorStore
│   ├── vespa.py                   # Implements VectorStore
│   └── fake.py                    # In-memory for testing
├── embedders/
│   ├── openai.py                  # Implements Embedder

│   └── fake.py                    # Returns fixed vectors
├── storage/
│   ├── azure_blob.py              # Implements FileStorage
│   ├── local.py                   # Implements FileStorage
│   └── fake.py                    # In-memory dict
└── redis/
    ├── pubsub.py                  # Implements StatePublisher
    └── fake.py                    # In-memory queue
```

### Why This Matters for Testing

**Before (current)**: Testing sync requires:
- Real Qdrant running
- Real Redis running
- Real file system
- Mocking OpenAI at HTTP level

**After (with protocols)**:
```python
async def test_sync_writes_to_vector_store():
    fake_vector_store = FakeVectorStore()
    fake_embedder = FakeEmbedder(vector=[0.1] * 1536)
    fake_storage = FakeFileStorage()

    await sync_ops.execute_sync(
        sync_id=sync.id,
        vector_store=fake_vector_store,
        embedder=fake_embedder,
        file_storage=fake_storage,
        ...
    )

    # Assert on fake state
    assert fake_vector_store.upserted_count == 42
    assert "entity-123" in fake_vector_store.points
    assert fake_storage.files["sync-123/entities.arf"] is not None
```

### Key Protocols for Sync

All in `core/protocols/` — sync imports them, adapters implement them:

```python
# core/protocols/destinations.py
@runtime_checkable
class Destination(Protocol):
    async def bulk_insert(self, entities: list[BaseEntity]) -> None: ...
    async def bulk_delete(self, ids: list[str]) -> None: ...
    async def search(self, query: str, limit: int, filter: Optional[dict] = None) -> list: ...

# core/protocols/embeddings.py
@runtime_checkable
class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...

# core/protocols/storage.py
@runtime_checkable
class FileStorage(Protocol):
    async def write(self, path: str, data: bytes) -> None: ...
    async def read(self, path: str) -> bytes | None: ...
    async def delete(self, path: str) -> None: ...
    async def list(self, prefix: str) -> list[str]: ...

# core/protocols/messaging.py
@runtime_checkable
class StatePublisher(Protocol):
    async def publish_progress(self, sync_job_id: UUID, stats: SyncStats) -> None: ...
    async def publish_heartbeat(self, sync_job_id: UUID) -> None: ...
```

### Incremental Migration Path

1. **Define protocols** in `core/protocols/` (by capability)
2. **Create adapters** that wrap existing implementations
3. **Inject protocols** into orchestrator (one at a time)
4. **Create fakes** for each protocol (in `adapters/X/fake.py`)
5. **Write integration tests** using fakes
6. **Delete direct dependencies** from orchestrator

---

## Deep Dive: Event Bus & Domain Events (IMPLEMENTED)

Domain code publishes events to an in-process bus. Subscribers handle side effects independently. This decouples the sync engine (and future domains) from webhooks, analytics, Redis PubSub, etc.

### Architecture

```
Domain code                    EventBus (InMemoryEventBus)              Subscribers
───────────                    ─────────────────────────────             ───────────
await event_bus.publish(  ──▶  fnmatch(event_type, pattern)  ──▶  WebhookSubscriber  (Svix)
  SyncLifecycleEvent(...)      asyncio.gather (fan-out)       ──▶  PostHogSubscriber  (analytics)
)                              failures isolated per-sub      ──▶  RealtimeSubscriber (Redis PubSub)
                                                              ──▶  CacheSubscriber    (invalidation)
```

### Two Layers: Protocol + Base Class

**Protocol** (`core/protocols/event_bus.py`) — what the bus requires:

```python
class DomainEvent(Protocol):
    event_type: str             # {domain}.{action}, glob-matched
    timestamp: datetime
    organization_id: UUID

class EventBus(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_pattern: str, handler: EventHandler) -> None: ...
```

**Base class** (`core/events/base.py`) — what event authors must inherit:

```python
class BaseDomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID
```

Protocol = bus's structural contract. Base class = Pydantic validation enforcement.

### Event Design

**Per-domain `str` enums** — no central mega-enum:

```python
# core/events/sync.py
class SyncEventType(str, Enum):        # satisfies Protocol's str return
    PENDING   = "sync.pending"
    COMPLETED = "sync.completed"
    ...

# core/events/auth.py (future)
class AuthEventType(str, Enum):
    FAILED = "auth.failed"
    ...
```

**Concrete events** inherit `BaseDomainEvent`, narrow `event_type`, add domain fields:

```python
class SyncLifecycleEvent(BaseDomainEvent):
    event_type: SyncEventType           # narrowed from str
    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID
    source_type: str = ""
    # ... metrics, error, etc.
```

**Events are self-contained** — subscribers never need to fetch more data.

### File Layout

```
core/events/
├── base.py          # BaseDomainEvent (Pydantic base)
├── sync.py          # SyncEventType + SyncLifecycleEvent
├── auth.py          # (future) AuthEventType + events
└── billing.py       # (future) BillingEventType + events

core/protocols/
└── event_bus.py     # DomainEvent, EventBus, EventHandler protocols

adapters/event_bus/
├── in_memory.py     # InMemoryEventBus (fnmatch + asyncio.gather)
└── fake.py          # FakeEventBus (records events for test assertions)
```

### Subscriber Wiring

All wiring in `core/container/factory.py` — explicit, one place:

```python
def _create_event_bus(webhook_publisher):
    bus = InMemoryEventBus()
    sync_subscriber = SyncEventSubscriber(webhook_publisher)
    for pattern in sync_subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, sync_subscriber.handle)
    # Future: posthog_subscriber, realtime_subscriber, etc.
    return bus
```

For ~5 subscribers this is ~20 lines. No auto-discovery magic needed.

### Planned Subscribers

| Subscriber | Pattern | Purpose |
|-----------|---------|---------|
| **Webhooks** (Svix) | `sync.*` | External webhook delivery (implemented) |
| **PostHog** | `*` | Analytics tracking of key lifecycle events |
| **Redis PubSub** | `*` | Real-time UI updates |
| **Audit log** | `*` | PostHog-based audit trail (maybe) |
| **Cache** | `sync.completed` | Cache population/invalidation (maybe) |

---

## The Interface Strategy

Protocols define contracts. This section explains **where** they live and **why**.

### The Decision Tree

```
"I need to define an interface"
         │
         ▼
"Is it cross-cutting infrastructure?" (messaging, storage, auth)
         │
    ┌────┴────┐
    Yes       No
    │         │
    ▼         ▼
core/     "Is it domain-specific?" (billing needs payment gateway)
protocols/       │
             ┌───┴───┐
             Yes     No (adapter-internal)
             │       │
             ▼       ▼
      domains/X/    Don't bother with
      protocols.py  a formal protocol
```

### Three Categories of Interfaces

| Category | Location | Example | Implemented By |
|----------|----------|---------|----------------|
| **Cross-cutting** | `core/protocols/` | `EventPublisher`, `Source`, `Destination` | Adapters |
| **Domain-specific** | `domains/X/protocols.py` | `PaymentGateway` (billing only) | Adapters (e.g., `adapters/stripe/`) |
| **Adapter-internal** | Within adapter (no protocol) | HTTP client variants | N/A — implementation detail |

**Note:** Adapters implement both cross-cutting protocols (from `core/protocols/`) AND domain-specific protocols (from `domains/X/protocols.py`).

### `core/protocols/` — Centralized Contracts

Organized by **capability**, not by consumer:

```
core/protocols/
├── __init__.py
├── messaging.py      # EventPublisher, StatePublisher
├── storage.py        # FileStorage, CredentialStore
├── sources.py        # Source
├── destinations.py   # Destination
├── embeddings.py     # Embedder
└── scheduling.py     # WorkflowRunner
```

**Rule:** If multiple parts of the app need it, it goes here.

### Source, Destination, Embedder as Protocols

The current `BaseSource` ABC is 659 lines — a contract buried under helper code. We split it:

**Protocol (minimal contract):**
```python
# core/protocols/sources.py

@runtime_checkable
class Source(Protocol):
    """What a source must do. Nothing more."""

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]: ...
    async def validate(self) -> bool: ...
```

**Source archetypes handle construction.** Sources are categorized by:
- **Auth type**: OAuth2 (with refresh, with rotating refresh), Direct credentials, API key
- **Sync mode**: Continuous (supports incremental via webhooks/polling) vs Batch

The existing `create()` classmethod stays — no per-source factory class needed. The archetype determines which mixins/helpers apply:

```python
# platform/sources/notion.py

@register_source(
    name="notion",
    auth_methods=[AuthenticationMethod.OAUTH_BROWSER],
    oauth_type=OAuthType.WITH_REFRESH,
    supports_continuous=False,  # Batch source
)
class NotionSource:
    """Implements Source protocol."""

    @classmethod
    async def create(cls, credentials=None, config=None) -> "NotionSource":
        # Archetype-based init (OAuth sources get token manager, etc.)
        ...

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        async for page in self._fetch_pages():
            yield NotionPageEntity(...)

    async def validate(self) -> bool:
        return await self._ping_api()
```

**Mixin (optional helpers):**
```python
# platform/sources/mixins.py

class OAuthSourceMixin:
    """Opt-in helpers for OAuth sources."""

    async def get_access_token(self) -> Optional[str]: ...
    async def refresh_on_unauthorized(self) -> Optional[str]: ...

class ConcurrentEntityMixin:
    """Opt-in helpers for concurrent processing."""

    async def process_entities_concurrent(self, items, worker, batch_size=10): ...
```

Sources can use mixins if they want the helpers, but the **protocol stays minimal**.

### Destination Protocol

```python
# core/protocols/destinations.py

@runtime_checkable
class Destination(Protocol):
    """What a destination must do."""

    async def setup_collection(self, collection_id: UUID, vector_size: int) -> None: ...
    async def bulk_insert(self, entities: list[BaseEntity]) -> None: ...
    async def bulk_delete(self, ids: list[str]) -> None: ...
    async def search(
        self,
        query: str,
        limit: int,
        filter: Optional[dict] = None
    ) -> list[SearchResult]: ...
```

### Domain-Specific Protocols

When only one domain needs an interface, it lives with that domain:

```python
# domains/billing/protocols.py

@runtime_checkable
class PaymentGateway(Protocol):
    """Billing's view of payment processing — domain vocabulary, not Stripe's."""

    async def create_customer(self, email: str, name: str) -> str: ...
    async def create_subscription(self, customer_id: str, plan: BillingPlan) -> str: ...
    async def cancel_subscription(self, subscription_id: str) -> None: ...
```

The Stripe adapter implements this in **domain terms**, hiding Stripe specifics:

```python
# adapters/stripe/client.py

class StripePaymentGateway:
    """Implements PaymentGateway using Stripe."""

    async def create_customer(self, email: str, name: str) -> str:
        customer = await stripe.Customer.create_async(email=email, name=name)
        return customer.id

    async def create_subscription(self, customer_id: str, plan: BillingPlan) -> str:
        price_id = self._plan_to_price_id(plan)  # Domain → Stripe mapping
        sub = await stripe.Subscription.create_async(customer=customer_id, items=[{"price": price_id}])
        return sub.id
```

### How It All Connects

```python
# 1. Protocol defined in core/protocols/
# core/protocols/messaging.py
class EventPublisher(Protocol):
    async def publish(self, org_id: UUID, event_type: str, payload: dict) -> None: ...

# 2. Adapter implements it
# adapters/svix/client.py
class SvixPublisher:
    async def publish(self, org_id: UUID, event_type: str, payload: dict) -> None:
        await self._client.message.create(self._app_id, MessageIn(...))

# 3. Container wires it
# core/container.py
@property
def event_publisher(self) -> EventPublisher:
    if self._event_publisher is None:
        self._event_publisher = SvixPublisher(settings.SVIX_API_KEY)
    return self._event_publisher

# 4. Domain uses it (via injection)
# domains/sync/operations.py
async def execute_sync(
    sync_id: UUID,
    event_publisher: EventPublisher,  # Protocol type
) -> None:
    # ... do sync ...
    await event_publisher.publish(org_id, "sync.completed", {"sync_id": str(sync_id)})

# 5. API endpoint injects it
# api/v1/endpoints/sync.py
@router.post("/{sync_id}/trigger")
async def trigger_sync(
    sync_id: UUID,
    publisher: EventPublisher = Depends(get_event_publisher),
):
    await sync_ops.execute_sync(sync_id, event_publisher=publisher)

# 6. Tests inject fakes
# tests/domains/sync/test_operations.py
async def test_sync_publishes_completion():
    fake = FakeEventPublisher()
    await execute_sync(sync_id, event_publisher=fake)
    assert fake.events[-1][1] == "sync.completed"
```

### Fake Implementations

Every protocol needs a fake for testing:

```python
# adapters/svix/fake.py

class FakeEventPublisher:
    """Test implementation — records calls, supports failure injection."""

    def __init__(self):
        self.events: list[tuple[UUID, str, dict]] = []
        self.should_fail = False

    async def publish(self, org_id: UUID, event_type: str, payload: dict) -> None:
        if self.should_fail:
            raise RuntimeError("Simulated failure")
        self.events.append((org_id, event_type, payload))

    # Test helpers
    def assert_published(self, event_type: str) -> dict:
        for _, et, payload in self.events:
            if et == event_type:
                return payload
        raise AssertionError(f"Event {event_type} was not published")
```

---

## Creational Patterns & Dependency Injection

This is the heart of the refactor. How do dependencies get created and wired together?

### The Problem Today

```python
# Current: Module-level singletons everywhere
# core/source_connection_service.py

from airweave.integrations.stripe_client import stripe_client  # Direct import
from airweave.core.temporal_service import temporal_service    # Direct import

class SourceConnectionService:
    async def create_connection(self, ...):
        # Tightly coupled — can't test without real Stripe/Temporal
        await stripe_client.create_customer(...)
        await temporal_service.start_workflow(...)
```

Testing this requires monkey-patching imports, which is fragile and doesn't catch type errors.

### The Solution: Dependency Container + FastAPI + Constructor Injection

A **lightweight container** with lazy initialization:

```python
# core/container.py

@dataclass
class Container:
    _credential_store: CredentialStore | None = None
    _event_publisher: EventPublisher | None = None
    # ... etc

    @property
    def credential_store(self) -> CredentialStore:
        if self._credential_store is None:
            from airweave.adapters.credentials.azure_keyvault import AzureKeyVaultStore
            self._credential_store = AzureKeyVaultStore()
        return self._credential_store

    def with_overrides(self, **overrides) -> "Container":
        """For testing — replace dependencies with fakes."""
        return Container(
            _credential_store=overrides.get("credential_store", self._credential_store),
            # ...
        )

container = Container()  # Global instance
```

| Concern | How It's Addressed |
|---------|-------------------|
| Lazy init | Real clients created on first access |
| No import cycles | Imports inside property getters |
| Testing | `with_overrides()` injects fakes |
| Type safety | Properties return protocol types |

### Injection at Both Entry Points

```
┌─────────────────────────────────────────────────────────────┐
│                        Container                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │CredentialStore│ │EventPublisher│  │ SyncExecutor │  ...  │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
           │                              │
           │ Depends()                    │ Constructor
           ▼                              ▼
   ┌───────────────┐              ┌───────────────┐
   │ API Endpoints │              │   Temporal    │
   │  (per-request)│              │  (at worker   │
   │               │              │   startup)    │
   └───────────────┘              └───────────────┘
```

**FastAPI** — wired per-request via `Depends()`:
```python
# api/deps.py
def get_credential_store() -> CredentialStore:
    return container.credential_store

# api/v1/endpoints/source_connections.py
@router.post("/")
async def create_source_connection(
    credential_store: CredentialStore = Depends(get_credential_store),
):
    return await operations.create(..., credential_store=credential_store)
```

**Temporal** — wired once at worker startup via constructor:
```python
# adapters/temporal/worker.py
def create_worker(client: Client, container: Container) -> Worker:
    return Worker(
        client,
        task_queue="sync-queue",
        activities=[
            RunSyncActivity(
                sync_executor=container.sync_executor,
                event_publisher=container.event_publisher,
            ),
        ],
    )

# adapters/temporal/activities/sync.py
class RunSyncActivity:
    def __init__(self, sync_executor: SyncExecutor, event_publisher: EventPublisher):
        self._sync_executor = sync_executor
        self._event_publisher = event_publisher

    @activity.defn
    async def run(self, sync_id: str, sync_job_id: str, org_id: str, force_full: bool = False):
        await sync_ops.execute_sync(
            sync_id=UUID(sync_id), sync_job_id=UUID(sync_job_id), org_id=UUID(org_id),
            sync_executor=self._sync_executor, event_publisher=self._event_publisher,
        )
```

### Testing with Fakes

```python
# tests/conftest.py
@pytest.fixture
def fake_credentials():
    return FakeCredentialStore()

# domains/source_connections/tests/test_operations.py
async def test_create_stores_credentials(db, ctx, fake_credentials):
    result = await operations.create(db, request, ctx, credential_store=fake_credentials)
    fake_credentials.assert_stored(result.integration_credential_id)

async def test_handles_credential_failure(db, ctx, fake_credentials):
    fake_credentials.should_fail = True
    with pytest.raises(RuntimeError, match="Simulated failure"):
        await operations.create(...)
```

### Key Design: Pass IDs, Not Objects

Workflows pass **IDs only** — activities fetch fresh data:

```python
# adapters/temporal/workflows/sync.py

@workflow.defn
class SyncWorkflow:
    @workflow.run
    async def run(self, sync_id: str, org_id: str, force_full: bool = False):
        # 1. Create job (returns job_id or None if already running)
        sync_job_id = await workflow.execute_activity(
            create_sync_job_activity, args=[sync_id, org_id, force_full], ...
        )
        if not sync_job_id:
            return  # Skip — job already running

        # 2. Execute sync — just IDs, no serialized objects
        await workflow.execute_activity(
            run_sync_activity, args=[sync_id, sync_job_id, org_id, force_full], ...
        )
```

**Why IDs only?**
- Tiny Temporal payloads (UUIDs vs serialized Pydantic models)
- Activities always fetch fresh data
- No stale state issues

### Domain Operations Do the Work

Activities are thin — business logic lives in domain operations:

```python
# domains/sync/operations.py

async def execute_sync(
    sync_id: UUID, sync_job_id: UUID, org_id: UUID, force_full_sync: bool,
    *, sync_executor: SyncExecutor, event_publisher: EventPublisher,
) -> None:
    """All business logic here — activity just calls this."""
    async with get_db_context() as db:
        sync, job, collection, connection = await _fetch_context(db, sync_id, sync_job_id)

        await lifecycle.transition_to_running(job, event_publisher)

        try:
            await sync_executor.run(sync, job, collection, connection, force_full_sync)
            await lifecycle.transition_to_completed(db, job, event_publisher)
        except asyncio.CancelledError:
            await lifecycle.transition_to_cancelled(db, job, event_publisher)
            raise
        except Exception as e:
            await lifecycle.transition_to_failed(db, job, str(e), event_publisher)
            raise
```

Status transitions and webhooks are isolated in `lifecycle.py`:

```python
# domains/sync/lifecycle.py

async def transition_to_running(job: SyncJob, event_publisher: EventPublisher):
    async with get_db_context() as db:
        await update_status(db, job.id, SyncJobStatus.RUNNING)
    await event_publisher.publish_sync_event(job.org_id, EventType.SYNC_RUNNING, ...)
```

### Factories and Builders

Beyond dependency injection, we use two patterns for complex object creation:

**Factory** — async construction with I/O and multiple dependencies:
```python
# search/factory.py
class SearchFactory:
    async def build(
        self, request_id: str, collection_id: UUID, search_request: SearchRequest,
        ctx: ApiContext, db: AsyncSession, ...
    ) -> SearchContext:
        collection = await crud.collection.get(db, id=collection_id, ctx=ctx)
        destination = await self._resolve_destination(db, collection, ctx)
        federated_sources = await self.get_federated_sources(db, collection, ctx)
        return SearchContext(
            collection=collection, destination=destination,
            federated_sources=federated_sources, ...
        )
```

**Builder (Layer Merge)** — merging config from multiple sources:
```python
# platform/sync/config/builder.py
class SyncConfigBuilder:
    @classmethod
    def build(cls, collection_overrides=None, sync_overrides=None, job_overrides=None) -> SyncConfig:
        config = SyncConfig()  # Schema defaults + env vars
        for overrides in [collection_overrides, sync_overrides, job_overrides]:
            if overrides:
                config = config.merge_with(overrides.model_dump(exclude_unset=True))
        return config
```

**Builder (Fluent API)** — chainable methods for complex queries:
```python
# core/admin_sync_service.py
class AdminSyncQueryBuilder:
    def __init__(self):
        self.query = select(Sync)

    def with_organization_id(self, org_id: UUID) -> "AdminSyncQueryBuilder":
        if org_id:
            self.query = self.query.where(Sync.organization_id == org_id)
        return self

    def with_status(self, status: str) -> "AdminSyncQueryBuilder":
        if status:
            self.query = self.query.where(Sync.status == SyncStatus(status))
        return self

# Usage
query = (AdminSyncQueryBuilder()
    .with_organization_id(org_id)
    .with_status("running")
    .with_source_type("notion")
    .query)
```

| Pattern | When to Use | Example |
|---------|-------------|---------|
| **Factory** | Async init, multiple db/api calls | `SearchFactory.build()` |
| **Builder (Merge)** | Layered config resolution | `SyncConfigBuilder.build()` |
| **Builder (Fluent)** | Complex queries with optional filters | `AdminSyncQueryBuilder` |
| **`create()` classmethod** | Archetype-based source init | `NotionSource.create()` |

---

## Pure Logic vs Operations

Every domain has two types of code:

### `logic.py` — Pure Functions (No I/O)

```python
# domains/billing/plans/logic.py

def analyze_plan_change(
    current: BillingPlan,
    target: BillingPlan,
    has_payment_method: bool,
) -> PlanChangeDecision:
    """Pure business logic — returns decision, doesn't execute it."""

    if target > current and not has_payment_method:
        return PlanChangeDecision(allowed=False, reason="Payment required")

    if target > current:
        return PlanChangeDecision(allowed=True, apply_immediately=True)

    if target < current:
        return PlanChangeDecision(allowed=True, apply_immediately=False)  # End of period
```

**Testing**: Direct function calls, no fixtures needed.

### `operations.py` — I/O Functions (Use Protocols)

```python
# domains/billing/subscriptions/operations.py

async def change_plan(
    db: AsyncSession,
    org_id: UUID,
    target_plan: BillingPlan,
    ctx: ApiContext,
    *,
    payment_gateway: PaymentGateway,  # Protocol
) -> Subscription:
    """Executes a plan change — has I/O."""

    # 1. Pure logic
    current = await get_current_plan(db, org_id)
    decision = logic.analyze_plan_change(current, target_plan, ctx.has_payment_method)

    if not decision.allowed:
        raise ValueError(decision.reason)

    # 2. I/O via protocol
    if decision.apply_immediately:
        await payment_gateway.update_subscription(org_id, target_plan)
    else:
        await payment_gateway.schedule_downgrade(org_id, target_plan)

    # 3. DB update
    return await update_subscription_record(db, org_id, target_plan)
```

**Testing**: Inject fake `PaymentGateway`, assert on fake state.

---

## Testing Strategy (IMPLEMENTED)

### Test Categories

| Category | Location | What to Test | Dependencies |
|----------|----------|--------------|--------------|
| **Unit (pure)** | `<package>/tests/test_logic.py` | Pure functions — no I/O | None |
| **Unit (with fakes)** | `<package>/tests/test_*.py` | Subscribers, operations | Individual fakes |
| **Integration (wiring)** | `<package>/tests/test_*_fanout.py` | Bus → subscriber → fake publisher | Real bus + fakes |
| **API (endpoint)** | `tests/integration/api/` | HTTP in → HTTP out, faked infra | `test_container` + fake `ApiContext` |
| **Cross-Domain** | `tests/integration/` | Multi-domain flows | `test_container` |
| **E2E** | `tests/e2e/` | Full stack against running services | Live infra (Donke) |

### Conftest Hierarchy

```
backend/
├── conftest.py                              # Root: env vars, shared fakes, test_container
├── airweave/
│   ├── domains/webhooks/tests/
│   │   └── conftest.py                      # Domain-specific: subscriber fixture
│   ├── domains/sync/tests/
│   │   └── conftest.py                      # Domain-specific: sync fixtures (future)
│   └── adapters/temporal/tests/
│       └── conftest.py                      # Adapter-specific: workflow fixtures (future)
└── tests/
    ├── unit/conftest.py                     # (inherits from root, minimal)
    └── integration/api/conftest.py          # API client with overridden container
```

Root conftest is loaded first for **both** testpaths. Shared fixtures live there once, domain conftest layers on top.

### The Test Container

The frozen `Container` dataclass makes test wiring trivial. Every protocol has a corresponding fake in `adapters/<name>/fake.py`. The root conftest builds a fully-faked container:

```python
# backend/conftest.py

@pytest.fixture
def fake_event_bus():
    return FakeEventBus()

@pytest.fixture
def fake_webhook_publisher():
    return FakeWebhookPublisher()

@pytest.fixture
def fake_webhook_admin():
    return FakeWebhookAdmin()

@pytest.fixture
def test_container(fake_event_bus, fake_webhook_publisher, fake_webhook_admin):
    return Container(
        event_bus=fake_event_bus,
        webhook_publisher=fake_webhook_publisher,
        webhook_admin=fake_webhook_admin,
    )
```

As more protocols land (`FileStorage`, `CredentialStore`, `WorkflowRunner`, etc.), each gets a fake and a fixture here. The `test_container` grows with the real container.

For partial overrides (e.g., real bus with fake publisher):

```python
container_with_real_bus = test_container.replace(event_bus=InMemoryEventBus())
```

### API Tests: Inject() Override

FastAPI endpoints use `Inject(ProtocolType)` which resolves from the global container. API tests override `get_container` so every `Inject()` call resolves to a fake:

```python
# tests/integration/api/conftest.py

@pytest_asyncio.fixture
async def client(test_container):
    app.dependency_overrides[get_container] = lambda: test_container
    app.dependency_overrides[get_context] = lambda: _make_fake_context()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

No monkeypatching. Endpoint code is identical to production — only the container contents differ.

### Fakes Pattern

Every adapter that implements a protocol also ships a fake:

```
adapters/
├── event_bus/
│   ├── in_memory.py          # Real: InMemoryEventBus
│   └── fake.py               # Test: FakeEventBus (records events)
├── webhooks/
│   ├── svix.py               # Real: SvixAdapter
│   └── fake.py               # Test: FakeWebhookPublisher, FakeWebhookAdmin
└── stripe/                   # (future)
    ├── client.py             # Real: StripePaymentGateway
    └── fake.py               # Test: FakePaymentGateway
```

Fakes record calls and expose test helpers (`assert_published`, `assert_subscription_created`, etc.). They optionally support failure injection (`fake.should_fail = True`).

### pytest Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "airweave"]   # Colocated tests anywhere under airweave/
python_files = ["test_*.py", "*_test.py"]
asyncio_mode = "auto"
```

```bash
# Run everything
pytest

# Run one domain's tests
pytest airweave/domains/webhooks/tests/

# Run API integration tests
pytest tests/integration/api/

# Skip slow/e2e for local dev
pytest -m "not slow" --ignore=tests/e2e/
```

---

## Migration Strategy

### Phase 1: Foundation

1. Create `core/protocols/` with all centralized protocols
2. Create `domains/` and `adapters/` directories
3. Create fake implementations for each protocol
4. Expand `core/container.py` with all dependencies
5. Create `adapters/temporal/worker.py` with DI wiring
6. Convert `platform/sources/_base.py` to `Source` protocol + optional mixins

### Phase 2: Domain Migration

Migrate one domain at a time:

| Domain | What Moves | Uses Protocols From |
|--------|-----------|---------------------|
| `source_connections` | OAuth flows, connection CRUD | `core/protocols/` (CredentialStore, WorkflowRunner) |
| `sync` | Sync execution, lifecycle | `core/protocols/` (Destination, Embedder, EventPublisher) |
| `billing` | Plans, subscriptions | `domains/billing/protocols.py` (PaymentGateway) — domain-specific |
| `search` | Query pipeline | `core/protocols/` (Destination, Embedder) |

Each migration:
1. Create `types.py` (domain-specific protocols only if needed)
2. Extract pure logic to `logic.py`
3. Create operations with protocol parameters
4. Update API endpoints to inject dependencies
5. Write tests with fakes

### Phase 2b: Temporal Refactor

1. Convert activities to classes with constructor injection
2. Move business logic from activities → `domains/sync/operations.py`
3. Extract lifecycle (status + webhooks) → `domains/sync/lifecycle.py`
4. Change workflows to pass IDs only
5. Update `worker.py` to instantiate activities with container

### Phase 3: Cleanup

1. Delete old `core/*_service.py` singletons
2. Delete old `platform/temporal/activities/` (replaced by `adapters/temporal/activities/`)
3. Rename `crud/` → `db/repositories/`
4. Move `models/` → `db/models/`
5. Full test pass

---

## Appendix: Terminology

| Term | Meaning |
|------|---------|
| **Domain** | Business logic package (e.g., `domains/billing/`) |
| **Adapter** | Infrastructure implementation (e.g., `adapters/stripe/`) |
| **Protocol** | Abstract interface — lives in `core/protocols/` or domain-specific `protocols.py` |
| **Mixin** | Optional helper code — opt-in conveniences (e.g., `OAuthSourceMixin`) |
| **Fake** | Test implementation of a protocol (e.g., `FakeEventPublisher`) |
| **Factory** | Class with async `build()` method for complex object creation with I/O |
| **Builder** | Chainable construction: layer merge (`SyncConfigBuilder`) or fluent API (`AdminSyncQueryBuilder`) |
| **Container** | Holds all protocol implementations, supports overrides |
| **Pure function** | No I/O, deterministic, trivially testable |
| **Operation** | Function with I/O, uses injected protocols |
| **Workflow** | Temporal orchestration — retry/timeout logic only |
| **Activity** | Temporal execution unit — thin wrapper calling domain ops |
| **Lifecycle** | Status transitions + side effects (webhooks, metrics) |
| **Archetype** | Source category (OAuth/Direct, Continuous/Batch) that determines initialization |

---

## Summary

| Before | After |
|--------|-------|
| 1900-line god services | Small, focused modules |
| Module singletons | Protocol-based injection |
| Direct Stripe/Temporal imports | Swappable adapters |
| Monkey-patching for tests | Fake injection |
| Mixed pure logic + I/O | Separated `logic.py` + `operations.py` |
| Tests in separate tree | Colocated with code |
| 275-line Temporal activities | Thin wrappers (~30 lines) calling domain ops |
| Serialized objects through Temporal | IDs only — activities fetch fresh data |
| 659-line `BaseSource` ABC | Minimal `Source` protocol + optional mixins |
| Protocols scattered per domain | Centralized in `core/protocols/` (domain-specific only when needed) |

**Key insight**: The container is just a dataclass with lazy properties. DI works the same everywhere:
- **API**: `Depends()` resolves from container per-request
- **Temporal**: Constructor injection at worker startup
- **Tests**: `container.with_overrides()` injects fakes

**Protocol strategy**: Cross-cutting protocols in `core/protocols/` (messaging, storage, sources, destinations, embeddings). Domain-specific protocols stay with the domain (e.g., `billing/protocols.py` for `PaymentGateway`).
