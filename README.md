<p align="center">
  <a href="https://app.airweave.ai" target="_blank" rel="noopener noreferrer">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-airweave-darkbg.svg"/>
      <source media="(prefers-color-scheme: light)" srcset="frontend/public/logo-airweave-lightbg.svg"/>
      <img width="400" alt="Airweave" src="frontend/public/logo-airweave-darkbg.svg"/>
    </picture>
  </a>
</p>

<p align="center">Open-source context retrieval layer for AI agents and RAG systems.</p>

<p align="center">
  <a href="https://app.airweave.ai" target="_blank"><img src="https://img.shields.io/badge/Airweave_Cloud-0066FF" alt="Airweave Cloud"></a>
  <a href="https://docs.airweave.ai" target="_blank"><img src="https://img.shields.io/badge/Docs-0066FF" alt="Documentation"></a>
  <a href="https://x.com/airweave_ai" target="_blank"><img src="https://img.shields.io/twitter/follow/airweave_ai?style=social" alt="Twitter"></a>
</p>

<p align="center">
  <a href="https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml"><img src="https://github.com/airweave-ai/airweave/actions/workflows/ruff.yml/badge.svg" alt="Ruff"></a>
  <a href="https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml"><img src="https://github.com/airweave-ai/airweave/actions/workflows/eslint.yml/badge.svg" alt="ESLint"></a>
  <a href="https://github.com/airweave-ai/airweave/actions/workflows/test-public-api.yml"><img src="https://github.com/airweave-ai/airweave/actions/workflows/test-public-api.yml/badge.svg" alt="System Tests"></a>
  <a href="https://pepy.tech/projects/airweave-sdk"><img src="https://static.pepy.tech/badge/airweave-sdk" alt="PyPI Downloads"></a>
  <a href="https://discord.gg/gDuebsWGkn"><img src="https://img.shields.io/discord/1323415085011701870?label=Discord&logo=discord&logoColor=white&style=flat-square" alt="Discord"></a>
</p>

<p align="center">
  <video width="100%" src="https://github.com/user-attachments/assets/995e4a36-3f88-4d8e-b401-6ca43db0c7bf" controls></video>
</p>

### What is Airweave?
Airweave connects to your apps, tools, and databases, continuously syncs their data, and exposes it through a unified, LLM-friendly search interface. AI agents query Airweave to retrieve relevant, grounded, up-to-date context from multiple sources in a single request.

### Where it fits
Airweave sits between your data sources and AI systems as shared retrieval infrastructure. It handles authentication, ingestion, syncing, indexing, and retrieval so you don't have to rebuild fragile pipelines for every agent or integration.

### How it works
1. **Connect** your apps, databases, and documents (50+ integrations)
2. **Airweave** syncs, indexes, and exposes your data through a unified retrieval layer
3. **Agents query** Airweave via our SDKs, REST API, MCP, or native integrations with popular agent frameworks
4. **Agents retrieve** relevant, grounded context on demand

## Quickstart

### Cloud-hosted: [app.airweave.ai](https://app.airweave.ai)

<a href="https://app.airweave.ai"><img src="https://img.shields.io/badge/Open_Airweave_Cloud-0066FF" alt="Open Airweave Cloud"></a>

### Self-hosted

```bash
git clone https://github.com/airweave-ai/airweave.git
cd airweave
./start.sh
```

→ http://localhost:8080

> Requires Docker and docker-compose

## Supported Integrations

<!-- START_APP_GRID -->

<p align="center">
<img src="frontend/src/components/icons/apps/airtable.svg" alt="Airtable" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/asana.svg" alt="Asana" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/attio.svg" alt="Attio" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/bitbucket.svg" alt="Bitbucket" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/box.svg" alt="Box" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/clickup.svg" alt="ClickUp" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/confluence.svg" alt="Confluence" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/dropbox.svg" alt="Dropbox" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/github.svg" alt="Github" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/gitlab.svg" alt="Gitlab" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/gmail.svg" alt="Gmail" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/google_calendar.svg" alt="Google Calendar" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/google_docs.svg" alt="Google Docs" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/google_drive.svg" alt="Google Drive" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/hubspot.svg" alt="Hubspot" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/jira.svg" alt="Jira" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/linear.svg" alt="Linear" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/notion.svg" alt="Notion" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/onedrive.svg" alt="Onedrive" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/salesforce.svg" alt="Salesforce" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/sharepoint.svg" alt="Sharepoint" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/slack.svg" alt="Slack" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/stripe.svg" alt="Stripe" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/trello.svg" alt="Trello" width="40" height="40" style="margin: 6px;" />
<img src="frontend/src/components/icons/apps/zendesk.svg" alt="Zendesk" width="40" height="40" style="margin: 6px;" />
</p>

<!-- END_APP_GRID -->

<p align="center"><a href="https://docs.airweave.ai/connectors"><img src="https://img.shields.io/badge/View_all_integrations-0066FF" alt="View all integrations"></a></p>

## SDKs

```bash
pip install airweave-sdk        # Python
npm install @airweave/sdk       # TypeScript
```

```python
from airweave import AirweaveSDK

client = AirweaveSDK(api_key="YOUR_API_KEY")
results = client.collections.search(
    readable_id="my-collection",
    query="Find recent failed payments"
)
```

<a href="https://docs.airweave.ai"><img src="https://img.shields.io/badge/SDK_Documentation-0066FF" alt="SDK Documentation"></a>
<a href="https://github.com/airweave-ai/airweave/tree/main/examples"><img src="https://img.shields.io/badge/Example_Notebooks-0066FF" alt="Example Notebooks"></a>

## Tech Stack

- **Frontend**: [React/TypeScript](https://react.dev/) with [ShadCN](https://ui.shadcn.com/)
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Databases**: [PostgreSQL](https://www.postgresql.org/) (metadata), [Qdrant](https://qdrant.tech/) (vectors)
- **Workers**: [Temporal](https://temporal.io/) (orchestration), [Redis](https://redis.io/) (pub/sub)
- **Deployment**: [Docker Compose](https://docs.docker.com/compose/) (dev), [Kubernetes](https://kubernetes.io/) (prod)

## Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md).

## License

[MIT License](LICENSE)

<p align="center">
  <a href="https://discord.gg/gDuebsWGkn">Discord</a> ·
  <a href="https://github.com/airweave-ai/airweave/issues">Issues</a> ·
  <a href="https://x.com/airweave_ai">Twitter</a>
</p>
