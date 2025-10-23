<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-airweave-darkbg.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="frontend/public/logo-airweave-lightbg.svg"/>
  <img width="837" alt="airweave-lettermark" style="padding-bottom: 12px;" src="frontend/public/logo-airweave-darkbg.svg"/>
</picture>

# Make Any App Searchable for AI Agents

[![Ruff](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml)
[![ESLint](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml)
[![System Tests](https://github.com/airweave-ai/airweave/actions/workflows/test-public-api.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/test-public-api.yml)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/airweave-sdk?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=BRIGHTGREEN&left_text=downloads)](https://pepy.tech/projects/airweave-sdk)
[![Discord](https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square)](https://discord.gg/gDuebsWGkn)
<br>
<div style="padding-top: 16px;">
<a href="https://trendshift.io/repositories/13748" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13748" alt="airweave-ai%2Fairweave | Trendshift" style="width: 250px; height: 55px; margin-right: 24px;" width="250" height="55"/></a>&nbsp;&nbsp;<a href="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app" target="_blank"><img src="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app/upvote_embed.svg" alt="Launch YC: Airweave - Let Agents Search Any App" style="margin-left: 12px;"/></a>
</div>

<br>

⭐ **Help us reach more developers and grow the Airweave community. Star this repo!**

</div>

## What is Airweave?

[Airweave](https://app.airweave.ai/) is a fully open-source tool that lets agents search any app. It connects to apps, productivity tools, databases, or document stores and transforms their contents into searchable knowledge bases, accessible through a standardized interface for agents.

The search interface is exposed via REST API or MCP. When using MCP, Airweave essentially builds a semantically searchable MCP server. The platform handles everything from auth and extraction to embedding and serving. You can find our documentation [here](https://docs.airweave.ai/welcome).

📺 Check out a quick demo of Airweave below:

<video width="100%" src="https://github.com/user-attachments/assets/995e4a36-3f88-4d8e-b401-6ca43db0c7bf" controls></video>

[**🔗 Example notebooks**](https://github.com/airweave-ai/airweave/tree/main/examples)

## Table of Contents

- [Airweave](#airweave)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [🚀 Quick Start](#-quick-start)
  - [🔌 Supported Integrations](#-supported-integrations)
  - [💻 Usage](#-usage)
    - [Frontend](#frontend)
    - [API](#api)
  - [📦 SDKs](#-sdks)
    - [Python](#python)
    - [TypeScript/JavaScript](#typescriptjavascript)
  - [🔑 Key Features](#-key-features)
  - [🔧 Technology Stack](#-tech-stack)
  - [👥 Contributing](#-contributing)
  - [📄 License](#-license)
  - [🔗 Connect](#-connect)

## 🚀 Quick Start

### Managed Service: [Airweave Cloud](https://app.airweave.ai/)

### Self-hosted:

Make sure docker and docker-compose are installed, then...

```bash
# 1. Clone the repository
git clone https://github.com/airweave-ai/airweave.git
cd airweave

# 2. Build and run
chmod +x start.sh
./start.sh
```

That's it! Access the dashboard at http://localhost:8080

## 🔌 Supported Integrations

<!-- START_APP_GRID -->

<p align="center">
<img src="frontend/src/components/icons/apps/airtable.svg" alt="Airtable" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/asana.svg" alt="Asana" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/attio.svg" alt="Attio" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/bitbucket.svg" alt="Bitbucket" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/box.svg" alt="Box" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/clickup.svg" alt="ClickUp" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/confluence.svg" alt="Confluence" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/ctti.svg" alt="CTTI" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/dropbox.svg" alt="Dropbox" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/excel.svg" alt="Dropbox" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/github.svg" alt="Github" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/gitlab.svg" alt="Gitlab" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/gmail.svg" alt="Gmail" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/google_calendar.svg" alt="Google Calendar" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/google_drive.svg" alt="Google Drive" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/hubspot.svg" alt="Hubspot" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/jira.svg" alt="Jira" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/linear.svg" alt="Linear" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/monday.svg" alt="Monday" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/notion.svg" alt="Notion" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/onedrive.svg" alt="Onedrive" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/onenote.svg" alt="OneNote" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/outlook_calendar.svg" alt="Outlook Calendar" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/outlook_mail.svg" alt="Outlook Mail" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/postgresql.svg" alt="Postgresql" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/salesforce.svg" alt="Salesforce" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/sharepoint.svg" alt="Sharepoint" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/slack.svg" alt="Slack" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/stripe.svg" alt="Stripe" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/teams.svg" alt="Teams" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/todoist.svg" alt="Todoist" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/trello.svg" alt="Trello" width="50" height="50" style="margin: 8px;" />
<img src="frontend/src/components/icons/apps/zendesk.svg" alt="Zendesk" width="50" height="50" style="margin: 8px;" />
</p>

<!-- END_APP_GRID -->

## 💻 Usage

### Frontend
- Access the UI at `http://localhost:8080`
- Connect sources, configure syncs, and query data

### API
- Swagger docs: `http://localhost:8001/docs`
- Create connections, trigger syncs, and search data

## 📦 SDKs

### Python

```bash
pip install airweave-sdk
```

```python
from airweave import AirweaveSDK

# Initialize client
client = AirweaveSDK(
    api_key="YOUR_API_KEY",
    base_url="http://localhost:8001"
)

# Create a collection
collection = client.collections.create(name="My Collection")

# Add a source connection
source = client.source_connections.create(
    name="My Stripe Connection",
    short_name="stripe",
    readable_collection_id=collection.readable_id,
    authentication={
        "credentials": {"api_key": "your_stripe_api_key"}
    }
)

# Semantic search (default)
results = client.collections.search(
    readable_id=collection.readable_id,
    query="Find recent failed payments"
)

# Hybrid search (semantic + keyword)
results = client.collections.search(
    readable_id=collection.readable_id,
    query="customer invoices Q4 2024",
    search_type="hybrid"
)

# With query expansion and reranking
results = client.collections.search(
    readable_id=collection.readable_id,
    query="technical documentation",
    enable_query_expansion=True,
    enable_reranking=True,
    top_k=20
)

# Search with recency bias (prioritize recent results)
results = client.collections.search(
    readable_id=collection.readable_id,
    query="critical bugs",
    recency_bias=0.8,  # 0.0 to 1.0, higher = more recent
    limit=10
)

# Get AI-generated answer instead of raw results
answer = client.collections.search(
    readable_id=collection.readable_id,
    query="What are our customer refund policies?",
    response_type="completion",
    enable_reranking=True
)
```

### TypeScript/JavaScript
```bash
npm install @airweave/sdk
# or
yarn add @airweave/sdk
```

```typescript
import { AirweaveSDKClient, AirweaveSDKEnvironment } from "@airweave/sdk";

// Initialize client
const client = new AirweaveSDKClient({
    apiKey: "YOUR_API_KEY",
    environment: AirweaveSDKEnvironment.Local
});

// Create a collection
const collection = await client.collections.create({
    name: "My Collection"
});

// Add a source connection
const source = await client.sourceConnections.create({
    name: "My Stripe Connection",
    shortName: "stripe",
    readableCollectionId: collection.readableId,
    authentication: {
        credentials: { apiKey: "your_stripe_api_key" }
    }
});

// Semantic search (default)
const results = await client.collections.search(
    collection.readableId,
    { query: "Find recent failed payments" }
);

// Hybrid search (semantic + keyword)
const hybridResults = await client.collections.search(
    collection.readableId,
    {
        query: "customer invoices Q4 2024",
        searchType: "hybrid"
    }
);

// With query expansion and reranking
const advancedResults = await client.collections.search(
    collection.readableId,
    {
        query: "technical documentation",
        enableQueryExpansion: true,
        enableReranking: true,
        topK: 20
    }
);

// Search with recency bias (prioritize recent results)
const recentResults = await client.collections.search(
    collection.readableId,
    {
        query: "critical bugs",
        recencyBias: 0.8,  // 0.0 to 1.0, higher = more recent
        limit: 10
    }
);

// Get AI-generated answer instead of raw results
const answer = await client.collections.search(
    collection.readableId,
    {
        query: "What are our customer refund policies?",
        responseType: "completion",
        enableReranking: true
    }
);
```

## 🔑 Key Features

- **Data synchronization** from 30+ sources with minimal config
- **Entity extraction** and transformation pipeline
- **Multi-tenant** architecture with OAuth2
- **Incremental updates** using content hashing
- **Semantic search** for agent queries
- **Versioning** for data changes

## 🔧 Tech Stack

- **Frontend**: React/TypeScript with ShadCN
- **Backend**: FastAPI (Python)
- **Databases**: PostgreSQL (metadata), Qdrant (vectors)
- **Workers**: Temporal (workflow orchestration), Redis (pub/sub)
- **Deployment**: Docker Compose (dev), Kubernetes (prod)

## 👥 Contributing

We welcome contributions! Please check [CONTRIBUTING.md](https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md) for details.

## 📄 License

Airweave is released under the [MIT](LICENSE) license.

## 🔗 Connect

- **[Discord](https://discord.com/invite/484HY9Ehxt)** - Get help and discuss features
- **[GitHub Issues](https://github.com/airweave-ai/airweave/issues)** - Report bugs or request features
- **[Twitter](https://x.com/airweave_ai)** - Follow for updates
