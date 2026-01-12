import {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import type { ConnectTheme, ThemeColors } from "./types";

// Default theme colors
const defaultDarkColors: Required<ThemeColors> = {
  background: "#0f172a",
  surface: "#1e293b",
  text: "#ffffff",
  textMuted: "#9ca3af",
  primary: "#06b6d4",
  primaryHover: "#0891b2",
  secondary: "#334155",
  secondaryHover: "#475569",
  border: "#334155",
  success: "#22c55e",
  error: "#ef4444",
};

const defaultLightColors: Required<ThemeColors> = {
  background: "#ffffff",
  surface: "#f9fafb",
  text: "#111827",
  textMuted: "#6b7280",
  primary: "#0891b2",
  primaryHover: "#0e7490",
  secondary: "#e5e7eb",
  secondaryHover: "#d1d5db",
  border: "#e5e7eb",
  success: "#16a34a",
  error: "#dc2626",
};

interface ThemeContextValue {
  theme: ConnectTheme;
  setTheme: (theme: ConnectTheme) => void;
  resolvedMode: "dark" | "light";
  colors: Required<ThemeColors>;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
  initialTheme?: ConnectTheme;
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setTheme] = useState<ConnectTheme>(
    initialTheme ?? { mode: "dark" },
  );
  const [systemPrefersDark, setSystemPrefersDark] = useState(true);

  // Listen for system theme changes
  useEffect(() => {
    if (typeof window === "undefined") return;

    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemPrefersDark(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => {
      setSystemPrefersDark(e.matches);
    };

    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  // Resolve the actual mode (dark or light)
  const resolvedMode: "dark" | "light" = useMemo(() => {
    if (theme.mode === "system") {
      return systemPrefersDark ? "dark" : "light";
    }
    return theme.mode;
  }, [theme.mode, systemPrefersDark]);

  // Merge custom colors with defaults
  const colors: Required<ThemeColors> = useMemo(() => {
    const defaultColors =
      resolvedMode === "dark" ? defaultDarkColors : defaultLightColors;
    const customColors = theme.colors?.[resolvedMode] ?? {};

    return {
      ...defaultColors,
      ...customColors,
    };
  }, [resolvedMode, theme.colors]);

  // Apply CSS custom properties to document
  useEffect(() => {
    if (typeof document === "undefined") return;

    const root = document.documentElement;
    root.style.setProperty("--connect-bg", colors.background);
    root.style.setProperty("--connect-surface", colors.surface);
    root.style.setProperty("--connect-text", colors.text);
    root.style.setProperty("--connect-text-muted", colors.textMuted);
    root.style.setProperty("--connect-primary", colors.primary);
    root.style.setProperty("--connect-primary-hover", colors.primaryHover);
    root.style.setProperty("--connect-secondary", colors.secondary);
    root.style.setProperty("--connect-secondary-hover", colors.secondaryHover);
    root.style.setProperty("--connect-border", colors.border);
    root.style.setProperty("--connect-success", colors.success);
    root.style.setProperty("--connect-error", colors.error);
  }, [colors]);

  const value: ThemeContextValue = useMemo(
    () => ({
      theme,
      setTheme,
      resolvedMode,
      colors,
    }),
    [theme, resolvedMode, colors],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

// Export defaults for reference
export { defaultDarkColors, defaultLightColors };
