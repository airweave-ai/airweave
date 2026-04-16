import { defaultPaginationKeywords, defineConfig } from '@hey-api/openapi-ts';

const collectionSearchQueryPaths = new Set([
  '/collections/{readable_id}/search/instant',
  '/collections/{readable_id}/search/classic',
  '/collections/{readable_id}/search/agentic',
  '/collections/{readable_id}/search/agentic/stream',
]);

export default defineConfig({
  input: './openapi/internal-openapi.json',
  output: 'src/shared/api/generated',
  parser: {
    hooks: {
      operations: {
        getKind: (operation) => {
          if (
            operation.method === 'post' &&
            collectionSearchQueryPaths.has(operation.path)
          ) {
            return ['query'];
          }
        },
      },
    },
    pagination: {
      keywords: [...defaultPaginationKeywords, 'skip', 'limit'],
    },
  },
  plugins: [
    '@hey-api/typescript',
    '@hey-api/sdk',
    {
      name: '@hey-api/client-fetch',
      runtimeConfigPath: '../client.ts',
    },
    {
      name: '@tanstack/react-query',
      queryOptions: true,
      queryKeys: {
        enabled: true,
        tags: true,
      },
      mutationOptions: true,
      infiniteQueryOptions: true,
      infiniteQueryKeys: true,
      useQuery: false,
      useMutation: false,
    },
  ],
});
