/**
 * Organization URL utilities
 *
 * URLs use combined slug format: {name-slug}-{short-id}
 * Example: acme-corp-a1b2c3d4
 *
 * The short-id is the first 8 characters of the UUID (without dashes)
 * This allows human-readable URLs while maintaining unique identification
 */

import type { Organization } from "./api/organizations";

/**
 * Convert a string to a URL-safe slug
 * - Converts to lowercase
 * - Replaces spaces and underscores with hyphens
 * - Removes non-alphanumeric characters (except hyphens)
 * - Collapses multiple hyphens into one
 * - Trims hyphens from start and end
 */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\s_]+/g, "-") // Replace spaces and underscores with hyphens
    .replace(/[^a-z0-9-]/g, "") // Remove non-alphanumeric (except hyphens)
    .replace(/-+/g, "-") // Collapse multiple hyphens
    .replace(/^-|-$/g, ""); // Trim hyphens from edges
}

/**
 * Extract a short ID from a UUID
 * Takes the first 8 characters (without dashes)
 */
export function getShortId(uuid: string): string {
  return uuid.replace(/-/g, "").slice(0, 8);
}

/**
 * Generate a URL-friendly org slug from an organization
 * Format: {slugified-name}-{short-id}
 * Example: "Acme Corp" with ID "a1b2c3d4-e5f6-..." -> "acme-corp-a1b2c3d4"
 */
export function generateOrgSlug(org: Organization): string {
  const nameSlug = slugify(org.name);
  const shortId = getShortId(org.id);
  return `${nameSlug}-${shortId}`;
}

/**
 * Parse the organization ID from a URL slug
 * The ID is the last segment after the final hyphen (8 characters)
 * Returns null if the slug format is invalid
 */
export function parseOrgIdFromSlug(slug: string): string | null {
  // The short ID is always 8 characters at the end after the last hyphen
  const match = slug.match(/-([a-f0-9]{8})$/);
  if (!match) return null;
  return match[1];
}

/**
 * Find an organization by its URL slug
 * Matches by comparing the short ID portion of the slug
 */
export function findOrgBySlug(
  organizations: Organization[],
  slug: string
): Organization | undefined {
  const shortId = parseOrgIdFromSlug(slug);
  if (!shortId) return undefined;

  return organizations.find((org) => getShortId(org.id) === shortId);
}

/**
 * Get the primary organization or fall back to the first one
 */
export function getPrimaryOrg(
  organizations: Organization[]
): Organization | undefined {
  return organizations.find((org) => org.is_primary) || organizations[0];
}
