/**
 * PostHog analytics for the hosted MCP server.
 *
 * Only used by the hosted HTTP entry point (index-http.ts).
 * The local/npx entry point (index.ts) never imports this module,
 * so no analytics are emitted in local mode.
 *
 * Events are batched and flushed asynchronously -- they never block
 * request handling or add latency to MCP responses.
 */

import { PostHog } from 'posthog-node';
import { createHash } from 'crypto';

let client: PostHog | null = null;

// Default PostHog config matching backend settings.py
const DEFAULT_API_KEY = 'phc_Ytp26UB3WwGCdjHTpDBI9HQg2ZA38ITMDKI6fE6EPGS';
const DEFAULT_HOST = 'https://eu.i.posthog.com';

export function initPostHog(): void {
    const apiKey = process.env.POSTHOG_API_KEY || DEFAULT_API_KEY;
    const host = process.env.POSTHOG_HOST || DEFAULT_HOST;

    client = new PostHog(apiKey, { host, flushAt: 20, flushInterval: 10000 });
    console.log(`PostHog: enabled (host: ${host})`);
}

export async function shutdownPostHog(): Promise<void> {
    if (client) {
        await client.shutdown();
        client = null;
    }
}

/**
 * Hash an API key to use as distinct_id.
 * We never store or send plaintext API keys to PostHog.
 */
function hashApiKey(apiKey: string): string {
    return createHash('sha256').update(apiKey).digest('hex').slice(0, 16);
}

export function trackMcpRequest(apiKey: string, properties: {
    method: string;
    collection: string;
    responseTimeMs?: number;
}): void {
    if (!client) return;
    client.capture({
        distinctId: hashApiKey(apiKey),
        event: 'mcp_request',
        properties
    });
}

export function trackMcpError(apiKey: string | undefined, properties: {
    errorCode: number;
    errorMessage: string;
    collection?: string;
}): void {
    if (!client) return;
    client.capture({
        distinctId: apiKey ? hashApiKey(apiKey) : 'anonymous',
        event: 'mcp_error',
        properties
    });
}
