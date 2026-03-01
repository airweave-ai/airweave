import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const originalFetch = globalThis.fetch;
const mockFetch = vi.fn();

describe('resolveOrganizationForCollection', () => {
    beforeEach(() => {
        vi.resetModules();
        globalThis.fetch = mockFetch;
        mockFetch.mockReset();
    });

    afterEach(() => {
        globalThis.fetch = originalFetch;
    });

    async function loadResolver() {
        return (await import('../../src/api/org-resolver.js')).resolveOrganizationForCollection;
    }

    function mockOrgsResponse(orgs: Array<{ id: string; name: string }>) {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => orgs,
        });
    }

    function mockCollectionProbe(collections: Array<{ readable_id: string }>) {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => collections,
        });
    }

    function mockCollectionProbeNotFound() {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: async () => [],
        });
    }

    describe('basic resolution', () => {
        it('returns orgId when collection found in first org', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'Org One' }]);
            mockCollectionProbe([{ readable_id: 'my-col' }]);

            const orgId = await resolve('token', 'https://api.test.com', 'my-col');
            expect(orgId).toBe('org-1');
        });

        it('probes multiple orgs and returns first match', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([
                { id: 'org-a', name: 'A' },
                { id: 'org-b', name: 'B' },
                { id: 'org-c', name: 'C' },
            ]);
            mockCollectionProbeNotFound();
            mockCollectionProbeNotFound();
            mockCollectionProbe([{ readable_id: 'target-col' }]);

            const orgId = await resolve('token', 'https://api.test.com', 'target-col');
            expect(orgId).toBe('org-c');
        });

        it('throws when user has zero organizations', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([]);

            await expect(
                resolve('token', 'https://api.test.com', 'col')
            ).rejects.toThrow('User does not belong to any organization');
        });

        it('throws descriptive error when collection not found in any org', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([
                { id: 'org-x', name: 'X Corp' },
                { id: 'org-y', name: 'Y Inc' },
            ]);
            mockCollectionProbeNotFound();
            mockCollectionProbeNotFound();

            await expect(
                resolve('token', 'https://api.test.com', 'missing-col')
            ).rejects.toThrow(/Collection "missing-col" not found.*X Corp.*Y Inc/);
        });
    });

    describe('API call correctness', () => {
        it('sends Authorization header with token on org list', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);

            await resolve('my-bearer-token', 'https://api.test.com', 'col');

            const [url, opts] = mockFetch.mock.calls[0];
            expect(url).toBe('https://api.test.com/organizations/');
            expect(opts.headers.Authorization).toBe('Bearer my-bearer-token');
        });

        it('sends X-Organization-ID header on collection probe', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);

            await resolve('tok', 'https://api.test.com', 'col');

            const [url, opts] = mockFetch.mock.calls[1];
            expect(url).toContain('/collections/');
            expect(opts.headers['X-Organization-ID']).toBe('org-1');
        });

        it('throws on non-OK org list response', async () => {
            const resolve = await loadResolver();
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                text: async () => 'Unauthorized',
            });

            await expect(
                resolve('bad-tok', 'https://api.test.com', 'col')
            ).rejects.toThrow('Failed to list organizations (401)');
        });
    });

    describe('caching', () => {
        it('cache hit returns without making HTTP calls', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);

            await resolve('tok', 'https://api.test.com', 'col');
            expect(mockFetch).toHaveBeenCalledTimes(2);

            mockFetch.mockClear();
            const orgId = await resolve('tok', 'https://api.test.com', 'col');
            expect(orgId).toBe('org-1');
            expect(mockFetch).not.toHaveBeenCalled();
        });

        it('cache expires after TTL', async () => {
            const resolve = await loadResolver();

            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);
            await resolve('tok', 'https://api.test.com', 'col');

            // Advance time past CACHE_TTL_MS (5 min)
            vi.useFakeTimers();
            vi.advanceTimersByTime(5 * 60 * 1000 + 1);

            mockFetch.mockClear();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);
            const orgId = await resolve('tok', 'https://api.test.com', 'col');

            expect(orgId).toBe('org-1');
            expect(mockFetch).toHaveBeenCalledTimes(2);

            vi.useRealTimers();
        });

        it('different tokens produce separate cache entries', async () => {
            const resolve = await loadResolver();

            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);
            await resolve('tok-a', 'https://api.test.com', 'col');

            mockOrgsResponse([{ id: 'org-2', name: 'P' }]);
            mockCollectionProbe([{ readable_id: 'col' }]);
            await resolve('tok-b', 'https://api.test.com', 'col');

            mockFetch.mockClear();
            expect(await resolve('tok-a', 'https://api.test.com', 'col')).toBe('org-1');
            expect(await resolve('tok-b', 'https://api.test.com', 'col')).toBe('org-2');
            expect(mockFetch).not.toHaveBeenCalled();
        });
    });

    describe('(Concern #4) sequential probing', () => {
        it('probes orgs one-by-one, producing N serial fetch calls', async () => {
            const resolve = await loadResolver();
            const callOrder: string[] = [];

            mockFetch.mockImplementation(async (url: string, opts: any) => {
                const urlStr = typeof url === 'string' ? url : url.toString();
                if (urlStr.includes('/organizations/')) {
                    callOrder.push('orgs');
                    return {
                        ok: true,
                        json: async () => [
                            { id: 'o1', name: 'O1' },
                            { id: 'o2', name: 'O2' },
                            { id: 'o3', name: 'O3' },
                        ],
                    };
                }
                const orgId = opts?.headers?.['X-Organization-ID'];
                callOrder.push(`probe:${orgId}`);
                const isTarget = orgId === 'o3';
                return {
                    ok: true,
                    json: async () => isTarget ? [{ readable_id: 'target' }] : [],
                };
            });

            await resolve('tok', 'https://api.test.com', 'target');

            // Verifies sequential: orgs first, then probe each org in order
            expect(callOrder).toEqual(['orgs', 'probe:o1', 'probe:o2', 'probe:o3']);
        });
    });

    describe('(Concern #5) unbounded cache growth', () => {
        it('cache grows past MAX_CACHE_ENTRIES when no entries have expired', async () => {
            const resolve = await loadResolver();
            const totalEntries = 510;

            for (let i = 0; i < totalEntries; i++) {
                mockFetch.mockReset();
                mockOrgsResponse([{ id: `org-${i}`, name: `O${i}` }]);
                mockCollectionProbe([{ readable_id: `col-${i}` }]);
                await resolve(`unique-token-${i}`, 'https://api.test.com', `col-${i}`);
            }

            // All entries should be cache hits — cache has grown past 500
            mockFetch.mockClear();
            for (let i = 0; i < totalEntries; i++) {
                const orgId = await resolve(`unique-token-${i}`, 'https://api.test.com', `col-${i}`);
                expect(orgId).toBe(`org-${i}`);
            }
            // No HTTP calls — all served from cache, proving >500 entries exist
            expect(mockFetch).not.toHaveBeenCalled();
        });
    });

    describe('(Concern #8) probeCollection limit=5 edge case', () => {
        it('misses collection when exact match is beyond first 5 results', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            // Return 5 results, none matching the target exactly
            mockCollectionProbe([
                { readable_id: 'col-a' },
                { readable_id: 'col-b' },
                { readable_id: 'col-c' },
                { readable_id: 'col-d' },
                { readable_id: 'col-e' },
            ]);

            await expect(
                resolve('tok', 'https://api.test.com', 'col-target')
            ).rejects.toThrow(/Collection "col-target" not found/);
        });
    });
});
