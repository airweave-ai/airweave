/**
 * Integration-style tests for the OAuth paths in index-http.ts.
 *
 * Because index-http.ts has side effects at module scope (creates app, calls
 * startServer), we faithfully replicate its auth logic in a test-local Express
 * app. This lets us verify the exact heuristics and edge cases without
 * importing the live module.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import express from 'express';
import request from 'supertest';

// ---- Replicated logic from index-http.ts ----

interface AuthInfo {
    token: string;
    clientId: string;
    scopes: string[];
    expiresAt?: number;
}

function extractBearerToken(header: string | undefined): string | undefined {
    if (!header || header.length < 8) return undefined;
    if (header.slice(0, 7).toLowerCase() !== 'bearer ') return undefined;
    return header.slice(7);
}

function extractApiKey(req: express.Request): string | undefined {
    return (req.headers['x-api-key'] as string) ||
        extractBearerToken(req.headers['authorization'] as string) ||
        undefined;
}

function extractMcpCredential(req: express.Request & { auth?: AuthInfo }): string | undefined {
    return req.auth?.token || extractApiKey(req);
}

// ---- Test helpers ----

type ReqWithAuth = express.Request & { auth?: AuthInfo };

function createOAuthApp(opts: {
    oauthEnabled: boolean;
    resolveOrg?: (token: string, collection: string) => Promise<string>;
    verifyToken?: (token: string) => AuthInfo | null;
}): express.Application {
    const app = express();
    app.use(express.json());

    if (opts.oauthEnabled && opts.verifyToken) {
        app.use((req: ReqWithAuth, _res, next) => {
            const bearer = extractBearerToken(req.headers['authorization'] as string);
            if (bearer) {
                const authInfo = opts.verifyToken!(bearer);
                if (authInfo) {
                    req.auth = authInfo;
                }
            }
            next();
        });
    }

    app.get('/health', (_req, res) => {
        res.json({ status: 'healthy' });
    });

    app.get('/', (_req, res) => {
        res.json({
            oauth: opts.oauthEnabled
                ? { enabled: true, discovery: '/.well-known/oauth-authorization-server' }
                : { enabled: false },
        });
    });

    app.post('/mcp', async (req: ReqWithAuth, res) => {
        const apiKey = extractMcpCredential(req);

        if (!apiKey) {
            res.status(401).json({
                jsonrpc: '2.0',
                error: { code: -32001, message: 'Authentication required' },
                id: req.body?.id || null,
            });
            return;
        }

        const collection = (req.headers['x-collection-readable-id'] as string) || 'default';

        let organizationId: string | undefined;
        const isOAuthRequest = opts.oauthEnabled && !req.headers['x-api-key'];
        if (isOAuthRequest && opts.resolveOrg) {
            try {
                organizationId = await opts.resolveOrg(apiKey, collection);
            } catch (err) {
                res.status(400).json({
                    jsonrpc: '2.0',
                    error: {
                        code: -32002,
                        message: err instanceof Error ? err.message : 'Org resolution failed',
                    },
                    id: req.body?.id || null,
                });
                return;
            }
        }

        res.json({
            credential: apiKey,
            collection,
            organizationId,
            isOAuthRequest,
            hadAuthInfo: !!req.auth,
        });
    });

    return app;
}

// ---- Tests ----

describe('index-http OAuth integration', () => {
    describe('health and info endpoints', () => {
        it('health returns 200 regardless of OAuth config', async () => {
            const app = createOAuthApp({ oauthEnabled: true });
            const res = await request(app).get('/health');
            expect(res.status).toBe(200);
            expect(res.body.status).toBe('healthy');
        });

        it('root info includes oauth.enabled and discovery when OAuth is on', async () => {
            const app = createOAuthApp({ oauthEnabled: true });
            const res = await request(app).get('/');
            expect(res.body.oauth.enabled).toBe(true);
            expect(res.body.oauth.discovery).toBe('/.well-known/oauth-authorization-server');
        });

        it('root info shows oauth disabled when off', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app).get('/');
            expect(res.body.oauth.enabled).toBe(false);
        });
    });

    describe('extractMcpCredential', () => {
        it('prefers req.auth.token over X-API-Key', async () => {
            const app = createOAuthApp({
                oauthEnabled: true,
                verifyToken: (tok) => ({
                    token: tok,
                    clientId: 'c',
                    scopes: [],
                }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer oauth-jwt')
                .set('X-API-Key', 'plain-api-key')
                .send({});

            expect(res.body.credential).toBe('oauth-jwt');
        });

        it('falls back to X-API-Key when no req.auth', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'my-key')
                .send({});

            expect(res.body.credential).toBe('my-key');
        });

        it('falls back to Bearer token when no req.auth and no X-API-Key', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer my-bearer-key')
                .send({});

            expect(res.body.credential).toBe('my-bearer-key');
        });

        it('returns 401 when no credential at all', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app).post('/mcp').send({});
            expect(res.status).toBe(401);
        });
    });

    describe('(Concern #1) isOAuthRequest heuristic', () => {
        it('skips org resolution when X-API-Key header present even with OAuth token', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-123');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyToken: (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer oauth-jwt')
                .set('X-API-Key', 'also-present')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.isOAuthRequest).toBe(false);
            expect(res.body.organizationId).toBeUndefined();
            expect(resolveOrg).not.toHaveBeenCalled();
        });

        it('triggers org resolution when only OAuth token is present (no X-API-Key)', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-456');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyToken: (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer oauth-jwt')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.isOAuthRequest).toBe(true);
            expect(res.body.organizationId).toBe('org-456');
            expect(resolveOrg).toHaveBeenCalledWith('oauth-jwt', 'default');
        });
    });

    describe('(Concern #2) API-key via Bearer when OAuth is enabled', () => {
        it('API-key user with Bearer header succeeds when verifyToken returns null', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-1');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyToken: (_tok) => null,
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer plain-api-key-not-jwt')
                .send({});

            // The middleware did NOT set req.auth, so extractMcpCredential
            // falls back to extractApiKey which parses the Bearer header.
            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('plain-api-key-not-jwt');
            expect(res.body.hadAuthInfo).toBe(false);
            // BUT isOAuthRequest is true (no X-API-Key header), so org resolution runs
            // with a plain API key — this will fail in production because the backend
            // expects a JWT for /organizations/. This documents the bug.
            expect(res.body.isOAuthRequest).toBe(true);
            expect(resolveOrg).toHaveBeenCalled();
        });

        it('API-key user with X-API-Key header works normally even with OAuth enabled', async () => {
            const resolveOrg = vi.fn();

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyToken: (_tok) => null,
            });

            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'my-plain-api-key')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('my-plain-api-key');
            expect(res.body.isOAuthRequest).toBe(false);
            expect(resolveOrg).not.toHaveBeenCalled();
        });
    });

    describe('OAuth disabled mode', () => {
        it('falls back to API key path with no OAuth middleware', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'key')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.isOAuthRequest).toBe(false);
            expect(res.body.organizationId).toBeUndefined();
        });
    });

    describe('org resolution error handling', () => {
        it('returns 400 when org resolution fails', async () => {
            const resolveOrg = vi.fn().mockRejectedValue(new Error('User not in any org'));

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyToken: (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer jwt')
                .send({ id: 'req-1' });

            expect(res.status).toBe(400);
            expect(res.body.error.code).toBe(-32002);
            expect(res.body.error.message).toBe('User not in any org');
            expect(res.body.id).toBe('req-1');
        });
    });
});
