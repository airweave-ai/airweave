import { defaultPaginationKeywords, defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: './openapi/internal-openapi.json',
  output: 'src/shared/api/generated',
  parser: {
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
