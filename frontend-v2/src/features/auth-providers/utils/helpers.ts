import { formatDate as sharedFormatDate } from "@/lib/date";

/**
 * Generates a random suffix for the readable ID
 * This ensures uniqueness for similar connection names
 */
export function generateRandomSuffix(): string {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 6; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

/**
 * Helper to generate the base readable ID from a name
 * Transforms name to lowercase, replaces spaces with hyphens, and removes special characters
 */
export function generateReadableIdBase(name: string): string {
  if (!name || name.trim() === "") return "";

  // Convert to lowercase and replace spaces with hyphens
  let readableId = name.toLowerCase().trim();

  // Replace any character that's not a letter, number, or space with nothing
  readableId = readableId.replace(/[^a-z0-9\s]/g, "");

  // Replace spaces with hyphens
  readableId = readableId.replace(/\s+/g, "-");

  // Ensure no consecutive hyphens
  readableId = readableId.replace(/-+/g, "-");

  // Trim hyphens from start and end
  readableId = readableId.replace(/^-|-$/g, "");

  return readableId;
}

/**
 * Generate a full readable ID with suffix
 */
export function generateReadableId(name: string, suffix: string): string {
  if (!name || name.trim() === "") return "";
  const base = generateReadableIdBase(name);
  return base ? `${base}-${suffix}` : "";
}

/**
 * Get auth provider icon URL based on short name and theme
 */
export function getAuthProviderIconUrl(
  shortName: string,
  theme?: string
): string {
  // Special cases for providers with specific file formats
  const specialCases: Record<string, string> = {
    klavis: "klavis.png",
    pipedream: "pipedream.jpeg",
  };

  // Check for special cases first
  if (specialCases[shortName]) {
    return `/src/components/icons/auth_providers/${specialCases[shortName]}`;
  }

  // Use -light version for dark theme, -dark version for light theme
  if (theme === "dark") {
    return `/src/components/icons/auth_providers/${shortName}-light.svg`;
  } else {
    return `/src/components/icons/auth_providers/${shortName}-dark.svg`;
  }
}

/**
 * Format a date string to a human-readable format with time.
 * Re-exports from shared date utilities with datetime style.
 */
export const formatDate = (dateString: string): string =>
  sharedFormatDate(dateString, "datetime");

/**
 * Coming soon providers list
 */
export const COMING_SOON_PROVIDERS = [
  {
    id: "coming-soon-klavis",
    name: "Klavis",
    short_name: "klavis",
    isComingSoon: true,
  },
];
