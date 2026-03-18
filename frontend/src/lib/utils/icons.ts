import { useTheme } from "@/lib/theme-provider";

export function getAppIconUrl(shortName: string, theme?: string): string {
  try {
    // Apollo default is black — use white-fill variant in dark mode
    if (shortName === "apollo" && theme === "dark") {
      return new URL(`/src/components/icons/apps/apollo-light.svg`, import.meta.url).href;
    }
    // Special handling for Attio icon in dark mode
    if (shortName === "attio" && theme === "dark") {
      return new URL(`/src/components/icons/apps/attio-light.svg`, import.meta.url).href;
    }
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
    // Special handling for Linear icon in dark mode
    if (shortName === "linear" && theme === "dark") {
      return new URL(`/src/components/icons/apps/linear-light.svg`, import.meta.url).href;
    }
    // White logos — use dark-fill variant in light mode
    if (shortName === "calcom" && theme !== "dark") {
      return new URL(`/src/components/icons/apps/calcom-light.svg`, import.meta.url).href;
    }
    if (shortName === "slab" && theme !== "dark") {
      return new URL(`/src/components/icons/apps/slab-light.svg`, import.meta.url).href;
    }
    return new URL(`/src/components/icons/apps/${shortName}.svg`, import.meta.url).href;
  } catch {
    return new URL(`/src/components/icons/apps/default-icon.svg`, import.meta.url).href;
  }
}

export function getAuthProviderIconUrl(shortName: string, theme?: string): string {
  // Special cases for providers with specific file formats
  const specialCases: { [key: string]: string } = {
    'klavis': 'klavis.png',
    'pipedream': 'pipedream.jpeg'
  };

  try {
    // Check for special cases first
    if (specialCases[shortName]) {
      return new URL(`/src/components/icons/auth_providers/${specialCases[shortName]}`, import.meta.url).href;
    }

    // Use -light version for dark theme, -dark version for light theme
    if (theme === "dark") {
      return new URL(`/src/components/icons/auth_providers/${shortName}-light.svg`, import.meta.url).href;
    } else {
      return new URL(`/src/components/icons/auth_providers/${shortName}-dark.svg`, import.meta.url).href;
    }
  } catch (e) {
    console.log(`Error loading auth provider icon: ${e}`);
    // Fallback to regular icon without theme suffix
    try {
      return new URL(`/src/components/icons/auth_providers/${shortName}.svg`, import.meta.url).href;
    } catch {
      return new URL('/src/components/icons/apps/default-icon.svg', import.meta.url).href;
    }
  }
}
