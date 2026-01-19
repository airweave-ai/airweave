import { useCallback, useState } from "react";

/**
 * Hook that syncs React state with localStorage.
 * Reads initial value from localStorage and persists changes.
 *
 * @param key - The localStorage key
 * @param defaultValue - Default value if nothing is stored
 *
 * @example
 * ```tsx
 * const [isExpanded, setIsExpanded] = useLocalStorageState("panel-expanded", true);
 * const [activeTab, setActiveTab] = useLocalStorageState<"a" | "b">("active-tab", "a");
 * ```
 */
export function useLocalStorageState<T>(
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }

    try {
      const stored = localStorage.getItem(key);
      if (stored === null) {
        return defaultValue;
      }

      if (typeof defaultValue === "boolean") {
        return (stored === "true") as T;
      }
      if (typeof defaultValue === "number") {
        const num = parseFloat(stored);
        return (isNaN(num) ? defaultValue : num) as T;
      }
      if (typeof defaultValue === "string") {
        return stored as T;
      }

      return JSON.parse(stored) as T;
    } catch {
      return defaultValue;
    }
  });

  const setStateWithStorage = useCallback(
    (value: T | ((prev: T) => T)) => {
      setState((prev) => {
        const nextValue =
          typeof value === "function" ? (value as (prev: T) => T)(prev) : value;

        try {
          if (typeof nextValue === "object") {
            localStorage.setItem(key, JSON.stringify(nextValue));
          } else {
            localStorage.setItem(key, String(nextValue));
          }
        } catch {
          // Ignore localStorage errors (e.g., quota exceeded, private browsing)
        }

        return nextValue;
      });
    },
    [key]
  );

  return [state, setStateWithStorage];
}
