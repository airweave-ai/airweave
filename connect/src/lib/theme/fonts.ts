import type { ThemeFonts } from "../types";

// Font weight constants
export const DEFAULT_BODY_WEIGHTS = [400, 500];
export const DEFAULT_HEADING_WEIGHTS = [500, 600, 700];
export const DEFAULT_BUTTON_WEIGHTS = [500, 600];

/**
 * Constructs a Google Fonts API URL from font specifications.
 * Returns null if no fonts are specified.
 *
 * Google Fonts API v2 format:
 * https://fonts.googleapis.com/css2?family=Font+Name:wght@400;500&family=Other+Font:wght@600&display=swap
 */
export function buildGoogleFontsUrl(fonts: ThemeFonts | undefined): string | null {
  if (!fonts) return null;

  const fontEntries: Map<string, Set<number>> = new Map();

  // Helper to add font with weights
  const addFont = (fontName: string | undefined, weights: number[]) => {
    if (!fontName) return;
    const existing = fontEntries.get(fontName) || new Set();
    weights.forEach((w) => existing.add(w));
    fontEntries.set(fontName, existing);
  };

  // Collect fonts with their weights
  addFont(fonts.body, DEFAULT_BODY_WEIGHTS);
  addFont(fonts.heading, DEFAULT_HEADING_WEIGHTS);
  addFont(fonts.button || fonts.body, DEFAULT_BUTTON_WEIGHTS);

  if (fontEntries.size === 0) return null;

  // Build URL
  const familyParams = Array.from(fontEntries.entries())
    .map(([name, weights]) => {
      const sortedWeights = Array.from(weights)
        .sort((a, b) => a - b)
        .join(";");
      // Replace spaces with + for URL encoding
      const encodedName = name.replace(/ /g, "+");
      return `family=${encodedName}:wght@${sortedWeights}`;
    })
    .join("&");

  return `https://fonts.googleapis.com/css2?${familyParams}&display=swap`;
}
