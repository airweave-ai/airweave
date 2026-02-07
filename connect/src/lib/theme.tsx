import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useHead } from "@unhead/react";
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
} from "./types";
import { buildGoogleFontsUrl, SYSTEM_FONT_STACK, PENDING_COLORS } from "./theme/index";

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

  // Merge custom colors with defaults, auto-deriving hover colors
  const colors: Required<ThemeColors> = useMemo(() => {
    if (isPending) return PENDING_COLORS;
    const defaultColors =
      resolvedMode === "dark" ? defaultDarkColors : defaultLightColors;
    const customColors = theme?.colors?.[resolvedMode] ?? {};

    // Merge base colors first
    const merged = {
      ...defaultColors,
      ...customColors,
    };

    // Auto-derive hover colors if not explicitly provided
    // Use CSS color-mix to darken by 15%
    if (customColors.primary && !customColors.primaryHover) {
      merged.primaryHover = `color-mix(in srgb, ${merged.primary} 85%, black)`;
    }
    if (customColors.secondary && !customColors.secondaryHover) {
      merged.secondaryHover = `color-mix(in srgb, ${merged.secondary} 85%, black)`;
    }

    return merged;
  }, [resolvedMode, theme, isPending]);

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

  // Load Google Fonts stylesheet via useHead
  const fontsUrl = buildGoogleFontsUrl(theme?.fonts);
  useHead({
    link: fontsUrl
      ? [
          { rel: "preconnect", href: "https://fonts.googleapis.com" },
          {
            rel: "preconnect",
            href: "https://fonts.gstatic.com",
            crossorigin: "anonymous",
          },
          { rel: "stylesheet", href: fontsUrl },
        ]
      : [],
  });

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
