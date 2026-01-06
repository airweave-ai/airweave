import { useSyncExternalStore } from "react";
import { aq as useUISettings } from "./router-BGxBdlkD.mjs";
const mediaQuery = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
function subscribeToSystemTheme(callback) {
  mediaQuery?.addEventListener("change", callback);
  return () => mediaQuery?.removeEventListener("change", callback);
}
function getSystemThemeSnapshot() {
  return mediaQuery?.matches ?? false;
}
function getSystemThemeServerSnapshot() {
  return true;
}
function useIsDark() {
  const theme = useUISettings((state) => state.theme);
  const systemPrefersDark = useSyncExternalStore(
    subscribeToSystemTheme,
    getSystemThemeSnapshot,
    getSystemThemeServerSnapshot
  );
  if (theme === "system") {
    return systemPrefersDark;
  }
  return theme === "dark";
}
export {
  useIsDark as u
};
