# Monke 🐒🥁 - Airweave Integration Testing Framework

**End-to-end testing framework for Airweave connectors using real API integrations**

## What is Monke?

Monke validates Airweave's data synchronization pipeline by creating real test data in external systems (GitHub, Notion, Asana, etc.), triggering syncs, and verifying the data appears correctly in the vector database.

The name: the **monke** (test orchestrator) plays the **bongo** (creates test data) to test the complete pipeline.

## Quick Start

```bash
# Test changed connectors (auto-detects from git diff)
./monke.sh

# Test specific connector
./monke.sh github

# Test multiple connectors in parallel
./monke.sh github asana notion

# Test all connectors
./monke.sh --all
```

The `monke.sh` script handles everything automatically:
- Creates Python virtual environment
- Installs dependencies
- Checks Airweave backend health
- Runs tests in parallel with progress UI
- Auto-detects changed connectors on feature branches

## Architecture Overview

### System Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                           MONKE FRAMEWORK                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  runner.py ──► Core Framework ──► Bongo ──► External API            │
│     │              │                │           │                   │
│     │              │                │           ▼                   │
│     │              │                │      (1) CREATE               │
│     │              │                │       Test Data               │
│     │              │                │                               │
│     │              ▼                │                               │
│     │         Test Config           │                               │
│     │         (YAML files)          │                               │
│     │                               │                               │
│     │              │                │                               │
│     │              ▼                ▼                               │
│     │         (2) TRIGGER ──► Airweave Backend                      │
│     │             Sync              │                               │
│     │                               ▼                               │
│     │                         (3) PULL DATA                         │
│     │                         from External API                     │
│     │                               │                               │
│     │                               ▼                               │
│     │                         (4) STORE in                          │
│     │                         Qdrant Vector DB                      │
│     │                               │                               │
│     └──────► (5) VERIFY ───────────►│                               │
│               Search & Check                                         │
│               Relevance Scores                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Core Concepts

#### 1. **Runner** (`runner.py`)
The main entry point that orchestrates everything. It:
- Parses command-line arguments
- Loads environment configuration
- Manages parallel test execution
- Provides Rich UI for local development or simple output for CI

#### 2. **Core Framework** (`core/`)
The brain of the testing system:

```
core/
├── config.py   # Parses YAML configs into TestConfig objects
├── flow.py     # Orchestrates the test flow (setup→test→cleanup)
├── steps.py    # Individual test steps (Create, Update, Delete, Verify)
├── runner.py   # Coordinates test execution and results
└── events.py   # Event bus for real-time progress updates
```

**TestFlow** executes this sequence:
```
Setup Phase       Create Phase      Update Phase      Delete Phase      Cleanup
    │                 │                 │                 │                │
    ▼                 ▼                 ▼                 ▼                ▼
┌────────┐      ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌─────────┐
│Create  │      │Create    │     │Update    │     │Delete    │     │Delete   │
│Test    │ ───► │Entities  │ ──► │Entities  │ ──► │Entities  │ ──► │Test     │
│Collection│     │via API   │     │via API   │     │via API   │     │Collection│
└────────┘      └──────────┘     └──────────┘     └──────────┘     └─────────┘
                      │                 │                 │
                      ▼                 ▼                 ▼
                ┌──────────┐     ┌──────────┐     ┌──────────┐
                │Sync &    │     │Sync &    │     │Sync &    │
                │Verify    │     │Verify    │     │Verify    │
                └──────────┘     └──────────┘     └──────────┘
```

#### 3. **Bongos** (`bongos/`)
Bongos are the API integrators that create real test data:

```python
class GitHubBongo(BaseBongo):
    connector_type = "github"  # Must match config filename

    async def create_entities(self):
        # Creates test files in GitHub repo

    async def update_entities(self):
        # Updates those files

    async def delete_entities(self):
        # Deletes the files

    async def cleanup(self):
        # Ensures everything is cleaned up
```

Each bongo:
- Inherits from `BaseBongo`
- Implements the four lifecycle methods
- Handles rate limiting and retries
- Tracks created entities for cleanup

#### 4. **Test Configurations** (`configs/`)
YAML files that define test parameters:

```yaml
name: github
connector_type: github
auth_provider: direct  # or 'composio'

config_fields:
  entity_count: 5          # How many test entities to create
  rate_limit_delay_ms: 1000  # API rate limiting
  test_branch: monke-test    # GitHub-specific config

deletion:
  partial_delete_count: 2    # Delete 2 entities first
  verify_partial_deletion: true  # Then verify they're gone
```

#### 5. **Generation** (`generation/`)
Content generators that create realistic test data:

```
generation/
├── schemas/          # Pydantic models for data structures
│   └── github.py    # GitHubFile, GitHubContent, etc.
└── github.py        # generate_github_content() using LLM
```

The generator:
- Uses OpenAI to create realistic content
- Embeds unique tokens for tracking
- Returns structured data for the bongo

### Authentication Flow with Composio

When tests run, the authentication flow works as follows:

```
Test Start
    │
    ▼
┌──────────────────┐
│ Check for        │
│ DM_AUTH_PROVIDER │
└──────────────────┘
    │
    ├─── "composio" ────────────────────┐
    │                                   ▼
    │                        ┌─────────────────────┐
    │                        │ Connect to Composio │
    │                        │ using API key       │
    │                        └─────────────────────┘
    │                                   │
    │                                   ▼
    │                        ┌─────────────────────┐
    │                        │ Get Auth Provider ID│
    │                        │ Store in env var    │
    │                        └─────────────────────┘
    │                                   │
    │                                   ▼
    │                        ┌─────────────────────┐
    │                        │ Use Composio for    │
    │                        │ all API calls       │
    │                        └─────────────────────┘
    │
    └─── "direct" or unset ─────────────┐
                                        ▼
                             ┌─────────────────────┐
                             │ Use direct tokens   │
                             │ from environment    │
                             └─────────────────────┘
```

This means:
- **Local dev**: Can use either Composio or direct tokens
- **CI/CD**: Always uses Composio for security
- **Production**: Will use Composio with service accounts

### Test Verification Strategy

The framework verifies data synchronization using semantic search:

```
Created Entity                  After Sync                    Verification
─────────────                   ──────────                    ────────────

File: test_abc.py     ──────►   Airweave pulls     ──────►   Search Qdrant:
Token: "xyz789"                  and indexes                  Query: "xyz789"
                                      │
                                      ▼                       Expected:
                                 Vector stored                Score ≥ 0.8
                                 in Qdrant                    (high relevance)
```

**Scoring thresholds:**
- `≥ 0.8` = Entity exists (creation/update successful)
- `< 0.3` = Entity deleted (deletion successful)
- Between = Uncertain state (test fails)

## Project Structure

```
monke/
├── 🎯 runner.py                # Unified test runner (entry point)
├── 🐚 monke.sh                 # Shell wrapper with auto-setup
│
├── 🧠 core/                    # Core framework
│   ├── config.py               # Configuration management
│   ├── flow.py                 # Test flow orchestration
│   ├── steps.py                # Test step implementations
│   ├── runner.py               # Test execution coordinator
│   └── events.py               # Event bus for progress updates
│
├── 🥁 bongos/                  # External API integrations
│   ├── base_bongo.py           # Abstract base class
│   ├── registry.py             # Auto-discovery system
│   ├── github.py               # GitHub API integration
│   ├── notion.py               # Notion API integration
│   ├── asana.py                # Asana API integration
│   └── ...                     # Other connectors
│
├── 🎨 generation/              # Test data generators
│   ├── schemas/                # Data models (Pydantic)
│   └── {connector}.py          # Content generators using LLM
│
├── ⚙️ configs/                 # Test configurations
│   └── {connector}.yaml        # One config per connector
│
├── 🔐 auth/                    # Authentication handling
│   ├── broker.py               # Auth provider interface
│   └── credentials_resolver.py # Credential resolution logic
│
└── 📝 env.test                 # Environment template
```

## Authentication & Credentials

### Understanding Composio

Composio is our authentication container that manages OAuth connections to external services. Instead of storing raw API tokens, Composio handles:
- OAuth flows and token refresh
- Credential encryption and storage
- Multi-tenant authentication
- Connection lifecycle management

In both local development and CI/CD, we use Composio to securely manage connector credentials:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Monke     │────►│   Composio   │────►│ External    │
│   Tests     │     │   Auth       │     │ APIs        │
│             │     │   Provider   │     │ (GitHub,    │
│             │     │              │     │  Notion,    │
│             │     │ • Stores     │     │  etc.)      │
│             │     │   OAuth      │     │             │
│             │     │   tokens     │     │             │
│             │     │ • Refreshes  │     │             │
│             │     │   expired    │     │             │
│             │     │   tokens     │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

### Setting Up Credentials

#### 1. Copy the template
```bash
cp monke/env.test monke/.env
```

#### 2. Configure authentication

**For Local Development (with Composio):**
```bash
# Core settings
AIRWEAVE_API_URL=http://localhost:8001
OPENAI_API_KEY=sk-...

# Composio configuration
DM_AUTH_PROVIDER=composio
DM_AUTH_PROVIDER_API_KEY=your_composio_api_key

# Per-connector Composio configs
GITHUB_AUTH_PROVIDER_ACCOUNT_ID=ca_xxx
GITHUB_AUTH_PROVIDER_AUTH_CONFIG_ID=ac_xxx
NOTION_AUTH_PROVIDER_ACCOUNT_ID=ca_xxx
NOTION_AUTH_PROVIDER_AUTH_CONFIG_ID=ac_xxx
```

**For Direct Credentials (simpler but less secure):**
```bash
# If not using Composio, provide tokens directly
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
GITHUB_REPO_NAME=owner/repo
NOTION_ACCESS_TOKEN=secret_...
ASANA_PERSONAL_ACCESS_TOKEN=1/...
```

### CI/CD Environment

In GitHub Actions, Composio credentials are injected as secrets:

```yaml
# .github/workflows/monke.yml
env:
  # Composio auth provider
  DM_AUTH_PROVIDER: composio
  DM_AUTH_PROVIDER_API_KEY: ${{ secrets.COMPOSIO_API_KEY }}

  # Connector-specific Composio configs
  GITHUB_AUTH_PROVIDER_ACCOUNT_ID: ${{ secrets.GITHUB_AUTH_PROVIDER_ACCOUNT_ID }}
  GITHUB_AUTH_PROVIDER_AUTH_CONFIG_ID: ${{ secrets.GITHUB_AUTH_PROVIDER_AUTH_CONFIG_ID }}

  # Other connectors...
  GMAIL_AUTH_PROVIDER_ACCOUNT_ID: ${{ secrets.GMAIL_AUTH_PROVIDER_ACCOUNT_ID }}
  GOOGLE_DRIVE_AUTH_PROVIDER_ACCOUNT_ID: ${{ secrets.GOOGLE_DRIVE_AUTH_PROVIDER_ACCOUNT_ID }}
```

The runner automatically:
1. Detects Composio configuration
2. Connects to Composio API
3. Retrieves auth provider ID
4. Uses it for all subsequent API calls

## Writing a New Connector

### Step 1: Create the Bongo
`monke/bongos/myapp.py`:

```python
from monke.bongos.base_bongo import BaseBongo

class MyAppBongo(BaseBongo):
    connector_type = "myapp"  # MUST match config filename

    async def create_entities(self):
        """Create test data via MyApp API."""
        entities = []
        for i in range(self.entity_count):
            # 1. Generate content
            content = await generate_myapp_content()

            # 2. Create via API
            response = await self.api_client.post("/items", json=content)

            # 3. Track for verification
            entities.append({
                "id": response["id"],
                "name": response["title"],
                "expected_content": unique_token
            })

        self.created_entities = entities
        return entities

    async def update_entities(self):
        """Update subset of entities."""
        # Update first 3 entities...

    async def delete_entities(self):
        """Delete all entities."""
        # Delete via API...

    async def cleanup(self):
        """Force cleanup any remaining artifacts."""
        # Ensure everything is gone...
```

### Step 2: Create the Generator
`monke/generation/myapp.py`:

```python
from monke.client.llm import LLMClient

async def generate_myapp_content(token: str):
    """Generate test content with embedded token."""
    llm = LLMClient()
    prompt = f"Generate test content. Include '{token}' naturally."
    return await llm.generate(prompt)
```

### Step 3: Create the Config
`monke/configs/myapp.yaml`:

```yaml
name: myapp
connector_type: myapp
auth_provider: direct

auth_fields:
  - api_key

config_fields:
  entity_count: 5
  rate_limit_delay_ms: 500
```

### Step 4: Test
```bash
./monke.sh myapp
```

## Advanced Usage

### Parallel Testing
```bash
# Control concurrency
MONKE_MAX_PARALLEL=10 ./monke.sh --all

# Or via CLI
python monke/runner.py --all --max-concurrency 10
```

### CI/CD Integration
```yaml
# GitHub Actions
- name: Run Tests
  env:
    CI: true  # Disables Rich UI
  run: |
    cd monke
    python runner.py --all
```

### Debug Mode
```bash
# Verbose output
MONKE_VERBOSE=1 ./monke.sh github

# Check logs
tail -f monke/logs/latest.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Backend not accessible" | Run `./start.sh` to start Airweave |
| "No credentials found" | Check `.env` file has required tokens |
| "Rate limit exceeded" | Increase `rate_limit_delay_ms` in config |
| "Low relevance scores" | Verify `OPENAI_API_KEY` is set |
| "Sync timeout" | Check Temporal workers are running |

### Manual Cleanup

If tests fail and leave artifacts:

```python
from airweave import AirweaveSDK

client = AirweaveSDK()
for collection in client.collections.list():
    if collection.name.startswith("monke-"):
        client.collections.delete(collection.id)
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AIRWEAVE_API_URL` | Backend URL | `http://localhost:8001` |
| `MONKE_MAX_PARALLEL` | Max concurrent tests | `5` |
| `MONKE_ENV_FILE` | Environment file | `monke/env.test` |
| `MONKE_NO_VENV` | Skip venv setup | `false` |
| `MONKE_VERBOSE` | Verbose output | `false` |
| `CI` | CI mode (simple output) | Auto-detected |

---

**Happy Testing! 🐒🥁✨**
