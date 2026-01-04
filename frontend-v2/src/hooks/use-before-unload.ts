import { useEffect } from "react";

/**
 * Hook that shows a browser warning when the user tries to leave/refresh the page.
 *
 * @param shouldWarn - Whether to show the warning (pass a boolean or a function that returns one)
 *
 * @example
 * ```tsx
 * // Warn when form is dirty
 * useBeforeUnload(isDirty);
 *
 * // Warn based on condition
 * useBeforeUnload(!hasOrganizations);
 *
 * // With callback
 * useBeforeUnload(() => formState.isDirty);
 * ```
 */
export function useBeforeUnload(shouldWarn: boolean | (() => boolean)) {
  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      const warn = typeof shouldWarn === "function" ? shouldWarn() : shouldWarn;

      if (warn) {
        event.preventDefault();
        // Modern browsers ignore custom messages, but returnValue is still required
        event.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [shouldWarn]);
}

