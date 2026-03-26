//  @ts-check

import { tanstackConfig } from '@tanstack/eslint-config';

export default [
  {
    ignores: ['dist/**', 'src/shared/api/generated/**'],
  },
  ...tanstackConfig,
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                '@/app',
                '@/app/*',
                '@/features',
                '@/features/*',
                '@/routes',
                '@/routes/*',
              ],
              message: 'shared must not depend on app, features, or routes.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['src/features/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/app', '@/app/*', '@/routes', '@/routes/*'],
              message: 'features must not depend on app or routes.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['src/app/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/routes', '@/routes/*'],
              message: 'app code must not import route definitions directly.',
            },
          ],
        },
      ],
    },
  },
];
