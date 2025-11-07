# Airweave Engineering Onboarding Video Series

## Video 1: "Airweave 101: Architecture & Core Data Flow" (15-20 min)

### Opening (2 min)
- **What is Airweave?** Context retrieval for AI agents across apps & databases
- **The Big Picture**: Show monorepo structure (backend, frontend, mcp, monke, donke)

### Section 1: High-Level Architecture (5 min)
**iPad Drawing Moment**: Draw the complete system architecture
- External APIs (GitHub, Slack, Notion, etc.)
- FastAPI Backend
- PostgreSQL (metadata)
- Qdrant (vectors)
- Redis (pub/sub)
- Temporal (orchestration)
- Frontend (React)
- MCP Server (Node.js)

**Code Reference**: `.cursor/rules/airweave-overview.mdc`
- Point out the monorepo structure
- Explain each component's role

### Section 2: Data Flow Journey (8 min)
**iPad Drawing Moment**: Trace a document's journey from source to search
```
External API → Sync Trigger → Temporal Workflow → Source Connector →
Entity Stream → Entity Pipeline → Embeddings → Qdrant → Search API → User
```

**Code Walkthrough**:
1. `backend/airweave/core/sync_service.py` - Entry point for syncs
2. `backend/airweave/platform/temporal/workflows/sync.py` - Durable execution
3. `backend/airweave/platform/sync/orchestrator.py` - The 5 phases
4. `backend/airweave/platform/sync/entity_pipeline.py` - Processing pipeline

**Key Concepts to Emphasize**:
- Async/streaming architecture (pull-based, not push)
- Separation of concerns (orchestrator vs pipeline)
- The 5 sync phases: Start → Process Entities → Access Controls → Cleanup → Complete

### Section 3: Source Connectors Deep Dive (5 min)
**Code Reference**: `backend/airweave/platform/sources/`

**Show Examples**:
- `github.py` - File-based connector
- `slack.py` - Federated search pattern
- `postgresql.py` - Database connector with continuous sync
- `salesforce.py` - OAuth with BYOC

**iPad Drawing Moment**: Draw the BaseSource inheritance tree
- BaseSource class
- @source decorator magic
- generate_entities() async generator pattern
- OAuth vs Direct auth flows

**Key Takeaway**: "Every connector follows the same pattern: authenticate → generate entities → stream data"

---

## Video 2: "Backend Deep Dive: CRUD, Auth & Services" (15-20 min)

### Section 1: The CRUD Layer Foundation (6 min)
**Code Reference**: `backend/airweave/crud/`, `.cursor/rules/crud-layer.mdc`

**iPad Drawing Moment**: Draw the CRUD inheritance hierarchy
```
CRUDBase
├── CRUDBaseOrganization (collections, syncs, connections)
├── CRUDBaseUser (user profiles)
└── CRUDPublic (sources, destinations, embedding models)
```

**Code Walkthrough**:
1. `backend/airweave/crud/_base_organization.py` - Show organization scoping
2. `backend/airweave/api/context.py` - ApiContext structure
3. Example: `backend/airweave/crud/crud_collection.py`

**Key Concepts**:
- ApiContext carries organization_id, user, auth_method, logger
- Unit of Work pattern for transactions
- Automatic user tracking (created_by_email, modified_by_email)
- Access validation in every operation

**Demo**: Show how to create a collection with proper context

### Section 2: OAuth2 & Integration Authentication (6 min)
**Code Reference**: `backend/airweave/platform/auth/`

**iPad Drawing Moment**: Draw OAuth2 flow
```
User → Frontend → Auth URL → External Provider → Callback → 
Token Exchange → Store Credentials → Refresh Token Management
```

**Code Walkthrough**:
1. `oauth2_service.py` - Main OAuth orchestration
2. `settings.py` - Integration settings from YAML
3. `yaml/prd.integrations.yaml` - Configuration examples

**Show 3 OAuth Patterns**:
- **access_only**: Slack (no refresh)
- **with_refresh**: GitHub (refresh token)
- **with_rotating_refresh**: Google (refresh token rotates)

**Key Concepts**:
- PKCE for security (Airtable example)
- TokenManager for automatic refresh
- Auth provider pattern (browser OAuth, auth provider, direct)

### Section 3: Service Layer Architecture (5 min)
**iPad Drawing Moment**: Draw service interactions
```
API Endpoint → Service → CRUD → Database
           ↓
    Business Logic
    Analytics Tracking
    Background Jobs
```

**Key Services Overview**:
- **SyncService**: Orchestrates data synchronization
- **OAuth2Service**: Handles authentication flows
- **Auth0Service**: User authentication & org management
- **StripeService**: Subscription & billing
- **PostHogService**: Analytics tracking

**Code Reference**: `backend/airweave/core/sync_service.py`

**Key Takeaway**: "Services contain business logic, CRUD handles data access"

---

## Video 3: "The Sync Pipeline: From Entities to Vectors" (20-25 min)

### Section 1: Entity Processing Pipeline (8 min)
**Code Reference**: `backend/airweave/platform/sync/entity_pipeline.py`

**iPad Drawing Moment**: Draw the complete entity pipeline flow
```
Raw Entity → Enrich Metadata → Transform (DAG) → Build Text Representation →
Chunk → Embed (Dense + Sparse) → Persist to Qdrant → Persist to DB → Update Progress
```

**Code Walkthrough**:
1. `EntityPipeline.process()` - Main entry point
2. `_build_textual_representations()` - Jinja2 templates
3. `_chunk_entities()` - Text splitting
4. `_embed_entities()` - Dense + sparse embeddings
5. `_persist_to_destinations()` - Qdrant writes

**Key Concepts**:
- Entity multiplication: 1 file → N chunks
- Content hashing for change detection
- Progressive cleanup of temp files
- Partition tracking for batching

### Section 2: SyncOrchestrator & Async Workers (6 min)
**Code Reference**: `backend/airweave/platform/sync/orchestrator.py`

**iPad Drawing Moment**: Draw the pull-based architecture
```
AsyncSourceStream (Producer)
    ↓ (bounded queue with backpressure)
AsyncWorkerPool (Consumers)
    ↓ (concurrent processing)
EntityPipeline
```

**Code Walkthrough**:
1. Show the 5 phases in `SyncOrchestrator.run()`
2. Explain micro-batching vs per-entity processing
3. Worker pool concurrency control

**Key Concepts**:
- Pull-based (not push) prevents memory issues
- Backpressure via bounded queue
- Worker pool manages concurrency
- Cancellation propagation

### Section 3: Qdrant Vector Storage (5 min)
**Code Reference**: `backend/airweave/platform/destinations/qdrant.py`

**iPad Drawing Moment**: Draw Qdrant collection strategy
```
Physical Collection = f"org_{org_id}_{collection_id}"
Point = {
  id: deterministic_uuid(sync_id, entity_id),
  vector: {dense: [...], bm25: {indices: [...], values: [...]}},
  payload: {entity data + airweave_collection_id filter}
}
```

**Code Walkthrough**:
1. `setup_collection()` - Collection creation with dense + sparse vectors
2. `insert()` - Point structure and payload normalization
3. Show multi-tenant filtering

**Key Concepts**:
- Physical collection naming for tenant isolation
- Deterministic UUIDs prevent duplicates
- Dense + sparse vectors for hybrid search
- Write concurrency semaphore

### Section 4: Search Operations (6 min)
**Code Reference**: `backend/airweave/search/operations/`

**iPad Drawing Moment**: Draw search pipeline
```
Query → [QueryExpansion] → Retrieval (Qdrant) → [FederatedSearch] →
[Reranking] → Apply Filters → [GenerateAnswer] → Results
```

**Code Walkthrough**:
1. `query_expansion.py` - LLM generates query variations
2. `retrieval.py` - Hybrid search (semantic + keyword with RRF)
3. `reranking.py` - Provider-based reranking (Cohere, Groq, OpenAI)
4. `federated_search.py` - Live searches (e.g., Slack)

**Key Concepts**:
- Provider fallback system
- Recency bias for temporal relevance
- RRF (Reciprocal Rank Fusion) for merging results
- Optional operations controlled by parameters

---

## Video 4: "The Interfaces to Our Product" (18-22 min)

### Section 1: Frontend UI (React) (5 min)
**Code Reference**: `frontend/src/`

**iPad Drawing Moment**: Draw frontend architecture
```
React Components → Zustand Stores → apiClient → Backend API
                                         ↓
                  Real-time: SSE Streams → Sync Progress
```

**Code Walkthrough**:
1. `frontend/src/main.tsx` - App initialization (Auth0, PostHog, Theme)
2. `frontend/src/lib/api.ts` - apiClient with token management
3. `frontend/src/lib/stores/sources.ts` - Zustand store example
4. `frontend/src/stores/syncStateStore.ts` - SSE subscription pattern

**Key Concepts**:
- ShadCN + Radix UI + Tailwind CSS
- Relative API paths (apiClient handles prefixing)
- Token provider pattern for auth
- SSE for real-time sync updates

**Demo**: Show a page component using stores and API calls

### Section 2: REST API (FastAPI) (4 min)
**Code Reference**: `backend/airweave/api/v1/endpoints/`

**iPad Drawing Moment**: Draw API request flow
```
HTTP Request → NGINX Ingress → FastAPI → Dependencies (auth, validation) →
Endpoint Handler → Service → CRUD → Database/Qdrant → Response
```

**Code Walkthrough**:
1. `backend/main.py` - FastAPI app initialization
2. `backend/airweave/api/v1/endpoints/collections.py` - Example endpoints
3. `backend/airweave/api/deps.py` - Dependency injection (auth, context)

**Key Concepts**:
- RESTful design (collections, sources, syncs, search)
- Dependency injection for ApiContext
- Pydantic schemas for validation
- Swagger docs at `/docs`

**Show**: Open Swagger UI and demonstrate an API call

### Section 3: Python & TypeScript SDKs (4 min)
**Code Reference**: `README.md` (SDK examples), `typescript-sdk/`

**iPad Drawing Moment**: Draw SDK architecture
```
User Code → SDK Client → HTTP Requests → Airweave API
                ↓
        Type-safe interfaces
        Automatic retries
        Error handling
```

**Show SDK Examples**:

**Python SDK**:
```python
from airweave import AirweaveSDK

client = AirweaveSDK(api_key="...", base_url="...")
collection = client.collections.create(name="My Collection")
results = client.collections.search(
    readable_id=collection.readable_id,
    query="Find recent payments",
    enable_reranking=True,
    recency_bias=0.8
)
```

**TypeScript SDK**:
```typescript
import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
    apiKey: "...",
    environment: AirweaveSDKEnvironment.Local
});
const results = await client.collections.search(
    collection.readableId,
    { query: "...", enableReranking: true }
);
```

**Key Concepts**:
- Generated from OpenAPI spec (Fern)
- Type-safe interfaces
- Async/await patterns

### Section 4: MCP Server (Model Context Protocol) (5 min)
**Code Reference**: `mcp/`

**iPad Drawing Moment**: Draw MCP architecture
```
Local Mode (Desktop):
Claude Desktop → stdio transport → MCP Server (Node.js) → Airweave API

Hosted Mode (Cloud):
OpenAI Agent Builder → Streamable HTTP → MCP Server (K8s) → Redis Sessions → Airweave API
```

**Code Walkthrough**:
1. `mcp/src/index.ts` - stdio transport (local)
2. `mcp/src/index-http.ts` - HTTP transport (hosted)
3. `mcp/src/tools/search-tool.ts` - Dynamic tool creation
4. `mcp/src/session/redis-session-manager.ts` - Session management

**Key Concepts**:
- Two transports: stdio (local) vs Streamable HTTP (cloud)
- Dynamic tool names per collection: `search-{collection}`
- Redis session management for horizontal scaling
- Full parameter exposure (limit, offset, recency_bias, etc.)

**Demo**: Show MCP server config for Claude Desktop

### Section 5: Documentation (Fern) (3 min)
**Code Reference**: `fern/`

**iPad Drawing Moment**: Show docs structure
```
fern/
├── definition/openapi.json    # API spec
├── docs.yml                   # Doc structure
└── docs/pages/                # Content
    ├── welcome/
    ├── quickstart/
    └── connectors/
```

**Show**: Navigate through https://docs.airweave.ai

**Key Concepts**:
- Auto-generated from OpenAPI
- Interactive API playground
- Connector guides with setup instructions
- SDK examples

**Key Takeaway**: "Multiple interfaces, one platform - choose the best tool for your use case"

---

## Video 5: "Infrastructure & Deployment" (15-18 min)

### Section 1: Azure Architecture Overview (5 min)
**Code Reference**: `infra-core/README.md`, `infra-core/.cursor/rules/infra-overview.mdc`

**iPad Drawing Moment**: Draw complete Azure architecture
```
                    Internet
                       ↓
                  Azure LB
                       ↓
                 NGINX Ingress
                       ↓
          ┌───────────────────────────┐
          │   AKS Cluster (10.0.1.0)  │
          ├───────────────────────────┤
          │ Backend API (FastAPI)     │
          │ Frontend (React)          │
          │ Temporal Workers (Python) │
          │ Temporal Server           │
          │ Qdrant (vectors)          │
          │ Redis (cache/pubsub)      │
          └───────────────────────────┘
                 ↓           ↓
          PostgreSQL    Key Vault
         (10.0.3.0)    (secrets)
```

**Key Components**:
- AKS for Kubernetes orchestration
- Managed PostgreSQL (private endpoint)
- Azure Key Vault (secrets)
- Container Registry (ACR)
- VNet with subnets
- Private DNS zones

### Section 2: Terraform Infrastructure as Code (4 min)
**Code Reference**: `infra-core/infra/`

**iPad Drawing Moment**: Draw Terraform module structure
```
main.tf
├── module: network (VNet, subnets, NSGs)
├── module: aks (cluster, node pools)
├── module: postgresql (managed DB)
├── module: keyvault (secrets storage)
└── module: monitoring (App Insights, Log Analytics)
```

**Code Walkthrough**:
1. `infra-core/infra/main.tf` - Root module
2. `infra-core/infra/dev.tfvars` - Environment config
3. Show a module: `infra-core/infra/modules/aks/main.tf`

**Key Concepts**:
- Environment-specific tfvars (dev, stg, prd)
- Remote state in Azure Storage
- Module reusability

### Section 3: Helm Charts & Deployments (4 min)
**Code Reference**: `infra-core/helm/airweave/`

**iPad Drawing Moment**: Draw Helm chart structure
```
helm/airweave/
├── Chart.yaml
├── values.yaml                # Default values
├── values-dev.yaml            # Dev overrides
├── values-prd.yaml            # Prod overrides
└── templates/
    ├── backend-deployment.yaml
    ├── frontend-deployment.yaml
    ├── temporal-worker-deployment.yaml
    └── ingress.yaml
```

**Code Walkthrough**:
1. `helm/airweave/values.yaml` - Configuration structure
2. `helm/airweave/templates/backend-deployment.yaml` - K8s deployment

**Key Concepts**:
- Helm for templating K8s manifests
- Environment-specific values files
- Rolling updates with zero downtime
- Workload Identity for pod authentication

### Section 4: Local Development with Docker Compose (5 min)
**Code Reference**: `docker/docker-compose.yml`

**iPad Drawing Moment**: Draw local architecture
```
docker-compose.yml
├── backend (FastAPI) :8001
├── frontend (Vite) :5173
├── postgres :5432
├── qdrant :6333
├── redis :6379
├── temporal :7233
└── temporal-ui :8088
```

**Code Walkthrough**:
1. `docker/docker-compose.yml` - Service definitions
2. `start.sh` - Startup script
3. `backend/entrypoint.dev.sh` - Dev mode with hot reload

**Key Concepts**:
- Volume mounts for hot reload
- Named networks for service discovery
- Environment variables from `.env`
- Health checks and dependencies

**Demo**: Show `./start.sh` and access the UI

---

## Video 6: "Testing & Monitoring: Monke & Donke" (15-18 min)

### Section 1: Monke - E2E Testing Framework (10 min)
**Code Reference**: `monke/`

**iPad Drawing Moment**: Draw Monke architecture
```
runner.py → TestFlow → Bongo → External API
                ↓              (create data)
           Test Steps              ↓
                ↓         Airweave Backend
        1. Create              (sync)
        2. Sync                   ↓
        3. Verify           Qdrant Vector DB
        4. Update               ↓
        5. Delete          Search & Verify
        6. Cleanup        (relevance scores)
```

**Code Walkthrough**:
1. `monke/runner.py` - Main entry point
2. `monke/core/flow.py` - TestFlow orchestration
3. `monke/core/steps.py` - Individual test steps
4. `monke/bongos/github.py` - Example bongo
5. `monke/configs/github.yaml` - Configuration

**Key Concepts**:
- **Bongos**: API integrators that create real test data
- **Test Flow**: Create → Sync → Verify → Update → Delete
- **Content Generation**: LLM-generated data with tracking tokens
- **Verification**: Vector search with relevance score thresholds
- **Parallel Execution**: Test multiple connectors simultaneously

**Demo**: Run `./monke.sh github` and show the Rich UI

**Why E2E Testing Matters**:
- Tests real API integrations (not mocks)
- Validates entire pipeline (source → sync → search)
- Catches integration bugs early
- Ensures connector reliability

### Section 2: Donke - Intelligent Error Monitoring (8 min)
**Code Reference**: `donke/`

**iPad Drawing Moment**: Draw Donke workflow
```
Azure Log Analytics → Fetch Errors → Cluster by Signature →
     ↓
LLM Analysis (Claude) → Severity Assessment → Context Enrichment (Airweave) →
     ↓
Suppression Check → Create Linear Ticket → Slack Alert with Mute Button
```

**Code Walkthrough**:
1. `donke/function_app.py` - Azure Function entry point
2. `donke/agent/orchestrator.py` - Error processing orchestration
3. `donke/agent/analysis.py` - LLM-powered analysis
4. `donke/agent/enrichment.py` - Airweave context search
5. `donke/clients/linear_client.py` - Ticket creation

**Key Concepts**:
- **Error Clustering**: Group by signature (file:line + message pattern)
- **LLM Analysis**: Claude assesses severity (P0-P3) and suggests actions
- **Context Enrichment**: Search Airweave for related tickets, code, docs
- **Smart Suppression**: 24h windows, manual mutes, regression detection
- **Automated Ticketing**: Create Linear tickets with rich context
- **Slack Integration**: Interactive mute buttons

**Show Examples**:
- Error signature in PostgreSQL
- LLM analysis output
- Linear ticket format
- Slack alert message

**Why This Matters**:
- Reduces noise (smart clustering)
- Speeds up debugging (context enrichment)
- Tracks regressions (returning errors)
- Improves response time (automated ticketing)

---

## Summary & Next Steps (2 min)

**Recap the Journey**:
1. ✅ Architecture & data flow fundamentals
2. ✅ Backend systems (CRUD, auth, services)
3. ✅ Sync pipeline (entities → vectors)
4. ✅ Product interfaces (UI, API, SDK, MCP, docs)
5. ✅ Infrastructure (Azure, Terraform, Helm, Docker)
6. ✅ Testing & monitoring (Monke, Donke)

**Where to Go Next**:
- Pick a connector to study deeply
- Contribute to Monke tests for a new connector
- Add a feature to the frontend
- Optimize a search operation
- Improve error handling in the sync pipeline

**Resources**:
- `.cursor/rules/` - Architecture documentation
- `CONTRIBUTING.md` - Contribution guide
- Discord: Ask questions in #engineering
- Pair programming: Schedule with the team

**Key Takeaway**: "You now understand how Airweave works end-to-end. Time to build!"

