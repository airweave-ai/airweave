import { formatDate as sharedFormatDate } from "@/lib/date";

/**
 * Get app/source icon URL based on short name and theme
 * Icons are located in the public/icons/connectors/ directory
 */
export function getAppIconUrl(shortName: string, theme?: string): string {
  // Special handling for icons that have light variants for dark mode
  const darkModeVariants: Record<string, string> = {
    attio: "attio-light.svg",
    notion: "notion-light.svg",
    clickup: "clickup-light.svg",
    github: "github-light.svg",
    linear: "linear-light.svg",
    zendesk: "zendesk-light.svg",
  };

  // Check for dark mode variant
  if (theme === "dark" && darkModeVariants[shortName]) {
    return `/icons/connectors/${darkModeVariants[shortName]}`;
  }

  // Default icon path
  return `/icons/connectors/${shortName}.svg`;
}

/**
 * Format a date string to a human-readable format with time.
 * Re-exports from shared date utilities with datetime style.
 */
export const formatDate = (dateString: string): string =>
  sharedFormatDate(dateString, "datetime");

/**
 * Get status display properties for a collection status
 */
export function getCollectionStatusDisplay(status: string): {
  label: string;
  variant: "default" | "success" | "warning" | "destructive";
} {
  switch (status) {
    case "ACTIVE":
      return { label: "Active", variant: "success" };
    case "NEEDS_SOURCE":
      return { label: "Needs Source", variant: "warning" };
    case "ERROR":
      return { label: "Error", variant: "destructive" };
    default:
      return { label: status, variant: "default" };
  }
}

/**
 * Get a consistent color class based on source short name (for fallback icons)
 */
export function getSourceColorClass(shortName: string): string {
  const colors = [
    "bg-blue-500",
    "bg-green-500",
    "bg-purple-500",
    "bg-orange-500",
    "bg-pink-500",
    "bg-indigo-500",
    "bg-red-500",
    "bg-yellow-500",
  ];

  // Hash the short name to get a consistent color
  const index =
    shortName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) %
    colors.length;
  return colors[index];
}
