<img width="1673" alt="airweave-lettermark" style="padding-bottom: 12px;" src="https://github.com/user-attachments/assets/e79a9af7-2e93-4888-9cf4-0f700f19fe05"/>


<div align="center">

[![Ruff](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml)
[![ESLint](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg)](https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml)
[![Backend Tests](https://github.com/airweave-ai/airweave/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/airweave-ai/airweave/actions/workflows/tests.yml)
[![Codecov](https://codecov.io/gh/airweave-ai/airweave/branch/main/graph/badge.svg)](https://codecov.io/gh/airweave-ai/airweave)
[![Discord](https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square)](https://discord.com/invite/484HY9Ehxt)

</div>

Turn any app into a semantic MCP server for AI agents. **Airweave** connects any app, database, URL, or API and makes it semantically searchable for agents.

### 🎥 Demo
https://github.com/user-attachments/assets/abdf85cb-a8f5-4b6c-b5a3-d4b5177e6bda


## Overview

Airweave simplifies the process of making information retrievable for your agent.

Whether you have structured or unstructured data, Airweave helps you break it into processable entities, store the data and make it retrievable through [REST and MCP endpoints](https://docs.airweave.ai).

---

## Table of Contents

- [Table of Contents](#table-of-contents)
- [Overview](#overview)
- [Quick Start](#quick-start)
  - [Steps](#steps)
- [Usage](#usage)
  - [Frontend](#frontend)
  - [API Endpoints (FastAPI)](#api-endpoints-fastapi)
- [Integrations - adding more every day!](#integrations---adding-more-every-day)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)
- [Contact \& Community](#contact--community)




## Quick Start

Below is a simple guide to get Airweave up and running locally. For more detailed instructions, refer to the [docs](https://docs.airweave.ai).


### Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/airweave-ai/airweave.git
   cd airweave
   ```

2. **Build and Run**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

That's it!

You now have Airweave running locally. You can log in to the dashboard, add a connection, configure your sync schedule and find information on your apps.


## Usage

To use Airweave, you can either use the frontend or the API.


### Frontend
- Access the React UI at `http://localhost:8080`.
- Navigate to Sources to add new integrations.
- Set up or view your sync schedules under Schedules.
- Monitor sync jobs in Jobs.

### API Endpoints (FastAPI)
- **Swagger Documentation:** `http://localhost:8001/docs`
- **Get All Sources:** `GET /sources`
- **Connect a Source:** `POST /connections/{short_name}`
- **Find information:**: `POST /search`


You can configure your own vector database in the app UI or via the API.
---

## Integrations - adding more every day!

<!-- START_APP_GRID -->

<p align="center">
  <div style="display: inline-block; text-align: center; padding: 4px;">
    <img src="frontend/src/components/icons/apps/asana.svg" alt="Asana" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/calendly.svg" alt="Calendly" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/chat-gpt.svg" alt="Chat-gpt" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/clickup.svg" alt="Clickup" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/confluence.svg" alt="Confluence" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/dropbox.svg" alt="Dropbox" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/facebook.svg" alt="Facebook" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/github.svg" alt="Github" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/gmail.svg" alt="Gmail" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/google_calendar.svg" alt="Google Calendar" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/google_drive.svg" alt="Google Drive" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/hubspot.svg" alt="Hubspot" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/intercom.svg" alt="Intercom" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/jira.svg" alt="Jira" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/linear.svg" alt="Linear" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/linkedin.svg" alt="Linkedin" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/mailchimp.svg" alt="Mailchimp" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/monday.svg" alt="Monday" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/mysql.svg" alt="Mysql" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/notion.svg" alt="Notion" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/onedrive.svg" alt="Onedrive" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/oracle.svg" alt="Oracle" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/outlook_calendar.svg" alt="Outlook Calendar" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/outlook_mail.svg" alt="Outlook Mail" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <img src="frontend/src/components/icons/apps/perplexity.svg" alt="Perplexity" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/postgresql.svg" alt="Postgresql" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/salesforce.svg" alt="Salesforce" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/slack.svg" alt="Slack" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/sql_server.svg" alt="Sql Server" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/sqlite.svg" alt="Sqlite" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/stripe.svg" alt="Stripe" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/todoist.svg" alt="Todoist" width="40" height="40" style="margin: 4px; padding: 2px;" />
    <span style="width: 40px; display: inline-block; margin: 4px;"></span><span style="width: 40px; display: inline-block; margin: 4px;"></span><img src="frontend/src/components/icons/apps/trello.svg" alt="Trello" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/whatsapp.svg" alt="Whatsapp" width="40" height="40" style="margin: 4px; padding: 2px;" /><img src="frontend/src/components/icons/apps/zendesk.svg" alt="Zendesk" width="40" height="40" style="margin: 4px; padding: 2px;" />
  </div>
</p>

<!-- END_APP_GRID -->


---

## Key Features
- **Over 25 integrations and counting**: Airweave is your one-stop shop for building agents that need to find information in a single queryable layer.
- **Simplicity**: Minimal configuration needed to find information in diverse sources: APIs, databases, apps and more.
- **Extensibility**: Easily add new source and embedder integrations with our
- **White-Labeled Multi-Tenant Support**: Ideal for SaaS builders, Airweave provides a streamlined OAuth2-based platform for syncing data across multiple tenants while maintaining privacy and security.
- **Entity Generators**: Each source (like a database, API, or file system) defines a `async def generate_entities()` that yields data in a consistent format. You can also define your own.
- **Automated Sync**: Schedule data synchronization or run on-demand sync jobs.
- **Versioning & Hashing**: Airweave detects changes in your data via hashing, updating only the modified entities.
- **Async-First**: Built to handle large-scale data synchronization asynchronously (upcoming: managed Redis workers for production scale).
- **Scalable**: Deploy locally via Docker Compose for development (upcoming: deploy with Kubernetes for production scale)


## Technology Stack

- **Frontend**: [React](https://reactjs.org/) (JavaScript/TypeScript)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Infrastructure**:
  - Local / Dev: [Docker Compose](https://docs.docker.com/compose/)
  - Production: (upcoming) [Kubernetes](https://kubernetes.io/)
- **Databases**:
  - [PostgreSQL](https://www.postgresql.org/) for relational data
  - Vector database: [Qdrant](https://qdrant.tech/)
- **Asynchronous Tasks**: [ARQ](https://arq-docs.helpmanual.io/) Redis for background workers

---

## Contributing

We welcome all contributions! Whether you're fixing a bug, improving documentation, or adding a new feature:

Please follow the existing code style and conventions. See [CONTRIBUTING.md](https://github.com/airweave-ai/airweave/blob/main/CONTRIBUTING.md) for more details.

---

## Roadmap

- **Additional Integrations**: Expand entity generators for popular SaaS APIs and databases.
- **Redis & Worker Queues**: Improved background job processing and caching for large or frequent syncs.
- **Webhooks**: Trigger syncs on external events (e.g., new data in a database).
- **Kubernetes Support**: Offer easy Helm charts for production-scale deployments.
- **Commercial Offerings**: Enterprise features, extended metrics, and priority support.

---

## License

Airweave is released under an open-core model. The community edition is licensed under the [MIT](LICENSE). Additional modules (for enterprise or advanced features) may be licensed separately.


## Contact & Community
- **Discord**: Join our Discord channel [here](https://discord.com/invite/484HY9Ehxt) to get help or discuss features.
- **GitHub Issues**: Report bugs or request new features in GitHub Issues.
- **Twitter**: Follow [@airweave_ai](https://x.com/airweave_ai) for updates.

That's it! We're looking forward to seeing what you build. If you have any questions, please don't hesitate to open an issue or reach out on Discord.
