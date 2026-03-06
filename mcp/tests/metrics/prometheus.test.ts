import { describe, it, expect, beforeEach } from 'vitest';
import express from 'express';
import request from 'supertest';
import { Registry, collectDefaultMetrics, Histogram, Counter, Gauge } from 'prom-client';

function createMetricsApp() {
    const register = new Registry();
    collectDefaultMetrics({ register });

    const httpRequestDuration = new Histogram({
        name: 'mcp_http_request_duration_seconds',
        help: 'Duration of HTTP requests in seconds',
        labelNames: ['method', 'route', 'status_code', 'auth_type'] as const,
        buckets: [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        registers: [register],
    });

    const httpRequestsTotal = new Counter({
        name: 'mcp_http_requests_total',
        help: 'Total number of HTTP requests',
        labelNames: ['method', 'route', 'status_code', 'auth_type'] as const,
        registers: [register],
    });

    const tokenVerificationDuration = new Histogram({
        name: 'mcp_oauth_token_verification_duration_seconds',
        help: 'Time to verify a JWT access token via JWKS',
        labelNames: ['status'] as const,
        buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
        registers: [register],
    });

    const tokenVerificationTotal = new Counter({
        name: 'mcp_oauth_token_verifications_total',
        help: 'Total JWT verification attempts',
        labelNames: ['status'] as const,
        registers: [register],
    });

    const codeExchangeDuration = new Histogram({
        name: 'mcp_oauth_code_exchange_duration_seconds',
        help: 'Time to exchange an Auth0 authorization code for tokens',
        labelNames: ['status'] as const,
        buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
        registers: [register],
    });

    const orgResolutionDuration = new Histogram({
        name: 'mcp_org_resolution_duration_seconds',
        help: 'Time to resolve which organization owns a collection',
        labelNames: ['status'] as const,
        buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        registers: [register],
    });

    const orgCacheHits = new Counter({
        name: 'mcp_org_cache_hits_total',
        help: 'Number of org-resolution cache hits',
        registers: [register],
    });

    const orgCacheMisses = new Counter({
        name: 'mcp_org_cache_misses_total',
        help: 'Number of org-resolution cache misses',
        registers: [register],
    });

    const orgCacheSize = new Gauge({
        name: 'mcp_org_cache_entries',
        help: 'Current number of entries in the org-resolution cache',
        registers: [register],
    });

    const searchDuration = new Histogram({
        name: 'mcp_search_duration_seconds',
        help: 'End-to-end time for a search request through the Airweave API',
        labelNames: ['status'] as const,
        buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        registers: [register],
    });

    const searchTotal = new Counter({
        name: 'mcp_search_requests_total',
        help: 'Total search requests through the MCP server',
        labelNames: ['status'] as const,
        registers: [register],
    });

    const app = express();

    app.get('/metrics', async (_req, res) => {
        res.set('Content-Type', register.contentType);
        res.end(await register.metrics());
    });

    app.post('/mcp', (req, res) => {
        const startTime = Date.now();
        const authType = (req.headers['x-api-key'] ? 'api-key' : 'none') as string;
        res.on('finish', () => {
            const duration = (Date.now() - startTime) / 1000;
            const labels = { method: 'POST', route: '/mcp', status_code: String(res.statusCode), auth_type: authType };
            httpRequestDuration.observe(labels, duration);
            httpRequestsTotal.inc(labels);
        });
        res.json({ ok: true });
    });

    return {
        app, register,
        httpRequestsTotal, httpRequestDuration,
        tokenVerificationDuration, tokenVerificationTotal,
        codeExchangeDuration,
        orgResolutionDuration, orgCacheHits, orgCacheMisses, orgCacheSize,
        searchDuration, searchTotal,
    };
}

describe('Prometheus metrics', () => {
    let app: express.Application;
    let register: Registry;
    let ctx: ReturnType<typeof createMetricsApp>;

    beforeEach(() => {
        ctx = createMetricsApp();
        app = ctx.app;
        register = ctx.register;
    });

    describe('HTTP metrics', () => {
        it('GET /metrics returns 200 with prometheus content type', async () => {
            const res = await request(app).get('/metrics');
            expect(res.status).toBe(200);
            expect(res.headers['content-type']).toMatch(/text\/(plain|openmetrics)/);
        });

        it('GET /metrics includes default Node.js process metrics', async () => {
            const res = await request(app).get('/metrics');
            expect(res.text).toContain('process_cpu_');
            expect(res.text).toContain('nodejs_');
        });

        it('counter increments after a request to /mcp', async () => {
            await request(app).post('/mcp').send({});
            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_http_requests_total');
            expect(res.text).toMatch(/mcp_http_requests_total\{.*method="POST".*\}\s+1/);
        });

        it('histogram records duration after a request to /mcp', async () => {
            await request(app).post('/mcp').send({});
            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_http_request_duration_seconds_bucket');
            expect(res.text).toContain('mcp_http_request_duration_seconds_count');
        });

        it('labels include auth_type dimension', async () => {
            await request(app).post('/mcp').set('X-API-Key', 'test-key').send({});
            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/auth_type="api-key"/);
        });

        it('counter accumulates across multiple requests', async () => {
            await request(app).post('/mcp').send({});
            await request(app).post('/mcp').send({});
            await request(app).post('/mcp').send({});
            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/mcp_http_requests_total\{.*\}\s+3/);
        });
    });

    describe('OAuth metrics', () => {
        it('token verification histogram records observations', async () => {
            const end = ctx.tokenVerificationDuration.startTimer();
            end({ status: 'success' });
            ctx.tokenVerificationTotal.inc({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_oauth_token_verification_duration_seconds_count');
            expect(res.text).toMatch(/mcp_oauth_token_verifications_total\{status="success"\}\s+1/);
        });

        it('token verification tracks errors separately', async () => {
            ctx.tokenVerificationTotal.inc({ status: 'error' });
            ctx.tokenVerificationTotal.inc({ status: 'success' });
            ctx.tokenVerificationTotal.inc({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/mcp_oauth_token_verifications_total\{status="error"\}\s+1/);
            expect(res.text).toMatch(/mcp_oauth_token_verifications_total\{status="success"\}\s+2/);
        });

        it('code exchange histogram records observations', async () => {
            const end = ctx.codeExchangeDuration.startTimer();
            end({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_oauth_code_exchange_duration_seconds_count');
        });
    });

    describe('Org resolution metrics', () => {
        it('tracks cache hits and misses', async () => {
            ctx.orgCacheHits.inc();
            ctx.orgCacheHits.inc();
            ctx.orgCacheMisses.inc();

            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/mcp_org_cache_hits_total\s+2/);
            expect(res.text).toMatch(/mcp_org_cache_misses_total\s+1/);
        });

        it('cache size gauge reflects current value', async () => {
            ctx.orgCacheSize.set(42);

            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/mcp_org_cache_entries\s+42/);
        });

        it('resolution duration histogram records observations', async () => {
            const end = ctx.orgResolutionDuration.startTimer();
            end({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_org_resolution_duration_seconds_count');
        });
    });

    describe('Search metrics', () => {
        it('search counter and histogram track calls', async () => {
            const end = ctx.searchDuration.startTimer();
            end({ status: 'success' });
            ctx.searchTotal.inc({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toContain('mcp_search_duration_seconds_count');
            expect(res.text).toMatch(/mcp_search_requests_total\{status="success"\}\s+1/);
        });

        it('search errors tracked separately from successes', async () => {
            ctx.searchTotal.inc({ status: 'error' });
            ctx.searchTotal.inc({ status: 'success' });
            ctx.searchTotal.inc({ status: 'success' });

            const res = await request(app).get('/metrics');
            expect(res.text).toMatch(/mcp_search_requests_total\{status="error"\}\s+1/);
            expect(res.text).toMatch(/mcp_search_requests_total\{status="success"\}\s+2/);
        });
    });
});
