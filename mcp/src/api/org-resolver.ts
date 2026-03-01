import { createHash } from 'node:crypto';

const CACHE_TTL_MS = 5 * 60 * 1000;
const MAX_CACHE_ENTRIES = 500;

interface CacheEntry {
    orgId: string;
    expiresAt: number;
}

interface OrgInfo {
    id: string;
    name: string;
}

const cache = new Map<string, CacheEntry>();

function cacheKey(token: string, collection: string): string {
    const hash = createHash('sha256').update(token).digest('hex').slice(0, 16);
    return `${hash}:${collection}`;
}

function evictExpired(): void {
    const now = Date.now();
    for (const [key, entry] of cache) {
        if (entry.expiresAt <= now) cache.delete(key);
    }
}

async function fetchOrganizations(token: string, baseUrl: string): Promise<OrgInfo[]> {
    const url = `${baseUrl}/organizations/`;
    const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`Failed to list organizations (${res.status}): ${body}`);
    }
    return res.json() as Promise<OrgInfo[]>;
}

interface CollectionInfo {
    readable_id: string;
}

async function probeCollection(
    token: string,
    baseUrl: string,
    orgId: string,
    collection: string,
): Promise<boolean> {
    const url = `${baseUrl}/collections/?search=${encodeURIComponent(collection)}&limit=5`;
    const res = await fetch(url, {
        headers: {
            'Authorization': `Bearer ${token}`,
            'X-Organization-ID': orgId,
        },
    });
    if (!res.ok) {
        if (res.status === 404) return false;
        const body = await res.text();
        throw new Error(`Unexpected response probing collection in org ${orgId} (${res.status}): ${body}`);
    }
    const results = await res.json() as CollectionInfo[];
    return results.some(c => c.readable_id === collection);
}

/**
 * Resolve which organization owns the given collection for this user.
 * Results are cached in-memory for CACHE_TTL_MS.
 */
export async function resolveOrganizationForCollection(
    token: string,
    baseUrl: string,
    collection: string,
): Promise<string> {
    const key = cacheKey(token, collection);
    const cached = cache.get(key);
    if (cached && cached.expiresAt > Date.now()) {
        return cached.orgId;
    }

    const orgs = await fetchOrganizations(token, baseUrl);
    if (orgs.length === 0) {
        throw new Error('User does not belong to any organization');
    }

    for (const org of orgs) {
        const found = await probeCollection(token, baseUrl, org.id, collection);
        if (found) {
            storeCache(key, org.id);
            return org.id;
        }
    }

    const tried = orgs.map(o => `${o.name} (${o.id})`).join(', ');
    throw new Error(
        `Collection "${collection}" not found in any of the user's organizations: ${tried}`,
    );
}

function storeCache(key: string, orgId: string): void {
    if (cache.size >= MAX_CACHE_ENTRIES) evictExpired();
    cache.set(key, { orgId, expiresAt: Date.now() + CACHE_TTL_MS });
}
