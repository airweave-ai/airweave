/**
 * Available feature flags in Airweave.
 * Must match backend FeatureFlag enum exactly.
 */
export const FeatureFlags = {
  // Storage & Infrastructure
  S3_DESTINATION: 's3_destination',

  // Search & Query
  ADVANCED_SEARCH: 'advanced_search',

  // Platform Features
  CUSTOM_ENTITIES: 'custom_entities',
  WHITE_LABEL: 'white_label',

  // Support & Services
  PRIORITY_SUPPORT: 'priority_support',

  // Rate Limiting
  SOURCE_RATE_LIMITING: 'source_rate_limiting',

  // Search
  AGENTIC_SEARCH: 'agentic_search',
} as const;

export type FeatureFlag = typeof FeatureFlags[keyof typeof FeatureFlags];
