// Airweave API client using the official SDK

import { AirweaveSDKClient } from '@airweave/sdk';
import { AirweaveConfig, SearchRequest, SearchResponse } from './types.js';
import { VERSION } from '../config/constants.js';

export class AirweaveClient {
    private client: AirweaveSDKClient;

    constructor(private config: AirweaveConfig) {
        this.client = new AirweaveSDKClient({
            apiKey: config.apiKey,
            baseUrl: config.baseUrl,
            headers: {
                'X-Client-Name': 'airweave-mcp-search',
                'X-Client-Version': VERSION,
            }
        });
    }

    async search(searchRequest: SearchRequest): Promise<SearchResponse> {
        try {
            console.error(`[${new Date().toISOString()}] AirweaveClient.search called with:`, JSON.stringify(searchRequest, null, 2));
        } catch (e) {
            console.error(`[${new Date().toISOString()}] AirweaveClient.search called (params not serializable)`);
        }

        // Mock mode for testing
        if (this.config.apiKey === 'test-key' && this.config.baseUrl.includes('localhost')) {
            return this.getMockResponse(searchRequest);
        }

        try {
            console.error(`[${new Date().toISOString()}] Calling SDK search with all params`);
            const response = await this.client.collections.search(this.config.collection, searchRequest);
            console.error(`[${new Date().toISOString()}] Search successful, got ${response.results?.length || 0} results`);
            return response;
        } catch (error: unknown) {
            console.error(`[${new Date().toISOString()}] Search error:`, error);
            const err = error as { statusCode?: number; message?: string; body?: unknown };
            if (err.statusCode) {
                const errorBody = typeof err.body === 'string' ? err.body : JSON.stringify(err.body);
                throw new Error(`Airweave API error (${err.statusCode}): ${err.message}\nStatus code: ${err.statusCode}\nBody: ${errorBody}`);
            } else {
                throw new Error(`Airweave API error: ${err.message || 'Unknown error'}`);
            }
        }
    }

    private getMockResponse(request: SearchRequest): SearchResponse {
        const { query, responseType, limit, offset, recencyBias, scoreThreshold } = request as any;

        const mockResults = [];
        const resultCount = Math.min(limit || 100, 5);

        for (let i = 0; i < resultCount; i++) {
            const score = 0.95 - (i * 0.1);

            if (scoreThreshold !== undefined && score < scoreThreshold) {
                continue;
            }

            mockResults.push({
                score: score,
                payload: {
                    source_name: `Mock Source ${i + 1}`,
                    entity_id: `mock_${i + 1}`,
                    title: `Mock Document ${i + 1} about "${query}"`,
                    md_content: `This is a mock response for the query "${query}".`,
                    created_at: new Date(Date.now() - (i * 24 * 60 * 60 * 1000)).toISOString(),
                }
            });
        }

        return {
            results: mockResults,
            completion: responseType === "completion"
                ? `Based on the search results for "${query}", here's a comprehensive summary of the findings...`
                : undefined
        };
    }
}
