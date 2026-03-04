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

    describe('parallel probing', () => {
        it('probes all orgs concurrently rather than sequentially', async () => {
            const resolve = await loadResolver();

            const initiated: string[] = [];
            const gates: Record<string, () => void> = {};

            mockFetch.mockImplementation(async (url: string, opts: any) => {
                const urlStr = typeof url === 'string' ? url : url.toString();
                if (urlStr.includes('/organizations/')) {
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
                initiated.push(orgId);
                // Block until the test explicitly opens the gate
                await new Promise<void>(r => { gates[orgId] = r; });
                const isTarget = orgId === 'o3';
                return {
                    ok: true,
                    json: async () => isTarget ? [{ readable_id: 'target' }] : [],
                };
            });

            const resultPromise = resolve('tok', 'https://api.test.com', 'target');

            // Flush microtasks so all parallel fetches are initiated
            await new Promise(r => setTimeout(r, 0));

            // With Promise.all, all 3 probes must have started before any resolved.
            // A sequential loop would only have initiated 1 at this point.
            expect(initiated).toHaveLength(3);
            expect(initiated).toContain('o1');
            expect(initiated).toContain('o2');
            expect(initiated).toContain('o3');

            // Unblock all probes
            gates['o1']();
            gates['o2']();
            gates['o3']();

            const orgId = await resultPromise;
            expect(orgId).toBe('o3');
        });

        it('returns first matching org when multiple orgs contain the collection', async () => {
            const resolve = await loadResolver();

            mockFetch.mockImplementation(async (url: string, opts: any) => {
                const urlStr = typeof url === 'string' ? url : url.toString();
                if (urlStr.includes('/organizations/')) {
                    return {
                        ok: true,
                        json: async () => [
                            { id: 'o1', name: 'O1' },
                            { id: 'o2', name: 'O2' },
                        ],
                    };
                }
                return {
                    ok: true,
                    json: async () => [{ readable_id: 'shared-col' }],
                };
            });

            const orgId = await resolve('tok', 'https://api.test.com', 'shared-col');
            // Should return the first org in the array that matches
            expect(orgId).toBe('o1');
        });
    });

    describe('cache size cap with LRU eviction', () => {
        it('evicts oldest entries to stay within MAX_CACHE_ENTRIES', async () => {
            const resolve = await loadResolver();
            const totalEntries = 510;

            for (let i = 0; i < totalEntries; i++) {
                mockFetch.mockReset();
                mockOrgsResponse([{ id: `org-${i}`, name: `O${i}` }]);
                mockCollectionProbe([{ readable_id: `col-${i}` }]);
                await resolve(`unique-token-${i}`, 'https://api.test.com', `col-${i}`);
            }

            // The earliest entries (0-9) should have been evicted via LRU.
            // Accessing them should trigger new HTTP calls.
            mockFetch.mockClear();
            for (let i = 0; i < 10; i++) {
                mockOrgsResponse([{ id: `org-${i}`, name: `O${i}` }]);
                mockCollectionProbe([{ readable_id: `col-${i}` }]);
            }
            for (let i = 0; i < 10; i++) {
                const orgId = await resolve(`unique-token-${i}`, 'https://api.test.com', `col-${i}`);
                expect(orgId).toBe(`org-${i}`);
            }
            // These required HTTP calls because they were evicted
            expect(mockFetch.mock.calls.length).toBeGreaterThan(0);

            // Recent entries (500-509) should still be cached
            mockFetch.mockClear();
            for (let i = 500; i < 510; i++) {
                const orgId = await resolve(`unique-token-${i}`, 'https://api.test.com', `col-${i}`);
                expect(orgId).toBe(`org-${i}`);
            }
            expect(mockFetch).not.toHaveBeenCalled();
        });
    });

    describe('probeCollection fetches without artificial limit', () => {
        it('finds collection when many results are returned', async () => {
            const resolve = await loadResolver();
            mockOrgsResponse([{ id: 'org-1', name: 'O' }]);
            mockCollectionProbe([
                { readable_id: 'col-a' },
                { readable_id: 'col-b' },
                { readable_id: 'col-c' },
                { readable_id: 'col-d' },
                { readable_id: 'col-e' },
                { readable_id: 'col-f' },
                { readable_id: 'col-target' },
            ]);

            const result = await resolve('tok', 'https://api.test.com', 'col-target');
            expect(result).toBe('org-1');
            const probeUrl = mockFetch.mock.calls[1][0] as string;
            expect(probeUrl).not.toContain('limit=');
        });
    });
});
