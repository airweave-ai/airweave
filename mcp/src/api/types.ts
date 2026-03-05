// Type definitions for Airweave API responses

import { AirweaveSDK } from '@airweave/sdk';

// Re-export SDK types for consistency
export type SearchResponse = AirweaveSDK.SearchResponse;
export type SearchRequest = AirweaveSDK.SearchRequest;

export interface AirweaveConfig {
    apiKey: string;
    collection: string;
    baseUrl: string;
    organizationId?: string;
}
