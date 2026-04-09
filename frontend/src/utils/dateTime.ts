/**
 * Utility functions for consistent UTC datetime handling
 * Ensures all runtime calculations are timezone-independent
 */

import { format } from "date-fns";

/**
 * Get current UTC time in milliseconds
 * Replacement for Date.now() to ensure UTC consistency
 */
export function utcNow(): number {
    return Date.now(); // Date.now() is already UTC
}

/**
 * Parse a backend timestamp as UTC
 * Backend sends naive UTC timestamps like "2024-01-15T10:00:00"
 * We need to explicitly parse these as UTC
 */
export function parseBackendTimestamp(timestamp: string | null | undefined): number | null {
    if (!timestamp) return null;

    // Check if timestamp has timezone info (Z, +XX:XX, or -XX:XX at the end)
    // Note: We can't just check for '-' because dates contain '-' (e.g., '2025-06-20')
    const hasTimezoneInfo = timestamp.includes('Z') ||
        /[+-]\d{2}:?\d{2}$/.test(timestamp);

    const utcTimestamp = hasTimezoneInfo ? timestamp : timestamp + 'Z';
    const parsed = Date.parse(utcTimestamp);

    return isNaN(parsed) ? null : parsed;
}

/**
 * Calculate runtime between two timestamps in milliseconds
 * Handles mixed timezone sources safely
 */
export function calculateRuntime(startTime: number, endTime?: number): number {
    const end = endTime ?? utcNow();
    const runtime = end - startTime;

    // Sanity check: reject unreasonable runtime values
    if (runtime < 0 || runtime > 24 * 60 * 60 * 1000) {
        console.warn('Unreasonable runtime detected:', runtime, 'ms');
        return 0;
    }

    return runtime;
}

/**
 * Parse a backend timestamp and format it using date-fns.
 * Returns an empty string for null/undefined/unparseable values.
 */
export function formatBackendTimestamp(
    timestamp: string | null | undefined,
    fmt: string,
): string {
    if (!timestamp) return "";
    const ms = parseBackendTimestamp(timestamp);
    if (ms === null) return "";
    return format(new Date(ms), fmt);
}

/**
 * Format runtime milliseconds into human-readable string
 */
export function formatRuntime(milliseconds: number): string {
    if (milliseconds === 0) return 'N/A';

    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
        return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}
