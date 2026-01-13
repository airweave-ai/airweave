import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  defaultDarkColors,
  defaultLabels,
  defaultLightColors,
  defaultOptions,
} from "./theme-defaults";
import type {
  ConnectLabels,
  ConnectOptions,
  ConnectTheme,
  ThemeColors,
  ThemeFonts,
} from "./types";

// Font weight constants
const DEFAULT_BODY_WEIGHTS = [400, 500];
const DEFAULT_HEADING_WEIGHTS = [500, 600, 700];
const DEFAULT_BUTTON_WEIGHTS = [500, 600];

const SYSTEM_FONT_STACK = `-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif`;

/**
 * Constructs a Google Fonts API URL from font specifications.
 * Returns null if no fonts are specified.
 *
 * Google Fonts API v2 format:
 * https://fonts.googleapis.com/css2?family=Font+Name:wght@400;500&family=Other+Font:wght@600&display=swap
 */
function buildGoogleFontsUrl(fonts: ThemeFonts | undefined): string | null {
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

/**
 * Injects a Google Fonts stylesheet into the document head.
 * Returns a cleanup function to remove the stylesheet.
 * Silently falls back to system fonts on failure.
 */
function injectGoogleFontsStylesheet(url: string): () => void {
  const linkId = "connect-google-fonts";

  // Remove existing stylesheet if present
  const existing = document.getElementById(linkId);
  if (existing) {
    existing.remove();
  }

  // Create and inject new stylesheet
  const link = document.createElement("link");
  link.id = linkId;
  link.rel = "stylesheet";
  link.href = url;

  // Handle load errors silently - system fonts will be used as fallback
  link.onerror = () => {
    link.remove();
  };

  document.head.appendChild(link);

  return () => {
    const el = document.getElementById(linkId);
    if (el) el.remove();
  };
}

/**
 * Darken a hex color by a percentage (0-100)
 */
function darkenColor(hex: string, percent: number): string {
  // Handle non-hex colors (transparent, rgb, etc.)
  if (!hex.startsWith("#")) return hex;

  let hexValue = hex.slice(1);

  // Expand 3-digit hex to 6-digit (e.g., #fff -> #ffffff)
  if (hexValue.length === 3) {
    hexValue = hexValue
      .split("")
      .map((c) => c + c)
      .join("");
  }

  // Parse and darken
  const num = parseInt(hexValue, 16);
  const r = Math.max(0, Math.floor((num >> 16) * (1 - percent / 100)));
  const g = Math.max(0, Math.floor(((num >> 8) & 0x00ff) * (1 - percent / 100)));
  const b = Math.max(0, Math.floor((num & 0x0000ff) * (1 - percent / 100)));

  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

interface ThemeContextValue {
  theme: ConnectTheme;
  setTheme: (theme: ConnectTheme) => void;
  resolvedMode: "dark" | "light";
  colors: Required<ThemeColors>;
  labels: Required<ConnectLabels>;
  options: Required<ConnectOptions>;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
  initialTheme?: ConnectTheme;
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setTheme] = useState<ConnectTheme | null>(initialTheme ?? null);
  const [systemPrefersDark, setSystemPrefersDark] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  const isPending = theme === null;

  // Listen for system theme changes
  useEffect(() => {
    if (typeof window === "undefined") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      setSystemPrefersDark(e.matches);
    };

    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  // Resolve the actual mode (dark or light)
  const resolvedMode: "dark" | "light" = useMemo(() => {
    if (isPending) return "light"; // Default for pending, but colors will be transparent
    if (theme.mode === "system") {
      return systemPrefersDark ? "dark" : "light";
    }
    return theme.mode;
  }, [theme, isPending, systemPrefersDark]);

  // Transparent colors for pending state (no flash)
  const pendingColors: Required<ThemeColors> = useMemo(
    () => ({
      background: "transparent",
      surface: "transparent",
      text: "transparent",
      textMuted: "transparent",
      primary: "transparent",
      primaryForeground: "transparent",
      primaryHover: "transparent",
      secondary: "transparent",
      secondaryHover: "transparent",
      border: "transparent",
      success: "transparent",
      error: "transparent",
    }),
    [],
  );

  // Merge custom colors with defaults, auto-deriving hover colors
  const colors: Required<ThemeColors> = useMemo(() => {
    if (isPending) return pendingColors;
    const defaultColors =
      resolvedMode === "dark" ? defaultDarkColors : defaultLightColors;
    const customColors = theme?.colors?.[resolvedMode] ?? {};

    // Merge base colors first
    const merged = {
      ...defaultColors,
      ...customColors,
    };

    // Auto-derive hover colors if not explicitly provided
    // Darken by 15% for a subtle but visible hover effect
    if (customColors.primary && !customColors.primaryHover) {
      merged.primaryHover = darkenColor(merged.primary, 15);
    }
    if (customColors.secondary && !customColors.secondaryHover) {
      merged.secondaryHover = darkenColor(merged.secondary, 15);
    }

    return merged;
  }, [resolvedMode, theme, isPending, pendingColors]);

  // Merge custom labels with defaults
  const labels: Required<ConnectLabels> = useMemo(() => {
    const customLabels = theme?.labels ?? {};
    return {
      ...defaultLabels,
      ...customLabels,
    };
  }, [theme]);

  // Merge custom options with defaults
  const options: Required<ConnectOptions> = useMemo(() => {
    const customOptions = theme?.options ?? {};
    return {
      ...defaultOptions,
      ...customOptions,
    };
  }, [theme]);

  // Apply CSS custom properties to document
  useEffect(() => {
    if (typeof document === "undefined") return;

    const root = document.documentElement;

    // Apply color variables
    root.style.setProperty("--connect-bg", colors.background);
    root.style.setProperty("--connect-surface", colors.surface);
    root.style.setProperty("--connect-text", colors.text);
    root.style.setProperty("--connect-text-muted", colors.textMuted);
    root.style.setProperty("--connect-primary", colors.primary);
    root.style.setProperty(
      "--connect-primary-foreground",
      colors.primaryForeground,
    );
    root.style.setProperty("--connect-primary-hover", colors.primaryHover);
    root.style.setProperty("--connect-secondary", colors.secondary);
    root.style.setProperty("--connect-secondary-hover", colors.secondaryHover);
    root.style.setProperty("--connect-border", colors.border);
    root.style.setProperty("--connect-success", colors.success);
    root.style.setProperty("--connect-error", colors.error);

    // Apply font variables
    const fonts = theme?.fonts;
    const bodyFont = fonts?.body
      ? `"${fonts.body}", ${SYSTEM_FONT_STACK}`
      : SYSTEM_FONT_STACK;
    const headingFont = fonts?.heading
      ? `"${fonts.heading}", ${SYSTEM_FONT_STACK}`
      : bodyFont;
    const buttonFont = fonts?.button
      ? `"${fonts.button}", ${SYSTEM_FONT_STACK}`
      : bodyFont;

    root.style.setProperty("--connect-font-body", bodyFont);
    root.style.setProperty("--connect-font-heading", headingFont);
    root.style.setProperty("--connect-font-button", buttonFont);
  }, [colors, theme?.fonts]);

  // Load Google Fonts stylesheet
  useEffect(() => {
    if (typeof document === "undefined" || isPending) return;

    const fontsUrl = buildGoogleFontsUrl(theme?.fonts);
    if (!fontsUrl) return;

    const cleanup = injectGoogleFontsStylesheet(fontsUrl);
    return cleanup;
  }, [theme?.fonts, isPending]);

  // Stable setTheme wrapper to prevent re-renders
  const setThemeStable = useCallback((newTheme: ConnectTheme) => {
    setTheme(newTheme);
  }, []);

  const value: ThemeContextValue = useMemo(
    () => ({
      theme: theme ?? { mode: "light" }, // Provide default for consumers
      setTheme: setThemeStable,
      resolvedMode,
      colors,
      labels,
      options,
    }),
    [theme, setThemeStable, resolvedMode, colors, labels, options],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- useTheme must be colocated with ThemeContext
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
