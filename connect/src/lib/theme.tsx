import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { ConnectLabels, ConnectTheme, ThemeColors } from "./types";

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

// Default labels
const defaultLabels: Required<ConnectLabels> = {
  // Main headings
  sourcesHeading: "Sources",

  // Connection status labels
  statusActive: "Active",
  statusSyncing: "Syncing",
  statusPendingAuth: "Pending Auth",
  statusError: "Error",
  statusInactive: "Inactive",

  // Connection item
  entitiesCount: "{count} entities",

  // Menu actions
  menuReconnect: "Reconnect",
  menuDelete: "Delete",

  // Empty state
  emptyStateHeading: "No sources connected yet",
  emptyStateDescription: "Connect a source to get started.",

  // Connect mode error
  connectModeErrorHeading: "Cannot View Connections",
  connectModeErrorDescription:
    "Viewing connections is not available in connect mode.",

  // Load error
  loadErrorHeading: "Failed to Load Connections",

  // Error screen titles
  errorInvalidTokenTitle: "Invalid Session",
  errorExpiredTokenTitle: "Session Expired",
  errorNetworkTitle: "Connection Error",
  errorSessionMismatchTitle: "Session Mismatch",
  errorDefaultTitle: "Error",

  // Error screen descriptions
  errorInvalidTokenDescription:
    "The session token is invalid. Please try again.",
  errorExpiredTokenDescription:
    "Your session has expired. Please refresh and try again.",
  errorNetworkDescription:
    "Unable to connect to the server. Please check your connection.",
  errorSessionMismatchDescription:
    "The session ID does not match. Please try again.",

  // Buttons
  buttonRetry: "Retry",
  buttonClose: "Close",

  // Footer
  poweredBy: "Powered by",
};

interface ThemeContextValue {
  theme: ConnectTheme;
  setTheme: (theme: ConnectTheme) => void;
  resolvedMode: "dark" | "light";
  colors: Required<ThemeColors>;
  labels: Required<ConnectLabels>;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
  initialTheme?: ConnectTheme;
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setTheme] = useState<ConnectTheme | null>(initialTheme ?? null);
  const [systemPrefersDark, setSystemPrefersDark] = useState(true);
  const isPending = theme === null;

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
      primaryHover: "transparent",
      secondary: "transparent",
      secondaryHover: "transparent",
      border: "transparent",
      success: "transparent",
      error: "transparent",
    }),
    [],
  );

  // Merge custom colors with defaults
  const colors: Required<ThemeColors> = useMemo(() => {
    if (isPending) return pendingColors;
    const defaultColors =
      resolvedMode === "dark" ? defaultDarkColors : defaultLightColors;
    const customColors = theme?.colors?.[resolvedMode] ?? {};

    return {
      ...defaultColors,
      ...customColors,
    };
  }, [resolvedMode, theme, isPending, pendingColors]);

  // Merge custom labels with defaults
  const labels: Required<ConnectLabels> = useMemo(() => {
    const customLabels = theme?.labels ?? {};
    return {
      ...defaultLabels,
      ...customLabels,
    };
  }, [theme]);

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
    }),
    [theme, setThemeStable, resolvedMode, colors, labels],
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
export { defaultDarkColors, defaultLabels, defaultLightColors };
