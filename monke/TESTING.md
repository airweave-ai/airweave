# Running Monke Tests

## Quick Start

1. **Set up environment**
   ```bash
   cp env.test .env
   # Edit .env with your credentials
   ```

2. **Run a test**
   ```bash
   # Test Notion integration
   python test.py --config configs/notion.yaml

   # Test GitHub integration
   python test.py --config configs/github.yaml

   # Test Asana integration
   python test.py --config configs/asana.yaml
   ```

## Environment Setup

### Option 1: Direct Credentials
Add credentials directly to `env.test`:
```bash
# For GitHub
GITHUB_PERSONAL_ACCESS_TOKEN=your_token
GITHUB_REPO_NAME=owner/repo

# For Notion
NOTION_PERSONAL_ACCESS_TOKEN=secret_your_token

# For Asana
ASANA_PERSONAL_ACCESS_TOKEN=your_token
```

### Option 2: Composio Auth Provider
Use Composio for managed authentication:
```bash
DM_AUTH_PROVIDER=composio
DM_AUTH_PROVIDER_API_KEY=your_composio_api_key

# Source-specific account IDs
GITHUB_AUTH_PROVIDER_ACCOUNT_ID=ca_xxx
GITHUB_AUTH_PROVIDER_AUTH_CONFIG_ID=ac_xxx

NOTION_AUTH_PROVIDER_ACCOUNT_ID=ca_xxx
NOTION_AUTH_PROVIDER_AUTH_CONFIG_ID=ac_xxx
```

## Configuration Files

Test configurations are in `configs/`:
- `github.yaml` - GitHub source testing
- `notion.yaml` - Notion source testing
- `asana.yaml` - Asana source testing

## Test Flow

Each test runs through these steps:
1. **Create** - Creates test entities in the source
2. **Sync** - Syncs data to Airweave
3. **Verify** - Verifies data was synced correctly
4. **Update** - Updates test entities
5. **Sync** - Re-syncs updated data
6. **Verify** - Verifies updates
7. **Delete** - Deletes test entities (partial then complete)
8. **Verify** - Verifies deletions were detected

## Custom Environment File

Use a different environment file:
```bash
python test.py --config configs/notion.yaml --env .env.production
```

## Troubleshooting

- **Missing credentials**: Check your env file has all required tokens
- **Rate limits**: Adjust `rate_limit_delay_ms` in configs
- **Auth errors**: Verify tokens have correct permissions
- **Sync failures**: Check Airweave backend is running (`AIRWEAVE_API_URL`)
