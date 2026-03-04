/**
 * Integration-style tests for the dual-auth (API key + OAuth) paths in
 * index-http.ts.
 *
 * Because index-http.ts has side effects at module scope (creates app, calls
 * startServer), we faithfully replicate its auth resolution logic in a
 * test-local Express app. This lets us verify the exact behavior without
 * importing the live module.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import express from 'express';
import request from 'supertest';
import { decodeJwt } from 'jose';

// ---- Replicated types and helpers from index-http.ts ----

interface AuthInfo {
    token: string;
    clientId: string;
    scopes: string[];
    expiresAt?: number;
}

type ReqWithAuth = express.Request & { auth?: AuthInfo; _authMethod?: 'oauth' | 'api-key' };

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

// ---- Test app factory ----

function createOAuthApp(opts: {
    oauthEnabled: boolean;
    resolveOrg?: (token: string, collection: string) => Promise<string>;
    verifyAccessToken?: (token: string) => Promise<AuthInfo>;
}): express.Application {
    const app = express();
    app.use(express.json());

    // Replicate resolveAuth middleware from index-http.ts
    const resolveAuth = async (req: ReqWithAuth, res: express.Response, next: express.NextFunction) => {
        if (req.headers['x-api-key']) {
            req._authMethod = 'api-key';
            return next();
        }

        const bearer = extractBearerToken(req.headers['authorization'] as string);
        if (bearer && opts.oauthEnabled && opts.verifyAccessToken) {
            try {
                req.auth = await opts.verifyAccessToken(bearer);
                req._authMethod = 'oauth';
            } catch {
                let isJwt = false;
                try { decodeJwt(bearer); isJwt = true; } catch {}
                if (isJwt) {
                    res.status(401).json({
                        jsonrpc: '2.0',
                        error: {
                            code: -32001,
                            message: 'Token expired or invalid',
                        },
                        id: null,
                    });
                    return;
                }
                req._authMethod = 'api-key';
            }
            return next();
        }

        if (bearer) {
            req._authMethod = 'api-key';
        }
        next();
    };

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

    app.post('/mcp', resolveAuth, async (req: ReqWithAuth, res) => {
        const isOAuth = req._authMethod === 'oauth';
        const credential = isOAuth ? req.auth!.token : extractApiKey(req);

        if (!credential) {
            res.status(401).json({
                jsonrpc: '2.0',
                error: { code: -32001, message: 'Authentication required' },
                id: req.body?.id || null,
            });
            return;
        }

        const collection = (req.headers['x-collection-readable-id'] as string) || 'default';

        let organizationId: string | undefined;
        if (isOAuth && opts.resolveOrg) {
            try {
                organizationId = await opts.resolveOrg(credential, collection);
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
            credential,
            collection,
            organizationId,
            authMethod: req._authMethod,
            hadAuthInfo: !!req.auth,
        });
    });

    return app;
}

// ---- Tests ----

describe('index-http dual auth', () => {
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

    describe('API key auth (X-API-Key header)', () => {
        it('accepts X-API-Key without attempting JWT verification', async () => {
            const verifyAccessToken = vi.fn();

            const app = createOAuthApp({
                oauthEnabled: true,
                verifyAccessToken,
            });

            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'my-api-key')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('my-api-key');
            expect(res.body.authMethod).toBe('api-key');
            expect(res.body.hadAuthInfo).toBe(false);
            expect(verifyAccessToken).not.toHaveBeenCalled();
        });

        it('X-API-Key takes priority even when Authorization header also present', async () => {
            const resolveOrg = vi.fn();

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async () => ({ token: 'jwt', clientId: 'c', scopes: [] }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'my-key')
                .set('Authorization', 'Bearer some-jwt')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('my-key');
            expect(res.body.authMethod).toBe('api-key');
            expect(res.body.organizationId).toBeUndefined();
            expect(resolveOrg).not.toHaveBeenCalled();
        });
    });

    describe('OAuth auth (Bearer JWT)', () => {
        it('verifies Bearer token as JWT and triggers org resolution', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-456');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async (tok) => ({
                    token: tok,
                    clientId: 'auth0-cid',
                    scopes: ['openid'],
                }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer valid-jwt-token')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('valid-jwt-token');
            expect(res.body.authMethod).toBe('oauth');
            expect(res.body.hadAuthInfo).toBe(true);
            expect(res.body.organizationId).toBe('org-456');
            expect(resolveOrg).toHaveBeenCalledWith('valid-jwt-token', 'default');
        });
    });

    describe('Bearer token with failed verification', () => {
        const fakeJwt = [
            Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64url'),
            Buffer.from(JSON.stringify({ sub: 'user', exp: 0 })).toString('base64url'),
            'fakesignature',
        ].join('.');

        it('returns 401 when structurally valid JWT fails verification', async () => {
            const app = createOAuthApp({
                oauthEnabled: true,
                verifyAccessToken: async () => { throw new Error('expired'); },
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', `Bearer ${fakeJwt}`)
                .send({});

            expect(res.status).toBe(401);
        });

        it('401 response has correct JSON-RPC error body', async () => {
            const app = createOAuthApp({
                oauthEnabled: true,
                verifyAccessToken: async () => { throw new Error('expired'); },
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', `Bearer ${fakeJwt}`)
                .send({});

            expect(res.body).toEqual({
                jsonrpc: '2.0',
                error: {
                    code: -32001,
                    message: 'Token expired or invalid',
                },
                id: null,
            });
        });

        it('falls back to api-key for non-JWT Bearer token when verification throws', async () => {
            const resolveOrg = vi.fn();

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async () => { throw new Error('not a JWT'); },
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer plain-api-key-abc')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('plain-api-key-abc');
            expect(res.body.authMethod).toBe('api-key');
            expect(res.body.hadAuthInfo).toBe(false);
            expect(res.body.organizationId).toBeUndefined();
            expect(resolveOrg).not.toHaveBeenCalled();
        });
    });

    describe('OAuth disabled mode', () => {
        it('treats Bearer token as API key without attempting JWT verification', async () => {
            const verifyAccessToken = vi.fn();

            const app = createOAuthApp({
                oauthEnabled: false,
                verifyAccessToken,
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer my-key')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.credential).toBe('my-key');
            expect(res.body.authMethod).toBe('api-key');
            expect(verifyAccessToken).not.toHaveBeenCalled();
        });

        it('X-API-Key works normally', async () => {
            const app = createOAuthApp({ oauthEnabled: false });
            const res = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'key')
                .send({});

            expect(res.status).toBe(200);
            expect(res.body.authMethod).toBe('api-key');
            expect(res.body.organizationId).toBeUndefined();
        });
    });

    describe('no credentials', () => {
        it('returns 401 when no auth headers present', async () => {
            const app = createOAuthApp({ oauthEnabled: true });
            const res = await request(app).post('/mcp').send({});
            expect(res.status).toBe(401);
        });

        it('returns 401 for non-Bearer Authorization scheme', async () => {
            const app = createOAuthApp({ oauthEnabled: true });
            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Basic dXNlcjpwYXNz')
                .send({});
            expect(res.status).toBe(401);
        });
    });

    describe('org resolution error handling', () => {
        it('returns 400 when org resolution fails for OAuth user', async () => {
            const resolveOrg = vi.fn().mockRejectedValue(new Error('User not in any org'));

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
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

    describe('collection header forwarding', () => {
        it('passes X-Collection-Readable-ID to org resolution', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-1');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
            });

            const res = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer jwt')
                .set('X-Collection-Readable-ID', 'my-collection')
                .send({});

            expect(res.status).toBe(200);
            expect(resolveOrg).toHaveBeenCalledWith('jwt', 'my-collection');
        });

        it('defaults collection to "default" when header absent', async () => {
            const resolveOrg = vi.fn().mockResolvedValue('org-1');

            const app = createOAuthApp({
                oauthEnabled: true,
                resolveOrg,
                verifyAccessToken: async (tok) => ({ token: tok, clientId: 'c', scopes: [] }),
            });

            await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer jwt')
                .send({});

            expect(resolveOrg).toHaveBeenCalledWith('jwt', 'default');
        });
    });
});
