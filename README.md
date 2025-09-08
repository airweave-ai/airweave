<picture>
  <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-and-lettermark-light.svg"/>
  <source media="(prefers-color-scheme: light)" srcset="frontend/public/logo-and-lettermark.svg"/>
  <img width="1673" alt="airweave-lettermark" style="padding-bottom: 12px;" src="frontend/public/logo-and-lettermark-light.svg"/>
</picture>

<div align="center">

[![Ruff](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml)
[![ESLint](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml)
[![Codecov](https://codecov.io/gh/airweave-ai/airweave/branch/main/graph/badge.svg)](https://codecov.io/gh/airweave-ai/airweave)
[![Discord](https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square)](https://discord.com/invite/484HY9Ehxt)
<br>
<div style="padding-top: 16px;">
<a href="https://trendshift.io/repositories/13748" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13748" alt="airweave-ai%2Fairweave | Trendshift" style="width: 250px; height: 55px; margin-right: 24px;" width="250" height="55"/></a>&nbsp;&nbsp;<a href="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app" target="_blank"><img src="https://www.ycombinator.com/launches/NX7-airweave-let-agents-search-any-app/upvote_embed.svg" alt="Launch YC: Airweave - Let Agents Search Any App" style="margin-left: 12px;"/></a>
</div>
</div>

## Overview

**Airweave is a tool that lets agents search any app.** It connects to apps, productivity tools, databases, or document stores and transforms their contents into searchable knowledge bases, accessible through a standardized interface for agents.

The search interface is exposed via REST API or MCP. When using MCP, Airweave essentially builds a semantically searchable MCP server. The platform handles everything from auth and extraction to embedding and serving.

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
  - [🔧 Technology Stack](#-technology-stack)
  - [🛣️ Roadmap](#️-roadmap)
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
  <div style="display: inline-block; text-align: center; padding: 4px;">
    <img src="frontend/src/components/icons/apps/asana.svg" alt="Asana" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/bitbucket.svg" alt="Bitbucket" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/calendly.svg" alt="Calendly" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/chat-gpt.svg" alt="Chat-gpt" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/clickup.svg" alt="Clickup" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/confluence.svg" alt="Confluence" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/ctti.svg" alt="Ctti" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/dropbox.svg" alt="Dropbox" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/elasticsearch.svg" alt="Elasticsearch" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/facebook.svg" alt="Facebook" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/github.svg" alt="Github" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/gmail.svg" alt="Gmail" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/google_calendar.svg" alt="Google Calendar" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/google_drive.svg" alt="Google Drive" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/hubspot.svg" alt="Hubspot" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/intercom.svg" alt="Intercom" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/jira.svg" alt="Jira" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/linear.svg" alt="Linear" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/linkedin.svg" alt="Linkedin" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/mailchimp.svg" alt="Mailchimp" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/monday.svg" alt="Monday" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/mysql.svg" alt="Mysql" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/notion.svg" alt="Notion" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/onedrive.svg" alt="Onedrive" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/oracle.svg" alt="Oracle" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/outlook_calendar.svg" alt="Outlook Calendar" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/outlook_mail.svg" alt="Outlook Mail" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/perplexity.svg" alt="Perplexity" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/postgresql.svg" alt="Postgresql" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/salesforce.svg" alt="Salesforce" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/slack.svg" alt="Slack" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/sql_server.svg" alt="Sql Server" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <span style="width: 40px; display: inline-block; margin: 4px;"></span><img src="frontend/src/components/icons/apps/sqlite.svg" alt="Sqlite" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/stripe.svg" alt="Stripe" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/todoist.svg" alt="Todoist" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/trello.svg" alt="Trello" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/whatsapp.svg" alt="Whatsapp" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/zendesk.svg" alt="Zendesk" width="40" height="40" style="margin: 4px; padding: 2px;" />
  </div>
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

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
    base_url="http://localhost:8001"
)
client.collections.create(
    name="name",
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

const client = new AirweaveSDKClient({
    apiKey: "YOUR_API_KEY",
    environment: AirweaveSDKEnvironment.Local
});
await client.collections.create({
    name: "name",
});
```

## 🔑 Key Features

- **Data synchronization** from 25+ sources with minimal config
- **Entity extraction** and transformation pipeline
- **Multi-tenant** architecture with OAuth2
- **Incremental updates** using content hashing
- **Semantic search** for agent queries
- **Versioning** for data changes
- **White-labeling** support for SaaS builders

## 🔧 Tech Stack

- **Frontend**: React/TypeScript with ShadCN
- **Backend**: FastAPI (Python)
- **Databases**: PostgreSQL (metadata), Qdrant (vectors)
- **Deployment**: Docker Compose (dev), Kubernetes (prod)

## 🛣️ Roadmap

- TBD

## 👥 Contributing

We welcome contributions! Please check [CONTRIBUTING.md](https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md) for details.

## 📄 License

Airweave is released under the [MIT](LICENSE) license.

## 🔗 Connect

- **[Discord](https://discord.com/invite/484HY9Ehxt)** - Get help and discuss features
- **[GitHub Issues](https://github.com/airweave-ai/airweave/issues)** - Report bugs or request features
- **[Twitter](https://x.com/airweave_ai)** - Follow for updates
