/**
 * Tests for the collection-not-set guidance response in the /mcp handler.
 *
 * Replicates the relevant logic from index-http.ts in a test-local Express app
 * to avoid importing the live module (which has side effects).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import express from 'express';
import request from 'supertest';

type ListCollectionsFn = (apiKey: string) => Promise<{ readable_id: string; name?: string }[]>;

function createGuidanceApp(opts: {
    listCollections: ListCollectionsFn;
    collectionEnv?: string;
}) {
    const app = express();
    app.use(express.json());

    app.post('/mcp', async (req, res) => {
        const apiKey = req.headers['x-api-key'] as string | undefined;
        if (!apiKey) {
            res.status(401).json({ jsonrpc: '2.0', error: { code: -32001, message: 'Auth required' }, id: null });
            return;
        }

        const collectionHeader = req.headers['x-collection-readable-id'] as string | undefined;
        const collectionEnv = opts.collectionEnv;

        if (!collectionHeader && !collectionEnv) {
            let collectionList = '';
            try {
                const collections = await opts.listCollections(apiKey);
                if (collections.length > 0) {
                    collectionList = '\n\nYour available collections:\n' +
                        collections.map(c => `- ${c.name || c.readable_id} (${c.readable_id})`).join('\n');
                }
            } catch {
                // listing failed
            }

            res.status(200).json({
                jsonrpc: '2.0',
                result: {
                    content: [{
                        type: 'text',
                        text: `No collection specified. Set the X-Collection-Readable-ID header or AIRWEAVE_COLLECTION env var.\n\nSee: https://docs.airweave.ai/mcp-server${collectionList}`,
                    }],
                },
                id: req.body?.id || null,
            });
            return;
        }

        const collection = collectionHeader || collectionEnv || 'default';
        res.status(200).json({
            jsonrpc: '2.0',
            result: { content: [{ type: 'text', text: `Searched ${collection}` }] },
            id: req.body?.id || null,
        });
    });

    return app;
}

describe('Collection guidance response', () => {
    let mockListCollections: ListCollectionsFn;

    beforeEach(() => {
        mockListCollections = vi.fn();
    });

    it('returns guidance with collection list when no collection is set', async () => {
        (mockListCollections as any).mockResolvedValue([
            { readable_id: 'slack-data', name: 'Slack Data' },
            { readable_id: 'confluence-docs', name: 'Confluence Docs' },
        ]);
        const app = createGuidanceApp({ listCollections: mockListCollections });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 1 });

        expect(res.status).toBe(200);
        const text = res.body.result.content[0].text;
        expect(text).toContain('No collection specified');
        expect(text).toContain('https://docs.airweave.ai/mcp-server');
        expect(text).toContain('slack-data');
        expect(text).toContain('Confluence Docs');
        expect(mockListCollections).toHaveBeenCalledWith('test-key');
    });

    it('proceeds normally when X-Collection-Readable-ID is set', async () => {
        const app = createGuidanceApp({ listCollections: mockListCollections });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .set('X-Collection-Readable-ID', 'my-collection')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 2 });

        expect(res.status).toBe(200);
        expect(res.body.result.content[0].text).toBe('Searched my-collection');
        expect(mockListCollections).not.toHaveBeenCalled();
    });

    it('proceeds normally when AIRWEAVE_COLLECTION env is set', async () => {
        const app = createGuidanceApp({
            listCollections: mockListCollections,
            collectionEnv: 'env-collection',
        });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 3 });

        expect(res.status).toBe(200);
        expect(res.body.result.content[0].text).toBe('Searched env-collection');
        expect(mockListCollections).not.toHaveBeenCalled();
    });

    it('returns guidance without list when listing fails', async () => {
        (mockListCollections as any).mockRejectedValue(new Error('API unreachable'));
        const app = createGuidanceApp({ listCollections: mockListCollections });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 4 });

        expect(res.status).toBe(200);
        const text = res.body.result.content[0].text;
        expect(text).toContain('No collection specified');
        expect(text).toContain('https://docs.airweave.ai/mcp-server');
        expect(text).not.toContain('Your available collections');
    });

    it('returns guidance without list when user has zero collections', async () => {
        (mockListCollections as any).mockResolvedValue([]);
        const app = createGuidanceApp({ listCollections: mockListCollections });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 5 });

        expect(res.status).toBe(200);
        const text = res.body.result.content[0].text;
        expect(text).toContain('No collection specified');
        expect(text).not.toContain('Your available collections');
    });

    it('uses readable_id as display name when name is missing', async () => {
        (mockListCollections as any).mockResolvedValue([
            { readable_id: 'no-name-collection' },
        ]);
        const app = createGuidanceApp({ listCollections: mockListCollections });

        const res = await request(app)
            .post('/mcp')
            .set('X-API-Key', 'test-key')
            .send({ jsonrpc: '2.0', method: 'tools/call', id: 6 });

        const text = res.body.result.content[0].text;
        expect(text).toContain('- no-name-collection (no-name-collection)');
    });
});
