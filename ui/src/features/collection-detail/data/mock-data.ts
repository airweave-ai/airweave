import type { Collection, Model } from './types'

export const collection: Collection = {
  id: 'anands-collection-4m6pbv',
  name: "Anand's collection 123",
  status: 'active',
  sources: [
    { name: 'Notion Connection', slug: 'makenotion', connected: true },
    { name: 'Asana Connection', slug: 'asana', connected: true },
    { name: 'Linear Connection', slug: 'linear', connected: true },
  ],
  schedule: 'Daily 2:29pm (Now)',
  lastSync: '23h ago',
  entities: {
    total: 0,
    types: [
      { name: 'NotionDatabase', count: 0 },
      { name: 'NotionFile', count: 0 },
      { name: 'NotionPage', count: 0 },
      { name: 'NotionProperty', count: 0 },
    ],
  },
}

export const askSuggestions = [
  'How do I search this collection?',
  'How do I add more sources?',
  'What entity types are available?',
]

export const models: Model[] = [
  { id: 'gpt-5.2', name: 'GPT-5.2', provider: 'OpenAI' },
  { id: 'claude-opus-4.5', name: 'Claude Opus 4.5', provider: 'Anthropic' },
  { id: 'claude-sonnet-4.5', name: 'Claude Sonnet 4.5', provider: 'Anthropic' },
  { id: 'gemini-3-pro', name: 'Gemini 3 Pro', provider: 'Google' },
]

export const defaultSuggestions = [
  'How do I connect a data source?',
  'What integrations are available?',
  'How do I create a sync?',
  'Explain the data pipeline',
]

export const mockResponses: Record<string, string> = {
  'How do I connect a data source?': `## Connecting a Data Source

To connect a data source in Airweave:

1. Navigate to **Sources** in the sidebar
2. Click **Add Source** to see available integrations
3. Select your data source type (API, Database, etc.)
4. Enter your credentials and configure the connection
5. Test the connection to verify it works

Would you like me to explain any specific data source?`,
  'What integrations are available?': `## Available Integrations

Airweave supports many popular integrations:

**APIs & Services**
- REST APIs
- GraphQL endpoints
- Webhooks

**Databases**
- PostgreSQL
- MySQL
- MongoDB

**Cloud Services**
- AWS S3
- Google Cloud
- Azure Blob

Check the **Sources** page for the complete list!`,
  'How do I create a sync?': `## Creating a Sync

To create a sync between data sources:

1. Go to **Syncs** in the navigation
2. Click **New Sync**
3. Select your source and destination
4. Configure mapping rules
5. Set the sync schedule (real-time, hourly, daily)
6. Save and activate the sync

The sync will begin automatically based on your schedule.`,
  'Explain the data pipeline': `## Airweave Data Pipeline

The data pipeline consists of:

**1. Sources**
Connect to your data origins (APIs, databases, files)

**2. Transformations**
Apply rules to clean and format your data

**3. Destinations**
Send processed data to target systems

**4. Monitoring**
Track sync status, errors, and performance

Each step is configurable and can be monitored in real-time.`,
}

export const fallbackResponses = [
  `That's a great question! Airweave makes it easy to connect and sync your data. You can explore the **Sources** page to see available integrations, or check the **Syncs** section to manage your data flows.`,
  `I'd be happy to help with that! For detailed information, you can check the documentation or explore the sidebar navigation to find the relevant section.`,
  `Good question! Airweave provides flexible options for data integration. Feel free to explore the interface or ask about specific features.`,
]
