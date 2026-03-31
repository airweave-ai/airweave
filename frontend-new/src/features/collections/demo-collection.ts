import type { Collection } from '@/shared/api';

export const demoCollectionDescription =
  'Sample data to explore how retrieval works. Try querying it.';

const demoCollection: Collection = {
  id: 'demo-collection',
  name: "Tonik's First Collection",
  readable_id: 'toniks-first-collection',
  created_at: '2026-03-30T00:00:00.000Z',
  modified_at: '2026-03-30T00:00:00.000Z',
  organization_id: 'demo-organization',
  status: 'ACTIVE',
  vector_size: 1536,
  embedding_model_name: 'demo-embedding-model',
  source_connection_summaries: [
    {
      short_name: 'notion',
      name: 'Notion',
    },
    {
      short_name: 'slack',
      name: 'Slack',
    },
    {
      short_name: 'linear',
      name: 'Linear',
    },
  ],
};

export function useDemoCollection(): Collection {
  return demoCollection;
}
