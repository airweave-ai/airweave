import { useTheme } from "@/lib/theme-provider";

export function getAppIconUrl(shortName: string, theme?: string): string {
  try {
    // Special handling for Notion icon in dark mode
    if (shortName === "notion" && theme === "dark") {
      return new URL(`/src/components/icons/apps/notion-light.svg`, import.meta.url).href;
    }
    if (shortName === "clickup" && theme === "dark") {
      return new URL(`/src/components/icons/apps/clickup-light.svg`, import.meta.url).href;
    }
    // Special handling for GitHub icon in dark mode
    if (shortName === "github" && theme === "dark") {
      return new URL(`/src/components/icons/apps/github-light.svg`, import.meta.url).href;
    }
    return new URL(`/src/components/icons/apps/${shortName}.svg`, import.meta.url).href;
  } catch {
    return new URL(`/src/components/icons/apps/default-icon.svg`, import.meta.url).href;
  }
}

export function getDestinationIconUrl(shortName: string): string {
  return new URL(`/src/components/icons/destinations/${shortName}.png`, import.meta.url).href;
}
