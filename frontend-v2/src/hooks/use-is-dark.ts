import { useSyncExternalStore } from "react";
import { useUISettings } from "../stores/ui-settings";

const mediaQuery =
  typeof window !== "undefined"
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;

function subscribeToSystemTheme(callback: () => void) {
  mediaQuery?.addEventListener("change", callback);
  return () => mediaQuery?.removeEventListener("change", callback);
}

function getSystemThemeSnapshot() {
  return mediaQuery?.matches ?? false;
}

function getSystemThemeServerSnapshot() {
  // Default to dark on server (matches the app's default theme)
  return true;
}

/**
 * Hook that returns whether dark mode is currently active.
 * Handles both explicit theme preference and system theme detection.
 * Reactively updates when theme preference or system preference changes.
 */
export function useIsDark(): boolean {
  const theme = useUISettings((state) => state.theme);

  // Subscribe to system theme changes using useSyncExternalStore
  const systemPrefersDark = useSyncExternalStore(
    subscribeToSystemTheme,
    getSystemThemeSnapshot,
    getSystemThemeServerSnapshot
  );

  // Derive dark mode based on theme setting
  if (theme === "system") {
    return systemPrefersDark;
  }
  return theme === "dark";
}
