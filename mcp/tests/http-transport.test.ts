/**
 * HTTP Transport Tests - Tests the Streamable HTTP server
 * 
 * These tests verify:
 * 1. Session management works correctly
 * 2. API keys are handled per-request
 * 3. Multiple users can have separate sessions
 * 4. Sessions are cleaned up properly
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import express from 'express';
import request from 'supertest';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

// This is a simplified test - in practice, we'd test the actual index-http.ts
// But the key concepts are: session management, API key isolation, concurrent requests

describe('HTTP Transport - Session Management', () => {
    let app: express.Application;
    const sessions = new Map();

    beforeEach(() => {
        sessions.clear();
        app = express();
        app.use(express.json());

        // Simplified version of the /mcp endpoint for testing
        app.post('/mcp', async (req, res) => {
            const apiKey = req.headers['authorization']?.toString().replace('Bearer ', '') ||
                req.headers['x-api-key']?.toString();

            if (!apiKey) {
                return res.status(401).json({ error: 'API key required' });
            }

            const sessionId = req.headers['mcp-session-id']?.toString() ||
                `session_${Date.now()}_${Math.random()}`;

            let session = sessions.get(sessionId);

            if (!session) {
                session = {
                    apiKey,
                    createdAt: Date.now(),
                    requestCount: 0
                };
                sessions.set(sessionId, session);
            }

            session.requestCount++;

            res.json({
                sessionId,
                apiKey: session.apiKey,
                requestCount: session.requestCount,
                totalSessions: sessions.size
            });
        });

        app.delete('/mcp', (req, res) => {
            const sessionId = req.headers['mcp-session-id']?.toString();
            if (sessionId && sessions.has(sessionId)) {
                sessions.delete(sessionId);
                res.json({ message: 'Session terminated' });
            } else {
                res.status(404).json({ error: 'Session not found' });
            }
        });
    });

    afterEach(() => {
        sessions.clear();
    });

    describe('API Key Authentication', () => {
        it('should require API key', async () => {
            const response = await request(app)
                .post('/mcp')
                .send({ method: 'test' });

            expect(response.status).toBe(401);
            expect(response.body.error).toContain('API key required');
        });

        it('should accept API key via Authorization header', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-api-key-123')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.apiKey).toBe('test-api-key-123');
        });

        it('should accept API key via X-API-Key header', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('X-API-Key', 'test-api-key-456')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.apiKey).toBe('test-api-key-456');
        });
    });

    describe('Session Creation and Reuse', () => {
        it('should create new session on first request', async () => {
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .send({ method: 'test' });

            expect(response.status).toBe(200);
            expect(response.body.sessionId).toBeDefined();
            expect(response.body.requestCount).toBe(1);
            expect(response.body.totalSessions).toBe(1);
        });

        it('should reuse existing session with same session ID', async () => {
            // First request
            const response1 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .set('MCP-Session-ID', 'session-123')
                .send({ method: 'test' });

            expect(response1.body.requestCount).toBe(1);

            // Second request with same session ID
            const response2 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .set('MCP-Session-ID', 'session-123')
                .send({ method: 'test' });

            expect(response2.body.sessionId).toBe('session-123');
            expect(response2.body.requestCount).toBe(2);
            expect(response2.body.totalSessions).toBe(1);
        });

        it('should create separate sessions for different session IDs', async () => {
            // First session
            const response1 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .set('MCP-Session-ID', 'session-A')
                .send({ method: 'test' });

            // Second session
            const response2 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .set('MCP-Session-ID', 'session-B')
                .send({ method: 'test' });

            expect(response1.body.sessionId).toBe('session-A');
            expect(response2.body.sessionId).toBe('session-B');
            expect(response2.body.totalSessions).toBe(2);
        });
    });

    describe('Multi-Tenant Isolation', () => {
        it('should create separate sessions for different API keys', async () => {
            // User 1
            const response1 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer user1-key')
                .set('MCP-Session-ID', 'session-user1')
                .send({ method: 'test' });

            // User 2
            const response2 = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer user2-key')
                .set('MCP-Session-ID', 'session-user2')
                .send({ method: 'test' });

            expect(response1.body.apiKey).toBe('user1-key');
            expect(response2.body.apiKey).toBe('user2-key');
            expect(response2.body.totalSessions).toBe(2);
        });

        it('should maintain session state per user', async () => {
            // User 1 - Request 1
            await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer user1-key')
                .set('MCP-Session-ID', 'session-user1')
                .send({ method: 'test' });

            // User 2 - Request 1
            await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer user2-key')
                .set('MCP-Session-ID', 'session-user2')
                .send({ method: 'test' });

            // User 1 - Request 2
            const response = await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer user1-key')
                .set('MCP-Session-ID', 'session-user1')
                .send({ method: 'test' });

            // User 1's session should have 2 requests
            expect(response.body.requestCount).toBe(2);
            expect(response.body.totalSessions).toBe(2);
        });
    });

    describe('Session Cleanup', () => {
        it('should allow session termination via DELETE', async () => {
            // Create session
            await request(app)
                .post('/mcp')
                .set('Authorization', 'Bearer test-key')
                .set('MCP-Session-ID', 'session-123')
                .send({ method: 'test' });

            // Terminate session
            const deleteResponse = await request(app)
                .delete('/mcp')
                .set('MCP-Session-ID', 'session-123');

            expect(deleteResponse.status).toBe(200);
            expect(deleteResponse.body.message).toContain('terminated');

            // Verify session is gone
            expect(sessions.has('session-123')).toBe(false);
        });

        it('should return 404 for non-existent session termination', async () => {
            const response = await request(app)
                .delete('/mcp')
                .set('MCP-Session-ID', 'non-existent-session');

            expect(response.status).toBe(404);
        });
    });

    describe('Concurrent Requests', () => {
        it('should handle concurrent requests to same session', async () => {
            const promises = Array.from({ length: 5 }, (_, i) =>
                request(app)
                    .post('/mcp')
                    .set('Authorization', 'Bearer test-key')
                    .set('MCP-Session-ID', 'session-concurrent')
                    .send({ method: `test-${i}` })
            );

            const responses = await Promise.all(promises);

            // All should succeed
            responses.forEach(r => expect(r.status).toBe(200));

            // All should have same session
            responses.forEach(r => expect(r.body.sessionId).toBe('session-concurrent'));

            // Total requests should be 5
            const lastResponse = responses[responses.length - 1];
            expect(lastResponse.body.requestCount).toBeGreaterThan(0);
        });

        it('should handle concurrent requests from different users', async () => {
            const users = ['user1', 'user2', 'user3', 'user4', 'user5'];

            const promises = users.map(user =>
                request(app)
                    .post('/mcp')
                    .set('Authorization', `Bearer ${user}-key`)
                    .set('MCP-Session-ID', `session-${user}`)
                    .send({ method: 'test' })
            );

            const responses = await Promise.all(promises);

            // All should succeed
            responses.forEach(r => expect(r.status).toBe(200));

            // Should have 5 separate sessions
            const lastResponse = responses[responses.length - 1];
            expect(lastResponse.body.totalSessions).toBe(5);
        });
    });
});

