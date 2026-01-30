/**
 * OAuth Token Validator for MCP Server
 * 
 * Validates OAuth access tokens issued by the Airweave authorization server.
 * Uses Redis caching for performance and calls the backend validation endpoint on cache miss.
 */

import { RedisSessionManager } from '../session/redis-session-manager.js';

export interface OAuthTokenValidationResult {
    valid: boolean;
    userId?: string;
    organizationId?: string;
    collectionId?: string;
}

export class OAuthTokenValidator {
    private sessionManager: RedisSessionManager;
    private backendUrl: string;

    constructor(sessionManager: RedisSessionManager, backendUrl: string) {
        this.sessionManager = sessionManager;
        this.backendUrl = backendUrl;
    }

    /**
     * Validate an OAuth access token
     * 
     * Flow:
     * 1. Check Redis cache for token validation result
     * 2. If cache miss, call backend /oauth/validate endpoint
     * 3. Cache the result with TTL
     * 4. Return validation result
     */
    async validateToken(token: string): Promise<OAuthTokenValidationResult> {
        // Generate cache key
        const cacheKey = `oauth:token:${this.hashToken(token)}`;

        try {
            // Try to get from Redis cache
            const cached = await this.sessionManager.getSession(cacheKey);
            if (cached) {
                console.log(`[${new Date().toISOString()}] OAuth token validation - cache hit`);
                // Stored as JSON in collection field
                const cachedData = JSON.parse(cached.collection);
                return {
                    valid: true,
                    userId: cachedData.userId,
                    organizationId: cachedData.organizationId,
                    collectionId: cachedData.collectionId,
                };
            }

            // Cache miss - validate with backend
            console.log(`[${new Date().toISOString()}] OAuth token validation - cache miss, calling backend`);
            const validationResult = await this.validateWithBackend(token);

            if (validationResult.valid) {
                // Cache the validation result (TTL: 1 hour)
                const cacheData = {
                    userId: validationResult.userId!,
                    organizationId: validationResult.organizationId!,
                    collectionId: validationResult.collectionId!,
                };

                await this.sessionManager.setSession({
                    sessionId: cacheKey,
                    apiKeyHash: this.hashToken(token),
                    collection: JSON.stringify(cacheData), // Store as JSON
                    baseUrl: this.backendUrl,
                    createdAt: Date.now(),
                    lastAccessedAt: Date.now(),
                }, false);
            }

            return validationResult;

        } catch (error) {
            console.error(`[${new Date().toISOString()}] OAuth token validation error:`, error);
            return { valid: false };
        }
    }

    /**
     * Validate token with backend API
     */
    private async validateWithBackend(token: string): Promise<OAuthTokenValidationResult> {
        try {
            const response = await fetch(`${this.backendUrl}/oauth/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `token=${encodeURIComponent(token)}`,
            });

            if (response.status === 401) {
                // Token is invalid/expired/revoked
                return { valid: false };
            }

            if (!response.ok) {
                throw new Error(`Backend validation failed: ${response.status}`);
            }

            const data = await response.json();
            return {
                valid: data.valid,
                userId: data.user_id,
                organizationId: data.organization_id,
                collectionId: data.collection_id,
            };

        } catch (error) {
            console.error('Backend validation error:', error);
            return { valid: false };
        }
    }

    /**
     * Hash token for cache key (simple SHA-256 equivalent using crypto)
     */
    private hashToken(token: string): string {
        // Simple hash for cache key - in production, use crypto.subtle.digest
        const crypto = require('crypto');
        return crypto.createHash('sha256').update(token).digest('hex');
    }

    /**
     * Clear token from cache (called when token is revoked)
     */
    async invalidateToken(token: string): Promise<void> {
        const cacheKey = `oauth:token:${this.hashToken(token)}`;
        await this.sessionManager.deleteSession(cacheKey);
    }
}
