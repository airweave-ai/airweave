import { Registry, collectDefaultMetrics, Histogram, Counter, Gauge } from 'prom-client';

export const register = new Registry();

collectDefaultMetrics({ register });

// ── HTTP ────────────────────────────────────────────────────────────────

export const httpRequestDuration = new Histogram({
    name: 'mcp_http_request_duration_seconds',
    help: 'Duration of HTTP requests in seconds',
    labelNames: ['method', 'route', 'status_code', 'auth_type'] as const,
    buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registers: [register],
});

export const httpRequestsTotal = new Counter({
    name: 'mcp_http_requests_total',
    help: 'Total number of HTTP requests',
    labelNames: ['method', 'route', 'status_code', 'auth_type'] as const,
    registers: [register],
});

// ── OAuth / Auth ────────────────────────────────────────────────────────

export const tokenVerificationDuration = new Histogram({
    name: 'mcp_oauth_token_verification_duration_seconds',
    help: 'Time to verify a JWT access token via JWKS',
    labelNames: ['status'] as const,
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
    registers: [register],
});

export const tokenVerificationTotal = new Counter({
    name: 'mcp_oauth_token_verifications_total',
    help: 'Total JWT verification attempts',
    labelNames: ['status'] as const,
    registers: [register],
});

export const codeExchangeDuration = new Histogram({
    name: 'mcp_oauth_code_exchange_duration_seconds',
    help: 'Time to exchange an Auth0 authorization code for tokens',
    labelNames: ['status'] as const,
    buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
    registers: [register],
});

// ── Org Resolution ──────────────────────────────────────────────────────

export const orgResolutionDuration = new Histogram({
    name: 'mcp_org_resolution_duration_seconds',
    help: 'Time to resolve which organization owns a collection',
    labelNames: ['status'] as const,
    buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registers: [register],
});

export const orgCacheHits = new Counter({
    name: 'mcp_org_cache_hits_total',
    help: 'Number of org-resolution cache hits',
    registers: [register],
});

export const orgCacheMisses = new Counter({
    name: 'mcp_org_cache_misses_total',
    help: 'Number of org-resolution cache misses',
    registers: [register],
});

export const orgCacheSize = new Gauge({
    name: 'mcp_org_cache_entries',
    help: 'Current number of entries in the org-resolution cache',
    registers: [register],
});

// ── Search ──────────────────────────────────────────────────────────────

export const searchDuration = new Histogram({
    name: 'mcp_search_duration_seconds',
    help: 'End-to-end time for a search request through the Airweave API',
    labelNames: ['status'] as const,
    buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    registers: [register],
});

export const searchTotal = new Counter({
    name: 'mcp_search_requests_total',
    help: 'Total search requests through the MCP server',
    labelNames: ['status'] as const,
    registers: [register],
});
