import type { CollectionSearchConfig } from './collection-search-model';

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
  config,
  query,
}: {
  collectionId: string;
  config: CollectionSearchConfig;
  query: string;
}): Record<CollectionCodeSnippetLanguage, CollectionCodeSnippet> {
  const { tier } = config;
  const snippetQuery = query.trim() || SEARCH_QUERY;
  const queryLiteral = JSON.stringify(snippetQuery);
  const nodeMethod =
    tier === 'instant'
      ? 'search.instant'
      : tier === 'agentic'
        ? 'search.agentic'
        : 'search.classic';
  const pythonMethod =
    tier === 'instant'
      ? 'search.instant'
      : tier === 'agentic'
        ? 'search.agentic'
        : 'search.classic';
  const nodeRequestLines = [`    query: ${queryLiteral}`];
  const pythonRequestLines = [`    query=${queryLiteral}`];

  if (tier === 'instant') {
    nodeRequestLines.push(
      `    retrieval_strategy: "${config.instant.retrievalStrategy}"`,
    );
    pythonRequestLines.push(
      `    retrieval_strategy="${config.instant.retrievalStrategy}"`,
    );
  }

  if (tier === 'agentic') {
    nodeRequestLines.push(`    thinking: ${String(config.agentic.thinking)}`);
    pythonRequestLines.push(
      `    thinking=${config.agentic.thinking ? 'True' : 'False'}`,
    );
  }

  if (config.filter.length > 0) {
    nodeRequestLines.push(formatNodeRequestProperty('filter', config.filter));
    pythonRequestLines.push(
      formatPythonRequestProperty('filter', config.filter),
    );
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
${nodeRequestLines.join(',\n')}
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
${pythonRequestLines.join(',\n')}
)`,
      responseCode: tierPythonResponseSnippets[tier],
    },
  };
}

function formatNodeRequestProperty(name: string, value: unknown) {
  const literal = JSON.stringify(value, null, 2);

  return literal
    .split('\n')
    .map((line, index) =>
      index === 0 ? `    ${name}: ${line}` : `    ${line}`,
    )
    .join('\n');
}

function formatPythonRequestProperty(name: string, value: unknown) {
  const literal = formatPythonLiteral(value);

  return literal
    .split('\n')
    .map((line, index) =>
      index === 0 ? `    ${name}=${line}` : `    ${line}`,
    )
    .join('\n');
}

function formatPythonLiteral(value: unknown, indentLevel = 0): string {
  const indent = '  '.repeat(indentLevel);
  const childIndent = '  '.repeat(indentLevel + 1);

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '[]';
    }

    return `[
${value
  .map((item) => `${childIndent}${formatPythonLiteral(item, indentLevel + 1)}`)
  .join(',\n')}
${indent}]`;
  }

  if (isPythonLiteralObject(value)) {
    const entries = Object.entries(value);

    if (entries.length === 0) {
      return '{}';
    }

    return `{
${entries
  .map(
    ([key, entryValue]) =>
      `${childIndent}${JSON.stringify(key)}: ${formatPythonLiteral(entryValue, indentLevel + 1)}`,
  )
  .join(',\n')}
${indent}}`;
  }

  if (typeof value === 'string') {
    return JSON.stringify(value);
  }

  if (typeof value === 'number') {
    return String(value);
  }

  if (typeof value === 'boolean') {
    return value ? 'True' : 'False';
  }

  return 'None';
}

function isPythonLiteralObject(
  value: unknown,
): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
