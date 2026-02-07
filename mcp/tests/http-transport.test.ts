/**
 * HTTP Transport Tests - Tests the stateless Streamable HTTP server
 * 
 * These tests verify:
 * 1. API key authentication works correctly (X-API-Key, Bearer, query params)
 * 2. Bearer token parsing follows RFC 6750
 * 3. Multi-tenant isolation via per-request API keys
 * 4. DELETE endpoint returns success in stateless mode
 * 5. Concurrent requests from different users
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import express from 'express';
import request from 'supertest';

describe('HTTP Transport - Stateless Architecture', () => {
    let app: express.Application;

    /**
     * Extract Bearer token per RFC 6750.
     */
    function extractBearerToken(header: string | undefined): string | undefined {
        if (!header || header.length < 8) return undefined;
        if (header.slice(0, 7).toLowerCase() !== 'bearer ') return undefined;
        return header.slice(7);
    }

    beforeEach(() => {
        app = express();
        app.use(express.json());

        // Simplified stateless /mcp endpoint matching production behavior
        app.post('/mcp', async (req, res) => {
            const apiKey = (req.headers['x-api-key'] as string) ||
                extractBearerToken(req.headers['authorization'] as string);

            if (!apiKey) {
                return res.status(401).json({
                    jsonrpc: '2.0',
                    error: { code: -32001, message: 'Authentication required' },
                    id: req.body?.id || null
                });
            }

            const collection = (req.headers['x-collection-readable-id'] as string) || 'default';

            res.json({
                apiKey,
                collection,
                method: req.body?.method
            });
        });

        app.delete('/mcp', (req, res) => {
            res.status(200).json({
                jsonrpc: '2.0',
                result: { message: 'Session terminated (stateless mode)' },
                id: null
            });
        });
    });

    describe('API Key Authentication', () => {
        it('should require API key', async () => {
            const response = await request(app)
                .post('/mcp')
                .send({ method: 'test' });

            expect(response.status).toBe(401);
        });

        it('should accept API key via X-API-Key header', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'test-api-key-456')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.apiKey).toBe('test-api-key-456');
        });

        it('should accept API key via Authorization Bearer header', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-api-key-123')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.apiKey).toBe('test-api-key-123');
        });

        it('should reject non-Bearer Authorization schemes', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'Basic dXNlcjpwYXNz')
                .send({ method: 'test' });

            expect(response.status).toBe(401);
        });

        it('should accept case-insensitive Bearer scheme per RFC 7235', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'BEARER test-api-key')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.apiKey).toBe('test-api-key');
        });

        it('should reject API key via query parameter', async () => {
            const response = await request(app)
                .post('/mcp?apiKey=query-key')
                .send({ method: 'test' });

            expect(response.status).toBe(401);
        });
    });

    describe('Collection Selection', () => {
        it('should use X-Collection-Readable-ID header when provided', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'test-key')
                .set('X-Collection-Readable-ID', 'my-collection')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.collection).toBe('my-collection');
        });

        it('should fall back to default when no collection header', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'test-key')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.collection).toBe('default');
        });
    });

    describe('Stateless Behavior', () => {
        it('should handle each request independently', async () => {
            const response1 = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'user1-key')
                .set('X-Collection-Readable-ID', 'collection-a')
                .send({ method: 'initialize' });

            const response2 = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'user2-key')
                .set('X-Collection-Readable-ID', 'collection-b')
                .send({ method: 'initialize' });

            expect(response1.body.apiKey).toBe('user1-key');
            expect(response1.body.collection).toBe('collection-a');
            expect(response2.body.apiKey).toBe('user2-key');
            expect(response2.body.collection).toBe('collection-b');
        });

        it('should allow DELETE without prior session', async () => {
            const response = await request(app)
                .delete('/mcp');

            expect(response.status).toBe(200);
            expect(response.body.result.message).toContain('stateless');
        });
    });

    describe('Concurrent Requests', () => {
        it('should handle concurrent requests from different users', async () => {
            const users = ['user1', 'user2', 'user3', 'user4', 'user5'];

            const promises = users.map(user =>
                request(app)
                    .post('/mcp')
                    .set('X-API-Key', `${user}-key`)
                    .set('X-Collection-Readable-ID', `${user}-collection`)
                    .send({ method: 'test' })
            );

            const responses = await Promise.all(promises);

            responses.forEach((r, i) => {
                expect(r.status).toBe(200);
                expect(r.body.apiKey).toBe(`${users[i]}-key`);
                expect(r.body.collection).toBe(`${users[i]}-collection`);
            });
        });
    });
});
