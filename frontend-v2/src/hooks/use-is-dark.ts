import { useEffect, useState } from "react";
import { useUISettings } from "../stores/ui-settings";

/**
 * Hook that returns whether dark mode is currently active.
 * Handles both explicit theme preference and system theme detection.
 * Reactively updates when theme preference or system preference changes.
 */
export function useIsDark(): boolean {
  const theme = useUISettings((state) => state.theme);
  const [isDark, setIsDark] = useState(() => {
    if (theme === "system") {
      return (
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      );
    }
    return theme === "dark";
  });

  useEffect(() => {
    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      setIsDark(mediaQuery.matches);

      const handleChange = (e: MediaQueryListEvent) => {
        setIsDark(e.matches);
      };

      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    } else {
      setIsDark(theme === "dark");
    }
  }, [theme]);

  return isDark;
}

