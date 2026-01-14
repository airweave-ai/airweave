/**
 * Get the URL for an app icon based on short_name and theme.
 * Icons are served from /icons/apps/{shortName}.svg
 */
export function getAppIconUrl(
  shortName: string,
  theme?: "dark" | "light",
): string {
  // Sources with dark-mode-specific light variants
  const darkModeVariants = [
    "attio",
    "notion",
    "clickup",
    "github",
    "linear",
    "zendesk",
  ];

  if (theme === "dark" && darkModeVariants.includes(shortName)) {
    return `/icons/apps/${shortName}-light.svg`;
  }

  return `/icons/apps/${shortName}.svg`;
}
