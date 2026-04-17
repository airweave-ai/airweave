export type CollectionCodeSnippetLanguage = 'node' | 'python';
export type CollectionCodeSnippetTier = 'agentic' | 'classic' | 'instant';

export interface CollectionCodeSnippet {
  requestCode: string;
  responseCode: string;
}

const SEARCH_QUERY = 'Ask a question about your data';

const tierResponseSnippets: Record<CollectionCodeSnippetTier, string> = {
  agentic: `const response = {
  results: [
    {
      entity_id: "doc_123",
      name: "Q1 Product Spec",
      relevance_score: 0.98,
      source_name: "notion",
      url: "https://www.notion.so/q1-product-spec",
    },
  ],
  completion: "The Q1 roadmap prioritizes onboarding, retrieval latency, and audit logging.",
};`,
  classic: `const response = {
  results: [
    {
      entity_id: "doc_123",
      name: "Q1 Product Spec",
      relevance_score: 0.98,
      source_name: "notion",
      url: "https://www.notion.so/q1-product-spec",
    },
  ],
};`,
  instant: `const response = {
  results: [
    {
      entity_id: "doc_123",
      name: "Q1 Product Spec",
      relevance_score: 0.98,
      source_name: "notion",
      url: "https://www.notion.so/q1-product-spec",
    },
  ],
};`,
};

const tierPythonResponseSnippets: Record<CollectionCodeSnippetTier, string> = {
  agentic: `{
    "results": [
        {
            "entity_id": "doc_123",
            "name": "Q1 Product Spec",
            "relevance_score": 0.98,
            "source_name": "notion",
            "url": "https://www.notion.so/q1-product-spec",
        },
    ],
    "completion": "The Q1 roadmap prioritizes onboarding, retrieval latency, and audit logging.",
}`,
  classic: `{
    "results": [
        {
            "entity_id": "doc_123",
            "name": "Q1 Product Spec",
            "relevance_score": 0.98,
            "source_name": "notion",
            "url": "https://www.notion.so/q1-product-spec",
        },
    ],
}`,
  instant: `{
    "results": [
        {
            "entity_id": "doc_123",
            "name": "Q1 Product Spec",
            "relevance_score": 0.98,
            "source_name": "notion",
            "url": "https://www.notion.so/q1-product-spec",
        },
    ],
}`,
};

export function createCollectionCodeSnippets({
  collectionId,
  tier,
}: {
  collectionId: string;
  tier: CollectionCodeSnippetTier;
}): Record<CollectionCodeSnippetLanguage, CollectionCodeSnippet> {
  const nodeMethod =
    tier === 'instant'
      ? 'searchInstant'
      : tier === 'agentic'
        ? 'searchAgentic'
        : 'searchClassic';
  const pythonMethod =
    tier === 'instant'
      ? 'search_instant'
      : tier === 'agentic'
        ? 'search_agentic'
        : 'search_classic';
  const nodeRequestLines = [`      query: "${SEARCH_QUERY}"`];
  const pythonRequestLines = [`        "query": "${SEARCH_QUERY}"`];

  if (tier === 'instant') {
    nodeRequestLines.push('      retrievalStrategy: "hybrid"');
    pythonRequestLines.push('        "retrieval_strategy": "hybrid"');
  }

  if (tier === 'agentic') {
    nodeRequestLines.push('      thinking: true');
    pythonRequestLines.push('        "thinking": True');
  }

  return {
    node: {
      requestCode: `import { AirweaveSDKClient } from "@airweave/sdk";

const client = new AirweaveSDKClient({
  apiKey: "YOUR_API_KEY",
});

const response = await client.collections.${nodeMethod}(
  "${collectionId}",
  {
    request: {
${nodeRequestLines.join(',\n')}
    },
  },
);`,
      responseCode: tierResponseSnippets[tier],
    },
    python: {
      requestCode: `from airweave import AirweaveSDK

client = AirweaveSDK(
    api_key="YOUR_API_KEY",
)

response = client.collections.${pythonMethod}(
    readable_id="${collectionId}",
    request={
${pythonRequestLines.join(',\n')}
    },
)`,
      responseCode: tierPythonResponseSnippets[tier],
    },
  };
}
